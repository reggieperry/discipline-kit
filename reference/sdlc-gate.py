#!/usr/bin/env python3
"""SDLC differential gate: capture and compare static-analysis baselines.

Toolchains
----------
One engine, per-toolchain scanners (a scanner-plugin layer). The engine — the
baseline/diff worktree model, the (file, code) multiset identity, rename tracking,
the relocation-advisory downgrade, the waiver system, and the verdict logic — is
language-agnostic. Each `Toolchain` supplies the scanners: a set of static-analysis
error-identity scanners (Check A), a suppression scan (Check B), and a test-weakening
scan (Check D). Detection is by marker file (`build.sbt` → scala, `pom.xml`/`build.gradle` → java,
`pyproject.toml` → python); `--toolchain` forces it.

  python  ruff / mypy / bandit; `#type:ignore`/`#noqa`/`#pyright:ignore`/`#nosec`;
          pytest skip markers + assert-keyword counts.
  scala   scalafix / wartremover (sbt; skipped by --no-static); `@nowarn`/
          `@SuppressWarnings`/`// scalafix:off`; munit `.ignore`/`munitIgnore`/
          `assume(false)` + assertion-site counts (assertEquals/assert/intercept/`:|`)
          + ScalaCheck-parameter weakening (minSuccessfulTests fall, maxDiscardRatio
          rise, forAllNoShrink). Plus a fail-closed compile precondition (Check Build:
          a non-compiling tree blocks rather than reading as clean, since a red build
          silences the linters) and, opt-in via `--coverage`, a scoverage coverage-drop
          scan (Check D). Spec: the kit's own scala-testing.md/scala-security.md.
  java    checkstyle (google_checks, Check A source scan); @SuppressWarnings/
          @SuppressFBWarnings/`//CHECKSTYLE:OFF`/`//NOPMD`; JUnit @Disabled/@Ignore +
          assertion sites (assertEquals/assertThat/assertThrows/fail) + jqwik parameter
          weakening (tries fall, ShrinkingMode.OFF appear — the shrinking key ALWAYS
          emitted so 0→1 is caught). Shared fail-closed compile precondition (mvn/gradle)
          and, opt-in via `--coverage`, a JaCoCo per-directory coverage-drop scan. SpotBugs
          (bytecode) fails CLOSED on a source-only tree; its default-path wiring awaits a
          compiled pilot. Spec: the kit's own java-* rules (v1.3.0).

Subcommands
-----------
baseline   Run the detected toolchain's scanners against the current working tree.
           Caller has typically checked out the merge-base SHA in a scratch worktree
           before invoking. Output is a directory of JSON files for diff to consume
           (static-<label>.json, suppressions.json, test-weakening.json, sha.txt,
           toolchain.txt). `--no-static` skips the sbt/uv static scanners (fast,
           regex-only); use the same flag on diff.

diff       Run the same scans on the current branch tip and compare against a
           previously captured baseline directory. Emits a JSON verdict:
           pass, advisory, or fail. Exits 0 on pass/advisory, 1 on fail, and 2 on an
           operational failure (e.g. a --coverage scan that could not complete —
           fail-closed, never read as "no coverage to check").

Identity model
--------------
Per-error identity is the (file, error-code) pair. Message text is dropped
because mypy and several ruff codes embed type names or other contextual
detail that legitimately changes across edits without representing a new
defect. Per-(file, code) multiset comparison catches swaps within a file
between distinct error codes; within-(file, code) swaps are a known v2.4
gap (would require AST-anchored identity).

Renames are tracked via `git diff --name-status -M` and applied to baseline
file paths before comparison.

Cross-file relocations whose global-(code) net is non-positive are
downgraded to advisories rather than blocks: a worker who moves a class
from a.py to b.py without changing its error count gets a soft signal
rather than an automatic bounce.

Suppressions (#type:ignore, #noqa, #pyright:ignore, #nosec) are tracked
separately. Targeted suppressions count under their specific code keys;
blanket forms count under a "BLANKET" key. Adding a blanket suppression
where a targeted one existed registers as a new key, not a count
preservation, so scope-broadening is caught.

Note on #nosec: bandit 1.9.4 silently treats `# nosec B603,B607`
(comma-separated rule IDs) as non-matching, while `# nosec B603 B607`
(space-separated) works correctly. The gate's pattern recognizes both
forms for anti-weakening accounting — if the worker adds either, it
counts as a new suppression. The pack's templates and prose direct
operators to use the space-separated form so the in-source intent
actually takes effect at bandit-execution time.

Pytest-anti-weakening tracks per-file count of pytest skip/xfail/skipif
markers (must not increase) and assert keywords (must not decrease per
file across rename map).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

# --- Static-analysis runners --------------------------------------------------


def _rel(path: str, root: Path) -> str:
    """Return path relative to root if path is under root; else return as-is."""
    try:
        return str(Path(path).resolve().relative_to(root))
    except ValueError:
        return path


def run_ruff(root: Path) -> Counter:
    """Run ruff with JSON output. Returns Counter[(file, code)] keyed by repo-relative paths."""
    proc = subprocess.run(
        ["uv", "run", "ruff", "check", ".", "--output-format=json"],
        capture_output=True,
        text=True,
        check=False,
    )
    findings: list[dict] = []
    if proc.stdout.strip():
        try:
            findings = json.loads(proc.stdout)
        except json.JSONDecodeError:
            sys.stderr.write("sdlc-gate: ruff produced non-JSON output; treating as no findings\n")
            findings = []
    counter: Counter = Counter()
    for f in findings:
        path = _rel(f.get("filename", ""), root)
        code = f.get("code", "?")
        counter[(path, code)] += 1
    return counter


_MYPY_LINE = re.compile(r"^(?P<path>[^:]+?):\d+:.*?error:.*?\[(?P<code>[^\]]+)\]\s*$")

# mypy emits semantically-equivalent codes whose exact spelling depends on
# tree state (whether an import is resolvable, whether a stub package is
# installed in the current worktree, etc.). The per-(file, code) identity
# model in this gate sees a code flip as "lost N errors of code X, gained
# N errors of code Y" on the same line — a false-positive block. The
# normalization map collapses known-equivalent codes to a canonical key
# so the diff sees no net change when the only difference is which
# spelling mypy chose.
#
# Each entry is conservative: only codes that fire on the same underlying
# defect class for the same line. Codes that look related but actually
# distinguish different defects (e.g. `import-not-found` vs
# `import-untyped` — module-missing vs stub-missing) are NOT collapsed.
_MYPY_CODE_ALIASES: dict[str, str] = {
    # mypy 2.x split [import] into more specific subcodes. Whether a
    # given site fires as the parent or the subcode depends on tree
    # state (e.g. is the test's import target on the path when mypy
    # walks this worktree?). Observed in practice:
    # same line, baseline=`[import]`, branch=`[import-not-found]`.
    "import-not-found": "import",
}


def _normalize_mypy_code(code: str) -> str:
    """Collapse equivalent mypy codes to a canonical key for diff identity."""
    return _MYPY_CODE_ALIASES.get(code, code)


def run_mypy(root: Path) -> Counter:
    """Run mypy and parse the [error-code] suffix. Returns Counter[(file, code)] keyed by repo-relative paths.

    Applies _normalize_mypy_code to each captured code so tree-state-dependent
    code spellings (e.g. [import] vs [import-not-found]) collapse to a
    canonical key. See _MYPY_CODE_ALIASES for the conservative alias list.
    """
    proc = subprocess.run(
        ["uv", "run", "mypy", ".", "--show-error-codes", "--no-error-summary"],
        capture_output=True,
        text=True,
        check=False,
    )
    counter: Counter = Counter()
    for line in proc.stdout.splitlines():
        m = _MYPY_LINE.match(line)
        if m:
            code = _normalize_mypy_code(m.group("code"))
            counter[(_rel(m.group("path"), root), code)] += 1
    return counter


def run_bandit(root: Path) -> Counter:
    """Run bandit with JSON output. Returns Counter[(file, test_id)] keyed by repo-relative paths.

    Invokes via `uvx` so the rig is not required to carry bandit in its dev deps;
    rigs that have configured `[tool.bandit]` in `pyproject.toml` get their
    configuration honoured automatically (bandit auto-detects pyproject.toml
    from the cwd). The exit code is ignored — we only consume the JSON
    findings list, never bandit's own pass/fail signal.

    Failures to invoke bandit at all (uvx unavailable, network unreachable
    for the ephemeral install) are not treated as findings — the function
    returns an empty Counter and logs a one-line note to stderr. Rigs that
    intentionally opt out of bandit will see zero baseline and zero branch
    findings, which is a no-op for the differential gate.
    """
    # Write JSON to a temp file rather than stdout — `uvx` itself prints a
    # one-line progress indicator to stdout that contaminates the JSON when
    # bandit is invoked through it. The `-o` flag has bandit write the
    # report to a file, which we then read.
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        report_path = Path(tmp.name)
    try:
        proc = subprocess.run(
            [
                "uvx",
                "bandit",
                "-c",
                "pyproject.toml",
                "-r",
                ".",
                "-f",
                "json",
                "-o",
                str(report_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode not in (0, 1):
            # 0 = clean; 1 = findings present; anything else is an invocation problem.
            sys.stderr.write(
                f"sdlc-gate: bandit invocation returned rc={proc.returncode}; "
                "treating as no findings\n",
            )
            return Counter()
        counter: Counter = Counter()
        try:
            report = json.loads(report_path.read_text() or "{}")
        except (json.JSONDecodeError, OSError):
            sys.stderr.write(
                "sdlc-gate: bandit produced non-JSON output; treating as no findings\n",
            )
            return counter
        for finding in report.get("results", []):
            path = _rel(finding.get("filename", ""), root)
            code = finding.get("test_id", "?")
            counter[(path, code)] += 1
        return counter
    finally:
        report_path.unlink(missing_ok=True)


# --- Suppression scan ---------------------------------------------------------


_SUPPRESSION_PATTERNS: list[tuple[re.Pattern, callable]] = [
    (
        re.compile(r"#\s*type:\s*ignore\[(?P<code>[^\]]+)\]"),
        lambda m: f"type:ignore[{m.group('code').strip()}]",
    ),
    (
        re.compile(r"#\s*type:\s*ignore(?!\[)"),
        lambda m: "type:ignore[BLANKET]",
    ),
    (
        re.compile(r"#\s*noqa:\s*(?P<code>[A-Za-z0-9, ]+)"),
        lambda m: f"noqa[{m.group('code').strip()}]",
    ),
    (
        re.compile(r"#\s*noqa(?![:\w])"),
        lambda m: "noqa[BLANKET]",
    ),
    (
        re.compile(r"#\s*pyright:\s*ignore"),
        lambda m: "pyright:ignore",
    ),
    # nosec — both forms recognised so workers cannot weaken by suppressing
    # findings. Space-separated rule IDs work at bandit-execution time;
    # comma-separated is silently broken in bandit 1.9.4 but the worker
    # adding either is the act we want to catch.
    (
        re.compile(r"#\s*nosec\s+(?P<code>B\d+(?:[ ,]+B\d+)*)\b"),
        lambda m: f"nosec[{m.group('code').strip()}]",
    ),
    (
        # Blanket: no `:` or word char immediately after (`# nosec:foo` and
        # `# nosec` followed by alnum aren't blanket forms), AND no
        # whitespace-then-B-digit (those are the targeted form handled above).
        re.compile(r"#\s*nosec(?![:\w])(?!\s+B\d)"),
        lambda m: "nosec[BLANKET]",
    ),
]


def _walk_python(root: Path):
    """Yield .py files under root, skipping hidden dirs, .venv, build dirs."""
    skip = {
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".gc",
        "build",
        "dist",
        ".git",
    }
    for path in root.rglob("*.py"):
        if any(part in skip or part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue
        yield path


def scan_suppressions(root: Path) -> Counter:
    """Scan all .py files for suppression directives.

    Returns Counter[(relative_path, directive_key)].
    """
    counter: Counter = Counter()
    for path in _walk_python(root):
        rel = str(path.relative_to(root))
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, extract in _SUPPRESSION_PATTERNS:
            for m in pattern.finditer(text):
                counter[(rel, extract(m))] += 1
    return counter


# --- Pytest weakening scan ----------------------------------------------------


_SKIP_MARKER = re.compile(r"@pytest\.mark\.(?:skip|xfail|skipif)(?:\(|\b)")
_ASSERT_KEYWORD = re.compile(r"\bassert\b")


def scan_pytest_weakening(root: Path) -> dict:
    """Per-test-file counts of skip markers and assert statements.

    Returns {"skips": {path: count}, "asserts": {path: count}}.
    """
    skips: dict[str, int] = {}
    asserts: dict[str, int] = {}
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return {"skips": skips, "asserts": asserts}
    for path in tests_dir.rglob("*.py"):
        rel = str(path.relative_to(root))
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        skips[rel] = len(_SKIP_MARKER.findall(text))
        asserts[rel] = len(_ASSERT_KEYWORD.findall(text))
    return {"skips": skips, "asserts": asserts}


# --- Scala scanners (port: same engine, sbt/regex scanners in place of uv) -----
# Spec source: the kit's own scala-security.md (suppressions + lint/security tools)
# and scala-testing.md §"Anti-weakening" (the test-weakening vectors). The port
# consumes that spec; it does not invent one.


def _walk_scala(root: Path):
    """Yield .scala/.sc files under root, skipping build/tool dirs."""
    skip = {"target", ".bloop", ".metals", ".bsp", ".git", "project", "node_modules",
            ".idea", ".vscode"}
    for path in list(root.rglob("*.scala")) + list(root.rglob("*.sc")):
        parts = path.relative_to(root).parts[:-1]
        if any(p in skip or p.startswith(".") for p in parts):
            continue
        yield path


# Suppression directives (scala-security.md): a bare `@nowarn` is the BLANKET key,
# a filtered `@nowarn("...")` a targeted key (scope-broadening from targeted to
# blanket registers as a new key, not a preserved count — same catch as the Python
# side); `@SuppressWarnings(Array(...))`; `// scalafix:off` (blanket or per-rule).
_NOWARN = r"@(?:scala\.)?(?:annotation\.)?nowarn"
_SCALA_SUPPRESSION_PATTERNS: list[tuple[re.Pattern, callable]] = [
    (re.compile(_NOWARN + r"\(\s*\"(?P<a>[^\"]*)\"\s*\)"), lambda m: f"nowarn[{m.group('a').strip()}]"),
    (re.compile(_NOWARN + r"(?!\s*\()"), lambda m: "nowarn[BLANKET]"),
    (re.compile(r"@SuppressWarnings\(\s*Array\((?P<a>[^)]*)\)\s*\)"),
     lambda m: f"SuppressWarnings[{' '.join(m.group('a').split())}]"),
    (re.compile(r"//\s*scalafix:off\s+(?P<r>\S+)"), lambda m: f"scalafix:off[{m.group('r')}]"),
    (re.compile(r"//\s*scalafix:off\s*$", re.M), lambda m: "scalafix:off[BLANKET]"),
]


def scan_scala_suppressions(root: Path) -> Counter:
    """Counter[(relative_path, directive_key)] over all .scala/.sc files."""
    counter: Counter = Counter()
    for path in _walk_scala(root):
        rel = str(path.relative_to(root))
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, extract in _SCALA_SUPPRESSION_PATTERNS:
            for m in pattern.finditer(text):
                counter[(rel, extract(m))] += 1
    return counter


# munit skip forms (scala-testing.md — the framework is munit, so no scalatest forms):
# `.ignore`, `assume(false, ...)`, `munitIgnore`.
_SCALA_SKIP = re.compile(r"\.ignore\b|\bmunitIgnore\b|\bassume\s*\(\s*false\b")
# assertion sites: assertEquals / assert( / assertEqualsDouble / assertNotEquals /
# intercept[ / a labeled `:|` conjunct. `\bassert\s*\(` does not match `assertEquals(`
# (no word boundary mid-identifier), so the forms count without overlap.
_SCALA_ASSERT = re.compile(
    r"\bassertEqualsDouble\b|\bassertNotEquals\b|\bassertEquals\b|\bassert\s*\(|"
    r"\bintercept\s*\[|:\|"
)
_SC_MIN = re.compile(r"(?:withMinSuccessfulTests\(|minSuccessfulTests\s*=\s*)(\d+)")
_SC_MAXDISCARD = re.compile(r"(?:withMaxDiscardRatio\(|maxDiscardRatio\s*=\s*)([\d.]+)")
_SC_NOSHRINK = re.compile(r"\bforAllNoShrink\b")


def _scala_is_test_file(rel: str) -> bool:
    return "/src/test/" in ("/" + rel) or rel.startswith("src/test/")


def scan_scala_test_weakening(root: Path) -> dict:
    """Per-test-file counts of skip markers and assertion sites, plus ScalaCheck
    parameter values. Returns {skips:{file:n}, asserts:{file:n}, params:{file:{...}}}.
    The engine's Check D handles skips (no-increase) + asserts (no-decrease) exactly
    as it does for pytest; the params sub-map drives a Scala-specific value check
    (minSuccessfulTests must not fall, maxDiscardRatio must not rise, forAllNoShrink
    must not appear/grow)."""
    skips: dict[str, int] = {}
    asserts: dict[str, int] = {}
    params: dict[str, dict] = {}
    for path in _walk_scala(root):
        rel = str(path.relative_to(root))
        if not _scala_is_test_file(rel):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        skips[rel] = len(_SCALA_SKIP.findall(text))
        asserts[rel] = len(_SCALA_ASSERT.findall(text))
        mins = [int(x) for x in _SC_MIN.findall(text)]
        maxd = [float(x) for x in _SC_MAXDISCARD.findall(text)]
        p: dict = {}
        if mins:
            p["minSuccessfulTests"] = min(mins)     # the weakest (lowest) floor in the file
        if maxd:
            p["maxDiscardRatio"] = max(maxd)        # the loosest (highest) discard cap
        noshrink = len(_SC_NOSHRINK.findall(text))
        if noshrink:
            p["forAllNoShrink"] = noshrink
        if p:
            params[rel] = p
    return {"skips": skips, "asserts": asserts, "params": params}


def _sbt_json_or_empty(root: Path, sbt_args: list[str], parse) -> Counter:
    """Shell out to sbt like the Python scanners shell out to uv, and parse. ANY
    invocation problem (sbt absent, plugin unconfigured, non-zero for a non-finding
    reason) returns an empty Counter with a one-line note — a repo that has not wired
    the lint toolchain sees a no-op differential, exactly like a rig that skips
    bandit. The regex scanners above are always available and carry the anti-weakening
    vectors the acceptance exercises; these add Check-A coverage when sbt is wired."""
    try:
        proc = subprocess.run(["sbt", "-batch", "-Dsbt.color=false", *sbt_args],
                              cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        sys.stderr.write(f"sdlc-gate: sbt {' '.join(sbt_args)} could not run; treating as no findings\n")
        return Counter()
    return parse(proc.stdout + proc.stderr, root)


def _parse_scalafix(out: str, root: Path) -> Counter:
    """scalafix --check emits `<path>:<line>:<col>: <level>: [<Rule>] <msg>`."""
    counter: Counter = Counter()
    pat = re.compile(r"^(?P<path>[^:\n]+\.scala):\d+:\d+:\s+\w+:\s+\[(?P<rule>[^\]]+)\]")
    for line in out.splitlines():
        m = pat.match(line.strip().removeprefix("[error] ").removeprefix("[warn] "))
        if m:
            counter[(_rel(m.group("path"), root), m.group("rule").strip())] += 1
    return counter


def _parse_wartremover(out: str, root: Path) -> Counter:
    """WartRemover warnings carry the wart name in the message, e.g.
    `[warn] <path>:<line>: <msg> [wartremover:Null]` or `... Wart: Null`."""
    counter: Counter = Counter()
    pat = re.compile(r"(?P<path>[^\s:]+\.scala):\d+.*?(?:wartremover:|Wart\.?\s*)(?P<wart>[A-Za-z]+)")
    for line in out.splitlines():
        m = pat.search(line)
        if m:
            counter[(_rel(m.group("path"), root), m.group("wart"))] += 1
    return counter


def run_scalafix(root: Path) -> Counter:
    return _sbt_json_or_empty(root, ["scalafix --check"], _parse_scalafix)


def run_wartremover(root: Path) -> Counter:
    return _sbt_json_or_empty(root, ["-Dgate.wartScan=true", "Test/compile"], _parse_wartremover)


# --- The fail-closed compile precondition (Check Build) ------------------------
# A red build silences the linters, so `_sbt_json_or_empty` parses an output that carries
# no scalafix/wartremover findings and returns an empty Counter — which the diff reads as
# "no new errors" and PASSES a tree that does not even compile (a fail-open). The precondition
# closes it: compile both source sets first; if either the branch or the baseline does not
# compile, block on Build/compile_error rather than trusting an empty scan.


def _compile_precondition_blocks(branch_status: str, baseline_status: str) -> list[dict]:
    """Fail-closed: if either tree does not compile, the linters could not have run, so
    'no new findings' is meaningless — block. 'skip' (sbt not invokable / no toolchain wired)
    is a no-op, matching the existing sbt-absent scanner behavior."""
    failed = [w for w, s in (("branch", branch_status), ("baseline", baseline_status)) if s == "fail"]
    if failed:
        return [{
            "check": "Build", "kind": "compile_error",
            "items": [{"which": w, "detail": "the tree does not compile"} for w in failed],
        }]
    return []


def sbt_compile_status(root: Path) -> str:
    """Run `sbt Test/compile` (compiles BOTH the main and test source sets). Returns 'ok'
    (compiles), 'fail' (does not compile), or 'skip' (sbt not invokable — a no-op, exactly
    like the sbt-absent path of the static scanners)."""
    try:
        proc = subprocess.run(["sbt", "-batch", "-Dsbt.color=false", "Test/compile"],
                              cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        sys.stderr.write("sdlc-gate: sbt Test/compile could not run; skipping the compile precondition\n")
        return "skip"
    return "ok" if proc.returncode == 0 else "fail"


# --- scoverage coverage-drop scan (Check D coverage) --------------------------
# scala-testing.md advertises "the differential gate scores coverage against the merge-base";
# without a scanner that promise is fail-open (a coverage regression sails through). Ported
# from the Scala gate's CoverageScan: parse scoverage.xml into a per-package-directory map,
# diff against the baseline, block a drop beyond COVERAGE_EPSILON. Coverage is heavy (an
# instrumented clean + full test run per tree), so it is opt-in behind --coverage.

COVERAGE_EPSILON = 0.5  # percentage points; a per-directory drop beyond this is a hard block


class CoverageOperationalError(RuntimeError):
    """Coverage was requested but the instrumented run could not produce a report. Fail-closed
    (exit 2): a failed scan must never be read as 'no coverage to check', which would silently
    disable the coverage-drop block on that tree."""


def _dir_of(p: str) -> str:
    i = p.rfind("/")
    return p[:i] if i >= 0 else "."


def parse_scoverage(xml: str, source_root: str = "src/main/scala") -> dict[str, float]:
    """Parse a scoverage.xml into {package-directory -> statement-coverage%}, keyed
    REPO-RELATIVE (source_root prefixed) so it shares the diff's path-space. The percent is
    recomputed from the integer counts (the rendered statement-rate is locale-sensitive); a
    package with zero statements is dropped, never minted as 100%. A DOCTYPE is rejected (XXE /
    entity-expansion closed) — a self-generated report never needs one."""
    if re.search(r"<!DOCTYPE", xml, re.IGNORECASE):
        raise ValueError("scoverage.xml carries a DOCTYPE; refusing to parse (XXE closed)")
    root = ET.fromstring(xml)  # ElementTree does not resolve external entities
    agg: dict[str, list[int]] = {}  # dir -> [statement-count, statements-invoked]
    for cls in root.iter("class"):
        filename = (cls.get("filename") or "").replace("\\", "/")
        if not filename:
            continue
        try:
            count = int(cls.get("statement-count", ""))
            invoked = int(cls.get("statements-invoked", ""))
        except (TypeError, ValueError):
            continue
        slot = agg.setdefault(f"{source_root}/{_dir_of(filename)}", [0, 0])
        slot[0] += count
        slot[1] += invoked
    return {d: (inv / cnt * 100.0) for d, (cnt, inv) in agg.items() if cnt > 0}


def _find_scoverage_xml(root: Path) -> Path | None:
    """The root project's scoverage.xml under a target/**/scoverage-report/ directory, walked
    (not hardcoded) so a Scala-version bump does not break it."""
    target = root / "target"
    if not target.is_dir():
        return None
    for p in target.rglob("scoverage.xml"):
        if p.parent.name == "scoverage-report":
            return p
    return None


def run_coverage(root: Path) -> dict[str, float]:
    """Run scoverage over `root` and read its report into the per-directory coverage map.
    FAIL-CLOSED: if the instrumented run cannot produce a report, raise
    CoverageOperationalError rather than returning an empty map. A clean run with no report is
    the only legitimate empty (nothing instrumented). `clean` is required — the coverage switch
    changes scalacOptions, and a stale non-instrumented compile would report the wrong numbers."""
    try:
        proc = subprocess.run(
            ["sbt", "-batch", "-Dsbt.color=false", "clean", "coverage", "test", "coverageReport"],
            cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CoverageOperationalError(f"coverage scan could not run: {e}") from e
    report = _find_scoverage_xml(root)
    if report is None:
        if proc.returncode != 0:
            raise CoverageOperationalError(
                f"coverage scan did not complete (sbt exit {proc.returncode}) and produced no report "
                "— refusing to read coverage as empty (fail-closed)")
        return {}
    try:
        return parse_scoverage(report.read_text())
    except OSError as e:
        raise CoverageOperationalError(f"coverage report unreadable: {e}") from e


def _translate_pkg(pkg: str, rename_map: dict[str, str]) -> str:
    """Directory reconciliation for the coverage diff: if every renamed file under `pkg` moved
    to one new directory, follow it (a rename `pkg/X.scala -> newdir/X.scala` implies
    `pkg -> newdir`), so a whole-package move does not false-positive as a coverage drop.
    Returns `pkg` unchanged when there is no single consistent target."""
    targets = {_dir_of(new) for old, new in rename_map.items() if _dir_of(old) == pkg}
    return next(iter(targets)) if len(targets) == 1 else pkg


def _diff_coverage(branch_cov: dict[str, float], baseline_cov: dict[str, float],
                   rename_map: dict[str, str], epsilon: float) -> list[dict]:
    """Check D coverage-drop: for each baseline package-directory, its branch coverage
    (reconciled through the file rename map) must not vanish and must not fall more than
    epsilon. A new package is not a drop."""
    items: list[dict] = []
    for pkg in sorted(baseline_cov):
        base_cov = baseline_cov[pkg]
        bc = branch_cov.get(pkg)
        if bc is None:
            bc = branch_cov.get(_translate_pkg(pkg, rename_map))
        if bc is None:
            items.append({"package": pkg, "baseline": round(base_cov, 1), "branch": None})
        elif bc < base_cov - epsilon:
            items.append({"package": pkg, "baseline": round(base_cov, 1), "branch": round(bc, 1)})
    if items:
        return [{"check": "D.coverage", "kind": "coverage_drop", "items": items}]
    return []


# --- Java toolchain scanners (v1.3.0) -----------------------------------------
# Java is a scanner-plugin: NO engine change. Source-based scanners (Checkstyle Check A,
# suppression Check B, test-weakening Check D incl. jqwik parameter values) mirror the Scala
# side; the compile-precondition and coverage seams are shared and toolchain-generic. SpotBugs
# (bytecode) fails CLOSED on a source-only tree rather than scanning empty and passing.


def _walk_java(root: Path):
    """Yield .java files under root, skipping build/tool dirs."""
    skip = {"target", "build", "out", "bin", ".git", "node_modules", ".idea", ".vscode", ".gradle"}
    for path in root.rglob("*.java"):
        parts = path.relative_to(root).parts[:-1]
        if any(p in skip or p.startswith(".") for p in parts):
            continue
        yield path


def _java_quoted_or_blanket(inner: str) -> str:
    vals = re.findall(r'"([^"]*)"', inner)
    return " ".join(vals) if vals else "BLANKET"


# Suppression directives (brief §1): @SuppressWarnings / @SuppressFBWarnings (SpotBugs) /
# //CHECKSTYLE:OFF / //NOPMD. A targeted directive is its own key; broadening targeted→blanket
# registers as a new key, not a preserved count — the same catch as the Python/Scala sides.
_JAVA_SUPPRESSION_PATTERNS: list[tuple[re.Pattern, callable]] = [
    (re.compile(r"@SuppressWarnings\((?P<a>[^)]*)\)"),
     lambda m: f"SuppressWarnings[{_java_quoted_or_blanket(m.group('a'))}]"),
    (re.compile(r"@SuppressFBWarnings\((?P<a>[^)]*)\)"),
     lambda m: f"SuppressFBWarnings[{_java_quoted_or_blanket(m.group('a'))}]"),
    (re.compile(r"//\s*CHECKSTYLE:OFF:\s*(?P<r>\S+)"),
     lambda m: f"CHECKSTYLE:OFF[{m.group('r')}]"),
    (re.compile(r"//\s*CHECKSTYLE:OFF\s*$", re.M),
     lambda m: "CHECKSTYLE:OFF[BLANKET]"),
    (re.compile(r"//\s*NOPMD:\s*(?P<r>\S+)"),
     lambda m: f"NOPMD[{m.group('r')}]"),
    (re.compile(r"//\s*NOPMD\b(?!:)"),
     lambda m: "NOPMD[BLANKET]"),
]


def scan_java_suppressions(root: Path) -> Counter:
    """Counter[(relative_path, directive_key)] over all .java files."""
    counter: Counter = Counter()
    for path in _walk_java(root):
        rel = str(path.relative_to(root))
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, extract in _JAVA_SUPPRESSION_PATTERNS:
            for m in pattern.finditer(text):
                counter[(rel, extract(m))] += 1
    return counter


# JUnit 5 skip markers (@Disabled) + JUnit 4 @Ignore; assertion sites (JUnit + AssertJ +
# jqwik fail); jqwik property-parameter weakening (tries fall, ShrinkingMode.OFF appear).
_JAVA_SKIP = re.compile(r"@Disabled\b|@Ignore\b")
_JAVA_ASSERT = re.compile(
    r"\bassertEquals\b|\bassertNotEquals\b|\bassertTrue\b|\bassertFalse\b|"
    r"\bassertNull\b|\bassertNotNull\b|\bassertSame\b|\bassertArrayEquals\b|"
    r"\bassertThrows\b|\bassertThat\b|\bfail\s*\(")
_JQWIK_TRIES = re.compile(r"@Property\([^)]*\btries\s*=\s*(\d+)")
_JQWIK_SHRINK = re.compile(r"ShrinkingMode\.OFF")


def _java_is_test_file(rel: str) -> bool:
    return "/src/test/" in ("/" + rel) or rel.startswith("src/test/")


def scan_java_test_weakening(root: Path) -> dict:
    """Per-test-file skip-marker and assertion-site counts, plus jqwik parameter values. Returns
    {skips:{file:n}, asserts:{file:n}, params:{file:{tries?, shrinkingOff}}}. The engine's Check D
    handles skips (no-increase) + asserts (no-decrease) exactly as for pytest/munit; the params
    sub-map drives the jqwik value check (tries must not fall, shrinkingOff must not rise).
    shrinkingOff is ALWAYS emitted (default 0) so a fresh ShrinkingMode.OFF (0→1) is caught — the
    only-when-present emission is the fail-open the committee flagged on Scala's forAllNoShrink."""
    skips: dict[str, int] = {}
    asserts: dict[str, int] = {}
    params: dict[str, dict] = {}
    for path in _walk_java(root):
        rel = str(path.relative_to(root))
        if not _java_is_test_file(rel):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        skips[rel] = len(_JAVA_SKIP.findall(text))
        asserts[rel] = len(_JAVA_ASSERT.findall(text))
        p: dict = {"shrinkingOff": len(_JQWIK_SHRINK.findall(text))}  # ALWAYS emitted (see docstring)
        tries = [int(x) for x in _JQWIK_TRIES.findall(text)]
        if tries:
            p["tries"] = min(tries)   # the weakest (lowest) tries floor in the file
        params[rel] = p
    return {"skips": skips, "asserts": asserts, "params": params}


# Check A source scanner: Checkstyle (google_checks). Findings keyed (file, rule-id). Tool absent
# / not invokable → empty Counter (a repo that has not wired Checkstyle sees a no-op differential,
# exactly like the sbt-absent Scala scanners). The XML is the documented Checkstyle format; a
# DOCTYPE is rejected (XXE closed), matching parse_scoverage.
def _parse_checkstyle(xml: str, root: Path) -> Counter:
    counter: Counter = Counter()
    if not xml.strip():
        return counter
    if re.search(r"<!DOCTYPE", xml, re.IGNORECASE):
        raise ValueError("checkstyle report carries a DOCTYPE; refusing to parse (XXE closed)")
    try:
        tree = ET.fromstring(xml)
    except ET.ParseError:
        return counter
    for fileel in tree.iter("file"):
        name = (fileel.get("name") or "").replace("\\", "/")
        try:
            rel = str(Path(name).resolve().relative_to(root.resolve()))
        except ValueError:
            rel = name.lstrip("/")
        for err in fileel.iter("error"):
            source = err.get("source") or "unknown"
            rule = source.rsplit(".", 1)[-1]  # ...checks.coding.MagicNumberCheck -> MagicNumberCheck
            counter[(rel, rule)] += 1
    return counter


def run_checkstyle(root: Path) -> Counter:
    files = [str(p) for p in _walk_java(root)]
    if not files:
        return Counter()
    try:
        proc = subprocess.run(
            ["checkstyle", "-c", "/google_checks.xml", "-f", "xml", *files],
            cwd=root, capture_output=True, text=True, check=False, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        sys.stderr.write("sdlc-gate: checkstyle not invokable; skipping the Checkstyle scan\n")
        return Counter()
    try:
        return _parse_checkstyle(proc.stdout, root)
    except ValueError as e:
        sys.stderr.write(f"sdlc-gate: {e}\n")
        return Counter()


class SpotBugsOperationalError(RuntimeError):
    """SpotBugs was invoked but could not analyze — it needs compiled bytecode and none was found.
    Fail-closed (like CoverageOperationalError): a can't-run must never read as 'no bugs found',
    which would silently disable the scan on a source-only tree (the committee's catch)."""


def _spotbugs_tool_present() -> bool:
    return shutil.which("spotbugs") is not None


def _java_classes_present(root: Path) -> bool:
    for d in ("target/classes", "build/classes"):
        base = root / d
        if base.is_dir() and next(base.rglob("*.class"), None) is not None:
            return True
    return False


def _parse_spotbugs(xml: str, root: Path) -> Counter:
    counter: Counter = Counter()
    if not xml.strip():
        return counter
    if re.search(r"<!DOCTYPE", xml, re.IGNORECASE):
        raise ValueError("spotbugs report carries a DOCTYPE; refusing to parse (XXE closed)")
    try:
        tree = ET.fromstring(xml)
    except ET.ParseError:
        return counter
    for bug in tree.iter("BugInstance"):
        kind = bug.get("type") or "unknown"
        src = bug.find(".//SourceLine")
        name = (src.get("sourcepath") if src is not None else None) or "unknown"
        counter[(name.replace("\\", "/"), kind)] += 1
    return counter


def run_spotbugs(root: Path) -> Counter:
    """Tool absent → empty (a clean skip, an unwired scanner). Tool PRESENT but no bytecode →
    SpotBugsOperationalError (fail-closed). Bytecode present → findings keyed (file, bug-pattern);
    that real-invocation path is exercised by a compiled pilot, not the source-only fixtures."""
    if not _spotbugs_tool_present():
        return Counter()
    if not _java_classes_present(root):
        raise SpotBugsOperationalError(
            "spotbugs is installed but no compiled classes were found (target/classes or "
            "build/classes) — refusing to scan a source-only tree and pass (fail-closed)")
    try:
        proc = subprocess.run(
            ["spotbugs", "-textui", "-xml:withMessages", "-low", str(root)],
            cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise SpotBugsOperationalError(f"spotbugs could not run: {e}") from e
    return _parse_spotbugs(proc.stdout, root)


def java_compile_status(root: Path) -> str:
    """mvn (default) or the Gradle wrapper → 'ok'/'fail'/'skip'. Hermetic: a scoped compile, no
    daemon (a daemon inside a pre-commit hook is a hermeticity defect). 'skip' when no build tool
    is invokable (a no-op, like the sbt-absent path)."""
    if (root / "pom.xml").exists():
        cmd = ["mvn", "-B", "-q", "-DskipTests", "test-compile"]
    elif (root / "gradlew").exists():
        cmd = ["./gradlew", "--no-daemon", "--console=plain", "testClasses"]
    elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        cmd = ["gradle", "--no-daemon", "--console=plain", "testClasses"]
    else:
        return "skip"
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        sys.stderr.write("sdlc-gate: java compile could not run; skipping the compile precondition\n")
        return "skip"
    return "ok" if proc.returncode == 0 else "fail"


# JaCoCo coverage (opt-in --coverage), mirroring scoverage: per-directory statement coverage,
# fail-closed on an operational failure. The XML is the documented JaCoCo report format.
def parse_jacoco(xml: str, source_root: str = "src/main/java") -> dict[str, float]:
    if re.search(r"<!DOCTYPE", xml, re.IGNORECASE):
        raise ValueError("jacoco.xml carries a DOCTYPE; refusing to parse (XXE closed)")
    tree = ET.fromstring(xml)
    agg: dict[str, list[int]] = {}  # dir -> [covered, missed] for LINE
    for pkg in tree.iter("package"):
        pkgname = (pkg.get("name") or "").replace("\\", "/")
        key = f"{source_root}/{pkgname}" if pkgname else source_root
        for sf in pkg.iter("sourcefile"):
            for ctr in sf.findall("counter"):
                if ctr.get("type") != "LINE":
                    continue
                try:
                    covered = int(ctr.get("covered", ""))
                    missed = int(ctr.get("missed", ""))
                except (TypeError, ValueError):
                    continue
                slot = agg.setdefault(key, [0, 0])
                slot[0] += covered
                slot[1] += missed
    return {d: (cov / (cov + mis) * 100.0) for d, (cov, mis) in agg.items() if (cov + mis) > 0}


def _find_jacoco_xml(root: Path) -> Path | None:
    for rel in ("target/site/jacoco/jacoco.xml", "build/reports/jacoco/test/jacocoTestReport.xml"):
        p = root / rel
        if p.is_file():
            return p
    return next(root.rglob("jacoco*.xml"), None)


def run_jacoco_coverage(root: Path) -> dict[str, float]:
    report = _find_jacoco_xml(root)
    if report is None:
        raise CoverageOperationalError(
            "jacoco report not found (target/site/jacoco or build/reports/jacoco) — refusing to "
            "read coverage as empty (fail-closed); run the build's jacoco report goal first")
    try:
        return parse_jacoco(report.read_text())
    except OSError as e:
        raise CoverageOperationalError(f"jacoco report unreadable: {e}") from e


# --- Toolchain plugins (one engine, per-toolchain scanners) --------------------


class Toolchain:
    """A per-language scanner set the engine drives uniformly. `static_labels` names
    the error-identity scanners (Check A); the rest map 1:1 to the Python originals."""

    name = "base"
    static_labels: list[str] = []
    param_directions: dict[str, str] = {}  # scalacheck: key -> "min" (no-fall) | "max" (no-rise)

    def detect(self, root: Path) -> bool:
        return False

    def static_analysis(self, root: Path) -> dict[str, Counter]:
        return {}

    def normalize(self, label: str, counter: Counter) -> Counter:
        return counter

    def suppressions(self, root: Path) -> Counter:
        return Counter()

    def test_weakening(self, root: Path) -> dict:
        return {"skips": {}, "asserts": {}, "params": {}}

    def compile_check(self, root: Path) -> str:
        """'ok' | 'fail' | 'skip' — the fail-closed compile precondition. Base: no compile step."""
        return "skip"

    def coverage(self, root: Path) -> dict[str, float]:
        """Per-package-directory statement coverage for the opt-in Check D coverage-drop. Base: none."""
        return {}

    def is_test_file(self, rel: str) -> bool:
        return rel.startswith("tests/")


class PythonToolchain(Toolchain):
    name = "python"
    static_labels = ["ruff", "mypy", "bandit"]

    def detect(self, root: Path) -> bool:
        return (root / "pyproject.toml").exists() or (root / "setup.py").exists()

    def static_analysis(self, root: Path) -> dict[str, Counter]:
        return {"ruff": run_ruff(root), "mypy": run_mypy(root), "bandit": run_bandit(root)}

    def normalize(self, label: str, counter: Counter) -> Counter:
        if label != "mypy":
            return counter
        out: Counter = Counter()
        for (file, code), n in counter.items():
            out[(file, _normalize_mypy_code(code))] += n
        return out

    def suppressions(self, root: Path) -> Counter:
        return scan_suppressions(root)

    def test_weakening(self, root: Path) -> dict:
        d = scan_pytest_weakening(root)
        d.setdefault("params", {})
        return d

    def is_test_file(self, rel: str) -> bool:
        return rel.startswith("tests/")


class ScalaToolchain(Toolchain):
    name = "scala"
    static_labels = ["scalafix", "wartremover"]
    param_directions = {"minSuccessfulTests": "min", "maxDiscardRatio": "max",
                        "forAllNoShrink": "max"}

    def detect(self, root: Path) -> bool:
        return (root / "build.sbt").exists()

    def static_analysis(self, root: Path) -> dict[str, Counter]:
        return {"scalafix": run_scalafix(root), "wartremover": run_wartremover(root)}

    def suppressions(self, root: Path) -> Counter:
        return scan_scala_suppressions(root)

    def test_weakening(self, root: Path) -> dict:
        return scan_scala_test_weakening(root)

    def compile_check(self, root: Path) -> str:
        return sbt_compile_status(root)

    def coverage(self, root: Path) -> dict[str, float]:
        return run_coverage(root)

    def is_test_file(self, rel: str) -> bool:
        return _scala_is_test_file(rel)


class JavaToolchain(Toolchain):
    name = "java"
    static_labels = ["checkstyle"]  # SpotBugs is bytecode/opt-in (fail-closed); not a default label
    param_directions = {"tries": "min", "shrinkingOff": "max"}

    def detect(self, root: Path) -> bool:
        return ((root / "pom.xml").exists() or (root / "build.gradle").exists()
                or (root / "build.gradle.kts").exists())

    def static_analysis(self, root: Path) -> dict[str, Counter]:
        return {"checkstyle": run_checkstyle(root)}

    def suppressions(self, root: Path) -> Counter:
        return scan_java_suppressions(root)

    def test_weakening(self, root: Path) -> dict:
        return scan_java_test_weakening(root)

    def compile_check(self, root: Path) -> str:
        return java_compile_status(root)

    def coverage(self, root: Path) -> dict[str, float]:
        return run_jacoco_coverage(root)

    def is_test_file(self, rel: str) -> bool:
        return _java_is_test_file(rel)


_TOOLCHAINS = {"python": PythonToolchain(), "scala": ScalaToolchain(), "java": JavaToolchain()}


def select_toolchain(root: Path, override: str | None) -> Toolchain:
    if override:
        if override not in _TOOLCHAINS:
            sys.stderr.write(f"sdlc-gate: unknown --toolchain {override!r}\n")
            sys.exit(2)
        return _TOOLCHAINS[override]
    for tc in (ScalaToolchain(), JavaToolchain(), PythonToolchain()):
        if tc.detect(root):
            return tc
    sys.stderr.write("sdlc-gate: no toolchain detected (no build.sbt, pom.xml/build.gradle, or "
                     "pyproject.toml); pass --toolchain scala|java|python\n")
    sys.exit(2)


def _check_scalacheck_params(branch_tw: dict, baseline_tw: dict, directions: dict[str, str],
                             rename_map: dict[str, str], deleted: set[str]) -> list[dict]:
    """Value-based weakening of ScalaCheck parameters (no analog on the Python side).
    A `min` key must not fall, a `max` key must not rise, across the rename map."""
    if not directions:
        return []
    base_params = baseline_tw.get("params", {})
    branch_params = branch_tw.get("params", {})
    weakened: list[dict] = []
    for bf, bvals in base_params.items():
        if bf in deleted:
            continue
        nf = rename_map.get(bf, bf)
        nvals = branch_params.get(nf, {})
        for key, direction in directions.items():
            if key not in bvals:
                continue
            b = bvals[key]
            n = nvals.get(key, 0 if direction == "max" else b)
            if (direction == "min" and n < b) or (direction == "max" and n > b):
                weakened.append({"file": nf, "param": key, "baseline": b, "branch": n})
    if weakened:
        return [{"check": "D.scalacheck", "kind": "weakened_property_params", "items": weakened}]
    return []


# --- Serialization helpers ----------------------------------------------------


def _serialize(counter: Counter) -> list[list]:
    """JSON can't key on tuples; emit list of [file, code, count]."""
    return [[k[0], k[1], v] for k, v in sorted(counter.items())]


def _deserialize(data: list) -> Counter:
    return Counter({(f, c): n for f, c, n in data})


# --- Subcommands --------------------------------------------------------------


def cmd_baseline(args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    root = Path(args.root).resolve()
    tc = select_toolchain(root, getattr(args, "toolchain", None))

    sys.stderr.write(f"sdlc-gate: capturing {tc.name} baseline at {out_dir} (sha={args.sha})\n")
    static = {} if getattr(args, "no_static", False) else tc.static_analysis(root)
    suppressions = tc.suppressions(root)
    test_w = tc.test_weakening(root)
    # The compile precondition status travels with the baseline so diff can fail-closed on a
    # baseline that did not compile (its empty static scan is not trustworthy).
    build_status = "skip" if getattr(args, "no_static", False) else tc.compile_check(root)
    coverage: dict[str, float] = {}
    if getattr(args, "coverage", False):
        try:
            coverage = tc.coverage(root)
        except CoverageOperationalError as e:
            sys.stderr.write(f"sdlc-gate: {e}\n")
            sys.exit(2)

    for label, counter in static.items():
        (out_dir / f"static-{label}.json").write_text(json.dumps(_serialize(counter), indent=2))
    (out_dir / "suppressions.json").write_text(json.dumps(_serialize(suppressions), indent=2))
    (out_dir / "test-weakening.json").write_text(json.dumps(test_w, indent=2))
    (out_dir / "sha.txt").write_text(args.sha + "\n")
    (out_dir / "toolchain.txt").write_text(tc.name + "\n")
    (out_dir / "build.txt").write_text(build_status + "\n")
    if getattr(args, "coverage", False):
        (out_dir / "coverage.json").write_text(json.dumps(coverage, indent=2))

    sys.stdout.write(
        json.dumps(
            {
                "ok": True,
                "sha": args.sha,
                "toolchain": tc.name,
                "out_dir": str(out_dir),
                "static": {
                    label: {"total": sum(c.values()), "keys": len(c)}
                    for label, c in static.items()
                },
                "suppressions_total": sum(suppressions.values()),
                "suppressions_keys": len(suppressions),
                "skip_total": sum(test_w["skips"].values()),
                "assert_total": sum(test_w["asserts"].values()),
            },
            indent=2,
        )
        + "\n"
    )


def _git_rename_map(baseline_sha: str) -> tuple[dict[str, str], set[str]]:
    """Returns (rename_map: baseline_path -> branch_path, deleted_paths)."""
    proc = subprocess.run(
        ["git", "diff", "--name-status", "-M", f"{baseline_sha}..HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    rename_map: dict[str, str] = {}
    deleted: set[str] = set()
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            rename_map[parts[1]] = parts[2]
        elif status == "D" and len(parts) >= 2:
            deleted.add(parts[1])
    return rename_map, deleted


def _translate(counter: Counter, rename_map: dict[str, str], deleted: set[str]) -> Counter:
    """Apply rename map to baseline counter; drop entries for deleted files."""
    out: Counter = Counter()
    for (file, code), n in counter.items():
        if file in deleted:
            continue
        new_file = rename_map.get(file, file)
        out[(new_file, code)] += n
    return out


def _load_baseline_snapshots(base_dir: Path) -> dict:
    """Load the toolchain-generic baseline: per-static-label counters (normalized by
    the toolchain — e.g. mypy code aliasing), suppressions, and test-weakening.

    Falls back to the pre-port Python filenames (`ruff.json`/`mypy.json`/`bandit.json`
    /`pytest-weakening.json`, no `toolchain.txt`) so a baseline captured by the
    unported gate still loads and compares.
    """
    baseline_sha = (base_dir / "sha.txt").read_text().strip()
    tc_file = base_dir / "toolchain.txt"
    tc_name = tc_file.read_text().strip() if tc_file.exists() else "python"
    tc = _TOOLCHAINS.get(tc_name, PythonToolchain())

    static: dict[str, Counter] = {}
    for label in tc.static_labels:
        f = base_dir / f"static-{label}.json"
        if not f.exists():
            f = base_dir / f"{label}.json"  # pre-port filename
        counter = _deserialize(json.loads(f.read_text())) if f.exists() else Counter()
        static[label] = tc.normalize(label, counter)

    baseline_supp = _deserialize(json.loads((base_dir / "suppressions.json").read_text()))
    tw_path = base_dir / "test-weakening.json"
    if not tw_path.exists():
        tw_path = base_dir / "pytest-weakening.json"  # pre-port filename
    baseline_tw = json.loads(tw_path.read_text())
    baseline_tw.setdefault("params", {})
    return {
        "sha": baseline_sha,
        "toolchain": tc_name,
        "tc": tc,
        "static": static,
        "supp": baseline_supp,
        "tw": baseline_tw,
    }


def _diff_errors(
    branch_c: Counter,
    base_c: Counter,
    label: str,
    rename_map: dict[str, str],
    deleted: set[str],
) -> tuple[list[dict], list[dict]]:
    """Check A: per-(file, code) error identity diff against a translated baseline.

    A per-file count increase is "hard" (blocks) when the global count for
    that code also rose, "soft" (advisory) when the file's increase is
    cancelled by a decrease elsewhere — that's a relocation, not a new
    error. Returns (blocks_to_add, advisories_to_add) for the caller.
    """
    translated = _translate(base_c, rename_map, deleted)
    per_file_new: list[dict] = []
    for (file, code), n in branch_c.items():
        base_n = translated.get((file, code), 0)
        if n > base_n:
            per_file_new.append({"file": file, "code": code, "new": n - base_n})
    global_branch: Counter = Counter()
    for (file, code), n in branch_c.items():
        global_branch[code] += n
    global_base: Counter = Counter()
    for (file, code), n in translated.items():
        global_base[code] += n
    hard: list[dict] = []
    soft: list[dict] = []
    for entry in per_file_new:
        net = global_branch[entry["code"]] - global_base[entry["code"]]
        entry["global_net"] = net
        if net <= 0:
            soft.append(entry)
        else:
            hard.append(entry)
    blocks_out: list[dict] = []
    advisories_out: list[dict] = []
    if hard:
        blocks_out.append({"check": f"A.{label}", "kind": "new_errors", "items": hard})
    if soft:
        advisories_out.append({"check": f"A.{label}", "kind": "relocated_errors", "items": soft})
    return blocks_out, advisories_out


def _parse_waivers(raw: str | None) -> list[dict]:
    """Parse the --assertion-loss-waiver JSON into a list of waiver dicts.

    Accepts a single object or a list. A malformed or incomplete entry is
    dropped — conservative, so the corresponding loss stays a hard block.
    """
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        sys.stderr.write("sdlc-gate: --assertion-loss-waiver is not valid JSON; ignoring\n")
        return []
    items = data if isinstance(data, list) else [data]
    out: list[dict] = []
    for w in items:
        if (
            isinstance(w, dict)
            and isinstance(w.get("file"), str)
            and isinstance(w.get("migrated_to_test"), str)
            and "expected_delta" in w
        ):
            out.append(w)
    return out


def _matching_waiver(waivers: list[dict], file: str) -> dict | None:
    for w in waivers:
        if w.get("file") == file:
            return w
    return None


def _removed_assert_predicates(baseline_sha: str, file: str) -> list[str]:
    """Normalized predicate text of each assertion removed from `file`
    between the baseline commit and the working tree. Empty on git failure
    (treated by the caller as a failed verification → block)."""
    try:
        out = subprocess.run(
            ["git", "diff", baseline_sha, "--", file],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        return []
    preds: list[str] = []
    for line in out.splitlines():
        if not line.startswith("-") or line.startswith("---"):
            continue
        body = line[1:]
        if not _ASSERT_KEYWORD.search(body):
            continue
        after = body.split("assert", 1)[1].strip()
        # Drop a trailing assertion message: `assert <expr>, "msg"`.
        after = re.split(r',\s*["\']', after, maxsplit=1)[0].strip()
        norm = " ".join(after.split())
        if norm:
            preds.append(norm)
    return preds


def _sibling_test_haystack(root: Path, sibling: str) -> str | None:
    """Whitespace-normalized source of the sibling file's collected `test_`
    functions. None if the file is missing or unparseable (→ verification
    fails). AST-scoping keeps module-level dead code / uncalled helpers from
    satisfying predicate containment."""
    try:
        src = (root / sibling).read_text()
    except OSError:
        return None
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    chunks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            seg = ast.get_source_segment(src, node)
            if seg:
                chunks.append(" ".join(seg.split()))
    return " ".join(chunks)


def _waiver_verifies(
    waiver: dict,
    file: str,
    lost: int,
    branch_pytest: dict,
    baseline_sha: str,
    root: Path,
) -> bool:
    """Three mechanical, git-only checks; ALL must pass. Any failure or
    exception → False, so the loss stays a hard block (issue #199)."""
    try:
        # 1. Delta-exactness: declared delta must match the measured loss
        #    exactly — a worker can only waive precisely what it declared.
        expected_delta = int(waiver["expected_delta"])
        if expected_delta >= 0 or lost != -expected_delta:
            return False
        sibling = waiver["migrated_to_test"]
        # 2. Sibling-grew: the migration target carries >= lost assertions now.
        if branch_pytest["asserts"].get(sibling, 0) < lost:
            return False
        # 3. Predicate-text containment: every removed predicate's text appears
        #    in the sibling's collected test_ functions — a real relocation,
        #    not a deletion dressed as one.
        preds = _removed_assert_predicates(baseline_sha, file)
        if not preds:
            return False
        haystack = _sibling_test_haystack(root, sibling)
        if haystack is None:
            return False
        return all(p in haystack for p in preds)
    except (KeyError, ValueError, TypeError):
        return False


def _check_pytest_weakening(
    branch_pytest: dict,
    baseline_pytest: dict,
    rename_map: dict[str, str],
    deleted: set[str],
    waivers: list[dict] | None = None,
    baseline_sha: str = "",
    root: Path | None = None,
) -> tuple[list[dict], list[dict]]:
    """Check D: new pytest.mark.skip markers + dropped assertion counts.

    Returns (blocks, advisories). Skip-marker increases (Check D.skips) are
    always hard blocks. Assertion-count regressions (Check D.asserts) are
    hard blocks too, EXCEPT when a spec-declared, mechanically-verified
    migration waiver applies (issue #199) — those downgrade to an advisory.
    """
    waivers = waivers or []
    if root is None:
        root = Path().resolve()
    blocks_out: list[dict] = []
    advisories_out: list[dict] = []

    new_skips: list[dict] = []
    for file, n in branch_pytest["skips"].items():
        base_n = 0
        for bf, bn in baseline_pytest["skips"].items():
            if rename_map.get(bf, bf) == file:
                base_n = bn
                break
        if n > base_n:
            new_skips.append({"file": file, "new": n - base_n})
    if new_skips:
        blocks_out.append({"check": "D.skips", "kind": "new_skip_markers", "items": new_skips})

    lost_asserts: list[dict] = []
    waived_asserts: list[dict] = []
    for bf, base_n in baseline_pytest["asserts"].items():
        if bf in deleted:
            continue
        new_f = rename_map.get(bf, bf)
        n = branch_pytest["asserts"].get(new_f, 0)
        if n < base_n:
            lost = base_n - n
            waiver = _matching_waiver(waivers, new_f)
            if waiver is not None and _waiver_verifies(
                waiver, new_f, lost, branch_pytest, baseline_sha, root
            ):
                waived_asserts.append(
                    {
                        "file": new_f,
                        "lost": lost,
                        "migrated_to_test": waiver["migrated_to_test"],
                        "migrated_in": waiver.get("migrated_in", ""),
                    }
                )
            else:
                lost_asserts.append({"file": new_f, "lost": lost})
    if lost_asserts:
        blocks_out.append({"check": "D.asserts", "kind": "lost_assertions", "items": lost_asserts})
    if waived_asserts:
        advisories_out.append(
            {"check": "D.asserts", "kind": "waived_assertion_migration", "items": waived_asserts}
        )

    return blocks_out, advisories_out


def cmd_diff(args: argparse.Namespace) -> None:
    base_dir = Path(args.baseline_dir)
    if not base_dir.exists():
        sys.stderr.write(f"sdlc-gate: baseline dir {base_dir} missing\n")
        sys.exit(2)

    baseline = _load_baseline_snapshots(base_dir)
    rename_map, deleted = _git_rename_map(baseline["sha"])

    root = Path().resolve()
    tc: Toolchain = baseline["tc"]

    # Fail-closed compile precondition (Check Build): a tree that does not compile silences the
    # linters, so an empty static scan must not read as "no new findings". If either the branch
    # or the baseline fails to compile, block immediately — before running (and trusting) the
    # scanners. 'skip' (sbt not wired) is a no-op; a pre-port baseline with no build.txt is 'skip'.
    branch_build = "skip" if getattr(args, "no_static", False) else tc.compile_check(root)
    baseline_build = (base_dir / "build.txt").read_text().strip() if (base_dir / "build.txt").exists() else "skip"
    compile_blocks = _compile_precondition_blocks(branch_build, baseline_build)
    if compile_blocks:
        sys.stdout.write(json.dumps({
            "verdict": "fail", "toolchain": tc.name, "baseline_sha": baseline["sha"],
            "blocks": compile_blocks, "advisories": [],
            "summary": {"compile": {"branch": branch_build, "baseline": baseline_build}},
        }, indent=2) + "\n")
        sys.exit(1)

    branch_static = {} if getattr(args, "no_static", False) else tc.static_analysis(root)
    branch_supp = tc.suppressions(root)
    branch_tw = tc.test_weakening(root)

    blocks: list[dict] = []
    advisories: list[dict] = []

    # Check A: per-(file, code) error-identity diff, per static-analysis label.
    for label in tc.static_labels:
        a_blocks, a_advisories = _diff_errors(
            branch_static.get(label, Counter()), baseline["static"].get(label, Counter()),
            label, rename_map, deleted,
        )
        blocks.extend(a_blocks)
        advisories.extend(a_advisories)

    # Check B: new suppressions
    translated_supp = _translate(baseline["supp"], rename_map, deleted)
    new_supp: list[dict] = []
    for (file, directive), n in branch_supp.items():
        base_n = translated_supp.get((file, directive), 0)
        if n > base_n:
            new_supp.append({"file": file, "directive": directive, "new": n - base_n})
    if new_supp:
        blocks.append({"check": "B", "kind": "new_suppressions", "items": new_supp})

    # Check C: deleted test files (advisory)
    deleted_tests = sorted(f for f in deleted if tc.is_test_file(f))
    if deleted_tests:
        advisories.append({"check": "C", "kind": "test_deletions", "items": deleted_tests})

    # Check D: test weakening (skip markers + lost assertions). A spec-declared,
    # mechanically-verified migration waiver downgrades a matching D.asserts loss to
    # advisory (issue #199); everything else stays a hard block. Then the Scala-only
    # ScalaCheck-parameter value check (no analog on the Python side; inert there).
    waivers = _parse_waivers(getattr(args, "assertion_loss_waiver", None))
    d_blocks, d_advisories = _check_pytest_weakening(
        branch_tw, baseline["tw"], rename_map, deleted,
        waivers=waivers, baseline_sha=baseline["sha"], root=root,
    )
    blocks.extend(d_blocks)
    advisories.extend(d_advisories)
    blocks.extend(_check_scalacheck_params(
        branch_tw, baseline["tw"], tc.param_directions, rename_map, deleted))

    # Check D coverage-drop (opt-in --coverage): a per-directory statement-coverage drop beyond
    # COVERAGE_EPSILON versus the baseline is a hard block. A failed coverage scan is operational
    # (exit 2, fail-closed) — never read as "no coverage to check".
    if getattr(args, "coverage", False):
        try:
            branch_cov = tc.coverage(root)
        except CoverageOperationalError as e:
            sys.stderr.write(f"sdlc-gate: {e}\n")
            sys.exit(2)
        cov_path = base_dir / "coverage.json"
        baseline_cov = json.loads(cov_path.read_text()) if cov_path.exists() else {}
        blocks.extend(_diff_coverage(branch_cov, baseline_cov, rename_map, COVERAGE_EPSILON))

    if blocks:
        verdict = "fail"
    elif advisories:
        verdict = "advisory"
    else:
        verdict = "pass"

    report = {
        "verdict": verdict,
        "toolchain": tc.name,
        "baseline_sha": baseline["sha"],
        "blocks": blocks,
        "advisories": advisories,
        "summary": {
            "static_branch": {l: sum(branch_static.get(l, Counter()).values()) for l in tc.static_labels},
            "static_baseline": {l: sum(baseline["static"].get(l, Counter()).values()) for l in tc.static_labels},
            "suppressions_branch": sum(branch_supp.values()),
            "suppressions_baseline": sum(baseline["supp"].values()),
            "skips_branch": sum(branch_tw["skips"].values()),
            "asserts_branch": sum(branch_tw["asserts"].values()),
        },
    }
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    sys.exit(0 if verdict in ("pass", "advisory") else 1)


# --- Entry point --------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(prog="sdlc-gate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_baseline = sub.add_parser(
        "baseline",
        help="Capture static-analysis / suppression / test-weakening baselines from the current tree",
    )
    p_baseline.add_argument("--sha", required=True, help="SHA being captured")
    p_baseline.add_argument("--out", required=True, help="Output directory")
    p_baseline.add_argument("--root", default=".", help="Project root (default: cwd)")
    p_baseline.add_argument("--toolchain", default=None, choices=["python", "scala", "java"],
                            help="Force the toolchain (default: auto-detect build.sbt/pom.xml/"
                                 "build.gradle/pyproject.toml)")
    p_baseline.add_argument("--no-static", action="store_true",
                            help="Skip the static-analysis scanners (sbt/uv); run only the fast "
                                 "regex checks (suppressions + test-weakening). Use the SAME flag on "
                                 "baseline and diff.")
    p_baseline.add_argument("--coverage", action="store_true",
                            help="Also capture scoverage statement coverage (scala). Runs an "
                                 "instrumented clean+test — heavy, opt-in. Use the SAME flag on diff.")
    p_baseline.set_defaults(func=cmd_baseline)

    p_diff = sub.add_parser(
        "diff",
        help="Diff the current tree against a captured baseline; emit verdict",
    )
    p_diff.add_argument("--baseline-dir", required=True)
    p_diff.add_argument(
        "--assertion-loss-waiver",
        default=None,
        help=(
            "JSON object (or list) declaring a sanctioned assertion-count loss: "
            '{"file", "expected_delta" (negative), "migrated_to_test", "migrated_in"}. '
            "A matching D.asserts loss downgrades to advisory only when the loss "
            "equals the declared delta exactly, the migration target carries at "
            "least that many assertions, and every removed predicate's text "
            "appears in the target's test_ functions. The caller reads this from "
            "the story's bead metadata (issue #199)."
        ),
    )
    p_diff.add_argument("--no-static", action="store_true",
                        help="Skip the static-analysis scanners; must match the baseline's capture.")
    p_diff.add_argument("--coverage", action="store_true",
                        help="Also diff scoverage coverage vs the baseline (scala); a per-directory "
                             "statement-coverage drop beyond 0.5pp blocks. Must match the baseline's "
                             "capture. A failed coverage scan exits 2 (operational, fail-closed).")
    p_diff.set_defaults(func=cmd_diff)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

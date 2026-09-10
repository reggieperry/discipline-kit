#!/usr/bin/env python3
"""SDLC differential gate: capture and compare static-analysis baselines.

Toolchains
----------
One engine, per-toolchain scanners (a scanner-plugin layer). The engine — the
baseline/diff worktree model, the (file, code) multiset identity, rename tracking,
the relocation-advisory downgrade, the waiver system, and the verdict logic — is
language-agnostic. Each `Toolchain` supplies the scanners: a set of static-analysis
error-identity scanners (Check A), a suppression scan (Check B), a test-weakening scan
(Check D), and four agent-smell checks — unreferenced code (E), whole-tree duplication (F),
per-function cognitive complexity delta (G), single-implementor abstractions (H) — each of
which reports itself NOT WIRED for a toolchain that lacks it rather than reading as clean.
Detection is by marker file (`build.sbt` → scala, `pom.xml`/`build.gradle` → java,
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
    # ruff exits 0 clean, 1 with findings, 2 on error; anything else is uv or the shell. Only the
    # first two are a scan. Until 2026-09-10 a non-JSON body was logged and treated as NO
    # FINDINGS, so a missing ruff read as a clean Check A — the fail-open this file exists to stop.
    if proc.returncode not in (0, 1):
        raise ScanOperationalError(
            f"ruff exited {proc.returncode}: {proc.stderr.strip()[:300]!r} — a ruff that did not "
            "run must not read as 'no findings'")
    findings: list[dict] = []
    if proc.stdout.strip():
        try:
            findings = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ScanOperationalError(
                f"ruff produced non-JSON output ({e}); refusing to read it as no findings") from e
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
        ["uv", "run", "mypy", ".", "--strict", "--show-error-codes", "--no-error-summary"],
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


# --- Python agent-smell runners (Checks E-H) ----------------------------------
# Measured 2026-09-10 against ruff 0.16.7, complexipy 8.0.1 and PMD 7.27.0 on a scratch clone of
# story-factory-experiment (83 .py files, 46 classes, 958 functions). The two uvx tools are PINNED
# in the invocation: every exit-code and output-shape rule below was read off that version, and a
# floating "latest" would leave the test suite asserting a contract nobody measured.

_PY_RUFF = "ruff@0.16.7"
_PY_COMPLEXIPY = "complexipy@8.0.1"


def _parsed_python(root: Path):
    """Yield (rel_path, ast.Module) for every file `_walk_python` yields, sorted, and RAISE on the
    first that does not parse. The precondition every E-H runner shares, because each tool's
    silence on such a file reads as clean: ruff emits one `invalid-syntax` finding and computes
    nothing else for the file; complexipy skips the file, exits 1 (the code it also uses for
    over-threshold) and still writes its JSON for the rest; CPD is a lexer and tokenizes `def x(:`
    without complaint. `python -m compileall` exits 0 on a missing file, so it is not the check.
    Bytes, not text, so a coding cookie is honoured; a NUL byte is a SyntaxError under 3.12."""
    for path in sorted(_walk_python(root)):
        rel = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_bytes(), filename=rel)
        except (SyntaxError, ValueError, OSError) as e:
            raise ScanOperationalError(
                f"{rel} does not parse under this interpreter ({e.__class__.__name__}: "
                f"{str(e)[:120]}); a tool's silence on it would read as clean") from e
        yield rel, tree


def _python_files(root: Path) -> list[str]:
    return [rel for rel, _ in _parsed_python(root)]


def _py_rel(path: str, root: Path) -> str:
    """Tool output paths back into the walk's path-space: ruff and CPD print absolute paths,
    complexipy echoes what it was handed (relative to `root`, which is the cwd it ran under)."""
    p = Path(path)
    try:
        return str((p if p.is_absolute() else root / p).resolve().relative_to(root))
    except ValueError:
        return path


def _py_run(cmd: list[str], root: Path):
    """`subprocess.run` under `root`, with an executable that cannot be spawned at all (no `uvx`
    on PATH, a `pmd` script with no execute bit) turned into the operational error it is; the
    raw OSError would surface as a traceback, which exits 1 rather than the 2 the gate's callers
    read as did-not-run."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=str(root))
    except OSError as e:
        raise ScanOperationalError(f"cannot run {cmd[0]!r}: {e}") from e


def _batched(items: list, size: int = 1000):
    """Explicit file lists on the command line, in batches: the walk is the denominator (ruff
    reports no count of its own, and complexipy lists only files that have functions), and a
    20k-file tree would otherwise brush ARG_MAX."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


# --- The class table: one AST pass shared by Check H and Check E's override filter -------------

_PY_ABSTRACT_DECORATORS = {"abstractmethod", "abstractproperty", "abstractclassmethod",
                           "abstractstaticmethod"}


def _py_base_name(node) -> str | None:
    """`Base`, `mod.Base`, `Base[T]` -> "Base"; a call or anything else -> None. Name-based, with
    no import resolution: two classes of one simple name in different files share implementors,
    which over-counts and so blocks LESS, never more."""
    if isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _py_is_abstract(cls: ast.ClassDef) -> bool:
    """Declared abstract: `ABC` among the bases, `metaclass=ABCMeta`, or any method under an
    `abstract*` decorator. `Protocol` is deliberately NOT here: its implementors are structural,
    and counting explicit subclasses of a Protocol would read every healthy one as
    single-implementor. Plain base classes are not here either — a class is a base because
    something subclasses it, so the count is >= 1 by construction and a new one-subclass helper
    (an exception type, a TestCase mixin) would block; the corpus's one such case was test
    scaffolding."""
    bases = [_py_base_name(b) for b in cls.bases]
    if "ABC" in bases:
        return True
    if any(kw.arg == "metaclass" and _py_base_name(kw.value) == "ABCMeta" for kw in cls.keywords):
        return True
    return any(_py_base_name(d) in _PY_ABSTRACT_DECORATORS
               for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               for d in n.decorator_list)


def _python_class_table(root: Path) -> tuple[list[str], list[dict]]:
    """(files, classes): every file the walk yields (the denominator) and one record per class —
    file, name, base names, whether it is declared abstract, and its methods' line spans."""
    files: list[str] = []
    classes: list[dict] = []
    for rel, tree in _parsed_python(root):
        files.append(rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {n.name: (n.lineno, n.end_lineno or n.lineno) for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            classes.append({"file": rel, "name": node.name,
                            "bases": [b for b in map(_py_base_name, node.bases) if b],
                            "abstract": _py_is_abstract(node), "methods": methods})
    return files, classes


def _py_overrides_in_tree(classes: list[dict], file: str, row: int) -> bool:
    """True when `row` sits in a method whose name an in-tree ancestor also defines. The innermost
    span wins (a nested class inside a method). A base not in the tree cannot vouch for anything,
    so a finding there stands."""
    hit = None
    for c in classes:
        if c["file"] != file:
            continue
        for name, (a, b) in c["methods"].items():
            if a <= row <= b and (hit is None or b - a < hit[2] - hit[1]):
                hit = (c, a, b, name)
    if hit is None:
        return False
    by_name: dict[str, list[dict]] = {}
    for c in classes:
        by_name.setdefault(c["name"], []).append(c)
    cls, _, _, method = hit
    seen: set[str] = set()
    stack = list(cls["bases"])
    while stack:
        base = stack.pop()
        if base in seen:
            continue
        seen.add(base)
        for anc in by_name.get(base, ()):
            if method in anc["methods"]:
                return True
            stack.extend(anc["bases"])
    return False


# --- Check E: ruff, isolated, minus what the corpus showed to be signature-dictated -------------

_PY_E_RULES = "ARG001,ARG002,ARG003,ARG004,F401,F811,F841"
_PY_E_TEST_GLOBS = ("**/tests/**", "**/test_*.py", "**/*_test.py", "**/conftest.py")
_PY_E_OVERRIDE_CODES = {"ARG002", "ARG003", "ARG004"}


def run_ruff_unreferenced(root: Path) -> "Scan":
    """Check E. `--isolated`, because the repo's own `ignore`, `exclude` and per-file lists would
    each make E blind somewhere without a trace, and the file list passed explicitly, because ruff
    reports no count of its own: the walk is the denominator. Explicit paths are linted whatever
    the repo excludes (measured). A path ruff was handed and could not read is exit 0, `[]` and a
    stderr warning — the fail-open shape — and the pinned version has no other signal for it, so
    the warning text is trapped.

    Three carve-outs, each read off the corpus rather than guessed: ARG005 is not selected, since
    a lambda's parameters are its caller's (93 of 93 lambda findings were interface stand-ins);
    ARG is ignored in test files, since a fake carries the signature of what it fakes and a
    fixture is requested for its side effect (every ARG001/ARG002 there was one of those); and an
    ARG finding on a method overriding an in-tree ancestor's method is dropped, since ruff cannot
    see the override without `@override` and the signature is the ancestor's. Unused `*args` /
    `**kwargs` are ignored for the same reason. `__init__.py` re-exports are the idiom, not
    unused imports. Left after the carve-outs on the corpus: 23 F401 and 1 F841, all real."""
    files, classes = _python_class_table(root)
    if not files:
        return Scan("ruff", 0, {})
    cmd = ["uvx", _PY_RUFF, "check", "--isolated", "--select", _PY_E_RULES,
           "--per-file-ignores", "__init__.py:F401",
           "--config", "lint.flake8-unused-arguments.ignore-variadic-names=true",
           "--output-format=json"]
    for glob in _PY_E_TEST_GLOBS:
        cmd += ["--per-file-ignores", f"{glob}:ARG"]
    counter: Counter = Counter()
    for batch in _batched(files):
        proc = _py_run(cmd + batch, root)
        # ruff: 0 clean, 1 findings, 2 error. uvx failing to resolve the tool is ALSO exit 1, with
        # an empty stdout — which is why the body must parse as a list in every case: a clean run
        # prints `[]`, never nothing.
        if proc.returncode not in (0, 1) or "Failed to lint" in proc.stderr:
            raise ScanOperationalError(
                f"ruff exited {proc.returncode}: {proc.stderr.strip()[:300]!r} — a ruff that did "
                "not run must not read as 'no unreferenced code'")
        try:
            findings = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ScanOperationalError(
                f"ruff (exit {proc.returncode}) produced no JSON ({e}; stderr "
                f"{proc.stderr.strip()[-200:]!r}); refusing to read it as no findings") from e
        if not isinstance(findings, list):
            raise ScanOperationalError(f"ruff JSON is not a list ({type(findings).__name__})")
        for f in findings:
            code = f.get("code")
            if not code or code == "invalid-syntax" or code == "E999":
                # Not a finding: the file did not parse for ruff, so nothing else was computed
                # for it. The precondition should have caught it; a stricter ruff parser is the
                # gap this closes.
                raise ScanOperationalError(
                    f"ruff could not parse {f.get('filename')!r}: {f.get('message', '')[:120]}")
            rel = _py_rel(f.get("filename", ""), root)
            row = int(f.get("location", {}).get("row", 0))
            if code in _PY_E_OVERRIDE_CODES and _py_overrides_in_tree(classes, rel, row):
                continue
            counter[(rel, code)] += 1
    return Scan("ruff", len(files), dict(counter))


# --- Check F: PMD CPD over the whole tree, fingerprinted from the clone's own text --------------

_CPD_TOKEN = re.compile(
    r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|#[^\n]*|\w+|[^\s\w]')


def _pmd_bin() -> str:
    """`pmd` on PATH, else `$PMD_HOME/bin/pmd`, else the newest `~/.local/opt/pmd-bin-*/bin/pmd`
    (the install rule's home for JVM tools). Absent everywhere is operational, not clean."""
    import os

    found = shutil.which("pmd")
    if found:
        return found
    home = os.environ.get("PMD_HOME")
    if home and (Path(home) / "bin" / "pmd").is_file():
        return str(Path(home) / "bin" / "pmd")
    candidates = sorted(Path.home().glob(".local/opt/pmd-bin-*/bin/pmd"),
                        key=lambda p: [int(x) if x.isdigit() else x
                                       for x in re.split(r"(\d+)", p.parts[-3])])
    if candidates:
        return str(candidates[-1])
    raise ScanOperationalError(
        "pmd not found (PATH, $PMD_HOME/bin/pmd, ~/.local/opt/pmd-bin-*/bin/pmd); Check F "
        "cannot run without it")


def _cpd_fingerprint(text: str) -> str:
    """Comments and whitespace out, strings kept whole, then hashed. CPD's Python lexer drops
    comments too, so two occurrences that differ only there are one clone to both. Not the
    `tokenize` module: a fragment sliced from mid-block dedents below its first line and
    tokenize raises on that."""
    import hashlib

    toks = [t for t in _CPD_TOKEN.findall(text) if not t.startswith("#")]
    return hashlib.sha256(" ".join(toks).encode("utf-8")).hexdigest()[:16]


def _cpd_occurrence_text(root: Path, rel: str, line: int, endline: int, col: int, endcol: int) -> str:
    """The clone's own text, sliced by CPD's 1-based `column` and exclusive `endcolumn` (measured).
    NOT the report's `<codefragment>`: that is rendered from the first occurrence's line start,
    so it carries a prefix outside the clone (`def compute` before `(items, factor):`) and would
    change fingerprint whenever a rename reorders which occurrence comes first."""
    lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    seg = lines[line - 1:endline]
    if not seg:
        return ""
    seg[-1] = seg[-1][:max(endcol - 1, 0)]
    seg[0] = seg[0][max(col - 1, 0):]
    return "\n".join(seg)


def _xml_local(tag: str) -> str:
    """The CPD report is namespaced (`{https://pmd-code.org/schema/cpd-report}file`)."""
    return tag.rsplit("}", 1)[-1]


def parse_cpd(xml: str, root: Path) -> tuple[int, dict]:
    """(files examined, fingerprint -> [[file, start, end], ...]). Since 7.3.0 the report lists
    every analysed file as `<file path= totalNumberOfTokens=>`, empty files included (measured),
    which is the denominator. An `<error>` element is a file the lexer gave up on — the report
    still comes out and the exit code is 5 — and reads as operational here, since the file it
    skipped is exactly the one that would read clean. A DOCTYPE is rejected (XXE closed)."""
    if re.search(r"<!DOCTYPE", xml, re.IGNORECASE):
        raise ScanOperationalError("cpd report carries a DOCTYPE; refusing to parse (XXE closed)")
    try:
        top = ET.fromstring(xml)
    except ET.ParseError as e:
        raise ScanOperationalError(f"cpd report is not XML ({e}); not a clean scan") from e
    examined = 0
    findings: dict[str, list] = {}
    for el in top:
        kind = _xml_local(el.tag)
        if kind == "error":
            raise ScanOperationalError(
                f"cpd skipped {el.get('filename')!r}: {(el.get('msg') or '')[:160]}")
        if kind == "file":
            examined += 1
            continue
        if kind != "duplication":
            continue
        occs = [f for f in el if _xml_local(f.tag) == "file"]
        if not occs:
            continue
        spans = [[_py_rel(f.get("path", ""), root), int(f.get("line", 0)), int(f.get("endline", 0))]
                 for f in occs]
        first = occs[0]
        text = _cpd_occurrence_text(root, spans[0][0], spans[0][1], spans[0][2],
                                    int(first.get("column", 1)), int(first.get("endcolumn", 0)))
        findings.setdefault(_cpd_fingerprint(text), []).extend(spans)
    return examined, findings


def run_cpd(root: Path) -> "Scan":
    """Check F. PMD CPD 7 on the walk's file list, at DUP_MIN_TOKENS. Exit contract (measured):
    0 no clones, 4 clones, 5 a recoverable error such as a file it could not lex or find (the
    report is still written and may hold clones — FAIL CLOSED), 1 an exception, 2 usage; anything
    else is the shell. Never `--no-fail-on-error` or `--no-fail-on-violation`, which would fold 4
    and 5 into 0. A report naming fewer files than were handed over is a silent skip and refuses
    too. 1.4 s wall on the 83-file corpus."""
    import tempfile

    files = _python_files(root)
    if not files:
        return Scan("pmd-cpd", 0, {})
    pmd = _pmd_bin()
    with tempfile.TemporaryDirectory() as td:
        listing = Path(td) / "files.txt"
        listing.write_text("\n".join(files) + "\n")
        report = Path(td) / "cpd.xml"
        proc = _py_run([pmd, "cpd", "--file-list", str(listing), "--language", "python",
                        "--minimum-tokens", str(DUP_MIN_TOKENS), "--format", "xml",
                        "--report-file", str(report)], root)
        if proc.returncode not in (0, 4):
            raise ScanOperationalError(
                f"pmd cpd exited {proc.returncode}: {proc.stderr.strip()[-300:]!r} — a CPD that "
                "did not finish must not read as 'no clones'")
        try:
            xml = report.read_text(encoding="utf-8")
        except OSError as e:
            raise ScanOperationalError(f"pmd cpd wrote no report ({e})") from e
    examined, findings = parse_cpd(xml, root)
    if examined != len(files):
        raise ScanOperationalError(
            f"pmd cpd reports {examined} files analysed but was handed {len(files)}; a file it "
            "silently skipped is one that reads clean")
    return Scan("pmd-cpd", examined, findings)


# --- Check G: complexipy, cognitive complexity per function -----------------------------------


def run_complexipy(root: Path) -> "Scan":
    """Check G. complexipy (cognitive, not radon's cyclomatic) over the walk's file list, keyed
    (file, function) with methods as `Class::method` and nested functions folded into their
    parent, as the tool names them. Whole-tree and never its `--diff` mode: the engine does the
    delta. `--max-complexity-allowed` is set unreachably high so that under it exit 1 has ONE
    meaning: a file it failed to process (its `--ignore-complexity` does not suppress the exit,
    measured on 8.0.1). Without `--output` it writes `complexipy-results.json` into the cwd, and
    without `--cache-dir` a `.complexipy_cache/` — both into the tree under test, so both are
    pointed at a temp dir. Two functions of one name in one file collide on the key; the higher
    value is kept."""
    import tempfile

    files = _python_files(root)
    if not files:
        return Scan("complexipy", 0, {})
    findings: dict[tuple[str, str], int] = {}
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "complexipy.json"
        base = ["uvx", _PY_COMPLEXIPY, "--quiet", "--output-format", "json", "--output", str(out),
                "--cache-dir", str(Path(td) / "cache"), "--max-complexity-allowed", "1000000"]
        for batch in _batched(files):
            out.unlink(missing_ok=True)
            proc = _py_run(base + batch, root)
            if proc.returncode != 0:
                # Its "Failed to process <file>" goes to STDOUT, quiet or not.
                raise ScanOperationalError(
                    f"complexipy exited {proc.returncode}: "
                    f"{(proc.stdout + proc.stderr).strip()[-300:]!r} — a complexipy that did not "
                    "finish must not read as 'nothing complex'")
            try:
                rows = json.loads(out.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                raise ScanOperationalError(f"complexipy wrote no readable JSON ({e})") from e
            if not isinstance(rows, list):
                raise ScanOperationalError(f"complexipy JSON is not a list ({type(rows).__name__})")
            for r in rows:
                key = (_py_rel(str(r.get("path", "")), root), str(r.get("function_name", "")))
                findings[key] = max(findings.get(key, 0), int(r.get("complexity", 0)))
    return Scan("complexipy", len(files), findings)


# --- Check H: declared abstractions and their in-tree implementors ------------------------------


def scan_python_abstractions(root: Path) -> "Scan":
    """Check H. Every class `_py_is_abstract` accepts, keyed (file, name) -> number of in-tree
    descendants (transitively, by simple name) that are not themselves declared abstract, so a
    two-layer hierarchy over one concrete class counts one implementor for each layer. The
    corpus had 46 classes and none declared abstract, so this scan's precision is by construction
    rather than by measurement there; the planted controls are in the test file."""
    files, classes = _python_class_table(root)
    children: dict[str, set[str]] = {}
    for c in classes:
        for b in c["bases"]:
            children.setdefault(b, set()).add(c["name"])
    abstract = {c["name"] for c in classes if c["abstract"]}
    findings: dict[tuple[str, str], int] = {}
    for c in classes:
        if not c["abstract"]:
            continue
        seen: set[str] = set()
        stack = [c["name"]]
        while stack:
            for kid in children.get(stack.pop(), ()):
                if kid not in seen:
                    seen.add(kid)
                    stack.append(kid)
        findings[(c["file"], c["name"])] = len(seen - abstract - {c["name"]})
    return Scan("ast", len(files), findings)


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
# Checks G and F (agent smells). Module-level so every toolchain reads the number the CLI set;
# overridable with --complexity-threshold / --dup-min-tokens.
COMPLEXITY_THRESHOLD = 15   # cognitive complexity per function; SonarQube's default
DUP_MIN_TOKENS = 75         # clone length; PMD CPD's floor for anything but the noisiest languages


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


# --- Checks E-H for Scala 3 ----------------------------------------------------------------
# Three tools, each captured before its parser was written (2026-09-10, sbt 1.12.11 + Scala 3.3.8,
# PMD 7.27.0, scalameta 4.13.9 under scala-cli 1.10.1), and each read under the contract in the
# E-H section below: a Scan carries the count of files the tool examined, and a tool that did not
# run raises. What was measured on the way here, in order: a warm zinc cache compiles zero sources
# and prints zero warnings, so an E scan without `clean` reads a planted unused parameter as clean;
# `-Werror` turns every unused symbol into a compile error and stops the test sources from ever
# being compiled, so it is stripped in every project scope rather than only at ThisBuild (where
# `set every ... -=` cycles); CPD given a `.sc` file drops it silently and exits 0; and the prior
# complexity script scored a flat else-if chain at depth 4 because else-if nests in the tree.


def _scala_sources(root: Path) -> list[str]:
    """The repo-relative `.scala` files F, G and H are handed, sorted so CPD lists occurrences in a
    stable order. `.sc` scripts are left out: CPD's scala tokenizer ignores them without saying so
    (measured: a two-file list with one `.sc` reports one file and exits 0), and scalameta's Source
    parser refuses their top-level statements."""
    return sorted(str(p.relative_to(root)) for p in _walk_scala(root) if p.suffix == ".scala")


# Check E: the compiler's own `-Wunused:all`, forced on. Injected as a command rather than a
# `set` per key because the options compile actually reads are `<project> / <config> / compile /
# scalacOptions`, which delegate to wherever the build put `-Werror`; deriving that key in every
# project scope is the only shape that strips a per-project `-Werror` as well as a ThisBuild one.
# Existing `-Wunused` flags go too, or scalac warns "set to all redundantly".
_SBT_UNUSED_SCAN_COMMAND = """set Global / commands += Command.command("gateUnusedScan") { state =>
  val ex = Project.extract(state)
  val drop = (o: String) => o == "-Werror" || o == "-Xfatal-warnings" || o.startsWith("-Wunused")
  val ss = ex.structure.allProjectRefs.flatMap { p =>
    Seq(Compile, Test).map { c =>
      (p / c / compile / scalacOptions) := ((p / c / scalacOptions).value.filterNot(drop) :+ "-Wunused:all")
    }
  }
  ex.appendWithSession(ss, state)
}"""

# Scala 3 renders a diagnostic as a header line naming the file, then the source line, a caret
# line, and the message; only the header and the message line are read. `[warn] 3 |import ...`
# carries the line number before the pipe and never matches the message pattern.
_SBT_UNUSED_HEADER = re.compile(
    r"^\[warn\] -- \[E\d+\] Unused Symbol Warning: (?P<path>.+?):(?P<line>\d+):(?P<col>\d+)\s*$")
_SBT_UNUSED_MESSAGE = re.compile(r"^\[warn\]\s+\|\s+(?P<msg>unused [a-z][a-z ]*?)\s*$")
_SBT_COMPILING = re.compile(r"^\[info\] compiling (?P<n>\d+) Scala sources?\b.*? to (?P<dir>\S+)")


def _parse_sbt_unused(out: str, root: Path) -> tuple[Counter, int]:
    """Counter[(file, unused-<kind>)] and the number of Scala sources sbt compiled. Scala 2 is
    refused rather than parsed: its warnings come as `path:line:col: Unused import`, which the
    Scala 3 header pattern would pass over, and a non-zero denominator with zero findings would
    then read as a clean 2.13 tree. The target directory on the compiling line carries the
    version (`target/scala-2.13/classes` against `target/scala-3.3.8/classes`)."""
    counter: Counter = Counter()
    files = 0
    pending: str | None = None
    for line in out.splitlines():
        m = _SBT_COMPILING.match(line)
        if m:
            if "/scala-2." in m.group("dir"):
                raise ScanOperationalError(
                    "the build compiles Scala 2 (" + m.group("dir") + "); the unused-symbol scan "
                    "reads Scala 3 diagnostics only and will not report a 2.x tree as clean")
            files += int(m.group("n"))
            continue
        m = _SBT_UNUSED_HEADER.match(line)
        if m:
            pending = _rel(m.group("path"), root)
            continue
        if pending is not None:
            m = _SBT_UNUSED_MESSAGE.match(line)
            if m:
                counter[(pending, m.group("msg").strip().replace(" ", "-"))] += 1
                pending = None
    return counter, files


def run_sbt_unused(root: Path) -> Scan:
    """`clean` then `Test/compile` with `-Wunused:all` on and `-Werror` off in every project. The
    clean is not optional: zinc recompiles nothing for an unchanged file and re-reports nothing,
    so without it the second run of a planted unused parameter reads clean (measured). Zero
    sources compiled after a clean is therefore a scan that did not happen, not an empty tree."""
    cmd = ["sbt", "-batch", "-Dsbt.color=false", _SBT_UNUSED_SCAN_COMMAND, "gateUnusedScan",
           "clean", "Test/compile"]
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False,
                              timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ScanOperationalError(f"sbt could not run for the unused-symbol scan: {e}") from e
    out = proc.stdout + proc.stderr
    if proc.returncode != 0:
        errors = [l for l in out.splitlines() if l.startswith("[error]")][:5]
        raise ScanOperationalError(
            f"sbt exited {proc.returncode} during the unused-symbol scan (the tree does not compile "
            f"with -Werror off, or the build did not load): {' / '.join(errors)[:400]}")
    counter, files = _parse_sbt_unused(out, root)
    if files == 0:
        raise ScanOperationalError(
            "sbt compiled no Scala sources after `clean`; the unused-symbol scan examined nothing "
            "and an empty result is not a clean one")
    return Scan(tool="sbt -Wunused:all", files=files, findings=dict(counter))


# Check F: PMD CPD over the whole tree, `--language scala`. Exit contract read from the CLI help
# and confirmed by probe: 0 nothing found, 4 duplications found, 5 a recoverable error such as a
# listed file it could not read (the report is still written, one file short), 1 unexpected, 2 usage.
def _pmd_binary() -> str | None:
    """`pmd` on PATH, else `$PMD_HOME/bin/pmd`, else the newest `~/.local/opt/pmd-bin-*/bin/pmd`,
    where a per-user unzip of the PMD distribution lands without a global install."""
    import os
    found = shutil.which("pmd")
    if found:
        return found
    home = os.environ.get("PMD_HOME")
    if home and (Path(home) / "bin" / "pmd").is_file():
        return str(Path(home) / "bin" / "pmd")
    candidates = sorted(Path.home().glob(".local/opt/pmd-bin-*/bin/pmd"))
    return str(candidates[-1]) if candidates else None


def _parse_cpd_xml(xml: str, root: Path) -> tuple[dict, int]:
    """{fingerprint: [[file, start, end], ...]} and the count of files CPD tokenized (its top-level
    `<file totalNumberOfTokens>` entries, which appear whether or not anything was duplicated). The
    fingerprint is a hash of the clone's rendered fragment with whitespace collapsed, so the same
    clone on both sides of the differential keys the same regardless of where its lines moved."""
    import hashlib
    if re.search(r"<!DOCTYPE", xml, re.IGNORECASE):
        raise ScanOperationalError("cpd report carries a DOCTYPE; refusing to parse (XXE closed)")
    try:
        tree = ET.fromstring(xml)
    except ET.ParseError as e:
        raise ScanOperationalError(f"cpd produced unparseable XML ({e}); not read as no clones") from e

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    files = 0
    findings: dict = {}
    for el in tree:
        if local(el.tag) == "file" and el.get("totalNumberOfTokens") is not None:
            files += 1
            continue
        if local(el.tag) != "duplication":
            continue
        occs = []
        fragment = ""
        for child in el:
            if local(child.tag) == "file":
                occs.append([_rel(child.get("path") or "", root), int(child.get("line") or 0),
                             int(child.get("endline") or 0)])
            elif local(child.tag) == "codefragment":
                fragment = child.text or ""
        fp = hashlib.sha256(" ".join(fragment.split()).encode("utf-8")).hexdigest()[:24]
        findings.setdefault(fp, []).extend(occs)
    return findings, files


def run_cpd_scala(root: Path) -> Scan:
    import tempfile
    pmd = _pmd_binary()
    if pmd is None:
        raise ScanOperationalError(
            "pmd not found (PATH, $PMD_HOME, or ~/.local/opt/pmd-bin-*); the clone scan did not run")
    sources = _scala_sources(root)
    if not sources:
        raise ScanOperationalError("no .scala sources under the root; the clone scan examined nothing")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
        tmp.write("\n".join(sources) + "\n")
        listfile = tmp.name
    try:
        cmd = [pmd, "cpd", "--minimum-tokens", str(DUP_MIN_TOKENS), "--language", "scala",
               "--file-list", listfile, "--format", "xml"]
        try:
            proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False,
                                  timeout=900)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ScanOperationalError(f"pmd cpd could not run: {e}") from e
    finally:
        Path(listfile).unlink(missing_ok=True)
    if proc.returncode not in (0, 4):
        raise ScanOperationalError(
            f"pmd cpd exited {proc.returncode} (5 = a file it could not tokenize or read; the report "
            f"would be short): {proc.stderr.strip()[:300]!r}")
    findings, files = _parse_cpd_xml(proc.stdout, root)
    if files != len(sources):
        raise ScanOperationalError(
            f"pmd cpd tokenized {files} of the {len(sources)} files it was given; a silently "
            "dropped file is not a clean one")
    return Scan(tool="pmd-cpd scala", files=files, findings=findings)


# Checks G and H: one scalameta program, written to a scratch directory and run by scala-cli with
# no build server, over the same file list as F. Its complexity is Sonar's cognitive complexity
# by the SLang rules, calibrated against hand-counted cases (a flat else-if chain of four arms is
# 4; three nested ifs with elses are 9; `a && b && c || d || e && f` is 3) and against a corpus
# function counted by hand. G keys a def by its enclosing-type path so two `apply`s in one file
# stay distinct; an overload collision keeps the higher value. H counts every `extends`/`with`,
# `new T {}` and `given T with` naming a trait or abstract class by simple name, so a
# SAM-converted lambda or a `given T = expr` alias is not an implementor it can see.
_SCALAMETA_SCRIPT = r'''//> using scala 3.3.8
//> using dep org.scalameta::scalameta:4.13.9
// Checks G and H for Scala, over scalameta trees. Written to a temp dir and run by sdlc-gate.py;
// argv is <root> <file-list>. Output is TSV on stdout: one FILES line (the denominator), G lines
// (file, qualified def name, cognitive complexity), H lines (file, abstraction, implementor count),
// and ERR lines for files that did not parse. Exit 3 when any ERR was written, so the gate refuses
// the scan rather than reading a short denominator as clean.
import scala.meta.*
import java.nio.file.{Files, Path, Paths}
import scala.jdk.CollectionConverters.*

object Gate:
  // Sonar's cognitive complexity, the SLang rules: if/loop/match/catch get 1 + nesting, else-if and
  // else get 1 with no nesting, each run of one boolean operator gets 1, and lambdas or nested defs
  // raise the nesting of what they contain without scoring themselves. No recursion increment,
  // matching sonar-scala. The parent operator travels only from a boolean infix to its operands.
  def complexity(body: Tree): Int =
    def visit(t: Tree, n: Int, op: String): Int = t match
      case t: Term.If =>
        1 + n + visit(t.cond, n, "") + visit(t.thenp, n + 1, "") + elseChain(t.elsep, n)
      case t: Term.While => 1 + n + visit(t.expr, n, "") + visit(t.body, n + 1, "")
      case t: Term.Do => 1 + n + visit(t.body, n + 1, "") + visit(t.expr, n, "")
      case t: Term.For => 1 + n + t.enums.map(visit(_, n, "")).sum + visit(t.body, n + 1, "")
      case t: Term.ForYield => 1 + n + t.enums.map(visit(_, n, "")).sum + visit(t.body, n + 1, "")
      case t: Term.Match => 1 + n + visit(t.expr, n, "") + t.cases.map(visit(_, n + 1, "")).sum
      case t: Term.Try =>
        val handler = if t.catchp.isEmpty then 0 else 1 + n + t.catchp.map(visit(_, n + 1, "")).sum
        visit(t.expr, n, "") + handler + t.finallyp.map(visit(_, n, "")).getOrElse(0)
      case t: Term.TryWithHandler =>
        visit(t.expr, n, "") + 1 + n + visit(t.catchp, n + 1, "") +
          t.finallyp.map(visit(_, n, "")).getOrElse(0)
      case t: Term.ApplyInfix if t.op.value == "&&" || t.op.value == "||" =>
        val o = t.op.value
        (if o == op then 0 else 1) + visit(t.lhs, n, o) + t.argClause.values.map(visit(_, n, o)).sum
      case t @ (_: Term.Function | _: Term.PartialFunction | _: Term.AnonymousFunction |
          _: Term.PolyFunction | _: Term.ContextFunction | _: Defn.Def) =>
        t.children.map(visit(_, n + 1, "")).sum
      case _ => t.children.map(visit(_, n, "")).sum
    def elseChain(e: Term, n: Int): Int = e match
      case t: Term.If => 1 + visit(t.cond, n, "") + visit(t.thenp, n + 1, "") + elseChain(t.elsep, n)
      case _: Lit.Unit if e.tokens.isEmpty => 0 // no else written; scalameta fills a unit
      case other => 1 + visit(other, n + 1, "")
    visit(body, 0, "")

  def simpleName(t: Type): Option[String] = t match
    case t: Type.Name => Some(t.value)
    case t: Type.Select => Some(t.name.value)
    case t: Type.Project => Some(t.name.value)
    case t: Type.Apply => simpleName(t.tpe)
    case t: Type.Annotate => simpleName(t.tpe)
    case t: Type.Refine => t.tpe.flatMap(simpleName)
    case _ => None

  def main(args: Array[String]): Unit =
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    val files = Files.readAllLines(Paths.get(args(1))).asScala.map(_.trim).filter(_.nonEmpty).toList
    val out = new StringBuilder
    var parsed = 0
    var failed = 0
    val abstractions = scala.collection.mutable.ListBuffer.empty[(String, String)]
    val implementors = scala.collection.mutable.Map.empty[String, Int].withDefaultValue(0)
    for f <- files do
      val p = root.resolve(f)
      val rel = root.relativize(p.toAbsolutePath.normalize).toString
      val input = Input.File(p)
      def parseWith(d: Dialect): Either[String, Source] =
        d(input).parse[Source] match
          case Parsed.Success(t) => Right(t)
          case e: Parsed.Error => Left(s"${e.pos.startLine + 1}:${e.pos.startColumn + 1}: ${e.message}")
      // Scala 3 first; a 2.13 file that the Scala 3 dialect refuses gets one more try.
      val tree = parseWith(dialects.Scala3).left.flatMap(msg => parseWith(dialects.Scala213).left.map(_ => msg))
      tree match
        case Left(msg) =>
          failed += 1
          out.append(s"ERR\t$rel\t${msg.replace('\t', ' ').replace('\n', ' ')}\n")
        case Right(src) =>
          parsed += 1
          val defs = scala.collection.mutable.Map.empty[String, Int]
          // Every def not inside another def is a G entry; a def inside a def scores into its
          // owner through complexity() and is walked here only so the H counts see the
          // `new Trait {}` instances a body creates.
          def walk(t: Tree, owners: List[String], inDef: Boolean): Unit = t match
            case d: Defn.Def =>
              if !inDef then
                val key = (d.name.value :: owners).reverse.mkString(".")
                defs(key) = math.max(defs.getOrElse(key, 0), complexity(d.body))
              d.children.foreach(walk(_, owners, true))
            case d: Defn.Trait =>
              abstractions += ((rel, d.name.value))
              countInits(d.templ.inits)
              d.children.foreach(walk(_, d.name.value :: owners, inDef))
            case d: Defn.Class =>
              if d.mods.exists(_.isInstanceOf[Mod.Abstract]) then abstractions += ((rel, d.name.value))
              countInits(d.templ.inits)
              d.children.foreach(walk(_, d.name.value :: owners, inDef))
            case d: Defn.Object =>
              countInits(d.templ.inits)
              d.children.foreach(walk(_, d.name.value :: owners, inDef))
            case d: Defn.Enum =>
              countInits(d.templ.inits)
              d.children.foreach(walk(_, d.name.value :: owners, inDef))
            case d: Defn.EnumCase =>
              countInits(d.inits)
              d.children.foreach(walk(_, owners, inDef))
            case d: Defn.Given =>
              countInits(d.templ.inits)
              val nm = d.name match
                case n: Term.Name => n.value
                case _ => "given"
              d.children.foreach(walk(_, nm :: owners, inDef))
            case d: Term.NewAnonymous =>
              countInits(d.templ.inits)
              d.children.foreach(walk(_, owners, inDef))
            case other => other.children.foreach(walk(_, owners, inDef))
          def countInits(inits: List[Init]): Unit =
            for i <- inits; n <- simpleName(i.tpe) do implementors(n) += 1
          walk(src, Nil, false)
          for (k, v) <- defs.toList.sortBy(_._1) do out.append(s"G\t$rel\t$k\t$v\n")
    for (file, name) <- abstractions.toList.sortBy(identity) do
      out.append(s"H\t$file\t$name\t${implementors(name)}\n")
    out.append(s"FILES\t$parsed\n")
    print(out)
    System.out.flush()
    if failed > 0 then sys.exit(3)
'''


def _scala_cli_binary() -> str | None:
    """scala-cli on PATH, else where `cs install scala-cli` puts it, which a hook's PATH may lack."""
    found = shutil.which("scala-cli")
    if found:
        return found
    local = Path.home() / ".local" / "share" / "coursier" / "bin" / "scala-cli"
    return str(local) if local.is_file() else None


def _parse_scalameta_tsv(out: str) -> tuple[dict, dict, int]:
    """(complexity {(file, def): cc}, abstractions {(file, name): implementors}, files parsed).
    A missing FILES line is the script not reaching its end, and is refused."""
    g: dict = {}
    h: dict = {}
    files: int | None = None
    for line in out.splitlines():
        parts = line.rstrip("\n").split("\t")
        if parts[0] == "G" and len(parts) == 4:
            g[(parts[1], parts[2])] = int(parts[3])
        elif parts[0] == "H" and len(parts) == 4:
            h[(parts[1], parts[2])] = int(parts[3])
        elif parts[0] == "FILES" and len(parts) == 2:
            files = int(parts[1])
    if files is None:
        raise ScanOperationalError(
            "the scalameta scan produced no FILES line; its output is not read as a result")
    return g, h, files


def run_scalameta_scan(root: Path) -> tuple[dict, dict, int]:
    """Write the script and the file list to a scratch directory and run it there, so scala-cli's
    `.scala-build` never lands in the repo. Exit 3 is the script's own "a file did not parse";
    anything else non-zero is scala-cli or the script's compile, and both are did-not-run."""
    import tempfile
    exe = _scala_cli_binary()
    if exe is None:
        raise ScanOperationalError(
            "scala-cli not found (PATH or ~/.local/share/coursier/bin); the scalameta scan did not run")
    sources = _scala_sources(root)
    if not sources:
        raise ScanOperationalError("no .scala sources under the root; the scalameta scan examined nothing")
    with tempfile.TemporaryDirectory(prefix="sdlc-gate-scalameta-") as td:
        (Path(td) / "Gate.scala").write_text(_SCALAMETA_SCRIPT)
        (Path(td) / "files.txt").write_text("\n".join(sources) + "\n")
        cmd = [exe, "run", "--server=false", "Gate.scala", "--", str(root), "files.txt"]
        try:
            proc = subprocess.run(cmd, cwd=td, capture_output=True, text=True, check=False,
                                  timeout=1800)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ScanOperationalError(f"scala-cli could not run the scalameta scan: {e}") from e
    if proc.returncode == 3:
        bad = [l for l in proc.stdout.splitlines() if l.startswith("ERR\t")][:5]
        raise ScanOperationalError(
            "the scalameta scan could not parse every file it was given; refusing a short "
            f"denominator: {' / '.join(bad)[:400]}")
    if proc.returncode != 0:
        raise ScanOperationalError(
            f"scala-cli exited {proc.returncode} running the scalameta scan: "
            f"{proc.stderr.strip()[-400:]!r}")
    g, h, files = _parse_scalameta_tsv(proc.stdout)
    if files == 0:
        raise ScanOperationalError("the scalameta scan parsed no files; an empty scan is not a clean one")
    return g, h, files


# G and H each run the script once. The same output serves both, and the second scala-cli start
# (about 8 s over 120 files) costs less than a memo whose staleness would have to be argued.
def run_scala_complexity(root: Path) -> Scan:
    g, _, files = run_scalameta_scan(root)
    return Scan(tool="scalameta cognitive-complexity", files=files, findings=g)


def run_scala_abstractions(root: Path) -> Scan:
    _, h, files = run_scalameta_scan(root)
    return Scan(tool="scalameta abstractions", files=files, findings=h)


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



# --- TypeScript toolchain scanners --------------------------------------------
# Every format below was captured from the installed tool before its parser was written:
# `eslint -f json` (an array of {filePath, messages:[{ruleId, severity, line}]}, where ruleId is
# NULL for directive-level findings), `tsc --noEmit -p tsconfig.json` (`file(line,col): error
# TSxxxx: msg`, exit 2 on errors), and istanbul's coverage-final.json from a real vitest run.

_TS_EXT = (".ts", ".tsx", ".mts", ".cts")
# Directories that hold code nobody in this repo wrote or reviews. node_modules is the one that
# matters: it dwarfs the source tree, and a single vendored @ts-ignore would otherwise enter the
# suppression baseline and then "improve" whenever a dependency changed.
_TS_SKIP_DIRS = {"node_modules", "dist", "build", "coverage", ".next", ".turbo", "out", ".git"}


def _walk_ts(root: Path):
    for path in root.rglob("*"):
        if path.suffix not in _TS_EXT or not path.is_file():
            continue
        if _TS_SKIP_DIRS.intersection(path.relative_to(root).parts):
            continue
        yield path


def _ts_rel(root: Path, name: str) -> str:
    name = name.replace("\\", "/")
    try:
        return str(Path(name).resolve().relative_to(root.resolve()))
    except ValueError:
        return name.lstrip("/")


def _parse_eslint_json(payload: str, root: Path) -> Counter:
    """Counter[(relative_path, rule-id)]. A null ruleId is kept under `(core)` rather than
    dropped: eslint reports 'Unused eslint-disable directive' that way, and that finding is
    precisely a suppression going stale — the last thing a differential should discard."""
    counter: Counter = Counter()
    if not payload.strip():
        return counter
    try:
        entries = json.loads(payload)
    except (ValueError, TypeError):
        return counter
    if not isinstance(entries, list):
        return counter
    for entry in entries:
        rel = _ts_rel(root, entry.get("filePath") or "")
        for msg in entry.get("messages") or []:
            counter[(rel, msg.get("ruleId") or "(core)")] += 1
    return counter


def run_eslint(root: Path) -> Counter:
    exe = _ts_bin(root, "eslint")
    if exe is None:
        sys.stderr.write("sdlc-gate: eslint not invokable; skipping the ESLint scan\n")
        return Counter()
    try:
        proc = subprocess.run([*exe, "-f", "json", "."],
                              cwd=root, capture_output=True, text=True, check=False, timeout=900)
    except (OSError, subprocess.TimeoutExpired):
        sys.stderr.write("sdlc-gate: eslint not invokable; skipping the ESLint scan\n")
        return Counter()
    return _parse_eslint_json(proc.stdout, root)


_TSC_ERROR = re.compile(r"^(?P<file>[^(\s][^(]*)\((?P<line>\d+),\d+\):\s*error\s+(?P<code>TS\d+):",
                        re.MULTILINE)


def _parse_tsc_output(text: str) -> Counter:
    """Counter[(relative_path, TSxxxx)] from tsc's own diagnostic lines. tsc already reports the
    path relative to the project root, so no resolution is needed — and must not be attempted,
    because the compile runs in a scratch worktree whose absolute path is not the repo's."""
    counter: Counter = Counter()
    for m in _TSC_ERROR.finditer(text):
        counter[(m.group("file").replace("\\", "/").strip(), m.group("code"))] += 1
    return counter


def _ts_bin(root: Path, name: str) -> list[str] | None:
    """The repo's own pinned binary if it has one, else the one on PATH. A repo-local tool is
    preferred because the differential compares two trees of THIS repo, and a globally-installed
    eslint at a different major version would report a different rule set on each side."""
    local = root / "node_modules" / ".bin" / name
    if local.is_file():
        return [str(local)]
    if shutil.which(name):
        return [name]
    if shutil.which("npx"):
        return ["npx", "--no-install", name]
    return None


def run_tsc(root: Path) -> Counter:
    exe = _ts_bin(root, "tsc")
    if exe is None or not (root / "tsconfig.json").is_file():
        sys.stderr.write("sdlc-gate: tsc not invokable or no tsconfig.json; skipping the tsc scan\n")
        return Counter()
    try:
        proc = subprocess.run([*exe, "--noEmit", "-p", "tsconfig.json"],
                              cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        sys.stderr.write("sdlc-gate: tsc not invokable; skipping the tsc scan\n")
        return Counter()
    return _parse_tsc_output(proc.stdout + proc.stderr)


# Suppression directives. eslint-disable-next-line and -line are matched before the bare form,
# and the bare form carries a negative lookahead, so one `// eslint-disable-next-line` counts
# once under its own key rather than twice under two.
_TS_SUPPRESSION_PATTERNS = [
    (re.compile(r"eslint-disable-next-line"), "eslint-disable-next-line"),
    (re.compile(r"eslint-disable-line"), "eslint-disable-line"),
    (re.compile(r"eslint-disable(?!-next-line|-line)"), "eslint-disable"),
    (re.compile(r"@ts-ignore"), "ts-ignore"),
    (re.compile(r"@ts-expect-error"), "ts-expect-error"),
    (re.compile(r"@ts-nocheck"), "ts-nocheck"),
]


def scan_ts_suppressions(root: Path) -> Counter:
    """Counter[(relative_path, directive_key)] over all TypeScript sources."""
    counter: Counter = Counter()
    for path in _walk_ts(root):
        rel = str(path.relative_to(root))
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, key in _TS_SUPPRESSION_PATTERNS:
            n = len(pattern.findall(text))
            if n:
                counter[(rel, key)] += n
    return counter


# `.only` sits with the skips deliberately. It does not disable the test it marks — it disables
# every OTHER test in the file, which is a larger suppression wearing a smaller word, and a
# committed `.only` is the classic way a suite silently stops covering anything.
_TS_SKIP = re.compile(
    r"\b(?:it|test|describe|suite|bench)\.(?:skip|only|todo|skipIf|failing)\b|\bx(?:it|describe|test)\b")
_TS_ASSERT = re.compile(r"\bexpect\s*\(|\bassert\w*\s*\(")


def _ts_is_test_file(rel: str) -> bool:
    rel = "/" + rel.replace("\\", "/")
    stem = rel.rsplit("/", 1)[-1]
    return (".test." in stem or ".spec." in stem
            or "/__tests__/" in rel or "/tests/" in rel or "/test/" in rel)


def scan_ts_test_weakening(root: Path) -> dict:
    """Per-test-file skip-marker and assertion-site counts. Check D handles them exactly as for
    pytest/munit/JUnit: skips must not rise, assertion sites must not fall. No `params` sub-map —
    fast-check's numRuns is the TypeScript analogue of ScalaCheck's minSuccessfulTests and is NOT
    scanned here, so a lowered numRuns passes. Stated rather than left to be discovered."""
    skips: dict[str, int] = {}
    asserts: dict[str, int] = {}
    for path in _walk_ts(root):
        rel = str(path.relative_to(root))
        if not _ts_is_test_file(rel):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        skips[rel] = len(_TS_SKIP.findall(text))
        asserts[rel] = len(_TS_ASSERT.findall(text))
    return {"skips": skips, "asserts": asserts, "params": {}}


def ts_compile_status(root: Path) -> str:
    """`tsc --noEmit` over the project → 'ok'/'fail'/'skip'. This is the fail-closed precondition:
    a tree that does not type-check cannot produce a trustworthy eslint differential, because
    eslint's type-aware rules degrade silently on a broken program."""
    if not (root / "tsconfig.json").is_file():
        return "skip"
    exe = _ts_bin(root, "tsc")
    if exe is None:
        return "skip"
    try:
        proc = subprocess.run([*exe, "--noEmit", "-p", "tsconfig.json"],
                              cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        sys.stderr.write("sdlc-gate: tsc could not run; skipping the compile precondition\n")
        return "skip"
    return "ok" if proc.returncode == 0 else "fail"


def parse_istanbul(payload: str, root: Path) -> dict[str, float]:
    """Per-directory statement coverage from istanbul's coverage-final.json, mirroring scoverage
    and JaCoCo. A file with zero statements contributes nothing rather than being minted as 100%,
    which is the same fail-open those two parsers close."""
    data = json.loads(payload)
    agg: dict[str, list[int]] = {}
    for key, entry in (data or {}).items():
        rel = _ts_rel(root, (entry or {}).get("path") or key)
        directory = str(Path(rel).parent).replace("\\", "/")
        counts = (entry or {}).get("s") or {}
        if not counts:
            continue
        slot = agg.setdefault(directory, [0, 0])
        slot[0] += sum(1 for v in counts.values() if v)
        slot[1] += len(counts)
    return {d: hit / total * 100.0 for d, (hit, total) in agg.items() if total > 0}


def run_istanbul_coverage(root: Path) -> dict[str, float]:
    report = root / "coverage" / "coverage-final.json"
    if not report.is_file():
        raise CoverageOperationalError(
            "coverage/coverage-final.json not found — refusing to read coverage as empty "
            "(fail-closed); run the suite with --coverage and the json reporter first")
    try:
        return parse_istanbul(report.read_text(), root)
    except (OSError, ValueError) as e:
        raise CoverageOperationalError(f"coverage-final.json unreadable: {e}") from e



# --- TypeScript Checks E-H --------------------------------------------------------------------
# Captured 2026-09-10 from a scratch clone of reasoning-society/frontend (75 .ts/.tsx files) with
# eslint 9.39.4, typescript-eslint 8.63, eslint-plugin-sonarjs 4.2.0, jscpd 5.2.0 (the Rust engine),
# knip 6.35.1, typescript 6.0.3 and node 24, every one resolved from the repo's OWN node_modules.
# The gate installs nothing; a tool it cannot resolve is a ScanOperationalError, never a skip, so a
# repo that lacks one fails closed until it is added. What was measured and shaped the code:
#   - eslint exits 0 clean, 1 with findings, 2 when it could not run; a syntax error is exit 1 with
#     a `fatal` message and a null ruleId, so exit 1 alone does not mean "ran".
#   - sonarjs at threshold 0 reports every function whose complexity is > 0 (a 0 is silent), with
#     a message that carries the number and NOT the function's name; its report location is the
#     name token, the method key, the `function` keyword or the arrow's `=>`, and the walker below
#     reproduces those anchors so a finding maps to a name. All 138 findings on the corpus matched.
#   - jscpd exits 0 with clones found (exit is opt-in via --exit-code), 2 on a bad flag. Its
#     `statistics.total.sources` counts only files that are at least min-tokens and min-lines
#     long (75 handed, 66 counted at 75 tokens; every handed file counted at 1), so sources <
#     handed is healthy and only sources > handed is a mis-scoped scan. A file with a syntax error IS counted as a source
#     and NO clone inside it is found (a byte-identical 69-token function in a healthy sibling
#     was reported, the one after a broken line was not), which is the silent fallback the walker's
#     parse precondition turns into a refusal. Only the SARIF reporter carries the tool's own
#     clone hash; the JSON reporter carries the statistics; both are asked for.
#   - knip exits 0 clean, 1 with issues, 2 when it could not run (no package.json, bad config),
#     and its JSON has no count of the files it analysed, so Check E's denominator is eslint's.
#   - The TypeScript parser sets no parent pointers until the binder runs, so the walker threads
#     its own ancestor chain rather than reading `node.parent`.

# JavaScript run by node with the repo's own `typescript`; written to a temp directory UNDER the
# repo's node_modules so bare `require("typescript")` resolves from the tree under scan. Embedded
# as a string so the gate stays one file. Exits 2 with {"error"} whenever it did not examine every
# file it was handed, including on the first syntactic diagnostic in any of them.
_TS_WALKER = r"""
"use strict";
const fs = require("fs");
const path = require("path");
const { createRequire } = require("module");

function fail(msg) {
  process.stdout.write(JSON.stringify({ error: msg }) + "\n");
  process.exit(2);
}

const [mode, rootArg, listFile] = process.argv.slice(2);
const root = rootArg ? path.resolve(rootArg) : "";
if (!mode || !root || !listFile) fail("usage: walker <functions|abstractions> <root> <listfile>");
let ts;
try {
  ts = createRequire(path.join(root, "package.json"))("typescript");
} catch (e) {
  try { ts = require("typescript"); } catch (e2) { fail("typescript not resolvable from " + root + ": " + e.message); }
}
const files = JSON.parse(fs.readFileSync(listFile, "utf8"));
const rel = (f) => path.relative(root, f).split(path.sep).join("/");

function compilerOptions() {
  const cfg = path.join(root, "tsconfig.json");
  let options = { target: ts.ScriptTarget.Latest, jsx: ts.JsxEmit.Preserve, allowJs: false };
  if (mode === "abstractions" && fs.existsSync(cfg)) {
    const read = ts.readConfigFile(cfg, ts.sys.readFile);
    if (!read.error) options = { ...ts.parseJsonConfigFileContent(read.config, ts.sys, root).options };
  }
  for (const k of ["noEmit", "composite", "incremental", "tsBuildInfoFile", "declaration",
                   "declarationMap", "sourceMap", "outDir"]) delete options[k];
  if (mode === "functions") { options.noResolve = true; options.noLib = true; options.types = []; }
  return options;
}

const program = ts.createProgram(files, compilerOptions());
const handed = new Set(files.map((f) => path.resolve(f)));
const roots = program.getSourceFiles().filter((sf) => handed.has(path.resolve(sf.fileName)));
if (roots.length !== files.length) {
  fail("program holds " + roots.length + " of the " + files.length + " files handed to it");
}
for (const sf of roots) {
  const diags = program.getSyntacticDiagnostics(sf);
  if (diags.length) {
    const d = diags[0];
    const { line } = sf.getLineAndCharacterOfPosition(d.start || 0);
    fail(rel(sf.fileName) + ":" + (line + 1) + ": " + ts.flattenDiagnosticMessageText(d.messageText, " "));
  }
}

function keyText(name, sf) {
  if (!name) return "<computed>";
  if (ts.isIdentifier(name) || ts.isPrivateIdentifier(name) || ts.isStringLiteral(name)
      || ts.isNumericLiteral(name) || ts.isNoSubstitutionTemplateLiteral(name)) return name.text;
  return name.getText(sf);
}

function lineCol(sf, pos) {
  const lc = sf.getLineAndCharacterOfPosition(pos);
  return [lc.line + 1, lc.character + 1];
}

function tokenChild(node, kind, sf) {
  for (const c of node.getChildren(sf)) if (c.kind === kind) return c;
  return null;
}

// eslint-plugin-sonarjs 4.x helpers/location.js getMainFunctionTokenLocation, reproduced: a
// declaration's name (its `function` keyword when anonymous), a method's or property's key, a
// function expression's `function` keyword, an arrow's `=>`.
function anchor(node, parent, sf) {
  if (ts.isFunctionDeclaration(node)) {
    if (node.name) return lineCol(sf, node.name.getStart(sf));
    const kw = tokenChild(node, ts.SyntaxKind.FunctionKeyword, sf);
    return lineCol(sf, kw ? kw.getStart(sf) : node.getStart(sf));
  }
  if (ts.isMethodDeclaration(node) || ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node)) {
    return lineCol(sf, node.name.getStart(sf));
  }
  if (ts.isConstructorDeclaration(node)) {
    const kw = tokenChild(node, ts.SyntaxKind.ConstructorKeyword, sf);
    return lineCol(sf, kw ? kw.getStart(sf) : node.getStart(sf));
  }
  if (ts.isFunctionExpression(node)) {
    if (parent && ts.isPropertyAssignment(parent)) return lineCol(sf, parent.name.getStart(sf));
    const kw = tokenChild(node, ts.SyntaxKind.FunctionKeyword, sf);
    return lineCol(sf, kw ? kw.getStart(sf) : node.getStart(sf));
  }
  if (ts.isArrowFunction(node)) return lineCol(sf, node.equalsGreaterThanToken.getStart(sf));
  return lineCol(sf, node.getStart(sf));
}

function isFunctionLike(node) {
  return ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node) || ts.isArrowFunction(node)
    || ts.isMethodDeclaration(node) || ts.isConstructorDeclaration(node)
    || ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node);
}

function calleeName(expr) {
  if (ts.isIdentifier(expr)) return expr.text;
  if (ts.isPropertyAccessExpression(expr)) return expr.name.text;
  if (ts.isCallExpression(expr)) return calleeName(expr.expression);
  return "call";
}

// An anonymous function is named by where it sits: the variable or property it is assigned to,
// `default` for a default export, the call it is passed to plus that call's first string argument
// (which is what names a describe/it body) or an ordinal among that callee's callbacks in the
// same parent, else an ordinal. Ordinals re-key when a sibling is inserted before them; a name
// derived from a string or an assignment does not.
function ownName(node, ancestors, sf, ordinal) {
  if (ts.isFunctionDeclaration(node)) return node.name ? node.name.text : "default";
  if (ts.isConstructorDeclaration(node)) return "constructor";
  if (ts.isGetAccessorDeclaration(node)) return "get " + keyText(node.name, sf);
  if (ts.isSetAccessorDeclaration(node)) return "set " + keyText(node.name, sf);
  if (ts.isMethodDeclaration(node)) return keyText(node.name, sf);
  let i = ancestors.length - 1;
  let p = ancestors[i];
  while (p && (ts.isParenthesizedExpression(p) || ts.isAsExpression(p) || ts.isSatisfiesExpression(p)
               || ts.isTypeAssertionExpression(p) || ts.isNonNullExpression(p))) p = ancestors[--i];
  if (!p) return "<anonymous#" + ordinal("<anonymous>") + ">";
  if (ts.isVariableDeclaration(p) && ts.isIdentifier(p.name)) return p.name.text;
  if (ts.isPropertyAssignment(p) || ts.isPropertyDeclaration(p)) return keyText(p.name, sf);
  if (ts.isBinaryExpression(p) && p.operatorToken.kind === ts.SyntaxKind.EqualsToken) return p.left.getText(sf);
  if (ts.isExportAssignment(p)) return "default";
  if (ts.isCallExpression(p) || ts.isNewExpression(p)) {
    const callee = ts.isNewExpression(p) ? "new " + calleeName(p.expression) : calleeName(p.expression);
    const a0 = p.arguments && p.arguments[0];
    if (a0 && (ts.isStringLiteral(a0) || ts.isNoSubstitutionTemplateLiteral(a0)) && a0 !== node) {
      return callee + "(" + JSON.stringify(a0.text) + ")";
    }
    return callee + "#" + ordinal(callee);
  }
  return "<anonymous#" + ordinal("<anonymous>") + ">";
}

function scopeName(node, ancestors, sf) {
  if (ts.isClassDeclaration(node) || ts.isClassExpression(node)) {
    if (node.name) return node.name.text;
    const p = ancestors[ancestors.length - 1];
    if (p && ts.isVariableDeclaration(p) && ts.isIdentifier(p.name)) return p.name.text;
    return "<class>";
  }
  if (ts.isModuleDeclaration(node)) return keyText(node.name, sf);
  return null;
}

function collectFunctions(sf, out) {
  const stack = [{ name: null, counters: new Map() }];
  const ancestors = [];
  const walk = (node) => {
    const fn = isFunctionLike(node);
    const scope = fn ? null : scopeName(node, ancestors, sf);
    if (fn) {
      const parent = stack[stack.length - 1];
      const ordinal = (k) => { const n = (parent.counters.get(k) || 0) + 1; parent.counters.set(k, n); return n; };
      const own = ownName(node, ancestors, sf, ordinal);
      const name = parent.name ? parent.name + "." + own : own;
      const [line, col] = anchor(node, ancestors[ancestors.length - 1], sf);
      out.push([rel(sf.fileName), name, line, col]);
      stack.push({ name, counters: new Map() });
    } else if (scope !== null) {
      const parent = stack[stack.length - 1];
      stack.push({ name: parent.name ? parent.name + "." + scope : scope, counters: new Map() });
    }
    ancestors.push(node);
    ts.forEachChild(node, walk);
    ancestors.pop();
    if (fn || scope !== null) stack.pop();
  };
  walk(sf);
}

// Every interface and class in the handed files, with the number of handed declarations whose
// heritage clause resolves to it through the checker (so an import, alias or re-export counts and
// a same-named type in another file does not). The kind travels so the gate decides which zero
// counts are findings.
function collectAbstractions(checker, out) {
  const decls = new Map();
  for (const sf of roots) {
    const ns = [];
    const walk = (node) => {
      if ((ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node)) && node.name) {
        const isAbstract = ts.isClassDeclaration(node)
          && (ts.getCombinedModifierFlags(node) & ts.ModifierFlags.Abstract) !== 0;
        const kind = ts.isInterfaceDeclaration(node) ? "interface" : (isAbstract ? "abstract" : "class");
        decls.set(node, { file: rel(sf.fileName), name: [...ns, node.name.text].join("."), kind, count: 0 });
      }
      const isNs = ts.isModuleDeclaration(node);
      if (isNs) ns.push(keyText(node.name, sf));
      ts.forEachChild(node, walk);
      if (isNs) ns.pop();
    };
    walk(sf);
  }
  for (const sf of roots) {
    const walk = (node) => {
      if ((ts.isClassDeclaration(node) || ts.isClassExpression(node) || ts.isInterfaceDeclaration(node)) && node.heritageClauses) {
        for (const hc of node.heritageClauses) {
          for (const t of hc.types) {
            let sym = checker.getSymbolAtLocation(t.expression);
            if (sym && (sym.flags & ts.SymbolFlags.Alias)) sym = checker.getAliasedSymbol(sym);
            for (const d of (sym && sym.declarations) || []) {
              const entry = decls.get(d);
              if (entry && d !== node) entry.count += 1;
            }
          }
        }
      }
      ts.forEachChild(node, walk);
    };
    walk(sf);
  }
  for (const e of decls.values()) out.push([e.file, e.name, e.kind, e.count]);
}

const result = { files: roots.length };
if (mode === "functions") {
  result.functions = [];
  for (const sf of roots) collectFunctions(sf, result.functions);
} else if (mode === "abstractions") {
  result.abstractions = [];
  collectAbstractions(program.getTypeChecker(), result.abstractions);
} else {
  fail("unknown mode " + mode);
}
process.stdout.write(JSON.stringify(result) + "\n");
"""

# Flat configs written next to the walker, so `import "typescript-eslint"` resolves from the repo's
# node_modules. `--no-config-lookup` keeps the repo's own eslint.config.js out of it: the check must
# report the same rule set on both sides of the differential whatever the repo configures.
#
# Check E's rule set. `args: "all"` with the `^_` escape mirrors tsc's own noUnusedParameters, which
# exempts an underscore-prefixed parameter; `(_event, value) =>` is a signature the caller dictates,
# not dead code, and reporting it would have the builder rename parameters to satisfy the gate.
# Rest siblings are the omit idiom (`const { a, ...rest } = o`). The core private-member rule costs
# nothing extra and covers `#field`; a TS `private` member goes unreported here (tsc's TS6133 has it).
_TS_UNREFERENCED_CONFIG = """import tseslint from "typescript-eslint";
export default [{
  files: ["**/*.{ts,tsx,mts,cts}"],
  languageOptions: { parser: tseslint.parser },
  plugins: { "@typescript-eslint": tseslint.plugin },
  rules: {
    "@typescript-eslint/no-unused-vars": ["error", {
      vars: "all", args: "all", argsIgnorePattern: "^_", caughtErrors: "all",
      caughtErrorsIgnorePattern: "^_", destructuredArrayIgnorePattern: "^_", ignoreRestSiblings: true }],
    "no-unused-private-class-members": "error",
  },
}];
"""
_TS_UNREFERENCED_RULES = {"@typescript-eslint/no-unused-vars", "no-unused-private-class-members"}

# Threshold 0 so the rule REPORTS every function's value; the gate applies COMPLEXITY_THRESHOLD.
_TS_COMPLEXITY_CONFIG = """import tseslint from "typescript-eslint";
import sonarjs from "eslint-plugin-sonarjs";
export default [{
  files: ["**/*.{ts,tsx,mts,cts}"],
  languageOptions: { parser: tseslint.parser },
  plugins: { sonarjs },
  rules: { "sonarjs/cognitive-complexity": ["error", 0] },
}];
"""
_TS_COMPLEXITY_RULE = "sonarjs/cognitive-complexity"
_TS_COMPLEXITY_MSG = re.compile(r"Cognitive Complexity from (?P<n>\d+) to the \d+ allowed")

# knip issue types that are declared-but-unreferenced code. The other direction (unlisted,
# unresolved, binaries: referenced but not declared) is a correctness matter, not Check E's.
_TS_KNIP_INCLUDE = ("files", "dependencies", "exports", "nsExports", "types", "nsTypes",
                    "enumMembers", "namespaceMembers")
_TS_KNIP_KEYS = _TS_KNIP_INCLUDE + ("devDependencies", "optionalPeerDependencies")


def _ts_files(root: Path) -> list[str]:
    """Repo-relative, sorted: the set every Check E-H tool is handed and measured against."""
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in _walk_ts(root))


def _ts_scratch_dir(root: Path) -> Path:
    """A temp dir under the repo's node_modules, so a config or script placed there resolves the
    repo's packages by bare specifier. No node_modules means no tool can run: refuse now."""
    nm = root / "node_modules"
    if not nm.is_dir():
        raise ScanOperationalError(
            f"{nm} does not exist; Checks E-H resolve eslint, jscpd, knip and typescript from the "
            "repo's own node_modules (install them; the gate installs nothing)")
    import tempfile
    return Path(tempfile.mkdtemp(prefix=".sdlc-gate-", dir=nm))


def _ts_run_eslint_json(root: Path, config: str, files: list[str]) -> list[dict]:
    """eslint with a gate-owned flat config over exactly `files`. One JSON entry per file linted;
    the count is asserted against what was handed, a `fatal` message (a parse failure) refuses,
    and only exit 0/1 with a JSON body is a scan."""
    exe = _ts_bin(root, "eslint")
    if exe is None:
        raise ScanOperationalError("eslint not invokable (no node_modules/.bin/eslint, none on PATH)")
    scratch = _ts_scratch_dir(root)
    try:
        cfg = scratch / "eslint.config.mjs"
        cfg.write_text(config)
        try:
            proc = subprocess.run([*exe, "--no-config-lookup", "-c", str(cfg), "-f", "json", *files],
                                  cwd=root, capture_output=True, text=True, check=False, timeout=1800)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ScanOperationalError(f"eslint could not run: {e}") from e
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if proc.returncode not in (0, 1):
        raise ScanOperationalError(
            f"eslint exited {proc.returncode}: {proc.stderr.strip()[:300]!r}; an eslint that did not "
            "run must not read as 'no findings'")
    try:
        entries = json.loads(proc.stdout)
    except ValueError as e:
        raise ScanOperationalError(f"eslint produced non-JSON output ({e}); refusing to read it as empty") from e
    if not isinstance(entries, list):
        raise ScanOperationalError("eslint JSON is not the per-file array its formatter documents")
    for entry in entries:
        for msg in entry.get("messages") or []:
            if msg.get("fatal"):
                raise ScanOperationalError(
                    f"eslint could not parse {_ts_rel(root, entry.get('filePath') or '')}:"
                    f"{msg.get('line')}: {msg.get('message')}; a file that did not parse was not scanned")
    if len(entries) != len(files):
        raise ScanOperationalError(
            f"eslint reported on {len(entries)} files but was handed {len(files)}; the denominator "
            "does not cover the tree")
    return entries


def _ts_run_walker(root: Path, mode: str, files: list[str]) -> dict:
    """The embedded walker in one mode. The script exits 2 with {"error"} whenever it did not
    examine every handed file, and its file count is asserted here as well."""
    node = shutil.which("node")
    if node is None:
        raise ScanOperationalError("node not on PATH; the TypeScript walker cannot run")
    scratch = _ts_scratch_dir(root)
    try:
        script = scratch / "walker.cjs"
        script.write_text(_TS_WALKER)
        listing = scratch / "files.json"
        listing.write_text(json.dumps([str(root / f) for f in files]))
        try:
            proc = subprocess.run([node, str(script), mode, str(root), str(listing)],
                                  cwd=root, capture_output=True, text=True, check=False, timeout=1800)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ScanOperationalError(f"walker ({mode}) could not run: {e}") from e
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        raise ScanOperationalError(
            f"walker ({mode}) exited {proc.returncode} without JSON: {proc.stderr.strip()[:300]!r}")
    if proc.returncode != 0 or not isinstance(out, dict) or "error" in out:
        why = out.get("error") if isinstance(out, dict) else out
        raise ScanOperationalError(f"walker ({mode}) refused: {why or proc.stderr.strip()[:300]!r}")
    if out.get("files") != len(files):
        raise ScanOperationalError(f"walker ({mode}) examined {out.get('files')} of {len(files)} files")
    return out


def _ts_run_knip(root: Path) -> Counter:
    """Counter[(file, 'knip:<issue type>')]. knip's documented exit codes: 0 clean, 1 issues, 2 did
    not run; the body must be its JSON reporter's {"issues": [...]} or the run is refused."""
    exe = _ts_bin(root, "knip")
    if exe is None:
        raise ScanOperationalError("knip not invokable (no node_modules/.bin/knip, none on PATH)")
    try:
        proc = subprocess.run([*exe, "--no-progress", "--no-config-hints", "--reporter", "json",
                               "--include", ",".join(_TS_KNIP_INCLUDE)],
                              cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ScanOperationalError(f"knip could not run: {e}") from e
    if proc.returncode not in (0, 1):
        raise ScanOperationalError(f"knip exited {proc.returncode}: {proc.stderr.strip()[:300]!r}")
    try:
        report = json.loads(proc.stdout)
    except ValueError as e:
        raise ScanOperationalError(f"knip produced non-JSON output ({e}); refusing to read it as clean") from e
    if not isinstance(report, dict) or not isinstance(report.get("issues"), list):
        raise ScanOperationalError("knip JSON lacks the 'issues' array its reporter documents")
    counter: Counter = Counter()
    for issue in report["issues"]:
        file = str(issue.get("file") or "").replace("\\", "/")
        for key in _TS_KNIP_KEYS:
            items = issue.get(key) or []
            n = sum(len(v) for v in items.values()) if isinstance(items, dict) else len(items)
            if n:
                counter[(file, f"knip:{key}")] += n
    return counter


def run_ts_unreferenced(root: Path) -> Scan:
    """Check E: eslint's unused-vars family per file plus knip's unused files/exports/types/members/
    dependencies. The denominator is eslint's (knip publishes none)."""
    files = _ts_files(root)
    if not files:
        return Scan("eslint+knip", 0, {})
    entries = _ts_run_eslint_json(root, _TS_UNREFERENCED_CONFIG, files)
    counter: Counter = Counter()
    for entry in entries:
        rel = _ts_rel(root, entry.get("filePath") or "")
        for msg in entry.get("messages") or []:
            if msg.get("ruleId") in _TS_UNREFERENCED_RULES:
                counter[(rel, msg["ruleId"])] += 1
    counter.update(_ts_run_knip(root))
    return Scan("eslint+knip", len(entries), dict(counter))


def run_ts_duplication(root: Path) -> Scan:
    """Check F: jscpd over the whole tree, keyed by the tool's own clone hash. The walker's parse
    pass runs first because a file jscpd cannot lex is counted and then silently not searched."""
    files = _ts_files(root)
    if not files:
        return Scan("jscpd", 0, {})
    _ts_run_walker(root, "functions", files)
    exe = _ts_bin(root, "jscpd")
    if exe is None:
        raise ScanOperationalError("jscpd not invokable (no node_modules/.bin/jscpd, none on PATH)")
    import tempfile
    out_dir = Path(tempfile.mkdtemp(prefix="sdlc-gate-jscpd-"))
    try:
        try:
            proc = subprocess.run(
                [*exe, "--min-tokens", str(DUP_MIN_TOKENS), "--reporters", "json,sarif",
                 "--output", str(out_dir), "--format", "typescript,tsx",
                 "--ignore", ",".join(f"**/{d}/**" for d in sorted(_TS_SKIP_DIRS)),
                 "--no-gitignore", "--max-size", "1gb", "--max-lines", "100000000", "--no-colors", "."],
                cwd=root, capture_output=True, text=True, check=False, timeout=1800)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ScanOperationalError(f"jscpd could not run: {e}") from e
        if proc.returncode != 0:
            raise ScanOperationalError(
                f"jscpd exited {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:300]!r}")
        try:
            report = json.loads((out_dir / "jscpd-report.json").read_text())
            sarif = json.loads((out_dir / "jscpd-report.sarif").read_text())
        except (OSError, ValueError) as e:
            raise ScanOperationalError(f"jscpd wrote no readable report: {e}") from e
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    try:
        sources = int(report["statistics"]["total"]["sources"])
        duplicates = report["duplicates"]
        results = sarif["runs"][0]["results"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise ScanOperationalError(f"jscpd report lacks the fields its reporters document: {e!r}") from e
    if sources > len(files):
        raise ScanOperationalError(
            f"jscpd counted {sources} sources but was handed {len(files)} files; it scanned outside the tree")
    if len(results) != len(duplicates):
        raise ScanOperationalError(
            f"jscpd's SARIF carries {len(results)} clones and its JSON {len(duplicates)}; same run, different reports")
    findings: dict[str, list] = {}
    for r in results:
        fp = (r.get("properties") or {}).get("clone_hash") or (r.get("partialFingerprints") or {}).get("jscpdCloneHash/v1")
        locs = [loc for loc in (r.get("locations") or [])] + [loc for loc in (r.get("relatedLocations") or [])]
        occs = []
        for loc in locs:
            phys = loc.get("physicalLocation") or {}
            uri = ((phys.get("artifactLocation") or {}).get("uri") or "").replace("\\", "/")
            region = phys.get("region") or {}
            if not fp or not uri or "startLine" not in region:
                raise ScanOperationalError("jscpd SARIF result lacks a hash, a uri or a region")
            occs.append([uri, int(region["startLine"]), int(region.get("endLine", region["startLine"]))])
        merged = findings.setdefault(fp, [])
        for o in occs:
            if o not in merged:
                merged.append(o)
    for occs in findings.values():
        occs.sort()
    return Scan("jscpd", sources, findings)


def run_ts_complexity(root: Path) -> Scan:
    """Check G: sonarjs's number for every function, named by the walker's anchor table. An anchor
    the table lacks is kept under `<line N>` rather than dropped, so the value still counts."""
    files = _ts_files(root)
    if not files:
        return Scan("eslint-plugin-sonarjs", 0, {})
    entries = _ts_run_eslint_json(root, _TS_COMPLEXITY_CONFIG, files)
    table = {(f, line, col): name for f, name, line, col in _ts_run_walker(root, "functions", files)["functions"]}
    findings: dict[tuple[str, str], int] = {}
    for entry in entries:
        rel = _ts_rel(root, entry.get("filePath") or "")
        for msg in entry.get("messages") or []:
            if msg.get("ruleId") != _TS_COMPLEXITY_RULE:
                continue
            m = _TS_COMPLEXITY_MSG.search(msg.get("message") or "")
            if not m:
                raise ScanOperationalError(
                    f"sonarjs message carries no complexity value: {msg.get('message')!r}; the format "
                    "this parser was written against has changed")
            name = table.get((rel, msg.get("line"), msg.get("column"))) or f"<line {msg.get('line')}>"
            key = (rel, name)
            findings[key] = max(findings.get(key, 0), int(m.group("n")))
    return Scan("eslint-plugin-sonarjs", len(entries), findings)


def run_ts_abstractions(root: Path) -> Scan:
    """Check H: implementor counts from the walker. An abstract class is always an abstraction. An
    interface or concrete class is one only once something extends or implements it: TypeScript
    is structural, so a `Props` interface with no `implements` anywhere is a type, not a contract
    nobody honours, and reporting it at 0 would fire on nearly every new component. The refusal
    the check exists for, a base class or interface extracted for ONE implementor, is the
    count-1 case and is kept."""
    files = _ts_files(root)
    if not files:
        return Scan("typescript-api", 0, {})
    out = _ts_run_walker(root, "abstractions", files)
    findings = {(f, name): int(count) for f, name, kind, count in out["abstractions"]
                if kind == "abstract" or int(count) >= 1}
    return Scan("typescript-api", out["files"], findings)




# --- Go toolchain scanners ----------------------------------------------------
# Captured from golangci-lint 2.12.2 and go 1.26 before any parser here was written. Two captured
# facts differ from the obvious guess and each has a test: golangci-lint appends a human summary
# AFTER its JSON document, and a coverprofile names files by module path rather than by repo path.

# vendor/ is dependency source nobody here reviews; testdata/ is excluded from the build by the
# go tool itself and routinely holds deliberately-broken fixtures, so scanning it would report
# findings against files that are supposed to be wrong.
_GO_SKIP_DIRS = {"vendor", "testdata", ".git"}


def _walk_go(root: Path):
    for path in root.rglob("*.go"):
        if not path.is_file():
            continue
        if _GO_SKIP_DIRS.intersection(path.relative_to(root).parts):
            continue
        yield path


def _parse_golangci_json(payload: str, root: Path) -> Counter:
    """Counter[(relative_path, linter)].

    golangci-lint 2.x with `--output.json.path stdout` writes its JSON document and then appends
    a human-readable summary ("3 issues:", "* errcheck: 1"). Feeding the whole stream to
    json.loads raises `Extra data`, and a parser that swallowed that error would report zero
    findings on every run — a differential that always passes. So the object is taken from the
    stream by decoding the first document and ignoring whatever trails it."""
    counter: Counter = Counter()
    if not payload.strip():
        return counter
    try:
        doc, _ = json.JSONDecoder().raw_decode(payload.lstrip())
    except ValueError:
        return counter
    if not isinstance(doc, dict):
        return counter
    for issue in doc.get("Issues") or []:
        pos = issue.get("Pos") or {}
        rel = (pos.get("Filename") or "").replace("\\", "/")
        if not rel:
            continue
        try:
            rel = str(Path(rel).resolve().relative_to(root.resolve()))
        except ValueError:
            rel = rel.lstrip("/")
        counter[(rel, issue.get("FromLinter") or "unknown")] += 1
    return counter


def run_golangci(root: Path) -> Counter:
    if not shutil.which("golangci-lint"):
        sys.stderr.write("sdlc-gate: golangci-lint not invokable; skipping the Go lint scan\n")
        return Counter()
    try:
        proc = subprocess.run(["golangci-lint", "run", "--output.json.path", "stdout", "./..."],
                              cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        sys.stderr.write("sdlc-gate: golangci-lint not invokable; skipping the Go lint scan\n")
        return Counter()
    return _parse_golangci_json(proc.stdout, root)


# `//nolint` bare, and `//nolint:linter1,linter2`. Each named linter becomes its own key so that
# widening `//nolint:errcheck` to `//nolint:errcheck,gosec` registers as a NEW suppression —
# keyed as one string, a broadened directive would look identical to a moved one.
_GO_NOLINT = re.compile(r"//\s*nolint(?::(?P<linters>[\w,\-]+))?")


def scan_go_suppressions(root: Path) -> Counter:
    """Counter[(relative_path, directive_key)] over all Go sources."""
    counter: Counter = Counter()
    for path in _walk_go(root):
        rel = str(path.relative_to(root))
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for m in _GO_NOLINT.finditer(text):
            linters = m.group("linters")
            if linters:
                for name in (x.strip() for x in linters.split(",")):
                    if name:
                        counter[(rel, f"nolint:{name}")] += 1
            else:
                counter[(rel, "nolint")] += 1
    return counter


# Skip family, and assertion sites across the stdlib idiom plus testify, which is near-universal.
_GO_SKIP = re.compile(r"\bt\.Skip(?:f|Now)?\s*\(|\bb\.Skip(?:f|Now)?\s*\(")
_GO_ASSERT = re.compile(
    r"\bt\.(?:Error|Errorf|Fatal|Fatalf)\s*\(|\b(?:assert|require)\.[A-Z]\w*\s*\(")


def _go_is_test_file(rel: str) -> bool:
    return rel.endswith("_test.go")


def scan_go_test_weakening(root: Path) -> dict:
    """Per-test-file skip-marker and assertion-site counts. Check D handles them as for every
    other toolchain: skips must not rise, assertion sites must not fall. No `params` sub-map —
    Go's property libraries are not standardised, so there is no analogue of ScalaCheck's
    minSuccessfulTests to police, and a fuzz corpus reduction would pass unseen."""
    skips: dict[str, int] = {}
    asserts: dict[str, int] = {}
    for path in _walk_go(root):
        rel = str(path.relative_to(root))
        if not _go_is_test_file(rel):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        skips[rel] = len(_GO_SKIP.findall(text))
        asserts[rel] = len(_GO_ASSERT.findall(text))
    return {"skips": skips, "asserts": asserts, "params": {}}


def go_compile_status(root: Path) -> str:
    """'ok'/'fail'/'skip' via `go test -run=^$ ./...`, which compiles the package AND its test
    files while running no test. `go build ./...` is the wrong precondition here: it never
    compiles _test.go, so a broken test source would pass it and then truncate every scan that
    reads test files — the same fail-open the Scala side closed by using Test/compile."""
    if not (root / "go.mod").is_file() or not shutil.which("go"):
        return "skip"
    try:
        proc = subprocess.run(["go", "test", "-run=^$", "-count=1", "./..."],
                              cwd=root, capture_output=True, text=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        sys.stderr.write("sdlc-gate: go compile could not run; skipping the compile precondition\n")
        return "skip"
    return "ok" if proc.returncode == 0 else "fail"


_GO_COVER_LINE = re.compile(r"^(?P<file>\S+?):\d+\.\d+,\d+\.\d+\s+(?P<stmts>\d+)\s+(?P<count>\d+)\s*$")


def parse_go_coverprofile(text: str, module_path: str) -> dict[str, float]:
    """Per-directory statement coverage from a `go test -coverprofile` file.

    The profile names each file by MODULE path — `example.com/m/internal/a/x.go` for a file at
    `internal/a/x.go` — so the module prefix is stripped before keying. Left on, every key would
    differ from nothing on the other side of the differential and each package would read as new.
    A block with zero statements contributes nothing rather than being minted as 100%."""
    agg: dict[str, list[int]] = {}
    prefix = module_path.rstrip("/") + "/" if module_path else ""
    for line in text.splitlines():
        m = _GO_COVER_LINE.match(line.strip())
        if not m:
            continue
        rel = m.group("file")
        if prefix and rel.startswith(prefix):
            rel = rel[len(prefix):]
        stmts, count = int(m.group("stmts")), int(m.group("count"))
        if stmts == 0:
            continue
        directory = str(Path(rel).parent).replace("\\", "/")
        slot = agg.setdefault(directory, [0, 0])
        slot[0] += stmts if count > 0 else 0
        slot[1] += stmts
    return {d: hit / total * 100.0 for d, (hit, total) in agg.items() if total > 0}


def _go_module_path(root: Path) -> str:
    try:
        for line in (root / "go.mod").read_text().splitlines():
            if line.startswith("module "):
                return line.split(None, 1)[1].strip()
    except OSError:
        pass
    return ""


def run_go_coverage(root: Path) -> dict[str, float]:
    profile = next((p for p in (root / "coverage.out", root / "cover.out") if p.is_file()), None)
    if profile is None:
        raise CoverageOperationalError(
            "no Go coverprofile found (coverage.out / cover.out) — refusing to read coverage as "
            "empty (fail-closed); run `go test -coverprofile=coverage.out ./...` first")
    try:
        return parse_go_coverprofile(profile.read_text(), _go_module_path(root))
    except OSError as e:
        raise CoverageOperationalError(f"coverprofile unreadable: {e}") from e


# --- Go: Checks E-H --------------------------------------------------------------------------
# Captured from golangci-lint 2.12.2 (its source at pkg/exitcodes: 0 clean, 1 issues, 2 warning
# under test, 3 failure, 4 timeout, 5 no Go files, 6 no config, 7 error logged) against
# a 2,045-file Go corpus on 2026-09-10. Three facts shaped every runner here:
#
#  - One syntax error in ONE file leaves exit code 1 — the same as "issues found" — with a single
#    `typecheck` issue and ZERO findings from every other linter for the WHOLE tree (9,349 gocognit
#    rows vanished). So the exit code cannot tell did-not-run from clean, and a `typecheck` issue
#    in the stream is the signal that the scan is not one.
#  - `--max-issues-per-linter` (50), `--max-same-issues` (3) and `--uniq-by-line` are on by default
#    and each silently truncates a count; a differential over truncated counts passes.
#  - With `--config` outside the tree, `Pos.Filename` is relative to the CONFIG's directory
#    (v2's `relative-path-mode: cfg`), so paths are asked for absolute and relativised here.
#
# The gate writes its own config for each check rather than reading the repo's, so the repo's
# exclusions, linter set and path skips cannot shape the denominator or the findings. The lock
# golangci-lint takes on /tmp by default is waived (`--allow-parallel-runners`): an IDE's lint in
# flight would otherwise make the gate exit 3 for a reason unrelated to the tree.

_GOLANGCI_ISSUE_LIMITS = """issues:
  max-issues-per-linter: 0
  max-same-issues: 0
  uniq-by-line: false
"""

# Check E. `unused` is default-on and skips EXPORTED identifiers (a blind spot to know about:
# an exported helper nobody calls is not reported). revive's `unused-parameter` only — its
# `unused-receiver` was measured on the corpus at 352 non-test hits, every one an
# interface-satisfying method with a named receiver (`func (c *X) CanFix() bool { return false }`),
# healthy Go that a new-count block would make the builder rename to `_`. unparam at its default:
# `check-exported: true` reported 15 non-test results, all exported methods satisfying an interface
# (`(*limitedWriter).Write` "result 1 (error) is always nil"), which is why the corpus's own CI is
# green with unparam on. Unused locals and imports are compile errors in Go and need no linter.
_GO_UNREFERENCED_CONFIG = """version: "2"
linters:
  default: none
  enable:
    - unused
    - unparam
    - revive
  settings:
    revive:
      rules:
        - name: unused-parameter
""" + _GOLANGCI_ISSUE_LIMITS

# Check G. gocognit reports a function only when its complexity is STRICTLY above
# min-complexity, so 0 reports every function that has any (a 0 could never block anyway).
_GO_COMPLEXITY_CONFIG = """version: "2"
linters:
  default: none
  enable:
    - gocognit
  settings:
    gocognit:
      min-complexity: 0
""" + _GOLANGCI_ISSUE_LIMITS

# Check F. Tests are not loaded at all (`run.tests: false`) rather than filtered afterwards:
# table-driven tests are a constant clone source, and filtering would still leave a clone
# between a test and a non-test file reported against the non-test side.
_GO_DUPLICATION_CONFIG = """version: "2"
run:
  tests: false
linters:
  default: none
  enable:
    - dupl
  settings:
    dupl:
      threshold: {threshold}
""" + _GOLANGCI_ISSUE_LIMITS

_GO_LIST_FILE_FIELDS = ("GoFiles", "CgoFiles", "TestGoFiles", "XTestGoFiles")


def _go_json_stream(payload: str) -> list:
    """`go list -json` writes one object after another, not an array."""
    dec = json.JSONDecoder()
    out, i = [], 0
    while True:
        while i < len(payload) and payload[i].isspace():
            i += 1
        if i >= len(payload):
            return out
        obj, i = dec.raw_decode(payload, i)
        out.append(obj)


def _go_list(root: Path, args: list[str], what: str) -> list[dict]:
    try:
        proc = subprocess.run(["go", "list", *args, "./..."], cwd=root, capture_output=True,
                              text=True, check=False, timeout=1800)
    except OSError as e:
        raise ScanOperationalError(f"{what}: `go list` could not start: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise ScanOperationalError(f"{what}: `go list` timed out") from e
    if proc.returncode != 0:
        raise ScanOperationalError(
            f"{what}: `go list` exited {proc.returncode}: {proc.stderr.strip()[:300]!r}")
    try:
        return _go_json_stream(proc.stdout)
    except ValueError as e:
        raise ScanOperationalError(f"{what}: `go list` output was not JSON ({e})") from e


def _go_files_examined(root: Path, tests: bool, what: str) -> int:
    """The denominator: golangci-lint loads `./...` through go/packages, which is `go list` with
    the same pattern, so the files it examines are the ones `go list` names — build-tag-excluded
    files (IgnoredGoFiles), vendor/ and testdata/ are outside both."""
    fields = _GO_LIST_FILE_FIELDS if tests else _GO_LIST_FILE_FIELDS[:2]
    files: set[str] = set()
    for pkg in _go_list(root, ["-e", "-json=Dir," + ",".join(fields)], what):
        for field in fields:
            for name in pkg.get(field) or []:
                files.add(str(Path(pkg.get("Dir") or "") / name))
    return len(files)


def _golangci_issues(root: Path, check: str, config: str) -> list[dict]:
    """Run golangci-lint under a gate-owned config; the issue list, or ScanOperationalError.
    Exit 0 and 1 are the only scans. A `typecheck` issue, a Report.Error, or a Report.Warnings
    (how a linter that could not run is surfaced) each mean the tree was not fully examined."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / f"sdlc-gate-{check}.yml"
        cfg.write_text(config)
        cmd = ["golangci-lint", "run", "--config", str(cfg), "--output.json.path", "stdout",
               "--show-stats=false", "--path-mode", "abs", "--allow-parallel-runners", "./..."]
        try:
            proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False,
                                  timeout=1800)
        except OSError as e:
            raise ScanOperationalError(f"check {check}: golangci-lint could not start: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise ScanOperationalError(f"check {check}: golangci-lint timed out") from e
    if proc.returncode not in (0, 1):
        raise ScanOperationalError(
            f"check {check}: golangci-lint exited {proc.returncode} (0 clean, 1 findings; anything "
            f"else did not run): {proc.stderr.strip()[:300]!r}")
    try:
        doc, _ = json.JSONDecoder().raw_decode(proc.stdout.lstrip())
    except ValueError as e:
        raise ScanOperationalError(
            f"check {check}: golangci-lint wrote non-JSON output ({e}); refusing to read it as "
            "no findings") from e
    if not isinstance(doc, dict):
        raise ScanOperationalError(f"check {check}: golangci-lint output was not an object")
    report = doc.get("Report") or {}
    if report.get("Error") or report.get("Warnings"):
        raise ScanOperationalError(
            f"check {check}: golangci-lint reported a problem: "
            f"{report.get('Error') or report.get('Warnings')!r}"[:400])
    issues = doc.get("Issues") or []
    typecheck = [i for i in issues if i.get("FromLinter") == "typecheck"]
    if typecheck:
        pos = typecheck[0].get("Pos") or {}
        raise ScanOperationalError(
            f"check {check}: the tree did not parse or type-check ({len(typecheck)} typecheck "
            f"issue(s); first: {pos.get('Filename')}:{pos.get('Line')} {typecheck[0].get('Text')!r}); "
            "every other linter's findings are truncated or absent on such a tree")
    return issues


def _go_issue_rel(issue: dict, root: Path) -> str:
    name = ((issue.get("Pos") or {}).get("Filename") or "").replace("\\", "/")
    try:
        return str(Path(name).resolve().relative_to(root.resolve()))
    except ValueError:
        return name


def _go_unreferenced_code(issue: dict) -> str:
    """(linter, kind) as one key. Shapes captured on a planted module: revive
    `unused-parameter: parameter 'b' seems to be unused, ...`; unused `func helperNeverCalled is
    unused` / `type sinkA is unused` / `func sinkA.Write is unused`; unparam
    `alwaysNil - result 1 (error) is always nil`."""
    linter = issue.get("FromLinter") or "unknown"
    text = issue.get("Text") or ""
    if linter == "revive":
        return "revive/" + text.split(":", 1)[0].strip()
    if linter == "unused":
        return "unused/" + (text.split(" ", 1)[0] or "other")
    if linter == "unparam":
        if "always receives" in text:
            return "unparam/always-receives"
        if " is unused" in text:
            return "unparam/param"
        if "result " in text:
            return "unparam/result"
        return "unparam/other"
    return f"{linter}/other"


def go_unreferenced(root: Path) -> Scan:
    findings: dict = {}
    for issue in _golangci_issues(root, "E", _GO_UNREFERENCED_CONFIG):
        key = (_go_issue_rel(issue, root), _go_unreferenced_code(issue))
        findings[key] = findings.get(key, 0) + 1
    return Scan("golangci-lint unused/unparam/revive", _go_files_examined(root, True, "check E"),
                findings)


_GO_COGNIT = re.compile(r"^cognitive complexity (?P<cc>\d+) of func `(?P<fn>[^`]+)` is high")


def go_complexity(root: Path) -> Scan:
    """(file, func) -> cognitive complexity. Methods arrive as `(*T).Name`. The only key that can
    repeat within a file is `init`, which Go allows more than once; the larger value is kept."""
    findings: dict = {}
    for issue in _golangci_issues(root, "G", _GO_COMPLEXITY_CONFIG):
        m = _GO_COGNIT.match(issue.get("Text") or "")
        if not m:
            raise ScanOperationalError(
                f"check G: unrecognised gocognit message {issue.get('Text')!r}; the parser is "
                "out of date with the tool, not the tree with the rule")
        key = (_go_issue_rel(issue, root), m.group("fn"))
        findings[key] = max(findings.get(key, 0), int(m.group("cc")))
    return Scan("golangci-lint gocognit", _go_files_examined(root, True, "check G"), findings)


# dupl groups clones by a hash over syntax-node TYPES alone (its syntax/hashSeq), so members of a
# group differ freely in identifiers, literals and operators, and it reports a group as a ring —
# each member "is duplicate of" the next. Groups are rebuilt from the ring here.
_GO_DUPL_TEXT = re.compile(r"^(\d+)-(\d+) lines are duplicate of `(?P<file>.+):(?P<s>\d+)-(?P<e>\d+)`$")

_GO_KEYWORDS = frozenset("break default func interface select case defer go map struct chan else "
                         "goto package switch const fallthrough if range type continue for import "
                         "return var".split())
_GO_TOKEN = re.compile(r"""
    (?P<skip>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<lit>`[^`]*`|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])+'|\d[\w.]*(?:(?<=[eEpP])[-+][\w.]*)?|\.\d[\w.]*)
  | (?P<ident>[^\W\d]\w*)
  | (?P<op><<=|>>=|&\^=|\.\.\.|&&|\|\||<-|\+\+|--|==|!=|<=|>=|:=|[-+*/%&|^]=|<<|>>|&\^|.)
""", re.S | re.X)


def _go_normalized_tokens(src: str) -> str:
    """Identifiers to `I`, literals to `L`, comments and whitespace gone, keywords and operators
    kept: the fingerprint survives a rename, a re-indent or a changed constant in one copy, which
    is what keeps a pre-existing clone from reading as new on every edit near it."""
    out = []
    for m in _GO_TOKEN.finditer(src):
        if m.group("skip"):
            continue
        if m.group("lit"):
            out.append("L")
        elif m.group("ident"):
            out.append(m.group("ident") if m.group("ident") in _GO_KEYWORDS else "I")
        else:
            out.append(m.group("op"))
    return " ".join(out)


def _go_clone_groups(issues: list[dict], root: Path) -> list[list[tuple[str, int, int]]]:
    parent: dict = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for issue in issues:
        m = _GO_DUPL_TEXT.match(issue.get("Text") or "")
        rng = issue.get("LineRange") or {}
        if not m or "From" not in rng:
            raise ScanOperationalError(
                f"check F: unrecognised dupl message {issue.get('Text')!r}; the parser is out of "
                "date with the tool, not the tree with the rule")
        src = (_go_issue_rel(issue, root), int(rng["From"]), int(rng["To"]))
        # The "duplicate of" path is the shortest path from the tool's cwd, the root.
        dst = (m.group("file").replace("\\", "/"), int(m.group("s")), int(m.group("e")))
        parent[find(src)] = find(dst)
    groups: dict = {}
    for member in parent:
        groups.setdefault(find(member), []).append(member)
    return [sorted(g) for g in groups.values() if len(g) > 1]


def go_duplication(root: Path) -> Scan:
    """fingerprint -> [[file, start, end], ...] over the non-test tree. The fingerprint is the
    MULTISET of the members' normalized token streams, so a third copy of a clone the baseline
    already had is a new fingerprint (the pair's was different) while the pair itself, moved down
    the file by an edit above it, is not."""
    import hashlib

    config = _GO_DUPLICATION_CONFIG.format(threshold=DUP_MIN_TOKENS)
    findings: dict = {}
    for group in _go_clone_groups(_golangci_issues(root, "F", config), root):
        hashes = []
        for file, start, end in group:
            try:
                lines = (root / file).read_text().splitlines()
            except OSError as e:
                raise ScanOperationalError(f"check F: dupl named {file}, which cannot be read: {e}") from e
            block = "\n".join(lines[start - 1:end])
            hashes.append(hashlib.sha1(_go_normalized_tokens(block).encode()).hexdigest())
        fp = hashlib.sha1("\n".join(sorted(hashes)).encode()).hexdigest()[:24]
        occs = [[f, s, e] for f, s, e in group]
        findings[fp] = sorted(findings.get(fp, []) + occs)
    return Scan("golangci-lint dupl", _go_files_examined(root, False, "check F"), findings)


# Check H is not off the shelf. golangci-lint's `iface` linter has an `opaque` check that reads
# like it, but its source (uudashr/iface/opaque) reports a FUNCTION whose declared interface
# return always carries one concrete type; it counts no implementors, so a new constructor for a
# five-implementor interface would read as a single-implementor abstraction. Instead the count is
# taken with go/types, whose `Implements` is the compiler's own answer, through a program the gate
# writes out and runs with `go run` — the toolchain the module itself selects, so the export data
# `go list -export` wrote is read by the importer that understands it.
#
# Main-module packages are type-checked FROM SOURCE: export data carries only the unexported
# types reachable from the exported API (measured: 5 of 25 in one package), and a constructor's
# unexported implementor is exactly what must be counted. Candidates are every named type in the
# module, test files included (a test double is an implementor: the consumer-side interface with
# one production type and one fake is idiomatic Go, not speculative generality), plus the exported
# types of every package the module imports (`*http.Client` satisfying a local `Doer`). What is
# counted is the DEFAULT build: a file behind a build tag is outside it, as it is for golangci-lint.
# Generic interfaces and generic candidates are skipped (nothing to instantiate them with), as is
# any interface with no methods.
_GO_IMPLEMENTORS_SRC = r'''
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/build"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type listPkg struct {
	ImportPath string
	Dir        string
	GoFiles    []string
	CgoFiles   []string
	Export     string
	ImportMap  map[string]string
	Module     *struct{ Main bool }
	Error      *struct{ Err string }
}

type loader struct {
	fset    *token.FileSet
	pkgs    map[string]*listPkg
	checked map[string]*types.Package
	gc      types.Importer
	cur     *listPkg
	files   map[string]bool
	errs    []string
}

// Import resolves through the importing package's ImportMap first, so that an external test
// (`pkg_test [pkg.test]`) sees `pkg [pkg.test]` and not the non-test build of the same package.
func (l *loader) Import(path string) (*types.Package, error) {
	if l.cur != nil {
		if mapped, ok := l.cur.ImportMap[path]; ok {
			path = mapped
		}
	}
	if p, ok := l.checked[path]; ok {
		return p, nil
	}
	if lp, ok := l.pkgs[path]; ok && lp.Module != nil && lp.Module.Main {
		return l.check(lp)
	}
	return l.gc.Import(path)
}

func (l *loader) check(lp *listPkg) (*types.Package, error) {
	if p, ok := l.checked[lp.ImportPath]; ok {
		return p, nil
	}
	if lp.Error != nil {
		return nil, fmt.Errorf("%s: %s", lp.ImportPath, lp.Error.Err)
	}
	var files []*ast.File
	for _, name := range append(append([]string{}, lp.GoFiles...), lp.CgoFiles...) {
		abs := filepath.Join(lp.Dir, name)
		f, err := parser.ParseFile(l.fset, abs, nil, 0)
		if err != nil {
			return nil, err
		}
		l.files[abs] = true
		files = append(files, f)
	}
	saved := l.cur
	l.cur = lp
	defer func() { l.cur = saved }()
	conf := types.Config{
		Importer:    l,
		FakeImportC: true,
		Sizes:       types.SizesFor("gc", build.Default.GOARCH),
		Error:       func(err error) { l.errs = append(l.errs, err.Error()) },
	}
	pkg, _ := conf.Check(lp.ImportPath, l.fset, files, nil)
	l.checked[lp.ImportPath] = pkg
	return pkg, nil
}

type candidate struct {
	key     string
	typ     types.Type
	methods map[string]bool
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(3)
}

func main() {
	if len(os.Args) != 2 {
		fail("usage: implementors <root> < go-list.json")
	}
	root, err := filepath.Abs(os.Args[1])
	if err != nil {
		fail("root: %v", err)
	}
	dec := json.NewDecoder(os.Stdin)
	var order []*listPkg
	pkgs := map[string]*listPkg{}
	for {
		var p listPkg
		if err := dec.Decode(&p); err == io.EOF {
			break
		} else if err != nil {
			fail("go list stream: %v", err)
		}
		lp := p
		pkgs[lp.ImportPath] = &lp
		order = append(order, &lp)
	}
	if len(order) == 0 {
		fail("go list stream was empty")
	}
	l := &loader{fset: token.NewFileSet(), pkgs: pkgs, checked: map[string]*types.Package{},
		files: map[string]bool{}}
	l.gc = importer.ForCompiler(l.fset, "gc", func(path string) (io.ReadCloser, error) {
		lp, ok := pkgs[path]
		if !ok || lp.Export == "" {
			return nil, fmt.Errorf("no export data listed for %q", path)
		}
		return os.Open(lp.Export)
	})
	// `go list -deps` is a post-order walk, so a package's dependencies are checked before it.
	for _, lp := range order {
		// `pkg.test` is the synthesized test binary: one generated file at an absolute cache
		// path, declaring nothing anyone wrote.
		if lp.Module == nil || !lp.Module.Main || strings.HasSuffix(lp.ImportPath, ".test") ||
			len(lp.GoFiles)+len(lp.CgoFiles) == 0 {
			continue
		}
		if _, err := l.check(lp); err != nil {
			fail("%v", err)
		}
	}
	if len(l.errs) > 0 {
		fail("%d type errors; first: %s", len(l.errs), l.errs[0])
	}

	rel := func(pos token.Pos) (string, bool) {
		p := l.fset.Position(pos)
		r, err := filepath.Rel(root, p.Filename)
		if err != nil || strings.HasPrefix(r, "..") {
			return "", false
		}
		return filepath.ToSlash(r), true
	}

	// A type declared in a non-test file is checked once per build variant (`pkg` and
	// `pkg [pkg.test]`) and is a distinct object in each, so interfaces and candidates are keyed
	// by declaration site with every variant's object kept: an interface from one variant is
	// compared against candidates from all of them.
	ifaces := map[string][]*types.Interface{}
	ifaceMethods := map[string]map[string]bool{}
	var cands []candidate
	external := map[*types.Package]bool{}
	addCandidate := func(key string, tn *types.TypeName) {
		named, ok := tn.Type().(*types.Named)
		if !ok || tn.IsAlias() || types.IsInterface(named) || named.TypeParams().Len() > 0 {
			return
		}
		ms := types.NewMethodSet(types.NewPointer(named))
		if ms.Len() == 0 {
			return
		}
		names := map[string]bool{}
		for i := 0; i < ms.Len(); i++ {
			names[ms.At(i).Obj().Name()] = true
		}
		cands = append(cands, candidate{key: key, typ: named, methods: names})
	}
	for _, pkg := range l.checked {
		if pkg == nil {
			continue
		}
		for _, imp := range pkg.Imports() {
			if _, main := l.checked[imp.Path()]; !main {
				external[imp] = true
			}
		}
		scope := pkg.Scope()
		for _, name := range scope.Names() {
			tn, ok := scope.Lookup(name).(*types.TypeName)
			if !ok || tn.IsAlias() {
				continue
			}
			file, ok := rel(tn.Pos())
			if !ok {
				continue
			}
			named, ok := tn.Type().(*types.Named)
			if !ok {
				continue
			}
			if iface, ok := named.Underlying().(*types.Interface); ok {
				if strings.HasSuffix(file, "_test.go") || iface.NumMethods() == 0 || named.TypeParams().Len() > 0 {
					continue
				}
				key := file + "\x00" + name
				ifaces[key] = append(ifaces[key], iface)
				if ifaceMethods[key] == nil {
					ifaceMethods[key] = map[string]bool{}
					for i := 0; i < iface.NumMethods(); i++ {
						ifaceMethods[key][iface.Method(i).Name()] = true
					}
				}
				continue
			}
			addCandidate(fmt.Sprintf("%s:%d", file, l.fset.Position(tn.Pos()).Line), tn)
		}
	}
	for imp := range external {
		scope := imp.Scope()
		for _, name := range scope.Names() {
			tn, ok := scope.Lookup(name).(*types.TypeName)
			if !ok || !tn.Exported() {
				continue
			}
			addCandidate(imp.Path()+"."+name, tn)
		}
	}

	type row struct {
		File         string `json:"file"`
		Name         string `json:"name"`
		Implementors int    `json:"implementors"`
	}
	var rows []row
	for key, objs := range ifaces {
		need := ifaceMethods[key]
		impl := map[string]bool{}
		for _, c := range cands {
			if impl[c.key] {
				continue
			}
			subset := true
			for m := range need {
				if !c.methods[m] {
					subset = false
					break
				}
			}
			if !subset {
				continue
			}
			for _, iface := range objs {
				if types.Implements(types.NewPointer(c.typ), iface) {
					impl[c.key] = true
					break
				}
			}
		}
		parts := strings.SplitN(key, "\x00", 2)
		rows = append(rows, row{File: parts[0], Name: parts[1], Implementors: len(impl)})
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].File != rows[j].File {
			return rows[i].File < rows[j].File
		}
		return rows[i].Name < rows[j].Name
	})
	out, _ := json.Marshal(map[string]any{"files": len(l.files), "interfaces": rows})
	os.Stdout.Write(out)
	os.Stdout.Write([]byte("\n"))
}
'''


def go_abstractions(root: Path) -> Scan:
    """(file, interface) -> implementor count, for every interface with methods declared in a
    non-test file of the module. `go run` folds the program's exit status into its own 1, so any
    non-zero is did-not-run; the program itself exits 3 on a parse or type error rather than
    counting over a partial tree."""
    import tempfile

    listing = _go_list(root, ["-e", "-export", "-deps", "-test",
                              "-json=ImportPath,Dir,GoFiles,CgoFiles,Export,ImportMap,Module,Error"],
                       "check H")
    payload = "\n".join(json.dumps(p) for p in listing)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "sdlc_gate_implementors.go"
        src.write_text(_GO_IMPLEMENTORS_SRC.lstrip())
        try:
            proc = subprocess.run(["go", "run", str(src), str(root)], cwd=root, input=payload,
                                  capture_output=True, text=True, check=False, timeout=1800)
        except OSError as e:
            raise ScanOperationalError(f"check H: `go run` could not start: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise ScanOperationalError("check H: the implementor count timed out") from e
    if proc.returncode != 0:
        raise ScanOperationalError(
            f"check H: implementor count exited {proc.returncode}: {proc.stderr.strip()[:300]!r}")
    try:
        doc = json.loads(proc.stdout)
        rows = doc["interfaces"]
        files = int(doc["files"])
    except (ValueError, KeyError, TypeError) as e:
        raise ScanOperationalError(f"check H: implementor count wrote no readable result ({e})") from e
    findings = {(r["file"], r["name"]): int(r["implementors"]) for r in rows or []}
    return Scan("go/types implementors", files, findings)


# --- Toolchain plugins (one engine, per-toolchain scanners) --------------------


# --- Checks E-H: agent smells, and the contract they share --------------------------------
#
# Added 2026-09-10 for a chain in which every line is agent-written. Each targets a smell the
# 2023-2026 literature measured as over-represented in agent output, and they share one rule the
# earlier checks reached piecemeal: a scanner returns a `Scan` carrying its own DENOMINATOR, and a
# scanner that could not run RAISES. "Ran and found nothing" and "did not run" are different facts
# and must never share a reading. Measured on the way here: `python -m compileall` exits 0 on a
# missing file; jscpd word-splits silently when its lexer gives up; pylint's duplicate-code reports
# nothing under --jobs>1; and this file's own run_ruff read non-JSON as "no findings".


class ScanOperationalError(RuntimeError):
    """A scanner that could not run. Fail-closed like CoverageOperationalError: the gate exits 2
    rather than reading the absence of findings as a clean result."""


class NotWired(Exception):
    """This check has no implementation for this toolchain. REPORTED, never skipped: `diff` lists
    every not-wired check under `not_wired`, the coverage receipt a consumer reads to learn what
    the gate did not look at for its language. A silent skip would make a toolchain implementing
    one check byte-identical in output to one implementing all four."""


class Scan:
    """One scanner's result WITH its denominator.

    `files` is how many files the tool actually examined. The engine refuses a branch scan that
    examined zero files, so an empty `findings` from a tool that looked at nothing is a
    did-not-run and not a clean. `findings` is keyed per check — see each Toolchain method.

    A plain class, not a dataclass: the test suite loads this file by path without registering
    it in sys.modules, and dataclass field resolution under `from __future__ import annotations`
    looks the module up by name. Stdlib-minimal is the point of this file anyway.
    """
    __slots__ = ("tool", "files", "findings")

    def __init__(self, tool: str, files: int, findings: dict) -> None:
        self.tool = tool
        self.files = files
        self.findings = findings

    def __repr__(self) -> str:
        return f"Scan(tool={self.tool!r}, files={self.files}, findings={len(self.findings)})"


def _diff_added_lines(baseline_sha: str) -> dict[str, set[int]]:
    """Lines the diff ADDED, per repo-relative file, from `git diff -U0`. Check F uses it to
    attribute a whole-tree clone to this change: only a fingerprint with at least one occurrence
    on an added line is the branch's doing."""
    proc = subprocess.run(["git", "diff", "-U0", baseline_sha, "--", "."],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ScanOperationalError(f"git diff against {baseline_sha} failed: {proc.stderr.strip()[:200]}")
    out: dict[str, set[int]] = {}
    cur: str | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("+++ "):
            cur = None if line == "+++ /dev/null" else line[4:].removeprefix("b/")
        elif line.startswith("@@") and cur is not None:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start, n = int(m.group(1)), int(m.group(2) or "1")
                out.setdefault(cur, set()).update(range(start, start + max(n, 1)))
    return out


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

    # --- Checks E-H. Each raises NotWired unless the subclass implements it. ---------------

    def unreferenced(self, root: Path) -> Scan:
        """Check E — declared-but-unreferenced code: unused parameters, locals, imports, private
        members, exports with no importer, config keys with no read site. Keyed (file, code) ->
        count, diffed exactly like Check A: a per-file count increase blocks.

        REACHABILITY, deliberately. "An abstraction with few subclasses" has no outcome evidence
        and one study finds it reducing faults; unreferenced code is the largest smell class for
        every model measured (14.7-42.7% of smells in Sonar's 2025 benchmark) and 9.9% of
        agent-written methods are deleted by reviewers before merge."""
        raise NotWired(f"unreferenced: not wired for {self.name}")

    def duplication(self, root: Path) -> Scan:
        """Check F — token-level clones over the WHOLE tree, not the diff. Keyed fingerprint ->
        list of [file, start_line, end_line]. A fingerprint absent from the baseline with at least
        one occurrence on an added line blocks.

        Whole-tree because the agent-specific form is re-implementing an existing helper inline
        (semantic redundancy at 1.87x human rates): the baseline holds one copy, the branch two,
        and only a scan that sees both can notice. A size control, not a defect proxy — clones at
        creation are not buggier; later inconsistent edits are."""
        raise NotWired(f"duplication: not wired for {self.name}")

    def complexity(self, root: Path) -> Scan:
        """Check G — COGNITIVE complexity per function, keyed (file, function) -> int. A function
        over COMPLEXITY_THRESHOLD that is new, or that rose above its baseline value, blocks.

        Cognitive not cyclomatic, and delta-checked: the rule is "do not push an already-complex
        function higher", never "split this". It targets the measured agent failure — iterative
        patching into one function, +41.6% under Cursor, a main() growing 38 -> 240 lines over
        eight checkpoints — without rewarding decomposition for its own sake, which is what
        craft-complexity.md's Ousterhout argument forbids a bare length threshold for."""
        raise NotWired(f"complexity: not wired for {self.name}")

    def abstractions(self, root: Path) -> Scan:
        """Check H — abstractions (interfaces, traits, abstract or base classes, protocols) keyed
        (file, name) -> implementor count. An abstraction NEW on the branch with at most one
        implementor blocks.

        The inheritance-dedup refusal: gate-driven deduplication via Extract Superclass produced
        Speculative Generality 68% of the time (Cedrim et al.), so a Check F block must not be
        dischargeable by inventing a base class."""
        raise NotWired(f"abstractions: not wired for {self.name}")


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

    # Checks E-H: the runners live with the other Python run_* functions above.

    def unreferenced(self, root: Path) -> Scan:
        return run_ruff_unreferenced(root)

    def duplication(self, root: Path) -> Scan:
        return run_cpd(root)

    def complexity(self, root: Path) -> Scan:
        return run_complexipy(root)

    def abstractions(self, root: Path) -> Scan:
        return scan_python_abstractions(root)


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

    # Checks E-H (Scala 3): the compiler for E, PMD CPD for F, one scalameta program for G and H.
    def unreferenced(self, root: Path) -> Scan:
        return run_sbt_unused(root)

    def duplication(self, root: Path) -> Scan:
        return run_cpd_scala(root)

    def complexity(self, root: Path) -> Scan:
        return run_scala_complexity(root)

    def abstractions(self, root: Path) -> Scan:
        return run_scala_abstractions(root)


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


class TypeScriptToolchain(Toolchain):
    name = "typescript"
    static_labels = ["eslint", "tsc"]

    def detect(self, root: Path) -> bool:
        return (root / "package.json").exists() or (root / "tsconfig.json").exists()

    def static_analysis(self, root: Path) -> dict[str, Counter]:
        return {"eslint": run_eslint(root), "tsc": run_tsc(root)}

    def suppressions(self, root: Path) -> Counter:
        return scan_ts_suppressions(root)

    def test_weakening(self, root: Path) -> dict:
        return scan_ts_test_weakening(root)

    def compile_check(self, root: Path) -> str:
        return ts_compile_status(root)

    def coverage(self, root: Path) -> dict[str, float]:
        return run_istanbul_coverage(root)

    def is_test_file(self, rel: str) -> bool:
        return _ts_is_test_file(rel)

    def unreferenced(self, root: Path) -> Scan:
        return run_ts_unreferenced(root)

    def duplication(self, root: Path) -> Scan:
        return run_ts_duplication(root)

    def complexity(self, root: Path) -> Scan:
        return run_ts_complexity(root)

    def abstractions(self, root: Path) -> Scan:
        return run_ts_abstractions(root)


class GoToolchain(Toolchain):
    name = "go"
    static_labels = ["golangci-lint"]

    def detect(self, root: Path) -> bool:
        return (root / "go.mod").exists()

    def static_analysis(self, root: Path) -> dict[str, Counter]:
        return {"golangci-lint": run_golangci(root)}

    def suppressions(self, root: Path) -> Counter:
        return scan_go_suppressions(root)

    def test_weakening(self, root: Path) -> dict:
        return scan_go_test_weakening(root)

    def compile_check(self, root: Path) -> str:
        return go_compile_status(root)

    def coverage(self, root: Path) -> dict[str, float]:
        return run_go_coverage(root)

    def is_test_file(self, rel: str) -> bool:
        return _go_is_test_file(rel)

    def unreferenced(self, root: Path) -> Scan:
        return go_unreferenced(root)

    def duplication(self, root: Path) -> Scan:
        return go_duplication(root)

    def complexity(self, root: Path) -> Scan:
        return go_complexity(root)

    def abstractions(self, root: Path) -> Scan:
        return go_abstractions(root)


_TOOLCHAINS = {"python": PythonToolchain(), "scala": ScalaToolchain(),
               "java": JavaToolchain(), "go": GoToolchain(),
               "typescript": TypeScriptToolchain()}


def select_toolchain(root: Path, override: str | None) -> Toolchain:
    if override:
        if override not in _TOOLCHAINS:
            sys.stderr.write(f"sdlc-gate: unknown --toolchain {override!r}\n")
            sys.exit(2)
        return _TOOLCHAINS[override]
    for tc in (ScalaToolchain(), JavaToolchain(), PythonToolchain(), GoToolchain(),
               TypeScriptToolchain()):
        if tc.detect(root):
            return tc
    sys.stderr.write("sdlc-gate: no toolchain detected (no build.sbt, pom.xml/build.gradle, "
                     "pyproject.toml, go.mod, or package.json/tsconfig.json); pass "
                     "--toolchain scala|java|python|go|typescript\n")
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


def _serialize_scan(findings: dict) -> list[list]:
    """E-H keys are tuples (E, G, H) or strings (F); emit [key-as-list, value]."""
    return [[list(k) if isinstance(k, tuple) else k, v]
            for k, v in sorted(findings.items(), key=lambda kv: str(kv[0]))]


def _deserialize_scan(data: list) -> dict:
    return {(tuple(k) if isinstance(k, list) else k): v for k, v in data}


def _load_agent_scans(base_dir: Path) -> dict:
    f = base_dir / "agent-scans.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _diff_unreferenced(branch: dict, base: dict, rename_map: dict[str, str], deleted: set[str],
                       added: dict[str, set[int]]) -> list[dict]:
    """Check E, shaped like Check A: per-(file, code) count increase against the translated baseline."""
    translated = _translate(Counter(base), rename_map, deleted)
    items = [{"file": f, "code": c, "new": n - translated.get((f, c), 0)}
             for (f, c), n in branch.items() if n > translated.get((f, c), 0)]
    items.sort(key=lambda d: (d["file"], d["code"]))
    return [{"check": "E", "kind": "new_unreferenced", "items": items}] if items else []


def _diff_duplication(branch: dict, base: dict, rename_map: dict[str, str], deleted: set[str],
                      added: dict[str, set[int]]) -> list[dict]:
    """Check F: a fingerprint new on the branch, with an occurrence on an added line, blocks."""
    items = []
    for fp, occs in branch.items():
        if fp in base:
            continue
        if any(any(start <= ln <= end for ln in added.get(f, ())) for f, start, end in occs):
            items.append({"fingerprint": fp, "occurrences": occs})
    return [{"check": "F", "kind": "new_clone", "items": items}] if items else []


def _diff_complexity(branch: dict, base: dict, rename_map: dict[str, str], deleted: set[str],
                     added: dict[str, set[int]]) -> list[dict]:
    """Check G: over threshold AND (new OR higher than its baseline value). Never fires on a
    function that merely IS complex; only on one this change made worse or introduced."""
    inverse = {v: k for k, v in rename_map.items()}
    items = []
    for (f, fn), cc in branch.items():
        if cc <= COMPLEXITY_THRESHOLD:
            continue
        prev = base.get((inverse.get(f, f), fn))
        if prev is None or cc > prev:
            items.append({"file": f, "function": fn, "branch": cc, "baseline": prev,
                          "threshold": COMPLEXITY_THRESHOLD})
    return [{"check": "G", "kind": "complexity_rose", "items": items}] if items else []


def _diff_abstractions(branch: dict, base: dict, rename_map: dict[str, str], deleted: set[str],
                       added: dict[str, set[int]]) -> list[dict]:
    """Check H: an abstraction new on the branch with <= 1 implementor blocks."""
    inverse = {v: k for k, v in rename_map.items()}
    items = [{"file": f, "name": n, "implementors": c}
             for (f, n), c in branch.items() if (inverse.get(f, f), n) not in base and c <= 1]
    return [{"check": "H", "kind": "single_implementor_abstraction", "items": items}] if items else []


_AGENT_CHECKS = (("E", "unreferenced", _diff_unreferenced),
                 ("F", "duplication", _diff_duplication),
                 ("G", "complexity", _diff_complexity),
                 ("H", "abstractions", _diff_abstractions))


def _capture_agent_scans(tc: "Toolchain", root: Path) -> dict[str, dict]:
    """Run E-H for a baseline. Not-wired is RECORDED; a scanner that cannot run stops the capture."""
    out: dict[str, dict] = {}
    for check, method_name, _ in _AGENT_CHECKS:
        try:
            s = getattr(tc, method_name)(root)
            out[check] = {"tool": s.tool, "files": s.files, "findings": _serialize_scan(s.findings)}
        except NotWired as e:
            out[check] = {"not_wired": str(e)}
        except ScanOperationalError as e:
            sys.stderr.write(f"sdlc-gate: {e}\n")
            sys.exit(2)
    return out


def _run_agent_checks(tc: "Toolchain", root: Path, base_dir: Path, baseline_sha: str,
                      rename_map: dict[str, str], deleted: set[str]
                      ) -> tuple[list[dict], list[str], dict[str, dict]]:
    """Run E-H against the baseline's agent-scans.json. Returns (blocks, not_wired, scans)."""
    base_all = _load_agent_scans(base_dir)
    blocks: list[dict] = []
    not_wired: list[str] = []
    scans: dict[str, dict] = {}
    added: dict[str, set[int]] | None = None
    for check, method_name, differ in _AGENT_CHECKS:
        base = base_all.get(check)
        if base is None:
            not_wired.append(f"{check}: no baseline scan (captured by an older gate?)")
            continue
        if "not_wired" in base:
            not_wired.append(f"{check}: {base['not_wired']}")
            continue
        try:
            branch = getattr(tc, method_name)(root)
        except NotWired as e:
            not_wired.append(f"{check}: {e}")
            continue
        except ScanOperationalError as e:
            sys.stderr.write(f"sdlc-gate: {e}\n")
            sys.exit(2)
        if branch.files == 0:
            sys.stderr.write(f"sdlc-gate: check {check} ({branch.tool}) examined 0 files on the "
                             "branch; an empty scan is not a clean one\n")
            sys.exit(2)
        scans[check] = {"tool": branch.tool, "files_branch": branch.files, "files_baseline": base["files"]}
        if added is None:
            added = _diff_added_lines(baseline_sha)
        blocks.extend(differ(branch.findings, _deserialize_scan(base["findings"]), rename_map, deleted, added))
    return blocks, not_wired, scans


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
    agent_scans = _capture_agent_scans(tc, root)
    (out_dir / "agent-scans.json").write_text(json.dumps(agent_scans, indent=2))
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

    agent_blocks, not_wired, agent_scans = _run_agent_checks(
        tc, root, base_dir, baseline["sha"], rename_map, deleted)
    blocks.extend(agent_blocks)

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
        # The coverage receipt: which of E-H did NOT run for this toolchain, and the file
        # denominators of those that did. A consumer reads this to know what the gate did not
        # look at; a report listing only findings reads identical whether it ran four checks or none.
        "not_wired": not_wired,
        "agent_scans": agent_scans,
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
    global COMPLEXITY_THRESHOLD, DUP_MIN_TOKENS
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

    for p in (p_baseline, p_diff):
        p.add_argument("--complexity-threshold", type=int, default=COMPLEXITY_THRESHOLD,
                       help="Check G: cognitive complexity a function may not be pushed past (default 15)")
        p.add_argument("--dup-min-tokens", type=int, default=DUP_MIN_TOKENS,
                       help="Check F: minimum clone length in tokens (default 75)")
    args = parser.parse_args()
    COMPLEXITY_THRESHOLD = args.complexity_threshold
    DUP_MIN_TOKENS = args.dup_min_tokens
    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Red-first fixture for `scripts/profile-check.sh`.

The profile-integrity court is ADR-0002/D3.2: a chain profile whose `trusted_base` omits its
own file, the CI workflows, or any path the commit-path check invokes or reads is a cage with
a hole in it, and the hole is invisible from the profile itself. The check derives the
required set MECHANICALLY from `scripts/check.sh` rather than from a hand-kept list, because
a hand-kept list is exactly the artifact that drifts when a check is added.

Each case builds a throwaway kit-shaped tree, runs the court against it with the root
argument, and asserts BOTH the exit code and a marker string. The exit code alone cannot tell
a court that found full coverage from one that extracted no invocations and had nothing to
require, and that second reading is the failure this court is most exposed to.

  valid               every required path covered                  -> 0, profile-check: clean
  no-profile          no .claude/chain/profile.toml at all         -> 0, nothing to guard
  unparseable         a profile that is not valid TOML             -> 2, profile-check: VOID
  profile-is-dir      a directory at the profile path              -> 2, profile-check: VOID
  no-check-script     no scripts/check.sh to derive the set from   -> 2, profile-check: VOID
  no-invocations      a check.sh that invokes nothing              -> 2, profile-check: VOID
  missed-conditional  `if ! bash tools/hidden.sh; then`            -> 2, profile-check: VOID
  missed-direct-exec  `./tools/direct.sh`, no interpreter word     -> 2, profile-check: VOID
  missed-module-form  `python3 -m tools.mod`, an option not a path -> 2, profile-check: VOID
  invoked-path-absent an invocation naming a file that is absent   -> 2, profile-check: VOID
  entry-not-relative  a trusted_base entry that is absolute        -> 2, profile-check: VOID
  entry-universal     a trusted_base entry of "." covering all     -> 2, profile-check: VOID
  trusted-base-string trusted_base declared as a string, not list  -> 2, profile-check: VOID
  no-trusted-base     a profile declaring no trusted_base at all   -> 1, profile-check: FAIL
  missing-own-file    trusted_base omits .claude/                  -> 1, .claude/
  own-dir-too-narrow  trusted_base stops at .claude/chain/         -> 1, .claude/
  missing-workflows   trusted_base omits .github/workflows/        -> 1, .github/workflows/
  missing-githooks    trusted_base omits .githooks/                -> 1, .githooks/
  missing-invoked     an invoked path no entry covers              -> 1, tools/extra.sh
  missing-story-input trusted_base omits stories/                  -> 1, stories/

THE EMPTY-EXTRACTION SEMANTICS ARE PINNED BY `no-invocations`, and they are VOID rather than
clean on purpose. Zero extracted invocations means the derivation read nothing, so every
required path it would have produced is absent from the requirement set and any trusted_base
whatsoever satisfies it. That is the shape of a court reporting green because it stopped
looking, which is the one reading this file exists to make impossible. `invoked-path-absent`
is the same argument one step earlier: a token the extractor produced that names no file is a
mis-parse, and a mis-parse must not be answered with a coverage verdict.

THE PARTIAL-EXTRACTION SEMANTICS ARE THE SAME ARGUMENT AT ONE INVOCATION RATHER THAN ALL OF
THEM, and the three `missed-*` cases exist because that reading is the harder one to see. The
extraction is line-start anchored, which is exact for the form check.sh uses and blind to every
other; measured on a four-line sample, one form of four was extracted and the other three read
clean, with the zero-case VOID staying quiet because the count was not zero. So the anchor is
paired with a sweep: any non-comment line that looks like an invocation and that the anchor did
not resolve is could-not-run. Each case here plants one such form with its target OUTSIDE every
declared prefix, so a court without the sweep reports clean on a tree whose real requirement set
is short by one. `missed-module-form` is the subtlest: the anchor matches that line and captures
`-m`, which the option skip then eats, so the case also pins that `-` is the only option token
the skip may legitimately consume (the heredoc form `python3 - <<'PY'`, which names no path).

`missing-own-file` and `missing-workflows` are D3.2's two named omissions, and `missing-invoked`
is its third clause. `own-dir-too-narrow` is the same clause read at the right width: a base
naming `.claude/chain/` satisfies the own-file requirement literally while leaving
`.claude/settings.json` outside the cage, and that file is the harness's project-settings source,
which ADR-0004/D3 pins per invocation because settings inject. `missing-githooks` extends the
logic to the hook: the literal text of D3.2 names what the check invokes or reads, and the hook
is upstream of that, but a story that can edit `.githooks/pre-commit` can stop the check running
at all, which is the widest version of the evasion the clause exists to block.

Run: python3 harness/fixtures/profile_check_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "scripts" / "profile-check.sh"

PASS_MARKER = "profile-check: clean"
NOTHING_MARKER = "nothing to guard"
VOID_MARKER = "profile-check: VOID"
FAIL_MARKER = "profile-check: FAIL"

# The kit's own shape, reduced to what the court reads: a commit-path check invoking two
# files, the story-graph inputs, the workflows, the hook, and the profile itself.
DEFAULT_BASE = (
    ".claude/",
    ".github/workflows/",
    ".githooks/",
    "scripts/",
    "harness/",
    "scrub-gate.sh",
    "docs/adrs/",
    "stories/",
)

DEFAULT_CHECK = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scrub-gate.sh
python3 harness/tool.py
"""


def toml_for(entries: tuple[str, ...] | None, *, raw: str | None = None) -> str:
    """The profile body. `raw` replaces the trusted_base line for the malformed cases."""
    head = 'terminal = "open-pr"\npush = "branches-only"\n'
    if raw is not None:
        return head + raw + "\n"
    if entries is None:
        return head
    items = ", ".join(f'"{e}"' for e in entries)
    return head + f"trusted_base = [{items}]\n"


def kit_tree(
    root: Path,
    *,
    entries: tuple[str, ...] | None = DEFAULT_BASE,
    raw_trusted: str | None = None,
    check_body: str = DEFAULT_CHECK,
    profile: bool = True,
    check_script: bool = True,
    extra_files: tuple[str, ...] = ("scrub-gate.sh", "harness/tool.py"),
) -> Path:
    """A minimal tree with the shape the court reads, and full coverage unless told otherwise.

    Every directory the court requires gets a real file: an empty directory would let a
    coverage answer be produced about a tree that holds nothing, which is the reading these
    cases exist to keep distinguishable.
    """
    kit = root / "kit"
    for rel in ("scripts", "harness", ".github/workflows", ".githooks", "docs/adrs", "stories"):
        (kit / rel).mkdir(parents=True)
    (kit / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (kit / ".githooks" / "pre-commit").write_text("#!/usr/bin/env bash\nbash scripts/check.sh\n")
    (kit / "docs" / "adrs" / "README.md").write_text("The registry.\n")
    (kit / "stories" / "README.md").write_text("The stories.\n")
    for rel in extra_files:
        p = kit / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# a file the check invokes\n")
    if check_script:
        (kit / "scripts" / "check.sh").write_text(check_body)
    if profile:
        chain = kit / ".claude" / "chain"
        chain.mkdir(parents=True)
        (chain / "profile.toml").write_text(toml_for(entries, raw=raw_trusted))
    return kit


def run(kit: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(TOOL), str(kit)], capture_output=True, text=True)


def case(name: str, want: int, marker: str, build) -> bool:
    with tempfile.TemporaryDirectory() as td:
        kit = build(Path(td))
        got = run(kit)
        said = got.stdout + got.stderr
        ok = got.returncode == want and marker in said
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want} naming '{marker}', got exit {got.returncode}")
        if not ok:
            print(f"       stdout: {got.stdout.strip()[:400]}")
            print(f"       stderr: {got.stderr.strip()[:400]}")
        return ok


def build_valid(root: Path) -> Path:
    return kit_tree(root)


def build_no_profile(root: Path) -> Path:
    return kit_tree(root, profile=False)


def build_unparseable(root: Path) -> Path:
    kit = kit_tree(root)
    (kit / ".claude" / "chain" / "profile.toml").write_text('terminal = "open-pr\ntrusted_base = [\n')
    return kit


def build_profile_is_dir(root: Path) -> Path:
    """A directory at the profile path. `tomllib.load` on a directory raises OSError, but the
    shell precondition catches it first so the court never depends on which one fires."""
    kit = kit_tree(root, profile=False)
    (kit / ".claude" / "chain" / "profile.toml").mkdir(parents=True)
    return kit


def build_no_check_script(root: Path) -> Path:
    """No commit-path check to derive the requirement set from. Nothing to require is not
    nothing to guard: the profile is present and claims a cage."""
    return kit_tree(root, check_script=False)


def build_no_invocations(root: Path) -> Path:
    """A check.sh that runs no `bash` or `python3` invocation at all. The extractor returns an
    empty set, which every trusted_base trivially satisfies, so the only honest answer is VOID."""
    return kit_tree(root, check_body='#!/usr/bin/env bash\nset -euo pipefail\necho "nothing here"\n')


def build_missed_conditional(root: Path) -> Path:
    """An invocation inside a conditional. The extraction is line-start anchored, so this one is
    invisible to it, and an invisible invocation is silently unrequired: `tools/` is outside every
    declared prefix here, and without the guard the tree reads clean."""
    return kit_tree(
        root,
        check_body=DEFAULT_CHECK + "if ! bash tools/hidden.sh; then exit 1; fi\n",
        extra_files=("scrub-gate.sh", "harness/tool.py", "tools/hidden.sh"),
    )


def build_missed_direct_exec(root: Path) -> Path:
    """A script run directly rather than through an interpreter. Same invisibility."""
    return kit_tree(
        root,
        check_body=DEFAULT_CHECK + "./tools/direct.sh\n",
        extra_files=("scrub-gate.sh", "harness/tool.py", "tools/direct.sh"),
    )


def build_missed_module_form(root: Path) -> Path:
    """`python3 -m pkg.mod`. The anchor MATCHES this line and captures `-m`, which the option
    skip then drops, so the module never enters the requirement set. The skip exists for the
    heredoc form `python3 - <<'PY'`, and `-` is the only option token it may legitimately eat."""
    return kit_tree(
        root,
        check_body=DEFAULT_CHECK + "python3 -m tools.mod\n",
        extra_files=("scrub-gate.sh", "harness/tool.py", "tools/mod.py"),
    )


def build_invoked_path_absent(root: Path) -> Path:
    """An extracted token naming a file that is not in the tree: a mis-parse or a stale check,
    either way not a coverage question."""
    return kit_tree(
        root,
        check_body=DEFAULT_CHECK + "python3 harness/gone.py\n",
    )


def build_entry_not_relative(root: Path) -> Path:
    return kit_tree(root, entries=DEFAULT_BASE + ("/etc/",))


def build_entry_universal(root: Path) -> Path:
    """An entry of "." covers every path by prefix, so the court would report full coverage of
    a profile that named nothing. It is not fail-open in the merge stage, where it would park
    every story, but it is a coverage verdict derived from a declaration that says nothing."""
    return kit_tree(root, entries=(".",))


def build_trusted_base_string(root: Path) -> Path:
    """A string where a list belongs. Coercing it would be a guess: `"scripts/"` read as a
    sequence is eight one-character entries, and a guess inside a fail-closed court is how
    fail-open enters. VOID is the honest code, since the declaration could not be read."""
    return kit_tree(root, raw_trusted='trusted_base = "scripts/"')


def build_no_trusted_base(root: Path) -> Path:
    """A profile with a posture and no cage. This is a finding rather than could-not-run: the
    declaration is readable and it omits every required path."""
    return kit_tree(root, entries=None)


def build_missing_own_file(root: Path) -> Path:
    return kit_tree(root, entries=tuple(e for e in DEFAULT_BASE if e != ".claude/"))


def build_own_dir_too_narrow(root: Path) -> Path:
    """A trusted_base naming `.claude/chain/` where the settings root belongs. It satisfies
    D3.2's own-file clause literally and leaves `.claude/settings.json` outside the cage, which
    is the surface ADR-0004/D3 pins per invocation because settings inject."""
    return kit_tree(
        root,
        entries=tuple(".claude/chain/" if e == ".claude/" else e for e in DEFAULT_BASE),
    )


def build_missing_workflows(root: Path) -> Path:
    return kit_tree(root, entries=tuple(e for e in DEFAULT_BASE if e != ".github/workflows/"))


def build_missing_githooks(root: Path) -> Path:
    return kit_tree(root, entries=tuple(e for e in DEFAULT_BASE if e != ".githooks/"))


def build_missing_invoked(root: Path) -> Path:
    """A check.sh gaining an invocation outside every declared prefix: the drift D3.2 is about."""
    return kit_tree(
        root,
        check_body=DEFAULT_CHECK + "bash tools/extra.sh\n",
        extra_files=("scrub-gate.sh", "harness/tool.py", "tools/extra.sh"),
    )


def build_missing_story_input(root: Path) -> Path:
    """The story-graph inputs are read, never invoked, so no extraction finds them."""
    return kit_tree(root, entries=tuple(e for e in DEFAULT_BASE if e != "stories/"))


def main() -> int:
    if not TOOL.is_file():
        print(f"profile_check_test: court not found at {TOOL}", file=sys.stderr)
        return 2
    results = [
        case("valid", 0, PASS_MARKER, build_valid),
        case("no-profile", 0, NOTHING_MARKER, build_no_profile),
        case("unparseable", 2, VOID_MARKER, build_unparseable),
        case("profile-is-dir", 2, VOID_MARKER, build_profile_is_dir),
        case("no-check-script", 2, VOID_MARKER, build_no_check_script),
        case("no-invocations", 2, VOID_MARKER, build_no_invocations),
        case("missed-conditional", 2, VOID_MARKER, build_missed_conditional),
        case("missed-direct-exec", 2, VOID_MARKER, build_missed_direct_exec),
        case("missed-module-form", 2, VOID_MARKER, build_missed_module_form),
        case("invoked-path-absent", 2, VOID_MARKER, build_invoked_path_absent),
        case("entry-not-relative", 2, VOID_MARKER, build_entry_not_relative),
        case("entry-universal", 2, VOID_MARKER, build_entry_universal),
        case("trusted-base-string", 2, VOID_MARKER, build_trusted_base_string),
        case("no-trusted-base", 1, FAIL_MARKER, build_no_trusted_base),
        case("missing-own-file", 1, ".claude/", build_missing_own_file),
        case("own-dir-too-narrow", 1, ".claude/", build_own_dir_too_narrow),
        case("missing-workflows", 1, ".github/workflows/", build_missing_workflows),
        case("missing-githooks", 1, ".githooks/", build_missing_githooks),
        case("missing-invoked", 1, "tools/extra.sh", build_missing_invoked),
        case("missing-story-input", 1, "stories/", build_missing_story_input),
    ]
    failed = results.count(False)
    print(f"profile_check_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

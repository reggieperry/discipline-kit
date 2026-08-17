#!/usr/bin/env python3
"""Red-first fixture for `scrub-gate.sh`.

The scrub gate is what stops a private identifier reaching a tarball, and until this fixture
existed it had never been observed firing. It ran on every commit, printed `clean` three times,
and nobody could say whether that meant no token was present or no token was reachable. Its two
most interesting behaviors were both invisible for exactly that reason: the `.git`-file
exclusion, added after a linked worktree's absolute gitdir path tripped TIER-1 on VCS metadata,
and the tier scoping, which is the whole reason there are tiers.

Each case builds a throwaway kit-shaped tree, runs the gate against it with the target-dir
argument, and asserts BOTH the exit code and a marker string. The exit code alone cannot tell a
tier that found nothing from a tier that was never reached, and the second is the failure this
gate is most exposed to.

  clean               a kit-shaped tree with nothing forbidden      -> 0, SCRUB GATE: PASS
  tier1-home-path     a home path planted in ordinary content       -> 1, TIER-1 violations
  tier1-username-slug the username in a path SLUG, not a path        -> 1, TIER-1 violations
  tier1-username-bare the username bare, as `ls -l` prints it        -> 1, TIER-1 violations
  tier1-home-path-in-license  LICENSE is carved out of ONE pattern   -> 1, TIER-1 violations
  tier1-license-copyright     the copyright holder's own name        -> 0, SCRUB GATE: PASS
  worktree-git-file   a `.git` FILE whose gitdir line is a home path -> 0, SCRUB GATE: PASS
  tier2-in-memories   a tier-2 token under memories/                -> 1, TIER-2 violations
  tier2-in-rules      the SAME token under claude-project/rules/    -> 0, SCRUB GATE: PASS
  absent-surface      a target with no memories/ directory          -> 2, VOID (never a pass)
  absent-target       a target directory that does not exist        -> 2, VOID (never a pass)

`tier2-in-memories` and `tier2-in-rules` are one case in two halves and are worth nothing apart:
the same bytes in two places must produce two verdicts, which is what "tier" means. A gate that
scanned rules/ for tier-2 tokens would fail the second half; one that scanned neither would pass
the second half and fail the first.

The four `tier1-*` cases beyond the first come from the D7 probe record's own audit, which found
the slash-anchored pattern blind to the username's other forms while the gate reported clean on
files carrying it. The last two are the LICENSE carve-out in both directions: the copyright line
names the copyright holder and must pass, and every other TIER-1 token must still be caught in
that same file, or the carve-out would be a file the gate stopped reading.

THE FORBIDDEN TIER-1 TOKENS ARE ASSEMBLED AT RUNTIME from fragments, so this file contains
neither of them. A fixture that had to carry a token literally would be a TIER-1 violation
itself, and the gate scans its own repository — the fixture would either fail the gate or force
an exclusion, and an exclusion is how a scanned surface stops being scanned.

Run: python3 harness/fixtures/scrub_gate_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "scrub-gate.sh"

# Assembled, never written whole. TIER-1 forbids both of these anywhere in the kit, so a
# fixture carrying either literally would be a violation of the gate it tests.
OPERATOR = "reg" + "gie"
FORBIDDEN_HOME = "/home/" + OPERATOR

# A TIER-2 token: forbidden under memories/ and claude-user/, allowed under rules/ as teaching
# material. Safe to write literally here, because harness/ is not a tier-2 surface.
TIER2_TOKEN = "reconciler"

PASS_MARKER = "SCRUB GATE: PASS"
TIER1_MARKER = "TIER-1 violations"
TIER2_MARKER = "TIER-2 violations"
VOID_MARKER = "SCRUB GATE: VOID"


def kit_tree(root: Path, surfaces: tuple[str, ...] = ("memories", "claude-user", "claude-project/rules")) -> Path:
    """A minimal tree with the shape the gate expects, and nothing forbidden in it.

    Every scanned surface gets a real file. An empty directory would let a tier report `clean`
    having read no bytes, which is the reading this fixture exists to be able to distinguish.
    """
    kit = root / "kit"
    kit.mkdir()
    for surface in surfaces:
        d = kit / surface
        d.mkdir(parents=True)
        (d / "note.md").write_text("Ordinary content with nothing forbidden in it.\n")
    (kit / "README.md").write_text("A kit-shaped tree.\n")
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


def build_clean(root: Path) -> Path:
    return kit_tree(root)


def build_mypy_cache(root: Path) -> Path:
    """A type-checker cache carrying the home path: a build artifact check.sh itself creates
    mid-run (mypy in the reference tests), never packaged, and excluded like __pycache__.
    Unexcluded, the first check.sh run after any mypy invocation blocks every later commit."""
    kit = kit_tree(root)
    cache = kit / ".mypy_cache" / "3.12"
    cache.mkdir(parents=True)
    (cache / "cache.db").write_text("meta " + FORBIDDEN_HOME + "/somewhere\n")
    return kit


def build_tier1_home_path(root: Path) -> Path:
    kit = kit_tree(root)
    (kit / "docs").mkdir()
    (kit / "docs" / "setup.md").write_text(f"Run it from {FORBIDDEN_HOME}/coding/kit and re-tar.\n")
    return kit


def build_worktree_git_file(root: Path) -> Path:
    """A linked worktree's `.git` is a FILE holding an absolute gitdir path, not a directory.

    `--exclude-dir=.git` does not reach a file, so before the `--exclude=.git` fix TIER-1 fired
    on the home path inside VCS metadata that the exclusion already intended to skip. The chain
    runs its phases in worktrees with this gate on the commit path, so every subagent commit
    blocked on the gate's own blind spot. Nothing else in this tree is forbidden, so a failure
    here is the exclusion and nothing else.
    """
    kit = kit_tree(root)
    (kit / ".git").write_text(f"gitdir: {FORBIDDEN_HOME}/coding/kit/.git/worktrees/phase\n")
    return kit


def build_tier1_username_slug(root: Path) -> Path:
    """The username in a path SLUG, which no slash-anchored pattern reaches.

    Measured by the D7 probe's own audit: this form and the `ls -l` one below carried the
    operator's username through 28 lines of retained raw output that the gate read as clean.
    """
    kit = kit_tree(root)
    (kit / "docs").mkdir()
    (kit / "docs" / "run.md").write_text(f"Scratch dir: /tmp/agent/-home-{OPERATOR}-coding-lab/run\n")
    return kit


def build_tier1_username_bare(root: Path) -> Path:
    """The username bare, as `ls -l` prints it in the owner and group columns."""
    kit = kit_tree(root)
    (kit / "docs").mkdir()
    (kit / "docs" / "listing.md").write_text(
        f"    drwxr-xr-x 2 {OPERATOR} {OPERATOR} 4096 Aug 12 19:12 worktrees\n"
    )
    return kit


def build_tier1_home_path_in_license(root: Path) -> Path:
    """LICENSE is carved out of the USERNAME pattern and of nothing else.

    The path form must still be caught there, or the carve-out would be a file the gate stops
    reading rather than a token it stops matching.
    """
    kit = kit_tree(root)
    (kit / "LICENSE").write_text(f"Apache 2.0, vendored from {FORBIDDEN_HOME}/licenses/apache.txt\n")
    return kit


def build_tier1_license_copyright(root: Path) -> Path:
    """The copyright holder's name in LICENSE is the license's content, not a leak."""
    kit = kit_tree(root)
    (kit / "LICENSE").write_text(f"   Copyright 2026 {OPERATOR.capitalize()} Perry\n")
    return kit


def build_tier2_in_memories(root: Path) -> Path:
    kit = kit_tree(root)
    (kit / "memories" / "note.md").write_text(
        f"The {TIER2_TOKEN} picks the story up within a tick.\n"
    )
    return kit


def build_tier2_in_rules(root: Path) -> Path:
    kit = kit_tree(root)
    (kit / "claude-project" / "rules" / "note.md").write_text(
        f"Illustrative only: a {TIER2_TOKEN} is the kind of component this rule describes.\n"
    )
    return kit


def build_absent_surface(root: Path) -> Path:
    """A target with no memories/ directory. grep answers "no match" for a directory that is not
    there, so before the precondition the tier printed `clean` and the gate printed PASS having
    read nothing at all on that surface."""
    return kit_tree(root, surfaces=("claude-user", "claude-project/rules"))


def build_absent_target(root: Path) -> Path:
    """A target directory that does not exist. `cd` fails, and without the `||` arm the gate
    would carry on with an empty `KIT` and scan the filesystem root."""
    return root / "no-such-directory"


def main() -> int:
    if not TOOL.is_file():
        print(f"scrub_gate_test: gate not found at {TOOL}", file=sys.stderr)
        return 2
    results = [
        case("clean", 0, PASS_MARKER, build_clean),
        case("tier1-home-path", 1, TIER1_MARKER, build_tier1_home_path),
        case("mypy-cache-excluded", 0, PASS_MARKER, build_mypy_cache),
        case("tier1-username-slug", 1, TIER1_MARKER, build_tier1_username_slug),
        case("tier1-username-bare", 1, TIER1_MARKER, build_tier1_username_bare),
        case("tier1-home-path-in-license", 1, TIER1_MARKER, build_tier1_home_path_in_license),
        case("tier1-license-copyright", 0, PASS_MARKER, build_tier1_license_copyright),
        case("worktree-git-file", 0, PASS_MARKER, build_worktree_git_file),
        case("tier2-in-memories", 1, TIER2_MARKER, build_tier2_in_memories),
        case("tier2-in-rules", 0, PASS_MARKER, build_tier2_in_rules),
        case("absent-surface", 2, VOID_MARKER, build_absent_surface),
        case("absent-target", 2, VOID_MARKER, build_absent_target),
    ]
    failed = results.count(False)
    print(f"scrub_gate_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

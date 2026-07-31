#!/usr/bin/env python3
"""Red-first fixture for `harness/rule_grades.py`.

An instrument that has never been observed failing is not known to be watching. Each case
builds a throwaway rules directory and asserts the checker's exit code:

  graded      every rule carries a vocabulary token                     -> 0
  ungraded    one rule has no grade line at all                         -> 1
  bad-token   one rule has a grade line with an out-of-vocabulary token -> 1
  empty       the rules directory exists but holds no rules             -> 2 (never a pass)
  missing     the rules directory does not exist                        -> 2 (never a pass)

The last two matter most: a checker that passes when it found nothing to check reports the
same green as one that verified everything.

Run: python3 harness/fixtures/rule_grades_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "rule_grades.py"

GRADED = """\
---
paths:
  - "**/*.py"
---

# Some rule

**Enforcement grade:** review and convention — nothing scans this.

Body text.
"""

UNGRADED = """\
# Some rule

Body text with no grade line at all.
"""

BAD_TOKEN = """\
# Some rule

**Enforcement grade:** totally fine honestly — trust me.

Body text.
"""


def run(rules_dir: Path) -> int:
    return subprocess.run(
        [sys.executable, str(TOOL), str(rules_dir)],
        capture_output=True, text=True,
    ).returncode


def case(name: str, files: dict[str, str] | None, want: int) -> bool:
    with tempfile.TemporaryDirectory() as td:
        rules = Path(td) / "rules"
        if files is not None:
            rules.mkdir()
            for fname, content in files.items():
                (rules / fname).write_text(content, encoding="utf-8")
        got = run(rules)
        ok = got == want
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want}, got {got}")
        return ok


def installed_layout_case(nest: tuple[str, ...]) -> bool:
    """Regression: the tool must find the rules with NO argument, at ANY depth.

    Every fixed-directory case above bypasses discovery entirely — so they all stayed green
    while discovery was broken. This one runs the tool with no argument, from a synthesized
    repo, at a chosen depth below the root.

    TWO depths, and the pair is the point: `start` is the script's own directory, so a fixed
    `parents[N]` is exactly right for one depth and points OUTSIDE the repo for every other —
    where it finds no rules, the reading this tool exists to refuse to call a pass. A single
    depth therefore cannot discriminate: measured on this fixture, a `parents[1]` mutant is
    correct for a 2-deep layout and passes it, and is caught only because the 1-deep case runs
    beside it. Keep both, and keep them unequal.
    """
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        (repo.joinpath(*nest)).mkdir(parents=True)
        (repo / ".claude" / "rules").mkdir(parents=True)
        (repo / ".claude" / "rules" / "a.md").write_text(GRADED, encoding="utf-8")
        installed = repo.joinpath(*nest) / "rule_grades.py"
        installed.write_text(TOOL.read_text(encoding="utf-8"), encoding="utf-8")
        got = subprocess.run(
            [sys.executable, str(installed)], capture_output=True, text=True, cwd=repo
        ).returncode
        ok = got == 0
        depth = "/".join(nest)
        print(f"  {'ok  ' if ok else 'FAIL'} discovery at {depth}/ (no argument): want exit 0, got {got}")
        return ok


def main() -> int:
    results = [
        case("graded", {"a.md": GRADED, "b.md": GRADED}, 0),
        case("ungraded", {"a.md": GRADED, "b.md": UNGRADED}, 1),
        case("bad-token", {"a.md": GRADED, "b.md": BAD_TOKEN}, 1),
        case("empty", {}, 2),
        case("missing", None, 2),
        installed_layout_case(("harness",)),
        installed_layout_case(("tools", "vendored")),
    ]
    if all(results):
        print("rule_grades_test: all cases pass")
        return 0
    print("rule_grades_test: FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

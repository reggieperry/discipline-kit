#!/usr/bin/env python3
"""Red-first fixture for `harness/ledger/rule_grades.py`.

An instrument that has never been observed failing is not known to be watching. Each case
builds a throwaway rules directory and asserts the checker's exit code:

  graded      every rule carries a vocabulary token                     -> 0
  ungraded    one rule has no grade line at all                         -> 1
  bad-token   one rule has a grade line with an out-of-vocabulary token -> 1
  empty       the rules directory exists but holds no rules             -> 2 (never a pass)
  missing     the rules directory does not exist                        -> 2 (never a pass)

The last two matter most: a checker that passes when it found nothing to check reports the
same green as one that verified everything.

Run: python3 harness/ledger/fixtures/rule_grades_test.py   (exit 0 = pass).
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


def installed_layout_case() -> bool:
    """Regression: the tool must find the rules with NO argument, from an INSTALLED layout.

    Every case above passes an explicit directory, which bypasses discovery entirely — so they
    all stayed green while discovery was broken. In the kit this file sits at `harness/ledger/`;
    an installed repo gets it at `ledger/`, one level shallower. A fixed `parents[N]` root is
    right for exactly one of those and points outside the repo for the other.
    """
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        (repo / "ledger").mkdir(parents=True)
        (repo / ".claude" / "rules").mkdir(parents=True)
        (repo / ".claude" / "rules" / "a.md").write_text(GRADED, encoding="utf-8")
        installed = repo / "ledger" / "rule_grades.py"
        installed.write_text(TOOL.read_text(encoding="utf-8"), encoding="utf-8")
        got = subprocess.run(
            [sys.executable, str(installed)], capture_output=True, text=True, cwd=repo
        ).returncode
        ok = got == 0
        print(f"  {'ok  ' if ok else 'FAIL'} installed-layout (no argument): want exit 0, got {got}")
        return ok


def main() -> int:
    results = [
        case("graded", {"a.md": GRADED, "b.md": GRADED}, 0),
        case("ungraded", {"a.md": GRADED, "b.md": UNGRADED}, 1),
        case("bad-token", {"a.md": GRADED, "b.md": BAD_TOKEN}, 1),
        case("empty", {}, 2),
        case("missing", None, 2),
        installed_layout_case(),
    ]
    if all(results):
        print("rule_grades_test: all cases pass")
        return 0
    print("rule_grades_test: FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

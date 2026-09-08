#!/usr/bin/env python3
"""Red-first fixture for `harness/rule_coverage.py`.

An instrument that has never been observed failing is not known to be watching. Each case builds a
throwaway rules directory and asserts the checker's exit code:

  covered       a declared language's test files reach a craft testing rule  -> 0
  uncovered     an overlay ships, but no craft testing rule reaches it       -> 1
  no-frontmatter a rule carries no paths: block, so it can never fire        -> 1
  no-globs      a rule declares paths: with nothing under it                 -> 1
  empty         the directory exists but holds no rules                      -> 2 (never a pass)
  missing       the directory does not exist                                 -> 2 (never a pass)

THE FIXTURES ENCODE THE FAILING CONDITION, never a copy of the shipped rules. A fixture that
snapshots live data goes stale and then fires for a reason unrelated to what it tests; these cannot,
because a language with no craft testing rule is DEFINED by having none.

Each case also asserts the string the checker prints, not merely its exit code. A control that
demands only a non-zero exit is satisfied by every way the checker can break, including the ways
that mean it never ran.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HARNESS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKER = os.path.join(HARNESS, "rule_coverage.py")

OVERLAY = '---\npaths:\n  - "**/*_test.zz"\n---\n\n# The zz testing overlay\n'
CRAFT_TDD = '---\npaths:\n  - "**/*_test.zz"\n---\n\n# craft-tdd\n'
CRAFT_TDD_BLIND = '---\npaths:\n  - "**/*.other"\n---\n\n# craft-tdd\n'
NO_FRONTMATTER = "# A rule with no paths: block\n\nNothing says when to inject this.\n"
NO_GLOBS = "---\npaths:\n---\n\n# A rule declaring no glob\n"


def run(rules_dir: str) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, CHECKER, rules_dir], capture_output=True, text=True
    )
    return p.returncode, p.stdout + p.stderr


def case(name: str, files: dict[str, str], expect_rc: int, expect_text: str) -> bool:
    with tempfile.TemporaryDirectory() as d:
        for fn, body in files.items():
            open(os.path.join(d, fn), "w", encoding="utf-8").write(body)
        rc, out = run(d)
    ok = rc == expect_rc and expect_text in out
    mark = "ok  " if ok else "FAIL"
    print(f"  {mark} {name:<16} expected rc={expect_rc} + {expect_text!r}, got rc={rc}")
    if not ok:
        print("       " + out.strip().replace("\n", "\n       "))
    return ok


def main() -> int:
    results = [
        case(
            "covered",
            {"zz-testing.md": OVERLAY, "craft-tdd.md": CRAFT_TDD},
            0,
            "every declared language reaches a craft testing rule",
        ),
        case(
            "uncovered",
            {"zz-testing.md": OVERLAY, "craft-tdd.md": CRAFT_TDD_BLIND},
            1,
            "reach no craft-* testing rule",
        ),
        case(
            "no-frontmatter",
            {"zz-testing.md": OVERLAY, "craft-tdd.md": CRAFT_TDD, "broken.md": NO_FRONTMATTER},
            1,
            "no paths: frontmatter",
        ),
        case(
            "no-globs",
            {"zz-testing.md": OVERLAY, "craft-tdd.md": CRAFT_TDD, "bare.md": NO_GLOBS},
            1,
            "declares no glob",
        ),
        case("empty", {}, 2, "holds no rules"),
    ]

    rc, out = run(os.path.join(tempfile.gettempdir(), "rule-coverage-absent-dir"))
    ok = rc == 2 and "does not exist" in out
    print(f"  {'ok  ' if ok else 'FAIL'} {'missing':<16} expected rc=2 + 'does not exist', got rc={rc}")
    results.append(ok)

    passed = sum(1 for r in results if r)
    print(f"rule-coverage fixture: {passed} of {len(results)} case(s) as specified")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

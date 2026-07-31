#!/usr/bin/env python3
"""rule_grades — every coding rule must declare its enforcement grade.

A rule that reads stronger than its gate is a quiet lie: the reader trusts a mechanical
guarantee that does not exist. So every file in the rules directory carries, immediately
after its H1, a line of the form:

    **Enforcement grade:** <token> — <what is policed, and what is not>

where <token> is drawn from a closed vocabulary:

    mechanically enforced   a check fails when this rule is broken
    partly mechanical       some conjuncts are checked; the grade names which, and which are not
    review and convention   nothing runs; this rule is carried by review

WHAT THIS CHECKS, AND WHAT IT DOES NOT. It enforces that a grade is DECLARED and drawn from
the vocabulary. It does NOT — and cannot — check that a grade is ACCURATE: no script can read
a rule and decide whether the gate really polices its topics. Grade accuracy is itself
review-and-convention, and saying so here is the point.

WHAT A GRADE DOES NOT SAY. It describes ENFORCEMENT — whether a check fails when
the rule is broken. It says nothing about whether the rule is CORRECT. A rule can be accurately
graded and still be wrong: one testing rule carried a correct "partly mechanical" grade while
naming law bundles that do not exist in the resolved artifact. Do not read a grade as a general
trust signal for a rule's content.

A related trap, which grades should name explicitly where it applies: a check that is OPT-IN
reports nothing when you opt out, so its silence is not evidence. The companion discipline is that a
scanner-wiring commit deletes that rule's stale grade in the same diff, so the label and the
gate move together or not at all.

Usage:
    python3 harness/rule_grades.py [RULES_DIR]

With no argument it takes the first of `.claude/rules` or `claude-project/rules` that exists,
relative to the repo root, so it works both in the kit and in an installed repo.

Exit 0 when every rule is graded, 1 on any ungraded or out-of-vocabulary rule, 2 when the
rules directory is missing or empty (an instrument that finds nothing to look at must say so
rather than pass).
"""
from __future__ import annotations

import sys
from pathlib import Path

MARKER = "**Enforcement grade:**"
TOKENS = ("mechanically enforced", "partly mechanical", "review and convention")
CANDIDATES = (".claude/rules", "claude-project/rules")


def resolve_dir(start: Path, argv: list[str]) -> Path | None:
    """Locate the rules directory.

    An explicit argument wins. Otherwise walk UP from this script looking for the first
    ancestor that holds a candidate directory. The walk matters because the script's depth
    below the repo root is not fixed: it sits at `harness/` in the kit and a consuming repo
    may vendor it anywhere. A fixed `parents[N]` is correct for exactly one depth and
    silently points OUTSIDE the repo for every other — where it finds no rules at all, which
    is the reading this tool is built to refuse to call a pass.
    """
    if argv:
        d = Path(argv[0])
        return d if d.is_dir() else None
    for ancestor in [start, *start.parents]:
        for rel in CANDIDATES:
            d = ancestor / rel
            if d.is_dir():
                return d
    return None


def grade_of(text: str) -> str | None:
    """The grade body of the first grade line, or None when the file declares none."""
    for line in text.splitlines():
        if line.startswith(MARKER):
            return line[len(MARKER):].strip()
    return None


def check(rules_dir: Path) -> tuple[int, int, list[str]]:
    """Returns (checked, failed, messages)."""
    problems: list[str] = []
    files = sorted(rules_dir.glob("*.md"))
    for p in files:
        body = grade_of(p.read_text(encoding="utf-8"))
        if body is None:
            problems.append(f"{p.name}: declares no enforcement grade")
        elif not body.startswith(TOKENS):
            problems.append(f"{p.name}: grade opens with an unknown token: {body[:60]!r}")
    return len(files), len(problems), problems


def main(argv: list[str]) -> int:
    rules_dir = resolve_dir(Path(__file__).resolve().parent, argv)
    if rules_dir is None:
        print("rule-grades: no rules directory found; refusing to pass vacuously", file=sys.stderr)
        return 2

    checked, failed, problems = check(rules_dir)
    if checked == 0:
        print(f"rule-grades: {rules_dir} holds no rules; refusing to pass vacuously", file=sys.stderr)
        return 2
    for m in problems:
        print(f"rule-grades: {m}", file=sys.stderr)
    if failed:
        print(f"rule-grades: {failed} of {checked} rule(s) ungraded or mis-graded", file=sys.stderr)
        return 1
    print(f"rule-grades: {checked} rules graded, vocabulary clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

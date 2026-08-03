#!/usr/bin/env python3
"""Emit the repo's discipline rules as JSON: name, path globs, and enforcement grade.

A workflow script cannot read the filesystem, so a review workflow cannot discover the rules
it should apply. This is the gathering half: the main loop runs it, hands the result to the
workflow as `args`, and the workflow does the glob matching in pure computation.

THE ENFORCEMENT GRADE IS THE POINT, not the rule list. Each rule declares whether it is
`mechanically enforced`, `partly mechanical`, or `review and convention`, and that decides
where a reviewer's attention is worth spending:

  review and convention   no check exists. A reader is the ONLY instrument, so this is where
                          review earns its keep.
  partly mechanical       the build catches part of it. Review the remainder, and do not
                          re-derive what the compiler already refuses.
  mechanically enforced   the build catches it. A reviewer re-checking it spends attention
                          that has an owner already.

  exit 0   the manifest is on stdout
  exit 2   no rules directory, or a rule with no grade — never an empty manifest passed off
           as a repo with no rules
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MARKER = "**Enforcement grade:**"
TOKENS = ("mechanically enforced", "partly mechanical", "review and convention")
# Both layouts, matching rule_grades.py: an installed repo keeps rules at .claude/rules, the kit
# itself at claude-project/rules. First one that exists wins.
CANDIDATES = (Path(".claude/rules"), Path("claude-project/rules"))


def globs_of(text: str) -> list[str]:
    """The `paths:` block from the rule's frontmatter, if it declares one."""
    out: list[str] = []
    in_block = False
    for line in text.splitlines():
        if line.startswith("paths:"):
            in_block = True
            continue
        if in_block:
            m = re.match(r'\s*-\s*"?([^"]+)"?\s*$', line)
            if m:
                out.append(m.group(1))
            else:
                break
    return out


def grade_of(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith(MARKER):
            rest = line[len(MARKER):].strip().lower()
            for t in TOKENS:
                if rest.startswith(t):
                    return t
    return None


def main() -> int:
    rules_dir = next((c for c in CANDIDATES if c.is_dir()), None)
    if rules_dir is None:
        print(
            f"rules-manifest: none of {', '.join(str(c) for c in CANDIDATES)} exists. "
            f"Nothing gathered.",
            file=sys.stderr,
        )
        return 2

    rules = []
    ungraded = []
    for f in sorted(rules_dir.glob("*.md")):
        text = f.read_text(errors="replace")
        grade = grade_of(text)
        if grade is None:
            ungraded.append(f.name)
            continue
        rules.append({"name": f.stem, "file": str(f), "paths": globs_of(text), "grade": grade})

    if ungraded:
        print(
            f"rules-manifest: {len(ungraded)} rule(s) carry no enforcement grade: "
            f"{', '.join(ungraded)}. A rule whose grade is unknown cannot be targeted, so this "
            f"refuses rather than silently dropping them.",
            file=sys.stderr,
        )
        return 2
    if not rules:
        print(f"rules-manifest: {rules_dir} holds no rules. Nothing gathered.", file=sys.stderr)
        return 2

    json.dump(rules, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

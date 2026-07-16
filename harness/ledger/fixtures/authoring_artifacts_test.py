#!/usr/bin/env python3
"""Structural guard for the authoring layer (discharges clm-0078; §15.51-52).

clm-0078 asserted that the authoring-layer artifacts landed with a specific shape. This fixture is the
named check that discharges the STRUCTURAL half of that claim (the format-quality half rests on the
acceptance testimony, clm-0080): the ADR template has its six sections in fixed order with a
non-negotiable Falsification condition, the registry exists, the story template carries the portable
frontmatter, six body sections, and the anti-weakening contract verbatim, the four authoring skills
exist, and no chain-coupled field leaked into the kit schema. It is also a standing guard — a future
edit that reorders the ADR sections or drops the anti-weakening lines fails here.

Red against a tree without the artifacts (any pre-v1.4.0 base), which is the observed-red disclosure.

Run: python3 harness/ledger/fixtures/authoring_artifacts_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# The kit root, whether run from the kit (harness/ledger/fixtures) or an installed repo (ledger/fixtures).
ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    fails: list[str] = []

    def check(cond: bool, label: str) -> None:
        if not cond:
            fails.append(label)

    adr = (ROOT / "harness/templates/ADR-template.md")
    t = adr.read_text() if adr.exists() else ""
    check(bool(t), "ADR-template.md exists")
    order = ["## Context", "## Decisions", "## Consequences",
             "## Alternatives", "## Falsification condition", "## Cross-references"]
    idx = [t.find(s) for s in order]
    check(all(i >= 0 for i in idx) and idx == sorted(idx),
          "ADR template: six sections present, in fixed order")
    check("Falsification" in t and "non-negotiable" in t.lower(),
          "ADR template: Falsification condition marked non-negotiable")
    check((ROOT / "docs/adrs/README.md").exists(), "docs/adrs/README.md registry exists")

    story = (ROOT / "harness/templates/story-template.md")
    s = story.read_text() if story.exists() else ""
    check(bool(s), "story-template.md exists")
    for field in ("id:", "title:", "deps:", "labels:", "sensitive_files:", "status:"):
        check(field in s, f"story template frontmatter has `{field.rstrip(':')}`")
    check(len(re.findall(r'^# ', s, re.M)) >= 6, "story template has >= 6 body sections")
    check("assertion count is not reduced" in s, "story template: anti-weakening — assertion count not reduced")
    check("no new suppressions" in s.lower(), "story template: anti-weakening — no new suppressions")
    check("skipped tests" in s.lower(), "story template: anti-weakening — no new skipped tests")

    for sk in ("adr-write", "story-write", "story-tighten", "story-intake"):
        check((ROOT / f"harness/skills/{sk}/SKILL.md").exists(), f"skill {sk} exists")

    check("filed_as_bead" not in s and "filed_as_bead" not in t,
          "no chain-coupled `filed_as_bead` in the kit templates")

    if fails:
        for f in fails:
            sys.stderr.write(f"  FAIL  {f}\n")
        sys.stderr.write(f"authoring_artifacts_test: {len(fails)} FAILED\n")
        return 1
    print("authoring_artifacts_test: PASS (ADR + story templates, registry, four skills — structure intact)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

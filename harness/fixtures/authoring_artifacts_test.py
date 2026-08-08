#!/usr/bin/env python3
"""Standing structural guard for the authoring layer, restored after the ledger removal
deleted its predecessor while the CHANGELOG still advertised it.

Checks the real tree, not a fixture:

  1. the ADR template carries a Status line and the six sections in fixed order
  2. every docs/adrs/ADR-*.md carries the same shape
  3. the ADR registry and the ADR files agree in both directions
  4. the story template carries its frontmatter keys, six body sections in order,
     and the anti-weakening contract verbatim
  5. the four authoring skills exist
  6. the authoring surface (skills + templates, recursively -- the installed issue
     templates included) is free of retired-ledger apparatus vocabulary -- the claim
     registry is gone (2026-07-30); an instruction to park a claim or cite a clm- id
     is an instruction nothing can execute. ADR files themselves are deliberately NOT
     vocabulary-scanned: naming the retired apparatus as a rejected precedent is
     legitimate there (ADR-0001 does), while in a skill or template the same words are
     instructions

Exit 0 all green; 1 any finding; 2 a surface is missing entirely (never a pass --
a guard that finds nothing to check must not report the same green as one that
verified everything).

Run: python3 harness/fixtures/authoring_artifacts_test.py [--root DIR]   (exit 0 = pass).
--root points the guard at a different tree; the red-proof fixture
(authoring_artifacts_fixture_test.py) uses it to demonstrate all three exits.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_args = sys.argv[1:]
if _args and (len(_args) != 2 or _args[0] != "--root"):
    print("authoring-artifacts: VOID: usage: authoring_artifacts_test.py [--root DIR] -- never a pass")
    sys.exit(2)
KIT = Path(_args[1]).resolve() if _args else Path(__file__).resolve().parent.parent.parent

ADR_TEMPLATE = KIT / "harness" / "templates" / "ADR-template.md"
STORY_TEMPLATE = KIT / "harness" / "templates" / "story-template.md"
ADR_DIR = KIT / "docs" / "adrs"
ADR_README = ADR_DIR / "README.md"
SKILLS = ["adr-write", "story-write", "story-intake", "story-tighten"]

ADR_SECTIONS = [
    "## Context",
    "## Decisions",
    "## Consequences",
    "## Alternatives",
    "## Falsification condition",
    "## Cross-references",
]

STORY_SECTIONS = [
    "# Problem / Context",
    "# Proposed approach",
    "# Scope and non-goals",
    "# Acceptance criteria",
    "# Risks and rollback",
    "# Notes",
]

STORY_FRONTMATTER_KEYS = ["id:", "title:", "deps:", "labels:", "sensitive_files:", "status:"]

ANTI_WEAKENING = [
    "The assertion count is not reduced versus the merge-base.",
    "No new suppressions are introduced versus the merge-base.",
    "No new skipped tests versus the merge-base.",
]

# The retired apparatus, by pattern. Each is an instruction or identifier that only makes
# sense if the deleted claim registry exists. "discharge" and "park" alone are NOT listed:
# both survive legitimately when bound directly to a named check or to chain flow state.
APPARATUS = [
    (r"\bclm-", "a claim-registry id or the id form itself"),
    (r"parked claims?", "the parked-claim lifecycle"),
    (r"park(s|ed|ing)? (a|the) (claim|criteria)", "the claim-parking instruction"),
    (r"claim-first", "the preregistration doctrine by its apparatus name"),
    (r"pre-regist", "the preregistration record or verb"),
    (r"\bboard id\b", "the ledger-era name for the external tracker id"),
    (r"the gate discharges", "gate-driven claim discharge"),
    (r"\bunverified\b", "the claim lifecycle state"),
    (r"\.hook-signed", "the retired forgery root"),
    (r"\bledger\b", "the apparatus by name"),
]


def fail(findings: list[str]) -> None:
    for f in findings:
        print(f"authoring-artifacts: {f}")
    print(f"authoring-artifacts: FAIL ({len(findings)} finding(s))")
    sys.exit(1)


def void(msg: str) -> None:
    print(f"authoring-artifacts: VOID: {msg} -- never a pass")
    sys.exit(2)


def sections_in_order(text: str, sections: list[str], where: str, findings: list[str]) -> None:
    pos = -1
    for s in sections:
        # match the heading at a line start, exact level
        m = re.search(rf"(?m)^{re.escape(s)}\s*$", text)
        if not m:
            findings.append(f"{where}: missing section '{s}'")
            continue
        if m.start() < pos:
            findings.append(f"{where}: section '{s}' out of order")
        pos = m.start()


def main() -> None:
    findings: list[str] = []

    for surface in (ADR_TEMPLATE, STORY_TEMPLATE, ADR_README):
        if not surface.exists():
            void(f"{surface.relative_to(KIT)} does not exist")

    # 1. + 2. ADR template and every ADR file: Status line + six sections in order.
    adr_files = sorted(ADR_DIR.glob("ADR-*.md"))
    for f in [ADR_TEMPLATE, *adr_files]:
        text = f.read_text(encoding="utf-8")
        where = str(f.relative_to(KIT))
        if "**Status:**" not in text:
            findings.append(f"{where}: no Status line")
        sections_in_order(text, ADR_SECTIONS, where, findings)

    # 3. Registry <-> files, both directions.
    readme = ADR_README.read_text(encoding="utf-8")
    heading = re.search(r"(?m)^## The registry\s*$", readme)
    if not heading:
        void("docs/adrs/README.md has no '## The registry' heading")
    registry = readme[heading.end():]
    registered = set(re.findall(r"\[?(ADR-\d{4})\]?", registry))
    for link_id, target in re.findall(r"\[(ADR-\d{4})\]\(([^)]+)\)", registry):
        if not (ADR_DIR / target).exists():
            findings.append(f"docs/adrs/README.md: {link_id} links to '{target}', which does not exist")
    on_disk = set()
    for f in adr_files:
        m = re.match(r"ADR-\d{4}(?=[-.])", f.name)
        if not m:
            findings.append(f"docs/adrs/{f.name}: filename does not start with a four-digit ADR-NNNN id")
            continue
        on_disk.add(m.group(0))
    for adr in sorted(on_disk - registered):
        findings.append(f"docs/adrs/README.md: {adr} exists on disk but is not registered")
    for adr in sorted(registered - on_disk):
        findings.append(f"docs/adrs/README.md: {adr} is registered but has no file")

    # 4. Story template: frontmatter, sections in order, anti-weakening verbatim.
    story = STORY_TEMPLATE.read_text(encoding="utf-8")
    for key in STORY_FRONTMATTER_KEYS:
        if not re.search(rf"(?m)^{re.escape(key)}", story):
            findings.append(f"harness/templates/story-template.md: frontmatter key '{key}' missing")
    sections_in_order(story, STORY_SECTIONS, "harness/templates/story-template.md", findings)
    for line in ANTI_WEAKENING:
        if line not in story:
            findings.append(f"harness/templates/story-template.md: anti-weakening line missing: '{line}'")

    # 5. The four authoring skills exist.
    skill_files = []
    for name in SKILLS:
        p = KIT / "harness" / "skills" / name / "SKILL.md"
        if p.exists():
            skill_files.append(p)
        else:
            findings.append(f"harness/skills/{name}/SKILL.md: missing")
    if not skill_files:
        void("no authoring skills found")

    # 6. The authoring surface is free of retired-ledger apparatus.
    surface_files = skill_files + sorted((KIT / "harness" / "templates").rglob("*.md"))
    for f in surface_files:
        text = f.read_text(encoding="utf-8")
        where = str(f.relative_to(KIT))
        for pattern, what in APPARATUS:
            for m in re.finditer(pattern, text):
                line_no = text.count("\n", 0, m.start()) + 1
                findings.append(f"{where}:{line_no}: retired apparatus ({what}): '{m.group(0)}'")

    if findings:
        fail(findings)
    print(
        f"authoring-artifacts: clean ({len(adr_files)} ADR(s), {len(skill_files)} skills, "
        f"{len(surface_files)} surface files scanned)"
    )


if __name__ == "__main__":
    main()

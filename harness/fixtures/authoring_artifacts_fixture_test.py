#!/usr/bin/env python3
"""Red-proof fixture for `authoring_artifacts_test.py` -- the guard demonstrated failing.

A guard that has only ever been run against a conforming tree is not known to be watching
(the neighbouring fixtures make the same argument for their checkers). Each case builds a
throwaway kit-shaped tree and asserts the guard's exit code via --root:

  conforming    template, story template, registry, four skills, no apparatus  -> 0
  apparatus     one skill instructs parking a claim under a clm- id            -> 1
  disorder      an ADR file with its sections out of order                     -> 1
  dead-link     a registry row linking a file that does not exist              -> 1
  missing       the ADR template absent entirely                               -> 2 (never a pass)

Run: python3 harness/fixtures/authoring_artifacts_fixture_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "authoring_artifacts_test.py"

ADR_SHAPE = """# ADR-NNNN: title

**Status:** Proposed (2026-01-01).

## Context

x

## Decisions

x

## Consequences

x

## Alternatives

x

## Falsification condition

x

## Cross-references

x
"""

STORY_SHAPE = """---
id: <ID>
title: <t>
deps: []
labels: []
sensitive_files: []
status: draft
---

# Problem / Context

x

# Proposed approach

x

# Scope and non-goals

x

# Acceptance criteria

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

x

# Notes

x
"""

README_SHAPE = """# ADRs

## The registry

| ADR | Title | Status | Falsifier (court) | Supersession | Date |
|-----|-------|--------|-------------------|--------------|------|
"""

SKILLS = ["adr-write", "story-write", "story-intake", "story-tighten"]


def build_tree(root: Path) -> None:
    (root / "harness" / "templates").mkdir(parents=True)
    (root / "docs" / "adrs").mkdir(parents=True)
    (root / "harness" / "templates" / "ADR-template.md").write_text(ADR_SHAPE)
    (root / "harness" / "templates" / "story-template.md").write_text(STORY_SHAPE)
    (root / "docs" / "adrs" / "README.md").write_text(README_SHAPE)
    for name in SKILLS:
        d = root / "harness" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}: clean skill\n\nName the check that settles it.\n")


def run(root: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(GUARD), "--root", str(root)],
        capture_output=True,
        text=True,
    )
    return r.returncode, r.stdout + r.stderr


def case(name: str, want: int, mutate, expect: str) -> bool:
    """expect pins WHICH finding fired, so a case cannot go red for an unrelated reason --
    the confounding an adversarial pass caught in the first version of this fixture."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_tree(root)
        mutate(root)
        got, out = run(root)
        ok = got == want and expect in out
        why = "" if ok else f" (exit {got}, expected marker {'present' if expect in out else 'ABSENT'})"
        print(f"authoring-fixture: {name}: want exit {want} + '{expect}' -> {'ok' if ok else 'FAIL' + why}")
        return ok


def plant_apparatus(root: Path) -> None:
    (root / "harness" / "skills" / "story-intake" / "SKILL.md").write_text(
        "# story-intake\n\nPark a parked claim under clm-0001 on the board id.\n"
    )


def plant_disorder(root: Path) -> None:
    # the ADR is REGISTERED with a correct link, so the only finding left is the order
    (root / "docs" / "adrs" / "ADR-0001-x.md").write_text(
        ADR_SHAPE.replace("## Context\n\nx\n\n## Decisions", "## Decisions\n\nx\n\n## Context")
    )
    (root / "docs" / "adrs" / "README.md").write_text(
        README_SHAPE + "| [ADR-0001](ADR-0001-x.md) | x | Proposed | none | None | 2026-01-01 |\n"
    )


def plant_dead_link(root: Path) -> None:
    # the id IS on disk and registered, so registered/on-disk agree; only the link target is wrong
    (root / "docs" / "adrs" / "ADR-0009-real.md").write_text(ADR_SHAPE)
    (root / "docs" / "adrs" / "README.md").write_text(
        README_SHAPE + "| [ADR-0009](ADR-0009-gone.md) | x | Proposed | none | None | 2026-01-01 |\n"
    )


def main() -> None:
    results = [
        case("conforming", 0, lambda root: None, "clean"),
        case("apparatus", 1, plant_apparatus, "retired apparatus"),
        case("disorder", 1, plant_disorder, "out of order"),
        case("dead-link", 1, plant_dead_link, "which does not exist"),
        case(
            "missing",
            2,
            lambda root: (root / "harness" / "templates" / "ADR-template.md").unlink(),
            "VOID",
        ),
    ]
    if not all(results):
        print("authoring-fixture: FAIL")
        sys.exit(1)
    print("authoring-fixture: all cases pass")


if __name__ == "__main__":
    main()

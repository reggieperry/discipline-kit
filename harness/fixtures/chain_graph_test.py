#!/usr/bin/env python3
"""Red-proof fixture for `harness/chain_graph.py` — the six A5 checks demonstrated failing.

A check whose failing case has never been demonstrated is not a check (the walkthrough's A5
says exactly that, and names the kit's own archived postcondition as the specimen). So every
one of the six integrity checks is pinned here by at least one known-good case exiting 0 and
at least one known-bad case exiting non-zero, and each bad case asserts the MARKER STRING its
finding prints. The marker assertion is the part that stops a confounded pass: a tree built to
be cyclic that exits 1 because its frontmatter was malformed has told us nothing about cycle
detection, and only the marker discriminates the two.

Each case builds a throwaway tree — `stories/` plus `docs/adrs/` with a generated registry —
and runs the checker over it with `--root`.

  check                  known-good                       known-bad
  1 parse                clean                            unknown-key, duplicate-key,
                                                          duplicate-id, malformed, wrong-type
  2 dangling deps        clean                            dangling-dep (asserts no CYCLE)
  3 cycles               clean                            cycle (asserts no DANGLING-DEP)
  4 adr references       clean                            unknown-adr, unknown-decision,
                                                          adr-without-decisions
  5 orphan ratio         orphan-ratio-printed             orphan-with-decisions
  6 reverse coverage     clean, waiver, superseded        uncovered-decision, zero-decisions

Three could-not-run cases pin exit 2, which is never a pass: no inputs at all, an empty
stories directory, and a missing ADR registry. One case runs the checker with NO argument from
a synthesized repo, because every `--root` case bypasses root discovery entirely and would stay
green while it was broken. One case reads the SHIPPED story template through the checker's own
parser, so the template and the schema cannot drift apart silently.

Run: python3 harness/fixtures/chain_graph_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent
TOOL = FIXTURES.parent / "chain_graph.py"
KIT = FIXTURES.parent.parent

ADR_BODY = """# {adr}: A fixture record

**Status:** Accepted (2026-01-01).

## Context

Fixture context.

## Decisions

### D1: The first decision

{d1}

### D2: The second decision

{d2}

## Consequences

None.

## Alternatives

None.

## Falsification condition

None.

## Cross-references

None.
"""

ADR_NO_DECISIONS = """# {adr}: A fixture record that decides nothing

**Status:** Accepted (2026-01-01).

## Context

Fixture context.

## Decisions

None recorded.

## Consequences

None.

## Alternatives

None.

## Falsification condition

None.

## Cross-references

None.
"""

WAIVER = "Covered-by: none—no code is owed until the substrate measurement lands."
SUPERSEDED = (
    "> **Superseded-in-part by ADR-0102 (2026-02-02).** **Retains:** nothing that a story "
    "would build."
)

BODY = """
# Problem / Context

Fixture story.

# Proposed approach

Fixture approach.

# Scope and non-goals

In scope: nothing.

# Acceptance criteria

- [ ] The assertion count is not reduced versus the merge-base.

# Risks and rollback

None.

# Notes

None.
"""


def story(**fields: str) -> str:
    """A story file from `key: value` pairs, in the order given."""
    lines = "\n".join(f"{k.replace('__', '-')}: {v}" for k, v in fields.items())
    return f"---\n{lines}\n---\n{BODY}"


def registry_for(adr_files: dict[str, str]) -> str:
    rows = "\n".join(
        f"| [{name[:8]}]({name}) | Fixture | Accepted | none | None | 2026-01-01 |"
        for name in sorted(adr_files)
    )
    return (
        "# Architecture Decision Records\n\n"
        "## The registry\n\n"
        "| ADR | Title | Status | Falsifier (court) | Supersession | Date |\n"
        "|-----|-------|--------|-----------------|--------------|------|\n"
        f"{rows}\n"
    )


def build(
    root: Path,
    stories: dict[str, str] | None,
    adrs: dict[str, str] | None,
    registry: str | None = None,
) -> None:
    """Write a throwaway tree. `None` means the directory is absent entirely."""
    if stories is not None:
        (root / "stories").mkdir(parents=True)
        for name, text in stories.items():
            (root / "stories" / name).write_text(text, encoding="utf-8")
    if adrs is not None:
        adr_dir = root / "docs" / "adrs"
        adr_dir.mkdir(parents=True)
        for name, text in adrs.items():
            (adr_dir / name).write_text(text, encoding="utf-8")
        (adr_dir / "README.md").write_text(
            registry if registry is not None else registry_for(adrs), encoding="utf-8"
        )


def run(root: Path) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, str(TOOL), "--root", str(root)], capture_output=True, text=True
    )
    return p.returncode, p.stdout + p.stderr


def case(
    name: str,
    stories: dict[str, str] | None,
    adrs: dict[str, str] | None,
    want: int,
    expect: tuple[str, ...] = (),
    forbid: tuple[str, ...] = (),
    registry: str | None = None,
) -> bool:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "repo"
        root.mkdir()
        build(root, stories, adrs, registry)
        got, out = run(root)
        problems = []
        if got != want:
            problems.append(f"want exit {want}, got {got}")
        for marker in expect:
            if marker not in out:
                problems.append(f"output does not carry {marker!r}")
        for marker in forbid:
            if marker in out:
                problems.append(f"output carries {marker!r}, which this case must not produce")
        ok = not problems
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {'; '.join(problems) if problems else 'as specified'}")
        if not ok:
            print("\n".join(f"        | {line}" for line in out.strip().splitlines()))
        return ok


def default_root_case() -> bool:
    """The checker must find its inputs with NO argument, from the kit layout.

    Every case above passes `--root`, which bypasses discovery entirely, so all of them would
    stay green while the default root pointed at the wrong directory. This one copies the
    checker into `<repo>/harness/` and runs it with no argument.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "repo"
        root.mkdir()
        build(root, CLEAN_STORIES, CLEAN_ADRS)
        (root / "harness").mkdir()
        installed = root / "harness" / "chain_graph.py"
        installed.write_text(TOOL.read_text(encoding="utf-8"), encoding="utf-8")
        p = subprocess.run(
            [sys.executable, str(installed)], capture_output=True, text=True, cwd=root
        )
        ok = p.returncode == 0
        print(f"  {'ok  ' if ok else 'FAIL'} default-root (no argument): want exit 0, got {p.returncode}")
        if not ok:
            print("\n".join(f"        | {line}" for line in (p.stdout + p.stderr).strip().splitlines()))
        return ok


def template_schema_case() -> bool:
    """The SHIPPED story template must parse under the checker's own strict parser.

    The template is the schema's only human-facing statement and the checker is its only
    machine-facing one. Nothing else compares them, so a key added to one and not the other
    would be found by the first story that used it, in a repository, months later.
    """
    sys.path.insert(0, str(TOOL.parent))
    import chain_graph

    text = (KIT / "harness" / "templates" / "story-template.md").read_text(encoding="utf-8")
    fields, errors = chain_graph.parse_frontmatter(text)
    problems = [f"parse error: {e}" for e in errors]
    missing = sorted(chain_graph.CHAIN_KEYS - set(fields))
    if missing:
        problems.append(f"template omits chain field(s): {', '.join(missing)}")
    unknown = sorted(set(fields) - chain_graph.KNOWN_KEYS)
    if unknown:
        problems.append(f"template carries key(s) the checker rejects: {', '.join(unknown)}")
    ok = not problems
    print(f"  {'ok  ' if ok else 'FAIL'} template-schema: {'; '.join(problems) if problems else 'template and checker agree'}")
    return ok


CLEAN_ADRS = {"ADR-0101-fixture.md": ADR_BODY.format(adr="ADR-0101", d1="Text.", d2="Text.")}
CLEAN_STORIES = {
    "STORY-0001-first.md": story(
        id="STORY-0001", title="First", deps="[]", adr="ADR-0101", decisions="[D1]"
    ),
    "STORY-0002-second.md": story(
        id="STORY-0002",
        title="Second",
        deps="[STORY-0001]",
        adr="ADR-0101",
        decisions="[D2]",
    ),
}


def main() -> int:
    two_decisions = ADR_BODY.format(adr="ADR-0101", d1="Text.", d2="Text.")
    results = [
        case("clean", CLEAN_STORIES, CLEAN_ADRS, 0, expect=("chain-graph: OK", "ORPHAN-RATIO")),
        case(
            "waiver",
            {"STORY-0001-first.md": story(id="STORY-0001", title="First", adr="ADR-0101", decisions="[D1]")},
            {"ADR-0101-fixture.md": ADR_BODY.format(adr="ADR-0101", d1="Text.", d2=WAIVER)},
            0,
            expect=("waived=1",),
        ),
        case(
            "superseded-excluded",
            {"STORY-0001-first.md": story(id="STORY-0001", title="First", adr="ADR-0101", decisions="[D1]")},
            {"ADR-0101-fixture.md": ADR_BODY.format(adr="ADR-0101", d1="Text.", d2=SUPERSEDED)},
            0,
            expect=("superseded=1",),
        ),
        case(
            "unknown-key",
            {"STORY-0001-first.md": story(id="STORY-0001", title="First", priority="high")},
            CLEAN_ADRS,
            1,
            expect=("PARSE-UNKNOWN-KEY", "priority"),
        ),
        case(
            "duplicate-key",
            {"STORY-0001-first.md": "---\nid: STORY-0001\ntitle: First\ntitle: Again\n---\n" + BODY},
            CLEAN_ADRS,
            1,
            expect=("PARSE-DUPLICATE-KEY", "title"),
        ),
        case(
            "duplicate-id",
            {
                "STORY-0001-first.md": story(id="STORY-0001", title="First"),
                "STORY-0001-again.md": story(id="STORY-0001", title="Again"),
            },
            CLEAN_ADRS,
            1,
            expect=("PARSE-DUPLICATE-ID", "STORY-0001-first.md", "STORY-0001-again.md"),
        ),
        case(
            "malformed",
            {"STORY-0001-first.md": "---\nid: STORY-0001\ntitle: First\nnested:\n  key: value\n---\n" + BODY},
            CLEAN_ADRS,
            1,
            expect=("PARSE-MALFORMED",),
        ),
        case(
            "wrong-type",
            {"STORY-0001-first.md": story(id="STORY-0001", title="First", deps="STORY-0002")},
            CLEAN_ADRS,
            1,
            expect=("PARSE-MALFORMED", "takes a sequence"),
        ),
        case(
            "dangling-dep",
            {
                "STORY-0001-first.md": story(
                    id="STORY-0001", title="First", deps="[STORY-0404]", adr="ADR-0101", decisions="[D1, D2]"
                )
            },
            CLEAN_ADRS,
            1,
            expect=("DANGLING-DEP", "STORY-0404", "0 resolved edge(s)"),
            forbid=("CYCLE ",),
        ),
        case(
            "cycle",
            {
                "STORY-0001-first.md": story(
                    id="STORY-0001", title="First", deps="[STORY-0002]", adr="ADR-0101", decisions="[D1]"
                ),
                "STORY-0002-second.md": story(
                    id="STORY-0002", title="Second", deps="[STORY-0001]", adr="ADR-0101", decisions="[D2]"
                ),
            },
            CLEAN_ADRS,
            1,
            expect=("CYCLE ", "STORY-0001", "STORY-0002"),
            forbid=("DANGLING-DEP",),
        ),
        case(
            "unknown-adr",
            {
                "STORY-0001-first.md": story(
                    id="STORY-0001", title="First", adr="ADR-0909", decisions="[D1]"
                ),
                "STORY-0002-second.md": story(
                    id="STORY-0002", title="Second", adr="ADR-0101", decisions="[D1, D2]"
                ),
            },
            CLEAN_ADRS,
            1,
            expect=("ADR-REF", "ADR-0909"),
        ),
        case(
            "unknown-decision",
            {
                "STORY-0001-first.md": story(
                    id="STORY-0001", title="First", adr="ADR-0101", decisions="[D1, D9]"
                ),
                "STORY-0002-second.md": story(
                    id="STORY-0002", title="Second", adr="ADR-0101", decisions="[D2]"
                ),
            },
            CLEAN_ADRS,
            1,
            expect=("ADR-REF", "D9"),
        ),
        case(
            "adr-without-decisions",
            {
                "STORY-0001-first.md": story(id="STORY-0001", title="First", adr="ADR-0101"),
                "STORY-0002-second.md": story(
                    id="STORY-0002", title="Second", adr="ADR-0101", decisions="[D1, D2]"
                ),
            },
            CLEAN_ADRS,
            1,
            expect=("ADR-REF", "no decisions"),
        ),
        case(
            "orphan-ratio-printed",
            {
                "STORY-0001-first.md": story(
                    id="STORY-0001", title="First", adr="ADR-0101", decisions="[D1, D2]"
                ),
                "STORY-0002-loose.md": story(id="STORY-0002", title="Loose", adr="ADR-0000"),
            },
            CLEAN_ADRS,
            0,
            expect=("ORPHAN-RATIO", "1 of 2"),
        ),
        case(
            "orphan-with-decisions",
            {
                "STORY-0001-first.md": story(
                    id="STORY-0001", title="First", adr="ADR-0101", decisions="[D1, D2]"
                ),
                "STORY-0002-loose.md": story(
                    id="STORY-0002", title="Loose", adr="ADR-0000", decisions="[D1]"
                ),
            },
            CLEAN_ADRS,
            1,
            expect=("ORPHAN-REF",),
        ),
        case(
            "uncovered-decision",
            {"STORY-0001-first.md": story(id="STORY-0001", title="First", adr="ADR-0101", decisions="[D1]")},
            {"ADR-0101-fixture.md": two_decisions},
            1,
            expect=("UNCOVERED-DECISION", "D2"),
        ),
        case(
            "zero-decisions",
            {"STORY-0001-first.md": story(id="STORY-0001", title="First")},
            {"ADR-0101-fixture.md": ADR_NO_DECISIONS.format(adr="ADR-0101")},
            1,
            expect=("ZERO-DECISIONS",),
        ),
        case("void-nothing", None, None, 2, expect=("VOID",)),
        case("void-no-stories", {}, CLEAN_ADRS, 2, expect=("VOID",)),
        case("void-no-registry", CLEAN_STORIES, None, 2, expect=("VOID",)),
        default_root_case(),
        template_schema_case(),
    ]
    if all(results):
        print(f"chain_graph_test: all {len(results)} cases pass")
        return 0
    print(f"chain_graph_test: FAILED ({sum(1 for r in results if not r)} of {len(results)})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

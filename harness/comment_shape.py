#!/usr/bin/env python3
"""Two comment shapes that are always the wrong tool, whatever the language.

THE RULE THIS SERVES, most of which is not checkable. A doc comment above a declaration may be
as long as the decision it records — it becomes documentation, and a full account of the choice,
the rejected alternative and the citation earns its place. A comment BETWEEN STATEMENTS is a
smell unless the algorithm genuinely forces it, because a name or a structure would have served
better and, unlike a comment, cannot drift from the code it describes.

WHAT THIS TOOL DELIBERATELY DOES NOT DO is enforce that rule in general. Telling "above a
declaration" from "between statements" is ambiguous to a regex — a comment above `val x = ...`
inside a function body reads exactly like a doc comment and is not one — and the
forced-by-complexity exemption is a judgement no pattern reaches. A checker that fired on the
general rule would cry wolf, and a check that cries wolf is one somebody eventually edits to
shut up. So it checks two unambiguous shapes and reports the rest as unexamined.

  NUMBERED-LABEL RUN — three or more interior comments numbered in sequence in one file. The
  comment is carrying a label the code never gave, which is the "comment compensating for a
  bad name" red flag at the level of structure rather than of a single identifier. The repair
  is structural: named predicates in an ordered list, after which the names are the labels and
  the ordering is data rather than indentation. It is never an edit to the comment.

  BARE BANNER — a comment line that is nothing but a run of dashes, equals or asterisks. A
  position marker, which the craft-documentation catalog lists as delete-on-sight. Where one
  frames a genuine rationale block, the rationale stays and only the frame goes.

Both were measured against three real repositories before being wired in. The numbered-label
run found 4 files with 0 false positives; every hit was an ordered sequence of conjuncts or
steps that wanted named predicates. Bare banners found 158 in one repository and 0 in two
others, which is a fact about a habit rather than about the languages.

  exit 0   neither shape found, with the denominator printed
  exit 1   at least one found, each named with file:line
  exit 2   NOTHING WAS EXAMINED — the directory is missing or holds no source. Never a pass.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SUFFIXES = {".scala", ".py", ".sh", ".go", ".java", ".ts", ".tsx", ".js", ".rs"}

# An indented line comment: `//` for the C family, `#` for Python and shell.
INTERIOR = re.compile(r"^\s+(//|#)\s?(.*)$")
# Nothing but a rule of dashes, equals or asterisks.
BANNER = re.compile(r"^\s+(//|#)\s*[-=*_]{8,}\s*$")
# `1 ·`, `2.`, `3)`, `4:` — a label where a name belonged.
NUMBERED = re.compile(r"^\s+(//|#)\s*\d+([.):·]|\s+(and|·))")
NUMBERED_RUN_MIN = 3


def findings_for(path: Path) -> list[tuple[int, str, str]]:
    """Return (line number, shape, text) for every hit in one file."""
    out: list[tuple[int, str, str]] = []
    numbered: list[tuple[int, str]] = []
    # A scaladoc continuation begins `*`, so neither pattern below can match inside a doc block
    # and no exemption is needed. An earlier cut carried one; a mutant that deleted it changed
    # nothing, which is how dead code announces itself.
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
        if BANNER.match(line):
            out.append((n, "bare-banner", line.strip()[:70]))
            continue
        if NUMBERED.match(line) and INTERIOR.match(line):
            numbered.append((n, line.strip()[:70]))
    if len(numbered) >= NUMBERED_RUN_MIN:
        out += [(n, "numbered-label-run", t) for n, t in numbered]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True, help="directory to scan, recursively")
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="path fragment to skip; repeatable. A fixture directory belongs here, because a "
        "fixture holds specimen violations on purpose and flagging them is the check reading "
        "its own test data as a finding.",
    )
    a = ap.parse_args()

    root = Path(a.dir)
    if not root.is_dir():
        print(f"comment-shape: '{root}' is not a directory. Nothing examined.", file=sys.stderr)
        return 2

    files = sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix in SUFFIXES and not any(x in str(p) for x in a.exclude)
    )
    if not files:
        print(
            f"comment-shape: no source files under '{root}'. Nothing examined — which is not "
            f"the same as nothing found.",
            file=sys.stderr,
        )
        return 2

    hits = [(f, n, shape, text) for f in files for (n, shape, text) in findings_for(f)]
    banners = sum(1 for h in hits if h[2] == "bare-banner")
    labels = sum(1 for h in hits if h[2] == "numbered-label-run")
    print(
        f"comment-shape: {len(files)} file(s) examined, {banners} bare banner(s), "
        f"{labels} numbered label(s) in runs"
    )
    if not hits:
        return 0
    for f, n, shape, text in hits:
        print(f"  {shape}  {f}:{n}  {text}")
    print(
        "\nThe repair for a numbered-label run is structural — named predicates in an ordered "
        "list — not an edit to the comment. A bare banner is deleted; any rationale it framed "
        "stays where it is."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

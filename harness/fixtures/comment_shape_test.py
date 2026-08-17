#!/usr/bin/env python3
"""Red-first fixture for `harness/comment_shape.py`.

The rule it enforces a NARROW PART OF: a doc comment above a declaration may be as long as the
decision it records, because it becomes documentation. A comment *between statements* is a
smell unless the algorithm forces it, because a name or a structure would have served better
and would not drift from the code.

Most of that rule is not mechanically checkable and the checker does not pretend otherwise.
Distinguishing "above a declaration" from "between statements" is ambiguous to a regex — a
comment above `val x = ...` inside a function body looks like a doc comment and is not one —
and the forced-by-complexity exemption is judgment. Two shapes ARE unambiguous, and were
measured against three real repositories before being wired in, per the rule that a check
crying wolf is one somebody eventually edits to shut up:

  NUMBERED-LABEL RUN   three or more interior comments numbered in sequence in one file.
                       The comment is carrying a label the code never gave. Measured: 4 files
                       across three repositories, 0 false positives — every hit was an ordered
                       sequence of conjuncts or steps that wanted named predicates.

  BARE BANNER          a comment line that is only a run of dashes or equals. A position
                       marker, which the craft-documentation catalog lists as delete-on-sight.
                       Measured: 158 in one repository, 0 in two others.

Cases:
  clean            neither shape present                          -> 0
  banner           one bare `// -----` line                        -> 1
  numbered-run     three numbered interior comments                -> 1
  numbered-under   two numbered comments, below the threshold      -> 0
  numbered-in-doc  numbered lines inside a `/** */` block          -> 0 (never fires on doc)
  short-banner     a bare rule at the 8-character threshold        -> 1
  contentful-rule  dashes WITH text between them                   -> 0 (not a position marker)
  history          a doc comment narrating the code's own past      -> 1
  history-first-cut  the other alternation branch, in an interior     -> 1
  constraint-not-history  the same fact as a live constraint        -> 0
  empty-dir        the directory exists but holds no source        -> 2 (never a pass)
  missing-dir      the directory does not exist                    -> 2 (never a pass)

The last two matter as much as the failing ones: a checker that passes when it found nothing
to check reports the same green as one that verified everything.

Run: python3 harness/fixtures/comment_shape_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "comment_shape.py"

CLEAN = """\
object Thing:
  /** Doc position. As long as the decision it records needs to be. */
  def run(x: Int): Int =
    val doubled = x * 2
    doubled + 1
"""

BANNER = """\
object Thing:
  // ---------------------------------------------------------------
  // A section header.
  // ---------------------------------------------------------------
  def run(x: Int): Int = x
"""

NUMBERED_RUN = """\
object Thing:
  def classify(x: Int): String =
    // 1 · the first check
    if x < 0 then "negative"
    // 2 · the second check
    else if x == 0 then "zero"
    // 3 · the third check
    else "positive"
"""

NUMBERED_UNDER = """\
object Thing:
  def classify(x: Int): String =
    // 1 · the first check
    if x < 0 then "negative"
    // 2 · the second check
    else "other"
"""

SHORT_BANNER = """\
object Thing:
  // --------
  def run(x: Int): Int = x
"""

CONTENTFUL_RULE = """\
object Thing:
  // -- see the note below --
  def run(x: Int): Int = x
"""

HISTORY = """\
object Thing:
  /** Six positions, and `α` is one of them.
    *
    * An earlier cut carried seven, having lifted the digest out — so a claim could not name the
    * term that produced it.
    */
  def run(x: Int): Int = x
"""

HISTORY_FIRST_CUT = """\
object Thing:
  def step(x: Int): Int =
    // The first cut matched on the event alone, so three cases collapsed to one.
    x + 1
"""

CONSTRAINT_NOT_HISTORY = """\
object Thing:
  /** Six positions, and `α` is one of them.
    *
    * Lifting the digest out gives seven and leaves a claim unable to name the term that
    * produced it. The schema version is checked at the boundary.
    */
  def run(x: Int): Int = x
"""

NUMBERED_IN_DOC = """\
object Thing:
  /** The gate's conjuncts, for the reader:
    *
    * 1. the context is recorded
    * 2. the contract is admitted
    * 3. the corner is True
    */
  def gate(x: Int): Boolean = x > 0
"""


def run_tool(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--dir", str(target)], capture_output=True, text=True
    )


def case(name: str, want: int, source: str | None) -> bool:
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "src"
        if source is not None:
            target.mkdir()
            (target / "Thing.scala").write_text(source)
        elif name == "empty-dir":
            target.mkdir()
        got = run_tool(target)
        ok = got.returncode == want
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want}, got {got.returncode}")
        if not ok:
            print(f"       stdout: {got.stdout.strip()[:240]}")
            print(f"       stderr: {got.stderr.strip()[:240]}")
        return ok


def main() -> int:
    if not TOOL.is_file():
        print(f"comment_shape_test: tool not found at {TOOL}", file=sys.stderr)
        return 2
    results = [
        case("clean", 0, CLEAN),
        case("banner", 1, BANNER),
        case("numbered-run", 1, NUMBERED_RUN),
        case("numbered-under", 0, NUMBERED_UNDER),
        case("numbered-in-doc", 0, NUMBERED_IN_DOC),
        case("short-banner", 1, SHORT_BANNER),
        case("contentful-rule", 0, CONTENTFUL_RULE),
        case("history", 1, HISTORY),
        case("history-first-cut", 1, HISTORY_FIRST_CUT),
        case("constraint-not-history", 0, CONSTRAINT_NOT_HISTORY),
        case("empty-dir", 2, None),
        case("missing-dir", 2, None),
    ]
    failed = results.count(False)
    print(f"comment_shape_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

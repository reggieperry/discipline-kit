#!/usr/bin/env python3
"""Red-first fixture for `harness/chain/receipt.py`.

The receipt court is where ADR-0002/D4 becomes mechanism: the reviewer's coverage receipt is
testimony, its denominator is not. The denominator is re-derived from the rules' declared
enforcement grades read from the PINNED examiner copy (ADR-0001/D3), never from the judged
tree, and a receipt covering less than the derived set parks the story — so a skipped
dimension cannot read as covered, and a grade edit in the judged worktree cannot shrink what
the reviewer owes.

Each case builds a throwaway pinned root (a `rules/` directory of graded rule files, declared
by a throwaway kit profile), writes a receipt, runs the court as a CLI, and asserts BOTH the
exit code and a marker string, because the exit code alone cannot tell a park from a refusal
that never derived a denominator at all. The three verdicts are the canonical contract of
ADR-0003/D2 read for this court's own act: 0 the receipt covers the denominator exactly, 1 the
park, 2 could-not-run.

The default pinned copy grades `alpha.md` "review and convention", `beta.md` "partly
mechanical" and `gamma.md` "mechanically enforced", so the derived denominator is
{alpha.md, beta.md}: the two grades that leave review carrying some part of the rule. That
`gamma.md` is absent from a passing receipt is asserted, not assumed — it is the inclusion
rule's own case.

  complete-0                exact coverage, comments and blanks ignored -> 0, PASS, no gamma.md
  short-receipt-parks-1     one owed rule missing (the story criterion) -> 1, PARK naming beta.md
  receipt-absent-parks-1    no receipt file at all: 0 of N covered      -> 1, PARK
  finding-parks-1           full coverage, one finding token            -> 1, PARK, not "uncovered"
  judged-grade-flip         the other story criterion, see below        -> denominator unmoved
  unknown-id-2              an id the pinned copy does not hold         -> 2, VOID naming it
  not-owed-id-2             a pinned but mechanically-enforced rule     -> 2, VOID naming it
  duplicate-id-2            the same dimension claimed twice            -> 2, VOID
  malformed-line-2          a line with no token                        -> 2, VOID naming the line
  bad-token-2               a token outside covered/finding             -> 2, VOID
  covered-trailing-text-2   a caveat after `covered`                    -> 2, VOID
  ungraded-pinned-rule-2    a pinned rule with no grade line            -> 2, VOID naming it
  empty-denominator-2       every pinned rule mechanically enforced     -> 2, VOID, never a pass
  rules-dir-absent-2        a pinned root with no rules copy            -> 2, VOID
  pinned-root-in-worktree-2 the root inside a git working tree          -> 2, VOID (D3)

JUDGED-GRADE-FLIP IS ADR-0002/D4'S NAMED COURT, the one case about a verdict rather than a
refusal. Its falsification condition is a denominator that shrinks when only the judged tree
changes. A judged git repository carries its own copy of the same rules under `.claude/rules/`,
and the court runs with that repository as its working directory holding a receipt that covers
alpha.md alone: the park must fire naming beta.md. Then beta.md's grade is flipped to
"mechanically enforced" in the judged copy ONLY — the edit that, if read, shrinks the
denominator to {alpha.md} and turns the short receipt complete — and the court runs again:
the exit code must be identical, the printed denominator line byte-identical, and the park
still naming beta.md. A court that derives from anywhere in the judged tree passes the second
run and fails here.

EVERY GIT SPAWN IN THIS FIXTURE SCRUBS `GIT_*` from its environment, and every court run gets
the same scrub. A pre-commit hook exports `GIT_DIR` and `GIT_INDEX_FILE`, a subprocess
inherits them, and a fixture that builds a throwaway repository writes into the real one
instead — the defect class this repository has paid for four times.

Run: python3 harness/fixtures/receipt_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "chain" / "receipt.py"

PASS_MARKER = "receipt: PASS"
PARK_MARKER = "receipt: PARK"
VOID_MARKER = "receipt: VOID"
DENOMINATOR_PREFIX = "receipt: denominator"

REVIEW = "review and convention"
PARTLY = "partly mechanical"
MECHANICAL = "mechanically enforced"

# The default pinned copy. alpha and beta are receipt-owed; gamma is not.
DEFAULT_RULES = {"alpha.md": REVIEW, "beta.md": PARTLY, "gamma.md": MECHANICAL}

COMPLETE_RECEIPT = """\
# the reviewer's receipt; comments and blank lines carry nothing

alpha.md covered
beta.md covered
"""


def clean_env() -> dict[str, str]:
    """The environment with git's own variables dropped, for fixture spawns and court runs."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=clean_env(),
    )


def rule_text(token: str) -> str:
    return f"# Some rule\n\n**Enforcement grade:** {token} — what is policed, and what is not.\n\nBody.\n"


def rules_dir(parent: Path, rules: dict[str, str | None]) -> Path:
    """A rules directory under `parent`. A None token writes a rule with no grade line."""
    d = parent / "rules"
    d.mkdir(parents=True)
    for name, token in rules.items():
        body = rule_text(token) if token is not None else "# Some rule\n\nNo grade here.\n"
        (d / name).write_text(body, encoding="utf-8")
    return d


def pinned_root(td: Path, rules: dict[str, str | None] | None = None,
                with_rules: bool = True) -> Path:
    """A pinned root outside every git working tree, holding the examiner copy of the rules."""
    root = td / "pinned"
    root.mkdir()
    if with_rules:
        rules_dir(root, DEFAULT_RULES if rules is None else rules)
    return root


def kit_tree(td: Path, pinned: Path) -> Path:
    """A repository-shaped tree carrying nothing but the chain profile the court reads."""
    kit = td / "kit"
    chain = kit / ".claude" / "chain"
    chain.mkdir(parents=True)
    (chain / "profile.toml").write_text(
        f'terminal = "open-pr"\npush = "branches-only"\npinned_root = "{pinned}"\n'
    )
    return kit


def judged_repo(td: Path, rules: dict[str, str | None]) -> Path:
    """A git working tree carrying its own copy of the rules at the place a checkout keeps them.

    Well-formed on purpose: a judged copy the court could not read would be refused for that
    reason instead of ignored for the right one, and the flip case would pass for the wrong
    reason.
    """
    repo = td / "judged"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main", ".")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "fixture")
    claude = repo / ".claude"
    claude.mkdir()
    rules_dir(claude, rules)
    (repo / "README.md").write_text("the judged tree\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "baseline")
    return repo


def run_tool(kit: Path, receipt: Path, *, cwd: Path | None = None
             ) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--receipt", str(receipt), "--root", str(kit)],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=clean_env(),
    )


def report(name: str, want: int, marker: str, got: subprocess.CompletedProcess[str],
           absent: str | None = None) -> bool:
    said = got.stdout + got.stderr
    ok = got.returncode == want and marker in said and (absent is None or absent not in said)
    detail = f", with '{absent}' absent" if absent else ""
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want} naming '{marker}'{detail}, "
          f"got exit {got.returncode}")
    if not ok:
        print(f"       stdout: {got.stdout.strip()[:400]}")
        print(f"       stderr: {got.stderr.strip()[:400]}")
    return ok


def case(name: str, want: int, marker: str, *, receipt: str | None,
         rules: dict[str, str | None] | None = None, with_rules: bool = True,
         absent: str | None = None) -> bool:
    """Build a pinned root and a kit tree, write the receipt, run the court, compare."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit = kit_tree(tmp, pinned_root(tmp, rules=rules, with_rules=with_rules))
        receipt_path = tmp / "receipt"
        if receipt is not None:
            receipt_path.write_text(receipt, encoding="utf-8")
        return report(name, want, marker, run_tool(kit, receipt_path), absent=absent)


def root_in_worktree_case() -> bool:
    """ADR-0001/D3 at this court: a rules copy inside a working tree pins nothing."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        judged = judged_repo(tmp, DEFAULT_RULES)
        rules_dir(judged / "pinned-shaped", DEFAULT_RULES)
        kit = kit_tree(tmp, judged / "pinned-shaped")
        receipt_path = tmp / "receipt"
        receipt_path.write_text(COMPLETE_RECEIPT, encoding="utf-8")
        return report("pinned-root-in-worktree-2", 2, VOID_MARKER, run_tool(kit, receipt_path))


def denominator_line(said: str) -> str | None:
    for line in said.splitlines():
        if line.startswith(DENOMINATOR_PREFIX):
            return line
    return None


def grade_flip_case() -> bool:
    """The story's second criterion: the denominator cannot be shrunk from the judged tree.

    Run one establishes the park against an untouched judged copy; run two flips beta.md's
    grade in the judged tree ONLY — the edit that would shrink the denominator to {alpha.md}
    and turn the short receipt complete — and everything the court says about the denominator
    must be identical.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit = kit_tree(tmp, pinned_root(tmp))
        judged = judged_repo(tmp, DEFAULT_RULES)
        receipt_path = judged / "receipt"
        receipt_path.write_text("alpha.md covered\n", encoding="utf-8")

        first = run_tool(kit, receipt_path, cwd=judged)
        first_said = first.stdout + first.stderr
        first_line = denominator_line(first_said)
        ok_first = (first.returncode == 1 and PARK_MARKER in first_said
                    and "beta.md" in first_said and first_line is not None
                    and "2" in (first_line or ""))

        flipped = judged / ".claude" / "rules" / "beta.md"
        flipped.write_text(rule_text(MECHANICAL), encoding="utf-8")
        second = run_tool(kit, receipt_path, cwd=judged)
        second_said = second.stdout + second.stderr
        second_line = denominator_line(second_said)
        unmoved = (second.returncode == first.returncode and PARK_MARKER in second_said
                   and "beta.md" in second_said and second_line == first_line)

    ok = ok_first and unmoved
    print(f"  {'ok  ' if ok else 'FAIL'} judged-grade-flip: want the park naming beta.md with "
          f"a 2-rule denominator, unchanged when only the judged copy's grade flips; "
          f"got exit {first.returncode}/{second.returncode}")
    if not ok:
        print(f"       first denominator: {first_line!r}")
        print(f"       second denominator: {second_line!r}")
        print(f"       first: {first_said.strip()[:400]}")
        print(f"       second: {second_said.strip()[:400]}")
    return ok


def main() -> int:
    if not TOOL.is_file():
        print(f"receipt_test: tool not found at {TOOL}", file=sys.stderr)
        return 2
    results = [
        case("complete-0", 0, PASS_MARKER, receipt=COMPLETE_RECEIPT, absent="gamma.md"),
        case("short-receipt-parks-1", 1, "beta.md",
             receipt="alpha.md covered\n", absent=PASS_MARKER),
        case("receipt-absent-parks-1", 1, "0 of 2", receipt=None, absent=PASS_MARKER),
        case("finding-parks-1", 1, "finding",
             receipt="alpha.md covered\nbeta.md finding the grade overstates the gate\n",
             absent="uncovered"),
        grade_flip_case(),
        case("unknown-id-2", 2, "zeta.md",
             receipt=COMPLETE_RECEIPT + "zeta.md covered\n"),
        case("not-owed-id-2", 2, "gamma.md",
             receipt=COMPLETE_RECEIPT + "gamma.md covered\n"),
        case("duplicate-id-2", 2, VOID_MARKER,
             receipt=COMPLETE_RECEIPT + "alpha.md covered\n"),
        case("malformed-line-2", 2, "line 1", receipt="alpha.md\nbeta.md covered\n"),
        case("bad-token-2", 2, VOID_MARKER, receipt="alpha.md coverd\nbeta.md covered\n"),
        case("covered-trailing-text-2", 2, VOID_MARKER,
             receipt="alpha.md covered except section 3\nbeta.md covered\n"),
        case("ungraded-pinned-rule-2", 2, "beta.md",
             rules={"alpha.md": REVIEW, "beta.md": None},
             receipt="alpha.md covered\nbeta.md covered\n"),
        case("empty-denominator-2", 2, VOID_MARKER,
             rules={"alpha.md": MECHANICAL, "gamma.md": MECHANICAL}, receipt=""),
        case("rules-dir-absent-2", 2, VOID_MARKER, with_rules=False,
             receipt=COMPLETE_RECEIPT),
        root_in_worktree_case(),
    ]
    failed = results.count(False)
    print(f"receipt_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

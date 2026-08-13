#!/usr/bin/env python3
"""The reviewer's coverage receipt, checked against a denominator the judged tree cannot shrink.

ADR-0002/D4 names the receipt as one of `merge_ok`'s two bounded testimony inputs. The per-lens
findings inside it are testimony by design — they carry what no check possesses, which
dimensions a reviewer examined. The denominator is NOT testimony: it is re-derived here from
the rules' declared enforcement grades, read from the pinned examiner copy per ADR-0001/D3 and
never from the judged tree, so a grade edit in the judged worktree cannot shrink what the
reviewer owes; and a receipt covering less than the derived set parks the story, so a skipped
dimension cannot read as covered. This module is the D4 court; the reviewer phase that emits
receipts is not built, and the park REF is the sequencer's to write at the merge stage — this
court only returns the verdict that obligates it.

THE RECEIPT is a plain text file, one line per rule-dimension:

    <rule-file> covered
    <rule-file> finding <the reviewer's pointer, opaque to this court>

`<rule-file>` is the rule's file name in the pinned rules directory (`writing-style.md`) — the
identity `harness/rule_grades.py` itself reports by. Blank lines, and lines whose first
non-space character is `#`, carry nothing. Nothing else does either: this court reads the id
and the token and judges neither the rule nor the finding.

THE DENOMINATOR comes from `<pinned_root>/rules/*.md`, the examiner copy of the coding rules,
resolved through the loader's own refusals (a root inside a working tree, material escaping
the root) and read with the same `grade_of` reader `rule_grades.py` runs on the commit path —
one definition of what a grade line says, so the two cannot drift apart. The inclusion rule is
stated once, at `receipt_owed`.

EVERY OPEN QUESTION IS DECIDED FAIL-CLOSED, each pinned by a fixture case:

- An ABSENT receipt parks. It is the short receipt's limiting case — 0 of N covered — and
  ADR-0002/D3.4 requires presence; the remedy is review coverage, not instrument repair,
  which is what makes this a verdict rather than could-not-run.
- A `finding` line counts its dimension as covered (it was examined) and PARKS the story.
  This court cannot see a finding's disposition — that is D3.5's refutation machinery — and
  a finding read as a pass would merge a reviewer-found defect silently.
- A line naming a rule outside the derived denominator — absent from the pinned copy, or
  pinned but mechanically enforced — is could-not-run: the receipt was written against some
  other rule set than the pinned copy, so it is not evidence about this denominator. Surplus
  never compensates; coverage is set equality, not a count.
- A DUPLICATE rule id is could-not-run even when the tokens agree: the schema is one line per
  dimension, and which line is the testimony is not decidable without judgment.
- A MALFORMED line — too few fields, an unknown token, a path-shaped id — is could-not-run,
  never a pass and never silently a park.
- A `covered` line carrying trailing text is malformed: the text is a caveat this court
  cannot read, and reading past it would launder the caveat into a clean pass. Only `finding`
  carries free text, because the pointer is the reviewer's to give and this court's to relay.
- A pinned rule whose grade is missing or out of vocabulary is could-not-run: reading it as
  not-owed would let an ungraded rule shrink the denominator.
- An EMPTY denominator — no rules directory, no rules, or none receipt-owed — is
  could-not-run: a court with nothing to check refuses to pass vacuously, `rule_grades.py`'s
  own posture.

Could-not-run dominates the park when both are met in one receipt, the loader's own ordering
rule: a receipt that does not parse against the pinned denominator is not evidence either way.

THE EXIT CONTRACT is ADR-0003/D2's canonical three, read for this court's own act:

    0   the receipt covers the derived denominator exactly, every token `covered`
    1   the PARK, the one verdict-shaped code: short coverage, an absent receipt, or a
        standing finding (ADR-0002/D4)
    2   could-not-run, naming what was missing or what did not parse; never a pass

Usage:
    python3 harness/chain/receipt.py --receipt <file> [--root <repo>]

`--root` is the repository whose `.claude/chain/profile.toml` declares the pinned root; it
defaults to the repository holding this file, never to anything derived from the receipt or
the working directory. It is what lets `harness/fixtures/receipt_test.py` point the court at
throwaway trees. The court is deliberately not on the commit path: it VOIDs until the
machine-hardening checklist creates the pinned root, and it has no caller until the reviewer
phase emits receipts — it wires the day both exist.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import loader  # noqa: E402  (resolved from this file's own directory, beside it)
import rule_grades  # noqa: E402  (the grade reader the denominator is grounded in, one level up)

PASS = 0
PARK = 1
COULD_NOT_RUN = 2

RULES = "rules"
COVERED = "covered"
FINDING = "finding"

CouldNotRun = loader.CouldNotRun


class Park(Exception):
    """ADR-0002/D4's park: a verdict about the story, carrying its reason."""


def say(line: str) -> None:
    print(line, flush=True)


def grade_token(name: str, body: str | None) -> str:
    """The vocabulary token a pinned rule's grade opens with, or could-not-run.

    Anything less than a parseable grade refuses: a rule read as ungraded-therefore-not-owed
    would be a judged-tree-shaped shrink performed by the pinned copy's own rot.
    """
    if body is None:
        raise CouldNotRun(
            f"{name} in the pinned rules copy declares no enforcement grade, so whether the "
            "reviewer owes it a lens cannot be derived"
        )
    for token in rule_grades.TOKENS:
        if body.startswith(token):
            return token
    raise CouldNotRun(
        f"{name} in the pinned rules copy opens its grade with an unknown token: {body[:60]!r}"
    )


def receipt_owed(pinned: Path) -> list[str]:
    """The denominator: every pinned rule whose grade leaves review carrying any part of it.

    THE INCLUSION RULE, in one sentence: a rule is receipt-owed exactly when its declared grade
    opens with "review and convention" or "partly mechanical" — the two tokens of
    `rule_grades.py`'s vocabulary that put some conjunct on review rather than on a check —
    and "mechanically enforced" is excluded because a check already fails when such a rule is
    broken, so a review lens adds no coverage a check does not have.
    """
    rules_copy = pinned / RULES
    loader.refuse_escaping_material(pinned, rules_copy)
    if not rules_copy.is_dir():
        raise CouldNotRun(
            f"no pinned rules copy at {rules_copy}, so no denominator can be derived "
            "(ADR-0002/D4 re-derives it from the pinned examiner copy and from nowhere else)"
        )
    files = sorted(rules_copy.glob("*.md"))
    if not files:
        raise CouldNotRun(f"{rules_copy} holds no rules; refusing to pass vacuously")
    owed = [p.name for p in files
            if grade_token(p.name, rule_grades.grade_of(p.read_text(encoding="utf-8")))
            != "mechanically enforced"]
    if not owed:
        raise CouldNotRun(
            f"every rule in {rules_copy} is mechanically enforced, so the denominator is "
            "empty; a receipt court with nothing to check refuses to pass vacuously"
        )
    say(f"receipt: denominator {len(owed)} receipt-owed rule(s) from {rules_copy.name}/: "
        f"{', '.join(owed)}")
    return owed


def parse_receipt(path: Path) -> list[tuple[str, str, str]] | None:
    """The receipt's lines as (rule id, token, pointer), or None when the file is absent.

    Absence is the caller's park, not a refusal: it is a fact about coverage. Everything that
    IS present must parse exactly, and the first line that does not is could-not-run.
    """
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise CouldNotRun(f"the receipt at {path} could not be read: {e}") from e
    entries: list[tuple[str, str, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            raise CouldNotRun(
                f"{path}, line {number}: {raw.strip()!r} is not '<rule-file> <token>'"
            )
        rule, token, pointer = fields[0], fields[1], " ".join(fields[2:])
        if "/" in rule or "\\" in rule or not rule.endswith(".md"):
            raise CouldNotRun(
                f"{path}, line {number}: {rule!r} is not a rule file name, so what dimension "
                "it claims is not decidable"
            )
        if token not in (COVERED, FINDING):
            raise CouldNotRun(
                f"{path}, line {number}: {token!r} is not '{COVERED}' or '{FINDING}'"
            )
        if token == COVERED and pointer:
            raise CouldNotRun(
                f"{path}, line {number}: a '{COVERED}' line carries trailing text "
                f"({pointer[:60]!r}), a caveat this court cannot read and must not read past"
            )
        entries.append((rule, token, pointer))
    return entries


def check(root: Path, receipt: Path) -> None:
    """Derive the denominator from the pinned copy and hold the receipt to it, or raise.

    The denominator derivation touches the pinned root only; nothing here reads the judged
    tree, takes a judged-tree argument, or resolves anything relative to the working
    directory, which is what the grade-flip fixture case observes from outside.
    """
    pinned = loader.declared_pinned_root(root)
    loader.refuse_judged_root(pinned)
    say(f"receipt: pinned root {pinned}, declared by {root / loader.PROFILE}")
    owed = receipt_owed(pinned)

    entries = parse_receipt(receipt)
    if entries is None:
        raise Park(f"no receipt at {receipt}, which covers 0 of {len(owed)} receipt-owed "
                   "rule(s)")

    seen: set[str] = set()
    for rule, _, _ in entries:
        if rule in seen:
            raise CouldNotRun(
                f"the receipt claims {rule} twice, and which line is the testimony is not "
                "decidable without judgment"
            )
        seen.add(rule)
    foreign = sorted(seen - set(owed))
    if foreign:
        raise CouldNotRun(
            f"the receipt names rule(s) outside the derived denominator: {', '.join(foreign)}; "
            "it was written against some other rule set than the pinned copy, so it is not "
            "evidence about this denominator"
        )

    say(f"receipt: covered {len(seen)} of {len(owed)} receipt-owed rule(s)")
    uncovered = sorted(set(owed) - seen)
    if uncovered:
        raise Park(f"the receipt covers {len(seen)} of {len(owed)} receipt-owed rule(s); "
                   f"uncovered: {', '.join(uncovered)}")
    findings = [(rule, pointer) for rule, token, pointer in entries if token == FINDING]
    if findings:
        listed = "; ".join(f"{rule} — {pointer}" if pointer else rule
                           for rule, pointer in findings)
        raise Park(f"{len(findings)} finding(s) stand in the receipt, and this court cannot "
                   f"see their disposition: {listed}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Check the reviewer's coverage receipt against the pinned denominator.")
    ap.add_argument("--receipt", required=True, help="the receipt the reviewer phase emitted")
    ap.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[2]),
        help="the repository whose chain profile declares the pinned root; the grader's own, "
             "never the graded tree",
    )
    a = ap.parse_args()

    try:
        check(Path(a.root).resolve(), Path(a.receipt))
    except Park as e:
        print(f"receipt: PARK: {e} (ADR-0002/D4)", file=sys.stderr)
        return PARK
    except CouldNotRun as e:
        print(f"receipt: VOID: {e}; not a pass", file=sys.stderr)
        return COULD_NOT_RUN
    except OSError as e:
        print(f"receipt: VOID: a filesystem read failed: {e}; not a pass", file=sys.stderr)
        return COULD_NOT_RUN
    print("receipt: PASS: the receipt covers every receipt-owed rule, every token covered")
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())

---
id: STORY-0008
title: The reviewer's coverage receipt and its re-derived denominator
deps: [STORY-0004]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0002
decisions: [D4]
group: B
---

# Problem / Context

The receipt's shape, the denominator re-derived from the rules' declared grades read from the pinned examiner copy, and the park on a short receipt land with the unbuilt reviewer phase. This story covers the receipt half only, which is the half merge_ok reads.

Grounding: `docs/adrs/ADR-0002-merge-posture.md`, D4. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

Receipt schema; denominator derivation from the pinned rules copy; park on short receipt; the completeness check with red and green fixtures.

# Scope and non-goals

In scope:

- the receipt and its checks

Out of scope:

- the reviewer phase brief itself

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] a receipt shorter than the derived denominator parks the story—verified by `the receipt-completeness check's known-bad fixture`: `short-receipt-parks-1` in `harness/fixtures/receipt_test.py` requires exit 1 naming the uncovered rule with the pass marker absent, and `receipt-absent-parks-1` pins the limiting case, 0 of N covered
- [x] the denominator cannot be shrunk from the judged tree—verified by `a fixture flipping a rule grade in the judged tree only`: `judged-grade-flip` flips a rule to "mechanically enforced" in the judged working tree's own rules copy and nothing else, and requires the exit code identical, the printed denominator line byte-identical, and the park still naming the same rule

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [x] The assertion count is not reduced versus the merge-base.
- [x] No new suppressions are introduced versus the merge-base. (What the tick covers: the new module carries two `noqa: E402` import lines, the same sys.path-then-import shape every existing chain module carries—advance, attempt, core, invoke—and no scanner on the commit path reads `noqa`; nothing else suppression-shaped was added.)
- [x] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a gamed denominator reads a skipped dimension as covered—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- Built 2026-08-13, the receipt half only. The schema (`<rule-file> covered|finding`, one line
  per rule-dimension), the inclusion rule (receipt-owed exactly when the grade opens with
  "review and convention" or "partly mechanical"), and every fail-closed decision—an absent
  receipt parks as the 0-of-N limiting case; a `finding` counts its dimension covered and
  parks; an id outside the denominator, a duplicate, and any malformed line (including
  `covered` with trailing text) are could-not-run; an ungraded pinned rule and an empty
  denominator are could-not-run—are stated in `harness/chain/receipt.py`'s docstring, each
  pinned by a case in `harness/fixtures/receipt_test.py` (15 cases). Red-first: 1 of 15 against
  a stub that admitted everything, the one green case green for the stub's reason. Six
  hand-applied mutations, six killed, each verified compiling and executing before the kill was
  believed. The fixture is wired into `scripts/check.sh`; the court itself stays off the commit
  path until the reviewer phase emits receipts and the pinned root exists—the loader
  precedent, recorded as the check.sh comment. Anti-weakening evidence: the diff versus
  033a1b3 deletes nothing (check.sh purely additive), the new module's two `noqa: E402` import
  lines match the established chain-module pattern, and the only "skip" matches are the word
  in prose.
- Merge-review fix round (FIX_NEEDED, all findings demonstrated by measurement; fixed
  red-first, re-verified). Containment now applies per rule FILE, not only per directory: one
  pinned rule symlinked into the judged tree handed that tree the grade, and a flip there
  shrank the denominator and signed a short receipt—exit 1 then exit 0 across the flip; both
  runs now VOID (`rule-file-symlink-escape`). An invalid-UTF-8 pinned rule escaped as a
  UnicodeDecodeError traceback with exit 1, the one verdict-shaped code; now could-not-run
  naming the file (`undecodable-pinned-rule-2`). The could-not-run-dominates-park ordering
  claim was unpinned—the reviewer's reorder mutation survived 19 of 19 minus the new case—
  and `short-and-foreign-2` now pins it (mutation re-applied: killed). The pointer-less
  `finding` is decided accepted-and-parking, stated in the docstring and pinned by
  `finding-bare-parks-1` (an empty pointer carries no caveat to launder, so the
  covered-trailer refusal's reason does not reach it; discriminates against the
  finding-park-dropped mutant). Three live rules grading themselves "mechanically enforced
  for <scope>" were regraded "partly mechanical" with the scope sentences retained
  (java-testing, python-testing, scala-testing); a scratch probe over a pinned copy of the
  live corpus moved the denominator from 50 to 53 of 57. Fixture at 19 cases; regression:
  original mutations 1 and 2 re-run, both still killed (6/19 and 14/19).
- Re-verification round: the fix round's own per-file refusal moved one corner from correct
  to verdict-shaped—a self-referential symlink among the pinned rules raises RuntimeError
  from pathlib's resolve on this interpreter, which neither the loader's refusal nor the
  OSError net catches, so it escaped as a traceback with exit 1 (at the merge-base the same
  tree read exit 2 through the read's OSError net). Closed red-first: the per-file refusal
  maps RuntimeError to could-not-run naming the file, pinned by `self-symlink-rule-2`;
  `rule-file-symlink-escape` (now also asserting its ADR-0001/D3 message) and
  `undecodable-pinned-rule-2` re-run as regression, both unchanged. Fixture at 20 cases.
- Follow-up, recorded not fixed (pre-existing, outside this story's diff): `loader.py`'s own
  `refuse_escaping_material` call sites share the latent RuntimeError class—`load`'s net is
  OSError-only—so a symlink loop in pinned postcondition material would escape the same way;
  the next loader story inherits it.

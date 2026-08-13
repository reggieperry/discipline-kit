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

- [ ] a receipt shorter than the derived denominator parks the story—verified by `the receipt-completeness check's known-bad fixture`
- [ ] the denominator cannot be shrunk from the judged tree—verified by `a fixture flipping a rule grade in the judged tree only`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a gamed denominator reads a skipped dimension as covered—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.

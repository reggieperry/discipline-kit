---
id: STORY-0007
title: The merge stage: merge_ok's conjuncts and the declared terminal act
deps: [STORY-0003, STORY-0006]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0002
decisions: [D1, D3, D5]
group: A
---

# Problem / Context

No conjunct of `merge_ok` is evaluated anywhere; neither terminal act exists; the push-scope guard and the merge record naming the forged-ref residue are future by the ADR's own text.

Grounding: `docs/adrs/ADR-0002-merge-posture.md`, D1, D3, and D5. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

The trial merge against one pinned candidate sha; the eight conjuncts with a per-conjunct receipt; conjunct 8's mechanism chosen here as the ADR reserves; both terminal acts behind the profile; the push-scope guard; the residue-naming merge record.

# Scope and non-goals

In scope:

- merge stage, terminal acts, push-scope guard, merge record

Out of scope:

- the PR-merge rules themselves (operator-side, per D1)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] merge_ok holds only when all eight conjuncts pass against the pinned sha—verified by `per-conjunct known-bad fixtures`
- [ ] a chain push of main is impossible under both terminal acts—verified by `the push-scope guard's fixture`
- [ ] the merge record names the forged-ref residue as open—verified by `a record-content assertion in the merge-stage fixture`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a conjunct evaluated against the wrong tree signs the wrong work—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- Recorded by STORY-0005's merge review: that story's seam discloses three residues the merge
  stage is the natural reader of, and how it consumes them is this story's interface call rather
  than the seam's. The seam reads porcelain once, before the postcondition runs and not after, so
  a postcondition that dirties the tree it grades is not caught there. It grades the WORKING TREE
  at the path it was given rather than a fresh checkout of the sha it records, which is the same
  question ADR-0002/D3.8 leaves open as a conjunct owed a mechanism—source-set integrity, the
  tree the checks graded being the tree being merged. And the forged-ref residue ADR-0001
  discloses stands: an agent holding Bash writes the same ref the seam writes, and D3.7's
  one-pinned-candidate-sha conjunct is evaluated over refs that carry that residue with them.

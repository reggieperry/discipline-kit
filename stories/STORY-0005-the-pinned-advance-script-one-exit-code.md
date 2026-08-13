---
id: STORY-0005
title: The pinned advance script: one exit-code contract, and the ref write inside it
deps: [STORY-0001, STORY-0004]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0003
decisions: [D2, D3, D6]
group: A
---

# Problem / Context

No advance script exists: the canonical 0/1/2 contract, the adaptation of divergent native contracts (red-proof), the ref write as the script's last act, and the porcelain-empty seam precondition are all decided and unbuilt.

Grounding: `docs/adrs/ADR-0003-sequencer-obligations.md`, D2, D3, and D6. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

One advance script per phase seam wrapping its postcondition: canonical exit contract, every other code reading could-not-run, ref written then exit 0 with a failed write forcing nonzero, porcelain-empty checked first.

# Scope and non-goals

In scope:

- the advance scripts and their fixtures

Out of scope:

- the seam court replay (STORY-0010), position derivation (STORY-0006)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] a failed ref write forces a nonzero exit—verified by `an advance-script fixture with update-ref forced to fail`
- [ ] a dirty tree at the seam reads could-not-run—verified by `the porcelain-precondition fixture`
- [ ] red-proof's native exit 2 reads as fail, not could-not-run—verified by `the adaptation fixture`
- [ ] a parent repository holding live phase worktrees still reads porcelain-empty at the seam, either because the precondition accounts for the worktree path or because the worktrees are placed outside the parent—verified by `a porcelain-precondition fixture case with a phase worktree materialized and the tree otherwise clean`
- [ ] the phase invocation pins its settings sources, so a user-scope hook cannot inject into a phase transcript—verified by `an invocation fixture run with a decoy user-scope SessionStart hook, asserting the hook's marker is absent from the phase transcript`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a wrapper that misroutes a broken instrument as a story fail—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- The last two acceptance criteria come from `docs/probe/D7-headless-probe-2026-08-12.md`, which
  measured both facts rather than predicting them: worktrees materialize under
  `.claude/worktrees/` INSIDE the parent repository and show up as an untracked directory, and
  user-scope SessionStart hooks fire in headless runs—the operator's own startup hook injected
  machine-identity detail into both legs' transcripts. The worktree criterion is written so
  either remedy discharges it, because that choice belongs to this story's builder and not to
  the probe.

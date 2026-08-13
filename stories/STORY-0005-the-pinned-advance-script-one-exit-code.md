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
- [ ] a parent repository holding a live phase worktree still reads porcelain-empty at the seam because the worktree is placed outside the parent (ADR-0004/D2 decided the arm)—verified by `a porcelain-precondition fixture case with a sequencer-created outside worktree materialized and the parent otherwise clean`
- [ ] the phase invocation pins its settings sources, so a user-scope hook cannot inject into a phase transcript—verified by `an invocation fixture run with a decoy user-scope SessionStart hook, asserting the hook's marker is absent from the phase transcript`
- [ ] a phase brief that does not resolve from pinned material fails closed before any invocation launches—verified by `an invocation fixture with the pinned brief absent, asserting a nonzero exit and no session started` (rewritten for ADR-0004/D1: there is no phase type to substitute; the brief is the composed prompt)

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
- The last three acceptance criteria come from `docs/probe/D7-headless-probe-2026-08-12.md`, read
  at its correction, which measured all three facts rather than predicting them. Worktrees
  materialize under `.claude/worktrees/` INSIDE the parent repository, and the audit strengthened
  the ground: the design's §4.8 VERIFIED mark claiming they are git-excluded is measured FALSE at
  2.1.224—`.git/info/exclude` is the stock template and the parent's porcelain prints
  `?? .claude/worktrees/`—so the precondition cannot rely on an exclusion the harness does not
  write. The worktree criterion is written so either remedy discharges it, because that choice
  belongs to this story's builder and not to the probe. User-scope SessionStart hooks fire in
  headless runs: the operator's own startup hook injected machine-identity detail into both legs'
  transcripts. And leg 1 measured the fail-open the third criterion closes—the wrapper's main
  agent, meeting a phase type it could not resolve, improvised a substitute brief from the judged
  tree and carried on, which is ADR-0001/D3's defect reached by initiative inside the wrapper.
- The third part of that corrected rule is a phase-brief content rule rather than a check, so it
  is recorded here instead of as a criterion: the invoking prompt carries spawn-by-name only and
  never phase instructions, because a prompt relaying instruction content can override the pinned
  definition. STORY-0009 carries the judged-tree half.

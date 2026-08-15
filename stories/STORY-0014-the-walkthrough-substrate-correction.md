---
id: STORY-0014
title: Correct the walkthrough's substrate assertion—the sequencer drives, not the main loop
deps: [STORY-0013]
labels: [chain, docs]
sensitive_files: []
status: draft
adr: ADR-0004
decisions: [D1]
group: B
---

# Problem / Context

ADR-0004's Consequences retired the walkthrough's substrate assertion—"the main loop drives"—and
recorded that its roughly a dozen sites "inherit the correction with the sequencer build." The
sequencer built (STORY-0013, merged); the correction is now due, and the walkthrough still
teaches the superseded substrate: an interactive main-loop session holding judgment on the
advancement path, the shape ADR-0004 rejected on disinterest.

Grounding against HEAD:

- `docs/sdlc-chain-walkthrough.md`—13 occurrences of "main loop" (`grep -c`, verified), including
  the rule statement at line 28 ("the main loop drives"), the D7 heading at line 401 ("The merge
  stage—main loop, not an agent"), and the per-stage prose at lines 228, 234, 240–241, 254, 263,
  288, 316, 357, and 404.
- `docs/adrs/ADR-0004-substrate-choice.md`, Consequences—"the walkthrough's substrate assertion
  ('the main loop drives') retires: the pinned sequencer drives, and phases are sessions. What
  survives, reworded, is its true half—the merge stage is not an agent, it is the sequencer's."
- `harness/chain/sequencer.py`—the pinned driver now exists, so the corrected prose describes
  shipped mechanism rather than intention.

# Proposed approach

Edit `docs/sdlc-chain-walkthrough.md` only. At each site, replace the main-loop framing with the
pinned sequencer per ADR-0004/D1's substrate—preserving each sentence's true content (verdicts
derived from refs and exit codes, never from a workflow's return string; the merge stage is the
sequencer's, not an agent's; the gate re-runs on the produced tree) and the document's structure
and length. This is a rewording pass, not a rewrite: sentences keep their claims with the correct
actor named.

# Scope and non-goals

In scope:

- the walkthrough's main-loop sites, reworded to the sequencer substrate

Out of scope:

- `docs/sdlc-chain-design.md` and the ADRs (their own texts stand as records; the design doc's
  wording corrections are separately recorded follow-ups)
- any file other than the walkthrough
- restructuring the walkthrough beyond the substrate rewording

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] the walkthrough contains zero occurrences of "main loop" and remains a substantially intact
      document naming the sequencer as the driver—verified by `the walkthrough-corrected pinned
      postcondition (grep zero, length floor, the sequencer named), graded at the phase seam and
      re-graded at the merged tree by conjunct 1's suite`
- [ ] the correction is chain-built: two live phases under sequencer.py run, phase refs recorded,
      the coverage receipt complete, all eight merge conjuncts passing, and the merge-local act
      advancing the dedicated clone's main—verified by `the composed merge record's merge_ok line
      and the sequencer's exit 0`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each
before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a rewording that drops a true claim while removing the stale actor—mitigation: the
  postcondition holds the mechanical floor (zero stale sites, document intact), and the receipt
  phase plus operator read of the diff at transplant hold the editorial content.
- Rollback: revert the story's commits; the walkthrough's prior text stands in history.

# Notes

- The chain's first production story: driven end to end by `sequencer.py run` in the dedicated
  clone, with the operator authoring pinned material and transplanting the result to the kit
  branch (the merge-local posture's operator-side trunk crossing).
- The originally proposed first production story (ci.yml) was refused by the chain's own gates:
  `.github/workflows/` is trusted_base, conjunct 2 parks any story diff touching it, and
  profile-check inside conjunct 1 refuses the narrowing that would evade it. That work landed
  operator-side (the delegation commit); the refusal is the anti-weakening architecture composing
  as designed and is worth this line so nobody re-proposes it.

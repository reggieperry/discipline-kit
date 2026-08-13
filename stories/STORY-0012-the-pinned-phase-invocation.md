---
id: STORY-0012
title: The pinned phase invocation—settings, brief, worktree custody, and the version-scoped probe
deps: [STORY-0003, STORY-0005]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0004
decisions: [D1, D2, D3, D4, D5]
group: A
---

# Problem / Context

ADR-0004 chose the substrate: each phase is its own headless invocation, driven by the
pinned sequencer, with sequencer-owned worktrees outside the parent and every invocation
pinning its settings sources and brief. None of that invocation layer exists.

Grounding: `docs/adrs/ADR-0004-substrate-choice.md`, D1 through D5, and the probe record
`docs/probe/D7-headless-probe-2026-08-12.md` with its correction section. Stub depth per the
walkthrough's proximity rule.

# Proposed approach

The invocation builder inside the sequencer: compose the phase prompt from the pinned brief
file; pin settings sources to the sequencer-supplied project settings, excluding user scope;
assert no `.claude/agents/` in the judged tree before each phase; create and remove
attest-only worktrees at a pinned location outside the parent; re-run dead phases under a
fresh attempt; record the harness version against the profile's pin and re-run the extended
D7 probe on change.

# Scope and non-goals

In scope:

- the invocation builder, its fences, and their fixtures

Out of scope:

- the seam and advance scripts (STORY-0005), the sequencer core (STORY-0006), the
  unattended-run envelope (its own owed record)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] each phase runs as exactly one headless invocation whose prompt is composed from the
      pinned brief file and nothing else—verified by `the invocation-builder fixture comparing
      the composed prompt byte-for-byte against the pinned brief`
- [ ] a phase run with a decoy user-scope SessionStart hook shows no injected content in its
      transcript—verified by `the settings-pinning fixture (the per-invocation twin of
      STORY-0006's sequencer-level case, cross-referenced there)`
- [ ] a `.claude/agents/` directory in the judged tree at phase start is a named finding,
      absence asserted from the filesystem—verified by `the pre-phase assertion's known-bad fixture`
- [ ] an attest-only phase runs in a sequencer-created worktree outside the parent, removed
      after the seam, with porcelain empty in BOTH trees at the seam (the parent, and the
      worktree the phase ran in, per ADR-0003/D6's every-seam rule)—verified by `the
      worktree-custody fixture, including STORY-0005's live-worktree porcelain case`
- [ ] a dead or compaction-marked phase is re-run under a fresh attempt with the pinned
      worktree path cleared first—verified by `the fresh-attempt fixture killing a phase
      mid-run and asserting the retry succeeds at the same pinned path`
- [ ] no phase can spawn a subagent, and no advancement-path source consumes a wrapper
      return string or depends on --resume—verified by `the D5 grep-shaped source check, one
      pattern wider, plus the post-batch transcript audit flagging any task-start event in a
      phase transcript`
- [ ] a harness version differing from the profile's pin re-runs the extended probe before
      any phase—verified by `the version-gate fixture`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: settings-source pinning drifts across harness releases—mitigation: the version gate
  re-runs the probe before trusting a new binary.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by ADR-0004's landing commit; the coverage gate requires this story in the same
  commit as the record it covers.

---
id: STORY-0011
title: Fail-closed start-up: the sequencer refuses to run unposture-d
deps: [STORY-0006]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0003
decisions: [D5]
group: A
---

# Problem / Context

ADR-0003/D5: the sequencer refuses to run—could-not-run, loudly—on an absent or unparseable profile, no declared terminal act, or an unset or incomplete trusted_base. The refusal path is code that does not exist.

Grounding: `docs/adrs/ADR-0003-sequencer-obligations.md`, D5. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

The start-up gate in the sequencer core, reading the profile as ADR-0002 shapes it, with a refusal fixture per condition.

# Scope and non-goals

In scope:

- the start-up refusals and their fixtures

Out of scope:

- the core's derivation (STORY-0006), the profile itself (STORY-0003)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] each refusal condition reads could-not-run with the condition named—verified by `one known-bad fixture per condition`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a sequencer that runs unguarded while reporting progress—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.

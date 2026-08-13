---
id: STORY-0003
title: The chain profile: schema, the kit's own instance, and its integrity check
deps: []
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0002
decisions: [D2]
group: A
---

# Problem / Context

No `.claude/chain/profile.toml` exists, so `merge-posture-check.sh` reports nothing to guard and two falsification courts read VOID. ADR-0002/D2 decides the posture is declared per repository.

Grounding: `docs/adrs/ADR-0002-merge-posture.md`, D2. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

Define the profile schema (terminal act, push scope, trusted_base), write this repository's instance, and build the profile-integrity check: fail when `trusted_base` omits its own file, the CI workflows, or any path the commit-path check invokes or reads.

# Scope and non-goals

In scope:

- schema, the kit's profile, the integrity check with red and green fixtures

Out of scope:

- the sequencer paths half (STORY-0009), any sequencer code

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] the kit's profile exists and `merge-posture-check.sh` reports a guarded pairing—verified by `bash scripts/merge-posture-check.sh`
- [ ] a profile whose trusted_base omits a required path fails—verified by `the profile-integrity check's known-bad fixture`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a wrong trusted_base list blesses the wrong cage—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- The schema should carry the settings-source pinning declaration, so the sources a phase and the
  sequencer invoke with are declared per repository beside the posture rather than hard-coded in
  whatever script happens to build the command line. `docs/probe/D7-headless-probe-2026-08-12.md`
  is why: user-scope SessionStart hooks fire in headless runs, and STORY-0005 and STORY-0006 each
  carry a criterion that the pinning holds.

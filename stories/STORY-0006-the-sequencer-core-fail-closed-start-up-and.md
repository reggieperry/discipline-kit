---
id: STORY-0006
title: The sequencer core: fail-closed start-up and re-derived position
deps: [STORY-0001, STORY-0003, STORY-0005]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0001
decisions: [D1, D5]
group: A
---

# Problem / Context

The position-derivation function over `refs/chain/<story>/attempt-<a>/phase-<n>`, the re-walk rule's atomic deletion, and the resume path reading only session ids and liveness do not exist.

Grounding: `docs/adrs/ADR-0001-advancement-re-derived.md`, D1 and D5. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

The derivation function and re-walk deletion as pinned code; the resume path; the fixture repository where derived position must equal planted refs; the grep-shaped source check for D5.

# Scope and non-goals

In scope:

- derivation, re-walk, resume reads, both courts

Out of scope:

- start-up refusal detail (STORY-0011), phases themselves

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] derived position equals planted refs across the fixture repository—verified by `the position fixture named in ADR-0001's Falsification section`
- [ ] no sequencer source reads the log, status frontmatter, or stream verdict fields for control flow—verified by `the D5 grep-shaped source check`
- [ ] the sequencer's own invocation pins its settings sources, so a user-scope hook cannot inject into the run it drives—verified by `an invocation fixture run with a decoy user-scope SessionStart hook, asserting the hook's marker is absent from every phase transcript the run produced (the sequencer itself is a script under ADR-0004/D1 and has no transcript)`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a derivation bug silently replays or skips a phase—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- The settings-source criterion comes from `docs/probe/D7-headless-probe-2026-08-12.md`: user-scope
  SessionStart hooks fire in headless runs, so an unattended run inherits whatever the operator's
  user-level hooks inject unless the invocation pins its sources. STORY-0005 carries the same
  criterion for the phase invocations; this one is the sequencer's own.

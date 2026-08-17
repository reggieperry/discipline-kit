---
id: STORY-0010
title: The seam court: the denial probe replayed against the real sequencer
deps: [STORY-0005]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0001
decisions: [D2]
group: A
---

# Problem / Context

ADR-0001/D2's court is specified and unbuilt: a did-nothing tree must FAIL, a known-good tree must PASS, a tools-disabled run must read could-not-run, replayed against the real seam.

Grounding: `docs/adrs/ADR-0001-advancement-re-derived.md`, D2. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

Build the replay as a fixture over the advance scripts of STORY-0005, per ADR-0001/D4's red-and-green rule applied to the seam itself.

# Scope and non-goals

In scope:

- the three-outcome replay fixture

Out of scope:

- the advance scripts (STORY-0005)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] did-nothing FAIL, known-good PASS, tools-disabled could-not-run—verified by `the seam-court fixture's four cases` (the fourth, a merge-review follow-up, denies the exec at the seam run itself rather than at the demonstration)

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [x] The assertion count is not reduced versus the merge-base.
- [x] No new suppressions are introduced versus the merge-base.
- [x] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a replay that passes against a stub seam (the confounded-case trap)—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.

---
id: STORY-0004
title: The postcondition loader: examiner material pinned, and no verdict before red and green
deps: []
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0001
decisions: [D3, D4]
group: A
---

# Problem / Context

Postconditions, their configuration, and their fixtures have no pinned resolution, and nothing refuses an undemonstrated postcondition. Both judged-tree violations D3 names are already measured in the design.

Grounding: `docs/adrs/ADR-0001-advancement-re-derived.md`, D3 and D4. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

A loader resolving postconditions from a pinned out-of-tree location; refusal (could-not-run) of any postcondition lacking its red and green fixtures; the examiner-pinning test.

# Scope and non-goals

In scope:

- the loader, the pinned layout, the pinning test

Out of scope:

- the advance scripts themselves (STORY-0005)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] an undemonstrated postcondition's verdict reads could-not-run—verified by `the loader's known-bad fixture (fixtures absent)`
- [ ] a verdict does not change when only the judged tree's copies change—verified by `the examiner-pinning test named in ADR-0001's Falsification section`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: pinned-path layout diverges from the machine-hardening checklist—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.

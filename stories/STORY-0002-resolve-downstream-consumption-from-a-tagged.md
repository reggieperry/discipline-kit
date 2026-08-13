---
id: STORY-0002
title: Resolve downstream consumption from a tagged release, and check it
deps: []
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0002
decisions: [D7]
group: B
---

# Problem / Context

`install.sh --refresh-rules` copies from whatever tree the checkout holds and scrapes a version from `CHANGELOG.md`; no tag is resolved, so a bad merge on `main` reaches consumers before any backstop acts. ADR-0002/D7 decides consumers resolve tags the operator mints.

Grounding: `docs/adrs/ADR-0002-merge-posture.md`, D7. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

Make the installer resolve a tagged release (checkout or archive of the tag) and refuse a bare tree; add a check that fails when a consumer path would resolve `main`.

# Scope and non-goals

In scope:

- `install.sh` tag resolution and its check

Out of scope:

- release automation, tag minting policy (operator acts, per D7)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] `install.sh --refresh-rules` resolves a tag, never the checkout tree—verified by `a new fixture case driving the installer against a repo where HEAD differs from the latest tag`
- [ ] a consumer path resolving `main` fails the build—verified by `the D7 court named in ADR-0002's Falsification section, wired into scripts/check.sh`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: installer behavior change breaks existing refresh flows—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.

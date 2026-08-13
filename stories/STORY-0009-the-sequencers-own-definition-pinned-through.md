---
id: STORY-0009
title: The sequencer's own definition pinned through the profile
deps: [STORY-0003]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0003
decisions: [D4]
group: A
---

# Problem / Context

ADR-0003/D4 requires the sequencer's definition and advance scripts resolved from a pinned out-of-tree copy, with their in-repo sources under trusted_base as the merge-time backstop; the profile check that watches this is the ADR-0002/D3.2 court extended one path set.

Grounding: `docs/adrs/ADR-0003-sequencer-obligations.md`, D4. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

Extend STORY-0003's profile schema and integrity check to the sequencer-definition and advance-script paths; document the pinned layout beside the postcondition loader's.

# Scope and non-goals

In scope:

- the path-set extension and its check cases

Out of scope:

- the profile base (STORY-0003), the loader (STORY-0004)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] a profile omitting the sequencer's definition path fails the profile check—verified by `the extended check's known-bad fixture`
- [ ] the pinned `--agents` payload is the sole definition source: the judged tree carries no agent-definition directory at all, asserted from the filesystem rather than inferred, and any definition found there is a finding whether or not it shares a name with a pinned one—verified by `a check case planting a definition under the judged tree's agent directory, both same-named and differently-named, and asserting the finding in each`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: the backstop mistaken for the mechanism again—the pinned copy is the mechanism—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- The one-source rule is `docs/probe/D7-headless-probe-2026-08-12.md`, read at its CORRECTION
  rather than at its first draft. Leg 2 as first written—two sources, the repo file's followed—was
  confounded: the repo file and the invoking prompt carried the same instruction, so nothing
  separated them. Leg 3 discriminates, with the repo definition removed and a neutral prompt: the
  pinned payload's instruction executed. The corrected rule is three-part, and only the first part
  is this story's, because only it is a check over the judged tree—the judged tree carries no
  agent-definition directory at all. The other two are the invocation's: the wrapper fails closed
  on a missing pinned type, which STORY-0005 carries, and the invoking prompt carries
  spawn-by-name only and never phase instructions, which is a phase-brief content rule noted
  there. Same-named is the wrong test on its own: leg 1 measured the wrapper's main agent
  improvising a substitute brief FROM THE JUDGED TREE when the pinned type did not resolve, so a
  differently-named definition sitting there is material too.

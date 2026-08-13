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
- [ ] the pinned `--agents` payload is the sole definition source: the judged tree carries no agent-definition directory at all, asserted from the filesystem rather than inferred, and any definition found there is a finding whether or not it shares a name with a pinned one—verified by `a check case asserting the judged tree has no agent-definition directory, with an empty directory a finding and a populated one a finding`

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
  there. Directory absence rather than name collision is the test, and leg 1 is why the route
  exists rather than why the name is irrelevant. Leg 1 carried no `--agents` payload at all: the
  repo-level definition was not registered in headless `-p` mode, `Agent(subagent_type: ...)`
  failed with "not found", and the wrapper's main agent then improvised a substitute brief FROM
  THE JUDGED TREE—ADR-0001/D3's defect reached by initiative inside the wrapper. What that
  measures is that a definition sitting in the judged tree is reachable material for the wrapper.
  It does NOT measure that a differently-named one would be read; that substitute came from the
  same-named file. Absence is therefore the fail-closed rule, chosen because the tree-read route
  is measured, not because breadth beyond it was.

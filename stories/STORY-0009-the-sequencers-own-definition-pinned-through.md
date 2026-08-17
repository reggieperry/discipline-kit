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

- [x] a profile omitting the sequencer's definition path fails the profile check—verified by `the extended check's known-bad fixture`: `missing-sequencer-sources` in `harness/fixtures/profile_check_test.py`, red-first (the unextended court read its tree clean, exit 0), now exit 1 naming `harness/chain/`. The omission the court can see is the one D4's falsification condition names—a `trusted_base` omitting the sequencer's in-repo sources—because the PINNED path is derived, not declared: see the key-shape note below
- [x] the pinned `--agents` payload is the sole definition source: the judged tree carries no agent-definition directory at all, asserted from the filesystem rather than inferred, and any definition found there is a finding whether or not it shares a name with a pinned one—verified by `a check case asserting the judged tree has no agent-definition directory, with an empty directory a finding and a populated one a finding`: the populated arm is STORY-0012's `agents-dir-known-bad-2`, the empty arm is this story's `agents-dir-empty-known-bad-2`, both in `harness/fixtures/invoke_test.py`; the mechanism is one presence read (`invoke.refuse_agents_directory`), so name-sharing is structurally irrelevant. The audit and the mapping are the discharge record below

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [x] The assertion count is not reduced versus the merge-base. Net adds only: `profile_check_test.py` 20 to 22 cases, `invoke_test.py` 29 to 30, `core_test.py` 58 to 60; no case, marker or state assertion removed anywhere.
- [x] No new suppressions are introduced versus the merge-base. The diff adds no marker of any kind; the six pre-existing `# noqa: E402` lines in the touched modules (two in `core.py`, four in `invoke.py`) are untouched.
- [x] No new skipped tests versus the merge-base. No fixture has a skip mechanism and every case runs on every invocation.

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
- The key shape, decided 2026-08-13: the pinned sequencer definition is DERIVED under
  `pinned_root` at `<pinned_root>/sequencer/`, not its own profile key. Grounds: every kind of
  pinned material is already composed under the root by a fixed name and none is keyed—the
  loader's `postconditions/`, the invocation layer's `briefs/`, `settings/` and `worktrees/`—and
  the profile's own `pinned_root` comment already reads "one root with several kinds of material
  under it". A first key for one kind would make that kind's location configurable while every
  other stays fixed, and STORY-0012's notes had already deferred a worktree-relocation key as
  schema-block work. Because the pinned path is derived, a profile cannot omit IT; what a profile
  can omit is D4's in-repo half, which is exactly the falsification condition ADR-0003 wrote
  ("a profile whose `trusted_base` omits the sequencer's definition path or the advance
  scripts"), so the court extension lands there. No schema key was added, so `core.py startup`'s
  validation is untouched and every existing court stays green; the layout is documented beside
  the loader's in `harness/chain/loader.py`, and the schema's comment block
  (`.claude/chain/profile.toml`) records the no-key decision.

# Discharge record

Criterion 2 closed audit-first, 2026-08-13, the STORY-0011 pattern: STORY-0012 had already built
most of the mechanism, so the deliverable is the mapping plus the one missing arm, never a
duplicate mechanism. What the audit found in `invoke.refuse_agents_directory`
(`harness/chain/invoke.py`) and its fixtures:

- the criterion's read is EXISTING: presence asserted from the filesystem (`found.exists()`),
  content never read—so an empty directory fires, a populated one fires, and name-sharing with a
  pinned definition cannot matter structurally. Fires on the judged tree AND the workspace, in
  both `compose`/`build` and `run` paths.
- the populated arm's case is EXISTING: `agents-dir-known-bad-2` (STORY-0012), which plants a
  populated `.claude/agents/` in the judged tree and asserts exit 2, `agents-directory`, and the
  judged tree's own path in the message.
- the empty arm's case was MISSING, and the gap was live, not cosmetic: the contents-keyed
  rewrite (`is_dir() and any(iterdir())` for `exists()`) survived the whole pre-existing
  suite—the populated known-bad still fired and every clean compose case still passed. Built
  here as `agents-dir-empty-known-bad-2`: an empty `.claude/agents/` in the judged tree reads
  exit 2 naming `agents-directory` and the judged tree's path. Red evidence is the mutation run
  (the case is the only one that fails under the contents-keyed mutant); against the real
  mechanism it passes immediately, which is the audit's point.
- discrimination, mapped: the contents-keyed mutant is killed only by the new empty case; the
  inverted mutant is killed by every clean compose case (STORY-0012's finding) and now ALSO by
  both known-bad cases directly, because their judged-tree path assertion catches the refusal
  naming the wrong tree.

Scope held to the Notes' one-source split: the wrapper's missing-pinned-type refusal is
STORY-0005's, the spawn-by-name prompt rule is a phase-brief content rule, and neither is
re-checked here.

Criterion 1's build, same date: `scripts/profile-check.sh` gains ADR-0003/D4's path set
(`SEQUENCER_SOURCES = ("harness/chain/",)`, the directory rather than a module list, since the
hand-kept list had measurably drifted), red-first by `missing-sequencer-sources`. The audit of
the run-time backstop it extends then found `core.py`'s `SEQUENCER_SOURCES` two modules short of
the live directory—`invoke.py` (STORY-0012) and `receipt.py` (STORY-0008) shipped without
joining it, where STORY-0007 had added `merge.py`—so a trusted_base omitting either started the
sequencer cleanly. Closed red-first in `core_test.py`: `trusted-base-omits-invocation-sources-2`
(both omissions must be NAMED in the refusal, so either drifting back out fails the case) and
`sequencer-sources-complete` (the tuple held to the live `harness/chain/*.py` listing, so the
next module cannot ship outside the gate silently). STORY-0011's discharge record described the
tuple as it stood then; this entry supersedes its count without editing that record.

The merge review (MERGE_SAFE, one should-fix) found a seventh mutant SURVIVING: the court's D4
set narrowed to `("harness/chain/core.py",)` passed all 21 cases, because
`missing-sequencer-sources` asserts the bare substring "harness/chain/", which is a prefix of
every module path beneath it—the mutant's uncovered line "harness/chain/core.py" contains the
marker, so the directory shape was pinned in prose only, and a revert to the drift-prone
hand-kept form this story removed from `core.py` would have landed silently
(`core.py startup`'s per-module refusal still fails closed at run time, so a lost defense
layer, not an opened fail-open). Closed red-first, the mutant verified executing and the revert
cmp-verified: `sequencer-file-not-directory` covers `harness/chain/core.py` by name, omits the
directory, and asserts the exact uncovered line with its trailing newline—the sole kill under
the reviewer's mutant. The existing case's marker was left as-is: tightening it would duplicate
that kill, not strengthen it.

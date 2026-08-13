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

- [x] each phase runs as exactly one headless invocation whose prompt is composed from the
      pinned brief file and nothing else—verified by `the invocation-builder fixture comparing
      the composed prompt byte-for-byte against the pinned brief`: `prompt-byte-identical` in
      `harness/fixtures/invoke_test.py` composes against a brief carrying an em dash, quotes, a
      shell metacharacter and no trailing newline, and requires the emitted prompt equal to the
      brief's bytes exactly, so any decoration or relay fails it; the composed argv is the
      probe's measured invocation shape and nothing else, and the invoking prompt IS the brief,
      so it carries no spawn instruction the brief does not
- [x] a phase run with a decoy user-scope SessionStart hook shows no injected content in its
      transcript—verified by `the settings-pinning fixture (the per-invocation twin of
      STORY-0006's sequencer-level case, cross-referenced there)`: `settings-pinning-decoy`
      plants the decoy hook in the calling HOME's settings AND a decoy `CLAUDE_CONFIG_DIR`, and
      asserts the strongest mechanical facts a stubbed harness allows—the materialized
      project settings are byte-identical to the pinned file with no decoy content, the
      composed environment repoints HOME and CLAUDE_CONFIG_DIR into the required-empty
      sequencer-owned home with the decoy path in no decided value, and the argv carries no
      settings flag, which is unmeasured ground ADR-0004/D3 forbids relying on. The transcript
      half is a live-run residue, stated in the notes
- [x] a `.claude/agents/` directory in the judged tree at phase start is a named finding,
      absence asserted from the filesystem—verified by `the pre-phase assertion's known-bad
      fixture`: `agents-dir-known-bad-2` plants the directory and requires exit 2 naming
      `agents-directory`; the assertion runs against the judged tree and the workspace both,
      and every clean compose case pins the passing half
- [x] an attest-only phase runs in a sequencer-created worktree outside the parent, removed
      after the seam, with porcelain empty in BOTH trees at the seam (the parent, and the
      worktree the phase ran in, per ADR-0003/D6's every-seam rule)—verified by `the
      worktree-custody fixture, including STORY-0005's live-worktree porcelain case`:
      `worktree-outside-parent-0` (the composed path under the pinned root, registered,
      demonstrably outside the parent—a path inside it is unreachable past `core.owned`'s
      working-tree condition), `worktree-live-porcelain-0` (both porcelain reads pass with the
      worktree live and the fence armed, the half STORY-0005's seam could not see),
      `seam-dirt-in-worktree-2` and `seam-dirt-in-parent-2` (either tree's dirt is a named
      refusal), and `seam-close-removes-0` (removed and unregistered after the seam)
- [x] a dead or compaction-marked phase is re-run under a fresh attempt with the pinned
      worktree path cleared first—verified by `the fresh-attempt fixture killing a phase
      mid-run and asserting the retry succeeds at the same pinned path`:
      `phase-death-fresh-attempt` runs a stub harness that dies mid-phase leaving an in-phase
      stream and a dirty corpse at the pinned path, requires the death named, then re-runs the
      same invocation and requires it to succeed at the same composed path with the corpse
      cleared first and no resume-shaped flag in either logged argv; `phase-compaction-death`
      pins that a compaction record reads as death even when a result record follows, and
      `resume-liveness-compacted` pins the liveness word at the one admitted reader
- [x] no phase can spawn a subagent, and no advancement-path source consumes a wrapper
      return string or depends on --resume—verified by `the D5 grep-shaped source check, one
      pattern wider, plus the post-batch transcript audit flagging any task-start event in a
      phase transcript`: the ninth pattern is `session-continue` (`--continue`,
      `--fork-session`)—the eight existing patterns already catch the wrapper's return text
      and the literal `--resume`, and what D1/D4 name that they miss is resumption wearing
      another flag—planted red in `core_test.py`'s `source-session-continue`; the check
      passes over the live five-module corpus with denominators printed.
      `harness/transcript_audit.py` scans phase stream JSONL for any `task_`-prefixed subtype
      (parser grounded in the probe's retained `task_started` record), audit not control flow,
      demonstrated red and green on synthetic streams by the four `audit-*` cases
- [x] a harness version differing from the profile's pin re-runs the extended probe before
      any phase—verified by `the version-gate fixture`: `version-mismatch-2` is the known-bad
      (a stub reporting 2.1.300 against the 2.1.224 pin reads exit 2, naming both versions and
      demanding the extended D7 probe), with `version-unpinned-2`, `version-unreadable-2` and
      `version-match-0` pinning the unpinned, unreadable and passing arms; the version is read
      through the same injectable command seam the spawn uses, and the gate runs first in
      every compose and run

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [x] The assertion count is not reduced versus the merge-base. Every existing fixture is
      untouched except `core_test.py`, which is a net add of one case (56 to 57);
      `invoke_test.py` is a net add of 26 cases, and `scripts/check.sh` gains one invocation
      and loses none.
- [x] No new suppressions are introduced versus the merge-base, with the same disclosure
      STORY-0006 made: `invoke.py` carries four `# noqa: E402` markers on its `sys.path`
      import lines, copied verbatim from the identical shape in `core.py`, `advance.py` and
      `attempt.py`. No linter on the commit path reads them; they are named because a marker
      nobody reads is still a marker.
- [x] No new skipped tests versus the merge-base. Neither fixture has a skip mechanism and
      every case runs on every invocation.

# Risks and rollback

- Risk: settings-source pinning drifts across harness releases—mitigation: the version gate
  re-runs the probe before trusting a new binary.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by ADR-0004's landing commit; the coverage gate requires this story in the same
  commit as the record it covers.
- The decoy criterion's transcript half is a live-run residue: no stub can show a real
  transcript free of injected hook content, so the fixture establishes the composition facts
  (materialized bytes, environment repointing, no unmeasured settings flag) and the live
  demonstration belongs to the separately gated smoke, not to this story's fixtures.
- The transcript-audit court is off the commit path until a batch writes phase transcripts: an
  empty corpus reads could-not-run, never clean, and no chain has run on any machine here.
  `invoke_test.py` is its red-and-green demonstration meanwhile; wiring the tool itself is
  recorded in `scripts/check.sh` beside the source check.
- "Fresh attempt" here is a fresh invocation at the same composed path, cleared first under
  `core.clear_owned`'s authority—never a resume. Whether the operator also takes a
  story-level attempt number (`core.py start-attempt`) is the driver's decision; both routes
  clear before they create.
- Phase worktrees and their isolated homes compose under `<pinned_root>/worktrees/`. The
  hardening checklist that will one day root-own the pinned root must leave that subtree
  sequencer-writable, or relocate it; no machine has run the checklist, so the tension is
  disclosed in `invoke.py`'s docstring rather than resolved here.
- A mutation-pass finding worth keeping: an inverted agents-directory assertion is NOT killed
  by the known-bad case alone—the workspace arm raises the same marker, so exit and marker
  both match—it is killed by every clean compose case refusing. The known-bad fixture
  demonstrates the finding fires; the clean cases carry the discrimination.
- `ci.yml` is untouched (its partial mirror of `check.sh` is a recorded follow-up under
  STORY-0003's entry); the new fixture rides `check.sh` only.
- The adversarial merge review's three findings are closed red-first: a COMMITTED
  `.claude/settings.local.json` is a tree-supplied project-scope settings source porcelain
  never names (tracked files read clean), refused from the filesystem before each phase like
  the agents directory (`settings-local-known-bad-2`); a `--version` printing invalid UTF-8
  escaped as an exception and exited 1, the one verdict-shaped code this layer must not
  produce, now read with replacement and pinned (`version-invalid-utf8-2`); and `seam-close`
  over a still-live fence destroyed the tamper evidence `seam-check` exists to name, now a
  `seam-not-checked` refusal with the worktree and fence preserved (`seam-close-unchecked-2`).
- The driver story must inherit ADR-0004/D4's letter explicitly—a dead phase is re-run under a
  NEW attempt—so this module's ability to re-invoke at the same attempt path is capability,
  not license: the driver decides the attempt number, and nothing here writes one.
- Follow-up recorded rather than taken (reviewer-recommended, optional): relocate phase
  worktrees OUT of `pinned_root` via an optional profile key with a sibling default, since the
  phase's cwd currently sits inside the pinned root's subtree with the examiner at `../../..`.
  Taking it properly means documenting the new key in the profile's schema block, which is
  beyond this story's containment (invoke.py and its fixtures), so it is recorded here for the
  driver or a hygiene slice.
- Recorded by STORY-0005's merge review, and owed here: the seam reads `git status --porcelain` in
  the ONE repository it was pointed at, and under ADR-0004/D2 an attest-only phase runs in a
  sequencer-owned worktree while the primary tree carries the story's commits. Both trees are live
  at that moment and only one is read, so the porcelain obligation of ADR-0003/D6 is met for the
  graded tree and unwatched for the other. Which tree the seam is pointed at, and whether the
  other one is checked at all, is decided by whatever composes the invocation—this story—rather
  than by the seam, which cannot know a worktree exists that it was not told about. STORY-0005's
  fixture pins both halves it can see: a worktree outside the parent leaves porcelain empty, and
  one inside the parent reads could-not-run.

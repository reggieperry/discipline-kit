# The first end-to-end walk, run 2026-08-14

The chain's first live run: two headless phases under the pinned invocation layer, the advance
seam writing real phase refs, and the merge stage evaluating all eight conjuncts before a
merge-local act advanced a dedicated clone's `main` by compare-and-swap. Harness 2.1.224—the
profile's pin, unchanged since the D7 probe—so the version gate passed without the extended
re-probe. Every stage ran the shipped CLIs unmodified; the operator acted as the sequencer,
driving them in ADR-0003's order, because the sequencer script does not exist yet.

## Setup

- **Pinned root** `/var/lib/discipline-chain/` provisioned per the layout the modules compose:
  `postconditions/` (walk-artifact; receipt-complete), `briefs/`, `settings/settings.json` (the
  ADR-0004/D3 spawn denial lives in the pinned bytes—invoke copies and verifies nothing),
  `rules/` (57 pinned, 53 receipt-owed), `worktrees/`, `records/`, `sequencer/`.
- **The dedicated clone**: a local-path clone with the origin remote then removed entirely—zero
  remotes, so a push from any actor has nowhere to go—profile flipped to
  `terminal = "merge-local"`, `push = "never"` (the exact pairing the courts require), and
  repo-local git identity with signing off, because the phases' repointed HOME hides all global
  git config.
- **The receipt-complete wrapper** (owed by STORY-0007's merge review) now exists as pinned
  material: one positional tree argument in, the receipt court's exit passed straight through.
  The in-tree receipt convention it fixes is `chain/receipt.txt`. Its green fixture pins the
  current 53-rule owed set and goes stale fail-closed: a rules regrade voids every merge at the
  demonstration until the fixture is regenerated.
- A pre-flight adversarial verification (GO) measured the commit-path suite green in 53 s inside
  a scratch worktree, confirmed the linked-worktree traps closed in the courts, and added two
  spend guards: this driving session's own `CLAUDE_CODE_*` variables scrubbed from the phase
  spawns, and a wide phase-2 timeout.

## The walk, as executed

| Step | Act | Observed |
|---|---|---|
| P1 | `invoke.py run` (phase 1, build) | gate pass; refusals pass; worktree detached at main; fence 57 bytes byte-identical; live `claude -p` from the 985-byte brief; liveness complete, 8 records |
| P2 | `seam-check` | fence verified and consumed; porcelain empty in both trees |
| P3 | harvest | worktree HEAD parent = main; `story/W1` created at the phase commit |
| P4-P5 | `seam-close`; checkout `story/W1` | worktree removed; main no longer checked out |
| P6 | `advance` phase 1, walk-artifact | demonstrated green 0 / red 1; seam exit 0 reads pass; `refs/chain/W1/attempt-1/phase-1` recorded and read back |
| P7 | `invoke.py run` (phase 2, review) | fresh worktree at the same composed path, detached at the story tip; liveness complete, 35 records |
| P8 | seam, harvest by `merge --ff-only` | 53-line receipt committed alone; fence untouched |
| P9 | `advance` phase 2, receipt-complete | the real court inside the seam: covered 53 of 53, PASS; phase-2 ref recorded |
| P10 | `core.py position` | attempt 1 phase 2, zero findings |
| P11 | `merge.py merge` | all eight conjuncts pass; `merge_ok: true`; merge-local CAS advanced the clone's main to the trial commit, `Merged-Story: W1`; record written |
| Post | `transcript_audit.py`; revert sanity | audit clean, no spawn event in 43 records; `revert -m 1` restores the pre-merge tree |

The record at `records/W1/merge-1.record` carries the eight per-conjunct receipt lines with
sources, exactly two testimony lines, the verbatim forged-ref residue with the merge-local blast
radius, and the six not-established lines.

## Findings

1. **The chain works end to end at 2.1.224.** Both live phases followed their briefs exactly:
   single-file commits, the fence left uncommitted, and phase 2 iterated its receipt against the
   real court to 53/53 before committing. The conjunct-1 suite ran green inside the merged-tree
   scratch, and conjunct 8's tree OID held through every link.
2. **Stream naming and the transcript audit are coupled only by convention.** `--stream` names
   are caller-chosen; the audit globs `*.jsonl`. The walk's `.stream` names made the audit VOID
   loudly ("an empty corpus is the wrong place, not a clean one")—the fail-closed arm doing its
   job—until the streams were copied under `.jsonl` names. The sequencer script must encode the
   `.jsonl` convention; until it exists this is operator discipline.
3. **The driver-harvest pattern is real and owed to the sequencer story.** There is no story
   branch in the invocation layer: phase commits land on the worktree's detached HEAD, and the
   driver anchors them (`git branch` for the first, `merge --ff-only` after) before seam-close
   clears the worktree. Ordering matters twice: harvest after seam-check but before seam-close,
   and never move a checked-out branch by `update-ref`.
4. **Repointed HOME hides all global git config.** Phase commits need repo-local identity in the
   judged repo, and a machine with global `commit.gpgsign` would otherwise fail phase commits.
   One hardening-checklist line: set repo-local identity (and signing off) in every dedicated
   clone.
5. **The spawn-denial bound is honest, not proven.** The audit found no spawn event in either
   transcript, but neither phase had a reason to spawn; whether the pinned deny rules would stop
   an attempt is unmeasured—the D5 extended probe's limb, unchanged.
6. **Session-environment hygiene matters when the driver is itself a harness session.** The
   phases inherit-and-patch the driver's environment; `CLAUDE_CODE_*` variables from the driving
   session were scrubbed at spawn as an unmeasured-risk guard. The sequencer should do the same.
7. **Live spend was small**: two short phases, 43 stream records total, everything else
   mechanical.

## What this walk did not establish

The unattended envelope (cron start, locking, budget)—the owed record it always was; the
spawn-denial and compaction limbs of the D5 extended probe; out-of-tree pinning of the sequencer
code itself (the wrapper execs the kit checkout's `receipt.py`; `sequencer/` remains layout);
and open-pr's forge path, untouched here by posture.

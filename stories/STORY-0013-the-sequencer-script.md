---
id: STORY-0013
title: Build the sequencer script—one pinned driver from start-attempt to the terminal act
deps: [STORY-0006, STORY-0007, STORY-0012]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0003
decisions: [D4, D6]
group: A
---

# Problem / Context

Every stage of the chain exists and the first end-to-end walk succeeded—driven by hand. The
operator acted as the sequencer, invoking the pinned CLIs in ADR-0003's order and carrying four
conventions from memory that no code encodes. A sequence that lives in an operator's head is the
defect class this kit exists to remove: the next hand-driven run re-derives the ordering, and any
slip lands on a fail-closed refusal at best and a wasted live phase at worst.

Grounding against HEAD:

- `harness/chain/invoke.py:71–88`—the six invocation acts exist as separate CLI entries; nothing
  chains gate → run → seam-check → seam-close, and nothing owns the ordering between them.
- `harness/chain/core.py:112–120`—`SEQUENCER_SOURCES` names seven modules; the driver that
  ADR-0004/D1 calls "the pinned sequencer" is not among them because it does not exist.
- `harness/chain/loader.py:28`—the pinned home `<pinned_root>/sequencer/` is documented layout
  with nothing resolving from it, per STORY-0009's honest status.
- `harness/transcript_audit.py:103`—the audit rglobs `*.jsonl`, while `invoke.py run --stream`
  names are caller-chosen; the walk's `.stream` names made the audit VOID until the streams were
  copied under `.jsonl` names (`docs/probe/first-walk-2026-08-14.md`, finding 2).
- `docs/probe/first-walk-2026-08-14.md`, findings 3, 4, and 6—the driver-harvest pattern (anchor
  the detached worktree commit after seam-check, before seam-close; fast-forward thereafter;
  never `update-ref` a checked-out branch), the repo-local git identity precondition under
  repointed HOME, and the `CLAUDE_CODE_*` environment scrub are all operator discipline today.

# Proposed approach

One new module, `harness/chain/sequencer.py`, in the style of its seven siblings: argparse acts,
`CouldNotRun`, scrubbed-env git, an injectable `--harness` seam so fixtures never touch the real
binary. It composes the acts the walk exercised, in the walk's order:

- **`run`**—the whole story: `core.py startup` posture, the repo-local-identity precondition,
  `start-attempt`, then per phase: `invoke.py run` (with the session-environment scrub applied to
  the spawn), `seam-check`, the harvest (create or fast-forward `refs/heads/story/<id>` from the
  worktree HEAD—after seam-check, before seam-close), `seam-close`, checkout, `advance.py`; then
  `position`, the merge stage, and the post-batch transcript audit—reported, never deciding
  advancement, per ADR-0001/D5's audit-not-control-flow shape.
- Streams are composed, not accepted: `<pinned_root>/sequencer/streams/<story>/p<n>.jsonl`, so
  the audit's `*.jsonl` corpus exists by construction.
- The per-story phase table (phase → brief name, postcondition name) is pinned material composed
  by fixed name under the pinned root, following the convention every other material kind uses;
  the exact shape is the pre-build design pass's first question (Notes).
- Exit contract: 0 = the story ran to its terminal outcome; 1 = a story verdict surfaced
  (a phase FAIL or a merge park)—relayed verbatim from the deciding court, never decided here;
  2 = could-not-run anywhere, and the run stops at the first one.
- The reference pattern to mirror is `merge.py`'s body: cheap refusals first, one act dispatch,
  every subprocess through the scrubbed env.

# Scope and non-goals

In scope:

- the sequencer module, its fixture file, its `SEQUENCER_SOURCES` entry, and its check.sh wiring

Out of scope:

- the unattended-run envelope (cron start, locking, budget)—its own owed record, which this
  story is the precondition for, not the delivery of
- out-of-tree pinning of the sequencer code itself (`sequencer/` stays layout; the walk record
  names the gap)
- the open-pr terminal path beyond what merge.py already carries (the walk ran merge-local; no
  forge is invoked by any fixture)
- re-opening any decided ordering: the module encodes ADR-0003's order, it does not re-derive it

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] one invocation runs a two-phase story end to end against a stub harness—worktrees, fence,
      harvest, phase refs, merge evaluate, and the composed record all real—verified by `the
      sequencer fixture's walk-replay case, asserting the phase refs, the story branch, the
      advanced main, and the record's merge_ok line`
- [x] the four walk findings are encoded, not remembered: streams composed as `*.jsonl` under the
      pinned root; the harvest ordered after seam-check and before seam-close with a checked-out
      branch never moved by update-ref; the spawn environment scrubbed of the driving session's
      `CLAUDE_CODE_*` variables; a clone without repo-local identity refused by name at
      start-up—verified by `one fixture case per finding, each red-first (the decoy-env case
      plants CLAUDECODE and asserts the stub harness never sees it; the identity case asserts the
      could-not-run marker)`
- [x] a phase FAIL parks the run: advance exit 1 stops the sequence, no later phase spawns, no
      merge is attempted, and the sequencer's exit relays 1 with the seam's own words—verified by
      `the park-relay fixture case, asserting the stub for phase 2 was never invoked`
- [x] the transcript audit runs post-batch as audit, not control flow: a planted spawn event in a
      phase stream yields the audit's finding in the sequencer's output while refs already
      written stay written—verified by `the audit-report fixture case`
- [x] the sequencer joins the watched source set: `SEQUENCER_SOURCES` gains the module (the
      completeness case forces this), the D5 source check reads it clean over 8 modules, and no
      new admitted reader appears—verified by `core_test's sequencer-sources-complete and the
      source check's live run inside check.sh`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each
before hand-off:

- [x] The assertion count is not reduced versus the merge-base.
- [x] No new suppressions are introduced versus the merge-base.
- [x] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: the sequencer quietly becomes a second verdict authority (reading streams beyond the
  admitted reader, or deciding from a wrapper string)—mitigation: the D5 source check already
  scans every `harness/chain/*.py` for exactly these shapes, and the module must land clean
  under it; its exit-1 arm relays a court's verdict verbatim and is pinned by the park-relay
  case to never originate one.
- Risk: fixture stubs drift from the real harness's stream shape—mitigation: the stub emits the
  probe-grounded record shapes core.admitted_signals already parses, and the walk record is the
  measured reference.
- Rollback: revert the story's commits; every court named here fails closed on absence, and the
  hand-driven runbook in the walk record remains executable.

# Notes

- Grounded in `docs/probe/first-walk-2026-08-14.md` (the walk IS the spec's source ticket; its
  findings 2, 3, 4, and 6 become the second criterion) and in ADR-0004/D1's naming of "the
  pinned sequencer" as the driver.
- The walkthrough's "main loop drives" sites inherit their recorded correction with this build.
- Open question for the pre-build design pass (the STORY-0007 pattern): the per-story phase
  table's shape—one manifest file per story under the pinned root mapping phase number to
  (brief, postcondition), versus deriving it from brief-file naming alone. The design pass
  decides; the builder implements as decided.
- Open question: whether the sequencer's `run` act should also drive a single phase in isolation
  (a `phase` act) for bounce/re-walk workflows, or whether `bounce` plus a re-`run` from position
  covers it. The design pass decides.
- Intake score against the story-tighten rubric (self-scored at authoring): scope 2, out-of-scope
  2, criteria 2, reference pattern 2, verification 2, frontmatter 2—tight band; the two open
  questions above are design-pass inputs, not spec gaps, and are recorded here rather than
  silently repaired.

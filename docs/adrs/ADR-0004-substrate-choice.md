# ADR-0004: Each phase is its own headless invocation, and the sequencer owns the worktrees

**Status:** Proposed (2026-08-12).
Acceptance gate: deep-reason passes recorded in
[reviews/ADR-0004-deep-reason.md](reviews/ADR-0004-deep-reason.md).

## Context

ADR-0003 decided the sequencer's obligations and left the substrate open pending one
measurement (D7). The measurement ran and was itself audited: the probe record
(`docs/probe/D7-headless-probe-2026-08-12.md`, with its same-day correction section) is the
evidence this record stands on. What it established: the session properties hold headlessly
at 2.1.224—subagent spawning via `--agents`, worktree isolation, project-scope PreToolUse
hooks under bypass permissions—so every candidate remains *capable*, and the choice falls to
ADR-0003/D7's named criteria: disinterest of the looker, and bounded context.

Four candidates, not three. ADR-0003 enumerated an interactive main-loop session, bare
headless `-p` phases, and one-shot wrapper sessions each spawning a phase subagent; a fourth
exists that it did not name—a single long headless `-p` session driving all phases as
subagents—and it is enumerated here so the record does not decide a fork it never stated.

Three measured facts discriminate where the capability probe could not:

- **The wrapper is not disinterested.** Leg 1 measured the wrapper's own main agent, told its
  pinned type was missing, improvising: it substituted another agent type, granted isolation
  on its own initiative, and took the phase brief from the judged tree—ADR-0001/D3's
  judged-party-supplies-the-examiner, reached by initiative, inside the candidate substrate.
  A model layer between the sequencer and the phase is a judgment holder wherever it sits.
- **Worktree custody cannot rest on the harness.** The design's claim that agent worktrees
  are git-excluded is measured false at 2.1.224: the parent's porcelain shows
  `.claude/worktrees/`, which lands directly on ADR-0003/D6's porcelain-empty seam
  precondition. A worktree the sequencer creates itself, outside the parent, has neither
  problem.
- **The instruction channel must be single-source.** Leg 3 showed the pinned `--agents`
  definition governs only as the sole source, and the invoking prompt's relayed content
  overrides it. Under a subagent-spawning substrate the prompt and the definition are two
  channels to police; under a bare invocation the prompt is the one channel, and the
  sequencer composes it from the pinned brief.

## Decisions

### D1: The substrate is a bare headless invocation per phase, driven by the pinned sequencer

Each phase runs as its own `claude -p` invocation; the phase *is* that session's main agent.
No wrapper session, no persistent main loop, no subagent spawn on the advancement path. The
sequencer (the pinned script of ADR-0003/D2–D4) composes the invocation from pinned
material, waits for exit, and runs the seam per ADR-0001/D2. Disinterest holds with no
intermediary to trust; context is bounded at one phase per session with documented
main-session behavior; a dead phase is re-run under a fresh attempt rather than resumed.

### D2: Attest-only isolation is sequencer-owned worktrees, outside the parent

Where a phase must not touch the primary tree (tester, reviewer), the sequencer creates a
git worktree at a pinned location outside the parent repository, invokes the phase with that
working directory, and removes the worktree after the seam. The harness's agent-worktree
feature is not on the advancement path: its placement inside the parent and its measured
non-exclusion are ADR-0003/D6 violations waiting to happen, and custody of the judged tree
belongs to the thing that grades it.

### D3: Every phase invocation pins its settings sources and its brief

The invocation carries the sequencer's pinned settings as the only project source and
excludes user-scope sources entirely—the probe measured a user-scope SessionStart hook
injecting operator machine identity into phase transcripts, and a phase fence that the
phased agent's own tree can edit is no fence. The phase brief is composed from the pinned
brief file (ADR-0003/D4 material); the judged tree carries no `.claude/agents/` directory at
all, asserted from the filesystem before each phase, so no competing definition source
exists to be found or improvised from.

### D4: Mid-phase death is a fresh attempt, never a resume

A phase that dies mid-run is re-run under a new attempt per ADR-0001/D1's re-walk rule; the
sequencer never resumes a half-dead phase session. Session ids stay admitted for diagnosis
per ADR-0001/D5. `--resume` under headless invocation is unmeasured and nothing here may
come to depend on it without a probe first.

### D5: The enabling facts are version-scoped, and a harness bump re-runs the probe

Every enabling fact is scoped to the measured 2.1.224. A harness version change re-runs the
D7 probe extended with one limb per D1–D3 reliance (headless completion behavior, worktree
creation from a pinned path, settings-source pinning taking effect). A future harness
restoring repo-level agent registration does not reopen this choice—it tightens D3's
no-agents-directory assertion, since judged-tree definitions would become live again.

## Consequences

- The walkthrough's substrate assertion ("the main loop drives") retires: the pinned
  sequencer drives, and phases are sessions. What survives, reworded, is its true half—the
  merge stage is not an agent, it is the sequencer's (ADR-0002/D1). The surfaces table and
  Stage D prose inherit the correction with the sequencer build.
- ADR-0003/D7 is fulfilled, not superseded: this is the successor record its closure clause
  names, and D1–D6 of ADR-0003 bind this substrate unchanged.
- The `agent_type`-keyed PreToolUse fence the design sketched for attest-only phases is
  replaced: with no subagent on the advancement path, the fence is the per-invocation pinned
  settings hooks of D3, which fire under bypass permissions by measurement.
- The unattended-run envelope (cron start, per-story locking, concurrency to a recorded
  budget) remains the owed record it always was; this record deliberately does not decide
  it. Prior prose reserved the name "ADR-0004" for it informally; this record takes the id
  per the registry's next-free rule, and the five informal references are rewritten in this
  commit to name the envelope record without a number.
- STORY-0012 (the pinned phase invocation) carries this record's build obligations; the
  coverage gate forces it into this same commit, which is that gate doing its job.

## Alternatives

- **The interactive main-loop session as sequencer** (the walkthrough's assertion): a model
  that has read every phase's output before deciding advancement—the self-report defect
  relocated—and the system's longest-lived context, with no stated overflow behavior.
  Rejected on both D7 criteria.
- **A single long headless session driving all phases** (the fourth candidate, enumerated
  here): inherits both main-loop defects without the interactive operator's oversight.
  Rejected on both criteria, stated so the fork is decided as enumerated.
- **One-shot wrapper sessions spawning one phase subagent each** (this record's own
  pre-draft hypothesis): keeps every verified session property, but the wrapper is a model
  layer holding judgment on the advancement path—measured improvising a brief from the
  judged tree when its pinned type was missing—and it keeps the subagent context-overflow
  hole open while doubling the instruction channels to police. Its one distinct purchase,
  the `agent_type`-keyed fence, is replaced by D3's per-invocation settings hooks. Rejected
  as dominated once the fence is re-homed.
- **Harness-managed agent worktrees for isolation** (under any substrate): placement inside
  the parent plus measured non-exclusion breaks the porcelain-empty seam; custody moves to
  the sequencer (D2).
- **Relying on ADR-0003's Alternatives paragraph that called bare `-p` "dominated"**: that
  paragraph predates the measurement and its stated reason (losing the worktree handoff) is
  answered by D2. The contradiction between it and D7's open fork is adjudicated here in
  D7's favor: the measurement governs, and this record is its named successor.

## Falsification condition

Per decision, courts named honestly—future checks are future, unwatched conditions read as
unwatched:

- **D1**: a phase executed as a subagent, or any wrapper return string consumed on an
  advancement path. Court: the D5 grep-shaped source check of ADR-0001 (STORY-0006), one
  pattern wider—future, named in STORY-0012.
- **D2**: a seam evaluation with a worktree present inside the parent, or an attest-only
  phase run in the primary tree. Court: STORY-0005's porcelain fixture gains a required
  live-worktree case; the worktree-custody fixture lands with STORY-0012—future.
- **D3**: a phase run whose settings sources include user scope, or a `.claude/agents/`
  directory present in the judged tree at phase start. Court: the pre-phase filesystem
  assertion plus an invocation-audit fixture with a decoy user-scope hook, both in
  STORY-0012—future; until then the probe record's measurement is the standing observation.
- **D4**: any advancement-path dependence on `--resume`. Court: the same source check as
  D1's—future.
- **D5**: a harness version change without the probe re-run, or a probe FAIL on any relied
  limb without this record reopening. Court: not mechanical—a version pin recorded in the
  chain profile with review on change; stated as review-watched, per the honest form.

## Cross-references

- Supersedes: None. Fulfills [ADR-0003](ADR-0003-sequencer-obligations.md)/D7 as its named
  successor; every obligation of ADR-0003 D1–D6 binds this substrate. Builds on
  [ADR-0001](ADR-0001-advancement-re-derived.md) and
  [ADR-0002](ADR-0002-merge-posture.md), both Accepted.
- Superseded by: None.
- Related: `docs/probe/D7-headless-probe-2026-08-12.md` (the measurement and its
  correction—the evidence throughout); `stories/STORY-0012-the-pinned-phase-invocation.md`
  (the build obligations); the owed unattended-run-envelope record (unnumbered until
  allocated); the owed containment-posture record (the forged-ref closure and the fence
  posture beyond D3's hooks).

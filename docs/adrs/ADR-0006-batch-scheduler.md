# ADR-0006: The batch scheduler—DAG-driven clone topology, N merge-ready candidates, no join

**Status:** Proposed (2026-08-15).
Pre-draft acceptance gate: one deep-reason pass, recorded in
[reviews/ADR-0006-deep-reason.md](reviews/ADR-0006-deep-reason.md), which found the proposed central
decision a category error and reset the spine from a compare-and-swap serial integration to
DAG-driven clone topology. A five-lens committee informs the record and is cited as an input.
Acceptance is the operator's.

## Context

The chain runs one story per `sequencer.py run`, and STORY-0016's envelope runs one story
unattended behind the hardening gate. The operator asked what it would take to run a PLANNED SET
of stories with declared inter-story dependencies—a DAG—unattended, in parallel where the DAG
allows and sequentially where a dependency forces it, for quicker completion of the whole set.

A five-lens committee established the shape of the answer, and a pre-draft deep-reason pass
corrected it against the code. Both findings are the ground this record stands on:

- **The throughput win is story concurrency, not phase parallelism.** Within one story the phases
  are a data-dependency chain—each grades the prior's committed tree—so intra-story phase
  parallelism has an Amdahl ceiling near 1.2x and is not clean (it re-founds the ff-only harvest,
  the single-final-ref merge pinning, and the contiguous-position model). It is a rejected
  alternative here. The parallelism that pays is across independent stories, near-linear in the
  ready-set breadth; depth is irreducible (a dependent story cannot start until its dependency's
  result exists).
- **Serial integration by compare-and-swap is a category error.** conjunct 7's CAS re-resolves
  `refs/heads/main` and swaps in one clone; it does no cross-story work. Two stories cannot share
  one clone concurrently—the sequencer drives the clone's single HEAD, index, and working tree
  (checkout the story branch, `merge --ff-only` the harvest), so concurrent walks corrupt each
  other. Independent stories therefore run in SEPARATE clones, each with its own `main`, and one
  story's merge never moves another's `main`, so the CAS never fires across stories. What
  serializes integration is clone topology driven by the DAG, not the CAS.
- **The honest product is N merge-ready candidates, not one joined tree.** The design doc's own
  ask is "merge-ready branches", plural; `story-tighten` already requires parallel children to be
  file-disjoint (a shared-hot-file pair is a predecessor-first edge, not a parallel pair); and
  under the kit's own open-pr posture a batch is N PRs whose integration is ADR-0002's existing
  operator-side merge rules. A single integrated candidate is an optional merge-local extra that
  costs a real join and a whole-batch review.
- **Unattended is gated on the hardening, and the profile is unmeasured.** ADR-0005/D2 refuses
  unattended operation until the host is hardened; the start gate enforces it. And the per-phase
  wall-clock profile the whole premise rests on has never been measured.

This record decides the batch scheduler on that corrected ground.

## Decisions

### D1: The batch scheduler is a new layer above the per-story runner; it owns clone topology and merge-retry orchestration, and adds no new graded logic

The scheduler reads the planned set and its DAG and launches per-story runs; it reuses `merge.py`'s
eight conjuncts unchanged and STORY-0016's per-launch gate, lock, and integrity check unchanged. It
does not touch the graded core—no new phase-grading, no change to the position model, the harvest,
or the merge conjuncts. What it owns is above that core: the assignment of stories to clones (D2),
the ready frontier over the DAG, the batch-level concurrency ceiling and spend budget (D5), and—only
where a cheap re-merge is wanted—the direct `merge.py merge` retry loop the sequencer's own `run`
does not expose (its `run` concludes an attempt on a merge park and would force a whole-story
re-spend). The scheduler is orchestration; the grading stays exactly where it is.

Covered-by: none—owed to the batch-scheduler story, not yet written; the scheduler reuses the graded core it schedules over, so nothing in that core is built here.

### D2: Concurrency is serialized by DAG-driven clone topology, not by a compare-and-swap on a shared main

Independent stories (no dependency edge, and file-disjoint per D4) run in SEPARATE dedicated clones
and produce N independent merge-ready candidates. There is no shared integration `main` to swap
into, and no join. A dependency edge is served one of two ways, both without a cross-story CAS:
same-clone-serial—the dependency's terminal act advances that clone's `main`, and the dependent's
phase-1 worktree is cut from the post-dependency tip—or a seeded clone whose base already carries
the dependency's result. In either the CAS is trivial, because nothing races. The within-clone CAS
(conjunct 7) keeps exactly its existing job: protecting a single clone against a re-invocation of
the same story and against a phase forging refs. It is not, and was never, cross-story
serialization; treating it as such was the category error the pre-draft gate caught.

Covered-by: none—owed to the batch-scheduler story; it is the topology the scheduler implements, built on the existing per-clone merge unchanged.

### D3: The batch's product is N merge-ready candidates crossed per-story, per terminal posture

The scheduler produces one merge-ready candidate per story, and crossing each to the real trunk
stays the operator's act, per candidate—not a whole-batch merge:

- under `open-pr` (the kit's own public target, ADR-0002/D2): N pull requests, whose integration is
  the operator's existing PR-merge rules—the batch adds no new integration mechanism, and the
  crossing is exactly ADR-0002's stated throughput bound;
- under `merge-local`: N per-clone `main`s, each a cherry-pick candidate the operator transplants.

A single integrated candidate—one combined tree the operator reviews and crosses once—is an
OPTIONAL merge-local extra, and it is the only case that costs a real new join (a merge of N
per-clone results with conflict handling) plus a whole-batch review. It is not the default, because
the default that survives the code is N candidates.

Covered-by: none—owed to the batch-scheduler story; it records the product per posture and inherits ADR-0002's crossing unchanged.

### D4: The parallel frontier must be file-disjoint, checked before launch; a runtime conflict is a fail-closed backstop

The scheduler refuses to launch two stories concurrently if their declared changed paths overlap.
Overlap is read pre-launch from the stories' own declarations (the plan path lists and
`sensitive_files`), and a same-file pair is treated as a dependency edge (predecessor-first), never
a parallel pair—`story-tighten` already holds this rule for a decomposition, and the scheduler
enforces it for an execution. A merge conflict that nonetheless reaches integration is a fail-closed
park (re-integration against the current tip, or escalation), never a silent drop. The residual is
disclosed: file-disjoint stories can still interact BEHAVIORALLY, and the only court for that is the
merged-tree commit-path check the merge stage already runs—as good as the repository's own tests,
generic to all merging, not specific to the batch.

Covered-by: none—owed to the batch-scheduler story; the pre-launch disjointness matrix is its check, the runtime park reuses the merge stage's existing conflict handling.

### D5: The batch is fail-closed and unattended-gated, with a batch-level concurrency ceiling and spend budget derived from a measured token rate

Every per-story launch inherits STORY-0016's start-gate invocation and gate-integrity precheck
unchanged, so the batch refuses on an unhardened host exactly as a single unattended run does. On
top of the envelope's PER-STORY lock and meter—which bound duplicate runs of one story and nothing
more—the scheduler adds a BATCH-level concurrency ceiling (how many stories run at once) and a batch
spend budget, the ceiling ADR-0003 and ADR-0004 already anticipate and the per-story envelope does
not provide. The concurrency ceiling is derived from a measured tokens-per-minute budget, never a
story count—the model tier's rate is looked up, not guessed—so the batch paces to the account's real
throughput rather than saturating it.

Covered-by: none—owed to the batch-scheduler story; the batch concurrency ceiling and budget are new, the per-launch gate/lock/integrity are STORY-0016's, reused.

### D6: The scheduler may be built ahead of the hardening, gate-enforced at runtime, and its throughput claim is measured before it is relied on

Like the envelope (ADR-0005/D7), the scheduler may be specified and built ahead of the hardening,
because its runtime enforcement of the start gate keeps the refused configuration refused: a built
scheduler on an unhardened host refuses to run, and build-and-test runs against fixtures and stubbed
gate results only, never a live unattended batch. And because the whole premise—that story
concurrency completes a set quicker—rests on an UNMEASURED per-phase wall-clock profile, a
measure-first obligation is a precondition of relying on the scheduler for speed: record per-phase
and per-story wall-clock over a few real stories before the batch is trusted to be faster. A
scheduler that is built and correct is not yet a scheduler that is known to help.

Covered-by: none—owed to the batch-scheduler story and a measurement record; it records a build-ordering and a precondition and builds nothing here.

## Consequences

- Story concurrency is available in principle as N separate clones the operator can run today,
  attended, by hand; the scheduler automates the frontier, the gating, and the pacing, and is
  refused unattended until the hardening lands.
- The graded core is untouched, which is why this is clean where the phase-DAG was not: the
  scheduler schedules over `merge.py` and the sequencer unchanged.
- Integration is not free. Where a single integrated candidate is wanted, it is a serial tail of
  full commit-check runs and a new join; the default N-candidate model avoids both and matches the
  operator's crossing today.
- The batch's speed-up is confined to the parallel BUILD of independent stories; the crossing to the
  real trunk stays serial and human, per candidate, per ADR-0002.
- The measure-first precondition means the scheduler is not presented as a speed win until the
  profile is recorded; a built scheduler whose profile shows the time is elsewhere is a correct tool
  that bought nothing, and the record says so rather than assuming.

## Alternatives

- **Serial integration via conjunct-7's compare-and-swap into a shared main** (the pre-draft
  framing): rejected as a category error—the CAS is a within-clone primitive, two stories cannot
  share one clone concurrently, and separate clones have separate `main`s the CAS never crosses.
- **Concurrent stories in one shared clone**: rejected—the sequencer drives the clone's single HEAD,
  index, and working tree, so concurrent phase walks corrupt each other; it would require rewriting
  the graded harvest/checkout path, which D1 refuses.
- **A single integrated `main` for the whole batch, by default**: rejected as the default—it costs a
  real join and a whole-batch review and is not what the operator's crossing needs; kept as an
  optional merge-local extra.
- **Intra-story phase parallelism (the phase-DAG)**: rejected—Amdahl ceiling ~1.2x, and it re-founds
  the ff-only harvest, the single-final-ref merge pinning, and the contiguous-position model; the
  committee ranked it the worst speedup-per-risk lever. Recorded here so it is not re-proposed.
- **Deriving batch concurrency from a story count**: rejected—the binding limit is the account's
  token rate, which must be measured, not a fixed fan-out.

## Falsification condition

Per the house form, each falsifier names its court; future courts are named as future, judgments as
review-watched.

- **D1**: a scheduler change that alters a merge conjunct, the position model, or the harvest.
  Court: the D5 grep-shaped source check plus review that the scheduler imports `merge`/`sequencer`
  and does not reimplement their graded logic—future, named with the batch-scheduler story.
- **D2**: two independent stories observed sharing one clone, or a cross-story dependence on a CAS.
  Court: the scheduler's clone-assignment fixture (one clone per concurrent story; a dependency edge
  same-clone-serial or seeded)—future.
- **D3**: a batch act that merges N stories into the real trunk without a per-candidate human
  crossing. Court: the terminal act stays `guarded_push`/merge-local's, which never pushes `main`
  (live, merge-posture-check); the whole-batch join is opt-in only—review-watched.
- **D4**: two file-overlapping stories launched into the same parallel frontier. Court: the
  pre-launch disjointness matrix (a known-bad fixture: two stories declaring one shared path refuse
  to co-launch)—future.
- **D5**: an unattended batch beginning on a host where the start gate does not clear, or a batch
  exceeding its concurrency ceiling or spend budget. Court: the per-launch start gate (STORY-0015,
  live once built) and the batch ceiling/budget fixtures—future; concurrency-from-measured-rate is
  review-watched (the rate is an operator lookup).
- **D6**: the scheduler relied on as a speed win with no recorded profile. Court: a measurement
  record (per-phase/per-story wall-clock over real stories) named as the precondition; its absence
  is the defect—future.

## Cross-references

- Supersedes: None. Inherits [ADR-0005](ADR-0005-containment-posture.md) (the hardening gate, the
  attended-only posture, D7's build-ahead-gate-enforced pattern), [ADR-0002](ADR-0002-merge-posture.md)
  (the chain never pushes the real trunk; the per-candidate human crossing), and
  [ADR-0001](ADR-0001-advancement-re-derived.md) (advancement re-derived from refs, unchanged per
  story). Builds above [STORY-0013](../../stories/STORY-0013-the-sequencer-script.md) (the sequencer),
  [STORY-0015](../../stories/STORY-0015-the-unattended-start-gate.md) (the gate), and
  [STORY-0016](../../stories/STORY-0016-the-unattended-run-envelope.md) (the per-story runner).
- Superseded by: None.
- Related: `harness/chain_graph.py` (the DAG is expressed via `deps:` and validated for cycles, but
  emits no frontier and does not read the planned set—the scheduler's frontier plumbing is new above
  it); the owed batch-scheduler story and the owed measurement record; the five-lens committee run
  (2026-08-15) that is this record's analysis input.

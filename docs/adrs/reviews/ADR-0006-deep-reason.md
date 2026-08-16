# ADR-0006 acceptance gate: the deep-reason record

Passes per `harness/skills/adr-write/SKILL.md`. Acceptance is the operator's; the gates below
inform that read and substitute for nothing.

## Pass 0 (analysis input), 2026-08-15: the five-lens committee

Before this record, a five-lens committee attacked the adjacent question—could a redesign cleanly
add parallelism to phases for quicker completion. Its findings are this record's analysis input, not
its gate: phase parallelism is ~1.2x and not clean (rejected here as an alternative); story
concurrency is the real throughput win, near-linear in the ready-set breadth, depth irreducible; the
integration model wants to reuse the merge stage rather than a new join; the hardening is the gate;
the per-phase profile is unmeasured. The committee's caveat—all five lenses share a model, so their
agreement is correlated—applies, which is why the pre-draft gate re-verified the load-bearing claim
against the code rather than inheriting it.

## Pass 1 (pre-draft), 2026-08-15: the central decision was a category error, the spine reset

A fresh-context adversary attacked the proposed framing (a batch scheduler whose central decision
was "parallel work, serial integration via conjunct-7's compare-and-swap, no new join"). It traced
the claim through the actual clone/worktree/main mechanics and found it does not hold. Findings taken
into the draft:

- **Blocker 1, the category error, taken as the reset spine.** conjunct 7's CAS is a within-clone,
  single-`main` primitive; it does no cross-story work. Two stories cannot share one clone
  concurrently—the sequencer drives the clone's single HEAD, index, and working tree (checkout the
  story branch, `merge --ff-only` the harvest), so concurrent walks corrupt each other. Independent
  stories run in separate clones with separate `main`s, and one story's merge never moves another's
  `main`, so the CAS never fires across stories. The real serializer is DAG-driven clone topology,
  which the proposed framing left uncosted. D2 was rebuilt on clone topology; the CAS keeps its
  actual, unrelated job (same-story re-invocation and forged-ref protection).
- **Blocker 2, D1+D2+D6 were mutually incompatible, resolved by choosing the topology.** "No new
  join AND untouched graded core AND a single integrated candidate" cannot all hold: a shared clone
  needs a graded-path rewrite; separate clones need either a new join or N candidates. The record
  chooses N merge-ready candidates (D3), which is also the design doc's own ask ("merge-ready
  branches", plural) and matches ADR-0002's per-candidate crossing; a single integrated candidate is
  kept as an optional merge-local extra that costs a join.
- **Blocker 3, the posture split made first-class.** The whole serial-integration / integrated-
  candidate story was merge-local-only; under open-pr (the kit's public target) a batch is N PRs
  whose integration is ADR-0002's existing operator-side rules, needing nothing new. D3 states the
  product per posture.
- Refinements taken: D1 reworded—the scheduler reuses the merge conjuncts unchanged but owns clone
  topology and the direct-`merge.py` retry loop the sequencer's `run` does not expose (it concludes
  an attempt on a park and would force a whole-story re-spend). D4 reframed—the parallel frontier
  must be file-disjoint, checked pre-launch from the plan lists and `sensitive_files` (a shared-file
  pair is a dependency edge, per `story-tighten`), with a runtime conflict park as backstop and the
  behavioral-interaction residual disclosed (the merged-tree commit-check is the only court). D5—the
  envelope's lock and meter are per-story, so the batch adds a concurrency ceiling and a batch
  budget, the ceiling ADR-0003/0004 anticipate, derived from a measured tokens-per-minute rate, not
  a story count. D6—build-ahead gate-enforced (like ADR-0005/D7) with a measure-first precondition,
  because the per-phase profile is unmeasured.
- Verified by the gate against the code: the sequencer drives the clone's own HEAD/index/worktree
  (`reconcile_story_branch`, `checked_out_story`, ff-only `harvest`); merge-local's CAS is per-clone
  against a per-clone `main`; a merge park writes the record and makes `selected_attempt` refuse
  resume (forcing `--fresh-attempt`, a whole-story re-spend), so the cheap re-merge is reachable only
  by driving `merge.py` directly; the per-story lock/meter in `unattended_run.py`; `chain_graph`
  detects cycles but emits no frontier and does not read the planned set.

The draft lands Proposed on the reset spine. The second deep-reason pass attacks the drafted record
before the operator's read; its verdict is recorded below this entry.

## Pass 2 (draft-attack), 2026-08-15: REVISE—three blockers to the operator's read, four refines, all folded in

A fresh-context adversary attacked the drafted record itself (not the framing) for claims the
operator might read as settled and act on. Verdict REVISE, "fix those three and this is
acceptance-ready." Every finding was applied to the draft; none was deferred or waved off.

- **Blocker 1+2, D2's dependency mechanism named a route the sequencer refuses.** The draft's
  two-route dependency handling described a same-clone serial route ("the dependent resumes in the
  dependency's clone after its merge"), but `reconcile_story_branch` requires `head==main_tip` at
  phase 0 and raises `clone-not-at-main` otherwise, and after a run the clone sits on `story/<dep>`,
  not `main`—so that route is actively refused, and the whole mechanism was also silently
  merge-local-only. Fixed: D2 now describes a single SEEDING mechanism—the dependency's result is
  placed as the dependent's clone `main` (its phase-1 base), so `merge-base(main, candidate)` is the
  seed and the dependency's paths stay out of `story_diff` (invisible to conjuncts 2 and 3),
  conditioned per posture (merge-local re-seats HEAD at `main` because the sequencer refuses a
  clone not at `main`; open-pr seeds from the candidate sha), with the crossing-order constraint
  disclosed (the dependent descends from the dependency, so the dependency crosses the real trunk
  first).
- **Blocker 3, D4 claimed a behavioral court that does not run.** The draft said the merged-tree
  commit-path check is "the only court" for behavioral interaction between disjoint parallel
  stories—but in the default N-candidate model each candidate's conjunct-1 runs on its own trial
  merge onto its own base, and nothing runs the check on A+B combined; worse, file-disjointness is
  required for a parallel launch and disjoint stories are exactly those with no dependency edge, so
  they are never integrated within the batch and never share a combined-tree court. Fixed: D4 now
  states there is NO default batch court for the interaction, that only the opt-in single-integrated
  candidate (D3) or the operator's serial real-trunk crossing catches it, so the parallel win is not
  read as behavioral safety.
- **Refine 1 (D4), the plan declaration is the disjointness input.** Stated: the pre-launch
  disjointness check consumes the same `--plan` touch-list conjunct 3 reconciles (with
  `sensitive_files` the flagged subset, not a substitute), whose producer is unbuilt (conjunct 3
  fail-closed until one exists), verified at merge as the backstop.
- **Refine 2 (D5), spend-rate vs concurrency-count.** Reworded: the batch throttles aggregate spend
  to the account's rate limit (an operator lookup of the tier's tokens-per-minute); converting that
  to a concurrency COUNT additionally needs per-story token consumption, which is the same unmeasured
  profile D6 defers—so the aggregate-spend throttle is the bound that holds until the profile exists.
- **Refine 3 (D6), measure-first teeth and gate scope.** Gave the precondition a bell (the scheduler
  prints `profile unmeasured—speedup unproven` until a measurement record exists) and noted the start
  gate certifies only host hardening, so the concurrency ceiling and spend throttle are the
  scheduler's own new code, courted by its own fixtures, not by the gate.
- **Refine 4 (D1), when the retry pays and that it is graded.** Added: the direct-`merge.py` retry
  pays only on a moved `main` (conjunct 7 lost its race) or a transient could-not-run, never a real
  conjunct FAIL (which just re-refuses), and each retried merge passes a fresh `--record` so it is
  graded afresh, not waved through.

The record stays Proposed. Acceptance is the operator's read; this gate informs it and settles
nothing on its own.

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

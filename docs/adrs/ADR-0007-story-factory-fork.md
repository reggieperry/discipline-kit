# ADR-0007: The story-factory fork—reuse an external orchestration substrate, not a hand-built scheduler

**Status:** Accepted (2026-08-16), on the operator's direction to decline ADR-0006 and record the
reuse fork; amended 2026-08-16 (operator-directed), D3 gains the pack/rig mapping, D4 gains the
examiner-denominator guard, and Consequences records the generation-time guidance-versus-enforcement
boundary—all elaboration and fail-closed strengthening, reversing no decision.
Acceptance gate: one deep-reason pass, recorded in
[reviews/ADR-0007-deep-reason.md](reviews/ADR-0007-deep-reason.md), attacking reuse-over-build; and
the operator's own read, given 2026-08-16, which no adversary pass substitutes for. The specific
substrate and its mechanics are evaluated in a private companion analysis held outside this repo, in
the operator's home directory, per the infra-scrub policy; this record stays substrate-agnostic.

## Context

The chain processes one story at a time through graded, fail-closed phases whose verdict is
re-derived from git refs and never self-reported (ADR-0001), stopping short of the published trunk
(ADR-0002) behind a containment posture that is attended-only until the hardening lands (ADR-0005).
That single-story pipeline is built and has run end to end. It also already serves small-scale
parallelism: a handful of independent stories can run at once, attended, one clone apiece, by hand.

What is not built is UNATTENDED parallelism at scale—a supervisor that schedules a dependency graph
of stories, sizes a pool of workers to demand, survives crashes, and drives a planned set to
completion overnight without a human at each step. ADR-0006 proposed to build that orchestration
inside the chain: a DAG-driven clone topology, a concurrency ceiling, an unattended-run envelope,
merge-retry orchestration. It reached Proposed and was drafted and draft-attacked.

The forcing observation: that orchestration—dependency-ordered scheduling, demand-sized worker
pools, scheduled and triggered dispatch, crash survival, multi-repo isolation, an observable event
stream—is not novel. A general-purpose multi-agent orchestration substrate already ships all of it,
and the chain's distinctive contribution is not the orchestration but the DISCIPLINE that rides on
it: the re-derived verdict, the fail-closed graded phases, the fence, the merge conjuncts. So the
real fork is not "how do we build the scheduler" but "do we build the orchestration floor at all, or
reuse a proven one and carry only our discipline onto it." A private companion analysis read the
candidate substrate's mechanics in detail and found the reuse seam clean; this record decides the
fork.

## Decisions

### D1: The chain does not build its own unattended-parallel orchestration; ADR-0006 is declined

The hand-built batch scheduler ADR-0006 proposed—the DAG clone topology, the concurrency ceiling,
the unattended-run envelope as new chain code—is not built. ADR-0006 is Rejected in favor of this
record. The single-story pipeline, its gates, and the merge stage stand unchanged; nothing already
built is removed. Attended, small-scale, hand-driven parallelism (one clone per independent story)
remains available and needs nothing new.

Covered-by: none—a decision not to build; its artifact is ADR-0006's Rejected status and this record.

### D2: Unattended parallelism, when built, reuses an external orchestration substrate; the chain's discipline mounts onto it as an importable pack, rather than reimplementing the floor

When unattended-parallel processing is wanted, the chain does not become the scheduler. A
general-purpose orchestration substrate provides the floor—dependency-ordered scheduling,
demand-sized worker pools, triggered and scheduled dispatch, crash survival, multi-repo isolation,
an observable event stream—and the chain's discipline is carried onto it as an importable,
version-pinned pack: the graded phases as the substrate's work units, the postconditions as the
mechanical gates between them, the fence as the worker's tool-permission settings, the merge
conjuncts as the final gate. The build is deferred; this Decision fixes the APPROACH—reuse, not
build—not a schedule.

Covered-by: none—owed to the reuse-pack build, not scheduled; deferred behind a measured need for unattended parallelism.

### D3: The reuse path adds exactly one new repository—the pack; the chain stays the source of truth, the substrate stays the engine, and target repos are the substrate's registered projects

The only new artifact is a private pack repository holding the substrate configuration: the phase
workers, the phase graph, and the mechanical gate scripts. The chain repository is unchanged and
remains the source of truth for the discipline—the pack vendors version-pinned copies of the chain's
grading and merge-conjunct logic, the same copy-not-share pattern the chain already uses to ship its
tools, so the discipline has one home and the pack is a downstream copy. The substrate is used as
its engine, not forked or modified. Each target repository is registered with the substrate as a
project, isolated by its own work namespace. The pack repository is private, because it necessarily
co-locates the discipline's internals with the named substrate that the chain repository is scrubbed
of.

The substrate splits configuration on two axes—the config unit it imports (its "pack") and the
target project it registers (its "rig")—and the chain's pieces map cleanly onto them, which is why
this Decision needs only one new repository. The pack is the method; the rig is the target the chain
was never part of:

| Chain piece | Pack (the method) or Rig (the target) |
|---|---|
| Phase workers, their prompts, the fence settings | Pack |
| The phase graph and the gate scripts (postcondition and merge-conjunct logic) | Pack, vendored version-pinned from the chain |
| The worktree/clone setup that isolates a phase | Pack ships the mechanism; the rig supplies its repo path |
| The target repository's own code | Rig |
| The target's own rules (the reviewer's lens source) and its own check script | Rig, read from the registered checkout |
| Per-target tuning (worker count, model, which reviewer) | Rig, by per-target override, never a pack copy |
| A story, and its brief | A work item in the rig's namespace |

So the chain does not fragment across the two axes: it IS the pack, the target repos are rigs it
never owned, and a story is a work item in a rig. The one genuinely divided concern is gate INPUT,
and it carries a guard stated in D4.

Covered-by: none—owed to the reuse-pack build; the chain repository itself acquires no new code under this Decision.

### D4: On the substrate, the discipline's gates are the closure mechanism, never the substrate's own self-report; this is the acceptance condition on any reuse build

The substrate's default is that a worker declares its own work done. That default is precisely the
confidently-wrong-at-signature failure the chain exists to prevent (ADR-0001). Therefore, on the
substrate, no phase advances by the worker closing its own unit: every phase is gated by a
mechanical check the controller runs—the chain's postcondition, re-deriving the verdict from git
refs—and only that check's pass advances the graph. A reuse build in which any phase can advance on
the substrate's self-report is non-conforming and is not shipped. The chain's three-valued verdict
(pass / fail / could-not-run-parks) must survive the mapping onto the substrate's gate, which is
binary by default; a could-not-run that reads as either pass or retry is the same defect in a new
place. The terminal act is inside this seam, not outside it: the branch push or PR-open that
concludes a story is controller-run—a side effect of the merge gate's pass—never an agent's step
body, so it cannot fire before the merge conjuncts have passed. That is ADR-0002/D5 carried onto the
substrate: the terminal act is the driver's, never an agent's. One gate INPUT divides in a way that
must fail closed (D3's mapping): the reviewer's coverage denominator—the set of review-owed rules,
read from the rules' declared grades—must be derived from a copy pinned OUTSIDE the target's judged
tree (pack- or city-side), never from the target's live rules. The substrate's default is the
opposite, a worker reading the registered checkout's own rules, so a phase that computed its
denominator from the target's live rules would let a story flip a grade to shrink its own review
scope—the exact hole the chain's pinned examiner copy closes (STORY-0008). The rule CONTENT the
reviewer reads may be the target's; the grade-derived denominator may not.

Covered-by: none—owed to the reuse-pack build and its gate-seam test; the invariant is ADR-0001 re-asserted for the substrate context.

## Consequences

- The chain keeps a bounded scope: the discipline (gates, re-derived verdict, fence, merge
  conjuncts) plus the single-story driver. It does not grow an orchestration subsystem, and the
  substantial code ADR-0006 would have added—scheduler, concurrency ceiling, unattended envelope,
  merge-retry loop—is not written or maintained.
- The unattended-parallel capability, when built, arrives as a small pack over a proven floor rather
  than a large hand-built subsystem: less code to write and keep correct, and the floor's
  scheduling, scaling, crash survival, and observability come for free.
- The cost is a dependency on an external, actively-changing substrate the chain does not control,
  whose defaults are permissive where the chain is fail-closed. The reuse build must guard against
  those defaults at every phase (D4), and the pack must track the substrate's churn.
  Self-containment—the chain's stated design goal of depending on no sibling repository—holds for the
  chain itself
  but not for the reuse pack, which is why the pack is a separate private repository, not part of the
  chain.
- The discipline now has two potential consumers: the built-in single-story driver and the reuse
  pack. The re-derived-verdict invariant (ADR-0001) must be honored by both, and the pack honors it
  only through D4's gate-seam—which is exactly where the reuse can silently fail.
- The substrate does not close ADR-0001's forged-completion residue—it relocates it. A worker holding
  a shell can write the substrate's work-and-dependency state directly, and can touch the git state
  the re-derivation reads, the same way a phase could forge a completion ref today; the worker's
  tool-permission fence is friction, not a sandbox (ADR-0005/D1). On the substrate that residue is
  consumed, not closed, and it is bounded exactly as the chain bounds the forged phase ref: by the
  OS-and-runtime isolation ADR-0005/D2 makes the precondition for unattended work, not by the fence.
  The reuse build inherits that residue and its bound; it introduces no new hole, but D4's gate-seam
  must not be read as closing the old one.
- The pack's vendored copy of the discipline is a cross-repo copy, and loses the same-repo
  commit-path checks that keep the chain's internal copy-not-share honest. A drift court is owed with
  the pack—the vendored grading and merge-conjunct logic matches the chain's pinned SHA, checked on
  the pack's own commit path—or the copy silently rots against its source.
- The discipline reaches the code-generation phase in two forms, and only one of them enforces. The
  pack delivers the chain's coding rules into the generation agent's working context and the fence
  into its harness settings, so the guidance that SHAPES the code travels with the pack alongside the
  gates that VERIFY it; the substrate's harness discovers the rules in the agent's workspace and
  applies the fence natively, and the pack may additionally wire an in-session harness check (a
  format-on-edit, a pre-tool block) that runs while the agent works. But every one of those is the
  GUIDANCE layer, not the enforcement: injected rules and in-session harness checks are advisory
  inside the agent's own process and hold only while that process honors them—the substrate's default
  even runs the harness with its permission prompts skipped. Treating in-session guidance or a harness
  hook as the gate is the same friction-for-enforcement error D4 refuses; the authoritative verdict
  stays the post-phase gate, re-derived from git refs outside the session. The generation-time layer
  makes conforming code likelier; the gate is what refuses code that is not.
- ADR-0006 is retired to Rejected. Its record, its decisions, and its two deep-reason passes stay in
  place as the graveyard: the next person to propose building the scheduler inherits why it was
  declined.

## Alternatives

- **Build the scheduler in the chain (ADR-0006).** Keeps the chain self-contained and in full
  control of every trust decision, because the discipline is built into the orchestration rather
  than guarded against it. Lost because it reimplements a large, proven orchestration
  floor—scheduling, pools, dispatch, crash survival, multi-repo, observability—as new chain code the
  chain would own and maintain, for a capability the substrate already ships; the self-containment
  and control it buys did not outweigh the build-and-maintain cost.
- **Do nothing—attended, hand-driven parallelism only.** Run a handful of clones by hand when
  parallelism is wanted. Adequate at small scale and available today at zero cost, but it does not
  reach unattended overnight processing of a planned set, which is the capability under question.
  Kept as the floor, not the answer.
- **A single integrated substrate that also owns the discipline, with no separate pack.** Rejected:
  it would either fork the substrate to inject the discipline—coupling the chain to the substrate's
  history and churn—or push the discipline's judgment into the substrate's engine, which the
  substrate's own design forbids (it keeps judgment out of the engine). The pack-over-unmodified-
  engine seam keeps the discipline in the chain's hands.

## Falsification condition

Per the house form, each falsifier names its court; a court that cannot yet convene is named as
future, and a judgment only a prototype or time settles is named as such.

- **D1/D2**: the reuse seam cannot preserve the re-derived-verdict invariant—some phase, on the
  substrate, is forced to close on the worker's self-report rather than a controller-run mechanical
  check, or the three-valued verdict cannot be expressed on the substrate's gate. Then reuse fails at
  the one thing the chain exists for, and building (ADR-0006) must be reopened. Court: the
  reuse-pack's gate-seam test—every phase advances only on a re-derived check; a could-not-run parks,
  never advances—a STANDING gate re-run on every substrate version bump, not a one-time acceptance,
  because the substrate churns and a permissive-default regression is silent (ADR-0001's green can
  mean not-looking)—future, built with the pack; until it exists and passes, this decision is
  unproven and reads as such.
- **D2/D3**: the reuse integration plus the cost of tracking the external substrate's churn exceeds,
  over a real build, what the hand-built scheduler would have cost to write and maintain. Then the
  build-versus-reuse call was wrong on its own economics. Court: not mechanical—the standing
  observation is the reuse-pack build's actual cost against ADR-0006's estimated cost, judged after
  the pack exists.
- **D4**: a shipped reuse build in which any phase—or the terminal act—advances on the substrate's
  self-report, or in which the reviewer computes its coverage denominator from the target's live
  rules rather than a copy pinned outside the judged tree. Court: the standing gate-seam test
  above—known-bad cases (a phase or a terminal push wired to fire on the worker's own done-signal;
  a denominator read from the target's own rules) must be refused—re-run on every substrate version
  bump, future, built with the pack.

## Cross-references

- Supersedes: None—ADR-0006 was Proposed and never accepted, so this record REJECTS it rather than
  superseding a governing decision. [ADR-0006](ADR-0006-batch-scheduler.md)'s decisions and its
  deep-reason record stand as the declined alternative.
- Inherits [ADR-0001](ADR-0001-advancement-re-derived.md) (advancement re-derived from refs—D4
  re-asserts it for the substrate), [ADR-0002](ADR-0002-merge-posture.md) (the chain never pushes
  the real trunk—the reuse merge gate keeps the per-candidate human crossing), and
  [ADR-0005](ADR-0005-containment-posture.md) (the containment posture—on the substrate, real
  isolation is the runtime the workers run in, and the attended-only-until-hardening bar carries
  over).
- Superseded by: None.
- Related: the private companion analysis of the candidate substrate, held outside this repo in the
  operator's home directory per the infra-scrub policy—the substrate's mechanics with source
  citations, and the reuse seam evaluated in detail; [ADR-0006](ADR-0006-batch-scheduler.md)'s
  five-lens committee and deep-reason record, which established that the orchestration ADR-0006 would
  build is largely a reimplementation of an existing floor.

---
paths:
  - "**/*.scala"
  - "**/*.sc"
---

# Scala concurrency

**Enforcement grade:** partly mechanical, at the margins — a repo that enables the typelevel scalafix rules gets non-fused monadic chains flagged through Check A. Nothing scans for `IO.blocking` versus `IO.delay`, `Resource` lifetimes, `Ref` over `var`, or bounded fan-out.

Effect lifecycle, shared state, and parallelism for a pipeline whose nodes do real I/O — model calls, file reads, metric sinks — while the domain core stays pure. cats-effect is the one effect system here; ZIO and raw `scala.concurrent.Future` are out, and mixing them in is banned (see "No raw Future" below). Sources: Gabriel Volpe, *Practical FP in Scala: A hands-on approach* (the "Sequential vs concurrent state" / "Atomic Ref" best-practices chapter, the regions-of-sharing discussion, and the bonus chapter on Concurrency, (Un)Cancelable regions, and Resource safety); Volpe, *Functional Event-Driven Architecture* (Ref-on-`AtomicReference`, the distributed-lock-as-`Resource`, and Supervisor-as-dependency); and the cats-effect documentation on the thread model and schedulers, plus Tim Spence's "Threading best practices in Cats Effect."

> See `scala-modules.md` for the concrete-`IO`-versus-tagless-final house call and the one-effect-system rule, `scala-types.md` for the opaque-type / ADT / `Validated` modeling that stays pure, `scala-testing.md` for `ScalaCheck` property tests and how to test effectful code deterministically, `scala-llm.md` for the timeout and retry budget on model calls, and `craft-tdd.md` for keeping concurrency policy out of the logic so the logic stays unit-testable.

## The effect boundary

- **The domain core is pure; effects are `IO`.** Your domain value types, ADTs, and `Validated` pipelines are referentially transparent values with no `IO` in their signatures — they compute, they do not act. Every node's I/O (the model call, reading inputs, writing a metric) is `IO`, threaded through the pipeline. Keep the two apart: a function that both computes a verdict and writes a metric is two functions wearing one name.
- **Build the program as a description, run it once at the edge.** Compose `IO` values with `flatMap` / `for` / the cats-effect combinators and hand the final `IO` to `IOApp.run`. Do not reach for `unsafeRunSync()` in pipeline or library code — it discards referential transparency and, as Volpe's "leaky state" example shows, throws away the `flatMap`-denoted region that tells you where a value is shared.

## No raw Future, one effect system

- **Do not introduce `scala.concurrent.Future`.** `Future` is eager — it starts running at construction, so it is not a description you can compose, retry, or cancel — and it carries an implicit `ExecutionContext` that silently routes work onto whatever pool is in scope. Where a dependency hands you a `Future`, wrap it at the seam with `IO.fromFuture(IO(makeTheFuture))` so the deferral is captured, and let nothing past the seam see the `Future`.
- **Do not mix in ZIO.** One effect system, one runtime, one set of fiber semantics. cats-effect `IO` is the house effect; a second effect type fragments cancellation and resource safety and forces interop shims at every boundary.

## Resource for every lifecycle

- **Anything acquired must be released by `Resource`, not by hand.** Model clients, file handles, metric sinks, thread pools, and any spawned long-lived process are `Resource[IO, A]`. `Resource.make(acquire)(release)` guarantees the finalizer runs on completion, on error, and on cancellation — the three exits a hand-written `try`/`finally` tends to miss. Volpe models even a distributed lock this way: acquire-on-`use`, release-in-finalizer.

```scala
import cats.effect.{IO, Resource}

def modelClient(cfg: ClientCfg): Resource[IO, ModelClient] =
  Resource.make(IO(ModelClient.open(cfg)))(c => IO(c.close()))

def metricSink(path: Path): Resource[IO, MetricSink] =
  Resource.make(IO(MetricSink.append(path)))(s => IO(s.flush()) *> IO(s.close()))

// Compose the whole rig into one Resource, use it once at the edge.
val rig: Resource[IO, Pipeline] =
  (modelClient(cfg), metricSink(out)).parTupled.map { case (mc, sink) =>
    Pipeline(mc, sink)
  }

val program: IO[Unit] = rig.use(pipeline => pipeline.runAllNodes(input))
```

- **Compose resources, don't nest `use` calls.** Build one `Resource` for the rig by combining the parts (`flatMap`, `parTupled`, a `for`-comprehension in `Resource`), then a single `.use` at the top. Nested `.use` blocks invert acquisition and release order by hand and make the lifetime hard to read; one composed `Resource` releases in the correct reverse order for free.

## Shared state — Ref and Deferred, never a `var`

- **Use `Ref[IO, A]` for shared mutable state; never a bare `var` or a `java.util.concurrent` primitive.** `Ref` is a purely functional concurrent mutable reference built on `AtomicReference#compareAndSet`; its `update` and `modify` are atomic, so the per-node instrumentation counters and a running tally compose without a lock. Create it inside `IO` (`Ref.of[IO, Int](0)`) so the allocation joins the program description rather than escaping as global state.
- **Reach for `Deferred[IO, A]` for one-shot signaling between fibers** — a gate completed exactly once that other fibers await. Use it when one fiber must wait for another to reach a point; do not simulate it by polling a `Ref` in a loop.
- **Keep the region of sharing explicit.** A piece of shared state is shared exactly within the `flatMap` (or `for`) block where it was created and passed down. Allocate it there and thread it through the functions that need it; do not hoist it to a top-level `val` resolved with `unsafeRunSync()`. The enclosing block is what tells the reader — and the compiler — who can touch the state.

```scala
import cats.effect.{IO, Ref}

final case class Tally(ref: Ref[IO, Int]):
  def bump: IO[Unit]    = ref.update(_ + 1)
  def count: IO[Int]    = ref.get

object Tally:
  // Allocation lives in IO; the region of sharing is the caller's flatMap block.
  val make: IO[Tally] = Ref.of[IO, Int](0).map(Tally(_))
```

- **Prefer `modify` when the update and its result must be one atomic step.** `ref.modify(s => (next(s), readback(s)))` reads and writes in a single CAS; a `get` followed by a separate `update` is a race.

## Never block the compute pool

The cats-effect runtime runs three pools: a work-stealing **compute** pool sized to the available processors, an unbounded **blocking** pool, and a small high-priority **scheduler/I-O-event** pool. `IO` runs on the compute pool by default. Per the cats-effect thread-model docs and Spence's best-practices write-up, running blocking code on the compute pool is *very* bad: one compute thread parked on a `Thread.sleep`, a JDBC call, or a synchronous file read removes a fraction of total throughput, and a few of them stall the whole pipeline.

- **Wrap any thread-blocking call in `IO.blocking`** (or `IO.interruptible` when it must be cancelable). These declare to the runtime that the effect blocks a thread, so it shifts the fiber onto the blocking pool and shifts it back to compute when the call returns. `IO(...)` / `IO.delay(...)` around a blocking call is the bug — the runtime's blocking-on-compute detector exists precisely to catch it.
- **Use `evalOn` to confine a body to a specific `ExecutionContext`** and have the continuation shift back automatically — for a library that demands its own pool.
- **Treat the distinction by what blocks.** A non-blocking async client returns an `IO` you compose directly; a synchronous, thread-parking call is `IO.blocking`. When unsure, assume it blocks.

```scala
import cats.effect.IO
import java.nio.file.{Files, Path}

// Synchronous file read parks a thread -> IO.blocking, shifted off compute.
def readInput(p: Path): IO[String] =
  IO.blocking(Files.readString(p))

// A long, cancelable blocking call -> IO.interruptible so cancellation can land.
def callLegacyScorer(req: Req): IO[Score] =
  IO.interruptible(LegacyScorer.scoreBlocking(req))
```

## Structured concurrency and bounded parallelism

A pipeline can be synchronous in its *logic* — a fixed sequence of nodes — but that does not force serial *effects*. Where a node's independent effects can overlap, parallelize them; everywhere, keep fiber lifetimes structured so nothing outlives its owner.

- **Use `parMapN` / `parTupled` / `parTraverse` for independent effects.** Combining independent `IO`s in parallel (config load and warm-up, or fanning a batch of inputs through a node) is `parMapN` or `parTraverse`; the result joins all of them and propagates the first failure, cancelling the rest. Volpe runs a Redis ping and a Postgres query in parallel with `parMapN` for exactly this.
- **Bound the fan-out with the `N` combinators** — `parTraverseN(n)` and `parSequenceN(n)` — so a batch of inputs cannot spawn unbounded concurrent model calls and exhaust connections or rate limits. Choose `n` deliberately; do not let `parTraverse` open one fiber per element against a metered model API.
- **Spawn fibers structurally, never bare `start` you then forget.** A fiber from `IO.start` that nothing joins or cancels is a leak. Use `.background` (a `Resource` whose finalizer cancels the fiber) for a child bounded to a scope, and `Supervisor` for fire-and-forget actions whose lifecycle is tied to the supervisor's `Resource` rather than the spawning fiber. `Supervisor[IO].use { sp => ... }` (often threaded as a `using` dependency, as Volpe does) is the sanctioned fire-and-forget; a raw discarded `start` is not.

```scala
import cats.effect.IO
import cats.syntax.all.*

// Fan a batch of inputs through one node with bounded parallelism.
def scoreBatch(node: Node, inputs: List[Input]): IO[List[Verdict]] =
  inputs.parTraverseN(4)(node.score)   // at most 4 concurrent model calls

// Two independent setup effects, run in parallel, both awaited.
val warmup: IO[(Client, Sink)] =
  (openClient, openSink).parTupled
```

## Cancellation and finalizers

- **`IO` is cancelable by default; let finalizers do the cleanup.** When a parallel branch fails and its siblings are cancelled, their `Resource` finalizers and `bracket`/`guarantee` blocks still run. Rely on that rather than draining state by hand. This is why acquired things belong in `Resource` and shared state in `Ref` — both survive cancellation cleanly.
- **Mark a region `uncancelable` only around an action that must complete atomically**, and use the supplied `Poll` to re-enable cancellation for any genuinely-blocking step inside it (Volpe's `nope`/`yup` example: an `uncancelable` region whose inner `gate.get` is wrapped in `poll(...)` so it does not dead-lock). Reach for `uncancelable` rarely and narrowly; the default cancelability is what keeps the pipeline responsive.

## Determinism and reproducibility

A run you can reproduce from a seed is easier to debug and to trust, so keep instrumentation and randomness deterministic rather than at the mercy of scheduling.

- **Do not let parallelism reorder a result that depends on order.** If a metric or an output is sensitive to node sequence, compute it from the structured result, not from the wall-clock order in which parallel branches happened to finish — `parTraverse` is non-deterministic in completion order even though it preserves result order.
- **Carry randomness as an effect, not as `scala.util.Random` global state.** Use `cats.effect.std.Random` (a `Resource`/`IO`-bound instance threaded through the nodes) so a run is reproducible from a seed and two parallel fibers cannot collide on a shared mutable generator.

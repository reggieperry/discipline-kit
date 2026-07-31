---
paths:
  - "**/*.scala"
  - "**/*.sc"
  - "build.sbt"
---

# Scala project and dependency structure

**Enforcement grade:** review and convention — sbt itself rejects a `dependsOn` cycle, but nothing in the gate enforces one-runtime-per-module, given placement, or the ban on orphan instances. A repo can mechanize the pure-versus-effectful seam with a dependency check on its core module.

How to organize packages, modules, and dependencies, and where to put the things the compiler resolves implicitly. Sources of record: the sbt Reference Manual on multi-project builds (scala-sbt.org/1.x/docs/Multi-Project.html); the Scala 3 reference on implicit resolution and implicit scope (docs.scala-lang.org/scala3/reference/changed-features/implicit-resolution.html); Gabriel Volpe, *Practical FP in Scala* (2nd ed), chapters 2 (tagless-final, modules, capability traits) and 6 (orphan instances); and the Typelevel community's settled position on concrete `IO` versus tagless final (typelevel/cats-effect#3133, "A little more `IO` and a little less `F[_]`"). One house rule governs the rest: **cats-effect is the one effect system here.**

> See `scala-types.md` for opaque types and ADT modeling of the values these modules pass, `scala-llm.md` for wrapping a model SDK at the seam, `scala-style.md` for naming and the braces default, `craft-complexity.md` for deep cohesive modules and the dependency-versus-obscurity frame, and `craft-domain-modeling.md` for drawing module boundaries along bounded-context seams.

## One effect system: cats-effect

What this set rests on is a single effect standard. Scala's sharpest practical risk is not a thin training corpus — it is a *fragmented* one: Scala 2 against Scala 3, and several competing effect systems (raw `Future`, cats-effect, ZIO) layered over an unsettled object-oriented-versus-functional split. Types catch a type error; they do not catch "used a coherent but wrong library." Every rule here exists to collapse that fragmentation to one coherent standard the model can pattern-match against.

- **cats-effect `IO` is the only effect type.** All effectful code returns `cats.effect.IO[A]` (or a `cats-effect` typeclass constraint where a genuine abstraction is earned — see below). The entry point is a `cats.effect.IOApp`.
- **ZIO is banned in this repo.** Do not add `dev.zio` dependencies, do not import `zio.*`, do not introduce `ZIO`, `ZLayer`, `ZStream`, or `Has`. ZIO is a fine ecosystem; mixing two effect systems in one codebase is the fragmentation failure this rule exists to prevent.
- **Do not mix raw `scala.concurrent.Future` into effectful code.** `Future` is eager, memoized, and not referentially transparent, so it composes wrongly with `IO` and breaks the reproducibility the rest of the code relies on. When a JVM library hands back a `Future` (an async SDK client is the realistic case — see `scala-llm.md`), wrap it once at the seam with `IO.fromFuture(IO(...))` or `IO.fromCompletableFuture`, and let `IO` flow from there. Never thread a bare `Future` through the pipeline.

```scala
// House default — effects are IO, the boundary is wrapped once.
def fetchRecord(id: OrderId): IO[Record] =
  IO.fromCompletableFuture(IO(client.fetchAsync(id)))

// Banned — a second effect system, and an eager Future leaking into the pipeline.
// import zio.*
// def fetchRecord(id: OrderId): ZIO[Any, Throwable, Record] = ???
// def fetchRecord(id: OrderId): Future[Record] = client.fetchAsync(id).asScala
```

## Keep the domain core pure; let effects live at the edges

- **The domain core — your value types, the ADTs, and the `Monoid`/`Semigroup`/`Order` instances that combine them — is pure and effect-free.** It computes with total functions; it does no `IO`. Pushing the combines and the folds into pure values is what makes them law-testable under ScalaCheck (`scala-testing.md`) and what makes a computation reproducible from its inputs alone.
- **`IO` belongs to the pipeline shell, not the domain core.** The service wiring, the config load, the model call, and the record store are effectful; the value routed through them is not. Keep the seam visible: an effectful function takes pure values in and returns pure values in `IO`.

## Concrete `IO` is the default; earn tagless final

Volpe presents tagless final (`def program[F[_]: Monad: Console]`) as a way to constrain a function to declared capabilities, and the technique is sound. But the settled community position — the cats-effect maintainers' own — is that **for application code, where you know which effect you run, abstracting over `F[_]` and writing `[F[_]: Sync]` everywhere is a false abstraction.** This is application code.

- **Default to concrete `cats.effect.IO`.** Write `def run(order: Order): IO[Receipt]`, not `def run[F[_]: Sync](order: Order): F[Receipt]`. Concrete `IO` is easier to write, easier to read, and the one effect every reader already knows is in play.
- **Reach for an `F[_]` typeclass constraint only when an abstraction is genuinely earned** — a reusable library-like component that several call sites must instantiate at different effect types, or a seam that a future transport must re-interpret. Volpe's own escape hatch applies: program against the narrowest capability (`Async`, `Temporal`, `Console`), never against a kitchen-sink constraint list. The principle of least power is the test — if no second instantiation exists, the abstraction is theatre and costs the reader a type parameter for nothing.
- **A stage seam is a function, not a tagless algebra by reflex.** A settled design is `node = (Contract, computation)` with concrete `IO`; keep the transport-agnostic *shape* (pure value in, value out) so an actor or streaming transport can slot in later, without paying for `F[_]` abstraction now.

## Modules: group cohesive services, wire them with smart constructors

When concrete `IO` leaves a top-level program with too many dependencies, the answer is not implicits — it is grouping. Volpe's "module" is a trait that bundles cohesive services; its companion object carries the smart constructor that builds the implementation as a `Resource`.

```scala
package modules

trait Ingest {
  def reader:    SourceReader
  def validator: Validator
  def store:     RecordStore
}

object Ingest {
  def make(cfg: Config): Resource[IO, Ingest] =
    (SourceReader.make(cfg), Validator.make, RecordStore.make(cfg)).mapN { (r, v, s) =>
      new Ingest {
        val reader    = r
        val validator = v
        val store     = s
      }
    }
}
```

- **Group along cohesion, build along resource lifecycle.** A module bundles services that belong together; its `make` returns a `Resource[IO, T]` so acquisition and release are paired and the `IOApp` composes a single resource at the top.
- **Pass domain services explicitly; never as implicits.** Volpe's rule is firm: business-logic algebras are passed as explicit constructor parameters. Implicit resolution is for coherent typeclass instances and a small set of common-effect capabilities (`Console`, a seeded `Random`, `GenUUID`), not for the pipeline's own services. Passing a dozen explicit dependencies at the top level is expected — that is what modules are for.

## Given-instance placement: companion objects, no orphans

Where you put a `given` (a typeclass instance) is a correctness decision, not a style one. The Scala 3 implicit scope of a type `T` includes `T`'s companion object; package prefixes no longer contribute. So the companion is where an instance is found with no import, and it is the only placement that guarantees coherence.

- **Put a typeclass instance in the companion object of the type it is for.** A `given Eq[OrderId]` goes in `object OrderId`. The compiler finds it through implicit scope, no import is needed, and — central point — **there can be exactly one such instance per type.** A duplicate is rejected, never silently overridden.
- **Do not write orphan instances** — an instance placed neither in the type's companion nor the typeclass's. Orphans are not in implicit scope, so they demand a fragile import, and two different orphans for one type can both compile while a wrong one wins at a given call site. Volpe is blunt here: orphan instances would be "immediately rejected, or even worse, silently overridden."
- **For instances over types you do not own** (a third-party or JVM type), collect them in one named mixin and bring them in with a single explicit import, rather than scattering them.

```scala
// instances for types this repo does not control
object OrphanInstances {
  given Eq[java.util.UUID]       = Eq.fromUniversalEquals
  given Order[java.time.Instant] = Order.by(_.toEpochMilli)
}
// at the use site, one deliberate import:
// import OrphanInstances.given
```

## sbt module boundaries: one root until a binary earns a split

Keep the build a single root module until the structure actually demands more, then split — each subproject producing a function-named binary — when the second binary is written, not before.

- **Start with one root `project`; do not pre-split.** Premature module trees add a dependency graph, cross-module visibility questions, and build latency for no benefit. A natural first split is a pure `domain` module, a `service` module (the pipeline), and a second binary such as a `cli` tool, drawn when that second binary appears.
- **When you do split, declare each subproject as a `lazy val ... = (project in file(...))` and wire compile dependencies with `dependsOn`.** `dependsOn` puts one project's compiled output on another's classpath and forces build order; the pure `domain` module depends on nothing and everything else depends on it. Keep the dependency arrows one-directional — a cycle means a boundary is in the wrong place (`craft-complexity.md`).
- **Distinguish `dependsOn` from `aggregate`.** `dependsOn` is a classpath-and-ordering relationship; `aggregate` only fans a task out across projects. Use `dependsOn` for real code dependencies; reserve `aggregate` on the root for running `test`/`compile` across the tree.
- **Factor shared settings through `ThisBuild`, not by copy-paste.** `scalaVersion`, `organization`, and the strict `scalacOptions` (`-Wunused:all`, `-Wvalue-discard`, `-explain`) live under `ThisBuild` so a subproject inherits them; a subproject overrides a key only with a stated reason.
- **Draw the hardest boundary at the pure-versus-effectful seam.** The pure `domain` module must not depend on `cats-effect`; keeping `IO` out of it at the build level makes the purity rule above structural rather than aspirational.

## Public API surface

- **Expose a small, stable surface; keep internals package-private.** A module's public types are a contract — the domain values on the wire, the module traits, the smart constructors. Mark helper types and intermediate machinery `private[pkg]` so they can be reshaped without breaking callers (`craft-complexity.md`: deep modules, narrow interfaces).
- **Name modules and packages after the domain concept they own** — `billing`, `pricing`, `inventory`, `scheduling` — never `utils`, `common`, `helpers`, or `core` as a grab-bag. A package with no cohesive responsibility becomes a dump; the package name is part of every import that reads it (`craft-domain-modeling.md`).

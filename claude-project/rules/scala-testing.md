---
paths:
  - "**/*Suite.scala"
  - "**/*Spec.scala"
  - "**/*Test.scala"
  - "**/src/test/**/*.scala"
---

# Scala testing

How to write Scala tests: munit suite structure, fixtures without shared mutable state, deterministic property-based testing with ScalaCheck, type-class laws checked with `discipline`, and algebraic laws as the default test shape for any lawful instance. Sources: the munit docs (FunSuite, fixtures, the ScalaCheck integration), the ScalaCheck user guide (`forAll`, `Gen`, labeling, shrinking, seeds), the Typelevel `discipline` / `cats-laws` / `algebra-laws` docs (`checkAll` and the `*Tests` law bundles), and *The Science of Functional Programming* (Sergei Winitzki) for the semigroup associativity law, the monoid identity laws, and the structural-analysis stance that a type-class instance is correct only once its laws are verified. The TDD cadence and design discipline are in `craft-tdd.md`; this rule is the Scala mechanics. The engines are pinned in `build.sbt`: `munit`, `munit-scalacheck`, `scalacheck`, `cats-laws`, `algebra-laws`, `discipline-munit`, and `munit-cats-effect`, all `% Test`.

> See `craft-tdd.md` for red-green-refactor and "listen to the tests", `scala-types.md` for the `enum` ADTs and `opaque` types whose laws these tests pin, `scala-style.md` for the brace and `given`/`using` defaults the examples follow, `scala-concurrency.md` for the one-effect-system rule the effectful suites obey, and `craft-domain-modeling.md` for why a `Money` or `Verdict` type carries behavior worth a law.

## The residue this rule carries

The governing principle is stated in `scala-types.md` ("encode what's cheap, test the residue"): the type encodes the invariants it cheaply can, and these tests carry the rest. The obligation that lands here is **two-sided** — for every invariant a type cannot state, write the law or property over valid input *and* the test that the type's validating smart constructor refuses or normalizes illegal input. The negative space is half the contract: a smart constructor with no test for what it does to a bad value is an unproven invariant. So an opaque scalar refined from `Double` — say a `Percent` constrained to `[0.0, 1.0]` and built through `Percent.of` — pins its laws with `checkAll` *and* pins the constructor's rejection of `NaN` and out-of-range input in `PercentSuite`. Test the rules a value obeys, and test what the constructor does when something tries to build an illegal one.

## Structure and naming

- **A test file is one `class` extending `munit.FunSuite`** (or `munit.ScalaCheckSuite` when it carries properties — `ScalaCheckSuite` extends `FunSuite`, so example and property tests live in the same class). Each case is a `test("...") { ... }` call whose name is a sentence about the behavior, not the method: `test("combine is commutative on two verdicts")`, not `test("combine")`.
- **One behavior per test, arrange-act-assert in order**, the act step a single call to the unit under test. Keep computation out of the test body — no branching or loops that derive the expected value; a `want` you have to compute is a `want` that can be wrong the same way the code is.
- **Group by the type under test, not by the layer.** The pure core (the value types, the combiner, the ADTs) gets pure suites with no effect runtime; the pipeline, the store, and the model-boundary adapters get their own suites. Name suites `XxxSuite` for the type `Xxx`.

## Assertions and failure messages

- **Use munit's `assertEquals(obtained, expected)`** — obtained first, expected second; munit prints a red/green diff on mismatch. Do not reach for raw `assert(a == b)` where an equality is meant: `assert` prints only "false", `assertEquals` prints both sides. Reserve `assert(cond, clue)` for genuine predicates, and attach a `clue(...)` so the failure names the value.
- **Assert on returned values and final state, not on interactions**, wherever collaborators are pure and fast — this is the classicist default `craft-tdd.md` sets. Pin interaction order only where the protocol itself is the unit under test (for example, that a node emits its calls in sequence).
- **`assertEquals` compares by `==`, so the types under test need a lawful `equals`.** Prefer `case class`/`enum` (structural equality for free) and `opaque type`s whose underlying value compares correctly. Never compare `Double` values with `==`; assert within a tolerance with `assertEqualsDouble(obtained, expected, delta)`.

## Fixtures, lifecycle, and no shared mutable state

- **Construct fresh state inside each test, or with a per-test `FunFixture`.** The default house position: a `val` in the suite body is shared across every test in the class, so any mutation leaks between cases and makes failures order-dependent. Immutable fixtures (a sample `Entry`, a fixed config) may be suite-level `val`s; anything mutable or owning a resource must not be.
- **For per-test resources use `FunFixture[T]`** with explicit setup and teardown, then `fixture.test("name") { resource => ... }`. Each test gets its own `T`; teardown runs even on failure. Compose two with `FunFixture.map2`.

```scala
val store: FunFixture[EventStore] = FunFixture(
  setup = _ => EventStore.inMemory(),     // one fresh store per test
  teardown = s => s.close()               // runs even if the test fails
)

store.test("records an entry and counts it") { store =>
  store.record(sampleEntry)
  assertEquals(store.count, 1)
}
```

- **Do not initialize resources in the class constructor or a suite-level `var`.** A suite may be instantiated for test discovery without running anything; a constructor-side resource then leaks. Reusable resources go through a `Fixture[T]` (override `beforeEach`/`afterEach`, register in `munitFixtures`); shared-once-per-suite setup goes through `beforeAll`/`afterAll`, never a mutated field.
- **Tests must be independently runnable and order-independent.** A test that only passes after another ran is a shared-state bug — fix the state, not the order. Do not rely on suite-level `var` accumulation.

## Effects under test

- **The pure core is pure — test it directly, with no IO runtime.** The value types, the combiner, and the ADT operations return values; assert on the values. This is most of the suite and must stay the fast, hermetic majority.
- **Where a unit returns `cats.effect.IO`, run it through munit-cats-effect, never `unsafeRunSync()` scattered in test bodies.** Return the `IO[Unit]` from the test and let the integration evaluate it. Do not bridge an `IO` to a `Future` or block on it to "make the assertion fit" — that mixing is the fragmentation `scala-concurrency.md` bans. Keep effectful suites few; push logic into the pure core so it can be example- and property-tested without a runtime.

## Property-based testing — the default for lawful code (ScalaCheck)

Property tests assert an invariant over a large generated input space and **shrink** any failure to a minimal counterexample, so they catch the cases you would never enumerate by hand. ScalaCheck is the house engine — the Scala equivalent of Go's `rapid` and Python's Hypothesis. For a type-class instance or a lawful combiner, **the laws are the specification**, so a property is the primary test of a combiner and an example test is the regression pin beside it.

- **Write a property with `property("...") = forAll { ... }`** in a `ScalaCheckSuite`. Favor strong properties — algebraic laws, a round-trip (`decode(encode(x)) == x`), or a comparison against a slow-but-obvious oracle — over trivially-true ones. Inside the body, prefer munit's `assertEquals` to a bare `Boolean`: it reports which side diverged.

```scala
import munit.ScalaCheckSuite
import org.scalacheck.Prop.forAll

class MergeSuite extends ScalaCheckSuite:

  property("combine is associative") {
    forAll { (a: Verdict, b: Verdict, c: Verdict) =>
      assertEquals(
        combine(combine(a, b), c),
        combine(a, combine(b, c))
      )
    }
  }

  property("combine is commutative") {
    forAll((a: Verdict, b: Verdict) => combine(a, b) == combine(b, a))
  }
```

### Type-class laws via `discipline` — prefer this for any instance

When an operation *is* a standard type class — a merge combiner as a `CommutativeMonoid` (or `BoundedSemilattice`), a value's `Eq`, a `Validated` `Applicative`, an ordering as `Order`, a numeric domain type as a `CommutativeRig` or `Semiring` — do not hand-write its laws. Give it the instance and check the instance against the prebuilt law set with `discipline`'s `checkAll`. The stock bundles are complete and correct; a hand-rolled `forAll("associative")` can be subtly wrong or silently miss a law the bundle covers (left versus right identity, `combineN` consistency, absorption). The kernel and cats laws come from `cats-laws` (`CommutativeMonoidTests`, `BoundedSemilatticeTests`, `EqTests`, the `Applicative` laws); the lattice and semiring laws come from `algebra-laws` (`LatticeTests`, `BoundedLatticeTests`, `RingTests.semiring`); `discipline-munit`'s `DisciplineSuite` runs them.

```scala
import munit.DisciplineSuite
import cats.kernel.laws.discipline.{BoundedSemilatticeTests, EqTests}

class VerdictLawsSuite extends DisciplineSuite:
  // requires given Arbitrary[Verdict], given Eq[Verdict], given BoundedSemilattice[Verdict] in scope
  checkAll("Verdict.boundedSemilattice", BoundedSemilatticeTests[Verdict].boundedSemilattice)
  checkAll("Verdict.eq",                 EqTests[Verdict].eqv)
```

`checkAll` registers one named munit test per law, so a failure points at the exact law — `boundedSemilattice.associative`, `semilattice.idempotent` — without your writing any of them. The instance is the design; the law check proves it lawful. This is the law-first red-green for an algebra: write the `checkAll` against the type class the operation must satisfy, watch it fail, implement the instance until every law passes.

**For the domain-specific laws no stock bundle carries** — an absorbing element a combiner pins (`combine(top, x) = top`), a structure-preserving map into a rendering carrier, an involution that defines a negation — author a custom `discipline.Laws` with its own `RuleSet` and `checkAll` it the same way:

```scala
import org.typelevel.discipline.Laws
import org.scalacheck.Prop.forAll
import cats.syntax.eq.*

trait MergeLaws[A] extends Laws:
  def A: Merge[A]
  def annihilator(using Arbitrary[A], Eq[A]): RuleSet = new DefaultRuleSet(
    name   = "merge",
    parent = None,
    "top annihilates" -> forAll((x: A) => A.combine(A.top, x) === A.top)
  )
```

Verify the absorbing element and the homomorphism direction against your specification before pinning them — state the algebra's actual laws, never assume them from memory.

### The laws a combiner must carry

A merge combiner is a commutative monoid over its domain (a `BoundedSemilattice` if it is idempotent), and it may pin an absorbing element on top. These are the laws *The Science of Functional Programming* names — semigroup associativity (§8.3.3) and the monoid identity law (§8.3.4) — applied to your own operations. When the combiner is given as that type class, the associativity, commutativity, identity, and idempotence laws below come from the `checkAll` above for free; keep the explicit `forAll` form here for the annihilator (until it is folded into the custom `RuleSet`) and for invariants that are not type-class laws. Each is a property; together they are the contract:

- **Associativity** — `combine(combine(a, b), c) == combine(a, combine(b, c))`. The order of folding a batch must not change the result.
- **Commutativity** — `combine(a, b) == combine(b, a)`. Which input arrived first must not change the result.
- **Identity** — `combine(a, empty) == a` and `combine(empty, a) == a`, where `empty` is the no-information unit (`Verdict.Unknown`).
- **The annihilator** — the absorbing element absorbs: `combine(a, top) == top` (state the absorbing element your algebra actually pins — for `Verdict` it is `Conflict`; verify it against your spec, do not assume one from memory).
- **Idempotence** — `combine(a, a) == a`, where the same input presented twice and double-counting would be a fault. Confirm the algebra actually claims idempotence before pinning it — it is a real, falsifiable property of this combiner, not a given.

Pin each law as its own named property so a failure names the law that broke. Where several conditions form one law, label them and conjoin with `&&` so the report points at the failing conjunct:

```scala
property("empty is a two-sided identity for combine") {
  forAll { (a: Verdict) =>
    (combine(a, Verdict.Unknown) == a) :| "right identity" &&
    (combine(Verdict.Unknown, a) == a) :| "left identity"
  }
}
```

### Generators

- **Define a `Gen[T]` for each domain type and expose it as an `Arbitrary[T]`** so `forAll` draws it implicitly. Build compound generators with a `for`-comprehension over `Gen.choose`, `Gen.oneOf`, and `Gen.const`; constrain at generation time, not by discarding inside the body.

```scala
import org.scalacheck.{Arbitrary, Gen}

val genEntry: Gen[Entry] =
  for
    account <- Gen.oneOf("cash", "ar", "revenue")
    cents   <- Gen.choose(-100_000L, 100_000L)
  yield Entry(account, cents)

given Arbitrary[Entry] = Arbitrary(genEntry)
```

- **Constrain generators at generation time** with `Gen.choose` / `Gen.oneOf` / `suchThat` rather than drawing wide and discarding inside the property — discards bleed into `maxDiscardRatio` and can starve the run. Keep generators total and pure: no wall-clock, no real IO, no ambient `scala.util.Random`; the only randomness is ScalaCheck's seeded source.
- **Use `classify`/`collect` to confirm the distribution covers the corners** — that the `Verdict` generator actually produces every case (`Unknown`, `Pass`, `Fail`, `Conflict`) and not just the common two. A property that never reaches a corner is green for the wrong reason.

### Determinism — no flakiness

A reproducible build needs reproducible tests, and a flaky property is a broken property.

- **A property must be a pure function of its drawn inputs.** No clock, no filesystem, no network, no shared `Random`. If the unit needs a clock or a store, inject a deterministic double (`craft-tdd.md`, "only mock what you own").
- **ScalaCheck runs from a seed; pin it so a green run stays green and a red one reproduces.** When a property fails, munit prints the seed; fix it for the suite by overriding `scalaCheckInitialSeed` (a base-64 `Seed` string) so the run is identical machine to machine, and tune the budget with `scalaCheckTestParameters`:

```scala
override def scalaCheckInitialSeed = "x9aQ2...base64-seed..."   // reproduce a found counterexample

override def scalaCheckTestParameters =
  super.scalaCheckTestParameters
    .withMinSuccessfulTests(500)   // laws deserve a wide sample
    .withMaxDiscardRatio(5)
```

- **When a property finds a counterexample, copy the minimized case into a named example test before you fix the code** — the law property covers the space, the example pins this exact regression forever. Then fix the code and watch both go green.
- **Reach for `forAllNoShrink` only to diagnose a misleading shrink**, never as the committed form — committed properties keep shrinking on so failures report the minimal counterexample. If shrinking lands on an invalid input, supply a `suchThat`-guarded `Shrink` rather than disabling it.

## Coverage

- **Measure with scoverage (`sbt coverage test coverageReport`) and treat it as a signal, not a target.** Never write assertion-free tests, or call a function with no `assert`, to raise the number — a covered line with no assertion is untested. The differential gate scores coverage against the merge-base; the way to keep it up is more behavior pinned, not more lines touched.
- **Gate slow or external suites** (anything hitting a live model, a real store, or the network) behind a tag or a separate sbt configuration, keeping the default `sbt test` fast and hermetic — the same split `craft-tdd.md` draws between unit, integration, and end-to-end.

## Anti-weakening (what the differential gate forbids)

Treat any of these versus the merge-base as test-suite weakening — do not introduce them:

- A test or property deleted with no equivalent replacement, or a previously-running case newly disabled with `.ignore`, `assume(false, ...)`, `munitIgnore`, a removed registration, or a commented-out body.
- A net drop in assertion sites for a suite (removed `assertEquals` / `assert` / `assertEqualsDouble` / `intercept` / labeled `:|` conjuncts), or a `forAll` law narrowed to a fixed example that no longer covers the space.
- A `want` loosened to a wildcard or an always-true comparison; an `assertEquals` turned into a bare `assert(true)`; an exception assertion (`intercept[E]`) deleted; an error swallowed with `.toOption` or a discarded `Either` where it was previously asserted.
- `minSuccessfulTests` lowered, `maxDiscardRatio` raised to mask a starving generator, or a property's generator widened so the hard corners (the `Conflict` and `Unknown` cases, a boundary amount, an empty batch) are no longer reached.
- A failing assertion downgraded to a `println`/`clue`/log so the failure becomes invisible, or a property switched to `forAllNoShrink` and committed (hides the minimal counterexample).
- A committed regression example (the minimized counterexample copied from a past property failure) deleted — that re-admits a known-bad input.

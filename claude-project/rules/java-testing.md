---
paths:
  - "**/*Test.java"
  - "**/*Tests.java"
  - "**/*Suite.java"
  - "**/src/test/**/*.java"
---

# Java testing

How to write Java tests: JUnit 5 (Jupiter) suite structure, a fresh test instance per method with no shared mutable state, AssertJ fluent assertions that read in the domain's words, and deterministic property-based testing with jqwik — one shared generator provider per module, corners pinned deliberately, and a distribution property that proves the generator reaches them. Sources: the JUnit 5 user guide (`@Test`, `@Nested`, `@DisplayName`, `@ParameterizedTest`, the per-method lifecycle, the conditional-execution annotations), the AssertJ documentation (`assertThat`, `as`, `assertThatThrownBy`, the type-specific assertions), and the jqwik user guide (`@Property`, `@ForAll`, `@Provide`, `Arbitraries`, `@Domain` / `DomainContextBase`, `Statistics`, shrinking, and seeds). The floor is Java 21 — records and sealed types carry the value-model invariants these tests pin. Unlike the Scala layer, Java has no stock law bundle, so the algebraic laws below are hand-written properties rather than a `checkAll`.

> See `java-types.md` for the records and sealed ADTs whose invariants these tests pin, `java-errors.md` for the exceptions the negative-space tests assert, `craft-tdd.md` for red-green-refactor and "listen to the tests", and `craft-xunit.md` for the arrange-act-assert and one-behavior-per-test mechanics this rule specializes.

## The residue this rule carries

The governing principle is stated in `java-types.md` ("encode what's cheap, test the residue"): the type encodes the invariants it cheaply can, and these tests carry the rest. The obligation that lands here is **two-sided** — for every invariant a type cannot state, write the property over valid input *and* the test that the validating constructor refuses illegal input. The negative space is half the contract. So a `record Percent(double value)` whose compact constructor throws on `NaN` or out-of-range input gets a property over `[0.0, 1.0]` values *and* an `assertThatThrownBy(() -> new Percent(1.5))` that pins the rejection. Test the rules a value obeys, and test what the constructor does when something tries to build an illegal one.

## Structure and naming

- **A test method is a `@Test` (or `@ParameterizedTest`) whose name states a behavior, not a method.** Attach a `@DisplayName` sentence — `@DisplayName("combine is commutative on two verdicts")`, not a bare `combine()`. Group related cases under a `@Nested` inner class so the report reads as an outline.
- **One behavior per test, arrange-act-assert in order**, the act step a single call to the unit under test. Keep computation out of the test body — a `want` you have to compute can be wrong the same way the code is.
- **Reach for `@ParameterizedTest` for table cases** rather than a hand-unrolled loop or copy-pasted methods; feed rows with `@CsvSource` / `@MethodSource` so each row is its own reported case.
- **Group by the type under test, not by the layer.** The pure core (value types, the combiner, the ADTs) gets pure suites with no framework fixtures; the boundary adapters get their own.

```java
@ParameterizedTest(name = "{0} + {1} = {2}")
@CsvSource({ "PASS, PASS, PASS", "PASS, FAIL, CONFLICT", "PASS, UNKNOWN, PASS" })
void combinesTableCases(Verdict a, Verdict b, Verdict expected) {
    assertThat(combine(a, b)).isEqualTo(expected);
}
```

## Assertions and failure messages

- **Use AssertJ's `assertThat(actual)...` with a domain-language `.as(...)` description**, not a bare JUnit `assertEquals`. A failure message should read in the domain's words, so the report says what broke, not just which two values differ: `assertThat(combine(a, b)).as("fold order must not change the verdict").isEqualTo(...)`.
- **Assert a thrown exception with `assertThatThrownBy(() -> ...)`**, chaining `.isInstanceOf(...)` and `.hasMessageContaining(...)`; never a `try/fail/catch` by hand. Assert on returned values and final state, not on interactions, wherever collaborators are pure — pin call order only where the protocol is itself the unit under test.
- **Compare doubles with a tolerance** — `assertThat(x).isCloseTo(expected, within(1e-9))` — never `isEqualTo` on a `double`. Records give structural equality for free; prefer them (and enums) so `isEqualTo` compares by value.

## Fixtures, lifecycle, and no shared mutable state

- **JUnit Jupiter creates a fresh test instance per method (the default `Lifecycle.PER_METHOD`), so construct mutable state inside the test or in a `@BeforeEach` field** — never a shared `static` field and never `Lifecycle.PER_CLASS` with mutation. Prefer constructor or field injection of collaborators over static setup; a `static` holding a store or a client leaks between tests and makes failures order-dependent.
- **Immutable fixtures may be `private final` fields**; anything mutable or owning a resource is built per test and torn down in `@AfterEach`, which runs even on failure. Tests must be independently runnable and order-independent — a test that only passes after another ran is a shared-state bug; fix the state, not the order.

## Property-based testing — the default for lawful code (jqwik)

A property asserts an invariant over a large generated input space and **shrinks** any failure to a minimal counterexample, so it catches cases you would never enumerate. For a combiner or a lawful value, the laws *are* the specification, so a property is the primary test and an example test is the regression pin beside it. Write it as `@Property void ...(@ForAll ... )` and assert with AssertJ inside.

**The laws a combiner must carry** — associativity, commutativity, a two-sided identity, the annihilator (the absorbing element your algebra actually pins — verify it against the spec, do not assume one), and idempotence where the same input twice must not double-count. Java has no `checkAll`, so pin each as its own named property so a failure names the law that broke:

```java
@Property
void combineIsAssociative(@ForAll Verdict a, @ForAll Verdict b, @ForAll Verdict c) {
    assertThat(combine(combine(a, b), c))
        .as("fold order must not change the result")
        .isEqualTo(combine(a, combine(b, c)));
}
```

### Generators

- **Collect the generators in one shared provider per module** — a class extending `net.jqwik.api.domains.DomainContextBase` with `@Provide Arbitrary<T>` methods, applied to a suite with `@Domain(CreditDomain.class)`. One canonical generator per type, shared across every suite that tests it, so a corner pinned once is pinned everywhere and two suites cannot drift into different distributions for the same type.
- **Constrain generators at generation time** with `Arbitraries.of` / `.filter` / `Combinators.combine`, not by drawing wide and discarding in the body. Keep them total and pure — no clock, no real IO, no ambient `Random`; the only randomness is jqwik's seeded source.
- **Pin the hard corners with `Arbitraries.frequency` / `frequencyOf`**, giving each boundary — empty, zero, the top, the contradiction — its own weighted branch beside the bulk draw, so every run reaches them rather than only on a lucky seed. This is what makes the distribution property below pass for the right reason.

```java
class CreditDomain extends DomainContextBase {
    @Provide Arbitrary<Verdict> verdicts() {
        return Arbitraries.frequency(               // corners weighted in deliberately
            Tuple.of(1, Verdict.CONFLICT),          // the contradiction corner
            Tuple.of(1, Verdict.UNKNOWN),           // the empty value
            Tuple.of(3, Verdict.PASS),
            Tuple.of(3, Verdict.FAIL));
    }
}
```

- **Commit a `Statistics` distribution property that asserts the generator reaches every corner.** Its body is always true, so its only effect is the coverage check — a silently-narrowed generator (a corner that stops being produced) then fails loudly instead of going quietly green. This is the guard the anti-weakening rule against generator-narrowing depends on.

```java
@Property
void theGeneratorReachesEveryCorner(@ForAll Verdict v) {
    Statistics.label("corner").collect(v.name());
    Statistics.coverage(c -> {
        c.check(Verdict.CONFLICT.name()).count(n -> n > 0);   // the contradiction is drawn
        c.check(Verdict.UNKNOWN.name()).count(n -> n > 0);    // the empty value is drawn
    });
}
```

### Determinism — no flakiness

- **A property must be a pure function of its drawn inputs** — no clock, filesystem, network, or shared `Random`. Inject a deterministic double where the unit needs a collaborator (`craft-tdd.md`, "only mock what you own").
- **jqwik runs from a seed and re-runs the last failing one; pin it to reproduce a counterexample** with `@Property(seed = "...")`, and tune the budget with `tries` (default 1000). When a property finds a counterexample, copy the minimized case into a named `@Test` before fixing the code — the property covers the space, the example pins this regression forever.
- **Leave shrinking on** — the default `ShrinkingMode.BOUNDED` reports the minimal counterexample. Never commit `ShrinkingMode.OFF`; use it only to diagnose a misleading shrink, then revert.

## Coverage

- **Measure with JaCoCo and treat it as a signal, not a target.** Never write an assertion-free test, or call a method with no `assertThat`, to raise the number — a covered line with no assertion is untested. The differential gate scores coverage against the merge-base; keep it up with more behavior pinned, not more lines touched.
- **Gate slow or external suites so the default run stays fast and hermetic.** A permanent `@EnabledIfEnvironmentVariable(named = "RUN_LIVE_STORE", matches = "1")` whose default keeps the suite hermetic is a standing fixture, not a disabled test; run it explicitly with the flag set. Use a stable `RUN_LIVE_*` naming convention.

## Anti-weakening (what the differential gate forbids)

Treat any of these versus the merge-base as suite weakening — do not introduce them:

- A test or property deleted with no equivalent replacement, or a previously-running case newly `@Disabled`, its `@Test` annotation removed, or its body commented out. `@Disabled` is the gate's business, not a habit — it is a Check-D weakening; disable only with a tracked reason, never to get to green.
- A net drop in assertion sites (removed `assertThat` / `assertThatThrownBy` / `@ParameterizedTest` rows), or a property narrowed to a fixed example that no longer covers the space.
- A `@Property(tries = N)` lowered, `ShrinkingMode.OFF` newly committed, or a generator widened / its `frequency` weights dropped so the hard corners are no longer reached.
- An assertion loosened to an always-true comparison, an exception assertion deleted, or a failing assertion downgraded to a log so the failure becomes invisible.
- A committed regression example — the minimized counterexample copied from a past property failure — deleted, which re-admits a known-bad input.

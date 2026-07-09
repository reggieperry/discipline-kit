---
name: xunit-test-patterns-meszaros
description: "xUnit Test Patterns (Meszaros 2007) — fine-grained test-double taxonomy, named test-smell catalog, 13 principles, fixture strategies, five-step roadmap. Builds on the existing GOOS/Fowler testing memories rather than replacing them."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

Read from "xUnit Test Patterns" by Gerard Meszaros (2007; 948 pages; extracted Chapters 2, 5, 11, 14 + List of Patterns; chapters 15–25 are the reference catalog and weren't read in full). Meszaros is the originator of the test-double taxonomy and the named test-smell vocabulary that GOOS / Fowler / pytest documentation all cite. The 13 principles are the chapter-5 rules; the four-phase test structure is the chapter-7 anatomy; the five-step roadmap is the chapter-14 synthesis.

**Why:** the existing testing memories ([[tdd_listening]], [[mock_discipline]], [[test_discipline]], [[refactoring_smells]]) draw on Meszaros indirectly via GOOS and Fowler but don't use the crisp vocabulary. Naming a smell precisely ("Fragile Test" vs "Erratic Test" vs "Obscure Test") makes the corrective conversation about a PR or a test artifact much shorter. The fine-grained test-double taxonomy (Dummy / Stub / Spy / Mock / Fake) closes ambiguity that "mock" alone leaves open. The principles overlap with GOOS but Meszaros's framing is independent and worth holding alongside.

**How to apply:** when reviewing test code (in PRs or any test artifact), name the smell or recommend the pattern by Meszaros's term. When designing a test, walk the five-step roadmap. When the test surface for a piece of work is ambiguous, the principles (in priority order: front door, communicate intent, independent tests, isolate SUT, one condition per test, four-phase structure) are the discriminator.

## The five Test Doubles (taxonomy)

Meszaros's fine-grained taxonomy. The umbrella term is **Test Double**; the five concrete types each have a specific job. Confusing them is the source of most test-design debates.

| Type | Purpose | When to use |
|---|---|---|
| **Dummy Object** | Placeholder passed as an argument; never actually used. | When the SUT's signature requires a parameter the test does not exercise. In dynamic Python, often `None` or `object()` suffices. |
| **Test Stub** | Replaces a DOC to control the SUT's *indirect inputs*. Returns canned responses. Two sub-types: **Responder** (returns valid/invalid values), **Saboteur** (raises exceptions to drive error paths). | When the SUT calls into a DOC whose return value must vary across test cases. |
| **Test Spy** | Stub that *records* calls so the test can assert on them after exercise. Implements **Behavior Verification** via post-hoc inspection. | When the SUT's side effects on a DOC are what the test cares about, but you can assert after the exercise phase. |
| **Mock Object** | DOC replacement loaded with *expectations* before exercise; asserts during exercise and fails immediately on unexpected call. Implements Behavior Verification via expectation matching. | When the test needs to fail immediately on the wrong call (e.g., security-critical, transaction-critical sequences). Heavier than Test Spy; couples the test to the call sequence. |
| **Fake Object** | Working alternative implementation of the DOC, lighter than the real thing (e.g., in-memory database). | When the real DOC is slow, unavailable, or has side effects the test cannot tolerate, AND the test cares about the DOC's semantics, not just its calls. |

A **Hard-Coded Test Double** has its responses baked into the subclass; a **Configurable Test Double** accepts a setup phase that feeds it values. Configurable is the v1 default; hard-coded is appropriate when the responses are universal across all tests of one suite.

The taxonomy refines [[mock_discipline]]'s GOOS rule "mock peers not internals." With Meszaros's vocabulary: a peer DOC gets a Test Stub (for indirect inputs), a Test Spy (for indirect outputs the test wants to assert on after), or a Mock Object (for indirect outputs where the call sequence is part of the invariant). Internal collaborators are never replaced by any Test Double.

## The four-phase test structure (Chapter 7)

Every test has four distinct sequential phases. Meszaros makes this universal; pytest's setup / test-body / teardown convention is a thin disguise over the same anatomy.

1. **Setup** — build the fixture (test data, SUT, any Test Doubles, install Doubles into SUT).
2. **Exercise** — call the SUT with the inputs the test cares about. *One* call to the SUT, not a sequence — if you need a sequence, you're testing multiple concerns.
3. **Verify** — assert on direct outputs (return values), post-test state, and indirect outputs (Spy / Mock assertions).
4. **Teardown** — tear down the fixture. Prefer **Implicit Teardown** (pytest's `yield` fixtures with `try/finally`) over in-line teardown. Best is **Fresh Fixture** per test so teardown is just garbage collection.

The phases should be visible at a glance — blank lines between them, comments `# Arrange`/`# Act`/`# Assert` if useful but usually unnecessary. Alternating exercise/verify calls is a smell (Eager Test).

## Named test smells

The five most actionable smells from Chapter 2 + Chapter 15. Cite by name when flagging in PR reviews or test output.

- **Obscure Test** — cannot understand at a glance what behavior is being verified. Sub-causes: **Mystery Guest** (fixture data appears from nowhere), **Eager Test** (verifies many things in one test), **Irrelevant Information** (constants and helpers that distract from the test's concern). Fix: extract Creation Methods + Custom Assertions + Test Utility Methods; reduce the test body to "given X, when Y, then Z" in one screen.
- **Conditional Test Logic** — `if`/`for`/`try` in the test body. Logic the test takes makes the test itself testable, which is the failure mode. Fix: parameterize via pytest fixtures or split into separate Test Methods. Loops are usually a sign of a missing Parameterized Test.
- **Fragile Test** — passes today, fails on unrelated change tomorrow. Sub-causes: **Interface Sensitivity** (test couples to UI / API shape that doesn't matter), **Behavior Sensitivity** (test fails on SUT changes that should be safe), **Data Sensitivity** (test depends on shared data that drifted), **Context Sensitivity** (test depends on environment, clock, files, network). Fix: Fresh Fixture per test; replace Shared Fixture with Fake Object; isolate SUT via Test Double for ambient dependencies.
- **Erratic Test** — sometimes-passes, sometimes-fails on the same code. Sub-causes: **Interacting Tests** (Shared Fixture pollution), **Test Run Wars** (parallel runs against shared resources), **Unrepeatable Tests** (depend on clock/randomness without seeding). Fix: per-test isolation; deterministic clock via dependency injection; seeded RNG.
- **Assertion Roulette** — multiple assertions in one test, with no Assertion Messages, so failure log doesn't tell you which assertion failed. Fix: Assertion Messages on every assertion, OR split into Single-Condition Tests, OR use a Custom Assertion that compares whole objects and reports the first mismatched field.

Two more worth naming but lower-frequency:
- **Slow Tests** — > 30s and the developer stops running them per change. Fix: Fake Object for slow DOCs; in-memory database; reduce per-test fixture size to Minimal Fixture.
- **Frequent Debugging** — needing the debugger to figure out why a test failed means the test isn't isolating the failure. Sign of coverage gap or Eager Test.

## The 13 principles (Chapter 5)

In priority order (the order Meszaros uses, which is also the order I'd suggest when prioritizing fixes):

1. **Write the Tests First.** TDD; production code falls out of tests, not the other way around. Already in [[tdd_listening]].
2. **Design for Testability.** When TDD is skipped, this becomes load-bearing. Already in [[oo_style]] via the dependencies-in-constructor rule.
3. **Use the Front Door First.** Test through the public interface with State Verification. Use Behavior Verification (Spy / Mock) only when State Verification cannot express the invariant. Back Door Manipulation (peeking at internals) is a last resort and tightly couples the test to implementation.
4. **Communicate Intent.** Tests are also documentation. "Single-Glance Readable" — the test should read in one screen and the intent should be obvious. Extract Test Utility Methods with Intent-Revealing Names. Tests longer than ~10 lines are a smell.
5. **Don't Modify the SUT.** No `if testing then ...` branches in production code. If the SUT needs Test Hooks, the design is wrong — fix the design.
6. **Keep Tests Independent.** Any test can run alone. Fresh Fixture per test, not Shared Fixture, unless the fixture is read-only.
7. **Isolate the SUT.** Use Test Doubles to replace DOCs whose behavior the test isn't verifying. Inject the dependencies (Dependency Injection / Lookup), don't reach into singletons.
8. **Minimize Test Overlap.** Each test condition is covered by exactly one test — no more, no less. Two tests that fail together for the same reason are duplication.
9. **Minimize Untestable Code.** Untestable code (GUI logic, multithreading, untestable Test Methods themselves) gets refactored into a **Humble Object** — extract logic into a testable component that the untestable shell delegates to.
10. **Keep Test Logic Out of Production Code.** No `if testing then` branches; no debug flags that change behavior; no environment-sniffing.
11. **Verify One Condition per Test.** Single-Condition Test. One assertion is fine; multiple assertions on the same logical condition (e.g., asserting all fields of a returned object) are also fine. Verifying two distinct behaviors in one test is the smell.
12. **Test Concerns Separately.** When a method handles multiple concerns, test each concern in its own test so failures point at the broken concern, not "something in this method."
13. **Ensure Commensurate Effort and Responsibility.** The effort to write/maintain a test should not exceed the effort to write the SUT. If it does, the SUT needs to be designed for testability or the test infrastructure needs work — but the *test* shouldn't bear the load.

## Fixture strategies (Chapters 8 + 9)

A **Fixture** is the state the SUT needs to be in before exercise. Strategies form a hierarchy:

- **Fresh Fixture (Transient)** — each test builds its own, garbage-collected after. *Default v1 choice.*
- **Fresh Fixture (Persistent)** — each test builds its own in a persistent store (database row, file). Needs explicit teardown.
- **Shared Fixture** — multiple tests reuse one fixture. *Avoid unless tests are read-only.* Standard cause of Interacting Tests + Fragile Tests.
- **Minimal Fixture** — the smallest possible fixture for each test. *Prefer this.* If a test only needs an order with one line item, don't build an account + customer + 10 orders.
- **Standard Fixture** — same fixture shape across many tests. Tempting for DRY but yields Fragile Fixture: changing the shape breaks N tests at once.

Setup styles:
- **In-line Setup** — fixture built inside the test method. Most explicit. Use for tests with unusual fixtures.
- **Delegated Setup** — test calls a Creation Method (e.g., `_make_order(...)`). The default for shared fixture shapes.
- **Implicit Setup** — fixture built in pytest's `fixture` decorator (or xUnit's `setUp`). Use when the fixture is identical across many tests in the same class.
- **Lazy Setup** — fixture built in the first test that needs it. Pytest's `scope="session"` fixtures are this shape.

## The five-step roadmap (Chapter 14)

Meszaros's synthesis for "how to learn / teach test automation." Also useful as a default order of operations when designing the test surface for a new module:

1. **Exercise the happy path** — one Simple Success Test that calls the SUT without assertions; passes if it doesn't crash. Build the fixture; run the method.
2. **Verify direct outputs of the happy path** — add assertions on return values and post-test state. Now it's a Self-Checking Test.
3. **Verify alternative paths** — vary arguments + vary pre-test state + control indirect inputs via Test Stubs (Responder for valid values, Saboteur for exceptions).
4. **Verify indirect output behavior** — use Test Spies or Mock Objects to assert on outgoing calls when State Verification can't capture the invariant.
5. **Optimize execution and maintainability** — make slow tests fast (Fake Object, Minimal Fixture); make Obscure Tests clear (Custom Assertion, Creation Method); reduce Test Code Duplication.

The roadmap matches how I'd add coverage to any module: happy path first, then assertions, then alternative paths, then behavior verification, then cleanup.

## When this contradicts existing memories

- [[mock_discipline]] (GOOS) uses "mock" generically. Meszaros's vocabulary is sharper. Resolution: use Meszaros's terms (Stub / Spy / Mock / Fake) and treat [[mock_discipline]]'s "mock peers not internals" rule as referring to *any* Test Double.
- [[test_discipline]]'s "fresh fixtures, probe boundaries, verify diagnostics" all overlap with the principles above. Meszaros adds the named smell vocabulary for when the fresh-fixture rule is violated.
- [[refactoring_smells]] is Fowler's catalog for production code; Meszaros's smell catalog (Obscure Test, Fragile Test, Erratic Test, etc.) is the test-code companion.

## Patterns referenced but not extracted in detail

The book's Parts II and III (chapters 15–25) document each pattern and smell with code examples. I have the List of Patterns (~75 named patterns + page references) but not the detailed entries. For deep-dive on a specific pattern (e.g., the exact mechanics of Mock Object setup vs Test Spy retrieval), read the page reference from the List of Patterns directly. Notable patterns I haven't extracted but may need later: Database Sandbox (650), Suite Fixture Setup (441), Transaction Rollback Teardown (668), Layer Test (337), Humble Object (695).

## Cross-references

- [[tdd_listening]] — GOOS TDD discipline; principle #1 of the 13
- [[mock_discipline]] — GOOS mock rules; refined by the 5-type taxonomy above
- [[oo_style]] — peer / message / context-independence; basis for Design for Testability (#2)
- [[test_discipline]] — readability / fresh fixtures / boundaries; the principles above are the canonical version
- [[refactoring_smells]] — Fowler's production-code smells; the test-smell catalog above is the sibling
- [[coding_methodology]] — synthesis memory; this entry should be cross-linked from it

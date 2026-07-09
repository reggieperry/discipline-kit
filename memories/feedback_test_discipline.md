---
name: test-discipline-readability-fixtures-boundaries
description: How to write tests that pull their weight. Names describe behavior; canonical setup-exercise-verify shape; fresh fixtures per test; probe boundaries; verify diagnostics. Synthesized from GOOS Ch 5/21-23 and Fowler Refactoring 2nd ed Ch 4.
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

A test suite that's hard to read or slow to run will be ignored. These are the discipline rules that keep test code maintainable as the codebase grows.

**Why:** the local `[[feedback_claims_need_tests]]` finding showed that prose claims drift from reality without tests behind them. A large test suite is an asset only if it remains readable, fast, and trustworthy. These rules guard that.

**How to apply:** every test should pass the checks below. When a test fails them, fix the test or the production code it surfaces — not by adding workarounds.

## Test names describe behavior, not methods

A test name should describe how the object behaves in the scenario being tested. `test_bid_accepted_when_below_stop_price` is good; `test_calculate_bid_price` is bad. The first survives refactoring; the second breaks when you rename the method or split it.

In Python: `def test_<noun>_<verb>_<condition>` reads cleanly. Group related tests in a class named after the scenario, not the SUT method.

## Canonical test shape: arrange, act, assert

Every test has three phases:

```
arrange (setup the fixture and any stubs)
act     (call the method under test — usually one line)
assert  (verify the outcome)
```

Sometimes called setup-exercise-verify, or given-when-then. The structure should be visible in the test body. If the act phase has more than one line, the test is probably exercising too much, or the SUT has a workflow that should be its own method.

## Fresh fixture per test

Set up a fresh fixture in a `setup` / `@pytest.fixture` / `beforeEach` block. Don't share state across tests; non-determinism caused by shared state is one of the most common sources of flaky-test misery (Fowler, Refactoring Ch 4).

If a fixture is genuinely expensive to construct, share it carefully and assert that tests don't mutate it. The default is fresh.

## Probe the boundaries

Tests should hit the happy path first, then deliberately the boundaries — empty collections, zero, negative numbers, strings where numbers are expected, types where collections are expected. Fowler: *"Think of the boundary conditions under which things might go wrong and concentrate your tests there."*

Adopt an *adversarial* mindset for boundaries: "How would I break this code if I were trying to?" That mindset surfaces test cases the happy-path mindset misses.

## Verify the failing test fails

Before writing the production code, run the test and observe it fail. Two checks:
1. It fails for the right reason. If it fails for an unexpected reason, your test setup or assumption is wrong.
2. The diagnostic message explains the failure clearly. If it doesn't, improve the test or the production code's error reporting *before* writing the fix. A year from now, that message is the only clue.

For existing code, before trusting a passing test, *inject a fault* into the production code and confirm the test fails. *"Always make sure a test will fail when it should."* (Fowler.)

## Few assertions, one verify per test (rule of thumb)

Each test should usually have one verification statement. When the first verification in a test fails, subsequent verifications don't run — useful information may be hidden. If two assertions are tightly related (e.g., shortfall and profit on the same fixture mutation), keeping them in one test is fine; if they're independent, split.

The same rule applies to expectations (mock assertions): few per test. Many expectations means you're testing too much or the SUT is doing too much.

## Test data builders for complex objects

When test setup gets verbose, extract a builder. The pattern: a class with chainable methods producing a domain object, with sensible defaults so each test only overrides what matters.

```python
class ExtractedFieldResultBuilder:
    def __init__(self):
        self._value = "default"
        self._confidence = "high"
        self._candidates = []
    def with_value(self, v): self._value = v; return self
    def with_candidates(self, *c): self._candidates = list(c); return self
    def build(self): return ExtractedFieldResult(self._value, self._confidence, self._candidates)
```

The test reads `a_result().with_value("X").with_candidates(c1, c2).build()` — domain vocabulary on the test side, complete and valid object on the production side.

## Risk-driven testing

Don't write tests for everything; write tests where the risk lives. Fowler is explicit: *"It is better to write and run incomplete tests than not to run complete tests."* Don't test getters and setters with no logic; do test the calculation, the state transition, the failure mode, the boundary.

A review on this codebase found prose claims unbacked by tests — that's exactly the risk. If the PR description says "idempotent" or "handles partial failure gracefully," the test suite must demonstrate it.

## Self-testing code

A test suite that requires manual checks to verify results is not self-testing. Every test asserts its own outcome programmatically. Hand-checking is for the first test of a calculation (to populate the expected value); after that, the assertion is mechanical.

Run tests frequently — every few minutes during active work, all tests at least daily. *"Never refactor on a red bar."* A failing test means stop and either fix or revert.

## What to test against synthetic LLM output

For LLM-driven code (per [[feedback_tdd_listening]]'s outside-in approach), tests come in three layers:

1. **Pure-Python tests** with stubbed LLM responses — fastest, run on every change, cover the logic.
2. **Integration tests** with the real LLM client against a local fixture or a known prompt — slower, run before commits.
3. **Evaluation harness** against real documents with ground truth — slowest, run for accuracy claims.

Property tests (Hypothesis) sit at layer 1 — they're pure-Python, fast, and verify invariants over the input space rather than against specific examples.

## Cross-references

- [[feedback_tdd_listening]] — write the failing test first; listen when it's awkward.
- [[feedback_mock_discipline]] — what to mock and what not to.
- [[feedback_claims_need_tests]] — local incident reinforcing the boundary discipline.
- Sources: *Growing Object-Oriented Software, Guided by Tests* Ch 5/21-23; *Refactoring: Improving the Design of Existing Code* 2nd edition Ch 4.

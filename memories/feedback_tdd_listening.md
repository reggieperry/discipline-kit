---
name: tdd-discipline-and-listening-to-the-tests
description: "Test-driven development as a design activity, not a verification activity. Distilled from Growing Object-Oriented Software, Guided by Tests (Freeman & Pryce). Write tests first to clarify intent; use difficulty-to-test as design feedback; nested feedback loops at every level."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

GOOS treats TDD as the way you discover and refine design, not as a verification step at the end. The book is the authoritative reference; this memo is what I take from it as personal practice.

**Why:** the technique only pays back when it drives the design. Writing tests after the code is finished is a useful sanity check but misses the design feedback that makes TDD economically worthwhile. A past PR review found three "claims need tests" drifts — exactly the failure mode that disciplined TDD prevents.

**How to apply:** when starting non-trivial work, write a failing test first, watch it fail with a clear diagnostic, then write the minimum code to make it pass, then refactor. Move from outside in: acceptance test for the feature (in domain terms) → unit test for the next collaborator → make pass → refactor. Don't write new functionality without a failing test.

## The Golden Rule

*Never write new functionality without a failing test.* (GOOS Ch 1.)

The tight cycle: write a failing test → make it pass → refactor. Around that, the outer cycle: write a failing acceptance test → write the failing unit tests that, together, make the acceptance test pass → done with that feature.

## Listen to the tests

This is the highest-value GOOS principle. *Difficulty writing a test is design feedback, not a tooling problem.* When a test is hard to set up or hard to read, the production code has a design weakness — the test is exposing it. Don't reach for mocking magic, class-loader hacks, or test-only inheritance to work around the difficulty; fix the design.

The specific signals (GOOS Ch 20):
- *I need to mock an object I can't replace (without magic).* Hidden dependency on a singleton or global (`new Date()`, `System.currentTimeMillis()`). Make the dependency explicit — pass it in.
- *Mocking concrete classes feels wrong.* It is wrong. Extract an interface. If you can't name a meaningful interface, the class is doing too much; break it up.
- *Bloated constructor.* The class has too many dependencies. Look for arguments that always travel together (package into a new object), or distinguish required dependencies from notifications/adjustments (defaults for the latter).
- *Confused object.* Unrelated responsibilities forcing in unrelated dependencies. Single-responsibility violation; split the class.
- *Too many expectations in a test.* Distinguish stubs (allowances) from expectations (assertions). If everything is an expectation, you're locking down too many interactions or testing too large a unit.

## Develop from inputs to outputs

Start with the events arriving at the system boundary; write the test that simulates those events; let the boundary object discover the supporting roles it needs from the rest of the system. Implement those roles. Continue inward. The middle of the system gets built last — and you only build what the boundary actually needs.

This is the opposite of starting with domain classes and hooking them up later. GOOS is explicit: starting in the middle feels like rapid progress but leads to building unnecessary or incorrect functionality.

## Unit-test behavior, not methods

A test named `testBidAccepted` describes a feature; a test named `testCalculateBidPrice` describes a method. Tests organized around behavior survive refactoring; tests organized around methods break every time you rename or split a method. The test name should describe how the object behaves in the scenario, in domain terms.

## Start with the simplest success case

Don't start with degenerate or failure cases — they don't tell you whether the design is right. Start with the simplest *successful* path. Once that's working, you know the shape of the solution and can prioritize between failure cases and further success cases. Keep a notepad of failure cases you noticed along the way.

## Write the test you want to read

Write the test first as if the supporting code already exists. Make it read clearly. Then build the support code to make it run. If the test reads awkwardly, the API you're imagining is awkward; revise it before implementing.

## Watch the test fail, with the right diagnostic

Before writing the production code, run the failing test and confirm:
1. It fails for the reason you expected.
2. The failure message tells you what's wrong, clearly. If the diagnostic is unclear, improve it before writing the fix — a year from now, that message is the only clue.

GOOS's small improvement to the standard TDD cycle: between "write a failing test" and "make it pass," there is "make the diagnostics clear."

## Three levels of testing

| Level | What | Cost | Tells us |
|---|---|---|---|
| Acceptance | Whole system end-to-end | Slow, integration | External quality (does the feature work?) |
| Integration | Our code against code we can't change | Medium | Whether our adapters match third-party reality |
| Unit | One object or small cluster | Fast | Internal quality (is the design loosely coupled, highly cohesive?) |

End-to-end acceptance tests measure progress. Unit tests catch regressions and give design feedback. Both matter; they tell us different things.

## Implicit dependencies are still dependencies

Hiding a dependency by using a global, a singleton, or a class-level static does not eliminate it — it just makes it inaccessible. The result: tests are clumsy and the code becomes brittle to environments. Make the dependency explicit (pass a `Clock`, a `Logger`, a `Filesystem` adapter in), even when it feels like over-engineering for the immediate test case.

## Logging is a feature (when it's user-facing)

Distinguish *support* logging (auditable, user-facing, part of the product) from *diagnostic* logging (programmer scaffolding). Support logging deserves to be a feature with tests; the design should pass in a support/notification object rather than reach for a logger directly. Diagnostic logging is scaffolding; it can be inline but should not interfere with the readability of production code.

If you find yourself mocking a logger to test what was logged, that's a smell — the right shape is to pass in a support object that records events the test can assert against.

## Cross-references

- [[feedback_oo_style]] — peers, Tell-Don't-Ask, the structural form GOOS pushes toward.
- [[feedback_mock_discipline]] — what to mock and what not to.
- [[feedback_test_discipline]] — readability, fixtures, boundaries.
- [[feedback_claims_need_tests]] — a local incident this reinforces.
- Source: Growing Object-Oriented Software, Guided by Tests (Freeman & Pryce).

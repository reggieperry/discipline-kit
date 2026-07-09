---
name: mock-discipline-what-to-mock-what-not-to
description: "Mocking rules from GOOS Ch 7-8 and 20. Mock peers, not internals. Only mock types you own. Don't mock values, concrete classes, third-party libraries. Use adapter layers around external code. Applies to Python `unittest.mock` and `pytest-mock` as much as to jMock."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

The GOOS mocking rules are subtle and often violated in the wild. Getting them right is what separates tests that drive design from tests that lock down implementation.

**Why:** mocks express the protocol an object expects from its collaborators. Mock the wrong thing and the test becomes brittle, expresses nothing meaningful about the design, and prevents refactoring. A PR review that found tests mocking too widely is what prompted this memo; the fix is codified below.

**How to apply:** before adding a mock to a test, ask the three questions below. Decline to mock if any answer is no.

## The three questions before mocking

1. **Is it a peer?** Mocks express the protocol between an object and its peers (dependencies, notifications, adjustments). They are not for the object's internals. If you're tempted to mock something that's an implementation detail (an internal helper, a private collaborator), the test is reaching inside the object. Refactor instead — extract a peer with a real interface, or move the behavior.
2. **Do we own the type?** "Don't mock what you don't own." Third-party types (database clients, HTTP libraries, vendor SDKs) should not be mocked directly. Reasons: we don't know how the real type behaves under all conditions; our mock will drift; library upgrades break our mocks. Wrap the third-party type in an adapter interface *we* own, then mock the adapter.
3. **Is it a value, not an object?** Don't mock values (dataclasses, frozen records, immutable collections, primitives wrapped for type safety). Just construct an instance with the values the test needs. If a value is awkward to construct, write a builder helper — don't mock around the problem.

## Don't mock concrete classes

Mocking a concrete class by inheriting from it and overriding methods locks the test to the current shape of that class. It hides the relationship being tested (the test no longer makes the dependency visible) and forces the test to know which methods are overridden and which aren't.

The fix is to extract an interface (`typing.Protocol` or `abc.ABC` in Python) describing only the methods the consumer actually uses. The class implements that interface; tests mock the interface. This is the Interface Segregation Principle: *clients should not be forced to depend on interfaces they don't use.*

If you can't think of a meaningful name for the extracted interface, that's a hint the class has too many responsibilities — the consumer is depending on a slice of behavior that deserves its own name.

## Adapter layer for third-party code

When working with a third-party API, write an adapter layer between your application and the library:

```
application objects  →  adapter (you own)  →  third-party API
                                   ↑
                          mock this in unit tests;
                          test this with focused integration tests
```

The adapter is *thin* — its job is to translate, not to add behavior. Unit tests mock the adapter (because you own it). A small number of focused integration tests exercise the adapter against the real third-party library to confirm your assumptions about its behavior. Most tests use the mocked adapter.

This pattern is also what FastAPI/Pydantic projects do well: define your application-domain models and only touch the third-party shapes at the boundary.

## Logging is special

A test that mocks a logger to check what was logged is a smell — it ties the test to the format and channel of the log message. The fix (GOOS Ch 20): introduce a notification/support object that the production code calls instead of the logger. The production code calls `support.notify_filtering(tracker, location, filter)`; the support object implementation in production logs, the support object in tests records calls for assertion.

The boundary case: pure diagnostic logging that's developer-facing scaffolding (debug, trace) doesn't need this treatment — it can be inline. Support logging that's user/operator/auditor-facing should be a feature, with tests.

## Few expectations per test

Distinguish *stubs* (allowances — "if asked, return this") from *expectations* (assertions — "I expect this to be called exactly this way"). In jMock/Mockito terms, `allowing(x).y()` vs `oneOf(x).y()`. Most calls in a test are stubs; only the call that represents the behavior under test should be an expectation.

When a test has many expectations, you can't tell what's being asserted vs what's just plumbing. Convert most of them to stubs; keep only the one or two that express the intent.

## Python specifics

`unittest.mock.MagicMock` is unforgiving — it stubs everything and asserts nothing unless you remember to. Use it sparingly:

- Prefer `Mock(spec=AdapterProtocol)` so unexpected attribute access fails — this enforces the interface contract.
- Use `monkeypatch` from `pytest` for module-level patching at boundaries; reserve it for cases where dependency injection isn't yet available.
- Avoid `patch('module.SomeClass')` mid-stream; if a class needs replacing for tests, the design wants you to pass it in as a constructor argument. Patching is the last resort, not the first.

## What this means in practice

When I write a test and I want to mock something, I run the three questions:
1. **Is it a peer?** If it's the object's internal helper, no — refactor.
2. **Do I own it?** If it's a library type, no — wrap it.
3. **Is it a value?** If yes, no — construct it.

If I pass all three, I mock the role (preferring `spec=Protocol`) and write the test against the interaction protocol. If a test has more than two or three expectations, I rethink — usually the test is doing too much or the production object has too many responsibilities.

## Cross-references

- [[feedback_tdd_listening]] — listening to tests includes listening to mock pain.
- [[feedback_oo_style]] — peers vs internals; the structural side of the same idea.
- Source: *Growing Object-Oriented Software, Guided by Tests* (Freeman & Pryce), Chapters 7, 8, 20.

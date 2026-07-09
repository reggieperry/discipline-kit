---
name: feedback-user-defined-types-and-property-tests
description: "Eight rules from *Robust Python* (Viafore, 2021) Parts II-IV — pick dict/dataclass/class by invariant load, double-underscore for invariant-protecting members, assert vs raise discipline, Protocols for \"shape we depend on\" (not ABCs), inverted dependency direction (truth-owner owns the type), named temporal dependencies via NewType, Hypothesis property tests for documented invariants, yield fixtures with try/finally for resource safety. Extends the type-system memory pair with the user-defined-type and testing-discipline material from the full release."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

The early-release of *Robust Python* covered only Part 1 (type system tools — already in [[reference-type-system-for-invariants]] and [[feedback-typechecker-adoption]]). The full release adds **Part II Chs 8-14** (Enums, Data Classes, Classes/Invariants, Interfaces, Subtyping, Protocols, runtime checking) and **Parts III-IV Chs 15-24** (Extensibility/OCP, Dependencies, Composability, Event-Driven, Pluggable Python, Static Analysis, Testing Strategy/AAA, Acceptance Testing, Property-Based with Hypothesis, Mutation Testing). The rules below are the net-new patterns from those parts that aren't already in the GOOS / Liskov / Fowler memories.

**Why:** the GOOS / Liskov / Fowler frame in the existing memory covers OO style, mock discipline, refactoring smells, and abstract data types. Viafore Part 2 sharpens the *Python-specific* mechanics — when to reach for a dataclass vs a class, how Python's name-mangling defends invariants, how Protocols replace inheritance for test-doubles, how Hypothesis turns documented invariants into shrinking-counterexample tests.

**How to apply:** at design time for a new domain type or invariant, walk rules 1-3. At interface design time (a new collaborator, a test double), walk rules 4-6. At test-writing time, walk rules 7-8.

---

## 1. Pick dict → dataclass → class by invariant load, not by reflex

**Rule.** Use the Ch 10 closing-flowchart heuristic: scalar enum set → `Enum`; homogeneous mapping → `dict`; heterogeneous bundle with no cross-field constraint → `@dataclass(frozen=True)`; heterogeneous bundle with a cross-field invariant → a class whose `__init__` asserts the invariant.

**Why.** Ch 10 "Closing Thoughts." Classes pay the encapsulation tax only when there's an invariant to defend. A dataclass when fields are interdependent is under-kill; a class without an invariant is overkill.

**Trigger.** New domain records, metadata bundles, stage-state objects. When a codebase reaches for Pydantic everywhere — fine for boundaries, but internal state with no cross-field rules should be a frozen dataclass, not a `BaseModel` (cheaper, no validation cost on every construction).

**How to apply.** When adding a new internal type, write the invariants on a comment line first. If none, frozen dataclass. If any, class with `__init__` asserting them and a docstring naming them. Reserve Pydantic for the boundary (LLM, HTTP, config parse) per [[feedback-security-when-writing-code]].

---

## 2. Encapsulate via double-underscore name-mangled members when an invariant must survive mutators

**Rule.** When a class holds an invariant mutators must preserve, store the protected state under a double-underscore attribute (`self.__toppings`). External `pizza.toppings.append(...)` raises `AttributeError`. Single-underscore is convention only — not enforced.

**Why.** Ch 10 "Protecting Data Access." Python's name-mangling is reachable as `pizza._PizzaSpecification__toppings`, but the casual mutation path fails, which is exactly the signal a future contributor needs.

**Trigger.** Any internal class with a cross-field invariant — a state object tracking an active stage plus a reclaim-eligible-since timestamp; an accumulator that depends on ordering. Watch for classes that expose mutable lists/dicts as public attributes.

**How to apply.** Promote the attribute to `__name`. Add a `def add_x(self, ...)` mutator that re-asserts the invariant. Expose reads as a copy (`return list(self.__items)`) per Ch 10's sidebar warning against returning references to mutable internals.

---

## 3. `assert` is for developer mistakes (may be stripped); `raise` is for caller / external errors (must run)

**Rule.** Use `assert` only for invariants you control internally — preconditions in `__init__`, postconditions a teammate could break. Use `raise <SpecificError>(...)` for anything that depends on caller input or external state. Never `assert` on LLM output, HTTP payloads, DB rows, config values.

**Why.** Ch 10 sidebar "Assertions Versus Exceptions." Python deployed with `-O` strips asserts. They are a developer-to-developer signal, not a runtime defense.

**Trigger.** Anywhere current code has `assert some_id is not None` after the id came from the LLM — exactly wrong. An `-O` deployment loses the check; even without `-O`, "AssertionError" is useless to operators. Pairs with [[feedback-pr-review-patterns]] Pattern 1.

**How to apply.** Grep `assert` across application code. For each one: could this fail because of external input? If yes, replace with `raise ValueError(...)` or a domain-specific exception. Keep asserts only inside class `__init__` invariant blocks and in test code.

---

## 4. Protocols for "shape we depend on"; ABCs only for "is-a we substitute"

**Rule.** When a function only needs an object to support a few specific methods/attributes (a *shape*), define a `Protocol` and annotate parameters as the protocol. Reserve inheritance / ABCs for genuine is-a relationships where the parent contract includes behavioral guarantees subclasses must uphold.

**Why.** Ch 13 "Do Protocols Eliminate the Need for Inheritance?" Protocols give static structural subtyping without forcing physical dependency. Inheritance is heavyweight for "I just need a `.split_in_half()` method on whatever you pass me."

**Trigger.** The LLM gateway abstraction you want for testing — when tests reach for `unittest.mock.MagicMock` against a vendor SDK. A `ChatClient(Protocol)` with `async def complete(self, prompt: str, *, timeout: float) -> str` lets you write a real `FakeChatClient` with a fixed surface area. Same shape for an embeddings gateway, a vector retriever, an entity-store reader.

**How to apply.** When adding a new collaborator a stage depends on, define the `Protocol` next to the *consumer* (Ch 13's structural framing), not next to the implementation. Keep it small (1-3 methods). Use `@runtime_checkable` only when a Union of protocols needs runtime discrimination. Pairs with [[feedback-mock-discipline]] ("only mock types you own").

---

## 5. Inverted dependency direction — the system that *knows the truth* owns the type

**Rule.** When two subsystems both reference a domain concept, the dependency arrow points *from* the system that doesn't know the truth *to* the system that does. Cycles between subsystems are a smell that the wrong system owns the truth.

**Why.** Ch 16 "Types of Dependencies" (pizza-maker inversion, Figs 16-3 vs 16-4). When the payment system and pizza-maker each have their own copy of "menu items," every change requires shotgun surgery. Inverting so the pizza-maker owns the menu type collapses the cycle.

**Trigger.** Multiple stages of a pipeline all reaching for "what is a chunk?" and "what is an entity?". When a concept is defined where it was first needed (say, the retriever), but the actual truth-owner is the ingester or the table that creates the rows — that owner is where the contract should live. Same for a field-definition type: the catalog that defines fields is the owner.

**How to apply.** When adding a new stage that needs a domain concept already used elsewhere, do not redefine it. Trace where the concept's source of truth lives (usually the DB owner / the boundary that creates it) and import from there. If two stages both import each other for the same concept, the concept needs a third home.

---

## 6. Name temporal dependencies — prefer `NewType` over comments

**Rule.** When operation A must precede operation B and the language can't force the order, pick one of three mitigations and write the choice down: (a) lift the precondition into a type via `NewType` so B can only be called with a value that's been through A; (b) embed the precondition check inside B; (c) leave a breadcrumb comment naming the temporal link by file:line.

**Why.** Ch 16 "Temporal Dependencies." Silent killers — the code "works" until someone adds a path that skips the precondition. The three mitigations are ordered by strength.

**Trigger.** Many places. Ordered-config invariants like `reclaim_threshold_seconds > llm_timeout_seconds > heartbeat_interval_seconds` ([[feedback-pr-review-patterns]] Pattern 3); persistence that assumes an id has been resolved first ([[reference-type-system-for-invariants]] rule 2 covers this via `NewType` if applied); a migration `downgrade` that assumes no dependent rows exist ([[feedback-pr-review-patterns]] Pattern 4).

**How to apply.** Pick the strongest mitigation that's cheap. `NewType` is free and the strongest — use it whenever the precondition produces or transforms a value. Embedded check is next. Breadcrumb is the fallback when neither fits; in that case the breadcrumb must name the *other* line by file:line so a grep finds the pair.

---

## 7. Hypothesis property tests for documented invariants

**Rule.** When a class or function carries a named invariant — including the "claims" from [[feedback-claims-need-tests]] (idempotent, bounded, degraded-mode) — write a Hypothesis test that asserts the invariant over a generated input strategy, not a specific example. Use `@given(strategies.X)` plus `@example(...)` for known-hard cases.

**Why.** Ch 23 "Property-Based Testing with Hypothesis." Invariants are exactly properties; example-based tests cover the inputs the author thought of, Hypothesis covers the inputs nobody thought of, and the shrinking gives the minimal counterexample for free.

**Trigger.** Numeric-math invariants (outputs ∈ [0, 1], monotone in input ratios, no NaN propagation); byte-budget invariants (a packed blob never exceeds budget regardless of input-list shape); similarity-score clamps (always `[0, 1]`); a cycle detector (for any DAG input, terminates and returns `cycles=False`).

**How to apply.** One Hypothesis test per documented invariant, alongside example-based tests, not instead. Use `hypothesis.strategies.from_type` for Pydantic models. Cap with `@settings(max_examples=200, deadline=500)` so the test stays fast. Once a module already uses Hypothesis ([[feedback-claims-need-tests]] reinforces this), the rule expands the surface to every claim-bearing function.

---

## 8. Fixtures `yield` inside `try/finally` — cleanup must run on failure

**Rule.** Test fixtures that allocate any resource (DB row, temp file, async task, index entry) use `yield` inside `try/finally`, not `return` with cleanup after. Cleanup-after-`return` doesn't run if the test's assertion fails.

**Why.** Ch 21 "Annihilate" + "Use Fixtures." Viafore shows the buggy pattern (`cleanup_database()` after `assert` skips on assertion failure) and the fix (`yield` inside `try/finally`). Same shape as [[feedback-pr-review-patterns]] Pattern 2 ("plan for cancellation, not just exceptions") applied to tests.

**Trigger.** A `db` fixture in `tests/conftest.py`; an index fixture; anywhere a fixture writes rows that need cleanup across tests. When fixtures use `return` and rely on the next test's cleanup to compensate — it works until test order changes and pollutes the mapper cache (see [[feedback-sqlalchemy-schema-strip-isolation]]).

**How to apply.** When writing a new fixture, default to `yield` + `try/finally`. The `return` form is only safe for a value that owns no external resource (frozen dataclass of test data, pre-built dict). Pairs with [[feedback-test-discipline]].

---

## What's not in scope (already covered)

- MonkeyType / Pytype workflow (Ch 7) — [[feedback-typechecker-adoption]] rule 4.
- `Literal`, `NewType`, `Final`, `TypedDict`, `Optional`, bounded TypeVar (Chs 4-5) — [[reference-type-system-for-invariants]].
- `UserDict`, `collections.abc` parameter types, mypy strict flags (Chs 5-6) — [[feedback-typechecker-adoption]].
- Gherkin / BDD `behave` framework (Ch 22) — overhead too high for most bake-offs; contradicts [[feedback-simplicity-principle]].
- Mutation testing with `mutmut` (Ch 24) — interesting meta-tool but only worth it once the test suite is mature enough to benefit; deferred.
- Pylint plugin authoring (Ch 20) — duplicates [[reference-local-quality-stack]] (semgrep + ruff).
- Event-Driven Architecture observer pattern (Ch 18) — contradicts [[feedback-demo-with-prod-risk]] "favor in-code patterns over new services."

## Related memory

- [[reference-type-system-for-invariants]] — Part 1 type tools (Literal/NewType/Final/TypedDict/Optional/bounded TypeVar)
- [[feedback-typechecker-adoption]] — mypy adoption playbook + ABC discipline
- [[feedback-pr-review-patterns]] — Pattern 1 (boundary defense, rule 3 here); Pattern 6 (invariants in docstrings, rule 1 here)
- [[feedback-claims-need-tests]] — rule 7 here gives Hypothesis as the mechanism
- [[feedback-mock-discipline]] — rule 4 here (Protocols) gives the Python idiom
- [[feedback-test-discipline]] / [[feedback-tdd-listening]] — rule 8 here extends fixture discipline
- [[reference-sources-to-consume]] — *Robust Python* (full release) priority reading

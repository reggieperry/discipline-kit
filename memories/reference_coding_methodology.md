---
name: coding-methodology-synthesis
description: "The unified coding/development/testing methodology, synthesized from Liskov 1974+1988, GOOS, and Fowler. The thesis, the five pillars, and the cycle."
metadata: 
  node_type: memory
  type: reference
  volatility: durable
---

The unified methodology. Distilled from four books; long-form treatment with examples in a companion HTML doc.

## Thesis

You cannot design software correctly up front. The design must emerge through cycles of building, testing, and refactoring. The cycles only work if they're cheap and safe. The four sources each make a different cycle cheap:

- **Liskov** makes *representation changes* cheap — rep is private behind the spec, so changing it doesn't ripple.
- **GOOS** makes *design changes* cheap — outside-in TDD surfaces design choices at the moment they're made; difficulty testing is design feedback.
- **Fowler** makes *structural changes* cheap — self-testing code + small steps means restructuring is bounded-risk.

Together they make the demo-with-prod-risk posture viable. Counter-cultural premise: small steps with feedback beat big plans with confidence.

## The five pillars

1. **Design through abstraction, not classes.** Operations and specs first; rep is private. Composition by default; inheritance only when LSP (behavioral substitutability) actually holds.
2. **Develop test-first, listening to the tests.** Acceptance test in domain terms → unit tests for boundary objects → discover supporting roles → make pass. Difficulty testing = design feedback.
3. **Refactor as you go, not on schedule.** Preparatory, comprehension, litter-pickup. Two hats (feature vs refactor) — never both at once. Beck: *"make the change easy, then make the easy change."*
4. **Test for behavior at the right level.** Names describe behavior; arrange-act-assert; fresh fixtures; probe boundaries. Three layers for LLM code: pure-Python with stubs / integration with adapter / eval harness. Property tests where invariants are dense.
5. **Verify continuously, build for change.** Self-testing code. CI + small commits + frequent integration. Tests must fail when they should. Build production-quality even for the demo.

## The cycle (10 steps)

1. **Frame** — acceptance criteria in domain language; identify boundary events.
2. **Sketch** — name roles (Protocols), not classes; one domain vocabulary per role.
3. **Write the failing acceptance test** — domain terms, watch it fail with a clear message.
4. **Drive down with unit tests** — outside-in; <code>Mock(spec=Protocol)</code> for peers, never for internals.
5. **Make each pass with minimum code** — defer optimization; keep a notepad for cleanups.
6. **Refactor** — switch hats; apply smells; tests green throughout; small commits.
7. **Cross boundaries deliberately** — third-party code goes behind adapters; domain code doesn't import library types.
8. **Verify and commit** — local quality stack clean; migrations upgrade/downgrade verified; small commits.
9. **Self-review** — a dedicated reviewer for orchestration diffs; every PR-description claim has a test.
10. **Reflect** — capture what made each step harder than expected; update notes if a principle needs sharpening.

The cycle is fractal — each step has a smaller cycle inside it.

## LLM-specific notes

- **The LLM is a third party — wrap it.** Adapter that takes a domain prompt, returns a Pydantic-validated domain object. Mock the adapter; integration-test the implementation against the real LLM. Structured outputs (JSON schema) over raw text scraping. See [[feedback_mock_discipline]].
- **Async boundaries are implicit dependencies.** Name the loop/thread for each piece; pass it in. Don't `asyncio.get_running_loop()` from a sync def. See [[feedback_async_thread_boundary]].
- **Migrations are refactors of the schema.** Local upgrade/downgrade/upgrade cycle before commit. Parallel-change (expand-contract) for prod-affecting changes. See [[feedback_local_migration_testing]].
- **State machines are object-oriented designs.** Transitions are operations; the state is the rep; LSP applies if methods get split. Use a dedicated state-machine reviewer on diffs touching the spine.
- **Pydantic / FastAPI / SQLAlchemy as adapters.** Pydantic at API boundary; ORM at persistence boundary; FastAPI route as HTTP adapter. Domain code imports none of them. Trivial CRUD endpoints are a pragmatic exception.

## Key heuristics (full tables in HTML doc)

- **Mock when:** peer / not value / type you own. Don't mock internals, values, third-party types, or concrete classes — extract a Protocol of what you actually use.
- **Protocol vs ABC:** default Protocol (structural). Use ABC for shared implementation via template method, or when nominal registration matters.
- **Refactor before adding a feature when:** Rule of Three triggered, the function is already long, you can't write the test without restructuring.
- **Inheritance is right when:** LSP holds AND composition would be substantially more awkward. Framework base classes are a separate category — inherit where the framework requires.
- **Property test when:** pure logic with dense invariants (confidence math, tree assembly, idempotency). Not for HTTP routes, state machines, LLM calls, or concurrency.

## Tensions resolved

- **Mock peers vs rep is private** — peers are roles via interfaces; mocking the role enforces the abstraction.
- **Refactor opportunistically vs test-first** — refactor is the third phase of the TDD cycle.
- **Only mock types you own vs we use FastAPI/Pydantic/SQLAlchemy** — wrap in adapters; domain tests don't import frameworks.
- **Inheritance compromises encapsulation vs framework base classes** — inherit at the boundary, compose in the interior.
- **Demo-with-prod-risk vs ship-fast-and-cheap** — not the same thing. Discipline is what makes demo-with-prod-risk cheap.
- **Methodology complexity vs "as simple as possible"** — the methodology is what makes simplicity safe.

## Cross-references

- [[reference_design_abstraction_lsp]] — Pillar 1 detail (Liskov).
- [[feedback_tdd_listening]] — Pillar 2 detail (GOOS).
- [[feedback_oo_style]] — Pillar 1 + 2, OO style.
- [[feedback_mock_discipline]] — mocking rules.
- [[feedback_test_discipline]] — Pillar 4 detail.
- [[feedback_refactoring_smells]] — Pillar 3 detail (Fowler).
- [[feedback_demo_with_prod_risk]] — the posture this methodology enables.
- [[feedback_simplicity_principle]] — the "simple but no simpler" call this methodology serves.

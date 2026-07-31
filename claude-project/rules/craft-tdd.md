---
paths:
  - "**/*.go"
  - "**/*.sh"
  - "**/*.py"
  - "**/*.scala"
  - "**/*.sc"
---

# Test-driven development and the design feedback it gives

How tests drive design, not just verify it. Source: Steve Freeman & Nat Pryce, *Growing Object-Oriented Software, Guided by Tests*. The mechanics of writing tests live in the language overlay; this rule is the cadence and the design discipline.

> See the active language overlay (`go-testing.md`, the `python-*` and `scala-*` sets) for test mechanics and property testing, `craft-complexity.md` for the deep modules testable code tends toward, and `craft-abstraction.md` for the small interfaces that "mock roles, not objects" produces.

## The cycle and its purpose

- **Write no new functionality without a failing test first** — the golden rule. The failing test says what to build and when you are done.
- **Run test → make it pass with the simplest code → refactor, and repeat.** Keep each step's implementation the simplest thing that passes; clean up under the green bar.
- **Watch the test fail before you make it pass, and read the failure message.** A wrong or unclear failure means you misunderstood the code or your diagnostics are weak — fix that now.
- **Start each feature with one failing acceptance test in domain terms**, then drive the units inside it. Begin with the simplest success case (not the error cases — note those for later), and work outside-in from the inputs toward the outputs, discovering collaborators as you go.

## Listen to the tests

- **When a test is hard to write, treat the difficulty as a design defect and fix the design — not the test.** The structure that resists testing will resist change. Hard setup, the urge to mock internals, or a need for class-loader tricks are all the code telling you something.
- **Pass dependencies in explicitly; never reach for globals, singletons, a package clock, or hidden statics.** An implicit dependency is still a dependency — making it explicit is what makes the unit testable and honest. A bloated constructor is a smell: extract the arguments that travel together into a named concept.
- **Keep expectations few.** Many expectations per test means the unit is too big or you are over-specifying its interactions.

## Outside-in, the walking skeleton, and the layers

- **Build a walking skeleton first** — the thinnest slice that you can automatically build, deploy, and test through the *whole* architecture. It flushes out integration and process risk while there is time to act.
- **Layer the tests: acceptance** (does the whole system do the job?), **integration** (does our code work against code we can't change?), and **unit** (do our objects do the right thing and compose conveniently?). Keep most tests fast in-memory unit tests, fewer integration, fewest end-to-end.
- **Separate tests that measure progress** (new, expected to fail) **from tests that catch regressions** (must always stay green); never commit a failing unit test to the shared branch.

## Mocks, used well

- **Mock roles, not objects.** Focus on the messages between collaborators — the relationships — not the classes. This is the discipline's central correction to itself.
- **Only mock types you own.** Wrap a third-party API (the model SDK, an external CLI such as `git` or a linter, the filesystem) in a thin adapter defined in your own terms, and verify that adapter with focused integration tests. You get no design feedback from mocking code you can't change, and the stub can lie about behavior the real thing doesn't have.
- **Mock an object's peers, never its internals; don't mock values** (construct them — use a test data builder if construction is painful). **Allow queries, expect commands**: queries are side-effect-free and may be called any number of times; commands change the world, so their occurrence is what you assert.

## The object style TDD pushes you toward

- **Tell, don't ask** — state what you want in the collaborator's terms and let it decide how, rather than pulling its data out and deciding for it. Ask only when querying a value, a collection, or a factory.
- **Give each object one responsibility you can state without "and", "or", or "but".** Keep objects context-independent — whatever an object needs about its environment is passed in, not built in, which also makes every unit test just another context.
- **Identify roles as narrow, client-driven interfaces and introduce value types for domain concepts even when they do little** — specific types localize change and attract behavior. (The language overlay gives the idiom.)

## Test quality

- **Test behavior, not methods; name each test as a sentence about what the object does in a scenario.** The name should let a reader diagnose a failure without reading the body.
- **Use a canonical arrange-act-assert shape, one coherent feature per test, and make failures informative.** Diagnostics are a first-class feature — you should never need a debugger to understand a failure. Specify precisely what should happen and no more; over-specification makes brittle tests.

## A choice, not a dogma — and reconciling with design-first

GOOS is the canonical **London-school (mockist)** position: drive design outside-in and specify interactions with mocks. The **classicist** position (Beck; Fowler's "Mockist vs Classicist") tests state through real collaborators and reserves doubles for awkward seams. And note the honest tension with `craft-complexity.md`: Ousterhout warns that strict test-first can be too incremental and tactical, and argues you should design the *abstraction* deliberately (design it twice) before chasing features.

Reconcile them: **design the deep abstraction first, then build it and pin its edges test-first.** Default to **classicist** — assert on returned values and state where collaborators are pure and fast — and reach for **hand-written test doubles at the true seams** (the data store, the model call, the filesystem, the clock), which is exactly where "only mock what you own" applies. Use mockist interaction-specification only where the *protocol itself* is under test (for example, that a component issues the right sequence of calls to a collaborator in the right order). The language overlay gives the test mechanics.

## The loop under an agentic author

An agent can *say* it did TDD; the loop below arranges the world so the claim is checkable instead of trusted. Five beats per slice:

1. **Red.** Write the test and observe it fail against the code-to-be. The red is evidence, not a
   sentence — read the failure message and check it fails for the reason you intended.
2. **Green.** Make it pass, under whatever mechanical check the repo runs on the commit path, so
   green is the machine's verdict rather than the author's.
3. **Refactor.** Clean up under green, as a separate commit that changes no test.
4. **Disclose.** The commit message records what was written before/alongside/after, what was
   observed red and by what route, any adjusted golden, and the refactor.

**The red bar decomposes into two claims, graded differently.** *Order* — that the test was written before the code — is **testimony forever**: git shows a commit sequence, but nothing proves the author didn't write the code first and reorder. *Detection power* — that the test actually fails when the behavior is absent — is **provable in principle**: build the implementation at the merge-base against the tests from HEAD and confirm the new tests go red, which kills tautologies and green-by-weakening. Trust the second, not the first; ask whether the test can fail, never whether TDD was followed. The shadowed-mechanism and dead-lens incidents (`feedback_claims_need_tests`, `feedback_reviewer_harness_fail_closed`) are why detection, not order, is the thing to prove.

**Court selection — when red-first is mandatory versus negotiable.** Red-first is **mandatory for detector-class slices**: any deliverable whose job is to *catch* something — a gate, a check, a tamper proof, a fail-closed property, a discriminating mechanism. A detector never observed red might catch nothing, and a green suite would never tell you. Elsewhere — an IO shell, a report generator, glue — red-first is **negotiable with disclosure**: the slice may declare *build-then-verify* in its process paragraph, provided it names the verification that stood in for the red bar (a dual-leg discharge, a cross-language recount, a live run). The founding project's D3 authorship writeup is the exemplar of correct allocation: the report generators declared build-then-verify with a dual-leg discharge, while the fail-closed properties — the discharge's tamper proof, the validator's exit code — were pinned red-first.

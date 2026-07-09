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

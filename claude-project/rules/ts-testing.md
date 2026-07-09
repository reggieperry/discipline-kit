---
paths:
  - "**/*.test.ts"
  - "**/*.test.tsx"
  - "**/*.spec.ts"
  - "**/*.spec.tsx"
  - "**/__tests__/**/*.ts"
  - "**/__tests__/**/*.tsx"
---

# TypeScript testing

How to write TypeScript tests: Vitest suite structure, behavior-named cases, querying the DOM the way a user does with React Testing Library, mocking the network at its boundary with MSW, property-based testing of pure logic with fast-check, and deterministic runs with no real clock or socket. Sources: the Vitest docs (`describe`/`it`/`expect`, `test.each`, the `vi` timer and mocking API, the v8 coverage provider), Testing Library (the React adapter, `@testing-library/user-event`, and Kent C. Dodds' guiding principles — query by accessible role and text, avoid testing implementation detail), `@testing-library/jest-dom` for the DOM matchers, MSW (Mock Service Worker — `setupServer`, `http`, `HttpResponse`), and fast-check (`fc.assert`/`fc.property`, seeds, `numRuns`). The TDD cadence and design discipline are in `craft-tdd.md` and `craft-xunit.md`; this rule is the TypeScript mechanics.

> See `craft-tdd.md` for red-green-refactor and "listen to the tests", `craft-xunit.md` for the test-double taxonomy (stub vs spy vs fake) the examples name, `ts-types.md` for the discriminated unions and branded types whose invariants these tests pin, `ts-react.md` for the component structure the DOM tests exercise, `ts-errors.md` for the `Result` shapes an assertion inspects instead of a thrown value, and `craft-domain-modeling.md` for why a `Money` or `Order` type carries behavior worth a property.

## The residue this rule carries

The governing principle is stated in `ts-types.md`: encode what the type system can state cheaply — a discriminated union, a branded `UserId`, a `readonly` field — and let these tests carry the rest. The obligation that lands here is two-sided. For every invariant the type cannot state, write the test over valid input *and* the test that the parser or smart constructor refuses illegal input. A `parseMoney` with no test for what it returns on `"-1"` or `"1.005"` is an unproven invariant; the negative space is half the contract. Test the rule a value obeys, and test what the boundary does when something tries to build an illegal one. TypeScript's types vanish at runtime, so anything crossing a trust boundary — JSON off the wire, a form field, a URL param — is `unknown` until a validator narrows it, and that validator is code with its own tests.

## Structure and naming

- **Group with `describe`, one behavior per `it`, and name the case as a sentence about the behavior**, not the method: `it('rejects a negative amount', …)`, not `it('parseMoney', …)`. The name should let a reader diagnose a failure without reading the body. Prefer `it` and `test` consistently within a file — pick one alias per project.
- **Structure each case arrange-act-assert in order, the act step a single call to the unit under test.** Keep computation out of the test body: no branching or loops that derive the expected value. A `want` you have to compute is a `want` that can be wrong the same way the code is.
- **Use `it.each` (or `test.each`) for table-style cases that share logic** — each row is reported and fails independently. Pass an array of objects and destructure, so each row reads as data, not positional tuples.

```ts
it.each([
  { input: 'a/b/c', sep: '/', want: ['a', 'b', 'c'] },
  { input: 'abc', sep: '/', want: ['abc'] },
  { input: '', sep: '/', want: [''] },
])('splits $input on $sep', ({ input, sep, want }) => {
  expect(split(input, sep)).toEqual(want)
})
```

- **Group by the unit under test, not by layer.** The pure logic (parsers, reducers, domain calculations) gets fast suites with no DOM and no React runtime; components get their own suites under `@testing-library/react`. Keep the two kinds in separate files so the pure suite stays a sub-millisecond majority.

## Assertions and matchers

- **Reach for the matcher that prints the useful diff.** Use `toBe` for primitives and reference identity, `toEqual` for deep structural equality of objects and arrays, and `toStrictEqual` when `undefined` properties and class identity must also match. Never assert deep equality with `toBe` — it compares references and the failure names nothing.
- **Assert on returned values and final rendered state, not on interactions**, wherever collaborators are pure and fast — the classicist default `craft-tdd.md` sets. Reserve spies (`vi.fn`, `vi.spyOn`) for the seam where the outgoing call *is* the observable effect (an analytics event, a write to a port you own), and assert on the state everywhere else.
- **For async code, `await expect(promise).rejects.toThrow(...)` or `.resolves` — never leave a floating promise.** A forgotten `await` on an assertion makes the test pass whatever the promise does. Add `expect.assertions(n)` to any test whose assertions live inside a `catch` or a callback, so a path that silently skips them fails.
- **Import the DOM matchers from `@testing-library/jest-dom`** (`toBeInTheDocument`, `toBeDisabled`, `toHaveTextContent`, `toHaveAccessibleName`) and register them once in the shared setup file. They assert on what a user perceives; a raw `expect(el).not.toBeNull()` does not.

## Query the DOM as a user does (React Testing Library)

The library's guiding principle is that a test resembling the way the software is used inspires confidence. Query by what a user perceives — the accessible role and the visible text — so the test survives a refactor that changes class names, wrapper markup, or internal state but not behavior.

- **Prefer `getByRole` with a `name` option**, then `getByLabelText` for form fields, then `getByText`. Reach for `getByTestId` only as a last resort for something with no accessible surface. Do not query by CSS class, tag structure, or `container.querySelector` — the `testing-library/no-node-access` and `no-container` lint rules flag both, and both couple the test to markup a user never sees.
- **Pick the query variant by intent.** `getBy*` asserts presence now and throws a helpful message if absent; `queryBy*` is the only one that returns `null`, so it is the sole correct choice for asserting *absence* (`expect(screen.queryByRole('alert')).not.toBeInTheDocument()`); `findBy*` returns a promise that retries, for an element that appears after an async update. Never wrap `getBy*` in a `try`/`catch` to test absence.

```tsx
import { render, screen } from '@testing-library/react'

it('announces the total once the order loads', async () => {
  render(<OrderSummary orderId="ord_42" />)
  expect(await screen.findByRole('status')).toHaveTextContent('$149.00')
})
```

- **Do not test implementation detail.** Assert on rendered output and accessible state, never on a component's `useState` value, a prop passed to a child, a hook's internals, or the count of renders. A test that reaches into internals re-breaks on every safe refactor and passes through real regressions the output would have caught.
- **Avoid snapshot-everything.** A whole-tree `toMatchSnapshot` asserts nothing specific, rots into a diff nobody reads, and gets regenerated on failure without thought. Reserve inline snapshots (`toMatchInlineSnapshot`) for a small, stable, self-documenting value — a serialized error, one formatted line — and assert on named roles and text for everything else.

## Interaction: `@testing-library/user-event` over `fireEvent`

- **Drive interaction through `userEvent`, not `fireEvent`.** `fireEvent` dispatches one synthetic event; `userEvent` replays the full sequence a real user triggers (hover, focus, keydown, keyup, input) and respects that a browser will not let a user click a hidden element or type into a disabled field — so it catches bugs `fireEvent` walks past. The `testing-library/prefer-user-event` rule enforces this.
- **Call `userEvent.setup()` once at the top of the test and reuse the returned instance**; every method is async, so `await` each. Do setup before `render`.

```tsx
import userEvent from '@testing-library/user-event'

it('disables submit until both fields are filled', async () => {
  const user = userEvent.setup()
  render(<CheckoutForm />)

  await user.type(screen.getByLabelText(/card number/i), '4242424242424242')
  await user.click(screen.getByRole('button', { name: /pay/i }))

  expect(screen.getByRole('button', { name: /pay/i })).toBeEnabled()
})
```

## The network boundary — mock with MSW, only what you own

Mock the network at the boundary, not by stubbing `fetch` or the client module. MSW intercepts the request itself, so the code under test runs its real client, real serialization, and real error handling — the test exercises everything up to the socket and replaces only the server. This is the `craft-tdd.md` rule "only mock what you own" applied to HTTP: you own the request contract, so mock the contract, not your own fetch wrapper.

- **Stand one `setupServer` up per suite, fail closed on any unhandled request, and reset handlers between tests** so a per-test override never leaks into the next case.

```ts
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  http.get('/api/profile/:id', ({ params }) =>
    HttpResponse.json({ id: params.id, name: 'Ada Lovelace' }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

- **`onUnhandledRequest: 'error'` is the house default** — a request no handler matches is a bug in the test or the code, not a warning to scroll past. It also guarantees no test silently reaches the real network.
- **Override per test with `server.use(...)` for the unhappy paths** — a 500, a timeout, a malformed body — to prove the code degrades correctly. This is a saboteur stub in the `craft-xunit.md` taxonomy; name it as one.

```ts
it('surfaces a retry banner when the profile endpoint is down', async () => {
  server.use(
    http.get('/api/profile/:id', () => new HttpResponse(null, { status: 503 })),
  )
  render(<Profile id="u_1" />)
  expect(await screen.findByRole('alert')).toHaveTextContent(/try again/i)
})
```

- **Do not mock a module you own to fake the network** (`vi.mock('./api-client')`). That skips the code you most want covered and lets the mock drift from the real client. Mock your own modules only to cut a genuinely awkward seam — a clock, a randomness source, a third-party widget with no test hook.

## Property-based testing — the default for pure logic (fast-check)

Property tests assert an invariant over a large generated input space and **shrink** any failure to a minimal counterexample, so they catch cases you would never enumerate by hand. fast-check is the house engine. The pure logic — a parser, a normalizer, the reducer that folds events into state — is where properties earn their keep; it has no React runtime, no DOM, and no network, so it runs thousands of cases in the time a component test renders once.

- **Write a property as `fc.assert(fc.property(...arbitraries, predicate))`.** Favor strong properties — a round-trip (`decode(encode(x))` equals `x`), idempotence (`f(f(x))` equals `f(x)`), a conservation law, or agreement with a slow-but-obvious oracle — over trivially-true ones. Inside the predicate use `expect`, so a failure reports which side diverged rather than a bare `false`.

```ts
import fc from 'fast-check'

const genEntry = fc.record({
  account: fc.constantFrom('cash', 'ar', 'revenue'),
  cents: fc.integer({ min: -100_000, max: 100_000 }),
})

it('folds ledger entries independent of order', () => {
  fc.assert(
    fc.property(fc.array(genEntry), (entries) => {
      const forward = balance(entries)
      const reversed = balance([...entries].reverse())
      expect(forward).toEqual(reversed)
    }),
    { seed: 4242, numRuns: 500 },
  )
})

it('round-trips a parsed amount back to its canonical string', () => {
  fc.assert(
    fc.property(fc.integer({ min: 0, max: 1_000_000 }), (cents) => {
      expect(parseMoney(formatMoney(cents))).toEqual(cents)
    }),
  )
})
```

- **Build compound inputs from arbitraries — `fc.record`, `fc.array`, `fc.constantFrom`, `fc.option`** — and constrain at generation time (`{ min, max }`) rather than drawing wide and discarding. Discards feed fast-check's exhaustion guard and can starve a run; reserve `fc.pre(...)` for a condition you genuinely cannot express in the generator.
- **When a property finds a counterexample, copy the minimized case into a named example test before you fix the code** — the property covers the space, the example pins this exact regression forever. Then fix and watch both go green.
- **Pin the seed on any committed property** (`{ seed }` per call, or `fc.configureGlobal({ seed })` in setup) so a green run stays green and a failure reproduces byte for byte across machines. The pure logic is where reducers, parsers, and domain calculations live — property-test it here so the component tests can assume it correct.

## Determinism — no flakiness

A flaky test is a broken test; a suite you cannot trust is one you stop reading. Every source of nondeterminism is injected or faked.

- **No real clock.** Freeze time with `vi.useFakeTimers()` and set the instant with `vi.setSystemTime(new Date('2026-01-01T00:00:00Z'))`; restore with `vi.useRealTimers()` in an `afterEach`. Advance deliberately with `vi.advanceTimersByTimeAsync(ms)` rather than waiting. When a component under fake timers also needs `userEvent`, wire the two together via user-event's `advanceTimers` option (`userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`), or its internal delays will hang.
- **No real network and no ambient randomness.** MSW covers HTTP; a `Math.random` or `crypto` dependency is injected and stubbed (`vi.spyOn`, or a seed passed in), never read from the global. Push wall-clock and randomness to the edges so the core is a pure function of its arguments and can be property-tested.
- **Do not sleep to wait for async work.** A hand-rolled `setTimeout` or `await new Promise(r => setTimeout(r, 50))` races the machine and flakes under load. Wait on the observable outcome instead — `findBy*` or `waitFor(() => expect(...))` retries until the assertion holds or a bounded timeout fails it.
- **Restore every global you touch.** `vi.stubGlobal`, `vi.spyOn`, and fake timers must be undone in teardown — set `restoreMocks: true` (and `unstubGlobals: true`) in the Vitest config so leakage between files is impossible, and never rely on file execution order.

## Coverage — a signal, not a target

- **Measure with the v8 provider (`@vitest/coverage-v8`, `coverage.provider: 'v8'`) and read it as a map of untested lines, never a number to hit.** A percentage mandate gets gamed into assertion-free tests that execute code and prove nothing. Prefer branch coverage over statement coverage — a statement-covered `if` whose false arm never runs is a hole the number hides.
- **Never call a function with no assertion to raise the count**, and never snapshot a tree to "cover" a component. A covered line with no assertion is untested. The way to move the number is more behavior pinned, not more lines touched. An anti-weakening gate scores coverage against the merge-base; keep it up by adding assertions, not lines.

## The test split — fast unit, integration, e2e

- **Keep most tests fast in-memory unit tests, fewer integration tests, fewest end-to-end** — the pyramid `craft-tdd.md` draws. Pure-logic and single-component suites are the fast base and run on every save. A component-plus-MSW suite that exercises a data flow is integration. A full-browser run (Playwright, Cypress) that drives the real app is e2e — the slowest and fewest, kept to the critical journeys.
- **Do not test in the wrong tier.** A pure calculation does not need a rendered component; a rendered component does not need a real browser. Push each assertion to the fastest tier that can make it, and gate the slow tiers (real browser, live services) behind a separate command so the default `vitest run` stays fast and hermetic.

## Anti-weakening (what the differential gate forbids)

Treat any of these versus the merge-base as test-suite weakening — do not introduce them:

- A test or property deleted with no equivalent replacement, or a previously-running case newly disabled with `it.skip`, `describe.skip`, `it.todo`, `xit`, or a commented-out body. The `vitest/no-disabled-tests` rule flags these.
- **An `it.only` / `describe.only` / `fdescribe` committed** — it silently disables every other test in the file. The `vitest/no-focused-tests` rule fails the build on it; never merge one.
- A net drop in assertion sites for a suite (removed `expect`, a dropped `it.each` row, a deleted `.rejects.toThrow`), or a property's `fc.property` narrowed to a fixed example that no longer covers the space.
- A `want` loosened to a wildcard, a `toEqual` downgraded to a truthiness check, an `expect(...).toThrow()` deleted, or an error swallowed where it was previously asserted.
- `numRuns` lowered, or a fast-check generator widened so the hard cases (the empty array, the boundary amount, the all-fields-absent record) are no longer reached.
- A deterministic seed removed from a property (re-admits flakiness), or a fake clock swapped back to the real one to make a timing assertion "pass".
- A failing assertion downgraded to a `console.log` so the failure becomes invisible, or a whole-tree snapshot dropped in as a substitute for the specific assertions it replaced.
- A committed regression example (the minimized counterexample copied from a past property failure) deleted — that re-admits a known-bad input.

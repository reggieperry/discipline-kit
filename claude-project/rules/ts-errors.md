---
paths:
  - "**/*.ts"
  - "**/*.tsx"
---

# TypeScript errors in the types

TypeScript inherits JavaScript's `throw`, which can throw any value and carries no type in the signature — so the discipline here is to pull failures back into the types wherever a caller branches on them, and to keep `throw` for the genuinely exceptional. A caught value is `unknown`, a custom error carries a discriminant, an expected failure rides a `Result` union rather than a thrown exception, and a floating rejected promise is a bug the linter must catch. Sources: the TypeScript Handbook (the `unknown` type, narrowing, discriminated unions, `never` for exhaustiveness); *Effective TypeScript* (Vanderkam), Items on modeling state with unions and on preferring `unknown` to `any`; the MDN `Error` reference (`Error`, `cause`, the built-in subclasses, `Error.isError`); typescript-eslint (`no-floating-promises`, `no-misused-promises`, `only-throw-error`); the neverthrow `Result` API; and the React docs on error boundaries. The design principle behind several of these rules — define errors out of existence — comes from `craft-complexity.md`.

> See `craft-complexity.md` for defining errors away, `craft-domain-modeling.md` for modeling the failure cases as part of the domain, `ts-types.md` for the discriminated-union and `unknown`/`never` machinery these rules lean on, `ts-react.md` for the component side of error boundaries, `ts-security.md` for what must never reach a user-facing message, and `ts-llm.md` for feeding validation errors back to the model.

## A caught value is `unknown` — narrow before you touch it

- **Turn on `useUnknownInCatchVariables` (it ships inside `strict`) and never widen it back.** A thrown value can be anything — a string, a number, a plain object — so the caught binding is typed `unknown`, and the compiler forces a narrowing before any property access. Reading `err.message` off an untyped catch is the same latent bug as a `null` dereference: it works until the day something throws a non-`Error`.
- **Narrow with `instanceof Error`, then fall through to a string coercion for the rest.** Do not assert the type with `as Error` — the assertion is a lie the moment a library throws a string.

```ts
function messageOf(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "unknown error";
}

try {
  await settleTrade(order);
} catch (err: unknown) {
  logger.warn(messageOf(err));
  throw err; // rethrow the original; see "handle once"
}
```

- **Do not annotate the catch binding as anything but `unknown`.** `catch (err: any)` and `catch (err: Error)` are both errors — the first defeats the flag, the second is unsound because the runtime makes no such guarantee. Where a helper must accept a caught value, its parameter type is `unknown`.
- **`instanceof` is unreliable across a realm boundary** (a value thrown from a different JS context, an iframe, or a bundling seam that duplicated the `Error` class). Where that is a real risk, narrow structurally — check `Error.isError(err)` (the platform predicate) or test the discriminant field directly (below) rather than the prototype chain.

## Custom errors subclass `Error` and carry a discriminant

- **Model a distinguishable failure as a subclass of `Error`, never a plain object or a bare string.** A subclass gives a real stack trace, works with `instanceof`, and — with a discriminant field — lets a caller switch on the failure mode. Set `name`, and thread the underlying cause through the standard `cause` option so the chain survives.

```ts
type ParseErrorKind = "empty-input" | "not-a-number" | "out-of-range";

class ParseError extends Error {
  readonly kind: ParseErrorKind;
  constructor(kind: ParseErrorKind, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "ParseError";
    this.kind = kind;
  }
}

throw new ParseError("not-a-number", `expected a port, got "${raw}"`);
```

- **Prefer a single subclass with a `kind` discriminant over a deep class hierarchy** when the cases share a shape. Callers switch on `kind`, the compiler checks exhaustiveness (below), and there is one place to look. Reach for separate classes only when the cases carry genuinely different payloads a `kind` field cannot unify.
- **Name the discriminant field consistently across the codebase — house default is `kind`** (reserve `type` for framework payloads that already claim it) — so every error union reads the same way and a shared handler can switch on one field.
- **Never `throw` a non-`Error`.** `throw "boom"`, `throw { code: 500 }`, and `throw Promise.reject()` all produce a value with no stack and defeat every `instanceof` narrowing downstream. The `@typescript-eslint/only-throw-error` rule (formerly `no-throw-literal`) enforces this with type information; keep it on and treat a finding as a real defect.

## Errors as values for expected failure; `throw` for the exceptional

- **Split failures into two categories and handle each in its own mechanism.** An *expected, recoverable* failure — parse failure, validation failure, a not-found lookup, a remote call that can fail — belongs in the return type, so the caller cannot forget it. A *truly exceptional* condition — a broken invariant, an unreachable branch, a misconfiguration the program cannot continue past — is a `throw`. The test is whether the immediate caller has a sensible branch to take; if it does, the failure is data, not an exception.
- **House default for the value-carrying shape is a `Result` discriminated union** — the neverthrow `Result<T, E>` (`ok(value)` / `err(error)`), or an equivalent hand-rolled `{ ok: true; value: T } | { ok: false; error: E }`. Pick one shape per codebase and hold to it; a Result and a hand-rolled union mixed in one module is the tax `craft-complexity.md` warns about.

```ts
import { ok, err, type Result } from "neverthrow";

function parsePort(raw: string): Result<number, ParseError> {
  if (raw === "") return err(new ParseError("empty-input", "port is empty"));
  const n = Number(raw);
  if (!Number.isInteger(n)) return err(new ParseError("not-a-number", `not a number: ${raw}`));
  if (n < 1 || n > 65535) return err(new ParseError("out-of-range", `port ${n} out of range`));
  return ok(n);
}
```

- **Chain value-errors with `andThen`; short-circuit on the first `err`.** A `Result` is fail-fast by construction — `andThen` threads the happy path and passes any `err` straight through, so a dependent sequence reads top to bottom without a pyramid of `if (result.isErr())`.

```ts
const conn = parsePort(rawPort).andThen((port) => connect(host, port));
```

- **A plain `T | undefined` is the right return only for a bare present/absent lookup with no reason to report** — the analog of an `Option`. The moment the caller needs to know *why* it failed, upgrade to a `Result`; do not overload `undefined` to mean both "absent" and "malformed."
- **Do not stack a `Result` inside a thrown exception, or vice versa.** Pick the mechanism at the function's contract and commit; a function that both returns `err(...)` and `throw`s for related failures forces every caller to guard twice.

## Model the failure in the return type — pick by what the caller does

- **Return a `Result<T, E>` when the immediate caller will branch on the outcome and the failure is part of the normal result.** The type makes the failure visible at the call site and the compiler will not let it be dropped — this is the default across the pure, non-UI core.
- **`throw` when the caller almost always cares only about the happy path and the failure should ride to a distant handler** — an HTTP boundary, a job runner, a React error boundary. Threading a `Result` through ten layers that each only forward it is pass-through overhead (`craft-complexity.md`); let it throw and catch once at the top. The trade-off — the error type vanishes from the signature — is one to make consciously, not by habit.
- **Keep the two convertible at the boundary.** `Result.fromThrowable` / `ResultAsync.fromPromise` wrap a throwing API into a value at the seam where you enter value-land; `result.match(onOk, onErr)` or an explicit `if (result.isErr()) throw result.error` re-enters throw-land at the seam where you leave it. Convert deliberately at a named boundary, not scattered mid-expression.

```ts
import { ResultAsync } from "neverthrow";

const body: ResultAsync<Payload, FetchError> = ResultAsync.fromPromise(
  fetch(url).then((r) => r.json() as Promise<Payload>),
  (cause): FetchError => new FetchError("fetch failed", { cause }),
);
```

## Never swallow, and handle each error once

- **An empty `catch {}` is banned.** A catch block that does nothing hides the failure and the bug behind it. If ignoring is genuinely correct, make it a deliberate, commented decision that at minimum narrows and logs, and name why the failure is safe to drop.
- **Never `catch` only to rethrow a vaguer error that loses context.** If you rewrap, pass the original through `cause` (`new DomainError("...", { cause: err })`) so the chain survives to the log at the top.
- **Handle each error exactly once.** Do not both log it and rethrow it — that produces duplicate, confusing log lines from every layer it passes through. Log where you actually handle and stop the failure, or propagate it with context, not both. The place that decides the user-facing response is the place that logs.
- **Keep the `try` block to the minimum statements that can throw.** A wide `try` obscures which call failed and risks catching an exception you did not anticipate — the same discipline as a narrow `except`.

## No floating promises, no promise where a value is expected

- **Every promise must be `await`ed, returned, or explicitly handled — a floating promise swallows its own rejection.** An async call whose result is discarded turns a rejection into an unhandled-rejection event far from the code that caused it, and on some runtimes into a process crash. Enable `@typescript-eslint/no-floating-promises`; it is one of the highest-value rules in the set.

```ts
// wrong — the rejection floats, unobserved
void 0;
saveOrder(order);

// right — await it, or deliberately detach with a handler
await saveOrder(order);
saveOrder(order).catch((err: unknown) => logger.error(messageOf(err)));
```

- **Never pass an async function where a void-returning callback is expected.** An `onClick={async () => …}` or an `array.forEach(async …)` returns a promise into a slot that ignores it, so rejections vanish and ordering guarantees evaporate. `@typescript-eslint/no-misused-promises` flags exactly this; where a handler must do async work, wrap the body so the outer callback stays synchronous and the inner promise is handled.
- **Reject an async function with an `Error`, the same as `throw`.** `Promise.reject("nope")` produces a caught `unknown` that is not an `Error`; `only-throw-error` covers rejections too. Reject with a real error object so downstream narrowing holds.

## Exhaust the error union — let `never` prove you did

- **Switch on the discriminant and make the default branch impossible.** When a caller handles a typed error union, an exhaustive `switch` with a `never`-typed default forces a compile error the day a new case is added — the safety a stringly-typed error throws away. This is the union-side payoff of the `kind` discriminant.

```ts
function assertNever(x: never): never {
  throw new Error(`unhandled error kind: ${JSON.stringify(x)}`);
}

function explain(e: ParseError): string {
  switch (e.kind) {
    case "empty-input":
      return "Provide a port number.";
    case "not-a-number":
      return "The port must be a number.";
    case "out-of-range":
      return "The port must be between 1 and 65535.";
    default:
      return assertNever(e.kind); // adding a 4th kind breaks the build here
  }
}
```

- **Handle only the cases whose recovery changes behavior; let the rest propagate.** You do not owe every layer a handler for every failure — code the happy path, recover the specific cases you can do something about, and let an unrecovered error reach the one boundary that decides the response. Exhaustiveness is for the union you have chosen to handle, not a mandate to handle every union everywhere.

## React error boundaries catch render-time failures

- **A thrown error during render is caught by an error boundary, not a `try/catch`.** React unwinds a subtree that throws while rendering; without a boundary above it, the whole app unmounts. Wrap each independently-recoverable region — a route, a panel, a widget — in a boundary so one failure degrades locally instead of blanking the page. An error boundary is a class component defining `static getDerivedStateFromError` (to render the fallback) and/or `componentDidCatch` (to log), or the `ErrorBoundary` component from `react-error-boundary` with a `FallbackComponent` (or `fallbackRender`) and an `onError` reporter.

```tsx
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";

function Fallback({ error, resetErrorBoundary }: FallbackProps): JSX.Element {
  // `error` is unknown-shaped at runtime — coerce, never render it raw
  return (
    <div role="alert">
      <p>This panel could not load.</p>
      <button onClick={resetErrorBoundary}>Retry</button>
    </div>
  );
}

<ErrorBoundary FallbackComponent={Fallback} onError={reportToTelemetry}>
  <TradeBlotter />
</ErrorBoundary>;
```

- **Error boundaries do not catch async, event-handler, or SSR errors** — only errors thrown during render, in lifecycle methods, and in constructors below them. A rejection from a click handler or a data fetch never reaches the boundary; handle those as values (a `Result` in state) or route them into the boundary deliberately by setting error state that the next render throws. Do not expect the boundary to cover a floating promise.

## Never leak a secret or an internal into a user-facing error

- **A user-facing message says what the user can do; it never carries a token, a key, a credential path, a stack trace, a SQL fragment, or a raw upstream error.** Those belong in the log behind the boundary, keyed to a correlation id the user can quote. This is the split between the internal error (rich, logged once, private) and the presented message (safe, actionable, generic).
- **Render the message at the edge from the typed case, not by surfacing `err.message` through the stack.** The internal `Error` may carry a detailed message for the log; the string a caller shows is derived from the discriminant, so an implementation detail can never accidentally reach a screen or an API response.
- **Do not serialize an `Error` straight into an HTTP response body or a client payload.** `JSON.stringify(err)` and returning `{ error: err.message }` are the common leaks. Map to a stable, enumerated response shape — a code plus a safe message — and log the rest. (See `ts-security.md` for the full boundary discipline.)

## Define errors out of existence

- **Prefer redefining an operation so the error case becomes the normal case** over adding another failure return — a `removeIfPresent` that succeeds when the item is already gone needs no error path at all, and an API that returns an empty list rather than a "not found" failure removes a branch from every caller. Where you cannot define the error away, handle it as low as you can (mask it) or aggregate many handlers into one high in the call path — a single boundary that maps the whole error union to a response beats a `try/catch` at every layer. Fewer failure sites means simpler, more reliable code and a smaller surface to get wrong (`craft-complexity.md`).

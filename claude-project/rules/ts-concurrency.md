---
paths:
  - "**/*.ts"
  - "**/*.tsx"
---

# TypeScript async concurrency

Promise lifecycle, cancellation, and bounded parallelism for code that runs on a single-threaded event loop and does real I/O — HTTP calls, a model API, file reads, subprocesses. The concurrency here is cooperative, not parallel: one thread interleaves many in-flight promises at `await` points, so the failure modes are floating promises, unbounded fan-out against a rate-limited service, interleaved reads and writes of shared state, and a blocked event loop, not data races on memory. Sources: MDN on `async`/`await`, `Promise` (`all`, `allSettled`, `race`, `any`), `AbortController`/`AbortSignal` (including the `AbortSignal.timeout()` and `AbortSignal.any()` static methods), and the event loop and microtask queue; the Node.js docs on the event loop, `worker_threads`, and `Symbol.asyncDispose`; Dan Vanderkam, *Effective TypeScript* (the items on preferring `async`/`await` to raw callbacks and never mixing them); and the typescript-eslint rules `no-floating-promises`, `no-misused-promises`, and `await-thenable`, plus the core ESLint `no-await-in-loop`.

> See `ts-errors.md` for how a rejected promise surfaces and the `unknown` catch clause, `ts-types.md` for typing the resolved value and narrowing `AbortSignal.reason`, `ts-testing.md` for driving async code deterministically with fake timers, `ts-react.md` for effect cleanup and request cancellation inside components — which this rule deliberately leaves out — and `craft-tdd.md` for keeping concurrency policy out of the logic so the logic stays unit-testable.

## async/await over raw promise chains

- **Write `async`/`await`; do not build `.then()`/`.catch()` chains by hand.** `await` linearizes control flow so the code reads top to bottom, error handling is a plain `try`/`catch`, and the types flow — `await p` where `p: Promise<Money>` yields `Money` with no callback plumbing. A `.then()` chain nests scope, drops values silently when a handler forgets to `return`, and splits error handling across `.catch()` arms. Effective TypeScript's rule is the house rule: prefer `async`/`await`, and do not mix the two styles on one operation.
- **Never mix `await` and `.then()` on the same value.** Pick one per operation. Threading a value through `await` and then handing the result to `.then()` reintroduces exactly the nesting `await` removed and makes the failure path ambiguous.
- **A function that contains `await` must be `async`; do not hand-roll a promise you could `await`.** Reserve `new Promise((resolve, reject) => …)` for wrapping a genuinely callback- or event-based API at the seam (a Node stream, an `EventEmitter`); everything past the seam is `async`/`await`.

```ts
// Wrap a callback API once, at the seam; the rest of the code is async/await.
function once(emitter: EventEmitter, event: string): Promise<unknown> {
  return new Promise((resolve) => emitter.once(event, resolve));
}

async function loadOrder(id: OrderId): Promise<Order> {
  const row = await db.orders.find(id); // linear; try/catch handles rejection
  return toOrder(row);
}
```

## Never leave a promise floating

A floating promise — one whose result is neither awaited nor otherwise consumed — is the sharpest defect in async code. Its rejection becomes an unhandled rejection, its ordering is nondeterministic, and the error surfaces far from its cause or not at all.

- **Enable `@typescript-eslint/no-floating-promises` and treat it as an error, not a warning.** Every promise-returning call in statement position must be handled one of three ways: `await` it, chain a `.catch()` that handles the rejection, or explicitly discard it with the `void` operator when firing it deliberately is the intent. There is no fourth option; a bare `doThing()` that returns a promise is the bug the rule exists to catch.
- **Use `void` only when discarding is deliberate, and pair it with an attached error handler** — `void thing().catch(reportError)`. `void` silences the linter but does not handle the rejection; a `void` with no `.catch()` still crashes on rejection. Prefer awaiting; reach for `void` for a genuine fire-and-forget (a best-effort metric emit) where the caller must not wait.
- **Enable `@typescript-eslint/no-misused-promises` too.** It catches the adjacent mistake — passing an `async` function where a void-returning callback is expected (an event handler, an `Array.prototype.forEach` callback, an `if` condition), so the returned promise floats invisibly. And enable `await-thenable`, which flags `await` on a non-promise (usually a forgotten call — `await fn` instead of `await fn()`).

```ts
// Awaited — the default.
await recordSignature(order);

// Deliberate fire-and-forget MUST carry its own rejection handler.
void emitMetric("order.signed").catch(reportError);

// no-misused-promises catches this: the async callback's promise floats.
items.forEach(async (i) => { await save(i); }); // flagged — use a for-of loop
```

## Combinators and bounded concurrency

The whole point of concurrency here is to overlap independent I/O. Choose the combinator by how failure should behave, and cap the fan-out so a batch cannot open unbounded connections against a metered API.

- **`Promise.all` for independent effects that must all succeed** — it resolves to the tuple of results and rejects on the first rejection. Note it does not cancel the siblings still in flight (JavaScript has no ambient cancellation); it only stops waiting for them, so thread an `AbortSignal` when the abandoned work should actually stop.
- **`Promise.allSettled` when you want every result regardless of individual failures** — it never rejects and returns a `{ status: "fulfilled" | "rejected" }` array to inspect per item. Use it for a batch where one bad element must not sink the rest.
- **`Promise.race` for the first settlement (win or lose), `Promise.any` for the first success.** `race` rejects if the first to settle rejects; `any` skips rejections and rejects only if all fail (with an `AggregateError`). Use `race` for a timeout-versus-work pattern, `any` for redundant sources where the first good answer wins.
- **Bound fan-out — never `Promise.all(items.map(callApi))` against a rate-limited service.** Mapping an array straight into `Promise.all` opens one in-flight call per element; a thousand-item batch is a thousand simultaneous connections. Gate concurrency with a limiter — the small, dependency-light `p-limit` is the house default (`pLimit(n)` returns a function that queues calls past `n` in flight). Choose `n` deliberately against the service's documented limits.

```ts
import pLimit from "p-limit";

// House default for a batch against a metered API: bounded concurrency.
const limit = pLimit(6); // at most 6 concurrent model calls
const results = await Promise.all(
  orders.map((o) => limit(() => scoreOrder(o, { signal }))),
);

// Want per-item outcomes instead of first-failure? allSettled.
const settled = await Promise.allSettled(orders.map((o) => limit(() => scoreOrder(o))));
const failures = settled.filter((r) => r.status === "rejected");
```

## No await in a loop when the calls are independent

- **Enable the core ESLint `no-await-in-loop`.** Awaiting inside a `for`/`while` body serializes the iterations — each call waits for the previous to finish — which throws away the concurrency `async`/`await` exists to provide. When the iterations are independent, build the array of promises and combine them (through a limiter, per the section above), do not `await` one at a time.
- **Keep the loop only when the iterations are genuinely dependent** — pagination that needs the previous cursor, a retry with backoff, a sequence where step N reads step N-1's result. That is the sanctioned exception the rule documents; disable it inline with a one-line comment stating why, rather than turning the rule off globally.

```ts
// Independent — do NOT serialize with await-in-loop.
const rows = await Promise.all(ids.map((id) => limit(() => fetchRow(id))));

// Dependent — the sequential await is correct; say so.
let cursor: Cursor | undefined;
do {
  // eslint-disable-next-line no-await-in-loop -- each page needs the prior cursor
  const page = await fetchPage(cursor);
  cursor = page.next;
} while (cursor);
```

## Cancellation: thread an AbortSignal

There is no ambient cancellation on the event loop — a promise you stop awaiting keeps running. The only mechanism is `AbortController`/`AbortSignal`, and it works only if the signal reaches the actual I/O.

- **Accept an optional `signal: AbortSignal` on every function that does cancelable I/O, and forward it to the underlying call** — `fetch(url, { signal })`, the SDK's request option, a subprocess's abort option. A signal that stops at your function boundary and never reaches `fetch` cancels nothing. This is the async analog of threading a lifetime through the call graph; do not stash the controller in module state.
- **Prefer the static factories over hand-built timers.** `AbortSignal.timeout(ms)` returns a signal that aborts itself after the deadline (reason set to a `TimeoutError`), replacing the `setTimeout` + `controller.abort()` + `clearTimeout` dance. `AbortSignal.any([a, b])` combines signals so a request aborts when either a caller-supplied signal or a local timeout fires. Put a timeout on every external call — the model API especially needs a bounded budget.
- **On abort, the pending promise rejects; distinguish that rejection from a real failure.** An aborted `fetch` rejects with an `AbortError` (or the signal's `reason`). Check `signal.aborted` or narrow the error before treating it as a fault, so a deliberate cancellation is not logged as a service outage.

```ts
async function scoreOrder(order: Order, opts: { signal?: AbortSignal } = {}): Promise<Score> {
  // Local budget, combined with any caller signal.
  const signal = opts.signal
    ? AbortSignal.any([opts.signal, AbortSignal.timeout(30_000)])
    : AbortSignal.timeout(30_000);

  const res = await fetch(scoringUrl(order), { signal }); // signal reaches the I/O
  return parseScore(await res.json());
}

// Caller distinguishes a deliberate abort from a real failure.
try {
  await scoreOrder(order, { signal: controller.signal });
} catch (err) {
  if (controller.signal.aborted) return; // canceled — not an outage
  throw err;
}
```

## Do not block the event loop

Node and the browser run your JavaScript on one thread. While a synchronous call runs, no other promise makes progress, no timer fires, and — on a server — no other request is served. Concurrency here is about yielding at `await` points, not about parallel threads.

- **Never call a synchronous, CPU-bound or thread-parking function on the request path.** Use `fs.promises.readFile`, not `fs.readFileSync`; the async socket APIs, not blocking ones. A synchronous JSON parse of a large payload, a synchronous crypto hash, or a tight compute loop stalls every in-flight promise until it returns.
- **Move genuine CPU-bound work off the event loop with a `worker_threads` Worker** (or a worker pool). This is the correct tool for parsing a huge document or running an expensive transform; `await`ing it does not help, because `await` yields at I/O, not mid-computation. A worker runs on its own thread and communicates by message-passing, so there is no shared-memory race to reason about.
- **Understand the microtask ordering: awaited continuations (microtasks) run before the next timer or I/O callback (macrotasks).** A tight recursive promise chain can starve timers and I/O. When you must break up a long synchronous span to let the loop breathe, yield explicitly with `await new Promise((r) => setTimeout(r, 0))` rather than assuming an `await` on an already-resolved value yields the loop.

```ts
import { Worker } from "node:worker_threads";

function hashInWorker(payload: Buffer): Promise<string> {
  return new Promise((resolve, reject) => {
    const w = new Worker(new URL("./hash-worker.js", import.meta.url), { workerData: payload });
    w.once("message", resolve); // CPU work runs off the event loop
    w.once("error", reject);
  });
}
```

## Shared state across interleaved awaits

Single-threaded does not mean race-free. Every `await` is a yield point where another task can run and mutate shared state. A read-modify-write straddling an `await` is a check-then-act race, the same hazard as a preemptive data race, minus the memory tearing.

- **Do not read a shared value, `await`, then write back based on the stale read.** Between the read and the write, another interleaved task may have changed it. Capture what you need before the `await`, or serialize access so only one task holds the resource at a time.
- **Serialize access to a single-writer resource with a promise chain or a mutex, not by hoping the interleaving works out.** A minimal serializing pattern chains each operation onto the tail of the previous promise; for anything beyond that, a small async-mutex library. This is the analog of guarding a shared field — one synchronization discipline per piece of shared state, applied consistently.
- **Prefer designing the shared state away.** Pass values as function arguments and return new results rather than mutating module-level state across awaits; immutable data threaded through the call graph has no interleaving hazard to reason about. Reach for a guarded mutable cell only when a genuinely shared resource (a connection, a token bucket) demands it.

```ts
// RACE: the read of `balance` and the write straddle an await.
async function badDebit(amount: Money): Promise<void> {
  const current = account.balance;      // read
  await audit.record(amount);           // yield — another debit can run here
  account.balance = current - amount;   // write from a possibly-stale read
}

// Serialize: each op chains onto the previous, so writes never interleave.
let tail: Promise<void> = Promise.resolve();
function debit(amount: Money): Promise<void> {
  tail = tail.then(async () => {
    await audit.record(amount);
    account.balance -= amount;          // single-writer, no interleaving
  });
  return tail;
}
```

## Structured cleanup

Whatever a scope acquires it must release — on the normal path, on a thrown error, and on cancellation. The async control flow makes the leak easy to miss, so make the cleanup structural rather than hand-placed at each exit.

- **Release with `finally`, or with `await using` when the resource declares async disposal.** A `try/finally` around an acquired handle runs the finalizer on every exit; that is the baseline. Where a resource implements `Symbol.asyncDispose`, `await using` (TypeScript 5.2+, `lib` set to include `esnext.disposable`) binds it to the block scope and disposes it automatically at scope exit, in reverse acquisition order — the same guarantee without a hand-written `finally` per resource.
- **Make disposal idempotent and non-throwing where you can.** A finalizer that throws while unwinding another error masks the original; catch and report inside the finalizer rather than letting it replace the in-flight failure.
- **Do not leave a timer, subprocess, or open connection dangling on the error path.** These are the resources a missing `finally` leaks. If a function opens it, that function's scope closes it.

```ts
// Prefer await using when the resource implements Symbol.asyncDispose.
async function withConnection(): Promise<Report> {
  await using conn = await pool.acquire(); // disposed at scope exit, even on throw
  return runReport(conn);
}

// Baseline: try/finally guarantees the release on every exit.
async function readOnce(path: string): Promise<string> {
  const handle = await fs.open(path, "r");
  try {
    return await handle.readFile({ encoding: "utf8" });
  } finally {
    await handle.close(); // runs on success, throw, and cancellation
  }
}
```

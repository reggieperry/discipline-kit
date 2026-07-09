---
name: feedback-async-cancellation-model
description: "Five asyncio rules from Fluent Python 2e Part V (Ramalho) — cancel-points only at await, TaskGroup for structured concurrency, executor \"pretense\" of cancellation, the no-I/O-bound-system myth, async iteration as its own cancellation surface, and the bounded-shutdown discipline. Conceptual companion to [[feedback-pr-review-patterns]] Pattern 2."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

[[feedback-pr-review-patterns]] Pattern 2 captured the *tactical* cancellation fixes from a PR review — `try/finally`, tracked task sets, sibling cancellation through `gather`. Ramalho gives the *mental model* underneath: cancellation is cooperative, lands only at `await` points, and the asyncio surface has subtle gotchas around executors and async iteration that the tactical fixes don't reach. The rules below are the conceptual layer.

**Why:** the five cancellation defects that prompted Pattern 2 all trace back to the same missing model — treating async functions as if they could be cancelled mid-statement. Internalizing Ramalho's "cancel-point only at await" framing prevents the next round of defects rather than catching them after.

**How to apply:** when writing or reviewing any `async def`, walk these five rules. Most relevant when designing lifespan handlers, long-running coroutines, or any function that schedules background tasks.

---

## 1. Every `await` is a cancel-point and a yield-point — the body between awaits is atomic

**Rule.** Mentally annotate every `await` in an async function as the only place cancellation can land and the only place blocking is allowed. CPU-bound work longer than ~5ms between two awaits stalls the entire event loop.

**Why.** Fluent Python Ch 19 "Supervisors Side-by-Side": "a coroutine can only be cancelled when it's suspended at an `await` expression." Cooperative multitasking makes the body between awaits implicitly atomic; conversely, every blocking call between awaits freezes every other coroutine sharing the loop.

**Trigger.** Any `async def` that does CPU-bound work — data merging, graph walks, JSON validation of payloads, `re.search` over text, stage handlers, heartbeat loops.

**How to apply.** Walk each `async def` and mark the awaits. Any CPU-bound block longer than ~5ms between two awaits goes through `await asyncio.to_thread(...)` (with rule 3's caveats) or `await asyncio.sleep(0)` as a stopgap. Document at the top of long-running coroutines which awaits are the cancel-points callers should expect to land on.

---

## 2. Sync libraries in an `async def` body freeze the process — `time.sleep`, blocking SQL drivers, `requests`, `urllib`

**Rule.** In any `async def`, `time.sleep`, sync HTTP clients (`requests`, `urllib`), sync DB drivers (`psycopg` sync mode), and raw `socket.recv` block the entire event loop, not just the calling coroutine. Wrap in `asyncio.to_thread` or replace with the async equivalent.

**Why.** Fluent Python Ch 19 "Experiment: Break the spinner for an insight." Replacing `await asyncio.sleep(3)` with `time.sleep(3)` causes the UI spinner to never appear because no other coroutine gets a turn.

**Trigger.** Any new code that mixes `psycopg` sync sessions with `async def` (even when the project standardizes on SQLAlchemy 2.0 async mode, a single sync escape is enough); any developer reaching for `requests` instead of `httpx.AsyncClient`; sync SDK calls inside a FastAPI lifespan handler or background tasks.

**How to apply.** In review, grep new async files for `time.sleep`, `requests.`, `psycopg2.`, `urllib`, raw `socket.`. Each hit: either wrap in `await asyncio.to_thread(...)` or replace with the async equivalent. The PR description should explicitly name which sync libraries the new code reaches for and why they're acceptable.

---

## 3. `run_in_executor` / `asyncio.to_thread` give the *pretense* of cancellation, not cancellation

**Rule.** Treat work submitted to `asyncio.to_thread` or any `run_in_executor` as **uncancellable from the asyncio side**. Push cancellation responsibility into the synchronous code: a periodic check on a `threading.Event` set by the lifespan, or a `WHERE status IN (...)` predicate that makes a stale write a no-op.

**Why.** Fluent Python Ch 21, Caleb Hattingh's tech-reviewer warning under "Delegating Tasks to Executors": "the underlying thread (if it's a ThreadPoolExecutor) has no cancellation mechanism. For example, a long-lived thread that is created inside a `run_in_executor` call may prevent your asyncio program from shutting down cleanly: `asyncio.run` will wait for the executor to fully shut down before returning, and it will wait forever if the executor jobs don't stop somehow on their own."

**Trigger.** Any component that uses `asyncio.to_thread` for sync SQLAlchemy sessions. The heartbeat-vs-finalizer race that [[feedback-async-thread-boundary]] partially covers is exactly this symptom. Any sync SQL `UPDATE` inside `asyncio.to_thread` during a lifespan-cancel path is affected.

**How to apply.** Cap executor work units to a hard wall-clock budget so shutdown can't hang indefinitely. Name the executor in the docstring: *"This coroutine cannot be interrupted between line N and line M because the work runs in the default ThreadPoolExecutor."* The `WHERE status IN (...)` predicate already in [[feedback-async-thread-boundary]] is the right pattern for making a late write a no-op.

---

## 4. Adopt `asyncio.TaskGroup` for structured concurrency where children's lifetime equals the parent's

**Rule.** Replace the manual `create_task` + tracked set + `try/finally` cancel-and-drain pattern with `async with asyncio.TaskGroup() as tg: tg.create_task(...)` wherever the children's lifetime is bounded by the enclosing scope. Keep the manual tracked-set pattern only for tasks that truly outlive the function that spawns them.

**Why.** Fluent Python Ch 21 "async Beyond asyncio: Curio." Quoting: "Task Groups support structured concurrency: a form of concurrent programming that constrains all the activity of a group of asynchronous tasks to a single entry and exit point... a TaskGroup ensures that all tasks spawned inside are completed or cancelled, and any exceptions raised, upon exiting the enclosed block." Available in Python 3.11+; pairs with `ExceptionGroup` (PEP 654).

**Trigger.** Any per-item fan-out that already uses an explicit gather + sibling-cancel pattern; this is a stronger replacement. Other candidates: any handler that spawns parallel reads, a shared-state dispatch. A lifespan-scoped tracking set (see [[feedback-pr-review-patterns]] Pattern 2) stays — those tasks outlive the lifespan body, so TaskGroup doesn't fit.

**How to apply.**
```python
async with asyncio.TaskGroup() as tg:
    for item in applicable_items:
        tg.create_task(_process_and_persist_one(item, parent_id=pid, deps=deps))
# All children completed-or-cancelled at exit; exceptions raised as ExceptionGroup.
```
When a child raises, the TaskGroup cancels siblings automatically — no manual `for t in tasks: t.cancel()` loop. Handle the resulting `ExceptionGroup` (or use `except* SomeError:` syntax) at the caller.

---

## 5. Lifespan teardown must bound every cleanup — `KeyboardInterrupt`/SIGTERM otherwise waits for the executor

**Rule.** The FastAPI lifespan teardown wraps each cleanup phase in `asyncio.wait_for(..., timeout=N)` and logs a warning rather than propagating the `TimeoutError`. Document the worst-case shutdown wall-clock in the lifespan docstring; verify with a test that injects a stuck executor job.

**Why.** Fluent Python Ch 21 `tcp_mojifinder.py` + executor warning (rule 3). On SIGINT/SIGTERM, asyncio cancels tasks, drains them, and *waits for the executor*. A wedged executor pins shutdown past Kubernetes' `terminationGracePeriodSeconds`, after which the pod is SIGKILL'd and durable state may not finalize.

**Trigger.** A lifespan handler that awaits a reconciliation task and calls a shutdown routine with its own timeout. The `to_thread` executor pool itself has no bound; a stuck DB UPDATE inside a `to_thread` can outlive that routine's timeout.

**How to apply.** Each cleanup phase gets an explicit timeout:
```python
try:
    await asyncio.wait_for(reconciliation_task, timeout=5.0)
except (asyncio.CancelledError, asyncio.TimeoutError):
    pass
await shutdown_in_flight_work(timeout=30.0)  # bounded
# If we ever add a default executor we own:
loop.shutdown_default_executor(timeout=10.0)  # 3.12+; on 3.11 wrap with asyncio.wait_for
```
Test: monkeypatch `to_thread` to hang, assert the lifespan teardown completes within the documented budget.

---

## What this memory does NOT add (because already covered)

- The Pattern 2 tactical fixes (`try/finally`, tracked tasks, sibling cancellation in gather) — see [[feedback-pr-review-patterns]].
- `BaseException` vs `Exception` for `CancelledError` — see [[feedback-pr-review-patterns]] Pattern 2.
- Bounded fan-out via `asyncio.Semaphore` — see [[feedback-security-when-writing-code]].
- Per-request timeouts on LLM calls — see [[feedback-security-when-writing-code]] and [[feedback-pr-review-patterns]] Pattern 1.

## Related memory

- [[feedback-pr-review-patterns]] — Pattern 2 is the tactical companion to this conceptual layer
- [[feedback-async-thread-boundary]] — the thread/loop boundary discipline; rule 3 here extends it
- [[feedback-concurrency-invariant-design]] — Postgres-side concurrency invariants
- [[feedback-typechecker-adoption]] — mypy catches missing-`await` and other async surface gotchas
- [[reference-sources-to-consume]] — Fluent Python 2e is the priority asyncio reference

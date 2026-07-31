---
paths:
  - "**/*.py"
---

# Python async concurrency

**Enforcement grade:** partly mechanical — `ruff` and `mypy` catch a few async slips (an un-awaited coroutine, a sync call typed async) through Check A. Cancellation, task lifetime, and blocking-the-loop are review and convention.

Structured concurrency with `asyncio` for code that does I/O and calls external services. Sources: the asyncio docs (tasks, the event loop), Python 3.11+ `TaskGroup`/`timeout`, and the GIL.

> See `craft-tdd.md` for separating functionality from concurrency policy so logic stays unit-testable, `python-llm.md` for timeouts on model calls, and `python-style.md` for the surrounding idioms.

## Structured concurrency

- **Use `asyncio.TaskGroup` (3.11+) for concurrent subtasks, not bare `gather`** — a TaskGroup cancels the remaining tasks on the first failure and raises an `ExceptionGroup`, where `gather` lets siblings run on. Handle failures with `except*` against the `ExceptionGroup`.
- **Reserve `asyncio.gather(..., return_exceptions=True)` for the one niche where you deliberately want per-task results-or-errors with no cancellation.**
- **Use `asyncio.run(main())` as the single program entrypoint** — it creates and tears down the loop correctly.

## Deadlines and cancellation

- **Set deadlines with `async with asyncio.timeout(delay):` (3.11+) over `wait_for`** — it is nestable, reschedulable, and raises `TimeoutError`. Put a timeout on every external call (the LLM API, a CLI subprocess such as `git`, the network).
- **Catch `asyncio.CancelledError` only to clean up, then re-raise it — never swallow it.** Suppressing cancellation breaks `TaskGroup` and `timeout`; call `task.uncancel()` only in the rare case you truly absorb a cancellation.
- **Keep a reference to every `asyncio.create_task()` result** — a task with no live reference can be garbage-collected mid-flight. Reserve `asyncio.shield()` for the rare operation that must survive caller cancellation.

## Don't block the loop

- **Never call a blocking function inside a coroutine** — use `await asyncio.sleep()` not `time.sleep()`, and async I/O libraries, not blocking sockets. One blocking call freezes every task on the loop.
- **Offload unavoidable blocking calls with `await asyncio.to_thread(fn, *args)`** (IO-bound only — it propagates `contextvars`). The GIL is the reason threads help I/O but not CPU work; push CPU-bound work to a `ProcessPoolExecutor`.

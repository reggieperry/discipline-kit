---
name: Trace the async/thread boundary explicitly
description: When code crosses asyncio / threadpool / SQLAlchemy worker thread boundaries, write down explicitly what runs where. Don't assume; the failures are silent.
type: feedback
volatility: durable
---
When code crosses asyncio / threadpool / executor boundaries, name the thread and event loop for each piece. The failures here are silent — wrong assumptions don't crash, they produce no-ops or races.

**Why:** A PR review surfaced two of these and they were the worst kind because the code looked fine in isolation. (1) `asyncio.get_running_loop()` raised in FastAPI sync `def` endpoints (which run in a threadpool), so the post-commit dispatch hook silently skipped the common path; the admin POST never kicked the pipeline. (2) `task.cancel()` on the heartbeat asyncio Task didn't propagate to an `asyncio.to_thread` worker mid-flight, so a "cancelled" heartbeat could still race the finalizer and overwrite a terminal status. Both were one-line conceptual mistakes that produced wrong-but-not-erroring runtime behaviour.

**How to apply:**
- Any time code uses `asyncio.to_thread`, `loop.run_in_executor`, a sync FastAPI endpoint (`def` instead of `async def`), or any sync DB call from an async coroutine — write a comment naming the thread and loop for each piece. "This runs on the event-loop thread; this runs in a worker thread; this scheduled task lives on the main loop."
- `asyncio.get_running_loop()` only works on the event-loop thread. From a worker thread, capture the main loop at startup (`set_main_loop(asyncio.get_running_loop())` in lifespan) and reach back with `asyncio.run_coroutine_threadsafe`.
- `task.cancel()` on an asyncio Task does not cancel the thread inside an `asyncio.to_thread` call. If the thread is mid-UPDATE, the UPDATE still runs. Guard with predicates at the persistence layer (e.g. `.where(status.in_('claimed','running'))`) so a stale write is a no-op.
- When a variable is reachable from two threads, ask: what protects it? When a coroutine is scheduled cross-thread, ask: which loop?
- FastAPI sync vs async endpoint choice matters: sync `def` → threadpool, async `def` → main loop. Code that needs the main loop must be on an async endpoint or use a captured-loop pattern.

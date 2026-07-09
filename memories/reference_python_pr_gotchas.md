---
name: Python / FastAPI / SQLAlchemy / Pydantic gotchas
description: Checklist of small idiom errors that surfaced in code review. Quick reference when writing or reviewing code in these areas.
type: reference
volatility: durable
---
Compact checklist of small idiom errors from code review. Use when writing or reviewing code in the affected areas.

## Pydantic

- **Required `list[X]` accepts `[]`.** Pydantic v2 doesn't enforce non-empty by default. If "required" means non-empty, add `Field(..., min_length=1)`.
- **`@field_validator` for cross-field rules; `@model_validator(mode="after")` when one field constrains another.** Pure type/length constraints belong on `Field(...)`.

## SQLAlchemy

- **In `__table_args__` for partial indexes, the mapped column isn't yet resolvable.** Don't use `Column("status").in_(...)` (the class constructor — produces an unbound Column object). Use `sa.text("status IN ('claimed','running')")` for `postgresql_where`, matching the migration's expression exactly.
- **`with_for_update()` doesn't work on the right side of an outer join.** When the query has `joinedload(Parent.children)` (which produces a LEFT OUTER JOIN), use `with_for_update(of=Parent)` to lock only the parent row. Postgres rejects the unrestricted form.
- **`db.commit()` between two writes destroys atomicity.** If two operations should commit-or-rollback as one unit, defer the commit to the last operation. The first one's commit is exactly what creates the half-applied-state bug.
- **`Session.close()` rolls back uncommitted changes by default.** So an exception escaping a route handler doesn't leak uncommitted writes — but only because the session dependency's finally clause closes the session. Don't rely on this if a path between the write and the exception calls `commit()`.

## Async / FastAPI

- **Sync `def` endpoints run in a threadpool; async `def` endpoints run on the event loop.** `asyncio.get_running_loop()` only works on the event-loop thread. From a sync endpoint, it raises.
- **Cross-thread coroutine scheduling needs `asyncio.run_coroutine_threadsafe(coro, loop)`.** Capture the loop at lifespan startup; reach back from worker threads.
- **`task.cancel()` doesn't cancel `asyncio.to_thread` workers** that are already executing. The thread runs to completion; the CancelledError surfaces only when control returns to async-land. Guard the persistence side with WHERE predicates so a stale write is a no-op.

## Library exceptions at module boundaries

- **Don't let a library's native exception class (e.g. `openpyxl.KeyError`) escape a public function in your own module.** Catch and translate to your module's exception type (`DataDictionaryError(["sheet not found: ..."])`). Callers shouldn't have to know which library is underneath.

## Standard idiom traps

- **`list.count(x)` inside a comprehension iterating that same list is O(n²).** Reach for `collections.Counter`, `set`, or a dict in one pass.
- **`{k for k in xs if xs.count(k) > 1}` looks clever and is the same trap.** Same fix.

## FastAPI lifespan

- **The lifespan handler is the only place an `asyncio` event loop is reliably available at process start.** Capture singletons (the main loop, registries, clients) here. Sync code that runs later can't call `asyncio.get_running_loop()` from the wrong thread.

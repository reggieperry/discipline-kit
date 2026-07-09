---
name: feedback-pr-review-patterns
description: Eight defensive-coding patterns distilled from a PR review
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

A PR review produced 22 validated fixes that cluster into eight recurring patterns. Each is a defensive habit to reach for when the relevant code surface appears, not a thing to learn after a reviewer points it out.

**Why:** all 22 were missed during initial coding. The failure mode was reading code with "does this work?" eyes instead of "what could go wrong?" eyes. These patterns capture the latter.

**How to apply:** when writing code that touches any of the surfaces below, run the relevant pattern through proactively. When reviewing your own code before pushing, run the full eight-pattern checklist.

---

## 1. Validate at boundaries, not in the middle

Data crossing an untrusted or unbounded boundary into the system needs explicit defense at the entry point. Upstream contracts (SDK timeouts, vector-distance ranges, LLM-returned IDs) are *hopes*, not guarantees.

- External HTTP/LLM call → set explicit `timeout=` via the client's `with_options(timeout=...)` or `asyncio.wait_for`. Default SDK timeouts (e.g., 600s with 2 retries = 30 min hang) are too long.
- Retrying a failure path → cap attempts and add a cooldown gate so a doomed input doesn't loop forever.
- API response carrying internal data → sanitize. Error messages exposed via APIs should be class name only; full detail goes to `logger.exception` server-side. `f"{type(exc).__name__}: {exc!s}"` is leaky (SDK / DSN / chunk fragments).
- Prompt assembled from documents → byte-budget the chunks blob (e.g., 64 KiB) and add an explicit "untrusted data" directive to the system prompt. Document text is not a directive to the model.
- Similarity ratios from a vector store → clamp to `[0, 1]` with `max(0.0, min(1.0, x))`. Cosine misfires can surface negatives.
- LLM-returned identifiers (chunk_ids, entity UUIDs) → validate against the source table before persisting. On miss, null + log; never persist dangling references.

Triggers to watch for: chat-completion / embedding calls, any `httpx`/`aiohttp` call, any `response.choices[0]` or `result.value` from an LLM, any field passed straight from API request into DB.

## 2. Plan for cancellation, not just exceptions

`asyncio.CancelledError` derives from `BaseException`, not `Exception`, so `try/except Exception` skips it. In async code, **cancellation is the normal exit at shutdown**, not exceptional.

- Any async function that allocates a resource (DB row, network connection, task) → use `try/finally` for cleanup, not `try/except`.
- Every `asyncio.create_task` that escapes the calling function → track in a module-level `set[asyncio.Task]`. The lifespan teardown must `cancel()` + `gather(..., return_exceptions=True)` with a bounded wait. Untracked tasks strand state.
- Inside `asyncio.gather(..., return_exceptions=True)` → it does NOT cancel sibling tasks when the gather itself is cancelled. Materialize the task list, wrap in `try/except CancelledError`, then cancel siblings and drain via a second `gather` before re-raising.
- `except (asyncio.CancelledError, Exception): pass` → never. Split the except: `CancelledError → pass`, `Exception → logger.warning(..., exc_info=True)`. Lumping hides genuine errors.
- Bare `except Exception` in async code → add a one-line comment naming that `CancelledError` is intentionally not caught, so cancellation propagates.

Triggers to watch for: `async def`, `asyncio.create_task`, `asyncio.gather`, lifespan handlers, any long-running coroutine that touches the DB.

## 3. Configuration is part of the public API

Any tunable a future operator might want to change at runtime should be runtime-tunable, with the invariant relationships between values documented next to them.

- Timing constants (heartbeat interval, reclaim threshold, request timeout, retry cap, cooldown duration) → in `Settings`, not module-level.
- Magic numbers passed to stage handlers (top_k, concurrency caps, fan-out limits, byte budgets) → through dependencies / settings, not hardcoded at call sites.
- Read settings via a small accessor function (`def _heartbeat_interval_seconds() -> int: return settings.X`) so test-time monkeypatches take effect on next call rather than at import.
- When values are interdependent, document the invariant: e.g., `RECLAIM_THRESHOLD > LLM_REQUEST_TIMEOUT > HEARTBEAT_INTERVAL`.

Triggers to watch for: `_DEFAULT_X = 60`, `top_k=8`, any `await asyncio.sleep(N)` with literal N, any hardcoded byte / count / timeout.

## 4. Migrations are symmetric

Upgrade and downgrade are equal-weight code paths; both need the same rigor.

- Every FK to a parent table → explicit `ondelete=` policy ("CASCADE" or "RESTRICT"). No default-without-thinking.
- Every `op.drop_table` in `downgrade()` → guard against user-authored / human-source data. Pattern: `SELECT COUNT(*) WHERE source = 'human'` → if `> 0`, raise with a clear message asking the operator to export first.
- Every migration that introduces a new table → corresponding entry in the migration-validation script's EXPECTED list.
- Verify upgrade-head + downgrade-base end-to-end on a fresh local Postgres before pushing. See [[feedback-local-migration-testing]]; this review added the human-authored-rows guard subpattern.

Triggers to watch for: `op.create_table`, `op.drop_table`, `ForeignKeyConstraint`, any new alembic file.

## 5. "Disabled" defaults need explicit re-enable hooks

Commented-out code rots silently. Visible placeholders force re-enable to surface in a diff.

- Every new mutating endpoint in a branch where auth is disabled → carries a commented `# _rbac=Depends(authorize_action("admin", "default"))` (or the appropriate tier) on its signature.
- Same for read endpoints that surface PII / per-project status.
- Same shape on `auth_router`, `CORS allow_origins=["*"]`, and similar "disabled for now" toggles: leave the production-correct value commented adjacent to the current one so the re-enable is a one-character diff per surface.

Triggers to watch for: any new `@router.post|.get|.put|.delete|.patch`, any auth-related `# `-commented line in the app entry point.

## 6. Concurrency invariants belong in docstrings

"Idempotent" / "thread-safe" / "no-op on retry" are claims. The invariant that makes the claim true is what to document.

- If a function relies on an upstream lock (a partial unique index, a SELECT FOR UPDATE on a parent row, an external advisory lock) for thread-safety → name the dependency in the docstring. Include the file:line of the lock so future-you can find it.
- If a "DELETE-then-INSERT" shape assumes a single writer → flag the assumption with a TODO that names what changes invalidate it (e.g., "wrong the moment user-authored rows land").
- The three idempotency invariants (don't crash on retry / last-writer-wins / reset to pristine — see [[feedback-idempotency-semantics]]) are not interchangeable. Pick the one that matches the retry semantic and name it.

Triggers to watch for: any function with "idempotent" or "safe to retry" in its docstring, any DELETE before INSERT, any UPSERT.

## 7. Claims need tests

When you write words like *idempotent*, *no-op on retry*, *cancellation-safe*, *bounded*, *degraded mode* — treat them as flags. Find or write the test that proves the claim. See [[feedback-claims-need-tests]] for the founding instance; this review reinforced it for cancellation and a re-kick cap.

Tests that prove cancellation-safety must actually call `task.cancel()` and inspect the durable record. Tests that prove a cap must drive the function past the cap and assert the no-op.

## 8. Algorithmic complexity is part of the spec

When a loop is O(n²) and only an input bound keeps it safe, name both — worst case and the cap that makes it acceptable. Future-you may raise the cap and need to know.

```python
# O(n²) worst case (n = number of entities). Bounded acceptable because
# _MAX_ENTITIES = 200 caps the walk at ~40K dict lookups, negligible vs
# the LLM call cost. If _MAX_ENTITIES rises significantly, memoize via
# ancestor_cache: dict[str, set[str]].
```

Triggers to watch for: nested loops over a collection that comes from an external boundary, any "this works because n is small" mental note.

---

## Related memory

- [[feedback-async-thread-boundary]] — companion to Pattern 2 on thread/loop boundaries
- [[feedback-security-when-writing-code]] — Pattern 1's broader security frame
- [[feedback-idempotency-semantics]] — the three-invariants taxonomy referenced in Pattern 6
- [[feedback-claims-need-tests]] — the founding statement of Pattern 7
- [[feedback-local-migration-testing]] — verification step for Pattern 4
- [[reference-python-pr-gotchas]] — small-idiom checklist; this memory is the larger-shape companion
- [[reference-sources-to-consume]] — external reading list that would have caught most of these proactively

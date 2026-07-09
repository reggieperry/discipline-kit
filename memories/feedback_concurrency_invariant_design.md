---
name: feedback-concurrency-invariant-design
description: "Seven rules from DDIA (Kleppmann) Chs 7-9 on naming invariants and picking the right defense per shape. Write skew vs single-row, MVCC snapshot scope, conditional UPDATE under snapshot isolation, idempotency keys for external side effects, monotonic vs wall-clock time, fencing tokens, safety vs liveness. Extends [[feedback-pr-review-patterns]] Pattern 6 and [[feedback-idempotency-semantics]] for the multi-row and stale-belief cases they don't cover."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

Any orchestration spine that runs work under concurrency exercises every concurrency surface DDIA Chs 7-9 covers — DB transactions, multi-worker claim/heartbeat, stale-belief on lease holders, external side effects (an LLM gateway or other paid API), safety vs liveness in reconciliation. The rules below capture the patterns the books surface that the existing memory does not yet name.

**Why:** [[feedback-pr-review-patterns]] Pattern 6 says "name the concurrency invariant in the docstring," but doesn't taxonomize the *kinds* of invariants and the *defenses* that fit each. [[feedback-idempotency-semantics]] covers the three retry-invariants but is silent on multi-row invariants, stale-belief, and the safety/liveness distinction. These rules fill those gaps.

**How to apply:** when designing or reviewing a function that touches durable state and runs under concurrency, walk the seven rules in order and pick the ones that fit the surface. Most functions only need 2-3; a few (the runner, persistence, status transitions) need most of them.

---

## 1. Write skew is its own category; row-locks on what you read aren't enough

**Rule.** When the function reads a set of rows to decide whether to act, and then writes a *different* row whose presence changes the set, you have write skew. Single-row defenses (`SELECT ... FOR UPDATE`, `ON CONFLICT`) do not cover it.

**Why.** DDIA Ch 7 "Write Skew and Phantoms" — write skew is a multi-row generalization of lost updates. Two concurrent transactions read overlapping rows, decide based on the read, write disjoint rows, and the multi-row invariant they each assumed is now violated by the combined effect.

**Trigger.** A reconciliation loop deciding whether to reclaim a stale run row (reads many, writes one); "at least one approver per field" rules; "all required fields populated → transition to AWAITING_REVIEW" checks; writer-arbitration where the choice depends on the absence of a sibling row.

**How to apply.** Name the invariant in plain English ("no two workers claim the same job," "at least one approver per field"). Pick one of three defenses:
- **Postgres `UNIQUE` or `EXCLUDE` constraint** covering the invariant — best when the invariant is a property of the table. A partial unique index on `runs(job_id) WHERE status IN ('claimed','running')` is exactly this shape.
- **`SELECT … FOR UPDATE` against a parent row** whose lock protects the whole set — best when there's a natural anchor (a parent row guards its child set).
- **`SERIALIZABLE` isolation on the specific code path** — best when no constraint and no anchor row exists. Heavier; reach for it case-by-case, not as a default.

Don't reach for `FOR UPDATE` on an empty result set — it locks nothing.

---

## 2. The MVCC snapshot is one transaction wide and ends at commit

**Rule.** When a function's correctness depends on "the state I read at line 10 still describes the state at line 30," wrap it in `REPEATABLE READ` explicitly. Default `READ COMMITTED` reads a fresh snapshot per statement.

**Why.** DDIA Ch 7 "Snapshot Isolation and Repeatable Read" — Postgres's default `READ COMMITTED` gives each statement a fresh snapshot, so multi-statement functions read a moving target. `REPEATABLE READ` pins one snapshot for the whole transaction. Neither includes the transaction's own pending writes from outside its visibility window.

**Trigger.** Any handler or background coroutine that issues two related SELECTs in the same session (load parent + load its children, load run + load its child runs); a dashboard reading mid-processing; cross-stage reads inside an orchestration spine.

**How to apply.**
```python
with db.connection().execution_options(isolation_level="REPEATABLE READ"):
    with db.begin():
        parent = db.scalar(select(Parent).where(...))
        children = db.scalars(select(Child).where(Child.parent_id == parent.id))
        # both reads see the same snapshot
```
Default `READ COMMITTED` is fine for single-statement work and intentional polling. Say so in the docstring when you stay with the default — silent assumption of consistency is what produces the read-skew anxiety.

---

## 3. Compare-and-set is conditional, not atomic — assert the row count

**Rule.** Every state-machine `UPDATE` includes the prior-state check in the `WHERE`, returns `RETURNING *` (or checks `rowcount`), and the caller treats `rowcount == 0` as "someone beat us," not as success.

**Why.** DDIA Ch 7 "Compare-and-set" — `UPDATE x SET v = new WHERE v = old` is lost-update prevention, but the `WHERE` can evaluate against a stale snapshot under `REPEATABLE READ` and silently succeed even when another writer changed the value first. Postgres re-reads the row under `READ COMMITTED`, but the pattern is unsafe under stricter isolation, and it always requires the caller to check the row count.

**Trigger.** A run-claim that uses a partial unique index for the single-claimant invariant alongside reconciliation `UPDATE runs SET status='failed' WHERE status IN ('claimed','running') AND last_heartbeat_at < cutoff` shapes. Any state-machine transition (`change_status` and per-stage transitions) is the same pattern.

**How to apply.**
```python
result = session.execute(
    update(Run)
    .where(Run.id == run_id)
    .where(Run.status.in_(("claimed", "running")))
    .values(status="done")
    .returning(Run.id)
)
updated = result.first()
if updated is None:
    raise ConcurrentTransitionError(...)  # someone else won
```
The unit test for the transition must drive two concurrent updates against the same row in a real Postgres session and assert exactly one wins. This is reachable today with `pytest.mark.integration`.

---

## 4. Retries with external side effects need an application-level dedup key

**Rule.** Every external side effect that costs money or has at-least-once semantics (LLM call, email, webhook, payment) carries an **idempotency key** derived deterministically from the caller's identity for that attempt. Reuse the same key across all retry layers for the same attempt; only bump the key when bumping the attempt number.

**Why.** DDIA Ch 7 "Handling errors and aborts" — five failure modes for naive retries, including: the request succeeded but the ack was lost (retry duplicates work), and side effects outside the DB happen even when the transaction aborts. The defense is named in [[feedback-idempotency-semantics]] as the "don't crash on retry" invariant; the **how** is the dedup key.

**Trigger.** Every paid API call in a per-field extraction or a structured-output call. Multiple retry layers can fire for the same attempt: the SDK's transparent retries, an `asyncio.wait_for` cap, the stage-level error path, and the reconciliation reclaim. All of them bill the gateway.

**How to apply.** Derive the key from `(run_id, item_key, attempt_number)`. Pass via `extra_headers={"Idempotency-Key": key}` into the request (if the SDK supports it). Persist the key on the per-item row (an `idempotency_key` column). The stage-level retry reuses the same key for the same attempt. Reconciliation produces a new key only when it bumps `attempt_number`. Reinforces [[feedback-idempotency-semantics]] for the "external side effect" case it doesn't currently name.

---

## 5. Use a monotonic clock for elapsed time; never compare wall-clock timestamps across processes

**Rule.** Elapsed time inside a process → `time.monotonic()`. Cross-process ordering → an authoritative source: Postgres `clock_timestamp()` (single source of truth) or a monotonic sequence (an `attempt_count`, a `bigserial` event_id).

**Why.** DDIA Ch 8 "Monotonic Versus Time-of-Day Clocks" + "Timestamps for ordering events" — NTP can drag the wall clock backward; in VMs the clock can jump forward by tens of milliseconds; last-writer-wins conflict resolution silently drops writes when two clocks disagree.

**Trigger.** Heartbeat staleness checks (`now() - last_heartbeat_at > threshold`); a reconciliation cooldown gate; any write-arbitration tie-break between two writers; log timestamp correlation across workers.

**How to apply.** Inside a single coroutine, `start = time.monotonic(); ...; elapsed = time.monotonic() - start`. For DB-stored timestamps, write them via `func.now()` or `func.clock_timestamp()` so Postgres is the single source. For "is this stale," compare two Postgres-written timestamps from the same DB (single clock). Reject any code that subtracts two `datetime.now()` calls from different processes.

---

## 6. A lease/lock holder cannot trust its own belief — protect the resource with a fencing token

**Rule.** Every claim that grants exclusive access to a resource gets a monotonically increasing fencing token. Every write from the holder includes the token in the `WHERE`; the resource rejects writes with a token less than the highest already seen.

**Why.** DDIA Ch 8 "The leader and the lock" + "Fencing tokens" — a process can pause arbitrarily (GC, VM steal, SIGSTOP) between `lease.isValid()` and the protected write. The lease expires; another holder takes over. The paused process resumes and writes anyway. Defense: the resource (not the holder) enforces the invariant.

**Trigger.** A `claimed_by` column identifies the worker but doesn't act as a fence — a paused worker could come back and overwrite a finalized row. A partial unique index prevents two *active* claims, but it doesn't prevent a stale write from a previously-active claim. This is the safety-property formalization of the existing [[feedback-async-thread-boundary]] discipline.

**How to apply.** Add a `claim_token: BIGINT` column to the run table, incremented per (re-)claim. Every UPDATE from a worker includes `WHERE claim_token = :token AND status IN ('claimed','running')`. Reconciliation increments the token when it reclaims. The persistence layer treats `rowcount == 0` as "stale write rejected — superseded by token N" and the worker logs + exits its loop. *This is a real schema change; capture as a follow-up story, not a same-PR fix.*

---

## 7. Articulate safety properties separately from liveness; only safety must hold under all conditions

**Rule.** In every docstring touching concurrency, write two labeled bullets — `Safety: ...` and `Liveness: ...`. The safety bullet must have a test that drives the function past the boundary (crash mid-write, double-claim, token rollback) and asserts the invariant. The liveness bullet may have a test asserting eventual progress under a happy assumption, plus a TODO naming when that assumption fails.

**Why.** DDIA Ch 8 "Safety and liveness" + Ch 9 "Fault-Tolerant Consensus" — safety = nothing bad ever happens (uniqueness, monotonicity, no double-commit); liveness = something good eventually happens. Safety violations cannot be undone. Liveness can be caveated (only if a majority is up; only if the network eventually recovers).

**Trigger.** Every docstring on an orchestration surface claiming "idempotent," "bounded," "exactly-once," "no-op on retry" — all safety. Claims like "reconciliation eventually reclaims stranded runs," "cooldown elapses then the job retries" — liveness. The two need different tests; the test failures mean different things.

**How to apply.** In docstrings:
```python
"""
Safety: at most one worker ever holds an active claim on a given job at
any moment. Guaranteed by the partial unique index uq_runs_active_job.

Liveness: a stranded job (status=PROCESSING, no active run) is re-kicked
within RECONCILIATION_INTERVAL_SECONDS. Guaranteed only if the
reconciliation loop is running.
"""
```
The safety test runs concurrent claims and asserts one wins. The liveness test runs a stranded job past the reconciliation tick and asserts re-kick. Sharpens [[feedback-claims-need-tests]] — "no-op" and "degraded mode" are safety claims; "eventually consistent" is liveness.

---

## Defense-selection cheat sheet

| Invariant shape | Defense |
|---|---|
| "At most one writer on a single row" | `SELECT … FOR UPDATE` on that row |
| "At most one row matching this predicate" | Postgres `UNIQUE` or partial unique index |
| "Multi-row property the writes break" (write skew) | `EXCLUDE` constraint, anchor-row lock, or `SERIALIZABLE` |
| "Transition iff prior state = X" | CAS with `WHERE prior=X` + rowcount check (rule 3) |
| "External call shouldn't double-bill on retry" | Idempotency key (rule 4) |
| "Stale lease-holder shouldn't corrupt resource" | Fencing token (rule 6) |
| "Two reads in the same handler must agree" | `REPEATABLE READ` (rule 2) |
| "Time-based decision across processes" | DB clock, not `datetime.now()` (rule 5) |

---

## Related memory

- [[feedback-idempotency-semantics]] — three retry-invariants; rule 4 here adds the external-side-effect axis
- [[feedback-pr-review-patterns]] — Pattern 6 (invariants in docstrings); rule 7 here adds the safety/liveness split
- [[feedback-async-thread-boundary]] — the lease/lock-holder pause is a generalization of the existing thread-boundary discipline
- [[feedback-local-migration-testing]] — required for the schema change in rule 6 if/when adopted
- [[feedback-demo-with-prod-risk]] — rules 6 and 7 are real production hardening, capture as follow-up stories
- [[reference-sources-to-consume]] — DDIA Chs 7-9 priority reading

---
name: feedback-postgres-concurrency-operational
description: "Seven Postgres-specific rules from Fontaine's *The Art of PostgreSQL* — serialization-failure retries with bounded backoff, `INSERT ... ON CONFLICT` over update-then-insert-if-missing, `REFRESH MATERIALIZED VIEW CONCURRENTLY` with required unique index, DDL `ACCESS EXCLUSIVE` lock awareness with `lock_timeout`, `LISTEN`/`NOTIFY` as a wakeup not a queue, append-only event log vs hot-row counter, diagnostic stack `application_name` + `pg_stat_statements` + `EXPLAIN (ANALYZE, VERBOSE, BUFFERS)`. Operational layer on top of [[feedback-concurrency-invariant-design]]."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

[[feedback-concurrency-invariant-design]] gave us the DDIA-level theory (write skew, MVCC scope, CAS, fencing tokens). Fontaine adds the Postgres-specific operational consequences DDIA doesn't show: what "could not serialize access" actually looks like at the wire, what the trigger-upsert anti-pattern looks like and why `ON CONFLICT` is the right primitive, what NOTIFY can and cannot do, and what DDL locks cost.

**Why:** the existing memory says "use Postgres correctly" in the abstract. These rules name the concrete features and SQL syntax. Each rule has a specific surface in a real codebase.

**How to apply:** at design time for new schema or new persistence code, walk the rules. At review time for migrations, use rule 4 (DDL lock awareness) as a checklist. When debugging slow / mysterious queries, run rule 7's three-step triage.

---

## 1. Serialization failures abort the entire transaction — callers MUST retry, not propagate

**Rule.** Any code path running under `REPEATABLE READ` or `SERIALIZABLE` ([[feedback-concurrency-invariant-design]] rule 2) wraps the transaction body in a bounded retry loop catching `psycopg.errors.SerializationFailure` (SQLSTATE 40001) and `DeadlockDetected` (40P01). On retry-exhaustion, surface a 503-shaped error, not the raw SQLSTATE.

**Why.** Ch 36 "Concurrent Updates and Isolation." Fontaine: *"Once an error occurs in a transaction, in PostgreSQL, the transaction can't commit anymore."* Even a subsequent `COMMIT` returns `ROLLBACK`. This is silent under `READ COMMITTED` and mandatory under stricter levels.

**Trigger.** Every code path that follows [[feedback-concurrency-invariant-design]] rule 2 — reads concurrent with a long-running write, multi-statement loads in handlers, cross-stage reads in an orchestration spine.

**How to apply.** Build one decorator and reuse it:
```python
def with_serialization_retry(max_attempts: int = 3):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except sa.exc.OperationalError as exc:
                    sqlstate = getattr(exc.orig, "sqlstate", None)
                    if sqlstate in ("40001", "40P01") and attempt < max_attempts:
                        time.sleep(0.05 * (2 ** (attempt - 1)))
                        continue
                    raise
        return wrapper
    return decorator
```
The retry assumes the function is naturally idempotent — pair with [[feedback-concurrency-invariant-design]] rule 3 (CAS with `WHERE prior=X`) so retried writes are no-ops. Test: drive two parallel `REPEATABLE READ` transactions against the same row in `pytest.mark.integration`, assert exactly one completes after retry.

---

## 2. The "update-then-insert-if-not-found" upsert is a primary-key conflict race — use `INSERT ... ON CONFLICT DO UPDATE`

**Rule.** Never write `UPDATE x SET v=v+1 WHERE k=:k; IF NOT FOUND THEN INSERT ...`. Two concurrent writers both miss, both INSERT, the second fails with `unique_violation`. The Postgres-correct primitive is `INSERT ... ON CONFLICT (key) DO UPDATE` in a single statement.

**Why.** Ch 38 "Trigger and Counters Anti-Pattern." Fontaine walks the exact race: T1 `UPDATE`→0 rows, T2 `UPDATE`→0 rows, T1 `INSERT`→ok, T2 `INSERT`→`duplicate key value violates unique constraint`.

**Trigger.** Persistence code that uses `DELETE`-then-`INSERT` under a single-writer assumption. If you ever add a per-key summary cache, daily counts, or merge logic, the trigger anti-pattern is what you'll write by accident.

**How to apply.**
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
stmt = pg_insert(Summary).values(key_id=kid, item_count=1)
stmt = stmt.on_conflict_do_update(
    index_elements=["key_id"],
    set_={"item_count": Summary.__table__.c.item_count + stmt.excluded.item_count},
)
```
The conflict target needs an actual `UNIQUE` constraint (or partial unique index — repeat the WHERE clause via `index_where=` when targeting a partial). Test: 100 concurrent writers at the same key under `pytest.mark.integration`, assert no `IntegrityError` and final count matches.

---

## 3. `REFRESH MATERIALIZED VIEW CONCURRENTLY` is the only refresh that doesn't block readers — and it requires a unique index

**Rule.** If you cache anything in a materialized view, the view MUST carry a `UNIQUE` index over a non-null column set, and the refresh job MUST use `CONCURRENTLY`. Plain `REFRESH MATERIALIZED VIEW` takes `ACCESS EXCLUSIVE` — readers hang for the duration.

**Why.** Ch 37 "Materialized Views." Postgres needs the unique index to compute a diff between old and new snapshots and apply deltas. Without it, `REFRESH ... CONCURRENTLY` errors out.

**Trigger.** The moment someone asks for an aggregate overview computed on every page load against a large base table, computing it on-read is wasteful and an MV is the simple fix.

**How to apply.** The Alembic migration that creates the view creates the unique index in the same revision; the migration-validation script ([[feedback-pr-review-patterns]] Pattern 4) lists both. Refresh trigger is a cron job or a `LISTEN`-driven worker (rule 5). Never refresh in-band on a write path.

---

## 4. `DROP TABLE` / most `ALTER TABLE` take `ACCESS EXCLUSIVE` — declare the lock level in the migration, set `lock_timeout`

**Rule.** In Alembic migrations that drop a column / table, rename, or change a column type, name the lock level in the migration docstring. Set `lock_timeout = '2s'; statement_timeout = '5s';` at the top so a stuck lock fails fast.

**Why.** Ch 35 "Delete but Keep a Few Rows." Fontaine: *"Those DDL require an access exclusive lock and will block all read and write traffic to both tables while they run."* `ACCESS EXCLUSIVE` is the strongest Postgres lock — queues behind running queries and blocks all new ones until acquired.

**Trigger.** Every Alembic migration you write. A correctness guard in a migration is separate from the lock-level disclosure, which is the *availability* guard.

**How to apply.** Three concrete moves for migrations on populated tables:
- **New non-null column**: add as nullable, batch-backfill (`WHERE id BETWEEN x AND x+1000`), then add `NOT NULL` as a validated `CHECK`. Avoid `ALTER TABLE ADD COLUMN NOT NULL DEFAULT` on big tables — implicit rewrite.
- **New index**: `op.create_index(..., postgresql_concurrently=True)` inside `with op.get_context().autocommit_block():` — `CONCURRENTLY` can't run in a transaction.
- **Any `ALTER TABLE`**: set `lock_timeout = '2s'; statement_timeout = '5s';` at the top of the migration so a stuck lock surfaces as a fast failure rather than hanging `ACCESS EXCLUSIVE` indefinitely.

---

## 5. `LISTEN`/`NOTIFY` is not a queue: it loses messages when no listener is connected, drops duplicate payloads inside a transaction

**Rule.** Don't reach for `LISTEN`/`NOTIFY` to drive an orchestration spine or a reconciliation loop. It's a cache-invalidation and "wake up and poll" primitive — nothing else.

**Why.** Ch 39 "Limitations of Listen and Notify." Fontaine: *"It is crucial that an application using the PostgreSQL notification capabilities are capable of missing events. Notifications are only sent to connected client connections."* And: *"If the same channel name is signaled multiple times from the same transaction with identical payload strings, the database server can decide to deliver a single notification only."* Plus the 8 KB payload cap.

**Trigger.** Any tempting "producer NOTIFYs when work finishes, consumer LISTENs for it" design — would seem to bypass the reconciliation loop but silently misses completions whenever a consumer process restarts.

**How to apply.** If you ever wire LISTEN/NOTIFY, the contract is *only*: "wake up the worker so it re-polls the source of truth." Payload is at most a small key. The worker MUST also have a periodic poll (the existing reconciliation interval) so a missed NOTIFY just delays work by one tick. Safety/liveness split per [[feedback-concurrency-invariant-design]] rule 7: safety guaranteed by the poll; liveness improved by NOTIFY.

---

## 6. Schema-level reframing: append a row instead of incrementing a counter

**Rule.** When a field is hot-write contended (per-entity counter, retry count, "files processed"), don't `UPDATE … SET n = n + 1 WHERE k = :k`. INSERT a row into an append-only event log and compute the counter at read time via `count(*) filter (where …)`. Pair with rule 3 (materialized view) if the read becomes hot.

**Why.** Ch 36 "Modeling for Concurrency." Fontaine benchmarks the `UPDATE … rts = rts + 1` shape against `INSERT INTO activity (action) VALUES ('rt')`. With 100 concurrent workers doing 50 retweets each, the UPDATE version was 36% slower; "the *update* version spent almost 1 second out of 3 seconds waiting for a free slot."

**Trigger.** A hot-write counter column such as an `attempt_count` / `last_error_at` updated on every reclaim by a reconciliation loop — under retry storms (rate-limited upstream, transient backend failures) the row becomes a hotspot. An append-only `events(run_id, key, event_type, occurred_at)` log with a covering index would replace it.

**How to apply.** Schema-level decision, not a code patch. Capture as a follow-up per [[feedback-demo-with-prod-risk]] — for a demo, the counter is fine; for prod-risk hardening, log + MV rollup is the right shape. Don't mix: don't write a trigger that turns the INSERT back into an UPDATE on a summary table without `ON CONFLICT` (rule 2).

---

## 7. Diagnostic stack for slow / suspicious queries: `application_name`, `pg_stat_statements`, `EXPLAIN (ANALYZE, VERBOSE, BUFFERS)`

**Rule.** When a query is mysteriously slow or a UI hang surfaces in dev, the first three moves — in order — are: filter `pg_stat_activity` by `application_name`, find the query in `pg_stat_statements` (mean exec time, calls, IO timing), run `EXPLAIN (ANALYZE, VERBOSE, BUFFERS)` and compare estimated vs effective row counts.

**Why.** Chs 7-8. Fontaine: `application_name` is settable via the connection string or `SET application_name = 'svc/persist'`. `pg_stat_statements` needs `shared_preload_libraries = 'pg_stat_statements'` and a restart. The `EXPLAIN (ANALYZE, VERBOSE, BUFFERS)` triple gives row-count gap *and* buffer-cache breakdown.

**Trigger.** Performance surprises under load. Without `application_name` set per-module, you can't tell from `pg_stat_activity` whether a long-running query came from the ingester, the API, or a worker — they share the pool.

**How to apply.** One-line change in your DB connection setup: add `?application_name=svc-{module}` to the DSN. Enable `pg_stat_statements` in the server config. Add a `make perf-snapshot` target dumping the top-20 slowest queries by mean time. When estimated vs effective row counts diverge by >1000x, check autovacuum / statistics targets first.

---

## What's not in scope

- B-tree / GiST / GIN / BRIN access-method overview — covered by what you already use (vector indexes are GiST-shaped; partial unique indexes are B-tree).
- SSI implementation theory — covered abstractly in [[feedback-concurrency-invariant-design]].
- Window functions, recursive CTEs, JSON operators — pure SQL syntax, not operational rules.
- Table partitioning / FDW / logical replication — out of scope.

## Related memory

- [[feedback-concurrency-invariant-design]] — the DDIA-level theory this memory operationalizes for Postgres
- [[feedback-pr-review-patterns]] — Pattern 4 (migration symmetry); rule 4 here adds availability awareness
- [[feedback-local-migration-testing]] — verify migrations end-to-end; rule 4 here adds `lock_timeout` to the playbook
- [[feedback-python-pr-gotchas]] — small-idiom checklist with SQLAlchemy 2.0 gotchas
- [[reference-sources-to-consume]] — *The Art of PostgreSQL* is the operational Postgres reference

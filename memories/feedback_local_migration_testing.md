---
name: Test locally including Alembic migrations
description: Before declaring DB-touching work done, run the migrations against a local Postgres and exercise the new schema with the new code.
type: feedback
volatility: durable
---
DB-touching changes are not done until they've been exercised against a local Postgres with the migrations applied. Alembic owns schema; an in-code schema-sync flag (e.g. `create_all` on boot) is local-only and not a substitute.

**Why:** migrations that compile aren't migrations that work — column type mismatches, missing indexes, broken downgrades, and data-migration ordering bugs only show up against a real Postgres. Catching them locally is cheap; catching them in CI or after merge is expensive. Pairs with the demo-with-prod-risk posture: a broken migration during a surprise prod cutover is exactly the failure mode that posture is meant to prevent.

**How to apply:**
- For every Alembic migration written, run on a clean local DB: `alembic upgrade head` from empty → success.
- Run on a populated local DB (existing data) when the migration touches existing tables — `alembic upgrade head` preserves data correctly.
- Run `alembic downgrade -1` and re-`upgrade head` to verify the downgrade is real, not a stub.
- After the migration applies cleanly, exercise the new schema with the new code path that consumes it (insert a row, query it, run the relevant unit/integration test) — proves the migration produces the schema the code expects.
- Run a local Postgres (e.g. a docker-compose service). Create any required extensions (such as `vector` or `uuid-ossp`) on first boot via an init SQL script.
- Integration tests should run against a real local Postgres with migrations applied, not against `Base.metadata.create_all()`.
- Don't mark a migration todo "done" until upgrade + downgrade + upgrade has been verified on the local DB.

---
name: sqlalchemy-schema-strip-isolation
description: A conftest db fixture's metadata schema-strip pollutes SQLAlchemy's per-mapper compiled-SQL cache, breaking Postgres tests run in the same session. Use a pytest marker to isolate.
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

Tests that talk to local Postgres via `SessionLocal` must be tagged `@pytest.mark.integration` and run in a separate `pytest -m integration` invocation from the SQLite-backed unit tests.

**Why:** `tests/conftest.py`'s `db` fixture creates an in-memory SQLite engine for unit tests. To make Postgres-typed models work against SQLite, it mutates `Base.metadata` in place — strips `table.schema` to `None` and remaps `JSONB` → `JSON`. Restoration on teardown puts the attributes back, BUT by then SQLAlchemy has compiled and cached INSERT/UPDATE SQL on the per-mapper bindings (and on engine + connection statement caches). The cached SQL omits the schema prefix. Subsequent Postgres queries in the same pytest session use the cached schema-less SQL and fail with `psycopg2.errors.UndefinedTable: relation "..." does not exist`.

Tried four fixes in the `db` fixture teardown — none worked:
- `engine.clear_compiled_cache()` — drops engine-level cache only
- `engine.dispose()` — drops the pool (and per-connection caches) but not the mapper cache
- `mapper._memoized_values.clear()` for all mappers
- `sqlalchemy.orm.configure_mappers()` reconfigure pass

The fix is structural: don't share `Base.metadata` between SQLite and Postgres test paths. That refactor is deferred. The workaround in place: `pytestmark = pytest.mark.integration` at the top of the integration test module, plus the `integration` marker registered in `pyproject.toml`.

**How to apply:**
- Any new test file that uses `SessionLocal` (real Postgres) must declare `pytestmark = pytest.mark.integration`.
- Local: `pytest -m "not integration"` for the unit suite; `pytest -m integration` for the integration tests. Separate invocations, separate processes.
- CI: if/when CI runs the whole suite, gate integration tests behind a separate job (`pytest -m integration`) that runs after the unit job (`pytest -m "not integration"`).
- New integration tests need their teardown to delete from any new child tables that have FKs to parent tables (extend the existing teardown pattern as tables are added).

---
name: security-when-writing-code
description: Proactive security rules to apply as code is written, not just in a retroactive audit. Derived from a hardening pass on data-pipeline / LLM-integration code.
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

When writing new code, apply these rules at the keystroke, not in a later cleanup pass. Each one names a class of finding that has shipped and had to be fixed retroactively.

## 1. Never persist `exc!s` into a column that flows out via an HTTP endpoint

**Rule:** error-message columns that get returned by any route must contain only the exception class name (or a correlation id), never the exception string.

**Why:** LLM-client SDK exceptions carry the gateway URL and request body excerpts (= retrieved document chunks). psycopg `OperationalError` carries the DSN. SQLAlchemy errors carry the SQL with parameter values. In an unauthenticated or demo posture every new route is world-readable, so the error column leaks. This exact bug shipped in error-persisting helpers that wrote the exception string to a returned column.

**How to apply:** on any `except Exception as exc:` that ends in a DB write to a column named `error_message` / `rationale` / similar:

```python
# WRONG — leaks gateway URL, document content, DSN
error_message=f"{type(exc).__name__}: {exc!s}"

# RIGHT
logger.exception("<op> failed project=%s", project_id)  # full detail server-side
error_message=f"<op> failed: {type(exc).__name__}"      # class name only over HTTP
```

If the operator needs to correlate, log a correlation id and persist that id, not the message body.

## 2. Bound every Pydantic string that came from an LLM or a document

**Rule:** every `str` field on a Pydantic model that receives LLM output or document chunk content gets a `Field(max_length=...)`.

**Why:** structured-output mode guarantees *shape*, not *value size*. A hallucinated or adversarial response can produce multi-megabyte strings that land verbatim in the DB and in any review UI. This shipped on entity-record models that lacked bounds.

**How to apply:** sane defaults — adjust per domain but never leave open:

| Field shape | `max_length` |
|---|---|
| source_text / rationale | 4096 (4 KiB) |
| name / parent_name / display_name | 256 |
| jurisdiction | 128 |
| entity_type / data_type | 64 |
| source_chunk_id / any UUID-ish | 64 |

For `source_chunk_id` specifically, also prefer `WHERE id = :chunk_id::uuid` over `WHERE id::text = :chunk_id` so non-UUID strings fail at parse time rather than after a sequential scan.

## 3. `maxItems` on every LLM structured-output array

**Rule:** any `"type": "array"` in a JSON schema sent to a structured-output request gets a `"maxItems"`. Also slice/cap in the consumer code (defense in depth).

**Why:** without it, a hallucinated thousand-entity response drives quadratic walks and thousands of DB writes.

**How to apply:**
```python
"entities": {
    "type": "array",
    "maxItems": 200,   # bound at the schema layer
    "items": {...},
}
```
In the consumer:
```python
if len(entities) > _MAX_ENTITIES:
    flags.append(f"entities_truncated: had {len(entities)}, capped at {_MAX_ENTITIES}")
    entities = entities[:_MAX_ENTITIES]
```

## 4. Total byte budget on anything concatenated into an LLM prompt

**Rule:** when formatting retrieved chunks or other variable-size content into an LLM prompt, enforce a total byte budget. Truncate per-chunk with explicit `[...truncated...]` markers; drop trailing chunks if the budget exhausts.

**Why:** prompt cost is a real DoS vector; an adversarial corpus with multi-megabyte chunks can blow past the model's context window and spike per-call cost.

**How to apply:** format retrieved chunks behind a total-byte budget. Default budget 64 KiB; tune per stage based on the model's context and the per-call response budget.

## 5. Destructive migration downgrades refuse if sensitive data exists

**Rule:** any migration `downgrade()` that drops a column or DELETEs rows containing audit-trail / human-corrected / compliance-mandated data must query for that data and raise `RuntimeError` with explicit counts before doing the drop.

**Why:** `op.execute("DELETE FROM x WHERE candidate_index > 0")` happily deletes corrections at index 0 too once the source column is dropped. A requirement that promised corrections survive can be silently broken by a downgrade that looks safe.

**How to apply:**
```python
def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT (SELECT COUNT(*) FROM app.t WHERE …) AS lossy, ..."
    )).one()
    lossy_count, ... = result
    if lossy_count > 0:
        raise RuntimeError(
            f"refusing to downgrade <table>: {lossy_count} rows would be lost. "
            "Export and re-import via a manual script first."
        )
    # ... actual downgrade steps
```

## 6. Every external call gets an explicit timeout

**Rule:** any LLM client, `httpx.AsyncClient(...)`, `psycopg.connect(...)`, and any other outbound IO MUST be constructed with an explicit `timeout=`. Per-unit-of-work coroutines wrap in `asyncio.wait_for`.

**Why:** without timeouts, one hung gateway pins one of N semaphore slots forever and the heartbeat keeps the run "alive" so reconciliation never reclaims. Extending a code spine without naming a pre-existing timeout gap is its own bug.

**How to apply:**
```python
chat_client = SomeAsyncClient(
    api_key=..., base_url=...,
    timeout=httpx.Timeout(connect=5, read=120, write=10, pool=5),
    max_retries=2,
)
conn = psycopg.connect(database_url, connect_timeout=5)
result = await asyncio.wait_for(extract_one_field(...), timeout=180)
```

## 7. Bound the fan-out

**Rule:** `asyncio.gather` whose length depends on request/registry input goes inside an `asyncio.Semaphore`. Long-running orchestrators have a module-level cap on concurrent runs.

**Why:** unbounded gather × paid LLM calls = cost amplification and gateway DoS. A surge after a process restart can saturate everything.

**How to apply:** give every input-sized fan-out its own `Semaphore`. Top-level orchestrators sit behind a module-level semaphore matching the in-flight budget.

## 8. Parameterize every `text()` and `op.execute()`

**Rule:** SQL strings never contain f-string interpolation or `+` concatenation. Bind params via `:name` + dict. Identifiers (schema/table/column names) that come from anywhere outside a literal must come from an allow-list.

**Why:** SQLAlchemy 2.x `text()` does NOT auto-escape — only `:name` placeholders are bound. `op.execute(text(...))` in migrations follows the same rule.

**How to apply:**
```python
# WRONG
db.execute(text(f"SELECT * FROM deals WHERE id = '{deal_id}'"))
# RIGHT
db.execute(text("SELECT * FROM deals WHERE id = :id"), {"id": deal_id})
# Identifier from request — whitelist
ALLOWED = {"created_at", "updated_at"}
col = sort_col if sort_col in ALLOWED else "created_at"
```

## 9. Pydantic boundary discipline

**Rule:**
- Write endpoints use a separate `…In` schema with `model_config = ConfigDict(extra="forbid")`.
- Response models use a separate `…Out` schema, not the ORM model directly.
- Never `**payload.model_dump()` into an ORM model — name the fields explicitly.
- `Field(max_length=…)` on every untrusted string (see rule #2).

**Why:** Pydantic v2's default `extra="ignore"` silently drops unknown fields — fine for inputs, but if a writer uses `**payload.model_dump()` and the ORM model has more fields (e.g., `creator_id`, `is_admin`), they'll pass through. Response models that reuse ORM types leak hashed passwords, MFA secrets, internal flags.

**How to apply:** every new endpoint gets a fresh `…In` / `…Out` pair. Persistence code names every field by hand.

## 10. Postgres tests are `pytest.mark.integration`

**Rule:** any test that uses a real Postgres session gets `pytestmark = pytest.mark.integration` at module level, runs only via `pytest -m integration` in a fresh process.

**Why:** a conftest `db` fixture that strips `Base.metadata.schema` for SQLite compatibility pollutes SQLAlchemy's per-mapper compiled-SQL cache; restoring `schema='app'` doesn't invalidate it. Postgres queries from a later test in the same process generate schema-less SQL and fail with `UndefinedTable`. See [[feedback_sqlalchemy_schema_strip_isolation]] — saved as its own memory.

## Cross-cutting

- **Local checks:** `bandit -r app`, `semgrep --config p/python --config p/owasp-top-ten --config p/sqlalchemy`, `ruff` with `S` (bandit) rules. Keep a project-local semgrep ruleset and extend it as new patterns are caught.
- **PR description hygiene:** when shipping code that extends a known-gappy area (RBAC commented out, no client timeouts, etc.), name the deferred items explicitly. A "demo with prod risk" posture is fine as long as the gaps are documented; silent perpetuation is not.

## Cross-references

- [[feedback_sqlalchemy_schema_strip_isolation]] — rule #10's full story.
- [[feedback_demo_with_prod_risk]] — why some of these get deferred rather than fixed immediately.
- [[feedback_claims_need_tests]] — sister rule: prose claims about idempotency / sanitization without a test are aspirational.
- [[reference_python_pr_gotchas]] — small idiom errors checklist; this memory is the larger systematic-discipline complement.

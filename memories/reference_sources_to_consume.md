---
name: reference-sources-to-consume
description: External reading list that would have caught most of the missed PR-review findings
metadata: 
  node_type: memory
  type: reference
  volatility: durable
---

PR review history has surfaced many valid technical findings missed on first pass. Most fall into eight defensive patterns (see [[feedback-pr-review-patterns]]). The sources below are what would have given the checklists to catch them proactively.

## Priority sources

All six core recommendations have been acquired and processed into memory entries:

- **Patrick Viafore, *Robust Python*** (full release) — defensive coding habits, type contracts, boundary validation, error-handling discipline. Processed into [[reference-type-system-for-invariants]], [[feedback-typechecker-adoption]], and [[feedback-user-defined-types-and-property-tests]].
- **Martin Kleppmann, *Designing Data-Intensive Applications*** — Chs 7-9 (transactions/concurrency) processed into [[feedback-concurrency-invariant-design]]; Chs 1-6 (the data-system half — storage/columnar, encoding/schema-evolution, partitioning) processed into [[reference_data_system_design]] for any columnar/Arrow/vector-store surface.
- **Luciano Ramalho, *Fluent Python* (2e)** — Part V (Chs 19-21, async + cancellation). Processed into [[feedback-async-cancellation-model]].
- **John Ousterhout, *A Philosophy of Software Design* (2e)** — measurable complexity, deep modules, design diagnostics. Processed into [[feedback-aposd-module-design]].
- **Chip Huyen, *AI Engineering*** — production LLM patterns, RAG, evaluation discipline, prompt-attack defenses. Processed into [[feedback-llm-prompt-defenses-and-evaluation]].
- **Harry Percival & Bob Gregory, *Architecture Patterns with Python*** — aggregates, optimistic concurrency, command/event split. Processed into [[feedback-aggregates-and-optimistic-concurrency]]; the architectural ceremony (Repository, UoW, MessageBus) explicitly deferred.
- **Dimitri Fontaine, *The Art of PostgreSQL*** — Postgres-specific operational patterns. Processed into [[feedback-postgres-concurrency-operational]].

## Reference docs (grep when the relevant surface appears)

- **[OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)** — LLM01 Prompt Injection, LLM02 Insecure Output Handling, LLM04 Model DoS, LLM06 Sensitive Information Disclosure, LLM08 Excessive Agency. Read once front-to-back, then reach for it any time the code touches LLM I/O.
- **Python docs on asyncio** — the Task/CancelledError sections are the critical parts. [Task.cancel](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel), [CancelledError](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError), [PEP 654 ExceptionGroups](https://peps.python.org/pep-0654/), [PEP 678 add_note](https://peps.python.org/pep-0678/), [TaskGroup since 3.11](https://docs.python.org/3/library/asyncio-task.html#task-groups).
- **[Alembic cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html)** — operational recipes (data-preservation guards, multi-pod migrations, conditional upgrades). The "Don't emit ... when not needed" patterns matter for downgrade symmetry (Pattern 4).
- **[Anthropic prompt engineering guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)** — esp. the sections on handling untrusted user content and the XML-tagging conventions for evidence vs instructions.
- **[Pydantic v2 docs](https://docs.pydantic.dev/latest/)** — boundary validation (`strict_mode`, `extra='forbid'`, `Field(max_length=...)` for any string fed by LLM or document content). Most of [[reference-python-pr-gotchas]] are Pydantic v2 idiom errors caught after the fact.
- **[FastAPI security docs](https://fastapi.tiangolo.com/tutorial/security/)** — the OAuth2 + scopes section frames Pattern 5 (auth placeholders) in the framework's own vocabulary.

## When to consume what

- New external dependency (a new SDK, a new HTTP client) → re-read OWASP LLM Top 10 (if LLM-shaped) or the equivalent OWASP API/Web Top 10. Always set timeouts.
- New asyncio code that touches lifespan / task / cancellation → re-read the asyncio Task section + Ramalho Ch 21.
- New migration → cross-check against alembic cookbook for data-preservation patterns + the [[feedback-local-migration-testing]] discipline.
- New LLM prompt or chunk-handling code → re-read OWASP LLM01 (Prompt Injection) and the Anthropic untrusted-input guidance.
- Reviewing my own diff before push → run the eight patterns from [[feedback-pr-review-patterns]] as a checklist.

## Related memory

- [[feedback-pr-review-patterns]] — the eight patterns these sources support
- [[reference-coding-methodology]] — the broader methodology synthesis already in the memory base
- [[reference-python-pr-gotchas]] — small-idiom checklist that overlaps with Pydantic / SQLAlchemy 2.0 docs above
- [[feedback-security-when-writing-code]] — the 10 security rules from a security audit, which OWASP LLM Top 10 broadens

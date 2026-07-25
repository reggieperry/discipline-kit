---
name: feedback-aggregates-and-optimistic-concurrency
description: "Five rules from Percival & Gregory's *Architecture Patterns with Python* — name the aggregate (consistency boundary) before sizing the transaction, prefer optimistic concurrency via `version_number` for low-contention writes, split commands (fail-fast) from events (isolated), keep payloads as plain frozen dataclasses with no behavior, do not introduce Repository/UoW/CQRS layers until tests or transaction sprawl warrant it. The \"when not to abstract\" half is as important as the \"what to name\" half."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

Percival & Gregory's *Architecture Patterns with Python* gives Python-specific vocabulary for the consistency-boundary discipline in [[feedback-concurrency-invariant-design]]. The rules below are what survives a HARSH filter — keep the operational discipline (aggregates, version numbers, command/event split), drop the architectural ceremony (Repository, UoW, MessageBus, full hexagonal) until tests or transaction sprawl actually demand it.

**Why:** the book proposes many abstraction layers. Most are *wrong* for a small or early-stage system per [[feedback-simplicity-principle]] and [[feedback-demo-with-prod-risk]]. The rules below are the essential ideas; the dropped rules at the bottom are the ceremony.

**How to apply:** at design time for new persistence functions or stage handlers, name the aggregate and pick optimistic vs pessimistic concurrency. At review time, push back on Repository / MessageBus / CQRS proposals unless the proposer can name a concrete pain point the current shape causes.

---

## 1. Split *commands* from *events* in the orchestration spine, even without a message bus

**Rule.** Tag each step in a stage handler as `COMMAND | EVENT`. Commands run the user-visible work and may raise; events do bookkeeping/notification and must not abort the surrounding command on failure.

**Why.** Ch 10 "Discussion: Events, Commands, and Error Handling." *"The only part of this code that has to complete is the command handler that creates an order."* Events are allowed to fail in isolation; commands fail fast and bubble.

**Trigger.** Stage handlers that mix both shapes. A handler that performs the core work (must succeed or the result is incomplete) is a command; an audit-log write or a downstream record refresh is an event. When they share one exception path, a logging-table outage can mask a real work failure or vice-versa. Pairs with [[feedback-pr-review-patterns]] Pattern 2 (cancellation vs exception) — the same except-clause discipline.

**How to apply.** No new bus needed. Tag each step explicitly and route exception handling: commands re-raise into the runner's failure path (with the existing claim-token / status discipline); events log-and-continue with `logger.exception` and never abort the surrounding command. Tests must drive each event-handler failure and assert the command still succeeds — backs [[feedback-claims-need-tests]] for the new "event-isolated" claim.

---

## 2. Pick the consistency boundary by naming the multi-row invariant — then size the transaction to exactly that boundary

**Rule.** For each persistence function, write one docstring line: *"Aggregate: <name>. Invariant: <plain English>. Boundary: <FOR UPDATE on parent | partial unique index | EXCLUDE constraint>."* If three persistence functions share an aggregate, lock the parent once at the runner and pass the locked context down — not lock per call.

**Why.** Ch 7 "Invariants, Constraints, and Consistency" + "Choosing an Aggregate." *"Each basket is a single consistency boundary responsible for maintaining its own invariants."* The aggregate is the unit you load and write atomically; wrong size shows up as deadlocks (too big) or write skew (too small).

**Trigger.** Persistence functions that DELETE-then-INSERT under an implicit single-writer assumption. Once a second writer source lands, the parent-scoped record set is the real aggregate (write-skew risk per [[feedback-concurrency-invariant-design]] rule 1).

**How to apply.** Extends [[feedback-concurrency-invariant-design]] rule 1 by naming the *chooser*, not just the defense. The docstring entry is the deliverable. Example: *"Aggregate: Parent. Invariant: at most one source-A row per (parent, field, candidate_index). Boundary: SELECT FOR UPDATE on `parents` for the runner's claim duration."*

---

## 3. Add `version_number` to aggregate roots and assert the row count on update — optimistic concurrency for low-contention writes

**Rule.** Add `version_number INT NOT NULL DEFAULT 0` to any aggregate root where two concurrent writers can otherwise succeed against a stale snapshot. The service-layer commit pattern: `UPDATE … SET v = v + 1, … WHERE id = :id AND v = :seen_v RETURNING *`. `rowcount == 0` → raise `StaleAggregate`, caller retries from a fresh read.

**Why.** Ch 7 "Optimistic Concurrency with Version Numbers." *"Version numbers are just one way to implement optimistic locking. You could achieve the same thing by setting the Postgres transaction isolation level to SERIALIZABLE, but that often comes at a severe performance cost."* The version number makes the implicit "I read this at v=3" check explicit and gives the writer a programmatic stale-write signal.

**Trigger.** Same surface as the fencing token in [[feedback-concurrency-invariant-design]] rule 6 — but cheaper. A run's `claim_token` is the right move for the pause-and-resume case (protects the *lease*). A `parents.version_number` is the right move for arbitrating between two writer sources and for re-processing collisions (protects the *data*). The two are not redundant.

**How to apply.** Migration adds `version_number` to the aggregate root and any aggregate with multi-writer risk. Service-layer pattern:
```python
result = session.execute(
    update(Parent)
    .where(Parent.id == parent_id)
    .where(Parent.version_number == seen_version)
    .values(version_number=Parent.version_number + 1, **fields)
    .returning(Parent.id, Parent.version_number)
)
row = result.first()
if row is None:
    raise StaleAggregateError(parent_id, seen_version)
```
Integration test pattern is [[feedback-sqlalchemy-schema-strip-isolation]]-compliant: `pytest.mark.integration`, real Postgres, two threads, assert one wins and version == seen + 1.

---

## 4. Prefer optimistic (version_number) over pessimistic (`FOR UPDATE` + `REPEATABLE READ`) for multi-statement reads, given low contention

**Rule.** Each persistence function picks one defense and names it. The default for a low-contention system is optimistic. Reach for `FOR UPDATE` only on the runner's claim, where waiting is correct and contention is real.

**Why.** Ch 7 "Optimistic Concurrency Control and Retries." *"Optimistic locking … we let them go ahead and just make sure we have a way to notice if there is a problem."* Pessimistic locks broadly and risks deadlock. When write contention is low, optimistic + retry wins.

**Trigger.** Sharpens [[feedback-concurrency-invariant-design]] rule 2 (`REPEATABLE READ` for multi-statement reads) by saying: don't escalate to `REPEATABLE READ` as a default — reach for version numbers first. At low scale, optimistic + retry is simpler to reason about than session-isolation gymnastics.

**How to apply.** The [[feedback-pr-review-patterns]] Pattern 6 docstring entry now reads `Concurrency: optimistic via parents.version_number` for most aggregates. The serialization-retry decorator in [[feedback-postgres-concurrency-operational]] rule 1 covers the few cases that genuinely need `REPEATABLE READ`.

---

## 5. Payloads are plain frozen dataclasses — no methods on event/command/value objects

**Rule.** Every event/command/payload in the spine is a `@dataclass(frozen=True)` (or Pydantic for I/O boundaries). Transformations belong in handlers or separate normalizer functions, not as methods on the value.

**Why.** Ch 8 "Events Are Simple Dataclasses." *"Events don't have any behavior, because they're pure data structures."* Keeping them dumb means they can be logged-and-replayed (Ch 10 "Recovering from Errors Synchronously"), serialized for cross-process work without ceremony, and used as test fixtures with minimal setup. Pairs with [[feedback-mock-discipline]] ("don't mock values, construct them") and [[feedback-oo-style]] ("values not objects").

**Trigger.** Orchestration stage payloads that have started to grow helper methods (`payload.normalize()`, `payload.with_attempt(n)`).

**How to apply.** Audit the orchestration layer for any payload with a method; extract to a module-level function. Add a one-line invariant comment: *"Value object; do not add behavior."* Builders for tests (per [[feedback-test-discipline]]) go in `tests/builders/` and return fully-valid payload values.

---

## What's not in scope (the architectural ceremony)

The book proposes many layers; a small or early-stage system does not need most of them yet. The deciding question is always **does this layer solve a concrete pain point our current shape causes?** If no, don't add it.

- **Repository pattern as a default abstraction.** SQLAlchemy `Session` is already an adapter; further wrapping is ceremony. Adopt only if test friction or transaction sprawl warrants ([[feedback-mock-discipline]] covers the test-double need).
- **Full Unit of Work context manager.** Adopt only where a use case genuinely spans multiple aggregates that must commit atomically.
- **In-process Message Bus.** The *command-vs-event error semantics* (rule 1) is the core idea; we can adopt that without the bus.
- **Hexagonal / ports-and-adapters as top-level project shape.** Covered by [[reference-coding-methodology]] Pillar 1.
- **Read-model views via raw SQL in a `views/` layer.** Worth adopting *if* the read-side queries grow clunky. Don't pre-build. (Architecture Patterns Ch 12.)
- **External Redis/RabbitMQ message bus.** Explicitly deferred per [[feedback-demo-with-prod-risk]].

## Related memory

- [[feedback-concurrency-invariant-design]] — DDIA theory; rules 2-4 here extend rules 1-3 there
- [[feedback-postgres-concurrency-operational]] — Postgres operational layer; rule 1 there (serialization retry) is the fallback when optimistic doesn't fit
- [[feedback-pr-review-patterns]] — Pattern 2 (cancellation) interacts with rule 1 here (command vs event)
- [[feedback-simplicity-principle]] / [[feedback-demo-with-prod-risk]] — the posture that lets us skip the architectural ceremony
- [[feedback-mock-discipline]] / [[feedback-oo-style]] — the test-double and values-not-objects discipline rule 5 enforces
- [[reference-sources-to-consume]] — Architecture Patterns with Python is the service-layer reference

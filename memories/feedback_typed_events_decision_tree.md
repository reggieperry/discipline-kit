---
name: typed-events-decision-tree
description: "When typed events are the right architectural pattern vs alternatives (method call, frozen dataclass, polymorphic dispatch, record-and-query Protocol). Five-question decision tree."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

Typed events are right when an **asynchronous handoff** happens between stages that must be independently restartable, auditable, and substitutable behind a uniform dispatch surface — pipeline boundaries where producer and consumer share no lifetime, no scope, and no caller context. They are wrong when the work is a synchronous computation against an aggregate's own invariants, when the output value itself carries the invariant (the type system enforces what events can only observe), or when one entity drives a polymorphic command against an external resource. A system can have both patterns deliberately; the principle below is the load-bearing distinction.

**Why:** typed events look elegant and have a clear discipline; it's tempting to extend the pattern everywhere a pipeline first establishes it. Selective adoption isn't accidental — each alternative pattern preserves something specific that typed events would cost. Naming the principle prevents future "let's make this an event too" drift.

**How to apply:** when deciding between typed events and alternatives, walk these five questions in order:

1. **Do producer and consumer share a lifetime?** If yes (one method's call frame includes the consumer), use a method call. The event substrate adds dispatch overhead, hides the call graph, and asserts a separation the runtime doesn't have. If no (a checkpoint, an interrupt, a process boundary, an overnight wait sits between them), continue.

2. **Is the boundary the unit of substrate-level concerns (checkpoint, budget, telemetry, audit, permission scoping)?** If yes, typed events let one substrate satisfy all those concerns at every boundary. If no — the work is one synchronous computation against one snapshot — direct composition is right.

3. **Does the output value itself carry an invariant the type system can express?** If yes, push the invariant into construction (`__post_init__` + token-of-construction). An event substrate cannot enforce structural invariants on what it carries; it can only observe.

4. **Does the output need to be queried from multiple angles over time by readers the producer doesn't know?** If yes, use a record-and-query Protocol (ledger, audit log). Pub-sub delivers each event once; durable records support re-query by many keys across many windows.

5. **Is the substitution surface inside one process across one external resource?** If yes, polymorphic dispatch (discriminated union of dataclasses with methods) is the right substitution surface. Method call is the work; the union is the substitution.

If a context fails (1) and passes (2), typed events are right. Apply them at exactly those contexts.

## Where each pattern fits

| Context | Pattern | Why |
| --- | --- | --- |
| Pipeline stages handing off in sequence | **Typed events** (frozen domain events) | Independent lifetimes (checkpoint resume), uniform substrate concerns, unknown future consumers, audit-unit boundary |
| Cross-process handoff | **Typed events** over a pub/sub substrate | Same four properties even more sharply across a process boundary |
| A sequence of validation gates collapsing to a discriminated union | **Pure functions composed in one method** | Single atomic decision against one frozen snapshot; no boundary inside |
| Safety-critical approval construction | **Frozen dataclass + token-of-construction** | The invariant belongs in the type's existence, not in an event consumer's responsibility |
| Command execution against one external resource | **Polymorphic method dispatch** | One connection, no second consumer, substitution via discriminated union |
| Cost/usage ledger | **Record-and-query Protocol** | Append-once-query-many-ways; pub-sub delivers each event once |
| Lifecycle accumulators | **Frozen + builder** | Producer/consumer share a lifetime; handoff at completion via an already-frozen value |
| Decision audit log | **Record** that borrows event vocabulary | Append-only audit; no subscriber dispatch |

## Things that LOOK like events but aren't

Append-once-queried-many-ways records (cost records, decision-audit records) are **records, not events** in the pipeline-substrate sense. No event-bus subscriber registers on them; both are queried, not dispatched. The "Event" word means "one thing that happened, sealed against later mutation" — same shape as pipeline events but a different role. Pipeline substrate events are consumed by exactly one next stage; ledger records are queried by many readers across many windows. Both want immutability; only the first wants pub-sub dispatch. The naming overlap is harmless but worth watching — it keeps the substrate from accreting work that belongs in storage, and keeps the audit log from accreting subscribers that should be queries.

## Common drift to flag in PR review

- "Let's emit a `GatePassed` event between validation gates" → no. Gates are pure functions over one snapshot; events would dilute the per-snapshot atomicity.
- "Let's make `ApprovedResult` a `ResultApproved` event the executor subscribes to" → no. The invariant belongs in the type's `__post_init__`, not in a consumer's responsibility.
- "Let's emit a `CommandRequested` event from the executor" → no. One external connection, no second consumer; polymorphic dispatch is the substitution surface.
- "Let's pub-sub on cost records so dashboards subscribe" → no. Dashboards query the ledger by period; record-and-query is the right pattern for write-once-read-many.

## Cross-references

- [[oo_style]] — Tell-Don't-Ask, peer stereotypes; method-call pattern's underpinning
- [[ddd_aggregates_and_optimistic_concurrency]] — aggregate-sizing; informs when a boundary earns event treatment
- [[aposd_module_design]] — module depth; events add interface surface, prefer deep modules
- [[postgres_concurrency_operational]] — LISTEN/NOTIFY is not a queue (constraint on cross-process events)

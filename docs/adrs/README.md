# Architecture Decision Records

This directory holds the Architecture Decision Records (ADRs) for the repository — the durable
log of the decisions that shape its architecture, why they were made, and the condition under
which each would be shown wrong. Each ADR is one file; the template is
`harness/templates/ADR-template.md`.

An ADR is not a design doc. A design doc explores; an ADR *decides*, and records the decision so
a future maintainer inherits the reasoning, not just the result. Reach for one at a
verdict-shaped, hard-to-reverse fork — a schema, an orchestration model, a protocol, a
fail-posture — the same forks that warrant a deep-reason or committee pass.

## Naming and ids

ADR files are named `ADR-NNNN-<slug>.md`, where `NNNN` is a four-digit zero-padded integer and
`<slug>` is a few kebab-case words naming the subject — for example
`ADR-0007-billing-idempotency.md`.

**Ids are stable and never renumbered.** Once an id is issued it belongs to that ADR
permanently, even after the ADR is superseded or deprecated. Allocate the next free integer;
never reuse a retired one, and never renumber to close a gap. A stable id is what lets every
cross-reference and commit message point at a decision that will still be there.
The next id is one past the highest in the registry table below.

## The fixed section order

Every ADR carries the same sections in the same order: **Context**, numbered **Decisions**,
**Consequences**, **Alternatives**, **Falsification condition**, and **Cross-references**. The
order is fixed so any ADR is scannable at a glance, and an empty section reads "None." rather
than being dropped. The template is authoritative on the shape.

## The Status line

A Status line near the top records the ADR's state — Proposed, Accepted, Superseded-in-part,
Superseded, or Deprecated — and cites the verdict that admitted it. An acceptance-gate pass, a
deep-reason adversary or a committee review, is *testimony*; testimony
attests but never signs, so the Status line links the recorded review (under `reviews/`) rather
than reporting the pass in prose. A verdict linked to its record is followable and checkable; a
verdict asserted in prose is neither.

## Per-Decision supersession

Decisions are numbered within the ADR (D1, D2, …) and each can be superseded on its own. When a
later ADR overturns part of an earlier one, the earlier Decision is **never deleted**: it keeps
its text and gains a "superseded-in-part" banner naming the successor and, explicitly, what it
**retains** — the parts that still govern. The ADR's Status line moves to Superseded-in-part;
its sibling Decisions are untouched and keep their numbers.

Supersede, never edit: a changed decision is a new record
that names the old one, not an edit that erases the fact that the decision changed. The audit
value is in the diff — a maintainer must be able to see what was decided, what replaced it, and
what survived.

## The falsifier names its court

The **Falsification condition** is non-negotiable: every ADR states the condition under which
its decision would be shown wrong. That condition is not allowed to live only in the ADR's
prose. Wherever it is mechanically checkable, it is wired as a named check on the commit path
(`scripts/check.sh`) and the ADR cites the check by name. As the design maxim holds, *a
falsifier living only in prose is a court nobody convenes*: a condition with no check is a
sentence nobody can act on, while a condition wired as a check has a court and a date it could
lose in. Where no mechanical check is possible the ADR says so plainly and names the standing
human observation that stands in — but a check is preferred, and an unwatched condition must
read as unwatched.

## The registry

Every ADR is registered here in the same commit that adds it. The next free id is one past the
highest `ADR-NNNN` in the table.

| ADR | Title | Status | Falsifier (court) | Supersession | Date |
|-----|-------|--------|-----------------|--------------|------|
| [ADR-0001](ADR-0001-advancement-re-derived.md) | Advancement is re-derived, never reported | Accepted | `chain-refspec-check.sh` (D1 edge, live); remaining courts future, named per decision | None | 2026-08-07 |
| [ADR-0002](ADR-0002-merge-posture.md) | The chain merges locally; publication is the operator's act | Proposed | `revert-sufficiency-check.sh`, `merge-posture-check.sh` (live); remaining courts future, named per decision | None | 2026-08-07 |

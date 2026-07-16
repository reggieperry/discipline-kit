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
cross-reference, ledger claim, and commit message point at a decision that will still be there.
The next id is one past the highest in the registry table below.

## The fixed section order

Every ADR carries the same sections in the same order: **Context**, numbered **Decisions**,
**Consequences**, **Alternatives**, **Falsification condition**, and **Cross-references**. The
order is fixed so any ADR is scannable at a glance, and an empty section reads "None." rather
than being dropped. The template is authoritative on the shape.

## The Status line

A Status line near the top records the ADR's state — Proposed, Accepted, Superseded-in-part,
Superseded, or Deprecated — and cites the verdict that admitted it. An acceptance-gate pass, a
deep-reason adversary or a committee review, lands in the ledger as *testimony*; testimony
attests but never signs, so the Status line cites the testimony's `clm-NNNN` rather than
reporting the pass in prose. A verdict cited by id is receipted and checkable; a verdict
asserted in prose is neither.

## Per-Decision supersession

Decisions are numbered within the ADR (D1, D2, …) and each can be superseded on its own. When a
later ADR overturns part of an earlier one, the earlier Decision is **never deleted**: it keeps
its text and gains a "superseded-in-part" banner naming the successor and, explicitly, what it
**retains** — the parts that still govern. The ADR's Status line moves to Superseded-in-part;
its sibling Decisions are untouched and keep their numbers.

This mirrors the ledger's supersede-never-edit discipline: a changed decision is a new record
that names the old one, not an edit that erases the fact that the decision changed. The audit
value is in the diff — a maintainer must be able to see what was decided, what replaced it, and
what survived.

## The falsifier registers as a claim

The **Falsification condition** is non-negotiable: every ADR states the condition under which
its decision would be shown wrong. That condition is not allowed to live only in the ADR's
prose. Wherever it is mechanically checkable, it registers in the ledger as a claim — an
`unverified` assertion parked under the check that would fire it — and the ADR cites the
`clm-NNNN`. As the design maxim holds, *a falsifier living only in prose is a court nobody
convenes*: a condition with no court is a sentence nobody can act on, while a condition
registered as a claim has a docket, a check, and a date it could lose in. Where no mechanical
check is possible the ADR says so plainly and names the standing human observation that stands
in — but a check is preferred.

## The registry

Every ADR is registered here in the same commit that adds it. The next free id is one past the
highest `ADR-NNNN` in the table.

| ADR | Title | Status | Falsifier (clm) | Supersession | Date |
|-----|-------|--------|-----------------|--------------|------|

_No ADRs registered yet._

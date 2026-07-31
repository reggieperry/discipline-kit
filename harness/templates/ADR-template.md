# ADR-NNNN: <short imperative title>

<!--
  Copy this file to docs/adrs/ADR-NNNN-<slug>.md and fill it in.
  - NNNN is the next free integer, zero-padded to four digits. Ids are stable and
    never renumbered — once ADR-0007 exists it is ADR-0007 forever, even after it is
    superseded. Gaps are fine; reuse is not. The next id is one past the highest in
    docs/adrs/README.md's registry table.
  - <slug> is a few kebab-case words naming the subject, e.g. billing-idempotency.
  - Register the new ADR in docs/adrs/README.md's table in the same commit.
  - The sections below appear in a fixed order. Do not reorder or drop them; an empty
    section reads "None." rather than being deleted.
-->

**Status:** Proposed | Accepted | Superseded-in-part | Superseded | Deprecated — <date>.
Acceptance gate: <deep-reason | committee> pass — <link to the review>.

<!--
  The Status line records the ADR's state and cites the verdict that admitted it. An
  acceptance-gate pass — a deep-reason adversary or a committee review — is *testimony*:
  a reader looked and found nothing, which is not the same as a check having run. Link
  the review so the claim is followable; a verdict asserted in prose is not.

  On a per-Decision supersession, set the state to "Superseded-in-part" and keep the
  citation to this ADR's original acceptance verdict; the superseding ADR carries its own.
-->

## Context

<!--
  The forces in play: the problem being decided, the constraints that bound it, and
  what was true when the decision was made. State the situation, not the answer — a
  reader who disagrees with the Decisions should still accept the Context. Keep it to
  what a future maintainer needs to reconstruct why this was a live question.
-->

_<Describe the problem, the constraints, and the state of the world that forces a decision.>_

## Decisions

<!--
  Each Decision is numbered and stands on its own — D1, D2, D3, … within this ADR. A
  Decision can be superseded individually, in whole or in part, by a later ADR; you
  never delete a Decision or renumber its siblings. A superseded Decision keeps its
  text and gains a "superseded-in-part" banner (see the example below) naming the
  successor and, explicitly, what it *retains* — the parts that still govern.

  Write each Decision as a claim in the present tense: "The service does X," not "We
  should consider X."
-->

### D1 — <the decision, stated as a claim>

_<One or two sentences stating exactly what is decided — precise enough that a reviewer
can tell whether an implementation conforms.>_

<!-- Repeat as D2, D3, … Record only the Decisions this ADR actually makes. -->

---

<!-- ILLUSTRATIVE EXAMPLE — delete this block in a real ADR. -->

### D-example — Idempotency keys are client-supplied UUIDs

The billing service requires every write request to carry a client-supplied `Idempotency-Key`
header holding a version-4 UUID; the service stores the key with its result and replays the
stored result on any retry inside the 24-hour retention window.

> **Superseded-in-part by ADR-0042 (2026-03-02).** ADR-0042 moves key *generation* to the
> gateway, so clients no longer mint the UUIDs. **Retains:** the 24-hour retention window and
> the store-and-replay semantics are unchanged and still govern; only the origin of the key moved.

<!-- END EXAMPLE -->

## Consequences

<!--
  What follows from the Decisions — the costs accepted, the constraints imposed, the
  follow-on work created, and the second-order effects. Include the ones that hurt; a
  Consequences section with no downside is not finished. Separate "what is now true"
  from "what we must still do."
-->

_<List the results, both the benefits banked and the costs and obligations accepted.>_

## Alternatives

<!--
  The options considered and not taken, one short paragraph each, with why each lost. A
  rejected alternative with no stated reason is not a real alternative. Design-twice
  discipline: the contrast is what shows the chosen path was not obvious by accident.
-->

_<For each option not taken: what it was, and the specific reason it lost.>_

## Falsification condition

<!--
  NON-NEGOTIABLE. State the condition under which this decision would be shown wrong —
  the observation, measurement, or event that would defeat it. A decision you cannot
  imagine being wrong is a preference, not a decision.

  Wherever the condition is mechanically checkable, name the check that would fire it —
  so the falsifier has something that can actually convene, rather than resting on
  someone remembering to look. Where no mechanical check is possible, say so plainly and
  name the standing human observation that stands in; a check is preferred, and an
  unwatched falsification condition should read as unwatched.
-->

_<The condition that would defeat this ADR.>_ Watched by `<check-name>`; <or: not
mechanically checkable — the standing observation is …>.

## Cross-references

<!--
  Pointers out: superseding and superseded ADRs, related ADRs, and the design docs or
  guides this builds on. Use ids and relative paths only.
-->

- Supersedes: _<ADR-NNNN, or None>_
- Superseded by: _<ADR-NNNN, or None>_
- Related: _<ADR-NNNN, docs/…, or None>_

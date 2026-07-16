---
name: adr-write
description: >-
  Record an architecture decision so it can be attacked, superseded, and audited. Load when writing or revising an architecture decision record: "write an ADR", "record this decision", "let's decide X architecturally", "should we do X or Y (architecturally)", "supersede that decision", or before drafting or redrafting any ADR. Covers the template structure and stable ids, the pre-draft deep-reason gate whose verdict lands on the Status line, gating status flips on named artifacts, registering the falsifier as a ledger claim, and superseding a single Decision without deleting it.
---

# adr-write: record a decision so it can lose

An ADR that only records what was chosen is a press release. An ADR that names the condition under which the choice was wrong, and points at the court that would convene, is a decision you can be held to. Write the second kind.

## When an ADR is the right instrument

Write one for a decision that is costly to reverse and that later work will cite: a structural boundary, a technology commitment, a wire or protocol shape, a build-vs-buy call. A reversible or local choice is a code comment or a note on the story, not an ADR — a record with no downstream citations is overhead. Keep one ADR to one decision area. Several related Decisions in a single record are fine and expected; a record that straddles two unrelated areas cannot be superseded cleanly, because overturning one area drags the citations of the other.

## Structure

Produce the record against `harness/templates/ADR-template.md`. Six parts, in order:

- **Context** — the forces in play and the constraint that makes a decision necessary. State what is true before the choice, not the choice itself.
- **Decisions** — the calls, each a numbered item (`D1`, `D2`, …) with a **stable id that is never renumbered**. Ids are addresses: a later ADR, a story, or a claim cites `ADR-0007/D2`, and renumbering breaks every citation silently. Insert a new Decision at the next free number; never reflow the existing ones.
- **Consequences** — what each Decision commits the system to, costs included. A consequence you would not accept is a Decision you have not actually made.
- **Alternatives** — the options rejected and *why*, one line each. The rejected branch is the part a future reader needs most, because they are standing at the same fork wondering why not.
- **Falsification condition** — non-negotiable, at least one per consequential Decision: the observable that would show this call was wrong. See "Register the falsifier as a claim" below; this is the section that turns an opinion into a bet.
- **Cross-references** — the ADRs this one supersedes or depends on, the stories that implement it, and the `clm-` ids that discharge its falsifiers.

## The shape of one Decision

A single Decision, carried through the six-part frame — the id fixed, the alternative named, the falsifier a claim rather than a sentence:

```
D2. Route inter-service claims through the typed schema, not free prose.
    Consequence: every producer emits the schema; a prose-only producer is
      rejected at the boundary, at the cost of a heavier producer contract.
    Alternative rejected: disciplined prose — cheaper to adopt, but nothing
      at the boundary can mechanically reject a malformed claim.
    Falsification: if the typed boundary shows no lower malformed-claim rate
      than the prose baseline over one release, this Decision bought nothing.
      Registered clm-0231 (schema-vs-prose reject-rate check).
```

`clm-0231` sits on the board, not in the prose. The day its check reads no improvement, the Decision is answerable — and a superseding Decision cites the same id so the successor inherits the standard it must beat.

## The pre-draft deep-reason gate

Before an ADR is drafted — and again before its second draft — a fresh-context `deep-reason` attack pressure-tests the decision. This is the standing trigger, not an optional courtesy: a verdict-shaped, hard-to-reverse call earns an adversary that did not help you reach it and does not share your session's blind spots. The attack hunts the case where the chosen Decision fails and a rejected Alternative would have held.

Its verdict is **receipted testimony recorded on the ADR's Status line**, never a self-reported "reviewed." The `deep-reason` pass lands as a `testimony` or `refutation` entry on the ledger (`ledger-write`), and the Status line cites that entry in the template's two-line form — the state on the first line, the gate citation on the second:

```
**Status:** Accepted — <date>.
Acceptance gate: deep-reason pass, testimony clm-0212 (no reachable refutation).
```

A pass that finds a defect appends a `refutation`; a clean pass appends `testimony` and signs nothing. A deep-reason verdict is not a signature — it is an adversary's absence report, bounded as such, and the ADR says so rather than dressing it as approval.

The testimony entry needs an `about` target, and there is no `clm-` id for the ADR itself, so point it at the **falsifier claim** the Falsification section registers — which means **append the falsifier claim first**, then the acceptance testimony `about` it. The one ledger id the ADR already owns is its falsifier; the acceptance verdict attaches to the same court the decision will be judged in.

## Status flips are gated on named artifacts

An ADR advances status only when a named artifact justifies the move — never on assertion alone. `Proposed → Accepted` needs the deep-reason verdict cited on the Status line. `Accepted → Implemented` needs the implementing story or the signed `clm-` id. `Accepted → Superseded` needs the successor ADR or Decision that replaces it. If the artifact does not exist yet, the status does not move yet; "we decided this" is a sentence, not an artifact.

## Register the falsifier as a claim

A falsifier that lives only in ADR prose is a court nobody convenes: nothing runs it, nothing watches it, and the day it fires there is no bell. Wherever the falsification condition is mechanically checkable, register it as a ledger claim and cite its `clm-` id in the ADR's Falsification section.

Use `ledger-preregister` to write the falsifier verbatim and park it under a check name the gate cannot yet run, so nothing auto-signs before the court is built; supersede it to the real check once that check exists. The ADR then cites the parked id, and the falsifier is a standing obligation on the board instead of a line in a document. Where a falsifier is genuinely not mechanical — a judgment call, an outcome that only time settles — say so in one line and name what would decide it; an honest unmechanizable falsifier beats a checkable one abandoned in prose.

The scar: an early ADR recorded its falsification condition as "revisit if throughput regresses" and cited no check. Throughput regressed and stayed regressed across two release cycles before anyone reread the record, because no court had been built to convene — the sentence sat inert while the system it condemned kept shipping. The one-line fix is a parked claim naming the regression check, cited by `clm-` id in the Falsification section, so the day the observable fires the board raises it.

## Supersede a Decision, never delete it

A Decision is superseded individually, not the whole ADR. When one call in a multi-Decision record is overturned, the ADR carries a **superseded-in-part banner** at the top naming what changed and, explicitly, what still holds — for example, `Superseded in part: D2 by ADR-0011/D1; D1, D3, and D4 stand.` The overturned Decision stays in place, its text intact, marked inline `[Superseded by ADR-0011/D1]`.

**Never delete a Decision.** The record of what changed is the point of the document. A reader who cannot see the abandoned call cannot tell a considered reversal from an oversight, and the next person to propose `D2` again has no graveyard to check. Deletion also strands every citation of `D2` that lives in stories, claims, and later ADRs. Supersession here is append-only for the same reason the ledger is (`ledger-retire`): the beaten call leaves the live decision by a pointer, not by an erasure.

## Cross-references

- `deep-reason` — the fresh-context adversary whose verdict gates `Proposed → Accepted`.
- `ledger-preregister` — parks the falsifier claim the Falsification section cites.
- `ledger-write` and `ledger-retire` — the entry discipline for the testimony line and the supersession pointer.
- `story-write` — the implementing story whose id gates `Accepted → Implemented`.

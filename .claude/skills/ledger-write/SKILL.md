---
name: ledger-write
description: >-
  The entry discipline for the dev-ledger. Load when about to append a claim, decision, finding, or operator authorization to ledger/claims.jsonl: "should this go in the ledger", "record that", "note the decision", "log the authorization", "append a claim", or any moment before running ledger/append. Covers the three-question test for what earns an entry, the claim-wording rules, which kind to use, and the append-only guardrails.
---

# ledger-write: the entry discipline

A ledger of everything is a diary; a ledger of the right things is an instrument. Write when the entry will do work later.

## The three-question test

Append only when at least two answers are yes.

1. Will anyone rely on this later? (a decision, a finding, a done-claim someone will build on)
2. Is there a mechanical discharge? (a check that could someday sign it, or an honest record of why it never can)
3. Would a dispute be expensive? (an authorization, a scope call, a contested result)

Two yeses: write it. Zero: leave it out, because the noise costs more than the record.

## How to write it

Compute the id, never guess it:

    ledger/board.sh next-id

Append through the one validating writer, and never edit the file by hand:

    echo '{"claim":"...","subject":"...","source":"claude-code","kind":"assertion","status":"unverified","check":"none"}' | ledger/append

`ledger/append` assigns the id and timestamp, fills the optional fields, and rejects a malformed or forged entry. Valid `source` values are `claude-code`, `subagent`, `human`, `hook`. The `kind` is `assertion`, `testimony`, or `refutation`. A fresh claim enters `unverified` with `check: "none"` unless a real check name applies.

## Claim wording

Write so a stranger could act on the line alone.

- Name the check: "discharged when `ledger/check.sh` recomputes clause (2) green", not "verified".
- Point at the artifact: the file, the receipt, the run, not "it works".
- State the boundary: what the claim does not cover, so the signature cannot be read wider than it earned.

## Registering a composed, existence, or interval claim

Three registration conventions, from the formal note (`docs/ledger-dynamics-note.html`, machine-checked 22/22 by `harness/algebra/validate_note.py`).

- **Name the connective.** A claim whose verdict composes over several courts states its composition rule by name — *truth-meet* (`∧ₜ`: every court must support; any opposite refutes; a width or ceiling exit blocks) or *truth-join* (`∨ₜ`: an existence claim). A composition clause that names neither is a defect in review. Template: `composition: truth-meet over {court-1, court-2}` or `composition: existence over habitats {h1, h2, h3}`.
- **Existence claims register their habitats and inherit the branch semantics (Theorem L6).** List every habitat the claim's text ranges over — typed events, prose annotations, dropped-wire corpora, whatever it reaches. *Confirm* only by a witness leaf that itself passes the gate, never by the composed `∨ₜ` root: Theorem L5's dual laundering signs a contested existence through a single unchecked habitat. *Refute* only when every registered habitat is checked and reads F; an unchecked habitat blocks refutation and never enables confirmation. The founding project's P4 existence-claim disposition is the worked example.
- **Interval claims use the sort's template.** A claim adjudicated by a confidence interval registers, at S0: the estimand, δ with its unit, the four exits verbatim (supported / opposite / practically-flat / indeterminate-by-width), the width guard, and the ceiling exit where a bounded instrument can compress range. This is Definition L9's exit function as a checklist; Lemma L10 guarantees the exits partition, so a registered interval claim can never land between verdicts.

## Which kind

- **assertion** is a claim about the work, and the default.
- **testimony** is review output (a `pr-review`, a `deep-reason`, a workflow verdict). It is `about` a claim and it never signs. Testimony is not a consolation prize: when a thing is not mechanically verified, an honest `unverified` assertion plus testimony that names its future court beats a fraudulent `signed`. The founding project's M3 press finding shipped exactly this way (clm-0122, an honest grade with its discharger named forward into the next cell).
- **refutation** is a defect found. It is `about` the claim it defeats, enters `unverified`, and blocks nothing by itself, which is precisely what a check should then confirm.

## Operator authorizations

Record an out-of-band authorization with principal, channel, and date: `"operator-authorized, direct, 2026-07-11"`. This is not ceremony. On the founding project a report once read the pronoun "you" as itself, built a violation narrative on the misread referent, and asserted it with forensic confidence in a document about attribution integrity. The one line that would have prevented it is this one, so a third reader can never again mistake who authorized what. The reader's side of that same scar is the `ledger-verify` skill.

## Guardrails

- Append-only. Never edit an existing line; a change is a new entry that supersedes the old one (`ledger-retire`). The audit holds every committed line byte-identical.
- A successor carries **both pointers**: `about` (the predecessor it concerns) and `supersedes` (the predecessor it replaces). A successor is at once a claim *about* its predecessor and its *replacement*, so both edges are explicit and tooling can walk either relation. The founding project discovered this shape under an append-rejection constraint — a testimony needs an `about` target — and it is the right one; adopt it as doctrine.
- Never hand-write `status: signed`. A signature comes only from a minting path — the commit-path gate, or the installer's `harness-verify` (self-recording as its own first customer) — never a hand-written line, and the pre-commit forgery guard blocks any signed line neither minted. Signing is the `ledger-discharge` skill.
- **The authorship note.** When a claim rests on a report or writeup, that document discloses the true authoring order in one sentence — what was written fresh, what was adapted from an existing template, what a prior session or another author produced — per the disclosure conventions (`harness/templates/report-conventions.md`). An outcome dressed as sole fresh work is a claim a future reader cannot weigh.

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

## Which kind

- **assertion** is a claim about the work, and the default.
- **testimony** is review output (a `pr-review`, a `deep-reason`, a workflow verdict). It is `about` a claim and it never signs. Testimony is not a consolation prize: when a thing is not mechanically verified, an honest `unverified` assertion plus testimony that names its future court beats a fraudulent `signed`. The founding project's M3 press finding shipped exactly this way (clm-0122, an honest grade with its discharger named forward into the next cell).
- **refutation** is a defect found. It is `about` the claim it defeats, enters `unverified`, and blocks nothing by itself, which is precisely what a check should then confirm.

## Operator authorizations

Record an out-of-band authorization with principal, channel, and date: `"operator-authorized, direct, 2026-07-11"`. This is not ceremony. On the founding project a report once read the pronoun "you" as itself, built a violation narrative on the misread referent, and asserted it with forensic confidence in a document about attribution integrity. The one line that would have prevented it is this one, so a third reader can never again mistake who authorized what. The reader's side of that same scar is the `ledger-verify` skill.

## Guardrails

- Append-only. Never edit an existing line; a change is a new entry that supersedes the old one (`ledger-retire`). The audit holds every committed line byte-identical.
- Never hand-write `status: signed`. Signatures come from the gate or they are forgeries, and the pre-commit forgery guard blocks any signed line it did not itself write. Signing is the `ledger-discharge` skill.

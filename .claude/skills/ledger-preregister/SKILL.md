---
name: ledger-preregister
description: >-
  Claim before building. Load when starting a milestone, cell, experiment, or any work whose "done" is contestable: "write the claim first", "pre-register this", "what would prove this", "draft the acceptance criteria", or drafting predictions before a run. Covers writing the claim verbatim up front, checking that every clause is dischargeable by a named check, and the park-under-a-non-runnable-check then supersede-at-landing pattern.
---

# ledger-preregister: claim before building

A "done" you write after the fact is a story. A claim you write before the run is a bet, and a bet you can lose is the only kind worth recording.

## Draft the claim before the work

Write the acceptance claim verbatim first: what will be true, and the exact check that will show it. Append it `unverified`.

## The claim is its own commit (the precedence timestamp)

The slice's acceptance claim lands as its **own ledger-only commit before any code commit** — a commit that touches `ledger/claims.jsonl` and nothing that builds the system. That commit is not ceremony: it is the precedence timestamp the `tdd-precedence` audit check reads, git's record that the claim preceded the code. Bundle the claim into the code commit and the timestamp is gone; the check warns, and rightly. Claim, commit, then build.

## Check every clause for dischargeability

For each clause, ask whether the named check can actually recompute it. A clause no check can discharge is a design error, and surfacing it now, before the work, is the point of writing the claim early.

The scar: on the founding project a validation claim was parked under `check=verify-d0` (clm-0128). The gate's runnable set is exactly `{repo-check, scala-check, scala-suite, typecheck}`, and `verify-d0` is not in it, so the gate would never queue that check. The undischargeable name was caught only because the claim existed to be attacked. Written after the run, that gap would have shipped as a signature meaning nothing.

## Park, then supersede

One pattern, two jobs.

1. **Park** the pre-registered claim under a check name the gate cannot run (any name outside the runnable set, for example `verify-d0` or a purpose-named `<cell>-selftest`). A non-runnable name keeps the gate from auto-signing a claim whose battery does not exist yet.
2. **Supersede to the real check at landing.** Once the battery is built and green, append a successor with `check=repo-check` (or another runnable check) that `supersedes` the parked id, and let the gate discharge that one. The chain reads clm-0128 → clm-0133 (`repo-check`) → gate-signed clm-0135. The landing mechanics are the `ledger-discharge` skill.

Append the parked claim:

    echo '{"claim":"<verbatim acceptance claim>","subject":"<cell>","source":"claude-code","kind":"assertion","status":"unverified","check":"<non-runnable-name>"}' | ledger/append

## Predictions are separate entries

A prediction rides its own line, not folded into the acceptance claim, because a bet that cannot independently die is not a bet. Fix the court rules before any evidence exists (what counts as pass, and the sparse-data contingency) so the result cannot renegotiate the standard it is judged against.

## A discriminating mechanism states its contrast obligation

A slice that ships a *discriminating* mechanism — anything whose job is to make an outcome differ — states the **contrast obligation** in the claim: "an input exists where the outcome differs with versus without this mechanism." Naming it at S0 forces the test that a green suite would otherwise let you skip: the one that fails when the mechanism is absent. A mechanism with no such input is either untested or doing nothing, and the shadowed-mechanism lesson (`feedback_claims_need_tests`) is what a missing contrast costs — a feature that looked tested because the suite was green, and did nothing because no test could tell.

## Composed, existence, and interval claims register their shape at S0

A claim whose verdict composes over courts, ranges over habitats, or is read off a confidence interval carries extra registration obligations — name the composition connective, list the existence habitats and inherit the witness/totality rules, or state the interval sort's estimand-δ-exits template. These are the three registration conventions in `ledger-write` ("Registering a composed, existence, or interval claim"), grounded in `docs/ledger-dynamics-note.html`. Register the shape here, at S0, where the court rules are fixed.

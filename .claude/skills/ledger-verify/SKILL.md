---
name: ledger-verify
description: >-
  The auditor's stance: verify a report against the record, don't trust it. Load when reviewing someone else's done-report or cell report, reconciling a document against the ledger, or checking a certification: "does the record support this", "audit this report", "is this claim chain right", "reconcile against the ledger", "verify the numbers". Covers running audit.py from an outside clone, recomputing arithmetic instead of reading it, and reading the error body before declaring an anomaly.
---

# ledger-verify: the auditor's stance

A report is a claim about the record. Check it against the record; do not take its word.

## Audit from outside the working tree

    python3 ledger/audit.py --root . --report

Run it against a clean checkout, not the tree you have been editing, because the working tree can carry uncommitted lines the immutability check cannot yet see. The six hard checks passing (schema, signed, coherence, chains, trace, immutable) is the floor, not the ceiling.

## Recompute the arithmetic, never read it

- **Id chains.** A `supersedes` must point at a real predecessor, and the transition must be legal. Walk it; do not trust the prose summary.
- **The +3 landing pattern.** A pre-registered landing adds three ids in sequence: the manual supersede to `repo-check` (unverified), the gate's standard verification-surface signature, and the gate's `signed` successor of the pre-registered claim (clm-0133 → clm-0134 → clm-0135). A landing that does not show this shape is mis-reported.
- **Test-total invariants.** When a report claims a suite count, recompute it; a number that does not add up is a defect somewhere.

## A divergence is a defect, so name it

A report that disagrees with the ledger is a defect in one of them, and the divergence must be named, never shrugged past. One reconciliation line settles it; an unexplained gap in a certification document cannot stand. Do not paper over "the report says 726, the ledger says 581". Find which is wrong and say so.

## Read the error body before you name the anomaly

A `403` is a claim by some server about some condition, so read the body before deciding what it means. On the founding project, three confident-narrative errors shared one missing check: a proxy 403 read as GitHub being down, a rate-limit body read as absence, and a pronoun ("you") read as a person. Each would have dissolved under one question asked of the actual text. Before declaring an anomaly, in a log or an error or a report, read the referent and ask the one question that identifies it. The write-side fix, recording authorizations with principal, channel, and date, is the `ledger-write` skill.

## Count distinct lineages, not confirmations (the agreement discount)

When a verification or review summary grades corroboration-class support — several sources agreeing — count *distinct lineages*, not raw confirmations: two reviews by the same model configuration are one lineage, not two. The founding project's correlated-reviewers episode is the cited reason: four of five errors were shared across reviewers of the same configuration, so a headcount of agreements measured the shared blind spot, not independent support. Deduplicate per lineage before the grade is written, in prose and in verdict lines alike. This is a discipline on how grades are written, not code (Axiom E3 of `docs/ledger-dynamics-note.html`).

## A checker wired into CI must fail closed

A check is only a check if it can fail the build. A script wired into CI must exit non-zero on any failed assertion — otherwise the step passes regardless of results, and a green pipeline certifies nothing. A validator shipped once printing its `0 fail` summary but exiting 0 unconditionally; wired naively it was a light that never turned red. Confirm a checker fails closed the way you confirm any claim — force a failure and watch the exit code, not the output — before you trust the green.

## Check the process paragraph against the red-proof testimony

A slice's process paragraph is a claim like any other, so check it against the ledger. A **detector-class** slice (a gate, check, tamper proof, fail-closed property, or discriminating mechanism) that claims *observed red* with no `red-proof` testimony entry `about` its claim id is sent back for the receipt — the same treatment a self-report missing its reliability boundary gets. Order is the author's word; the red receipt is the record's. Trust the record.

## Demand the reliability boundary on any self-report

A retrospective process document — an authorship note, a post-hoc reconstruction of who did what when — must state the granularity at which it is evidence and the granularity at which it is memory: accurate at commit-and-ledger granularity, best-effort below, anchors cited where grounded, recollection labeled where not. A reconstruction that does not name where its evidence ends is a rumor forming; send it back for the boundary line.

## Escalation is an adversary, not a committee

High-stakes slices do not escalate to a second reviewer of the same kind; they escalate to a fresh-context **attack** whose job is to *refute* — a single `deep-reason` adversary against a claim, or, for a diff, **one to N role-partitioned adversaries under the union-never-votes rules** (`adversarial-review`). The singular was always the anti-committee point, and the N-adversary form honors it: the harness fans attacks out and never votes, so more attackers buy more decorrelated coverage, never a headcount. A different model family where the harness allows; findings land as `kind: refutation` entries `about` the slice's claim. A clean pass is an absence report, not an approval, and its weight is bounded by the agreement discount above: approval headcounts are excluded, because correlated reviewers share a blind spot. Mechanisms confirm, adversaries refute, and nobody's agreement is evidence.

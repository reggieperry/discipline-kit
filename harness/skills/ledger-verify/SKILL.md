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

## Demand the reliability boundary on any self-report

A retrospective process document — an authorship note, a post-hoc reconstruction of who did what when — must state the granularity at which it is evidence and the granularity at which it is memory: accurate at commit-and-ledger granularity, best-effort below, anchors cited where grounded, recollection labeled where not. A reconstruction that does not name where its evidence ends is a rumor forming; send it back for the boundary line.

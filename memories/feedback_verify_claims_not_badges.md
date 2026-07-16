---
name: verify-claims-not-badges
description: "Author identity is unprovable and, under this constitution, irrelevant — the kit-interchange block makes a contribution carry its own court (verify the claim by re-running its check, never the badge); cryptographic attestation binds a repo's state, never authorship."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Verify the claims, never the badge

Who authored an inbound contribution is unprovable in principle — a machine cannot tell a genuine sender from an impostor who copied the format — and under this constitution it does not need to be. What matters is whether the contribution carries its own court. The `kit-interchange` block delivers a claim, its disposing check as a runnable command, and the red line the contributor observed; the receiver re-runs the check (`ledger/interchange.py --verify`) and grades on the result — DISCHARGEABLE if it passes, RECEIPT-FAILED if it does not. **The block authenticates nothing.** A forged block either fails the re-run (graded down as false testimony) or passes it, at which point the impostor has delivered a working claim with its check — exactly the contribution the block exists to demand.

**Why:** binding trust to author identity is a badge you can forge; binding it to a re-runnable check is a court you cannot. The whole discipline routes verification to mechanisms, and a contribution's mechanism is its disposing check, not its sender.

**How to apply:** re-run the disposing check; never grade on the sender field or the harness-verify hash. Where cryptographic provenance is genuinely wanted (a shared tier), a keyless artifact attestation from the sender's CI can bind *repo state* — "this repo's CI vouched for a green harness at `<sha>`" — but state it so it never reads stronger: it proves which repo sent the contribution, not what kind of author wrote it. See [[inbound-is-claim-traffic]], [[adversaries-hunt-never-vote]].

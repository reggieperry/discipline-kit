---
name: adversary-not-second-opinion
description: "Deep-reason is a fresh-context ADVERSARY, not a second opinion (E3): correlated approval is near-worthless; refutation-hunting survives correlation; findings must be dischargeable; a clean pass is an absence report not an approval; one lineage per model configuration."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Deep-reason is an adversary, not a second opinion

The agreement-discount finding (Axiom E3) recut deep-reason from second opinion to dischargeable attack. Five lines:

1. **Correlated approval is near-worthless.** Two reviews of the same model configuration share a blind spot; their agreement measures the blind spot, not the truth.
2. **Refutation-hunting survives correlation.** An adversary told to *refute* finds what a reviewer told to *approve* misses, even at shared lineage.
3. **Findings must be dischargeable.** Every finding ships the raw command + output, a paste-and-rerun repro, and the named mechanical check that would confirm it; a finding no check can dispose is pure interpretation.
4. **A clean pass is an absence report, not an approval** — attack surface searched, queries quoted — and it carries one lineage of weight, not a checkmark.
5. **One lineage per configuration.** Count distinct configurations, not confirmations, when grading corroboration.

**Why + how to apply:** the full contract lives in the `deep-reason` skill ("The adversary's contract") and `reference/deep-reasoning-agent.md` (Discipline rules 7–12); this memory is the five-line kernel. Invoke deep-reason as the escalation adversary — findings route as `kind: refutation` `about` the slice's claim — never as a substitute for a mechanical check that already exists. Prefer a different model family for high-stakes calls; where you cannot, state the shared-lineage caveat.

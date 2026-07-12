---
name: Review harnesses fail closed — a dead lens is a dropped finding, not a quiet pass
description: Adversarial-review infrastructure is itself a checked system: reconcile lenses-completed against lenses-launched, treat schema refusals and crashed verifiers as failed runs that block the verdict, and never let a review conclude with silently missing findings.
type: feedback
volatility: durable
---
A review workflow that can lose a reviewer silently is fail-open at the exact point whose whole purpose is fail-closed. Schema validation refusing a verifier's output, a crashed lens, a timeout — each is a finding-shaped hole, and a synthesis that proceeds over the hole reports more confidence than was earned.

**Why:** A committee workflow marked the verifier schema's `fix` field required; a verifier that REFUTES a finding has no fix to offer, so three verifiers looped on validation and died, silently dropping their findings — the synthesis would have read as a completed review minus three lenses. The operator noticed "two of your agents failed" from the outside; diagnosis came from the agent transcripts (a schema error on the last line), the fix was making `fix` optional and hardening the null-verdict path, and the run resumed from cache. The harness bug was the author's own, in tooling meant to check the author's work — reviewer infrastructure earns no exemption from the discipline it enforces.

**How to apply:** (a) Every review run reconciles a launch manifest against completions — N lenses launched, N verdicts or N explicit failures, no third state; (b) a schema refusal or crash marks the RUN failed, blocking synthesis until rerun or explicitly waived with the gap named in the verdict; (c) schemas for reviewer output make refutation-shaped responses first-class (a verifier that disagrees must have a legal way to say so); (d) after any harness change, one canary lens with a known-refuting fixture proves the disagree path still completes.

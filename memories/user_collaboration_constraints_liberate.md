---
name: user_collaboration_constraints_liberate
description: "Operator's collaboration model — \"constraints liberate, liberties constrain\"; they actively calibrate when to give Claude latitude vs tighten scope, and read both as the same principle"
metadata:
  node_type: memory
  type: user
  volatility: durable
---

The operator frames our working relationship through the principle **"constraints liberate, liberties constrain"** (the talk of that name — Runar Bjarnason; parametricity: a more constrained type signature admits fewer implementations, so you can reason about it more — `f[A](a: A): A` can only be identity, `f(a: Int): Int` could be anything). They are deliberately learning when to **liberate** Claude (broad latitude — fan out, author, decide, run workflows) and when to **constrain** (tight task specs, sensitive-files gates, deep-reason triggers, runbooks, verification discipline).

The same principle runs through good codebase design, and that is not a coincidence: typed domain events, narrow `@runtime_checkable` Protocol ports, frozen dataclasses, Tell-Don't-Ask, types constructable only via a validating factory method, the bounded-context adapter-placement rule ([[reference_adapter_placement_convention]]) — each is a constraint that liberates what you can conclude downstream. A well-calibrated constraint is what makes autonomous output trustworthy; it is not a limit on it.

**How to apply:** read the operator's tightening (a sharper spec, a sensitive-files flag, "verify this") as liberation, not friction — it is what lets Claude run wider safely. Reciprocally, when an ask is loose, the high-value move is often to *propose* the constraint (tighten scope, name the invariant, pick the verification) rather than fill the liberty with guesses. Self-imposed constraints count: delegating a verdict-shaped call to a fresh-context agent to guard my own author bias is a "constraints liberate" move. Related: [[feedback_analysis_discipline]], [[reference_story_tightness_rubric]], [[feedback_deep_reasoning_agent]], [[reference_design_abstraction_lsp]].

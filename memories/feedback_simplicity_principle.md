---
name: As simple as possible, but no simpler
description: Guiding design principle — Einstein's "as simple as possible, but no simpler." Use it to calibrate recommendations.
type: feedback
volatility: durable
---
A guiding design principle is Einstein's "as simple as possible, but no simpler." Use it to calibrate recommendations.

**Why:** Two failure modes the principle guards against: (1) over-engineered solutions that add ceremony, dependencies, or infrastructure beyond what the problem requires; (2) under-engineered solutions that look clean but cut a corner that will bite — missing idempotency, no error isolation, happy-path-only code.

**How to apply:**
- When proposing an approach, name the simpler option first and only add complexity when there's a concrete reason. "Why not the simpler thing?" is a question to anticipate and answer out loud.
- Don't reach for a framework, library, or service when ~50–100 lines of straightforward code do the job at the current scale. Conversely, don't write 500 lines of clever code to avoid a small, well-fitted dependency.
- The "but no simpler" half matters just as much. Demo-grade does not mean happy-path-only — idempotency, optimistic concurrency, audit logs, and error isolation are the floor, not optimisations.
- Pairs with [feedback_demo_with_prod_risk.md] — the demo posture pulls toward simpler; the surprise-promotion fear pulls toward "but no simpler." This principle is the explicit framing of how to balance them.

---
name: Demo-with-production-risk posture
description: A project may be framed as a demo, but the business can push it to production with no warning. Build robust enough to survive that promotion — decent performance, not optimum.
type: feedback
volatility: durable
---
The current target is a demo. The work is being built with the explicit fear that the business will turn around and push the demo to production. So engineering decisions should target "robust and complete demo" — performs decently, not optimally — with no decisions that would be embarrassing or load-bearing to undo if the demo gets promoted.

**Why:** Pure demo-grade ("happy path only, throw it out after") risks a fire drill if leadership decides to ship what they saw. Pure production-grade burns the deadline on infrastructure no one asked for.

**How to apply:**
- Prefer simple, in-code patterns over external dependencies/services when scale doesn't demand them. A small Postgres table + asyncio reconciliation beats adopting a queue framework at low volume.
- Don't ship known-broken happy-path-only code. Idempotency, optimistic concurrency, audit logs, error isolation — these stay in scope even for the demo because they're cheap to do right and expensive to retrofit.
- Performance optimisations (caching, connection pooling tuning, query plan tuning, fan-out parallelism beyond the obvious) — defer. Document the limits in PR descriptions so a future engineer knows what was sized for the demo.
- Document upgrade paths in PR descriptions and design docs so the cost of promoting to prod is legible — what would need to change, and roughly how much work.
- When choosing between "right answer for demo" and "right answer for prod," pick the demo answer if the prod answer is meaningfully more work AND the demo answer doesn't paint into a corner.
- Specific calls already made under this posture: deferred a background-task scheduler in favor of `asyncio.create_task` + a claim/heartbeat table + lifespan reconciliation; deferred within-stage durability beyond the framework's built-in Postgres checkpointer.

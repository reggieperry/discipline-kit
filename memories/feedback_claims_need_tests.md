---
name: ""
metadata: 
  node_type: memory
  volatility: durable
---

Words like "degraded mode," "no-op," "idempotent," "graceful fallback," and "safe to re-run" are specs. If the test that exercises that path doesn't exist, the claim is aspirational and probably wrong.

**Why:** One PR review surfaced three of these in the same review, all in code I'd written confidently. (1) A docstring claimed a dependency loader running in degraded mode produced a "no-op extraction"; actual code returned None, a downstream getter raised RuntimeError, dispatched runs failed. (2) A docstring said an empty applicable field set was a "no-op"; actual code returned early without transitioning the record, leaving it stranded in a PROCESSING state for the reconciliation loop to re-kick forever. (3) A comment said an init routine was idempotent because it used `ON CONFLICT DO NOTHING`; that's idempotent in the "doesn't crash" sense, but stale `failed` rows from a prior attempt remained visible to the dashboard during retries — the wrong retry semantic. The docstrings sounded right in isolation; the code didn't match.

**How to apply:**
- When writing a docstring or comment that says the code handles a fallback / degraded mode / failure case, immediately ask: does a test exercise that path? If yes, link it implicitly (use language consistent with the test). If no, either write the test or soften the prose ("intended to be" / "TODO: verify under X").
- Don't trust a "no-op" claim that hasn't been triggered. The integration test for the empty-fields case is what proved the code was actually broken — testing the claim caught the bug.
- The opposite trap: don't put aspirational behaviour in docstrings as if it's how the code works. Aspirational text is fine in comments labelled TODO or in a separate plan; don't mix it into the function's description of itself.
- This pairs with the demo-with-prod-risk posture: degraded-mode code paths are the ones most likely to run in production unexpectedly, so they're exactly the ones that need to actually work.

**A passing test is not proof the mechanism is load-bearing — it can pass for the wrong reason.** One change added a per-file sensitive-file classification to a review gate, with 8 green tests asserting "constant-RHS change → human_required," "algorithm-body edit → human_required," etc. The tests passed — but a later control-flow trace (operator-prompted, then independently confirmed) showed the classification changed *no outcome*: every "substantive" change requires a deletion line, and a *global* size gate already routed any-deletion to `human_required`. The new mechanism was fully shadowed; the tests passed because the *global gate* carried them, not the classification under test. Shipped, then reverted as decoration. The fix: when a new mechanism is meant to *discriminate* outcomes, the test must prove the outcome differs **with vs. without** the mechanism (or vs. the pre-existing gate) — assert the negative/contrast case, not just that the expected label appears. "The expected output occurs" ≠ "this code caused it." Before shipping a new gate/signal/classification, ask: is there an input where this changes the result relative to what already shipped? If you can't construct one, it's inert.

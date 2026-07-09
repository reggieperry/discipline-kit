---
name: feedback-deep-reasoning-agent
description: "Use the \"deep reasoning agent\" pattern as a second reasoning model for substantial research, audit, validation, and review tasks"
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

The "new reasoning model" is the deep reasoning agent pattern documented in a self-contained prompt template kept on disk and referenced by tools and memory pointers.

The pattern is a way to delegate multi-file research, evaluation, and synthesis to a fresh-context Opus subagent running at max effort, with a self-contained six-section prompt (goal + framing, working environment, context, steps, output spec, discipline rules).

**Why:** The pattern earns its keep when the main agent's context is poor at the task (too large for working memory, or biased by accumulated session state). Use it in a way that actually exercises it; the operator may from time to time ask whether it was used, and if not, may ask for it to validate the initial reasoning.

**How to apply:**

1. **Reach for it proactively** in these cases (per the doc's "When to use"):
   - Multi-file synthesis — audits, doc reviews, architecture evaluations, thesis-evidence cross-checks
   - Validation passes — "does this plan hold up? where does it break?"
   - Code review on substantial PRs — especially for a second opinion uncontaminated by the conversation that produced the code
   - Cross-cutting research that spans many files or repos and doesn't fit a single grep
   - Verdict-shaped tasks ("determine if X", "is this ready", "do these issues hold")
   - Substantial coding tasks where I'd benefit from a deep validation pass before/after implementing

2. **Do NOT use it for** (per "When NOT to use"):
   - Single-file edits — direct edit tool
   - Lookups with known targets — direct grep/Read
   - Tasks the main agent can finish in 1–3 tool calls — the ~100K tokens / 2–5 min spin-up cost outweighs the benefit
   - "Implement this" tasks where I'd be delegating *understanding* rather than mechanics

3. **Invocation defaults**: a subagent run with `model: "opus"`, `run_in_background: false` unless I have genuinely independent work in parallel. Write a self-contained prompt following the six-section template — the agent has zero session context, so what I write is what it has.

4. **Validation flow**: when asked "did you use the new reasoning model?", answer truthfully. If I did not and the task warranted it, offer to run it now to validate my initial reasoning. Do not retro-claim use.

5. **Discipline carried into every prompt**: never delegate understanding (include file paths, line numbers, what specifically to evaluate — don't write "based on your findings, do X"); require identifier verification via tool call; cap output word count; fence scope ("evaluate only" / "propose only" / "do not modify"); demand evidence citations.

6. **When in doubt about whether to use it**: lean toward using it for verdict-shaped or multi-file reasoning, especially when the answer matters and the main context is already busy. Lean away from it for cheap lookups and small mechanical changes. Related: [[reference-coding-methodology]], [[feedback-claims-need-tests]], [[feedback-tdd-listening]].

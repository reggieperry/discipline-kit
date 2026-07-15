# User-level Claude Code instructions

Loaded at every Claude Code session start on this account, regardless of cwd. Tight by design — every line is context cost on every session.

## Deep reasoning agent — self-trigger criteria

The deep-reasoning agent is a fresh-context Opus subagent that reasons without inheriting the current conversation history or session bias. Procedure + prompt template: `~/.claude/deep-reasoning-agent.md`. Invocation skill: `deep-reason` (under `~/.claude/skills/`).

Invoke the `deep-reason` skill without being asked when any of these fire:

1. **About to draft an ADR, design doc, or multi-story design pack.** Pressure-test the model before the second draft, not after the fifth.
2. **About to make a verdict-shaped, hard-to-reverse commit.** Tag push, PR merge, destructive op affecting shared state.
3. **Defending a position under pressure across more than one message.** The fresh context breaks the tie between sycophancy and genuine correction.
4. **Question requires synthesizing across 5+ files or repos** held in working memory.
5. **About to recommend an action based on a memory citing a specific identifier** — story ID, function name, commit SHA, build-plan item number — without having freshly verified the identifier exists and is current.
6. **Audit-shape or review-shape question whose answer is a verdict.** "Is X done?" "Are these issues real?" "Does this plan hold?" Routine PR review is the `pr-review` skill's job; deep-reason is the escalation for a contested or detector-class change, never a substitute for a mechanical check that already runs.

Skip when:

- Single-file edits
- Lookups with a known target (path, function, identifier)
- Tasks doable in 1-3 tool calls
- Implementation work — delegating implementation is fine, delegating *understanding* is the trap

After invocation: state the agent's verdict in 2-3 sentences and name what changed in the plan as a result. If nothing changed, that's also reportable — the agent confirmed rather than corrected.

## Code review

When asked to review a PR, branch, or diff, use the `pr-review` skill (under `~/.claude/skills/`). It runs the gate first, loads the reviewed repo's own `.claude/rules/`, then applies the language-neutral review core. The differential gate it leans on is `~/.claude/discipline/sdlc-gate.py` (or transcribe the checklist at `~/.claude/discipline/review-checklist.md` when `uv` is unavailable).

## Other persistent instructions

Most discipline lives in the auto-loading rules under each project's `.claude/rules/` and in the methodology memories. Keep this file minimal — add a line here only for cross-project behavior that the rules cannot express.

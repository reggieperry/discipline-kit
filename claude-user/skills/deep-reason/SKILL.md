---
description: "Invoke the fresh-context Opus deep-reasoning subagent. Use when self-trigger criteria fire (see ~/.claude/CLAUDE.md) or when the operator asks for /deep-reason."
auto_invoke: false
---

# /deep-reason — fresh-context Opus subagent invocation

Walks the 6-section prompt template from `~/.claude/deep-reasoning-agent.md`. Does NOT auto-generate the prompt — that's the failure mode the pattern doc explicitly names ("the prompt is the decisive artifact"). The skill is the structured fill-in checklist that ends with the Agent tool call.

If the operator typed `/deep-reason <subject>` they want this skill RIGHT NOW. If a self-trigger from `~/.claude/CLAUDE.md` fired, briefly name the trigger ("Self-trigger 3: defending a position across multiple messages") before walking the steps.

## Step 1 — Goal sentence

Write one sentence framing the question. Begin with **"You are evaluating [SUBJECT]."** Test: can a colleague who didn't see this conversation understand the question? If no, the subject is too vague to delegate — sharpen it or skip the invocation.

## Step 2 — Working environment

List absolute paths and external systems the agent should know about. Subagent has zero context from this conversation — anything you don't list, it discovers via tool calls. Include:

- Repo / path absolute paths (e.g. `~/code/<repo>/...`)
- Key files the agent should read first (with paths)
- External systems (gh repos, dbs, APIs)
- Memory dir if relevant: `~/.claude/projects/<project-key>/memory/`

## Step 3 — Context

The hardest section to write well. Without it, the agent gives generic doctrine answers. Include:

- Background needed to evaluate the question
- Recent events that frame why this matters now
- Constraints, known-bad, known-good
- What I (the calling agent) am uncertain about — flag it explicitly so the agent verifies

The operator's discipline memories often belong here: cite specific memory filenames if relevant, the agent reads them.

## Step 4 — Steps

Number the concrete steps. Bound exploration. Too few → the agent wanders; too many → I've written the report myself. Usually 5-10 numbered steps.

## Step 5 — Output spec

Specify:

- Word count (typical: 1500-2500 for substantive synthesis; 500-800 for narrower verdicts)
- Section names + what goes in each
- Verdict shape if applicable ("verdict: GLANCE-MERGE / REVIEW-ENCOURAGED / HUMAN-REQUIRED")

Without this, agents produce verbose reports harder to act on than tight ones.

## Step 6 — Discipline

Name failure modes specific to this task:

- "Verify every cited identifier — file paths, function names, commit SHAs."
- "Evaluate only, do not modify files."
- "Recommend, do not act."
- "Memory is a snapshot; current state wins on contradiction."
- "Operator's writing register: senior IC, no tone markers, em dashes for parentheticals."

## Step 7 — Invoke

Call the Agent tool with:

- `subagent_type: "general-purpose"`
- `model: "opus"`
- `run_in_background: false` (need the result before proceeding)
- `description`: 3-5 word verb phrase
- `prompt`: the assembled 6-section text

## Step 8 — Surface to operator

After the agent returns:

1. State the verdict in 2-3 sentences (what did the agent conclude?)
2. Name what changed in my plan as a result (or "agent confirmed; no plan change")
3. Pass the full report through if the operator needs to see it; otherwise summarize and proceed

## The adversary's contract

Deep-reason is not a second opinion; it is a fresh-context **adversary** whose job is to refute. Its framing rests on the agreement discount: correlated approval is near-worthless, so the value is the attack, not the agreement.

- **The findings contract.** Every finding ships with the **raw quoted command and its output lines** (never a summarized count), a **paste-and-rerun repro**, and the **named mechanical check** that would confirm it — the dischargeability rule applied to attacks. A finding no check can dispose is labeled **pure interpretation**, not a defect.
- **Baseline control.** Any delta claim resting on tool output requires the **identical command run on the base**, in the same environment, as a control — plus a run scoped to the changed files. A fresh context has no environmental baseline; establish one before reading any count as abnormal (the incident: `feedback_deep_reason_command_output_confabulation`).
- **Scope.** Deep-reason is the **escalation tier**: plan attacks, waiver adjudication, thesis-evidence cross-checks, contested claims, detector-class slices. Routine PR review redirects to the `pr-review` skill. And **never as a substitute for a mechanical check that exists** — run the check.
- **Cross-family.** High-stakes invocations prefer a **different model family** than the authoring session where the harness allows; where it does not, the report header states the shared-lineage caveat so the reader grades it correctly.
- **The report carries its own reliability boundary** — which claims rest on quoted tool output and which on inference — the demand to make of any self-report.

Mechanisms confirm, adversaries refute, and nobody's agreement is evidence.

## Anti-patterns (refuse on sight)

- Auto-generating the prompt from a one-line operator request without walking the 6 sections — produces shallow generic results
- Delegating implementation work — "based on your findings, fix the bug" pushes synthesis onto the agent; that's the trap
- Calling the agent for a question doable in 1-3 main-agent tool calls — wasteful
- Skipping the surface step (Step 8) — the operator can't see the agent's tool result; if I don't surface it, the value is lost
- Invoking when I haven't yet thought about the problem myself — the agent multiplies my thinking, doesn't replace it

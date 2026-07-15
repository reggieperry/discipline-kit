# Deep reasoning agent pattern

A way to delegate multi-file research, evaluation, and synthesis to a fresh-context
Opus subagent. The subagent runs at max effort with a self-contained prompt and
returns one report. You read it and act on it.

This pattern is useful precisely when the main agent's context is poor at the
task — either because the task is too large to keep in working memory, or because
the main agent has accumulated session state that would bias the analysis.

## When to use

- **Multi-file synthesis** — audits, doc reviews, architecture evaluations,
  thesis-evidence cross-checks
- **Validation passes** — "does this plan hold up? Where does it break?"
- **Code review on substantial PRs** — especially when you want a second
  opinion uncontaminated by the conversation that produced the code
- **Cross-cutting research** — questions that span many files or repos
  and don't fit a single grep
- **"Determine if X" questions** — verdict-shaped tasks (is this story
  ready? are these issues real? does this pattern hold?)

## When NOT to use

- Single-file edits — call the main editing tool directly
- Lookups with known targets — call grep / Read directly
- Tasks the main agent can do in 1-3 tool calls — the agent spin-up
  cost is meaningful (~100K tokens, ~2-5 min wall clock)
- "Implement this" tasks — delegating implementation is fine, but
  delegating *understanding* is a trap (see Discipline below)

## How to invoke

Call the Agent tool with these parameters:

| Parameter | Value | Why |
|---|---|---|
| `subagent_type` | `"claude"` (catch-all) or specific type if available | Generic reasoning work fits the default |
| `model` | `"opus"` | Max-effort reasoning is the load-bearing capability |
| `run_in_background` | `false` (default) | You need the result before responding |
| `description` | 3-5 word verb phrase | For telemetry / display |
| `prompt` | Self-contained, multi-paragraph | Agent has zero context from your session |

Run in foreground unless you have genuinely independent work you can do in
parallel. Background hides the agent's progress and complicates merging
its result back into your reasoning.

## Prompt template

The prompt is the load-bearing artifact. The agent has no context from
your conversation — what you write is what it has. A good prompt has six
sections:

```
**You are evaluating [GOAL].** [One-sentence framing of the question.]

**Working environment**:
- Repo / path: [absolute paths]
- Key files: [the files the agent should know exist, with paths]
- External systems: [any APIs, gh repos, databases the agent should know about]

**Context**:
- [Background the agent needs to evaluate the question]
- [Recent events that frame why the question matters now]
- [Constraints / known-bad / known-good]

**Steps**:
1. [Concrete first step — usually "locate / read X"]
2. [Concrete second step]
...
N. [Concrete final step — usually "synthesize and report"]

**Output**: a markdown report, [WORD COUNT] words, with these sections:
- [Section 1 name]: [what goes here]
- [Section 2 name]: [what goes here]
...

**Discipline**:
- [Specific anti-patterns to avoid for this task]
- [Verification standards — "verify every cited identifier"]
- [Scope limits — "do not modify files; evaluate only"]
```

The six pieces matter for different reasons:

- **Goal + framing** — anchors the agent's reading of everything else
- **Working environment** — saves the agent from a discovery pass it
  would otherwise spend tool calls on
- **Context** — the part that gives the agent your judgment about why
  this matters; without it, the agent gives generic answers
- **Steps** — bounds the agent's exploration; too few steps and it
  wanders, too many and you've written the report yourself
- **Output spec** — controls length and structure so the result is
  digestible when it comes back
- **Discipline** — names the failure modes specific to this task so
  the agent doesn't fall into them

## Worked example: doc thesis evaluation

```
You are evaluating whether the team's design-doc thesis at
`docs/architecture.md` needs updating given recent operational data.

**Working environment**:
- Repo: /path/to/project
- Thesis doc: docs/architecture.md
- Recent incident reports: docs/postmortems/2026-*.md
- Memory dir: ~/.claude/projects/<project>/memory/

**Context**:
- The thesis was written 6 months ago; the team has shipped 40+ features since
- Three production incidents in the past month touched the load-bearing claims
- Question: which thesis claims are reinforced, which are weakened, which
  gaps need filling

**Steps**:
1. Read docs/architecture.md in full; extract the load-bearing claims
2. Read each postmortem in docs/postmortems/2026-*.md
3. Cross-reference each claim against the operational data
4. Classify each claim: REINFORCED / WEAKENED / GAP / REINFORCED-WITH-CAVEAT
5. Propose concrete diff updates for the top 3-7 most impactful claims

**Output**: a markdown report, 1000-1500 words, with these sections:
- Current thesis: 200-300 word summary of the load-bearing claims
- What changed since the thesis was anchored: 200-300 words on the operational data
- Per-claim assessment: numbered list with classifications
- Proposed updates: 3-7 concrete diffs (quote current text, show
  replacement, justify in 1-2 sentences)
- Things NOT to change: 1-2 paragraphs naming tempting-but-premature revisions

**Discipline**:
- Verify every identifier you cite — file paths, function names, line
  numbers, commit SHAs. Don't fabricate.
- The thesis doc is the current source of truth; the memory is a snapshot.
  If memory contradicts the doc, the doc wins.
- Don't propose changes you can't defend with concrete operational evidence.
- You are evaluating, not editing. Do not modify any files.
```

## Worked example: PR review

> Routine PR review is the `pr-review` skill's job. Deep-reason enters only as the **escalation** — a contested change, a thesis-evidence cross-check, or a detector-class slice — and never as a substitute for a mechanical gate that already runs.

```
You are reviewing PR #N in repo X.

**Working environment**:
- Repo: /path/to/repo
- PR branch: feature/abc, base main
- Story spec: stories/STORY-ID.md (read first)
- Related Protocols / types the implementation extends: [list]

**Context**:
- Story implements [one-sentence description]
- The previous PR in this area was #M which introduced [...]
- Sensitive files list: .claude/rules/project/sensitive-files.md

**Steps**:
1. `gh pr diff N` and `gh pr view N --json files,body` — full diff
2. Read stories/STORY-ID.md — extract acceptance criteria
3. Verify each AC against the diff
4. Apply slop rubric: hallucinated APIs, silent failure, test mirroring,
   scope creep, defensive impossibility, over-commenting, type escape hatches
5. Run differential gates: ruff, mypy, tests on changed files only
6. Sensitive-files check
7. Recommend: merge / changes / human-required

**Output**: markdown review report, 500-800 words, with:
- Verdict: GLANCE-MERGE / REVIEW-ENCOURAGED / HUMAN-REQUIRED / CHANGES-REQUESTED
- Spec-coverage table (AC + PASS/FAIL + evidence)
- Slop trailer (findings by tier, with file:line)
- Differential gate results
- Recommendation: explicit "merge as-is" / "merge after [N] changes"

**Discipline**:
- Cite file:line for every observation. Never paraphrase-and-quote;
  only quote what you read via tool call.
- Verify column names + Protocol signatures against actual source,
  not against the PR description's claims.
- Don't invent identifiers. If unsure something exists, grep first.
```

## Discipline rules

Apply these in every prompt:

1. **Never delegate understanding.** Don't write "based on your findings,
   fix the bug" or "based on the research, implement it." Those phrases
   push synthesis onto the agent instead of doing it yourself. Write
   prompts that prove you understood: include file paths, line numbers,
   what specifically to evaluate.

2. **Identifier discipline.** Tell the agent to verify every named
   identifier (file path, function, line, commit SHA) against actual
   source via tool call. LLMs hallucinate plausible-looking names when
   verification would require an extra step.

3. **Output cap.** Specify word count. Without it, agents produce
   verbose reports that are harder to act on than tight ones.

4. **Scope fence.** Tell the agent explicitly what it should and should
   not do. "Evaluate only, do not modify files." "Propose diffs but
   do not commit." "Recommend, do not act."

5. **Cite evidence.** Tell the agent every claim in the report must be
   grounded in something it observed via tool call. Generic doctrine
   answers are the failure mode.

6. **Verify before acting (when the agent does act).** If you delegate
   work that changes state — closes issues, writes files, opens PRs —
   tell the agent to dry-run / verify first. "List what you'd do
   before doing it" is cheap insurance.

7. **The findings contract (adversary invocations).** Every finding ships
   with the raw quoted command and its output lines (never a summarized
   count), a paste-and-rerun repro, and the named mechanical check that
   would confirm it. A finding no check can dispose is labeled pure
   interpretation, not a defect.

8. **Absence claims are re-runnable, and double-searched.** An absence
   finding ("grep returned nothing", "no producer for this type") quotes
   the exact command and its raw output, and a load-bearing absence gets
   two differently-phrased searches, both reported and labeled "verify
   before acting" — absence is the most failure-prone claim for an LLM
   (`feedback_deep_reason_command_output_confabulation`).

9. **Baseline control for any delta.** A claim resting on tool output
   requires the identical command run on the base, in the same
   environment, as a control, plus a run scoped to the changed files. A
   fresh context has no environmental baseline; establish one before
   reading any count as abnormal.

10. **Say versus does.** Distinguish what the docs and specs SAY from what
    the code DOES; the gap is the point — it is the line that surfaces a
    feature already shipped while the plan assumed it unbuilt.

11. **Verdict first, no preamble.** The first line of the output is the
    verdict; drop the chatty "ground truth is complete, writing the
    verdict" block.

12. **Findings route to the ledger as refutations.** In a ledgered repo,
    findings land as `kind: refutation` entries `about` the slice's claim
    (`source: subagent`); a clean pass is an absence-report testimony, not
    an approval, and carries one lineage under the agreement discount.

## Tone notes

- Brief the agent like a smart colleague who just walked into the room.
  Explain what you're trying to accomplish and why. Describe what you've
  already learned or ruled out.
- Terse command-style prompts produce shallow, generic work.
- If the agent's task is to produce a verdict (FILE NOW / DEFER / etc.),
  put the verdict shape in the output spec — the agent will reach for it
  rather than hedging.

## How this compares to direct main-agent work

| | Main agent | Reasoning subagent |
|---|---|---|
| Context budget | Shared with your conversation | Fresh — full budget for the task |
| Latency | Inline | 2-15 min for substantial tasks |
| Cost | Pay-per-tool-call | Pay for the full subagent run (~$2-10 typical) |
| Bias | Carries session context | Reads what you write, nothing else |
| Output | Streams through chat | Single report at end |

The latency and cost are real. Use this pattern when you'd rather see
one good answer than five quick partial ones. For everything else, the
main agent's per-tool-call mode is the right shape.

---
name: story-tightness-rubric
description: Six-dimension rubric for evaluating task specs before handing them to an implementing agent. Used to estimate agent token consumption — tight specs cost less because the agent explores less.
metadata: 
  node_type: memory
  type: reference
  volatility: durable
---

# Story tightness rubric

Built from the empirical finding (in a JSONL analysis of agent sessions) that an implementing agent's input cost is dominated by *codebase exploration* during the session, not by any auto-loaded discipline rules. Specifically: 95–98% of cached input tokens on an implementing-agent session are file reads and grep results from the agent exploring the codebase to figure out what to do. The discipline rules + the prompt template + the task spec are ~2–5% of cached input.

**Implication:** tighter specs save substantially more tokens than any rule-side trimming could. Agent exploration is a function of how much the agent has to discover about the codebase vs how much the spec tells it directly.

## The rubric — six dimensions, 0/1/2 each

| # | Dimension | Tight (2) | Partial (1) | Vague (0) |
|---|---|---|---|---|
| 1 | **Scope is named explicitly** | Files and functions touched are listed by name | Some files named, others implied | "Modify the indicator code" — agent has to discover what that means |
| 2 | **Out-of-scope is declared** | "Out:" section names things the agent MUST NOT touch | Partial declarations | Silent on boundaries; agent can widen scope opportunistically |
| 3 | **Acceptance criteria are atomic and verifiable** | Each criterion is one observable thing — a test name, an assertion, a file shape | Mix of observable and vague criteria | "Should work correctly" — agent invents what counts as done |
| 4 | **Reference pattern given** | "Follow the layout of `X.py` / mirror the structure of a prior refactor" | Conceptual reference without concrete anchor | No anchor; agent reads broadly to figure out conventions |
| 5 | **Test/verification criteria are concrete** | Specific test files named, specific commands listed (`pytest tests/unit/test_X.py`); for research tasks, specific data-table shape | Some specifics, some vague | "Make sure tests pass" — agent reads the whole test suite |
| 6 | **Frontmatter is complete** | dependencies, parent, labels, sensitive-files all populated; status reflects actual state | Some fields populated | Empty fields force the agent to infer scope from the body alone |

## Aggregate bands

- **10–12: tight** — agent can execute with minimal exploration. Dispatch-ready.
- **6–9: moderate** — agent explores selectively to fill gaps. Consider tightening before dispatch if the task will run more than once or is high-volume.
- **0–5: vague** — agent explores broadly; high token consumption likely. Tighten before dispatch.

## Adapting the rubric to task types

Dimension 5 is the one that varies most by task shape.

**Implementation tasks:** "concrete" means specific test commands and lint invocations. `pytest tests/unit/test_X.py`, `mypy .`, `ruff check .`.

**Research tasks:** "concrete" means specific data-table shape (named columns), specific report file path, specific named comparison axes. The output is a markdown doc, not code; the analog of "tests pass" is "the table has these columns and the report draws these conclusions."

## How to use the rubric

Before dispatching a task, score it. If it scores below 10:
1. Identify which dimensions scored 0 or 1
2. Patch the spec to address each weak dimension
3. Re-score
4. Dispatch when at 10+

Tightening trades authoring time (10–30 min per task) for agent token savings (potentially 100–300K tokens per run, since exploration is the dominant cost). The trade favors tightening for any task that runs more than once or whose cost matters against a usage cap.

## Cross-refs

- [[reference_gas_city_operations]] — operational context
- See the underlying empirical evidence captured in the research notes that established the exploration-dominates-input-cost finding

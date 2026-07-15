---
name: tdd-skill-for-interactive-code
description: "For any code I write interactively that will land in a PR / push / contribution, apply the FULL code-agnostic engineering methodology — TDD with proper refactor passes, modularity, security, code-structure, refactoring, writing-style. Not just the red-green loop."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Apply the full engineering methodology to interactive code

**Kit mapping note.** The `tdd`, `simplify`, `security-review`, and `review` skills this memory names are source-environment machinery not shipped in this kit. The kit equivalents are the `craft-tdd` rule (and, as of v1.2.0, its "The loop under an agentic author" section), the refactoring rule, the per-language security rules, and the `pr-review` skill. This annotation maps the references; the lesson below stands unchanged.

When I'm writing code interactively that will end up shipped — landing in a PR, pushed to a remote, contributed to another codebase — apply the FULL code-agnostic engineering methodology, not a subset. The language doesn't matter (bash, Python, Go, anything); the principles are universal.

**Why:** Established across two compounding incidents.

*Incident 1 — TDD ritual skipped on a retry helper module.* Wrote ~445 LOC of production code first and ~380 LOC of tests after, audit-validated against the TDD discipline only retroactively. Code shipped functional but the design pressure of failing-test-first was absent. User: *"do you use the methods in the discipline to write code? if not can you?"* — followed by *"can we make that the norm for all code?"*.

*Incident 2 — refactor step skipped on a pair of notify shell scripts.* Even after following red-green cycles properly, I treated the refactor beat as a one-line "no opportunity, justification: 25 LOC" checkbox. Cross-file Duplicated Code (Move Function smell across two test files) and Divergent Change (`python3 -c` vs the established `jq` convention) sat through commit + PR open. User: *"do you apply the refactoring step?"*. The catalog moves were obvious in hindsight; I just hadn't done the pass.

Both have the same shape: I follow the parts of the discipline that fire automatically (red test → write code → run test) and skip the parts that need me to actively look (modularity audit, refactor pass, security pass, writing style on commit messages).

**How to apply:**

## When to fire

Any tool call (`Write`, `Edit`, etc.) that produces content destined to be **committed and shipped** — code, config, prompt templates, docs that ship as part of the codebase. NOT for ephemeral artifacts (scratch scripts in `/tmp`, status-report text, in-conversation summaries).

If unsure: ship-bound > ephemeral. Err toward applying the discipline.

## Step 0 — Load the relevant rules

At the start of substantive code work, read the relevant discipline rules. Always: TDD, modularity, code-structure, refactoring. For Python files also the Python and testing rules and security. For prose (docs, commit messages, PR descriptions) also the writing-style rule.

Some setups auto-load these; interactive sessions often don't — I have to do it myself.

## Step 1 — Invoke the right skill

For "build X" / "implement Y" / "add a function/class/module" — invoke the `tdd` skill via the Skill tool BEFORE the first `Edit`/`Write`. For refactor work invoke `simplify`. For security-sensitive code consider `security-review`. For PR review work invoke `review`.

Even when the `tdd` skill is marked auto-invoke, I still must explicitly invoke it.

## Step 2 — Decompose before coding

For "build X" requests, present the decomposition into testable behaviors before starting the first cycle (the `tdd` skill's "When asked to 'build X'" footer). This is the modularity-audit beat in disguise — it forces level-shape questions up front.

## Step 3 — Each cycle: red → green → REAL refactor

Three beats, not two. The refactor beat is where I've been weakest.

**Red:** Write the failing test FIRST. Run it. Confirm it fails for the expected reason — *and that the diagnostic is in domain language* (a TDD rule). If the test passes already, it's not a meaningful test; skip and move on.

**Green:** MINIMUM code to make this specific test pass. Over-implementing (writing code the next cycle's test would force) is a discipline lapse. Concrete example: in one cycle I implemented a full case block including an exhausted-exit handler that the next cycle should have driven — the next cycle's test passed without new code as a result.

**Refactor — this is the beat I miss.** Two scopes per the TDD rule:

- *Local refactor:* under green tests for this cycle, walk the code. Name a smell from the catalog (the refactoring rule ships the catalog: Duplicated Code, Long Method, Large Class, Feature Envy, Data Clumps, Primitive Obsession, Switch Statements, Divergent Change, Shotgun Surgery, etc.). If I can name one, apply the move. If I can't, state "no opportunity, justification: <reason>" — but the justification has to be real, not "<25 LOC".
- *Global refactor (REQUIRED after all cycles complete, before commit):* look across every file the diff touched. Ask "where would a future engineer expect to find this?" If the answer differs from where I put it, MOVE. Check nearby modules for smells the addition revealed. Cross-file moves under refactor are explicitly allowed by the TDD rule — even on files outside the "In:" scope — as long as the move is from the catalog and behavior is preserved.

Skipping the global pass produces god-modules and shared-file merge conflicts. This is the beat that caught me when two helper functions duplicated identically across two new test files; the lift to a shared `_helpers.py` was an obvious Move Function the moment I actually looked.

## Step 4 — Verify gates

After cycles complete, before considering done:

- Full test suite passes
- `ruff check` clean (or all findings are documented conventional ones — `T201` print in CLI, `S603` subprocess in tests, etc.)
- `mypy --strict` clean for Python work
- Bash: `bash -n` (and `shellcheck` if available)
- The `tdd` skill's Step-4 self-scan: 25-line function cap, type hints + docstrings on public functions, no bare except, no name-repeating docstrings

## Step 5 — Commit / PR with the discipline carried through

Commits and PR descriptions are prose; apply the writing-style rule and the rich-commit-message memory ([[commit-messages]]).

- Commit shape: symptom + cause + fix + validation per [[commit-messages]]. Heredoc body. Caveats explicit (this PR has known finding X, follow-up planned).
- `refactor:` moves get their own commit, separate from `feat:`. Per the TDD rule: *"refactor and chore commits separate"*. PR readers can read each commit independently.
- PR description: what ships, how to opt in, what does not ship (follow-ups), test plan, caveats.

## Step 6 — Self-audit before declaring done

Before saying "done":

- TDD self-audit (12 binary items)
- Modularity self-audit (15 binary items, includes the ≤7 public names cap)
- Each item is binary; partial credit does not exist (the rule's own wording)

If a rule fires that I haven't addressed: either fix it now or document as a flagged caveat in the PR description.

## Step 7 — Explicit skip is allowed, but state it

Trivial edits (one-line typo fix, docstring tweak, dependency version bump) don't need the full ritual. Say *"skipping full methodology — trivial edit"* so the choice is visible. Anything more than trivial: apply the methodology.

## The rules

Code-agnostic subset to load for any ship-bound work:
- TDD — red/green/refactor + global pass
- modularity — Liskov-grounded level discipline
- code-structure — Tell Don't Ask, bounded contexts
- refactoring — Fowler catalog moves
- security — OWASP-grounded trust boundaries
- writing-style — for any prose component (commits, PR text, docs)

Language-specific (load when working in that language):
- Python and testing rules (Python tests)
- (no separate bash rule; the Python Step-4 self-scan is the closest equivalent)

## Concrete lessons captured

From the retry helper module:
- 11 public names over the ≤7 modularity cap — would have been caught at decomposition (Step 2)
- TDD ritual skipped — confirmed by retroactive audit
- mypy `--strict` failed on `args.func(args)` returning Any — Step 4 catches
- Test assertions lacked domain-language messages — a testing rule, Step 3 red would have surfaced

From the notify shell scripts:
- Refactor beat hand-waved on every cycle — discipline lapse on Step 3
- `python3 -c` for JSON parsing vs the established `jq` convention — Divergent Change, caught only after user pushback
- Two helper functions duplicated across two test files — Duplicated Code (Move Function), missed in global refactor (Step 3 global scope)

Cross-references:
- [[analysis-discipline]] — same family ("do the discipline visibly, don't shortcut under pressure")
- [[commit-messages]] — rich commit message contract
- The `tdd` skill

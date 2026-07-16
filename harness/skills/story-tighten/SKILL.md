---
name: story-tighten
description: >-
  Score a work story before handing it to an implementing agent, and split it when it is too big. Load before dispatch: "is this story ready", "tighten this story", "score this spec", "score this story", "this is too big, split it", "decompose this work", "can an agent take this as-is". Covers the six-dimension 0/1/2 readiness rubric, the dispatch-at-10 bar, and the structured story decomposition (SSD) rule for cutting an oversized story along file-ownership and dependency seams.
---

# story-tighten: score and decompose a story before handoff

A vague story does not fail loudly — it burns the implementing agent's budget on exploration. The dominant input cost of an implementing-agent session is the agent reading the codebase to reconstruct what the story left unsaid. Every dimension the spec answers directly is exploration the agent does not have to do. Score the story before dispatch, tighten what scores low, and split what is too big for one slice.

## The rubric — six dimensions, 0/1/2 each

Score each dimension: 2 solid, 1 partial, 0 absent. Maximum 12. Score against the reader who will actually execute the story — an agent with no prior context on this codebase. A dimension earns a 2 only if that reader could act on it without asking a question; if you find yourself supplying the missing piece from your own head as you score, that dimension is a 1 at best.

| # | Dimension | Solid (2) | Partial (1) | Absent (0) |
|---|---|---|---|---|
| 1 | **Problem clarity — grounded in real code** | The problem is concrete and points at the actual code — files, functions, or symbols named; the current behavior and why it is wrong are visible | The problem is described but the code anchor is partial — some files named, the rest left to find | Abstract ("improve the parser"); the agent must reverse-engineer what is broken |
| 2 | **Scope boundedness — non-goals stated** | An explicit non-goals / out-of-scope section names what the slice must not touch | Some boundaries stated, others implied | Silent on boundaries; the agent can widen scope opportunistically |
| 3 | **Acceptance criteria — mechanical and anti-weakening** | Each criterion is one observable check — a named test, an assertion, a command — and the set forbids weakening (no deleted tests, no new suppressions, no coverage drop) | A mix of observable and vague criteria; anti-weakening unstated | "Should work"; the agent invents what counts as done |
| 4 | **Dependencies and sequencing — named** | Predecessors and landing order are named; the slice states what must already exist | Some dependencies named, sequencing left implicit | Silent on order; a missing predecessor surfaces mid-flight |
| 5 | **Sensitive files / blast radius — identified** | The files the slice touches are listed, and any sensitive or shared-hot path is flagged | The main files named, the blast radius unstated | No file list; the blast radius is invisible until the agent is editing |
| 6 | **Size — single-slice-able** | One reviewable, independently landable slice | Borderline — plausibly one slice, plausibly two | Clearly several slices bundled; decompose first (see SSD below) |

## The dispatch line — 10 or above

A story scoring **10+** of 12 is dispatch-ready: an agent can execute it with minimal exploration. Below 10, tighten it first. The bar is 10 rather than 12 to allow one soft dimension — a story can carry a single 1 and still hand off cleanly — but no dimension may sit at 0, since a 0 anywhere is a gap the agent will fill by guessing. The trade is deliberate — 10 to 30 minutes of authoring against a much larger agent-token cost, and it favors tightening for any story that will run more than once or whose cost counts against a usage cap.

## How to use it

1. Score all six dimensions.
2. If the total is below 10, list every dimension that scored 0 or 1.
3. Patch the spec to answer each weak dimension — name the files, add the non-goals section, make each acceptance criterion a runnable check.
4. Re-score. Dispatch at 10+.

A 0 on dimension 6 is not a tightening job — it is a decomposition job. Go to SSD.

### A scored example

A story reads: "Speed up report generation. Make sure the tests pass." Score it — problem clarity 1 (a symptom, no code anchor), non-goals 0, acceptance criteria 0 ("tests pass" names nothing), dependencies 0, sensitive files 0, size 1. Total 2 — vague, and an agent would read most of the report subsystem to guess the rest.

Tighten it: name the function (`buildMonthlyReport` in `report/render.*`), state the non-goal (the query layer is out of scope), make the criterion mechanical ("the existing `render` suite stays green and adds a case asserting a single pass over the row set; no test deleted, no suppression added"), name the predecessor (the row-batching slice must land first), list the touched files, and confirm it is one slice. Re-score: 12. Now dispatch.

## SSD — structured story decomposition

When a story is too big for one slice, split it. **Split along file-ownership and dependency seams, never along conceptual or feature boundaries.**

The reason is mechanical, not stylistic. Cutting a story by feature — "the read path" and "the write path", say — tends to produce children that all edit the same modules. They collide on those files and cannot land independently; the split buys nothing but the illusion of smaller stories. Cutting along file-ownership and dependency seams produces children that own disjoint files and can land in any order — real, independent slices. A shared-hot-file seam is a real seam, but it does not parallelize: it serializes into a predecessor-first chain, so the payoff there is review and revert granularity, not throughput.

**Each child must independently score 10+ on the rubric above.** A decomposition that yields a child scoring 8 has not finished — it has moved the vagueness, not removed it. Score every child before filing any of them.

Peel off a slice on its own even when the bulk stays together if it is premature (its consumer is a not-yet-built sibling), optional (an optimization), a different risk class, or sensitive.

Validate the set before filing. Build a file-touch matrix — child down one axis, file across the other — and confirm no file is written by two children that are meant to land in parallel; where two children share a file, they are a predecessor-first chain, not independent slices, and the story should say so. Check the sensitive footprint of each child, then score each child on the six dimensions. A set is ready only when every child clears 10 and the matrix shows the seams are real.

The most common miss is dimension 3 dressed up: acceptance criteria that read as checks but name none — "the report renders correctly", "behavior is preserved". Those are a 1, not a 2. A criterion is a 2 only when a machine, not a reader's judgment, can decide whether it holds.

## Cross-refs

- `story-write` — authoring the story the rubric then scores.
- `story-intake` — where a filed story is triaged; a sub-10 story is bounced back here to tighten.
- `ledger-preregister` — dimension 3's acceptance criteria are the same dischargeable-by-a-named-check clauses a pre-registered claim commits to; write them once.

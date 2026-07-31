---
name: story-write
description: >-
  Write a work story before building it. Load when drafting a story, spec, or ticket for a piece of work: "write a story for X", "spec this work", "draft the acceptance criteria for this task", "turn this into a ticket", "draft a spec for this bug". Covers the portable frontmatter and six body sections of the story template, verifying the problem against HEAD at file:line, and carrying the anti-weakening contract verbatim in the acceptance criteria.
---

# story-write: the spec before the build

A story is a promise you can be held to. Write the problem where the code actually is, and the acceptance where a check can reach it, or the promise is one no reviewer can hold you to.

## Is this a story yet?

A piece of work earns a story when its "done" is contestable — someone could disagree that it is finished — and it is large enough to outlive one sitting. Turning a raw request into that decision is `story-intake`; this skill assumes intake has said yes and picks up at the blank template (`harness/templates/story-template.md`).

## The frontmatter is portable

Fill the frontmatter and nothing beyond it — the fields travel with the story to any tracker, so keep them tool-neutral.

- `id` — a stable slug, assigned once and never reused.
- `title` — one imperative line, naming the change and not the symptom.
- `deps` — the story ids this one is blocked by; empty is a valid answer, and the honest one when nothing blocks.
- `labels` — flat classifying tags (area, kind), no tracker syntax.
- `sensitive_files` — paths whose change demands extra review (auth, money, the gate, a fail-closed core); listing them here routes review off the story, not off a diff discovered after the fact.
- `status` — `draft` or `ready`; a story starts `draft` and turns `ready` only once every section below survives `story-tighten`.

No chain-coupled fields. A portable story carries no bead id, no queue name, no runtime handle — those belong to whatever files it, never to the spec.

## The six body sections

The template's body is six sections, each answering one question a reader would otherwise ask in review.

1. **Context** — why this work, and the parent it serves (the ADR or build-plan item). One paragraph; link, do not re-argue.
2. **Problem** — the concrete gap in the code today, cited at `path:line` (next section).
3. **Approach** — the intended change, sliced small enough that each slice is a red-first commit.
4. **Acceptance criteria** — the conditions that make it done, carrying the anti-weakening contract verbatim (below).
5. **Test plan** — how each criterion is discharged, and which test goes red first.
6. **Out of scope** — the explicit non-goals, so the story cannot be read wider than it earned.

## Verify the problem against HEAD

The problem statement points at real code, not an abstraction. Before writing it, grep or read HEAD, find the lines the work concerns, and cite them `path:line` — for example, "the fallback in `src/foo/parser.ext:214` returns a default on a parse error, which the caller then signs as success." A problem described in the abstract ("error handling is weak") survives any diff and proves nothing; a problem pinned to lines is one a reviewer can open and a fix can close. If the cited lines have moved by the time work starts, the story is stale — re-ground it before it goes `ready`.

## Acceptance criteria carry the anti-weakening contract

A story's acceptance criteria are settled BEFORE any code, one line each. Write each so a named check discharges it, not a reader's judgment: name the check and point at the artifact, never "it works."

Every acceptance section carries the anti-weakening contract verbatim, alongside its work-specific criteria:

- the assertion count is not reduced versus the merge-base,
- no new suppressions are introduced versus the merge-base,
- no new skipped tests are introduced versus the merge-base.

These three are not the story's novelty — they are the floor under it, the differential gate's baseline stated in the story so the work cannot be closed by weakening the checks that would catch it. Copy them verbatim into every story; the work-specific criteria sit above them.

## A detector story declares its red

When the story ships a detector — a gate, a check, a fail-closed guard, a tamper proof, or any mechanism whose job is to make one outcome differ from another — the test plan promises more than a green suite. It names the input where the outcome differs with the mechanism versus without it, and it commits to an observed-red proof for that test: the mechanism's guard test is watched failing before the guard exists. Never-red is not an option for a detector, because a guard that was never seen to fire is a guard no one has shown fires. State the obligation in the story so the build cannot skip it.

## After the draft

A draft is not `ready`. `story-tighten` is the sharpening pass — it splits a story too large for one red-first slice, cuts an acceptance line no check can reach, and re-grounds a stale `path:line`. When the story turns on a decision chosen among alternatives, that decision is an ADR and not a story section: write it with `adr-write` and have the story cite it. Once the story is `ready`, its acceptance criteria are the standing obligations the build loop works against.

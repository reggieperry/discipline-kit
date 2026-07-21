---
description: Drive a story through the five-phase ledger-gated chain (planner, worker, tester, reviewer, finalizer), advancing only on ledger state. The finalizer parks for your merge — the chain never merges.
argument-hint: <story-file-path | "raw feature request in prose">
---

# /chain — the ledger-gated build chain (parent-session driver)

You are the DRIVER. You run in the parent session and orchestrate five subagents, but you advance ONLY on ledger and git state you re-derive yourself — never on a subagent's prose. Every halt fails closed. Run every postcondition check and the audit from the harness path (`ledger/`), never from a branch-editable copy — a branch under review must not weaken the grader that checks it.

The driver holds no judgment of its own: it sequences phases, re-derives predicates, and routes failures. The five phases and the operator are the only minds. (This is the parent-session tier. A Dynamic-Workflow tier is a deferred, separately-verified upgrade; the workflow script cannot run these shell predicates itself, so the parent session runs them here.)

Argument: `$ARGUMENTS` — a story file path, or a raw feature request in prose.

## 0. Entry — reach a `ready` story plus the operator's go
- **Raw feature request** → run `story-write`, then `story-tighten`. A story scoring below the ready bar goes BACK to the operator with the rubric gaps as questions — the chain does not launch on a loose spec.
- **Story path** → run `story-intake` (same bar).
- Launch receipt: the story at `ready` AND the operator's explicit go. Create the chain branch. Do not proceed without both.

## The driver law
After each phase, RE-DERIVE its postcondition from `ledger/claims.jsonl` (via `ledger/board.sh`) and git (`git diff`, `git log`, `git show --stat`) — not from what the subagent told you. A failed postcondition is not an error message; it is a **parked claim naming exactly what is missing**, so an abandoned chain stays legible on the board weeks later. Then route:

- **Postcondition failed (the phase produced wrong output)** → compose a correction brief containing ONLY the failed predicate plus the verbatim receipts (no interpretation of your own), re-invoke the SAME phase fresh, up to `chain.max_retries` (default 2). Log every attempt as testimony.
- **A phase self-parked (exhaustion, blocked-on-decision, or a judgment item)** → surface that parked claim to the operator and do NOT retry it — exhaustion is not a redo. Read the board for a parked claim from the phase BEFORE applying the retry ladder.
- **A blocking refutation from review** → worker loop-back: re-invoke `chain-worker` for the fix, then `chain-tester` re-attests, then review again. This is not a retry. If the refutation cannot be discharged, HALT with the contest visible on the board.
- Budget one operator question per phase run.

## The five phases (invoke each subagent fresh, by name)
1. **chain-planner** → postcondition (`postcondition.py planner-parked <story-id>`, exit 2 halts): parked `unverified` claims exist for the story, one per acceptance criterion, each under a NON-runnable check (halt on a runnable-check park — else a criterion gets "signed" at plan time by a generic suite that never tested it); also confirm the park commit touches only `ledger/` (`git show --stat`).
2. **chain-worker** → postcondition: every parked claim `signed` or parked-with-reason; a `red-proof` receipt on the board for each detector-class slice; the worker's commits touch NO trusted-base path (the build-time judge carve-out — a worker with Write+Bash could otherwise disable the gate that signs it). Enforce this MECHANICALLY, not by reading the worker's report: run `trusted-base-touched.sh <phase-start-sha>` (the fence predicate over the `trusted-base` list — the gate, hooks, `.github/`, `.claude/`, and `CLAUDE.md`); a non-zero exit names the touched path and halts the chain closed. It scans every commit in the range (not just endpoints, so touch-then-revert is caught) and the working tree, and fails closed on a bad base or an empty list. **Provenance:** for the mechanical guarantee, invoke a PRISTINE copy of the predicate and pass a pristine `trusted-base` list from outside the branch — a phase that rewrote its own in-tree `.claude/chain/` copy would weaken the fence that grades it. Running the in-tree copy unguarded makes the fence only as strong as the human who reviews the PR — acceptable for the base tier (the human merge IS the backstop), not for auto-merge (which needs the pinned copy, same as the differential gate). The list is the base tier; the auto-merge tier extends it to the check-definition + build config, where a green check is the merge warrant.
3. **chain-tester** → postcondition: an attestation testimony exists `about` the story's claims AND — checked by YOU from the harness path via `postcondition.py tester-clean <tester-phase-base>` (exit 2 halts) — `git diff` against the worker's head is empty outside test paths; additionally require any test-path change to be purely additive (new tests/assertions only, no edit to an existing assertion line — a count-based check misses in-place semantic weakening). A tester that touched production or weakened a grader cannot hand off.
4. **chain-reviewer** — first choose the tier: baseline `pr-review`; escalate to the two adversarial roles when the story is detector-class or lists `sensitive_files`, **re-derived from the story frontmatter, never the planner's plan note**; for an auto-merge candidate, force the full committee unconditionally. Invoke ONCE PER ROLE, fresh context (logic-and-state, then abuse-and-boundaries). Postcondition: a review entry exists per role, citing the actual changed files, AND no blocking refutation stands open (`postcondition.py no-open-refutation <story-id>`, exit 2 halts). A blocking refutation routes to the worker loop-back above; ledger-state gating verifies the entry's SHAPE and receipts, not the review's soundness — the operator's merge remains the substantive check.
5. **chain-finalizer** → postcondition: PR created with head at the reviewed sha; done-report filed; story archived merge-pending; closing claim parked "awaiting operator merge, PR #N"; **the PR is UNMERGED** — `gh pr view <N> --json state,mergedAt` shows OPEN and null `mergedAt`, halt closed if merged. "The finalizer does not merge" is this re-derived postcondition, not the finalizer's word.

## Terminal state
The chain ends at **PR created + closing claim parked**, awaiting YOUR merge. When you merge, run the merge-close reconcile (`/chain --reconcile <PR#>`, a later slice) to close the parked closing-claim and backfill the archive's `merged_pr` and `closed_at`. Until then the parked closing-claim is the chain's honest "done pending your merge" — not an abandoned dangling entry.

## Config (recorded in the Options configuration claim)
- `chain.max_retries` (default 2) — postcondition-failure retries per phase.
- `chain.autonomous_merge` (default off) — the finalizer parks for operator merge. Do not enable without the full protected-paths fence in `chain-finalizer`; merge authority is an operator act, not a reviewer's silence.

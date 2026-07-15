---
name: ledger-retire
description: >-
  Supersession and the librarian, safely. Load when correcting, updating, or replacing a claim, or tidying the board: "that claim is now wrong", "update the finding", "clean up the ledger", "retire the old one", "run the librarian", "--sweep". Covers supersede-never-edit (including our own beliefs), why signed is terminal, and the verbatim-move-plus-sidecar retirement that is immutability-safe in any later commit.
---

# ledger-retire: supersession and the librarian, safely

The record is append-only. You do not fix a claim; you supersede it, and the old line stays exactly as written.

## Supersede, never edit, including your own beliefs

A changed belief is a new entry whose `supersedes` names the old one, not an edit to the old one. This holds for our own findings too. On the founding project, when the M3 press observation evolved it was not rewritten; it was left standing with its discharger named forward into the next cell (clm-0122). Editing a line to match new understanding erases the fact that the understanding changed.

When the successor is also *about* the predecessor — a testimony refining it, a refutation defeating it — it carries **both** pointers: `supersedes` (the replacement edge) and `about` (the concerns edge), so tooling can walk either relation. (The write-side statement is in `ledger-write`.)

## Signed is terminal

The audit's legal-transition table admits no exit from `signed`: `LEGAL_NEXT` maps a signed claim to the empty set, so a signed claim is never superseded in place. If a signed result later proves premature but not wrong, you neither rewrite it nor supersede it: a fuller restatement is a new, independent claim, and the original signed line stays on the board. A signed claim is defeated only by a `refutation` about it and then retired, never edited.

## Retire is verbatim-move plus sidecar — safe in any later commit

Retiring moves a defeated or superseded claim off the live board into `ledger/trace/<id>.jsonl`, which receives the original claim line **byte-identical** plus a separate retirement record (`retire_of` / `trace_reason` / `retired_by`). Because the committed line is preserved unchanged, the immutability check is satisfied even when the claim was first committed in an *earlier* commit — so a claim may be retired safely in **any later commit**, and a late sweep at a landing is now legal. This lifted the same-commit-only constraint the older rewrite-in-place mechanics forced (see the changelog and `harness/ledger/README.md`, both current).

    ledger/librarian            # report superseded-but-live and contested claims
    ledger/librarian --sweep    # retire every superseded-but-live claim (a dedicated cleanup, any commit)

`--sweep` retires the *whole* superseded-but-live backlog, so run it deliberately as its own cleanup pass rather than bolting it onto a landing where its scope surprises you.

## The scar, verbatim

On the founding project, at a milestone landing, `ledger/librarian --sweep` was run to retire a just-superseded claim (clm-0128). It over-reached. `--sweep` retires every superseded-but-live claim across the whole board, so it also tried to retire long-committed predecessors (clm-0121, clm-0125, and a tail) whose supersession had been committed in earlier commits. Moving those long-committed lines to trace in this commit is a late retirement, and `audit.py` flagged roughly twenty `[immutable] … edited or lost` violations. The fix was to revert (`git checkout ledger/claims.jsonl` and `git clean -f ledger/trace/`), re-run the audit clean, and land append-only: the superseding clm-0133 was appended, and clm-0128 was left live-but-superseded. This incident motivated the v1.1.0 fix (verbatim-move plus sidecar); the constraint it taught — retire only in the same commit — no longer binds, and a late sweep at a landing is now safe. The durable lesson is narrower: `--sweep` retires the *whole* superseded-but-live backlog, so run it deliberately as its own cleanup pass, not bolted onto a landing where its scope is a surprise.

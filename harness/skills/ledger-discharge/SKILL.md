---
name: ledger-discharge
description: >-
  Cite a signature instead of re-earning it, and land through the gate. Load when about to establish or land a result, or when finishing and shipping work: "don't re-run that check, we already signed it", "cite the signed claim to skip verification", "land this milestone", "commit and push this milestone", "will the gate sign this commit", "sign it off", "close out the cell". Covers finding and citing an existing signed claim instead of re-running its check, plus the landing mechanics: how the gate signs, the supersession-signing pattern, and the pushed line.
---

# ledger-discharge: cite before re-checking, and how signing actually works

Verification cost falls toward zero when signatures are spent instead of re-earned. Before you verify anything, check whether the ledger already holds it.

## Cite first

    ledger/board.sh find <fact>

- Already `signed`? Cite the `clm-NNNN` and move on. Do not re-run the check; the signature is the receipt.
- Not there, and the fact will be needed twice? Mint the claim now (`ledger-write`) so the next instance can cite it instead of re-deriving it.
- Not there, needed once? Do the work; not everything earns a line.

## How the gate actually signs

Signing is not something you write. It is something the commit-path gate does, and only the gate.

1. A landing commit stages code, or a pending unverified claim names a runnable check. The gate runs the repo's mechanical check: `ledger/check.sh` (or, absent that file, the toolchain the gate auto-detects), which must cover every language that builds the system.
2. On failure the gate appends a `refuted` entry and blocks the commit. Approving review testimony never signs; a green reviewer with a red check still means the commit is blocked.
3. On pass the gate signs. At post-commit it appends a `signed` entry carrying the commit sha and the run reference, and records the entry's line-hash so the forgery guard admits it next time.

## The supersession-signing pattern

A claim parked under a non-runnable check (`ledger-preregister`) lands by superseding it to the real check and letting the gate sign:

    # append the successor that points the parked claim at the real check
    echo '{"claim":"<same claim, verbatim>","subject":"<cell>","source":"claude-code","kind":"assertion","status":"unverified","check":"repo-check","supersedes":"<parked-id>"}' | ledger/append
    # then commit; the gate runs repo-check and, on green, appends the signed successor

The chain is parked, superseded to `repo-check`, then gate-signed (clm-0128 → clm-0133 → clm-0135).

## The semantics line

Every discharge states what its signature actually certifies. A mechanical check passing certifies *this receipt reproduces* or *these two legs agree* — not that the underlying work is correct; correctness beyond the check rests on whatever independent leg the claim names (a second-language recount, an adversarial review, a hand-verified oracle). The claim carries one clause saying so, and pointing at that leg. A signature read wider than the check earned is the forgery the whole discipline exists to prevent — committed politely, in prose, instead of in a `status` field. Where the discharge compares receipts across two implementations, the comparability policy belongs in that clause too: integer receipts byte-identical; float receipts under a pinned rounding mode or a stated tolerance.

## The pushed line

A milestone that has not left the machine is drafted, not done. The done-report carries `pushed: <remote>@<sha>`, the remote and short sha you pushed to (`git remote -v`). Land, let the gate sign, push, and record the line.

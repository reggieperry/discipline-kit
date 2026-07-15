---
name: ledger-board
description: >-
  Read the board before you write to it. Load at the start of a work session in a repo running the dev-ledger harness, and whenever you're about to scope or start a piece of work whose "done" is contestable (a research question, milestone, cell, experiment, or build-vs-not decision), or when asking "what's open", "where were we", "has this come up before", "should we build X", "is this new". Runs ledger/board.sh to show the open claims, the do-not-rebuild graveyard, and every prior claim on a topic, so a settled or refuted question is cited rather than re-litigated.
---

# ledger-board: read before writing

The ledger is four instruments at once: a memory that outlives the instance, a to-do list (the unverified column), a bank of certainty (signed claims you cite instead of re-earning), and a court of precedent (refutations nobody should re-walk). Read it before you design anything.

## Do this first

From the repo root:

    ledger/board.sh open              # the research program at a glance: what is still unverified
    ledger/board.sh find <topic>      # every prior claim on the topic, any status, live and trace

If the topic has history, the history decides.

- **A prior refutation ends the design conversation.** When `find` surfaces a claim whose framing was refuted, do not re-propose it. Cite the entry, or state explicitly what is different this time. `ledger/board.sh graveyard` is the standing do-not-rebuild list.
- **A prior signed claim gets cited, not re-verified.** When the fact you were about to establish is already `signed`, cite its `clm-NNNN` and spend the saved effort elsewhere. Re-earning a signature you already hold is waste.
- **A stale open claim is a live question.** `ledger/board.sh stale` lists unverified claims older than thirty days, beliefs the program carries without having examined them.

## The scar

The founding project's capacity conjecture. A committee had already refuted the "pure capacity ceiling" framing (clm-0026, its refuting verdict recorded at clm-0027; only the arithmetic survived, signed later at clm-0047). When the framing resurfaced, `ledger/board.sh find capacity` produced the corpse in two seconds and stopped a re-derivation cold, against the days it would have cost to rebuild and re-refute it. That is the whole return on reading first: grep is cheap, and rebuilding a refuted idea is not.

## Notes

- `board.sh` is read-only by design; it never writes. Minting is the `ledger-write` skill, signing is the gate (`ledger-discharge`), retiring is `ledger-retire`.
- `find` searches the live board and `ledger/trace/`, so a superseded or defeated line is still found.
- `board.sh --selftest` proves the views against a committed fixture; run it if the output ever looks wrong.

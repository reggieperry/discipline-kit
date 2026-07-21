#!/usr/bin/env python3
"""Property (law) tests for the dev-ledger calculus — the Python analog of the Scala LedgerLawsSuite.

The Scala claim-calculus is held to LAWS (checkAll / discipline RuleSets): determinacy, confluence,
non-fabrication. The Python dev-ledger calculus (ledger/model.py) carries the same operations —
`resolved_ids` (the supersession fold), `superseded_ids`, `mentions` — and must be held to the
analogous invariants, or a future edit could silently make the gate, the audit, and the chain read the
ledger differently. Example-based fixtures pin known cases; these pin the laws over MANY generated
ledgers.

Generation is SEEDED (deterministic, reproducible — the kit's determinism discipline), mirroring how
ScalaCheck drives the Scala laws.

Run: python3 harness/ledger/fixtures/model_laws_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # harness/ledger — the model under test
import model  # noqa: E402

SEED = 20260721   # fixed: reproducible, and varies the corpus without wall-clock nondeterminism
CASES = 400
STATUSES = ("unverified", "signed", "refuted", "retired")
KINDS = ("assertion", "testimony", "refutation")


def gen_ledger(rng: random.Random) -> list[dict]:
    """A random but well-formed-enough ledger: unique ids in order, each entry optionally superseding
    or about-ing an EARLIER id (as the append-only discipline requires — a successor follows what it
    supersedes)."""
    n = rng.randint(0, 14)
    ents: list[dict] = []
    for i in range(n):
        eid = f"clm-{i}"
        e = {"id": eid, "status": rng.choice(STATUSES), "kind": rng.choice(KINDS),
             "subject": rng.choice(["s1", "s2", "story-x"]), "claim": f"claim {i} about story-x"}
        if i > 0 and rng.random() < 0.5:
            e["supersedes"] = f"clm-{rng.randint(0, i - 1)}"
        if i > 0 and rng.random() < 0.3:
            e["about"] = f"clm-{rng.randint(0, i - 1)}"
        if rng.random() < 0.05:
            e["check"] = rng.choice(list(model.RUNNABLE) + ["some-selftest", "none"])
        ents.append(e)
    return ents


def check(cond: bool, law: str, ents: list[dict]) -> None:
    if not cond:
        raise AssertionError(f"LAW VIOLATED: {law}\n  ledger={ents}")


def main() -> int:
    rng = random.Random(SEED)
    for _ in range(CASES):
        ents = gen_ledger(rng)
        ids = {e["id"] for e in ents}
        resolved = model.resolved_ids(ents)
        superseded = model.superseded_ids(ents)
        signed = {e["id"] for e in ents if e.get("status") == "signed"}

        # L1 — DETERMINACY / order-independence (confluence): resolved_ids depends on the SET of
        # entries, not their order. Shuffle and re-fold; the result must be identical.
        shuffled = ents[:]
        rng.shuffle(shuffled)
        check(model.resolved_ids(shuffled) == resolved, "resolved_ids is order-independent", ents)

        # L2 — SIGNED ⊆ RESOLVED: a signed entry has, by definition, made it through the gate.
        check(signed <= resolved, "every signed id is resolved", ents)

        # L3 — NON-FABRICATION (soundness): no id is resolved without a signature root. Every resolved
        # X is either signed, or superseded by SOME entry that is itself resolved (checked over ALL
        # superseders — not a lossy target→superseder map, which is the very bug L1 guards against).
        # Nothing appears from nowhere — the analog of the Scala non-fabrication theorem.
        for x in resolved:
            grounded = x in signed or any(
                e.get("supersedes") == x and e["id"] in resolved for e in ents)
            check(grounded, f"resolved id {x} traces to a signature (no fabrication)", ents)

        # L4 — CLOSURE / completeness (fixpoint): the fold reaches everything it should. If a resolved
        # entry supersedes Y, then Y is resolved too — running the closure again adds nothing.
        for e in ents:
            if e["id"] in resolved and e.get("supersedes"):
                check(e["supersedes"] in resolved,
                      "a claim superseded by a resolved entry is resolved (closure)", ents)

        # L5 — resolved_ids ⊆ ids: it never invents ids not in the ledger.
        check(resolved <= ids, "resolved_ids stays within the ledger's ids", ents)

        # L6 — MONOTONICITY: appending a fresh signed entry only GROWS the resolved set (adding
        # evidence never un-resolves — the ledger is append-only and confirmations accumulate).
        grown = ents + [{"id": "clm-new", "status": "signed", "kind": "assertion",
                         "subject": "s1", "claim": "fresh"}]
        check(resolved <= model.resolved_ids(grown), "resolved_ids is monotone under a new signature", ents)

        # L7 — superseded_ids is EXACTLY the supersedes-targets present.
        check(superseded == {e["supersedes"] for e in ents if e.get("supersedes")},
              "superseded_ids = the set of supersedes-targets", ents)

        # L8 — mentions: an entry names its own subject and its own claim text.
        for e in ents:
            check(model.mentions(e, e["subject"]) and model.mentions(e, "story-x"),
                  "mentions finds the entry's own subject/claim", ents)

    # --- the closed operation algebra (static invariants, no generation needed) ---
    # A1 — the status-transition relation is CLOSED over the status vocabulary: every key and every
    # target is a valid Status. A transition to a word outside STATUSES would be an unrepresentable
    # operation leaking in.
    for pre, nexts in model.LEGAL_NEXT.items():
        assert pre in model.STATUSES, f"LEGAL_NEXT key {pre!r} is not a valid status"
        assert set(nexts) <= model.STATUSES, f"LEGAL_NEXT[{pre!r}] escapes the status vocabulary: {nexts}"
    # A2 — every status HAS a transition rule (the relation is total over the vocabulary).
    assert set(model.LEGAL_NEXT) == set(model.STATUSES), \
        "LEGAL_NEXT must cover every status (a status with no rule is an undefined operation)"
    # A3 — `signed` is TERMINAL: a signed claim is never superseded in place (defeat = refutation about
    # it + retirement). This is the one place the dev-ledger diverges from a research ledger.
    assert model.LEGAL_NEXT["signed"] == frozenset(), "signed must be terminal (no in-place successor)"
    assert model.LEGAL_NEXT["retired"] == frozenset(), "retired must be terminal"
    # A4 — the vocabularies are non-empty closed sets, and RUNNABLE ∩ GENERATIVE is empty (a check
    # cannot be both signable and non-mechanical — that overlap would let a generative 'check' sign).
    for name, s in (("KINDS", model.KINDS), ("STATUSES", model.STATUSES),
                    ("SOURCES", model.SOURCES), ("RUNNABLE", model.RUNNABLE)):
        assert isinstance(s, frozenset) and s, f"{name} must be a non-empty frozenset"
    assert model.RUNNABLE.isdisjoint(model.GENERATIVE), \
        "a runnable (signable) check must never also be generative (non-mechanical)"

    print(f"model_laws_test: PASS ({CASES} generated ledgers, seed {SEED} — determinacy, signed⊆resolved, "
          "non-fabrication, closure, monotonicity, superseded, mentions; + the closed transition algebra: "
          "LEGAL_NEXT total & closed over STATUSES, signed/retired terminal, runnable∩generative=∅)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

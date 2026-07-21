#!/usr/bin/env python3
"""model.py — the dev-ledger's claim-calculus, in one place.

The dev-ledger is an append-only log of graded claims; reading it back — what is signable, what a
supersession chain resolves to, whether a refutation still stands — is a small calculus, and it was
being re-derived independently in gate.py (pending_runnable), audit.py (chains), and the chain's
postcondition.py (resolved_ids), with three copies of the RUNNABLE set. This module owns those
operations so the gate, the audit, and the chain predicates all read the ledger the SAME way — a
correctness property, not only DRY: a divergence between two of those views is a way for the chain to
advance on a belief state the gate does not hold.

This is a SEPARATE instance from the reasoning system's own claim-algebra calculus (the Scala
`claimalgebra.calculus`: BelnapReader / Ledger / Resolution) — same shape, disjoint subject (a repo's
development vs. the object under study) and language. It mirrors those concepts; it does not fold into
them.
"""
from __future__ import annotations

import json
from pathlib import Path

# The checks the commit-path gate can actually run and therefore sign against. A claim parked under a
# name OUTSIDE this set is a pre-registered obligation the gate will not auto-discharge.
RUNNABLE = {"repo-check", "scala-check", "scala-suite", "typecheck"}

# The four-word status vocabulary of the ledger.
STATUSES = {"unverified", "signed", "refuted", "retired"}


def load(path) -> list[dict]:
    """Parse a claims.jsonl into a list of entries, skipping blank and malformed lines (a hostile or
    truncated line must not crash a reader — it is simply not a claim we can reason about)."""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def is_signed(e: dict) -> bool:
    return e.get("status") == "signed"


def is_runnable(e: dict) -> bool:
    return e.get("check") in RUNNABLE


def superseded_ids(ents: list[dict]) -> set[str]:
    """The set of ids that some entry supersedes — i.e. claims replaced by a successor. The gate
    excludes these from its pending-to-sign set (a superseded claim's original line stays on the
    ledger by the immutability discipline, but must not re-trigger the check or be re-signed)."""
    return {e["supersedes"] for e in ents if e.get("supersedes")}


def resolved_ids(ents: list[dict]) -> set[str]:
    """Ids that have 'made it through the gate': every signed entry, plus every claim transitively
    superseded toward a signed one. The worker loop-back re-registers a fix (parked, runnable check),
    the gate signs a successor that SUPERSEDES the parked fix, and that fix may itself supersede the
    original claim — so a signature can be several supersession hops from what it ultimately resolves.
    Following that chain is what lets a refutation's disposal be recognized.

    A claim is resolved if ANY entry that supersedes it is resolved — NOT via a target→superseder map,
    which would silently drop all but one superseder of the same claim and make the result depend on
    iteration order (a monotone closure must not). The fixpoint below is order-independent by
    construction."""
    resolved = {e["id"] for e in ents if is_signed(e) and e.get("id")}
    changed = True
    while changed:
        changed = False
        for e in ents:
            sup = e.get("supersedes")
            # e supersedes `sup`; if the successor e is resolved, the claim it replaced is resolved too
            if sup and e.get("id") in resolved and sup not in resolved:
                resolved.add(sup)
                changed = True
    return resolved


def mentions(e: dict, needle: str) -> bool:
    """Whether an entry's subject or claim text names `needle` (e.g. a story id) — the ledger schema
    has no dedicated cross-reference field, so ids ride in the text by convention."""
    return needle in (str(e.get("subject", "")) + " " + str(e.get("claim", "")))

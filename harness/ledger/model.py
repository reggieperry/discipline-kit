#!/usr/bin/env python3
"""model.py — the dev-ledger's claim-calculus and typed vocabulary, in one place.

The dev-ledger is an append-only log of graded claims; reading it back — what is signable, what a
supersession chain resolves to, whether a refutation still stands — is a small calculus, and it was
being re-derived independently in gate.py (pending_runnable), audit.py (chains), and the chain's
postcondition.py (resolved_ids), with the closed vocabularies scattered. This module owns those
operations AND the closed vocabularies (the kinds, statuses, sources, runnable checks, and the legal
status-transition relation) so the gate, the audit, and the chain read the ledger the SAME way — a
correctness property, not only DRY: a divergence between two of those views is a way for the chain to
advance on a belief state the gate does not hold.

The vocabularies are typed as `Literal`s and the operations are annotated so `mypy` carries the
consistency the way a compiler would in a typed FP language — the Python stand-in for making illegal
states unrepresentable: the closed set is defined ONCE, and a field that strays outside it is a type
error (statically, under mypy) and a law violation (dynamically, under model_laws_test).

A SEPARATE instance from the reasoning system's own claim-algebra calculus (the Scala
`claimalgebra.calculus`: BelnapReader / Ledger / Resolution) — same shape, disjoint subject (a repo's
development vs. the object under study) and language. It mirrors those concepts; it does not fold in.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypedDict, Union, cast

# --- the closed vocabularies (the ledger's algebra of legal values) ---------------------------------

Kind = Literal["assertion", "testimony", "refutation"]
Status = Literal["unverified", "signed", "refuted", "retired"]
Source = Literal["claude-code", "subagent", "human", "hook"]

KINDS: frozenset[str] = frozenset(("assertion", "testimony", "refutation"))
STATUSES: frozenset[str] = frozenset(("unverified", "signed", "refuted", "retired"))
SOURCES: frozenset[str] = frozenset(("claude-code", "subagent", "human", "hook"))

# The checks the commit-path gate can actually run and therefore sign against. A claim parked under a
# name OUTSIDE this set is a pre-registered obligation the gate will not auto-discharge.
RUNNABLE: frozenset[str] = frozenset(("repo-check", "scala-check", "scala-suite", "typecheck"))

# discharged_by.check values that are NOT a mechanical check — a signed entry naming one is a forgery.
GENERATIVE: frozenset[str] = frozenset(
    ("none", "pr-review", "deep-reason", "testimony", "workflow-verify", "claude-code", "subagent"))

# The legal status-transition relation: the statuses a SUCCESSOR entry may carry, keyed by the
# predecessor's status. This is the ledger's closed operation algebra on state — `signed` is terminal
# (a signed claim is never superseded in place; it is defeated only by a refutation about it plus
# retirement), and `refuted`/`retired` stay on the record. Centralized here so the gate and the audit
# share one transition table.
LEGAL_NEXT: dict[str, frozenset[str]] = {
    "unverified": frozenset(("signed", "refuted", "unverified")),
    "signed": frozenset(),
    "refuted": frozenset(),
    "retired": frozenset(),
}


class Claim(TypedDict, total=False):
    """A ledger entry. `total=False` because entries are parsed from JSONL and read defensively with
    `.get()` — every field is accessed as possibly-absent, which is exactly the load-and-reason
    contract. The types pin the SHAPE; the closed-vocabulary membership of `kind`/`status`/`source` is
    pinned by the frozensets above and checked by the audit + the property laws."""
    id: str
    ts: str
    subject: str
    claim: str
    source: str
    kind: str
    status: str
    check: str
    about: Union[str, None]
    supersedes: Union[str, None]
    discharged_by: dict
    sha: str
    trace_reason: Union[str, None]
    discharged: Union[str, None]


# --- the operations (the calculus over the log) -----------------------------------------------------

def load(path: Union[str, Path]) -> list[Claim]:
    """Parse a claims.jsonl into entries, skipping blank and malformed lines (a hostile or truncated
    line must not crash a reader — it is simply not a claim we can reason about)."""
    p = Path(path)
    if not p.exists():
        return []
    out: list[Claim] = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            out.append(cast("Claim", parsed))  # a JSON object is a Claim's shape; membership checked elsewhere
    return out


def is_signed(e: Claim) -> bool:
    return e.get("status") == "signed"


def is_runnable(e: Claim) -> bool:
    return e.get("check") in RUNNABLE


def superseded_ids(ents: list[Claim]) -> set[str]:
    """The set of ids that some entry supersedes — i.e. claims replaced by a successor. The gate
    excludes these from its pending-to-sign set (a superseded claim's original line stays on the
    ledger by the immutability discipline, but must not re-trigger the check or be re-signed)."""
    out: set[str] = set()
    for e in ents:
        sup = e.get("supersedes")
        if sup:
            out.add(sup)
    return out


def resolved_ids(ents: list[Claim]) -> set[str]:
    """Ids that have 'made it through the gate': every signed entry, plus every claim transitively
    superseded toward a signed one. The worker loop-back re-registers a fix (parked, runnable check),
    the gate signs a successor that SUPERSEDES the parked fix, and that fix may itself supersede the
    original claim — so a signature can be several supersession hops from what it ultimately resolves.
    Following that chain is what lets a refutation's disposal be recognized.

    A claim is resolved if ANY entry that supersedes it is resolved — NOT via a target→superseder map,
    which would silently drop all but one superseder of the same claim and make the result depend on
    iteration order (a monotone closure must not). The fixpoint below is order-independent by
    construction (pinned by model_laws_test L1)."""
    resolved: set[str] = {e["id"] for e in ents if is_signed(e) and e.get("id")}
    changed = True
    while changed:
        changed = False
        for e in ents:
            sup = e.get("supersedes")
            eid = e.get("id")
            # e supersedes `sup`; if the successor e is resolved, the claim it replaced is resolved too
            if sup and eid in resolved and sup not in resolved:
                resolved.add(sup)
                changed = True
    return resolved


def mentions(e: Claim, needle: str) -> bool:
    """Whether an entry's subject or claim text names `needle` (e.g. a story id) — the ledger schema
    has no dedicated cross-reference field, so ids ride in the text by convention."""
    return needle in (str(e.get("subject", "")) + " " + str(e.get("claim", "")))

#!/usr/bin/env python3
"""Byte-identity gate for the two gate.py copies (§18 whole-branch review, Cluster C).

The kit ships the commit-path gate in two places: the master `harness/ledger/gate.py` (what the
installer copies into an adopter) and the kit's own active `ledger/gate.py` (what governs this repo).
CLAUDE.md's invariant is that they are byte-identical — but nothing MECHANICALLY enforced it, so a
change to one (e.g. a chain phase editing only the fenced-copy or only the master) could silently
poison every future adopter's gate. This check fails if they ever diverge.

Run: python3 harness/ledger/fixtures/gate_copies_identical_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
MASTER = KIT / "harness" / "ledger" / "gate.py"
ACTIVE = KIT / "ledger" / "gate.py"


def diverged(a: bytes, b: bytes) -> bool:
    return a != b


def main() -> int:
    # first prove the comparison logic itself (so a no-op guard can't pass vacuously)
    assert diverged(b"x", b"y") is True, "the divergence check must flag differing bytes"
    assert diverged(b"same", b"same") is False, "the divergence check must pass identical bytes"

    assert MASTER.exists(), f"master gate missing: {MASTER}"
    assert ACTIVE.exists(), f"active gate missing: {ACTIVE}"
    m, a = MASTER.read_bytes(), ACTIVE.read_bytes()
    assert not diverged(m, a), (
        "gate.py copies have DIVERGED — harness/ledger/gate.py != ledger/gate.py. The two must stay "
        "byte-identical (the master is what adopters install; the active copy governs this repo). "
        f"master={len(m)}B active={len(a)}B. `cp harness/ledger/gate.py ledger/gate.py` after any "
        "intended change, and change BOTH in the same commit."
    )
    print("gate_copies_identical_test: PASS (harness/ledger/gate.py == ledger/gate.py, byte-identical)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

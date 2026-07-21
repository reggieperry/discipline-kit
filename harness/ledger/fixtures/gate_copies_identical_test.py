#!/usr/bin/env python3
"""Byte-identity gate for the kit's two-copy ledger tools (§18 whole-branch review, Cluster C).

The kit ships each core ledger tool in two places: the master `harness/ledger/<tool>` (what the
installer copies into an adopter) and the kit's own active `ledger/<tool>` (what governs this repo).
The invariant is that they are byte-identical — but nothing MECHANICALLY enforced it, so a change to
one (a chain phase editing only the fenced copy or only the master, or a hand-refactor that forgets to
sync) could silently poison every future adopter's gate. This fails if any tracked pair diverges.

Covers gate.py (the sole signer), audit.py, and model.py (the shared claim-calculus) — the tools that
carry logic and were most recently refactored across copies.

Run: python3 harness/ledger/fixtures/gate_copies_identical_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
TOOLS = ("gate.py", "audit.py", "model.py")


def diverged(a: bytes, b: bytes) -> bool:
    return a != b


def main() -> int:
    # first prove the comparison logic itself (so a no-op guard can't pass vacuously)
    assert diverged(b"x", b"y") is True, "the divergence check must flag differing bytes"
    assert diverged(b"same", b"same") is False, "the divergence check must pass identical bytes"

    for tool in TOOLS:
        master = KIT / "harness" / "ledger" / tool
        active = KIT / "ledger" / tool
        assert master.exists(), f"master missing: {master}"
        assert active.exists(), f"active missing: {active}"
        m, a = master.read_bytes(), active.read_bytes()
        assert not diverged(m, a), (
            f"{tool} copies have DIVERGED — harness/ledger/{tool} != ledger/{tool}. The two must stay "
            f"byte-identical (the master is what adopters install; the active copy governs this repo). "
            f"master={len(m)}B active={len(a)}B. `cp harness/ledger/{tool} ledger/{tool}` after any "
            "intended change, and change BOTH in the same commit."
        )
    print(f"gate_copies_identical_test: PASS ({', '.join(TOOLS)} — each master==active, byte-identical)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

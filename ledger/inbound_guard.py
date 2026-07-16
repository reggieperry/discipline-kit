#!/usr/bin/env python3
"""inbound_guard.py — reject a signed ledger line arriving through an un-gated commit path.

The forgery guard in gate.py is hook-local: it runs on a commit made on a harnessed machine. A fork
PR, a teammate's un-harnessed laptop, or a fresh machine can add a `"status":"signed"` ledger line
that nothing structurally rejects on the way in. This guard closes that on the inbound side. It reads
a unified diff on stdin and exits 1 if any ADDED line to a ledger `claims.jsonl` (or `trace/`) file is
a signed entry — signatures are minted only by the repo's own gate.

    git diff <base>..<head> -- ledger/ | python3 ledger/inbound_guard.py

Scope note: the companion workflow (harness/templates/inbound-guard.yml) runs this only on FORK PRs,
so the maintainer's own gate-signed PRs are exempt; a fork's added signature can never be trusted, and
the doctrine is that a contributor sends the claim, not the verdict. Exit 0 = clean; 1 = a signed line
was added; 2 = usage error.
"""
from __future__ import annotations

import re
import sys

# A ledger entry is one JSON object per line; a signed one carries "status":"signed".
_SIGNED = re.compile(r'"status"\s*:\s*"signed"')
# The ledger store files this guard watches (added lines elsewhere are not its business).
_LEDGER_FILE = re.compile(r'^\+\+\+ b/(.*ledger/claims\.jsonl|.*ledger/trace/.*\.jsonl)\s*$')


def scan(diff_text: str) -> list[str]:
    """Return the offending added signed lines (empty = clean)."""
    offending: list[str] = []
    in_ledger = False
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            in_ledger = bool(_LEDGER_FILE.match(line))
            continue
        if line.startswith("--- ") or line.startswith("diff --git") or line.startswith("@@"):
            continue
        # an ADDED content line (not the +++ header, handled above)
        if in_ledger and line.startswith("+") and not line.startswith("+++"):
            if _SIGNED.search(line):
                offending.append(line[1:].strip())
    return offending


def main() -> int:
    diff_text = sys.stdin.read()
    offending = scan(diff_text)
    if offending:
        sys.stderr.write(
            "inbound-guard: a signed ledger line was added through this diff — REJECTED.\n"
            "signatures are minted only by this repo's gate; contribute the claim, not the verdict.\n")
        for o in offending[:5]:
            sys.stderr.write(f"  + {o[:140]}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

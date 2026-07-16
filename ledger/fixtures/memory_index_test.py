#!/usr/bin/env python3
"""Red-first fixture for audit.py's MEMORY.md index-size check (§13.41 / v1.3.3).

Index honesty with teeth (the mnemosyne lesson: a warn-only budget fires into a void). A
`memories/MEMORY.md` over the soft budget (default 16 KB) WARNs; over the hard budget (default
24 KB) is a genuine FAIL that fails the audit — with or without `--strict`. Budgets are config-keyed
via `LEDGER_MEM_SOFT_KB` / `LEDGER_MEM_HARD_KB`. An absent index is a no-op.

Red against the shipped audit (no such check): an oversized index passes, so the "oversized fails"
assertion is red until the check lands.

Run: python3 harness/ledger/fixtures/memory_index_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "audit.py"


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def git(root: Path, *a: str):
    return run(["git", *a], root)


def make_repo(root: Path, index_kb: int) -> None:
    """A minimal valid ledger (one clean claim) plus a memories/MEMORY.md of index_kb kilobytes."""
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    (root / "ledger").mkdir()
    claim = {"id": "clm-0000", "ts": "2026-07-15T00:00:00Z", "source": "claude-code",
             "kind": "assertion", "status": "unverified", "check": "none", "claim": "seed"}
    (root / "ledger" / "claims.jsonl").write_text(json.dumps(claim) + "\n")
    (root / "memories").mkdir()
    body = "# index\n\n" + ("- [a](a.md) — one terse line about a memory that is padded out.\n" * 1000)
    # pad/trim to the requested size
    target = index_kb * 1024
    if len(body) < target:
        body += "x" * (target - len(body))
    else:
        body = body[:target]
    (root / "memories" / "MEMORY.md").write_text(body)


def audit(root: Path, strict: bool = False):
    cmd = [sys.executable, str(AUDIT), "--root", str(root)]
    if strict:
        cmd.append("--strict")
    return run(cmd, root)


def main() -> int:
    # HARD: an oversized index (> 24 KB) FAILs the audit outright (teeth) — red against the shipped audit.
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        make_repo(r, 26)
        res = audit(r)
        assert res.returncode == 1, f"an oversized (26 KB) MEMORY.md must FAIL the audit (exit 1), got {res.returncode}:\n{res.stdout}"
        assert "memory-index" in res.stdout, f"the FAIL must name memory-index:\n{res.stdout}"
        assert "FAIL  memory-index" in res.stdout or "FAIL [memory-index]" in res.stdout, \
            f"the summary must show memory-index as FAIL:\n{res.stdout}"

    # SOFT: between soft and hard WARNs — passes non-strict, fails under --strict.
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        make_repo(r, 18)
        res = audit(r)
        assert res.returncode == 0, f"an 18 KB index must not FAIL non-strict, got {res.returncode}:\n{res.stdout}"
        assert "WARN" in res.stdout and "memory-index" in res.stdout, f"18 KB must WARN memory-index:\n{res.stdout}"
        res_strict = audit(r, strict=True)
        assert res_strict.returncode == 1, f"an 18 KB index must FAIL under --strict, got {res_strict.returncode}"

    # OK: a small index is clean.
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        make_repo(r, 3)
        res = audit(r)
        assert res.returncode == 0, f"a 3 KB index must pass, got {res.returncode}:\n{res.stdout}"
        assert "WARN  memory-index" not in res.stdout and "FAIL  memory-index" not in res.stdout, \
            f"a small index must not warn or fail memory-index:\n{res.stdout}"

    print("memory_index_test: PASS (hard FAILs, soft WARNs / strict-fails, small clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

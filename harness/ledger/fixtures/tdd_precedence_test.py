#!/usr/bin/env python3
"""Red-first fixture for audit.py's `tdd-precedence` warn check and the `red-proof coverage` report
line. Each case is a throwaway git repo with a specific claim-commit sequence:
  - precedence-GOOD: the parked claim is its own ledger-only commit, an ancestor of the code → no warn.
  - precedence-LATE: the parked claim rides the same commit as code → the precedence timestamp is
    missing, and tdd-precedence must WARN.
  - coverage: a test-bearing slice reads 0/1 without a red-proof receipt, 1/1 once one is filed.

Run: python3 harness/ledger/fixtures/tdd_precedence_test.py   (exit 0 = pass).
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


def init_repo(root: Path):
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    (root / "ledger").mkdir()


def commit_claim(root: Path, obj: dict, msg: str, extra: tuple[str, str] | None = None):
    """Append one claim line, optionally add a file (extra=(path, content)), then commit."""
    obj = {"ts": "2026-07-14T00:00:00Z", "source": "claude-code", **obj}
    with (root / "ledger" / "claims.jsonl").open("a") as f:
        f.write(json.dumps(obj) + "\n")
    if extra:
        (root / extra[0]).write_text(extra[1])
    git(root, "add", "-A")
    git(root, "commit", "-qm", msg)


def audit(root: Path) -> str:
    return run([sys.executable, str(AUDIT), "--root", str(root), "--report"], root).stdout


def parked(cid, claim):
    return {"id": cid, "claim": claim, "kind": "assertion", "status": "unverified", "check": "none"}


def landing(cid, sup, claim):
    return {"id": cid, "claim": claim, "kind": "assertion", "status": "unverified",
            "check": "repo-check", "supersedes": sup}


def main() -> int:
    # precedence-GOOD: claim its own ledger-only commit, then land + code
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        init_repo(r)
        commit_claim(r, parked("clm-0001", "slice A"), "claim A (ledger-only)")
        commit_claim(r, landing("clm-0002", "clm-0001", "slice A done"), "land A + code",
                     extra=("impl.py", "x = 1\n"))
        out = audit(r)
        assert "[tdd-precedence]" not in out, f"precedence-good must not warn:\n{out}"
        assert "PASS  tdd-precedence" in out, f"precedence-good must PASS tdd-precedence:\n{out}"

    # precedence-LATE: claim rides the same commit as code
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        init_repo(r)
        commit_claim(r, parked("clm-0001", "slice B"), "claim B + code (late!)",
                     extra=("impl.py", "y = 1\n"))
        commit_claim(r, landing("clm-0002", "clm-0001", "slice B done"), "land B")
        out = audit(r)
        assert "[tdd-precedence]" in out, f"precedence-late must WARN tdd-precedence:\n{out}"

    # coverage: a test-bearing slice, 0/1 then 1/1 once a red-proof receipt is filed
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        init_repo(r)
        commit_claim(r, parked("clm-0001", "slice C"), "claim C (ledger-only)")
        commit_claim(r, landing("clm-0002", "clm-0001", "slice C done"), "land C + test",
                     extra=("test_c.py", "assert 1 == 1\n"))
        out = audit(r)
        assert "red-proof coverage: 0/1 test-bearing slices" in out, f"coverage 0/1:\n{out}"
        commit_claim(r, {"id": "clm-0003", "kind": "testimony", "about": "clm-0001",
                         "status": "unverified", "check": "none",
                         "claim": "red-proof: 1 new test path(s) failed against base abcd1234 (red confirmed)"},
                     "red-proof receipt")
        out = audit(r)
        assert "red-proof coverage: 1/1 test-bearing slices" in out, f"coverage 1/1:\n{out}"

    # three-link discharge chain (clm-0030): park-nonrunnable -> repo-check(+test) -> signed. The
    # repo-check MIDDLE link lands with code, but it is a discharge step, not a claim-first event, so
    # tdd-precedence must NOT warn (only the ORIGINAL parked claim pairs); AND a red-proof receipt
    # about the SIGNED 3rd link still credits the slice's coverage (the forward-chain walk).
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        init_repo(r)
        commit_claim(r, {"id": "clm-0001", "claim": "slice D", "kind": "assertion",
                         "status": "unverified", "check": "loop-preregister"}, "claim D (ledger-only)")
        commit_claim(r, {"id": "clm-0002", "claim": "slice D", "kind": "assertion", "status": "unverified",
                         "check": "repo-check", "supersedes": "clm-0001"},
                     "supersede to repo-check + test", extra=("test_d.py", "assert 1 == 1\n"))
        commit_claim(r, {"id": "clm-0003", "claim": "slice D", "kind": "assertion", "status": "unverified",
                         "check": "repo-check", "supersedes": "clm-0002"}, "gate-sign successor (ledger-only)")
        out = audit(r)
        assert "[tdd-precedence]" not in out, \
            f"a three-link discharge chain must NOT warn — the repo-check middle link is a discharge, not claim-first (clm-0030):\n{out}"
        assert "red-proof coverage: 0/1 test-bearing slices" in out, f"three-link coverage 0/1 before a receipt:\n{out}"
        commit_claim(r, {"id": "clm-0004", "kind": "testimony", "about": "clm-0003", "status": "unverified",
                         "check": "none",
                         "claim": "red-proof: 1 new test path(s) failed against base abcd1234 (red confirmed)"},
                     "red-proof about the signed 3rd link")
        out = audit(r)
        assert "red-proof coverage: 1/1 test-bearing slices" in out, \
            f"the forward-chain walk must credit a receipt about the signed 3rd link (clm-0030):\n{out}"

    print("tdd_precedence_test: PASS (precedence good/late; coverage 0/1 then 1/1; three-link no warn + 3rd-link coverage)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

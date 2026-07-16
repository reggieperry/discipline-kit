#!/usr/bin/env python3
"""Red-first fixture for audit.py's squash-safe precedence (v1.3.1). Two throwaway git repos:

  - PR-MODE: an intact branch (ledger-only claim commit -> code+supersede commit). `audit.py --certify`
    verifies precedence by ancestry and emits a precedence certificate (a testimony about the parked
    claim), idempotently.
  - SQUASH-SIM: the branch collapsed to ONE code-carrying commit (claim + successor + code together,
    the squash signature xc == yc). The main-side tdd-precedence has no ancestry to read, so it WARNS
    'no precedence certificate' without the certificate line, and is CLEAN with it.

Red against the shipped audit.py: `--certify` does not exist, and the collapsed case warns
'landed with code' (not 'no precedence certificate') and ignores certificates.

Run: python3 harness/ledger/fixtures/squash_precedence_test.py   (exit 0 = pass).
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


def git(root, *a):
    return run(["git", *a], root)


def init_repo(root):
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    (root / "ledger").mkdir()


def append_claim(root, obj):
    obj = {"ts": "2026-07-14T00:00:00Z", "source": "claude-code", **obj}
    with (root / "ledger" / "claims.jsonl").open("a") as f:
        f.write(json.dumps(obj) + "\n")


def commit(root, msg):
    git(root, "add", "-A")
    git(root, "commit", "-qm", msg)


def parked(cid, claim):
    return {"id": cid, "claim": claim, "kind": "assertion", "status": "unverified", "check": "none"}


def landing(cid, sup, claim):
    return {"id": cid, "claim": claim, "kind": "assertion", "status": "unverified",
            "check": "repo-check", "supersedes": sup}


def audit_report(root):
    return run([sys.executable, str(AUDIT), "--root", str(root), "--report"], root).stdout


def certify(root):
    return run([sys.executable, str(AUDIT), "--root", str(root), "--certify"], root)


def claims_text(root):
    return (root / "ledger" / "claims.jsonl").read_text()


def main() -> int:
    # PR-MODE: intact branch; --certify emits a precedence certificate about the parked claim
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        init_repo(r)
        append_claim(r, parked("clm-0001", "slice A"))
        commit(r, "claim A (ledger-only)")
        append_claim(r, landing("clm-0002", "clm-0001", "slice A done"))
        (r / "impl.py").write_text("x = 1\n")
        commit(r, "land A + code")
        res = certify(r)
        assert res.returncode == 0, f"--certify must exist and exit 0 on verifiable precedence:\n{res.stderr}"
        assert "precedence verified: clm-0001" in claims_text(r), \
            f"--certify must emit a precedence certificate about clm-0001:\n{claims_text(r)}"
        certify(r)  # idempotent — a second run must not duplicate
        assert claims_text(r).count("precedence verified: clm-0001") == 1, \
            "--certify must be idempotent (no duplicate certificate)"

    # SQUASH-SIM: claim + successor + code collapse into ONE code-carrying commit (xc == yc)
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        init_repo(r)
        append_claim(r, parked("clm-0001", "slice B"))
        append_claim(r, landing("clm-0002", "clm-0001", "slice B done"))
        (r / "impl.py").write_text("y = 1\n")
        commit(r, "squashed: claim + successor + code in one commit")
        out = audit_report(r)
        assert "no precedence certificate" in out, \
            f"a squash-collapsed pair must warn 'no precedence certificate':\n{out}"
        # add the certificate -> the collapsed pair is now clean
        append_claim(r, {"id": "clm-0003", "kind": "testimony", "about": "clm-0001",
                         "status": "unverified", "check": "none", "source": "hook",
                         "claim": "precedence verified: clm-0001 ledger-only commit abcd1234 "
                                  "precedes its code at ef567890 (branch feat, run 42)"})
        commit(r, "add precedence certificate")
        out = audit_report(r)
        assert "no precedence certificate" not in out, \
            f"the precedence certificate must clear the squash warn:\n{out}"

    print("squash_precedence_test: PASS (--certify emits; squash warns without cert, clean with it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

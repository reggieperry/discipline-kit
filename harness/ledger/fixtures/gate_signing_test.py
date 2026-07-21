#!/usr/bin/env python3
"""Red-first fixture for IN-COMMIT signing (§18; the gate signs atomically).

On a green check, the gate must sign each pending runnable claim IN the commit that earns it: the
signed entry is part of HEAD's committed `ledger/claims.jsonl`, and the working tree is CLEAN
afterward. No separate post-commit phase leaves the signature dirty in the working tree (which is
easy to mistake for noise and revert). Red against the two-phase gate, which signs post-commit into
the working tree, so the signature is uncommitted (dirty) and NOT in HEAD.

Run: python3 harness/ledger/fixtures/gate_signing_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
INSTALLER = KIT / "install-harness.sh"


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        run(["git", "init", "-q"], repo)
        run(["git", "config", "user.email", "t@t"], repo)
        run(["git", "config", "user.name", "t"], repo)
        (repo / "README.md").write_text("x\n")
        run(["git", "add", "-A"], repo)
        run(["git", "commit", "-qm", "init"], repo)

        # full harness (the gate under test + wired hooks)
        r = run(["bash", str(INSTALLER), "--dir", str(repo)])
        assert r.returncode == 0, f"install must succeed:\n{r.stdout}\n{r.stderr}"

        # a passing check via the sentinel-gated env override (no real build in a scratch repo)
        (repo / "ledger" / ".test-mode").write_text("")
        env = dict(os.environ, LEDGER_CHECK_CMD="true")

        # park a claim under repo-check (a pending runnable assertion)
        claim = {"claim": "widget behaves", "subject": "w", "source": "claude-code",
                 "kind": "assertion", "status": "unverified", "check": "repo-check"}
        ap = subprocess.run([sys.executable, str(repo / "ledger" / "append")], cwd=repo, env=env,
                            input=json.dumps(claim), capture_output=True, text=True)
        assert ap.returncode == 0, f"append must succeed:\n{ap.stdout}\n{ap.stderr}"

        # commit the install + the parked claim in one go; the gate runs the (passing) check and signs
        run(["git", "add", "-A"], repo)
        c = run(["git", "commit", "-qm", "land widget"], repo, env=env)
        assert c.returncode == 0, f"the discharging commit must succeed:\n{c.stdout}\n{c.stderr}"

        # (1) the working tree must be CLEAN — no signature left dirty for a follow-up commit
        status = run(["git", "status", "--porcelain"], repo).stdout.strip()
        assert status == "", \
            f"working tree must be CLEAN after an in-commit-signing commit — a dirty tree means the\n" \
            f"signature was written post-commit and is uncommitted:\n{status}"

        # (2) the claim's signature must be committed IN the discharging commit (present in HEAD)
        head = run(["git", "show", "HEAD:ledger/claims.jsonl"], repo).stdout
        entries = [json.loads(l) for l in head.splitlines() if l.strip()]
        signed = [e for e in entries if e.get("status") == "signed" and "widget behaves" in e.get("claim", "")]
        assert signed, \
            "the claim's signature must be part of the discharging commit — found no signed " \
            "'widget behaves' entry in HEAD's claims.jsonl (it was signed post-commit, not in-commit)"

    print("gate_signing_test: PASS (claim signed IN its commit; working tree clean, no post-commit dirt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

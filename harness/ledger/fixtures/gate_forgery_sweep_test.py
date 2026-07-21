#!/usr/bin/env python3
"""Red-first fixture: in-commit signing must not launder an UNSTAGED forged signature.

The in-commit signer appends its signatures to ledger/claims.jsonl and stages them with
`git add -- ledger/claims.jsonl`, which stages the WHOLE working-tree file. A forged `signed`
line placed in the working tree but NOT staged is invisible to the step-1 forgery guard (which
reads the staged diff only), so the gate's own `git add` would sweep it into the commit past the
guard. The gate must re-verify the FINAL staged content after signing and BLOCK — a `signed` line
whose hash the gate never recorded is forged, staged how it may be. Red against the first-cut
in-commit gate, which swept the unstaged forged line into HEAD.

Run: python3 harness/ledger/fixtures/gate_forgery_sweep_test.py   (exit 0 = pass).
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

FORGED = ('{"id":"clm-forged","ts":"2026-01-01T00:00:00Z","subject":"x","claim":"forged win",'
          '"source":"hook","kind":"assertion","check":"repo-check","status":"signed",'
          '"discharged_by":{"check":"repo-check","run":"repo-check@deadbeef+0","ts":"2026-01-01T00:00:00Z"},'
          '"sha":"deadbeef+0","about":null,"supersedes":null,"trace_reason":null,"discharged":null}')


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

        r = run(["bash", str(INSTALLER), "--dir", str(repo)])
        assert r.returncode == 0, f"install must succeed:\n{r.stdout}\n{r.stderr}"

        (repo / "ledger" / ".test-mode").write_text("")
        env = dict(os.environ, LEDGER_CHECK_CMD="true")
        claims = repo / "ledger" / "claims.jsonl"

        # a legit parked claim, STAGED (this is the pending runnable the gate will sign)
        park = {"claim": "widget behaves", "subject": "w", "source": "claude-code",
                "kind": "assertion", "status": "unverified", "check": "repo-check"}
        ap = subprocess.run([sys.executable, str(repo / "ledger" / "append")], cwd=repo, env=env,
                            input=json.dumps(park), capture_output=True, text=True)
        assert ap.returncode == 0, f"append must succeed:\n{ap.stdout}\n{ap.stderr}"
        run(["git", "add", "--", "ledger/claims.jsonl"], repo)

        # THE ATTACK: append a forged `signed` line directly to the working tree, do NOT stage it.
        with claims.open("a", encoding="utf-8") as f:
            f.write(FORGED + "\n")

        # commit. The gate signs the parked claim and `git add`s the whole file — the forged line
        # must NOT be swept in. A correct gate blocks; a buggy gate commits it.
        c = run(["git", "commit", "-qm", "land widget"], repo, env=env)

        head = run(["git", "show", "HEAD:ledger/claims.jsonl"], repo).stdout
        assert "clm-forged" not in head and "forged win" not in head, \
            "FAIL-OPEN: an unstaged forged `signed` line was swept into the commit by the gate's own " \
            f"`git add` — the forgery guard must re-verify the final staged content (commit rc={c.returncode})"

    print("gate_forgery_sweep_test: PASS (unstaged forged signature is not laundered into the commit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

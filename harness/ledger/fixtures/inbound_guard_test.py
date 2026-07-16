#!/usr/bin/env python3
"""Red-first fixture for the inbound signed-line guard (§17.61 / v1.5.0).

The forgery guard is hook-local, so a fork PR (a commit path with no gate) could add a
`"status":"signed"` ledger line nothing structurally rejects. `inbound_guard.py` reads a unified
diff on stdin and FAILS (exit 1) when any ADDED line is a signed ledger entry — signatures are
minted only by the repo's own gate; a contributor sends the claim, not the verdict. An added
unverified claim or a testimony entry passes; a REMOVED signed line passes (only additions are
inbound). Red against a guard that does not exist yet.

Run: python3 harness/ledger/fixtures/inbound_guard_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "inbound_guard.py"

SIGNED = '{"id":"clm-9001","ts":"2026-07-15T00:00:00Z","claim":"x","subject":"s","source":"hook","kind":"assertion","status":"signed","check":"repo-check","sha":"deadbeef"}'
UNVERIF = '{"id":"clm-9002","ts":"2026-07-15T00:00:00Z","claim":"x","subject":"s","source":"claude-code","kind":"assertion","status":"unverified","check":"none"}'
TESTIM = '{"id":"clm-9003","ts":"2026-07-15T00:00:00Z","claim":"review says x","subject":"s","source":"subagent","kind":"testimony","status":"unverified","check":"none","about":"clm-9002"}'


def diff(added=(), removed=()):
    body = ["diff --git a/ledger/claims.jsonl b/ledger/claims.jsonl",
            "--- a/ledger/claims.jsonl", "+++ b/ledger/claims.jsonl", "@@ -1 +1,3 @@"]
    body += ["+" + a for a in added]
    body += ["-" + r for r in removed]
    return "\n".join(body) + "\n"


def run(diff_text):
    return subprocess.run([sys.executable, str(GUARD)], input=diff_text,
                          capture_output=True, text=True)


def main() -> int:
    # ADDED signed line -> violation (exit 1) with the doctrine message
    r = run(diff(added=[SIGNED]))
    assert r.returncode == 1, f"an added signed line must FAIL the guard, got {r.returncode}:\n{r.stdout}{r.stderr}"
    assert "contribute the claim, not the verdict" in (r.stdout + r.stderr), \
        f"the guard must print the doctrine message:\n{r.stdout}{r.stderr}"

    # ADDED unverified claim -> clean
    r = run(diff(added=[UNVERIF]))
    assert r.returncode == 0, f"an added unverified claim must PASS, got {r.returncode}:\n{r.stdout}{r.stderr}"

    # ADDED testimony -> clean
    r = run(diff(added=[TESTIM]))
    assert r.returncode == 0, f"an added testimony entry must PASS, got {r.returncode}:\n{r.stdout}{r.stderr}"

    # REMOVED signed line -> clean (only ADDED signed lines are inbound)
    r = run(diff(removed=[SIGNED]))
    assert r.returncode == 0, f"a removed signed line must PASS (not an addition), got {r.returncode}"

    # mixed: an unverified claim AND a signed line added -> violation (the signed one)
    r = run(diff(added=[UNVERIF, SIGNED]))
    assert r.returncode == 1, "a diff adding any signed line must fail even alongside a clean claim"

    print("inbound_guard_test: PASS (added signed FAILs; unverified/testimony/removed-signed PASS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

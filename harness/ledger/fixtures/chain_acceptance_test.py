#!/usr/bin/env python3
"""Red-first acceptance fixture for the /chain driver's fail-closed refusals (§18; brief item 15).

The driver advances only on re-derived ledger/git state, and REFUSES to advance past a bad phase.
This simulates each of the three refusal states and asserts the mechanical postcondition predicate
(harness/chain/postcondition.py) halts closed (exit 2), plus a clean state that passes (exit 0):

  1. planner parked nothing            -> planner-parked  halts
  2. tester's diff touched production  -> tester-clean    halts
  3. an undischarged blocking refutation -> no-open-refutation halts

Red against a missing/permissive predicate.

Run: python3 harness/ledger/fixtures/chain_acceptance_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
PRED = KIT / "harness" / "chain" / "postcondition.py"


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def write_ledger(path, entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


def pc(sub, *args, cwd=None, ledger=None):
    cmd = [sys.executable, str(PRED), sub, *args]
    env = None
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          env={**__import__("os").environ, "LEDGER_FILE": str(ledger)} if ledger else None)


def main() -> int:
    assert PRED.exists(), f"postcondition predicate missing: {PRED}"

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        run(["git", "init", "-q"], repo)
        run(["git", "config", "user.email", "t@t"], repo)
        run(["git", "config", "user.name", "t"], repo)
        led = repo / "claims.jsonl"

        story = "story-widget-1"

        # 1a. planner parked nothing -> HALT (exit 2)
        write_ledger(led, [{"id": "clm-1", "subject": "other", "claim": "unrelated",
                            "kind": "assertion", "status": "unverified", "check": "none"}])
        r = pc("planner-parked", story, ledger=led)
        assert r.returncode == 2, f"planner-parked must HALT when nothing was parked, got {r.returncode}:\n{r.stderr}"

        # 1b. a parked (non-runnable) claim for the story -> PASS (exit 0)
        write_ledger(led, [{"id": "clm-2", "subject": story, "claim": "widget behaves (story: %s)" % story,
                            "kind": "assertion", "status": "unverified", "check": "widget-selftest"}])
        r = pc("planner-parked", story, ledger=led)
        assert r.returncode == 0, f"planner-parked must PASS with a parked claim, got {r.returncode}:\n{r.stderr}"

        # 1c. a claim parked under a RUNNABLE check is not a valid park (would auto-sign) -> HALT
        write_ledger(led, [{"id": "clm-3", "subject": story, "claim": "widget (story: %s)" % story,
                            "kind": "assertion", "status": "unverified", "check": "repo-check"}])
        r = pc("planner-parked", story, ledger=led)
        assert r.returncode == 2, f"planner-parked must HALT when the only claim is under a runnable check, got {r.returncode}"

        # 2a. tester touched PRODUCTION code -> HALT
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "app.py").write_text("v = 1\n")
        run(["git", "add", "-A"], repo)
        run(["git", "commit", "-qm", "base"], repo)
        base = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        (repo / "src" / "app.py").write_text("v = 2\n")  # production change
        run(["git", "add", "-A"], repo); run(["git", "commit", "-qm", "tester touched prod"], repo)
        r = pc("tester-clean", base, cwd=repo)
        assert r.returncode == 2 and "src/app.py" in r.stderr, \
            f"tester-clean must HALT when a non-test path changed, got {r.returncode}:\n{r.stderr}"

        # 2b. tester changed only TEST paths -> PASS
        base2 = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        (repo / "tests").mkdir(exist_ok=True)
        (repo / "tests" / "test_app.py").write_text("def test_v(): assert True\n")
        run(["git", "add", "-A"], repo); run(["git", "commit", "-qm", "tester added a test"], repo)
        r = pc("tester-clean", base2, cwd=repo)
        assert r.returncode == 0, f"tester-clean must PASS when only test paths changed, got {r.returncode}:\n{r.stderr}"

        # 2c. the tester's own attestation append to ledger/claims.jsonl must PASS — it is the tester's
        # legitimate output, not a production touch (Cluster A sibling; is_test_path rejects it otherwise).
        base2c = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        (repo / "ledger").mkdir(exist_ok=True)
        (repo / "ledger" / "claims.jsonl").write_text('{"id":"clm-att","kind":"testimony"}\n')
        run(["git", "add", "-A"], repo); run(["git", "commit", "-qm", "tester attestation"], repo)
        r = pc("tester-clean", base2c, cwd=repo)
        assert r.returncode == 0, \
            f"tester-clean must PASS an attestation-only claims.jsonl change, got {r.returncode}:\n{r.stderr}"

        # 3a. an undischarged blocking refutation about the story -> HALT
        write_ledger(led, [
            {"id": "clm-10", "subject": story, "claim": "widget behaves (story: %s)" % story,
             "kind": "assertion", "status": "unverified", "check": "widget-selftest"},
            {"id": "clm-11", "subject": story, "claim": "widget is wrong (story: %s)" % story,
             "kind": "refutation", "status": "unverified", "check": "none", "about": "clm-10"},
        ])
        r = pc("no-open-refutation", story, ledger=led)
        assert r.returncode == 2 and "clm-11" in r.stderr, \
            f"no-open-refutation must HALT on an open refutation, got {r.returncode}:\n{r.stderr}"

        # 3b. the refutation healed by a signed successor about it -> PASS
        write_ledger(led, [
            {"id": "clm-10", "subject": story, "claim": "widget behaves (story: %s)" % story,
             "kind": "assertion", "status": "unverified", "check": "widget-selftest"},
            {"id": "clm-11", "subject": story, "claim": "widget is wrong (story: %s)" % story,
             "kind": "refutation", "status": "unverified", "check": "none", "about": "clm-10"},
            {"id": "clm-12", "subject": story, "claim": "fixed; refutation disposed (story: %s)" % story,
             "kind": "assertion", "status": "signed", "check": "repo-check", "about": "clm-11"},
        ])
        r = pc("no-open-refutation", story, ledger=led)
        assert r.returncode == 0, f"no-open-refutation must PASS once the refutation is disposed, got {r.returncode}:\n{r.stderr}"

    print("chain_acceptance_test: PASS (3 fail-closed refusals halt; clean states advance)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

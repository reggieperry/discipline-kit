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

        # 2d. an in-place WEAKENING of an existing test assertion (assertEquals(x,5)->assertEquals(x,x))
        # must HALT — it changes test lines, not purely adds. The attest-only tester has no legitimate
        # reason to edit an existing grader line; a count-based check misses this, so require additive.
        base2d = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        (repo / "tests" / "test_app.py").write_text("def test_v(): assert v == v\n")  # weakened from == 2
        run(["git", "add", "-A"], repo); run(["git", "commit", "-qm", "tester weakens a test"], repo)
        r = pc("tester-clean", base2d, cwd=repo)
        assert r.returncode == 2, \
            f"tester-clean must HALT on an in-place test weakening (non-additive), got {r.returncode}:\n{r.stderr}"

        # 3a. an open blocking refutation about a story claim -> HALT. The refutation carries the
        # reviewer's real shape: `about` the refuted claim, story id NOT in its own text (the reviewer
        # is never told to embed it) — so detection MUST follow the about-edge to the claim, which does
        # carry the story id. (The old fixture masked the gap by hand-writing "(story:)" here.)
        write_ledger(led, [
            {"id": "clm-10", "subject": story, "claim": "widget behaves (story: %s)" % story,
             "kind": "assertion", "status": "unverified", "check": "widget-selftest"},
            {"id": "clm-11", "subject": "review", "claim": "the widget mishandles zero — repro attached",
             "kind": "refutation", "status": "unverified", "check": "none", "about": "clm-10"},
        ])
        r = pc("no-open-refutation", story, ledger=led)
        assert r.returncode == 2 and "clm-11" in r.stderr, \
            f"an open refutation must HALT even when the story id is only on the refuted claim " \
            f"(about-edge scoping), got {r.returncode}:\n{r.stderr}"

        # 3b. an already-SIGNED refuted claim, NO superseding fix -> still HALT. A refutation says the
        # claim is now known-wrong; the claim's PRE-EXISTING signature does not dispose it — only a
        # superseding fix that passed the gate does. (This is the second fail-open: keying on "C is
        # resolved" wrongly disposed a fresh refutation about an old signature.)
        write_ledger(led, [
            {"id": "clm-30", "subject": story, "claim": "widget behaves (story: %s)" % story,
             "kind": "assertion", "status": "signed", "check": "repo-check"},
            {"id": "clm-31", "subject": "review", "claim": "the signed widget is actually wrong",
             "kind": "refutation", "status": "unverified", "check": "none", "about": "clm-30"},
        ])
        r = pc("no-open-refutation", story, ledger=led)
        assert r.returncode == 2 and "clm-31" in r.stderr, \
            f"a refutation about an already-signed claim with NO superseding fix must HALT, got {r.returncode}:\n{r.stderr}"

        # 3c. the REACHABLE disposal: the worker loop-back fixes the refuted claim and the gate signs a
        # successor that SUPERSEDES it -> disposed -> PASS.
        write_ledger(led, [
            {"id": "clm-40", "subject": story, "claim": "widget behaves (story: %s)" % story,
             "kind": "assertion", "status": "unverified", "check": "widget-selftest"},
            {"id": "clm-41", "subject": "review", "claim": "the widget mishandles zero",
             "kind": "refutation", "status": "unverified", "check": "none", "about": "clm-40"},
            {"id": "clm-42", "subject": story, "claim": "widget behaves, fixed (story: %s)" % story,
             "kind": "assertion", "status": "signed", "check": "repo-check", "supersedes": "clm-40"},
        ])
        r = pc("no-open-refutation", story, ledger=led)
        assert r.returncode == 0, \
            f"no-open-refutation must PASS once a signed successor SUPERSEDES the refuted claim, got {r.returncode}:\n{r.stderr}"

        # 3d. a resolved fix-claim directly `about` the refutation also disposes it -> PASS.
        write_ledger(led, [
            {"id": "clm-50", "subject": story, "claim": "widget behaves (story: %s)" % story,
             "kind": "assertion", "status": "unverified", "check": "widget-selftest"},
            {"id": "clm-51", "subject": "review", "claim": "the widget mishandles zero",
             "kind": "refutation", "status": "unverified", "check": "none", "about": "clm-50"},
            {"id": "clm-52", "subject": story, "claim": "refutation addressed (story: %s)" % story,
             "kind": "assertion", "status": "signed", "check": "repo-check", "about": "clm-51"},
        ])
        r = pc("no-open-refutation", story, ledger=led)
        assert r.returncode == 0, f"a resolved entry about the refutation must dispose it, got {r.returncode}:\n{r.stderr}"

        # 4. worker-complete: an UNTOUCHED planner-original criterion (never built) HALTS the worker
        # phase — the worker must not hand off a story with an open obligation.
        write_ledger(led, [
            {"id": "clm-60", "subject": story, "claim": "criterion A (story: %s)" % story,
             "kind": "assertion", "status": "unverified", "check": "a-selftest"},  # untouched
        ])
        r = pc("worker-complete", story, ledger=led)
        assert r.returncode == 2 and "clm-60" in r.stderr, \
            f"worker-complete must HALT on an untouched criterion, got {r.returncode}:\n{r.stderr}"

        # 4b. a BUILT criterion (superseded by a signed successor) -> PASS.
        write_ledger(led, [
            {"id": "clm-70", "subject": story, "claim": "criterion A (story: %s)" % story,
             "kind": "assertion", "status": "unverified", "check": "a-selftest"},
            {"id": "clm-71", "subject": story, "claim": "criterion A, built (story: %s)" % story,
             "kind": "assertion", "status": "signed", "check": "repo-check", "supersedes": "clm-70"},
        ])
        r = pc("worker-complete", story, ledger=led)
        assert r.returncode == 0, f"worker-complete must PASS a built (superseded->signed) criterion, got {r.returncode}:\n{r.stderr}"

        # 4c. a DEFERRED criterion (worker re-parked it with a reason — supersedes the original under a
        # non-runnable check) -> PASS (parked-with-reason is a legitimate, addressed disposition).
        write_ledger(led, [
            {"id": "clm-80", "subject": story, "claim": "criterion A (story: %s)" % story,
             "kind": "assertion", "status": "unverified", "check": "a-selftest"},
            {"id": "clm-81", "subject": story, "claim": "criterion A deferred: blocked on X (story: %s)" % story,
             "kind": "assertion", "status": "unverified", "check": "a-deferred", "supersedes": "clm-80"},
        ])
        r = pc("worker-complete", story, ledger=led)
        assert r.returncode == 0, f"worker-complete must PASS a deferred (re-parked) criterion, got {r.returncode}:\n{r.stderr}"

    print("chain_acceptance_test: PASS (3 fail-closed refusals halt; clean states advance; "
          "worker-complete halts an untouched criterion)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Red-first fixture for the kit-interchange parser/verifier (§17.65 / v1.5.0).

A contribution into another repo carries a machine-parseable `kit-interchange: v1` block naming the
claim it discharges and the disposing check as a runnable command. The receiver's parser
(`interchange.py`) parses it and, under `--verify`, RE-RUNS the disposing check to grade the
contribution: DISCHARGEABLE when the check passes, RECEIPT-FAILED when it does not. The block
authenticates nothing — a forged block whose check passes is still DISCHARGEABLE (verify the claims,
never the badge); a forged or honest block whose check fails is RECEIPT-FAILED.

Red against a parser that does not exist yet.

Run: python3 harness/ledger/fixtures/interchange_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PARSER = Path(__file__).resolve().parent.parent / "interchange.py"


def block(sender="v1.5.0, tier private", check="true", forged=False):
    hv = "0000forged0000" if forged else "abc123realhash"
    return (
        "kit-interchange: v1\n"
        f"sender: {sender}\n"
        "claim: the widget handler rejects a negative quantity\n"
        f"disposing-check: {check}\n"
        "red: test_widget_rejects_negative failed against base 1234abcd (red confirmed)\n"
        f"harness-verify: {hv}\n"
    )


def run(text, verify=True):
    args = [sys.executable, str(PARSER)]
    if verify:
        args.append("--verify")
    return subprocess.run(args, input=text, capture_output=True, text=True)


def main() -> int:
    # 1. VALID block, disposing check passes -> DISCHARGEABLE (exit 0)
    r = run(block(check="true"))
    assert r.returncode == 0, f"a valid block whose check passes must be DISCHARGEABLE (exit 0), got {r.returncode}:\n{r.stdout}{r.stderr}"
    assert "DISCHARGEABLE" in (r.stdout + r.stderr), f"must grade DISCHARGEABLE:\n{r.stdout}{r.stderr}"

    # 2. RECEIPT-FAILING block, disposing check fails on re-run -> RECEIPT-FAILED (exit 1)
    r = run(block(check="false"))
    assert r.returncode == 1, f"a block whose check fails must be RECEIPT-FAILED (exit 1), got {r.returncode}:\n{r.stdout}{r.stderr}"
    assert "RECEIPT-FAILED" in (r.stdout + r.stderr), f"must grade RECEIPT-FAILED:\n{r.stdout}{r.stderr}"

    # 3. RECEIPT-PASSING FORGED block (fake sender + hash, but the check passes) -> DISCHARGEABLE
    r = run(block(sender="v9.9.9, tier impostor", check="true", forged=True))
    assert r.returncode == 0, f"a forged block whose check PASSES must still be DISCHARGEABLE (verify the claim, not the badge), got {r.returncode}:\n{r.stdout}{r.stderr}"
    assert "DISCHARGEABLE" in (r.stdout + r.stderr)

    # 4. MALFORMED block (missing the disposing-check field) -> exit 2
    bad = "kit-interchange: v1\nsender: v1.5.0\nclaim: something\n"
    r = run(bad)
    assert r.returncode == 2, f"a malformed block (no disposing-check) must exit 2, got {r.returncode}:\n{r.stdout}{r.stderr}"

    # 5. Not a kit-interchange block at all -> exit 2 (malformed)
    r = run("just some PR prose with no block\n")
    assert r.returncode == 2, f"a body with no interchange block must exit 2, got {r.returncode}"

    print("interchange_test: PASS (valid->DISCHARGEABLE, failing->RECEIPT-FAILED, forged-passing->DISCHARGEABLE, malformed->2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

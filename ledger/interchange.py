#!/usr/bin/env python3
"""interchange.py — parse a kit-interchange block and, under --verify, grade it by re-running its check.

A contribution filed into another harnessed repo (a PR or issue body) carries a machine-parseable
block so the receiver can dispose it mechanically instead of trusting prose:

    kit-interchange: v1
    sender: <ledger/VERSION>, tier <tier>
    claim: <the claim this contribution discharges, verbatim>
    disposing-check: <a runnable command that turns red on the defect / green on the fix>
    red: <the pasted red line the contributor observed>
    harness-verify: <the sender's harness-verify hash>

The doctrine this encodes: **the block authenticates nothing; it makes contributions dischargeable.**
This parser does NOT verify the sender or the harness-verify hash — author identity is unprovable and,
under this constitution, unnecessary. It parses the block and, with `--verify`, RE-RUNS the
`disposing-check` and grades:

  - DISCHARGEABLE   — the disposing check passed (exit 0). The claim carries its own court; accept it,
                      forged badge or not (a forged block whose check passes has delivered a working
                      claim with its check, which is the contribution the block exists to demand).
  - RECEIPT-FAILED  — the disposing check failed (exit 1). The receipt does not hold; grade the
                      contribution down to false testimony.
  - MALFORMED       — no interchange block, or a required field missing (exit 2).

    <pr-body> | python3 ledger/interchange.py            # parse only (exit 0 valid / 2 malformed)
    <pr-body> | python3 ledger/interchange.py --verify   # parse + re-run the check + grade

SECURITY: `--verify` runs the contributed command. Run it only in a sandbox you would run a
contributor's tests in (a CI job with no secrets), exactly as you would any inbound test.
"""
from __future__ import annotations

import subprocess
import sys

_REQUIRED = ("claim", "disposing-check")


def parse(body: str) -> dict | None:
    """Return the block's fields, or None if there is no kit-interchange block."""
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("kit-interchange:"):
            start = i
            break
    if start is None:
        return None
    fields: dict[str, str] = {"kit-interchange": lines[start].split(":", 1)[1].strip()}
    for line in lines[start + 1:]:
        if not line.strip():
            break  # a blank line ends the block
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        fields[key.strip().lower()] = val.strip()
    return fields


def main() -> int:
    verify = "--verify" in sys.argv[1:]
    body = sys.stdin.read()
    fields = parse(body)
    if fields is None:
        sys.stderr.write("interchange: MALFORMED — no `kit-interchange:` block found\n")
        return 2
    missing = [k for k in _REQUIRED if not fields.get(k)]
    if missing:
        sys.stderr.write(f"interchange: MALFORMED — missing required field(s): {', '.join(missing)}\n")
        return 2

    check = fields["disposing-check"]
    if not verify:
        print(f"interchange: parsed (claim, disposing-check `{check}`) — run with --verify to grade")
        return 0

    # Re-run the disposing check. The badge is not verified — only the claim's court.
    try:
        proc = subprocess.run(check, shell=True, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        sys.stderr.write(f"interchange: RECEIPT-FAILED — disposing check could not run: {e}\n")
        return 1
    if proc.returncode == 0:
        print("interchange: DISCHARGEABLE — the disposing check passed; the claim carries its court "
              "(the sender badge is not verified and does not need to be)")
        return 0
    sys.stderr.write("interchange: RECEIPT-FAILED — the disposing check did not pass on re-run; "
                     "grade this contribution down to false testimony\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())

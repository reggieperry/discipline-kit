#!/usr/bin/env python3
"""Red-first fixture for the mechanical four-state committee verdict (§18; the veto-only reframe).

verdict.py aggregates the reviewer roles' outputs into the four-state Belnap read, FAIL-CLOSED:
CLEAN only when every launched role produced a well-formed clean completion (positive-existence
against the launch manifest — NOT "zero refutations => CLEAN"); REFUTED on any blocking refutation;
CONTESTED on a split / a finding with no disposing check / a judge touch; INDETERMINATE on any role
that is missing, malformed, or errored. Exit encodes the verdict for the driver's routing:
0=CLEAN, 2=REFUTED, 3=CONTESTED, 4=INDETERMINATE. Red against a missing/permissive aggregator (one
that would call an errored or absent role CLEAN).

Run: python3 harness/ledger/fixtures/chain_verdict_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
AGG = KIT / "harness" / "chain" / "verdict.py"

CLEAN, REFUTED, CONTESTED, INDETERMINATE = 0, 2, 3, 4


def run_verdict(manifest, verdicts, tmp):
    (tmp / "manifest.json").write_text(json.dumps(manifest))
    vdir = tmp / "verdicts"
    vdir.mkdir(exist_ok=True)
    for f in vdir.glob("*.json"):
        f.unlink()
    for role, body in verdicts.items():
        (vdir / f"{role}.json").write_text(body if isinstance(body, str) else json.dumps(body))
    r = subprocess.run([sys.executable, str(AGG), str(tmp / "manifest.json"), str(vdir)],
                       capture_output=True, text=True)
    return r


def main() -> int:
    assert AGG.exists(), f"verdict aggregator missing: {AGG}"

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        roles = ["logic-and-state", "abuse-and-boundaries"]

        def v(word):
            return {"role": "r", "verdict": word}

        # 1. all roles clean -> CLEAN
        r = run_verdict(roles, {"logic-and-state": {"role": "logic-and-state", "verdict": "clean"},
                                "abuse-and-boundaries": {"role": "abuse-and-boundaries", "verdict": "clean"}}, tmp)
        assert r.returncode == CLEAN, f"all-clean must be CLEAN(0), got {r.returncode}:\n{r.stdout}{r.stderr}"
        assert "CLEAN" in r.stdout

        # 2. one role refuted -> REFUTED (a caught defect vetoes)
        r = run_verdict(roles, {"logic-and-state": v("refuted"),
                                "abuse-and-boundaries": v("clean")}, tmp)
        assert r.returncode == REFUTED, f"any refutation must be REFUTED(2), got {r.returncode}:\n{r.stdout}{r.stderr}"
        assert "REFUTED" in r.stdout

        # 3. one role contested -> CONTESTED
        r = run_verdict(roles, {"logic-and-state": v("contested"),
                                "abuse-and-boundaries": v("clean")}, tmp)
        assert r.returncode == CONTESTED, f"a contest must be CONTESTED(3), got {r.returncode}:\n{r.stdout}{r.stderr}"
        assert "CONTESTED" in r.stdout

        # 4. a launched role is MISSING its verdict file -> INDETERMINATE (positive-existence, fail closed)
        r = run_verdict(roles, {"logic-and-state": v("clean")}, tmp)  # abuse-and-boundaries absent
        assert r.returncode == INDETERMINATE, \
            f"a missing role must be INDETERMINATE(4), never CLEAN, got {r.returncode}:\n{r.stdout}{r.stderr}"
        assert "INDETERMINATE" in r.stdout

        # 5. a role reported an ERROR -> INDETERMINATE (an errored reviewer is never a clean vote)
        r = run_verdict(roles, {"logic-and-state": v("clean"),
                                "abuse-and-boundaries": v("error")}, tmp)
        assert r.returncode == INDETERMINATE, \
            f"an errored role must be INDETERMINATE(4), got {r.returncode}:\n{r.stdout}{r.stderr}"

        # 6. a MALFORMED verdict file -> INDETERMINATE (cannot read => cannot call clean)
        r = run_verdict(roles, {"logic-and-state": v("clean"),
                                "abuse-and-boundaries": "{not json"}, tmp)
        assert r.returncode == INDETERMINATE, \
            f"a malformed verdict must be INDETERMINATE(4), got {r.returncode}:\n{r.stdout}{r.stderr}"

        # 7. an unknown verdict word -> INDETERMINATE (fail closed on the unrecognized)
        r = run_verdict(roles, {"logic-and-state": v("clean"),
                                "abuse-and-boundaries": v("looks-fine-to-me")}, tmp)
        assert r.returncode == INDETERMINATE, \
            f"an unknown verdict word must be INDETERMINATE(4), got {r.returncode}:\n{r.stdout}{r.stderr}"

        # 8. an EMPTY manifest cannot be CLEAN (an empty committee vetoes nothing but authorizes nothing)
        r = run_verdict([], {}, tmp)
        assert r.returncode != CLEAN, \
            f"an empty manifest must NOT be CLEAN, got {r.returncode}:\n{r.stdout}{r.stderr}"

        # 9. REFUTED dominates a co-present contest (a real defect is the strongest signal to act on)
        r = run_verdict(roles, {"logic-and-state": v("refuted"),
                                "abuse-and-boundaries": v("contested")}, tmp)
        assert r.returncode == REFUTED, f"refuted must dominate contested, got {r.returncode}:\n{r.stdout}{r.stderr}"

    print("chain_verdict_test: PASS (CLEAN only on unanimous-complete; refuted/contested/missing/"
          "errored/malformed/unknown/empty all fail closed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Red fixture for the retire/immutability fix (verbatim-move + sidecar).

Proves the defect and the cure end to end against a real git history:
  - retire a claim whose live form was committed in an EARLIER commit, then run the audit;
  - the immutability check must PASS (green) because the committed line survives byte-identical in
    trace, while the OLD in-place-rewrite form FAILS it (red) — the D0-sweep incident in miniature.

Self-contained: builds a throwaway git repo, copies the real ledger tooling into it, and asserts.
Run: python3 harness/ledger/fixtures/retire_immutable_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent  # harness/ledger/


def run(cmd, cwd, stdin=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"command failed ({r.returncode}): {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def audit(root: Path):
    return subprocess.run([sys.executable, str(root / "ledger" / "audit.py"), "--root", str(root)],
                          cwd=root, capture_output=True, text=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ledger = root / "ledger"
        ledger.mkdir()
        for tool in ("model.py", "append", "audit.py", "retire"):
            shutil.copy(TOOLS / tool, ledger / tool)
            (ledger / tool).chmod(0o755)

        run(["git", "init", "-q"], root)
        run(["git", "config", "user.email", "t@t"], root)
        run(["git", "config", "user.name", "t"], root)

        # two claims: A, then B (the superseder). Distinct ts so any monotonicity stays satisfied.
        a = {"claim": "the first claim, to be retired", "source": "claude-code",
             "kind": "assertion", "status": "unverified", "check": "none"}
        aid = run([sys.executable, str(ledger / "append")], root, stdin=json.dumps(a)).stdout.strip()
        import time
        time.sleep(1.1)
        b = {"claim": "the superseding claim", "source": "claude-code",
             "kind": "assertion", "status": "unverified", "check": "none"}
        bid = run([sys.executable, str(ledger / "append")], root, stdin=json.dumps(b)).stdout.strip()

        # commit A and B — now their live lines are in git history
        run(["git", "add", "-A"], root)
        run(["git", "commit", "-q", "-m", "add claims"], root)
        committed = [l for l in (ledger / "claims.jsonl").read_text().splitlines() if l.strip()]
        a_line = next(l for l in committed if json.loads(l).get("id") == aid)

        # baseline: the committed ledger audits clean
        r0 = audit(root)
        assert r0.returncode == 0, f"baseline audit should pass:\n{r0.stdout}"

        # retire A (pointing at B) via the real tool — the verbatim-move + sidecar form
        run([sys.executable, str(ledger / "retire"), aid, "superseded by " + bid, bid], root)

        tf = ledger / "trace" / f"{aid}.jsonl"
        tlines = [l for l in tf.read_text().splitlines() if l.strip()]
        assert len(tlines) == 2, f"trace should hold the verbatim line + a sidecar, got {len(tlines)}"
        assert tlines[0] == a_line, "line 1 must be the committed claim line, BYTE-IDENTICAL"
        rec = json.loads(tlines[1])
        assert rec.get("retire_of") == aid and rec.get("retired_by") == bid \
            and rec.get("trace_reason"), f"sidecar malformed: {rec}"

        # THE CURE: retiring a previously-committed claim now audits clean (immutable passes)
        rg = audit(root)
        assert rg.returncode == 0, f"GREEN expected — verbatim-move keeps immutable happy:\n{rg.stdout}"
        assert "FAIL  immutable" not in rg.stdout, f"immutable must pass:\n{rg.stdout}"

        # THE DEFECT: the OLD in-place-rewrite form (single mutated line, no verbatim original) fails
        old = json.loads(a_line)
        old["status"] = "retired"
        old["trace_reason"] = "superseded by " + bid
        old["retired_by"] = bid
        tf.write_text(json.dumps(old, separators=(",", ":"), ensure_ascii=False) + "\n")
        rr = audit(root)
        assert rr.returncode != 0 and "FAIL  immutable" in rr.stdout, \
            f"RED expected — the old rewrite-in-place form should trip immutable:\n{rr.stdout}"

    print("retire_immutable_test: PASS (verbatim-move green, old rewrite red)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

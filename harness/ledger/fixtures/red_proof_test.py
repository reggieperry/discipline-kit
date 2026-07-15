#!/usr/bin/env python3
"""Red-first fixture for `ledger/red-proof` — it must itself pass its own bar.

Two cases, each a throwaway git repo with a BASE commit (implementation v1) and a HEAD commit
(implementation v2 + one new test):
  - GENUINE: the new test asserts the v2 behavior, so against the BASE implementation it FAILS
    → red-proof must exit 0 (red confirmed).
  - TAUTOLOGICAL: the new test asserts something independent of the implementation, so against BASE
    it PASSES → red-proof must exit 1 (it does not detect the diff).

Run: python3 harness/ledger/fixtures/red_proof_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "red-proof"
APPEND = Path(__file__).resolve().parent.parent / "append"


def run(cmd, cwd, stdin=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"setup command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def build_repo(root: Path, head_test_name: str, head_test_body: str):
    (root / "ledger").mkdir()
    shutil.copy(TOOL, root / "ledger" / "red-proof")
    (root / "ledger" / "red-proof").chmod(0o755)
    shutil.copy(APPEND, root / "ledger" / "append")
    (root / "ledger" / "append").chmod(0o755)
    # a parked slice claim so a red-proof receipt has an `about` target
    (root / "ledger" / "claims.jsonl").write_text(
        '{"claim":"slice X","subject":"kit","source":"claude-code","kind":"assertion",'
        '"status":"unverified","check":"none","id":"clm-0001","ts":"2026-07-14T00:00:00Z"}\n')
    run(["git", "init", "-q"], root)
    run(["git", "config", "user.email", "t@t"], root)
    run(["git", "config", "user.name", "t"], root)
    # BASE: implementation v1
    (root / "impl.py").write_text("def f():\n    return 1\n")
    run(["git", "add", "-A"], root)
    run(["git", "commit", "-q", "-m", "base v1"], root)
    base = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
    # HEAD: implementation v2 + the new test
    (root / "impl.py").write_text("def f():\n    return 2\n")
    (root / head_test_name).write_text(head_test_body)
    run(["git", "add", "-A"], root)
    run(["git", "commit", "-q", "-m", "head v2 + test"], root)
    return base


def red_proof(root: Path, base: str, test_name: str, ledger_about: str | None = None):
    cmd = [sys.executable, str(root / "ledger" / "red-proof"),
           "--root", str(root), "--base", base,
           "--test-cmd", f"{sys.executable} {test_name}", "--tests", test_name]
    if ledger_about is not None:
        cmd += ["--about", ledger_about, "--ledger"]
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True)


def last_claim(root: Path) -> dict:
    lines = (root / "ledger" / "claims.jsonl").read_text().splitlines()
    return json.loads(lines[-1]) if lines else {}


def main() -> int:
    genuine = "import impl\nassert impl.f() == 2, 'detects v2'\nprint('ok')\n"
    taut = "assert 1 == 1\nprint('ok')\n"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = build_repo(root, "test_impl.py", genuine)
        r = red_proof(root, base, "test_impl.py")
        assert r.returncode == 0, f"GENUINE test must pass red-proof (exit 0):\n{r.stdout}\n{r.stderr}"
        assert "red confirmed" in r.stdout, f"expected 'red confirmed':\n{r.stdout}"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = build_repo(root, "test_taut.py", taut)
        r = red_proof(root, base, "test_taut.py")
        assert r.returncode == 1, f"TAUTOLOGICAL test must FAIL red-proof (exit 1):\n{r.stdout}\n{r.stderr}"
        assert "NOT red" in r.stdout, f"expected 'NOT red':\n{r.stdout}"

    # §2: --about/--ledger files a testimony receipt on confirmed-red
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = build_repo(root, "test_impl.py", genuine)
        r = red_proof(root, base, "test_impl.py", ledger_about="clm-0001")
        assert r.returncode == 0, f"GENUINE + --ledger must exit 0:\n{r.stdout}\n{r.stderr}"
        rec = last_claim(root)
        assert (rec.get("kind") == "testimony" and rec.get("about") == "clm-0001"
                and rec.get("check") == "none" and rec.get("status") == "unverified"), \
            f"receipt must be an unverified testimony about clm-0001:\n{rec}"
        assert "red confirmed" in rec.get("claim", ""), f"receipt wording (red confirmed):\n{rec}"

    # §2: --about/--ledger records the not-red finding on a tautology (worth MORE, not less)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = build_repo(root, "test_taut.py", taut)
        r = red_proof(root, base, "test_taut.py", ledger_about="clm-0001")
        assert r.returncode == 1, f"TAUT + --ledger must exit 1:\n{r.stdout}\n{r.stderr}"
        rec = last_claim(root)
        assert rec.get("kind") == "testimony" and "NOT red" in rec.get("claim", ""), \
            f"not-red receipt must record the tautology:\n{rec}"

    # §2: no --ledger flag → no write (behavior unchanged without the flags)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = build_repo(root, "test_impl.py", genuine)
        before = (root / "ledger" / "claims.jsonl").read_text()
        red_proof(root, base, "test_impl.py")  # no --ledger
        after = (root / "ledger" / "claims.jsonl").read_text()
        assert before == after, "red-proof without --ledger must not touch the ledger"

    print("red_proof_test: PASS (genuine → red; tautological → rejected; receipts filed with --ledger)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

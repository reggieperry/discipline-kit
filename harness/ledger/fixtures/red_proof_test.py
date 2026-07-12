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

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "red-proof"


def run(cmd, cwd, stdin=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"setup command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def build_repo(root: Path, head_test_name: str, head_test_body: str):
    (root / "ledger").mkdir()
    shutil.copy(TOOL, root / "ledger" / "red-proof")
    (root / "ledger" / "red-proof").chmod(0o755)
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


def red_proof(root: Path, base: str, test_name: str):
    return subprocess.run(
        [sys.executable, str(root / "ledger" / "red-proof"),
         "--root", str(root), "--base", base,
         "--test-cmd", f"{sys.executable} {test_name}", "--tests", test_name],
        cwd=root, capture_output=True, text=True)


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

    print("red_proof_test: PASS (genuine → red confirmed; tautological → rejected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Red-first fixture for the chain trusted-base fence predicate (§18; the reframe's mechanical fence).

`trusted-base-touched.sh <base>` is the mechanical form of the worker's "touched no trusted-base
path" postcondition: it prints every path changed since <base> that falls under a trusted-base
prefix (the judge that grades the chain — the gate, the hooks, the CI config, the chain's own
agents/commands/rules) and exits 2, or exits 0 when only ordinary product paths changed. It is
rename-aware, so a move INTO the trusted base is caught too. Red against a missing/permissive
predicate.

Run: python3 harness/ledger/fixtures/chain_fence_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
LIST = KIT / "harness" / "chain" / "trusted-base"
PRED = KIT / "harness" / "chain" / "trusted-base-touched.sh"


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def commit(repo, rel, body="x\n"):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-qm", f"touch {rel}"], repo)


def main() -> int:
    assert LIST.exists(), f"trusted-base list missing: {LIST}"
    assert PRED.exists(), f"fence predicate missing: {PRED}"

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        run(["git", "init", "-q"], repo)
        run(["git", "config", "user.email", "t@t"], repo)
        run(["git", "config", "user.name", "t"], repo)
        # the fence files, where the driver would find them post-install
        (repo / ".claude" / "chain").mkdir(parents=True)
        shutil.copy(LIST, repo / ".claude" / "chain" / "trusted-base")
        shutil.copy(PRED, repo / ".claude" / "chain" / "trusted-base-touched.sh")
        commit(repo, "README.md")
        base = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        pred = str(repo / ".claude" / "chain" / "trusted-base-touched.sh")

        # 1. a product-only change => clean (exit 0)
        commit(repo, "src/widget.py", "def widget(): pass\n")
        r = run(["bash", pred, base], repo)
        assert r.returncode == 0, \
            f"a product-only change must pass the fence (exit 0), got {r.returncode}:\n{r.stdout}{r.stderr}"

        # 2. a change touching a trusted-base path (the gate) => blocked (exit 2), path named
        commit(repo, "ledger/gate.py", "print('tampered')\n")
        r = run(["bash", pred, base], repo)
        assert r.returncode == 2, \
            f"a change touching ledger/ must trip the fence (exit 2), got {r.returncode}:\n{r.stdout}{r.stderr}"
        assert "ledger/gate.py" in r.stdout, \
            f"the fence must name the touched trusted-base path, got:\n{r.stdout}"

        # 3. a rename that MOVES a file into the trusted base => caught
        base2 = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        (repo / ".claude" / "commands").mkdir(parents=True, exist_ok=True)  # git mv needs the dest dir
        mv = run(["git", "mv", "src/widget.py", ".claude/commands/sneak.md"], repo)
        assert mv.returncode == 0, f"git mv setup failed: {mv.stderr}"
        run(["git", "commit", "-qm", "move into .claude/commands"], repo)
        r = run(["bash", pred, base2], repo)
        assert r.returncode == 2 and ".claude/commands/sneak.md" in r.stdout, \
            f"a move INTO the trusted base must be caught (exit 2 + named), got {r.returncode}:\n{r.stdout}"

        # 4. touch-then-revert (F2): disable the gate, land damage, restore identical bytes. The net
        # tree diff base4..HEAD is clean, but the per-commit scan must still catch the transient tamper.
        base4 = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        orig = (repo / "ledger" / "gate.py").read_text()
        commit(repo, "ledger/gate.py", "print('disabled')\n")
        commit(repo, "src/evil.py", "BACKDOOR = True\n")
        commit(repo, "ledger/gate.py", orig)
        r = run(["bash", pred, base4], repo)
        assert r.returncode == 2 and "ledger/gate.py" in r.stdout, \
            f"touch-then-revert of the gate must be caught by the per-commit scan (exit 2), got {r.returncode}:\n{r.stdout}"

        # 5. bad base ref (F3): a fence that cannot resolve its input fails CLOSED, not open.
        r = run(["bash", pred, "deadbeefdeadbeefdeadbeef"], repo)
        assert r.returncode == 2, f"an unresolvable base must fail closed (exit 2), got {r.returncode}"

        # 6. empty/gutted list (F4): a list that protects nothing fails CLOSED.
        base6 = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        commit(repo, "ledger/gate.py", "print('touch')\n")
        (repo / "empty-list").write_text("# only comments\n\n")
        r = run(["bash", pred, base6, str(repo / "empty-list")], repo)
        assert r.returncode == 2, f"an empty list must fail closed (exit 2), got {r.returncode}"

        # 7. uncommitted trusted-path edit (F2/C): a dirty working tree is tamper even with a clean diff.
        base7 = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        (repo / ".githooks").mkdir(exist_ok=True)
        (repo / ".githooks" / "pre-commit").write_text("exit 0\n")  # dirty, uncommitted
        r = run(["bash", pred, base7], repo)
        assert r.returncode == 2 and ".githooks/" in r.stdout, \
            f"an uncommitted trusted-path edit must be caught (exit 2), got {r.returncode}:\n{r.stdout}"

    print("chain_fence_test: PASS (prefix/rename core + fail-closed on bad-base/empty-list, "
          "touch-then-revert, and uncommitted tamper)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

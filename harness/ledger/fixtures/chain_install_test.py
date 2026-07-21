#!/usr/bin/env python3
"""Red-first fixture for the chain install plumbing (§18 chain-core; the CI-neutral base).

The five chain agents (harness/agents/chain-*.md) and the /chain command (harness/commands/chain.md)
must install into a target repo's .claude/agents/ and .claude/commands/ under an explicit --with-chain
opt-in, and a base install (no flag) must install NEITHER — the chain is default-off and the base stays
CI-neutral (auto-merge is a separate add-on that alone touches .github/ and branch protection). Red
against the shipped installer, which knows no --with-chain flag and installs neither agents nor commands.

Run: python3 harness/ledger/fixtures/chain_install_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
INSTALLER = KIT / "install-harness.sh"

AGENTS = [f"chain-{role}" for role in ("planner", "worker", "tester", "reviewer", "finalizer")]


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def fresh_repo(td):
    repo = Path(td)
    run(["git", "init", "-q"], repo)
    run(["git", "config", "user.email", "t@t"], repo)
    run(["git", "config", "user.name", "t"], repo)
    (repo / "README.md").write_text("x\n")
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-qm", "init"], repo)
    return repo


def main() -> int:
    # 1. --with-chain installs the five agents + the /chain command.
    with tempfile.TemporaryDirectory() as td:
        repo = fresh_repo(td)
        r = run(["bash", str(INSTALLER), "--dir", str(repo), "--with-chain"])
        assert r.returncode == 0, f"install --with-chain must succeed:\n{r.stdout}\n{r.stderr}"
        for a in AGENTS:
            p = repo / ".claude" / "agents" / f"{a}.md"
            assert p.exists() and p.read_text().strip(), \
                f"--with-chain must install the chain agent: .claude/agents/{a}.md missing"
        cmd = repo / ".claude" / "commands" / "chain.md"
        assert cmd.exists() and cmd.read_text().strip(), \
            "--with-chain must install the /chain command: .claude/commands/chain.md missing"
        # the installed driver is the real one (a distinctive marker), not a stub
        assert "parent-session driver" in cmd.read_text(), \
            "the installed chain.md must be the real driver, not a stub"

    # 2. A base install (no flag) installs NEITHER — chain is opt-in, base stays CI-neutral.
    with tempfile.TemporaryDirectory() as td:
        repo = fresh_repo(td)
        r = run(["bash", str(INSTALLER), "--dir", str(repo)])
        assert r.returncode == 0, f"base install must succeed:\n{r.stdout}\n{r.stderr}"
        assert not (repo / ".claude" / "agents").exists(), \
            "base install must NOT install chain agents (chain is opt-in via --with-chain)"
        assert not (repo / ".claude" / "commands").exists(), \
            "base install must NOT install the /chain command (chain is opt-in)"

    print("chain_install_test: PASS (--with-chain installs 5 agents + /chain; base install installs neither)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

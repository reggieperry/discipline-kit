#!/usr/bin/env python3
"""Regression fixture for `install.sh --refresh-rules`.

An already-installed repo does not pick up rule updates on its own — the per-project rules copy is a
manual step. `install.sh --refresh-rules [--dir <repo>]` re-copies `claude-project/rules/*.md` into an
existing `.claude/rules/`. This pins that behavior: a stale shipped rule is overwritten with the kit's
current copy, a rule the repo authored under another name is left alone, the repo's `CLAUDE.md` is
never touched, and the flag refuses (non-zero) when there is no `.claude/rules` to refresh.

Added after the flag shipped — a regression pin, not red-first: it fails if `--refresh-rules` is
removed or stops copying (the stale marker would survive), or if it starts clobbering a repo-authored
rule or the repo's `CLAUDE.md`.

Run: python3 harness/ledger/fixtures/refresh_rules_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
INSTALLER = KIT / "install.sh"
CANARY_RULE = "writing-style.md"  # a rule the kit actually ships; the refresh must overwrite a stale copy


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main() -> int:
    current = (KIT / "claude-project" / "rules" / CANARY_RULE).read_text()

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        rules = repo / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / CANARY_RULE).write_text("STALE — pre-refresh\n")        # a shipped rule, out of date
        (rules / "repo-local-rule.md").write_text("repo authored — keep me\n")  # not shipped; must survive
        (repo / "CLAUDE.md").write_text("repo CLAUDE.md — do not touch\n")       # must be untouched

        r = run(["bash", str(INSTALLER), "--refresh-rules", "--dir", str(repo)])
        assert r.returncode == 0, f"--refresh-rules must succeed:\n{r.stdout}\n{r.stderr}"

        assert (rules / CANARY_RULE).read_text() == current, \
            "--refresh-rules must overwrite a stale shipped rule with the kit's current copy"
        assert (rules / "repo-local-rule.md").read_text() == "repo authored — keep me\n", \
            "--refresh-rules must not delete a rule the repo authored under another name"
        assert (repo / "CLAUDE.md").read_text() == "repo CLAUDE.md — do not touch\n", \
            "--refresh-rules must never touch the repo's CLAUDE.md"

    # the guard: it is a refresh, not a first install — refuse when there is no .claude/rules
    with tempfile.TemporaryDirectory() as bare:
        r2 = run(["bash", str(INSTALLER), "--refresh-rules", "--dir", bare])
        assert r2.returncode != 0, \
            "--refresh-rules must refuse (non-zero) when the target has no .claude/rules to refresh"

    print("refresh_rules_test: PASS (stale rule refreshed; repo-authored rule + CLAUDE.md untouched; guard fires)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

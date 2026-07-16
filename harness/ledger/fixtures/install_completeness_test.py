#!/usr/bin/env python3
"""Red-first fixture for install-completeness (§14.49 finding 2 / v1.3.5).

The installed docs (operators-manual, the ledger-write skill, the ledger README) reference
`report-conventions.md` and `check.sh.example`. A fresh install must therefore vendor them into the
target's `ledger/`, or a fresh instance working from the installed repo alone cannot find the
conventions it is pointed at. Red against the shipped installer, which copies the tooling and
operators-manual but leaves these two referenced docs absent.

Run: python3 harness/ledger/fixtures/install_completeness_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
INSTALLER = KIT / "install-harness.sh"

# Docs the installed operators-manual / skills reference by name, which must be present post-install.
REFERENCED_DOCS = ["ledger/report-conventions.md", "ledger/check.sh.example"]


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        run(["git", "init", "-q"], repo)
        run(["git", "config", "user.email", "t@t"], repo)
        run(["git", "config", "user.name", "t"], repo)
        (repo / "README.md").write_text("x\n")
        run(["git", "add", "-A"], repo)
        run(["git", "commit", "-qm", "init"], repo)

        r = run(["bash", str(INSTALLER), "--dir", str(repo)])
        assert r.returncode == 0, f"install must succeed:\n{r.stdout}\n{r.stderr}"

        for rel in REFERENCED_DOCS:
            p = repo / rel
            assert p.exists() and p.read_text().strip(), \
                f"a referenced doc must be vendored into the target on install: {rel} is missing"

        # and its content is the real doc (not a stub) — distinctive markers of report-conventions.md
        rc = (repo / "ledger" / "report-conventions.md").read_text()
        assert "red-proof" in rc and "observed red" in rc, \
            "the vendored report-conventions.md must be the real doc, not a stub"

    print("install_completeness_test: PASS (report-conventions.md + check.sh.example vendored on install)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

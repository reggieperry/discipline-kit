#!/usr/bin/env python3
"""Red-first fixture for install-harness.sh --upgrade.

A real first install, then a kit-owned file staled and a repo-owned file added. `--upgrade` must:
overwrite the kit-owned file with the kit's current version, leave the repo-owned file byte-untouched,
and write a ledger/VERSION stamp. Red against the shipped installer (which rejects --upgrade).

Run: python3 harness/ledger/fixtures/install_upgrade_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
INSTALLER = KIT / "install-harness.sh"
KIT_AUDIT = KIT / "harness" / "ledger" / "audit.py"


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
        assert r.returncode == 0, f"first install must succeed:\n{r.stdout}\n{r.stderr}"

        # stale a kit-owned file; add a repo-owned check.sh
        (repo / "ledger" / "audit.py").write_text("# OLD STALE VERSION\n")
        (repo / "ledger" / "check.sh").write_text("# REPO OWNED — do not touch\n")

        run(["bash", str(INSTALLER), "--dir", str(repo), "--upgrade"])
        audit_after = (repo / "ledger" / "audit.py").read_text()
        assert "# OLD STALE VERSION" not in audit_after, \
            f"--upgrade must overwrite the stale kit-owned audit.py"
        assert audit_after == KIT_AUDIT.read_text(), "upgraded audit.py must equal the kit's current version"
        assert (repo / "ledger" / "check.sh").read_text() == "# REPO OWNED — do not touch\n", \
            "repo-owned check.sh must be left byte-untouched"
        v = repo / "ledger" / "VERSION"
        assert v.exists() and v.read_text().strip(), "a ledger/VERSION stamp must be written"

    print("install_upgrade_test: PASS (kit-owned upgraded; repo-owned untouched; VERSION stamped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

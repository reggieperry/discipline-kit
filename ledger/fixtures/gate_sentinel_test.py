#!/usr/bin/env python3
"""Red-first fixture for gate.py's env-override sentinel guard.

`LEDGER_CHECK_CMD` / `LEDGER_CODE_EXTS` are honored ONLY when `ledger/.test-mode` exists — a
gitignored sentinel that only harness-verify.sh and the fixtures create. Without it the override is
ignored, closing the cheap bypass an automated collaborator could otherwise take (inject a fake
check). Red against a gate that honors the env unconditionally.

Run: python3 harness/ledger/fixtures/gate_sentinel_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / "gate.py"


def load_gate(root: Path):
    (root / "ledger").mkdir(parents=True, exist_ok=True)
    dst = root / "ledger" / "gate.py"
    shutil.copy(GATE, dst)
    spec = importlib.util.spec_from_file_location("gate_under_test", dst)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    os.environ["LEDGER_CHECK_CMD"] = "echo pwned"
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)  # bare temp repo: no check.sh, no build markers, no sentinel
            g = load_gate(root)
            assert g.check_command() is None, \
                f"LEDGER_CHECK_CMD must be IGNORED without the sentinel, got {g.check_command()!r}"
            (root / "ledger" / ".test-mode").write_text("")
            assert g.check_command() == ["echo", "pwned"], \
                f"LEDGER_CHECK_CMD must be honored WITH the sentinel, got {g.check_command()!r}"
    finally:
        del os.environ["LEDGER_CHECK_CMD"]
    print("gate_sentinel_test: PASS (env override ignored without sentinel, honored with it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env bash
# scripts/check.sh — the kit's own mechanical check, run by the pre-commit hook.
#
# This is what a green commit means: a machine ran the suite, not that the author said so. It is
# deliberately NOT part of any claim apparatus — it takes no arguments, writes no record, and its
# only output is an exit code. Formerly this ran inside the dev-ledger gate; the ledger was removed
# 2026-07-30 after its own record showed it contributed one bit the compiler already returns, and
# the check was kept because it is the part that was catching things.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scrub-gate.sh
python3 harness/rule_grades.py
python3 harness/fixtures/rule_grades_test.py
python3 reference/test_sdlc_gate.py
python3 harness/algebra/validate_note.py

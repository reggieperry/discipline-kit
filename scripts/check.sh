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
bash harness/shellcheck_all.sh

# The em-dash rule this kit's own writing-style.md states. It was spaced here until 2026-08-03 and
# is now closed, matching the voicing canon; existing prose is grandfathered by
# scripts/em-dash-exempt.txt rather than rewritten. Without this the rule would be a preference in
# the one repository that authors it, which is how it drifted from the canon in the first place.
bash scripts/em-dash-check.sh

# ADR-0001/D1's edge court: refs/chain/* is per-instance run state; a remote refspec or
# mirror covering it silently resets or publishes in-flight chains. Live from the day the
# ADR landed, sequencer or not.
bash scripts/chain-refspec-check.sh
python3 harness/rule_grades.py
python3 harness/fixtures/rule_grades_test.py
python3 harness/fixtures/scope_check_test.py
python3 harness/fixtures/comment_shape_test.py
python3 harness/comment_shape.py --dir harness --exclude fixtures
python3 reference/test_sdlc_gate.py
python3 harness/algebra/validate_note.py

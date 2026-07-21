#!/usr/bin/env bash
# The kit's own mechanical check — dogfooding the loop it ships. Runs the acceptance suite over the
# SOURCE (harness/, reference/), the same steps as .github/workflows/ci.yml minus the slow installer
# fixture. A staged .py/.sh fires this via the gate; a non-zero exit blocks the commit.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scrub-gate.sh
sh harness/ledger/board.sh --selftest
python3 harness/ledger/fixtures/retire_immutable_test.py
python3 harness/ledger/fixtures/red_proof_test.py
python3 harness/ledger/fixtures/tdd_precedence_test.py
python3 harness/ledger/fixtures/gate_sentinel_test.py
python3 harness/ledger/fixtures/java_plumbing_test.py
python3 harness/ledger/fixtures/squash_precedence_test.py
python3 harness/ledger/fixtures/memory_index_test.py
python3 harness/ledger/fixtures/install_completeness_test.py
python3 harness/ledger/fixtures/inbound_guard_test.py
python3 harness/ledger/fixtures/interchange_test.py
python3 harness/ledger/fixtures/authoring_artifacts_test.py
python3 harness/ledger/fixtures/chain_install_test.py
python3 harness/ledger/fixtures/gate_signing_test.py
python3 harness/ledger/fixtures/gate_forgery_sweep_test.py
python3 harness/ledger/fixtures/gate_copies_identical_test.py
python3 harness/ledger/fixtures/model_laws_test.py
python3 harness/ledger/fixtures/chain_fence_test.py
python3 harness/ledger/fixtures/chain_acceptance_test.py
python3 harness/ledger/fixtures/chain_verdict_test.py
python3 reference/test_sdlc_gate.py
python3 harness/algebra/validate_note.py

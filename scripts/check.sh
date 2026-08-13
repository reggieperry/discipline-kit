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

# ADR-0002's live courts: the revert premise proven per commit, and a chain profile
# enabling autonomous merge without push = "never" fails the build.
bash scripts/revert-sufficiency-check.sh
bash scripts/merge-posture-check.sh

# ADR-0002/D3.2's court, named future in that record and live from 2026-08-12: a chain profile
# whose trusted_base omits its own file, the CI workflows, or any path this file invokes or reads
# is a cage with a hole in it. The required set is derived from THIS file's invocations rather
# than hand-kept, so adding a check below adds it to the requirement automatically.
bash scripts/profile-check.sh

# ADR-0001/D1's edge court: refs/chain/* is per-instance run state; a remote refspec or
# mirror covering it silently resets or publishes in-flight chains. Live from the day the
# ADR landed, sequencer or not.
bash scripts/chain-refspec-check.sh
python3 harness/rule_grades.py
python3 harness/fixtures/authoring_artifacts_test.py
# The story graph's fixture and checker, both on the commit path since 2026-08-12, when the
# coverage triage closed the graph. A new ADR without stories or waivers, a dangling dep, or
# a cycle fails the commit that adds it; the current denominators print on every run.
python3 harness/fixtures/chain_graph_test.py
python3 harness/chain_graph.py
python3 harness/fixtures/authoring_artifacts_fixture_test.py
python3 harness/fixtures/rule_grades_test.py
python3 harness/fixtures/scope_check_test.py
# The scrub gate runs first in this file and had never been observed firing. Its fixture points
# it at throwaway trees with planted tokens, so a tier that stops scanning is caught here rather
# than by a private identifier reaching a tarball.
python3 harness/fixtures/scrub_gate_test.py
# The profile court's own fixture, on the commit path for the same reason every other one is:
# the court passes against this repository, and a court only ever observed passing is not known
# to be watching. Its trees plant each omission ADR-0002/D3.2 names.
python3 harness/fixtures/profile_check_test.py
# The postcondition loader's fixture, on the commit path; the loader itself deliberately is not,
# for the reason the chain graph's checker was held back until its triage closed. The loader
# resolves examiner material from the profile's out-of-tree `pinned_root`, that directory is
# created by the machine-hardening checklist, and the checklist has not run on any machine here,
# so the loader VOIDs, which on the commit path would block every commit rather than report a
# defect. It wires the day the root exists. The fixture needs no such root: it builds its own.
python3 harness/fixtures/loader_test.py
# The seam's fixture, wired for the same reason and with the same boundary: `advance.py` and
# `attempt.py` resolve examiner material through the loader, so they VOID on every machine until
# the pinned root exists, and a tool that VOIDs on the commit path blocks every commit rather than
# reporting a defect. The fixture builds its own throwaway roots and repositories, so it needs
# neither the pinned root nor a chain to be running.
python3 harness/fixtures/advance_test.py
# ADR-0001/D2's court: the denial probe replayed against the real advance seam. A did-nothing
# tree must FAIL, a known-good tree must PASS, and an examiner that cannot execute must read
# could-not-run with no ref written—never a pass. The fixture builds its own throwaway pinned
# roots and repositories, so like the seam's other fixtures it needs no pinned root to exist.
python3 harness/fixtures/seam_court_test.py
# The sequencer core's fixture, wired on the same boundary: `core.py` reads a chain profile whose
# pinned_root the machine-hardening checklist has not created, so its start-up gate VOIDs on every
# machine here and the CLI stays off the commit path. The fixture builds its own profiles and
# repositories, so it needs neither.
python3 harness/fixtures/core_test.py
# The invocation layer's fixture, on the same boundary as the loader's and the seam's: the
# invoke CLI reads the profile's pinned root and VOIDs on every machine until the hardening
# checklist creates it, so only the fixture is wired. It builds its own profiles, repositories,
# pinned material and stub harness binaries — the real `claude` is never invoked here — and it
# demonstrates the post-batch transcript audit red and green on synthetic streams.
python3 harness/fixtures/invoke_test.py
# The merge stage's fixture, on the same boundary as the seam's and the invoke layer's: the
# merge CLI reads the profile's pinned root and VOIDs on every machine until the hardening
# checklist creates it, so only the fixture is wired. It builds its own dedicated clones, bare
# local remotes, pinned material and stub commit-check/forge binaries — no real forge is ever
# invoked — and it asserts the record's forged-ref residue line verbatim, per posture.
python3 harness/fixtures/merge_test.py
# ADR-0001/D5's court, named future in that record because it "would grep nothing and prove
# nothing" until a sequencer source existed. Five exist now, so unlike the runtime it wires
# directly: it reads sources rather than a pinned root, and it passes today with its denominators
# printed on every run.
python3 harness/sequencer_source_check.py
# ADR-0004/D1's other court, the post-batch transcript audit (harness/transcript_audit.py), stays
# off the commit path for the loader's reason: it reads the phase transcripts a batch wrote, no
# chain has run on this machine, and an empty corpus reads could-not-run, never clean. It wires
# the day a batch writes transcripts; until then invoke_test.py above is its red-and-green
# demonstration.
python3 harness/fixtures/comment_shape_test.py
python3 harness/comment_shape.py --dir harness --exclude fixtures
python3 reference/test_sdlc_gate.py
python3 harness/algebra/validate_note.py

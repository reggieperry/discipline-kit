---
id: STORY-0011
title: Fail-closed start-up: the sequencer refuses to run unposture-d
deps: [STORY-0006]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0003
decisions: [D5]
group: A
---

# Problem / Context

ADR-0003/D5: the sequencer refuses to run—could-not-run, loudly—on an absent or unparseable profile, no declared terminal act, or an unset or incomplete trusted_base. The refusal path is code that does not exist.

Grounding: `docs/adrs/ADR-0003-sequencer-obligations.md`, D5. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

The start-up gate in the sequencer core, reading the profile as ADR-0002 shapes it, with a refusal fixture per condition.

# Scope and non-goals

In scope:

- the start-up refusals and their fixtures

Out of scope:

- the core's derivation (STORY-0006), the profile itself (STORY-0003)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] each refusal condition reads could-not-run with the condition named—verified by `one known-bad fixture per condition`, which STORY-0006 already built: the start-up block of `harness/fixtures/core_test.py` (one clean case, thirteen refusal cases), whose `judge` requires exit 2 AND the condition's own marker in the output, so the exit code never stands alone. Audited 2026-08-12 against ADR-0003/D5's text condition by condition, each one also re-driven by hand against `core.py startup` on a throwaway profile; the mapping is the discharge record below. Build residue: zero—no new fixture was owed, and none was added

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [x] The assertion count is not reduced versus the merge-base. This story lands records only—no fixture, check, or source changed—so the suite is byte-identical to the merge-base, and `core_test.py` runs 56 of 56 either way.
- [x] No new suppressions are introduced versus the merge-base. The diff touches this story file and `CHANGELOG.md` and nothing else.
- [x] No new skipped tests versus the merge-base. Same diff; the fixture has no skip mechanism and every case runs on every invocation.

# Risks and rollback

- Risk: a sequencer that runs unguarded while reporting progress—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- Discharged 2026-08-12 on `feat/startup-refusals` by audit rather than by build: STORY-0006 had
  already landed the gate and one known-bad fixture per condition, so this story's deliverable is
  the discharge record below and the audit behind it. The problem statement's "the refusal path
  is code that does not exist" was true at allocation and false by the time the story was picked
  up—STORY-0006 merged in between.

# Discharge record

Closure by audit, 2026-08-12: STORY-0006, merged at this branch's base, built the start-up gate
(`harness/chain/core.py`, the `startup` act) and its per-condition fixtures. The audit read D5's
text, ran the start-up cases (56 of 56 in `harness/fixtures/core_test.py`), and re-drove each
condition by hand against `core.py startup` on throwaway profiles: every refusal exits
2—could-not-run under ADR-0003/D2's exit contract—and names its condition on stderr
(`core: VOID: <condition>: …`), so the exit code alone never has to tell them apart. One line
per D5 condition, as the record states them:

- the chain profile is absent → `profile-absent-2`, asserting exit 2 and `profile-absent` named
- the chain profile is unparseable → `profile-unparseable-2` (malformed TOML) and
  `profile-not-a-file-2` (a directory at the profile path), each asserting exit 2 and
  `profile-unparseable` named
- no terminal act is declared → `terminal-undeclared-2`, asserting exit 2 and
  `terminal-undeclared` named; `terminal-nested-2` pins that a declaration below the top level
  does not count, and `terminal-unknown-2` refuses an act ADR-0002/D1 does not name, asserting
  `terminal-unknown` named
- `trusted_base` is unset → `trusted-base-unset-2` (no key) and `trusted-base-empty-2` (an
  empty list), each asserting exit 2 and `trusted-base-unset` named
- `trusted_base` omits the D4 paths → `trusted-base-incomplete-2`, asserting exit 2 and
  `trusted-base-incomplete` named; the required set is `core.py`'s `SEQUENCER_SOURCES`, the
  four `harness/chain/*.py` modules that are the sequencer's in-repo definition today

Beyond D5's named list, the same gate refuses under its schema clause ("the profile keys are
read as ADR-0002 (Proposed) shapes them"), and those arms were audited with it: the ADR-0002/D1
pairing (`push-missing-2` and `push-unpaired-2`, each naming `push-unpaired`) and the pinned
root (`pinned-root-unset-2` naming `pinned-root`, `pinned-root-in-worktree-2` naming the
inside-a-working-tree refusal)—a missing `pinned_root` being the concern STORY-0004's recorded
judgment call routed to this story. D5 names no condition beyond these: neither
`harness_version` nor the settings sources appear anywhere in it (the settings-source pin is
ADR-0004/D3's, carried by STORY-0006's decoy case and STORY-0012).

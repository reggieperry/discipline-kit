---
id: STORY-0006
title: The sequencer core: fail-closed start-up and re-derived position
deps: [STORY-0001, STORY-0003, STORY-0005]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0001
decisions: [D1, D5]
group: A
---

# Problem / Context

The position-derivation function over `refs/chain/<story>/attempt-<a>/phase-<n>`, the re-walk rule's atomic deletion, and the resume path reading only session ids and liveness do not exist.

Grounding: `docs/adrs/ADR-0001-advancement-re-derived.md`, D1 and D5. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

The derivation function and re-walk deletion as pinned code; the resume path; the fixture repository where derived position must equal planted refs; the grep-shaped source check for D5.

# Scope and non-goals

In scope:

- derivation, re-walk, resume reads, both courts

Out of scope:

- start-up refusal detail (STORY-0011), phases themselves

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] derived position equals planted refs across the fixture repository—verified by `the position fixture named in ADR-0001's Falsification section`, which is the thirteen `position-*` cases of `harness/fixtures/core_test.py`: a throwaway repository carries planted refs and the derived position must equal them across contiguous, gapped, missing-first, multi-attempt, empty, foreign-ref, attempt-with-no-phase, non-integer-phase, phase-zero, non-integer-attempt, another-story and hostile-`GIT_DIR` permutations, plus a `--repo` that is no working tree. The gap permutations are the ones that discriminate: the derivation returns the highest CONTIGUOUS phase and names the hole as an integrity finding, so the case fails against a derivation that reads the highest ref present
- [x] no sequencer source reads the log, status frontmatter, or stream verdict fields for control flow—verified by `the D5 grep-shaped source check`, which is `harness/sequencer_source_check.py`, wired into `scripts/check.sh` and passing today over four modules with its denominators printed (files, code lines, comment and docstring lines dropped, patterns, admitted readers). Eight patterns run over a comment-stripped and docstring-stripped view; the two stream-shaped ones are exempt inside the one admitted reader and the verdict-shaped ones are exempt nowhere, including inside it; a ninth conjunct reads the reader's declared `ADMITTED_KEYS` as data, since widening that set widens what the runtime admits without changing a line of control flow. Fifteen `source-*` cases in `core_test.py` plant one violation per pattern, the two clean shapes, the prose-only shape, and both could-not-run states
- [x] the sequencer's own invocation pins its settings sources, so a user-scope hook cannot inject into the run it drives—verified by `an invocation fixture run with a decoy user-scope SessionStart hook, asserting the hook's marker is absent from every phase transcript the run produced (the sequencer itself is a script under ADR-0004/D1 and has no transcript)`, SCOPED TO WHAT THE CORE CAN PIN TODAY and no further: `core_test.py`'s `decoy-user-hook` runs the core with `HOME` redirected to a fake user scope carrying a SessionStart hook, and with a `claude` on PATH that writes the hook's marker if it is ever invoked. The core produces zero phase transcripts because it composes no invocation at all, so the marker is absent and the count of harness invocations is zero, with a git spy beside it logging invocations to prove the shimmed PATH was live rather than ignored. The per-invocation settings audit is STORY-0012's criterion of the same name, cross-referenced there

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [x] The assertion count is not reduced versus the merge-base. Every existing fixture is untouched and `core_test.py` is a net add of 56 cases; `scripts/check.sh` gains two invocations and loses none.
- [x] No new suppressions are introduced versus the merge-base, with one disclosure rather than a claim: `core.py` carries two `# noqa: E402` markers on its `import attempt` and `import loader` lines, copied verbatim from the identical import shape in `advance.py` and `attempt.py`, which insert their own directory on `sys.path` first. No linter on the commit path reads them, so they suppress nothing that runs here; they are named because a marker nobody reads is still a marker.
- [x] No new skipped tests versus the merge-base. The fixture has no skip mechanism and every case runs on every invocation.

# Risks and rollback

- Risk: a derivation bug silently replays or skips a phase—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- The settings-source criterion comes from `docs/probe/D7-headless-probe-2026-08-12.md`: user-scope
  SessionStart hooks fire in headless runs, so an unattended run inherits whatever the operator's
  user-level hooks inject unless the invocation pins its sources. STORY-0005 carries the same
  criterion for the phase invocations; this one is the sequencer's own.
- Discharged 2026-08-12 on `feat/chain-core`: `harness/chain/core.py` (the start-up gate, the
  position derivation, the resume read and the attempt boundary), `harness/sequencer_source_check.py`
  (ADR-0001/D5's court, which that record left unclaimed because it "would grep nothing and prove
  nothing" until a sequencer source existed), and their 56-case fixture
  `harness/fixtures/core_test.py`, with both the fixture and the check wired into `scripts/check.sh`.
  The core CLI itself stays off the commit path for the loader's reason: its start-up gate reads a
  `pinned_root` the machine-hardening checklist has not created on any machine here, so it VOIDs
  everywhere, and a tool that VOIDs on the commit path blocks every commit rather than reporting a
  defect. The check has no such dependency, which is why it wires.
- POSITION SEMANTICS, and the gap rule is the decision inside them. Position is the highest
  CONTIGUOUS phase from 1 within the current attempt, where the current attempt is the highest
  attempt number any ref under the story mentions—including a ref that is not a phase, so an
  attempt that started and completed nothing never has its number reused. A phase ref standing
  above a missing one does not raise the position: the hole is a named integrity finding, and
  `position`, `resume` and `start-attempt` each exit could-not-run on any finding rather than
  deriving from a namespace nobody can account for. The asymmetry is the reason: re-running a
  phase that already has a ref costs a phase, and skipping one signs work no postcondition ever
  graded at the seam. Two ref shapes are distinguished on purpose. A ref under the story that is
  not phase-shaped—a park ref, a note under an attempt—is reported as foreign and is not a
  finding, matching the re-walk's own "not a phase ref, left alone" stance. A ref that IS
  phase-shaped but whose attempt or phase component is not a positive integer (`phase-x`,
  `phase-0`, `attempt-one/phase-1`) is a finding, because something wrote into the namespace in a
  shape the re-walk rule cannot order.
- THE CLEARING-AUTHORITY DECISION this story part-owns, recorded here with its reasoning because
  `harness/chain/attempt.py`'s docstring names STORY-0006 and STORY-0011 as where it is settled.
  ADR-0004/D2 says every attempt start clears the pinned worktree path; `attempt.py` refuses to
  delete a directory git does not know about, and the tension is real: a phase that crashed
  leaving an unregistered directory behind wedges every retry of that story until an operator
  intervenes. The decision is that on a fresh attempt the sequencer MAY force-clear an
  unregistered on-disk path at the pinned location it owns, after recording what it found, and
  `attempt.py` is UNCHANGED—its refusal stays correct for what it is, a tool acting on a path a
  caller named. What makes the authority safe in `core.py` is that no caller names a path: the
  core COMPOSES it from the pinned worktree root, the story id and the attempt number, so there is
  no mistyped argument to act on. Three conditions are checked before anything is removed, and
  each has a case: the path is the one this attempt composes; it is not a symlink, because what a
  link names is not the sequencer's; and no git working tree contains its parent, so graded and
  examiner material are structurally out of reach. An inventory of the directory's contents is
  printed before the removal, so an unattended clearing leaves a record of what was destroyed.
  THE RESIDUE IS DISCLOSED RATHER THAN CLOSED: a directory a human created at exactly
  `<root>/<story-id>/attempt-<n>` is deleted. That path shape is not one anybody types by
  accident, and the alternative is the availability failure D2 named. STORY-0011 gets the fixture
  for the refusal conditions.
- WHAT STORY-0011 INHERITS. The start-up gate is built here because start-up is where it runs, and
  its six conditions each have one case already (`profile-absent`, `profile-unparseable` in two
  shapes, `terminal-undeclared` including the nested-table refusal, `terminal-unknown`,
  `push-unpaired` in two shapes, `trusted-base-unset` in two shapes, `trusted-base-incomplete`,
  and `pinned-root` unset or inside a working tree). What is left for that story is the refusal
  path's own depth: profile shapes this build does not enumerate, the completeness half of
  ADR-0003/D5 beyond the sequencer's own sources, and the operator-facing wording of each
  refusal. The pairing table is reimplemented from ADR-0002/D1 rather than imported, because
  `scripts/merge-posture-check.sh` holds it inside a heredoc and there is nothing to import; that
  court remains the authority on the commit path and this is the same rule read at start-up.
- The 2026-08-03 mutation lesson was applied: thirteen mutations, thirteen killed, each one
  compiled with `py_compile` before its result was believed, and each one named the cases that
  objected. Two SURVIVED on the first pass and both were real gaps rather than bad mutations—the
  symlink condition was masked by `shutil.rmtree` refusing symlinks on its own, so the case was
  passing for a reason that was not the code under test, and the ordering property of the resume
  read was unobservable because the value is dropped on the refusal path either way. Closed by
  asserting each refusal's own condition name rather than the generic marker, and by having the
  one admitted reader announce that it is reading.

---
id: STORY-0016
title: Build the unattended-run envelope—cron, locking, budget, gate-enforced at runtime
deps: [STORY-0013, STORY-0015]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0005
decisions: [D7]
group: A
---

# Problem / Context

The chain runs one story per `sequencer.py run` invocation, driven by hand. There is no unattended
runner: nothing schedules a run, prevents two runs colliding on one story, or bounds the spend of a
run no human is watching. ADR-0005/D7 permits building this envelope ahead of the hardening, on the
condition that its runner enforces the unattended-start gate at runtime so a built envelope on an
unhardened host refuses to run rather than running unhardened.

Grounding against HEAD:

- `harness/chain/sequencer.py`—the per-story driver the envelope wraps: one `run` act, no
  scheduling, no locking, no budget, no gate call.
- `docs/adrs/ADR-0005-containment-posture.md`, D7—the four conditions this runner must meet: the
  start gate built and fixture-tested first (STORY-0015); the runner invokes it first, as the
  run-user, and starts only on an affirmative exit-0 clear (an absent, non-executable, or unreadable
  gate is a refuse condition, never a missing result read as clear); the runner integrity-checks the
  gate out-of-band (root-owned, not run-user- or operator-writable) before trusting clear, because a
  stubbed gate cannot run its own examiner-ownership check; and build-and-test runs against fixtures
  and stubbed gate results only, never a live unattended run and never a real-gate stub-to-clear.
- `INSTALL-HARDENING.md`, Step 6—the gate STORY-0015 builds, which this runner calls.

# Proposed approach

An unattended entry point (a script the operator schedules by cron or systemd timer) wrapping
`sequencer.py run`, with four parts:

- **The gate call, first and fail-closed.** Before anything, integrity-check the gate binary
  (root-owned, not run-user- or operator-writable) and invoke it as the run-user; start the run
  only on exit 0 clear. A nonzero exit, an absent or non-executable or unreadable gate, or a
  failed integrity check all refuse, loudly, exit 2. This is D7's runtime enforcement and is the
  story's spine.
- **Per-story locking.** A run holds an exclusive lock on its story id (a lockfile or `flock`), so
  a second invocation on the same story blocks or refuses rather than racing the refs and worktrees.
- **A budget meter.** A recorded spend ceiling per run; the runner stops launching phases when the
  ceiling is reached, and the stop is a named, recorded outcome, never a silent cap.
- **The sequencer call.** On a clear gate and an acquired lock and budget remaining, run
  `sequencer.py run` for the story, relaying its exit.

Mirror `sequencer.py`'s style: cheap refusals first, the gate and lock before any spend, every
subprocess through the scrubbed env. The whole thing is testable against fixtures—a throwaway
pinned root, gate stubs returning each of clear, exit 2, and absent, a fake budget meter, and two
concurrent invocations for the lock—exactly as STORY-0006 and STORY-0011 test against planted holes.

# Scope and non-goals

In scope:

- the unattended entry point, its gate enforcement, its locking, its budget meter, and their fixtures

Out of scope:

- the start gate itself (STORY-0015, a hard dependency)
- applying the hardening (INSTALL-HARDENING.md, operator work)
- any live unattended run against the reference host—the runner is built and tested against fixtures
  and stubbed gate results only, per D7 condition 4; a real unattended run waits on the hardening
- the cron/systemd schedule entry itself (operator configuration; the runner is what it invokes)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] the runner starts the sequencer only on an exit-0 clear from the gate; a gate returning
      exit 2, or absent, non-executable, or unreadable, refuses without starting the sequencer—verified
      by `the envelope fixture's gate-result cases (stubs returning clear, exit 2, and absent),
      asserting the sequencer stub is invoked only on clear`
- [ ] a gate that is not root-owned or is run-user- or operator-writable is refused before its
      result is trusted—verified by `the envelope fixture's gate-integrity known-bad case (a
      writable gate stub returning clear is still refused)`
- [ ] two concurrent invocations on one story do not both run: the second blocks or refuses—verified
      by `the envelope fixture's concurrent-invocation case asserting exactly one sequencer run`
- [ ] a run reaching its budget ceiling stops launching phases with a named recorded outcome, not a
      silent cap—verified by `the envelope fixture's budget-ceiling case asserting the stop is named`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each
before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: the runner treats an absent or stubbed gate as clear and runs unhardened—the exact
  configuration ADR-0005 refuses—mitigation: D7's conditions are the criteria above, each red-first;
  absent-gate-refuses and writable-gate-refuses are named known-bad cases, and build-and-test never
  performs a live run (D7 condition 4).
- Risk: a silent budget cap reads as a clean short run—mitigation: the budget stop is a named
  recorded outcome, pinned by the budget-ceiling case.
- Rollback: revert the story's commits; nothing schedules the runner until the operator adds a cron
  entry, and the runner refuses on this host regardless (the gate exits 2).

# Notes

- This is a detector story: the gate-refusal and gate-integrity guards are watched red before they
  exist (a runner without the gate call, or without the integrity precheck, runs the sequencer stub
  on a stubbed-clear or writable gate, which the criteria catch).
- Depends on STORY-0015 (the start gate must be built and fixture-tested first, per D7 condition 1)
  and STORY-0013 (the sequencer it wraps).
- The runner must invoke the gate with the same environment a phase gets. The gate's
  credential-reach condition measures reachability under the gate's own `PATH` and environment, so
  a `gh` or credential present to a phase but absent to the gate would read clear while the phase
  can still push. Invoke the gate in Step 6's `sudo -u RUN_USER env -i …` form, the same allowlist a
  phase is spawned under, so the gate measures the environment it is certifying.
- ADR-0005/D7's honest ceiling holds here: this runner being built and ready is not a blessing to
  run. Permissibility to run remains the gate's clear, reachable only on a hardened host, and on the
  reference host the runner refuses.

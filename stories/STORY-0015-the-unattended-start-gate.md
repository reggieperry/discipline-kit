---
id: STORY-0015
title: Build the unattended-start gate—the fail-closed court that refuses an unhardened host
deps: []
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0005
decisions: [D2]
group: A
---

# Problem / Context

ADR-0005/D2 makes OS run-identity isolation and D5's sandbox the precondition for unattended
operation, and names a fail-closed court that must refuse to run unless every hardening condition
holds. That court is specified but unbuilt, so there is no mechanical refusal of the exact
configuration ADR-0005 exists to prevent: an unattended chain over an unhardened host. D7 requires
this gate built and fixture-tested before the envelope runner, because the runner enforces it at
runtime.

Grounding against HEAD:

- `INSTALL-HARDENING.md`, Step 6—the gate's specification: it runs as the declared run-user and
  asserts `id -u` matches first (a gate run as root or the operator makes every sudo and ownership
  probe a catastrophic false pass), checks all six conditions every run, exits 2 naming any failed
  condition, and treats an unmeasurable condition (a missing tool, an unreadable path, a git error)
  as exit 2, never a skip.
- `docs/adrs/ADR-0005-containment-posture.md`, D2 (the four run-identity conditions), D5 (the
  sandbox), and D7 (which requires this gate built first, fixture-tested one-planted-hole-per-condition).
- `scripts/profile-check.sh` and `harness/chain/core.py` (`startup`)—the kit's fail-closed court
  idiom and its three-valued exit convention (0 clear, 2 could-not-run) this gate follows.

# Proposed approach

A standalone check, `scripts/unattended-start-gate.sh` (or `harness/chain/`—the builder's call,
matching the court siblings), with a fixture in `harness/fixtures/`. It takes the run-user, the
pinned root, the clone, and the expected remotes as arguments; asserts its own identity first; then
runs the six condition probes from INSTALL-HARDENING Step 6, each with its exact measurement:

- `sudo -n true` fails for the run-user, and `sudo -l -U` reports no sudo (both polarities);
- every pinned examiner path is root-owned and not run-user-writable, proven by a write attempt as
  the run-user, not only by octal mode;
- the run-user resolves no publish credential (`gh auth token` and `git credential fill` return
  nothing, no token in the environment—the credential-path test, not a file stat);
- the per-run directories are run-user owned;
- a `bwrap --unshare-user` probe succeeds and the settings carry `sandbox.enabled` and
  `sandbox.failIfUnavailable` (the probe alone is insufficient—Claude fails open);
- the clone's remotes match the declared expectation.

Any failed or unmeasurable condition exits 2 naming it; exit 0 only when all six hold. The gate
never short-circuits and checks every condition every run, because a partial gate is worse than
none.

# Scope and non-goals

In scope:

- the gate, its identity self-guard, its six condition probes, and its fixture

Out of scope:

- the envelope runner that invokes it (STORY-0016)
- applying the hardening itself (INSTALL-HARDENING.md, operator work)
- wiring the gate into `scripts/check.sh` (it VOIDs on a host with no run-user, like the other
  pinned-root courts; the fixture runs on the commit path, the tool does not)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [ ] each of the six conditions, planted as a lone hole against an otherwise-clear throwaway host,
      yields exit 2 naming exactly that condition—verified by `the gate fixture's one-planted-hole-per-condition
      cases (six known-bad, one all-clear)`
- [ ] a fully-clear throwaway host yields exit 0—verified by `the gate fixture's all-clear case`
- [ ] the gate run as root or as an identity other than the declared run-user refuses (exit 2),
      never a false clear—verified by `the gate fixture's wrong-identity known-bad case`
- [ ] an unmeasurable condition (a missing probe tool, an unreadable path) exits 2, never a
      skip-to-clear—verified by `the gate fixture's unmeasurable-condition known-bad case`

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each
before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: the gate reads clear on a condition it did not actually measure (the instrument reading
  clean because nothing looked)—mitigation: unmeasurable is exit 2 by construction, pinned by the
  unmeasurable-condition case; the write-attempt and credential-resolution probes exercise the
  mechanism rather than a proxy.
- Risk: the gate run as the wrong identity passes vacuously—mitigation: the `id -u` self-guard is
  the first check, pinned by the wrong-identity case.
- Rollback: revert the story's commits; the gate fails closed on absence, and unattended operation
  stays refused with or without it (the envelope runner of STORY-0016 refuses when the gate is
  absent).

# Notes

- This is a detector story: its guard tests are watched red before the guard exists (each
  planted-hole case fails against a gate that does not yet check that condition).
- Grounded in INSTALL-HARDENING.md Step 6 (the spec) and ADR-0005/D2, D5, D7. The gate is
  buildable and testable now against fixtures; on the reference host it exits 2 and refuses, which
  is the correct behavior and lifts nothing D2 refuses.

# ADR-0005: The containment posture—the fence is friction, and isolation is the precondition for unattended work

**Status:** Proposed (2026-08-15).
Pre-draft acceptance gate: one deep-reason pass, recorded in
[reviews/ADR-0005-deep-reason.md](reviews/ADR-0005-deep-reason.md), which measured the framing's
blast-radius bound false on the reference host and reset the record's spine. Acceptance is
reserved for the operator's own read, because this record's subject is exactly how much a phase
can reach that the operator would answer for; an adversary pass informs that read and substitutes
for nothing.

## Context

ADR-0001 decided how the chain knows where it is, ADR-0002 what happens at the trunk, ADR-0003
the sequencer's obligations, and ADR-0004 the substrate. Each deferred one object to a record not
yet written: the forged-ref closure, and the fence posture beyond ADR-0004/D3's per-invocation
hooks. This is that record. It decides what a phase—a headless `claude -p` session holding Bash,
which for a build phase means nearly every capability—can and cannot reach, what the trust
boundary actually is, and how the residues three prior records handed here are bounded or closed.

The design doc's §4.1–4.3 did the containment analysis this record promotes to decisions, with
its measurements. Its position: containment is hook-based, never `permissions.deny`-based, because
under `--dangerously-skip-permissions`—which the invocation layer uses—the deny layer is
weakened (five of six shell-string evasions succeeded, `bash -c` among them) while a PreToolUse
hook exiting 2 survives the bypass. Its honest ceiling: the fence catches drift and accidents; it
does not contain a phase that means to get out, and what reaches the trunk rests on the human
merge.

The pre-draft gate measured the reference host and found the framing that leaned on a disposable
clone to be false there, which is the fact this record is built around:

- The phase runs as the operator's own uid, in group `sudo`, with `sudo -n -l` reporting
  `(ALL) NOPASSWD: ALL`. Passwordless root is one Bash call away.
- The sandbox does not work here: `bwrap --unshare-user` fails `setting up uid map: Permission
  denied` under `kernel.apparmor_restrict_unprivileged_userns=1`, with no bwrap AppArmor profile.
  The sandbox is the only surveyed mechanism that reaches inside `bash -c` and `python -c`.
- `/etc/claude-code/managed-settings.json` is absent, and its tier is a trust root only if
  passwordless sudo is removed first, which it is not.
- The pinned examiner root `/var/lib/discipline-chain` is owner- and group-writable by that uid
  and is shared across the operator's real clone and every dedicated clone.
- The operator's real checkout is reachable by absolute path and carries a public GitHub `origin`;
  the gh push token at the operator home's `.config/gh/hosts.yml` is readable by that uid via an
  absolute path, which the invocation layer's HOME repoint does not protect—it defeats `~`-relative and
  default-config lookups, not an absolute read.

So on an unhardened host the dedicated clone bounds only `git push` under default remote
resolution from inside the clone. It bounds nothing a phase reaches by absolute path or by sudo:
not the shared examiner root, not the real checkout, not the ambient publish credential. The
runs to date have been safe because they were attended and their briefs operator-authored, not
because a boundary held. This record makes that precise and names what unattended operation
requires before it may begin.

## Decisions

### D1: In-process fencing is friction, not containment; it is retained as defense-in-depth against accident and drift

No `permissions.deny` rule, `tools:` allowlist, PreToolUse hook, tool-availability deny, or
environment scrub is treated as containment of a phase that means to get out. Each is friction:
it raises the cost of an accident by about one line and the cost of intent by zero, because under
`--dangerously-skip-permissions` the deny layer is weakened and every shell-string fence is
evadable by `bash -c`, and because on a host without a working sandbox nothing reaches inside an
interpreter invocation. The friction layers are kept—they catch the unmotivated reach, which is
the path an honest phase takes first—but the record never counts them toward the trust boundary.
This promotes design §4.1's position to a decision and inherits ADR-0004/D3, which already made
the per-invocation pinned settings hooks the fence and superseded the agent_type-keyed one.

Covered-by: none—it records a posture and builds nothing; the friction layers it declines to count as containment already exist.

### D2: OS-level run-identity isolation is the precondition for unattended operation; absent it, unattended is refused and the posture is attended-only

Unattended operation—a run no human is watching as it happens—may begin only on a host where a
dedicated unprivileged run-identity holds, established and checked, not assumed:

- the run-user has no passwordless sudo (`sudo -n true` exits non-zero for it);
- the pinned examiner material (`settings/`, `briefs/`, `postconditions/`, `phases/`, `rules/`,
  and the sequencer definition) is root-owned and not group- or other-writable, so a phase cannot
  poison the fence or the graders it will be judged by;
- the run-identity holds no reach to the operator's publish credentials and no write to the
  operator's real checkouts;
- the per-run writable directories (`worktrees/`, `streams/`, `records/`) are owned by the
  run-user or mounted per run, so one run cannot corrupt another's evidence.

This is the decision that makes any blast-radius bound true: only under it does "the worst a
phase does is corrupt its own run's writable set" hold. On the reference host none of these
holds today, so unattended operation is refused there now, and the honest posture is
attended-only—a human authoring the briefs and watching the run, accepting the un-contained risk
in real time. The unattended-run envelope record (cron, locking, budget) is downstream of this
one and may not be drafted until D2's gate exists, because an unattended chain over an unhardened
host is the exact configuration this record refuses.

Covered-by: none—its court, the unattended-start gate, is owed with the unattended-run envelope and blocked on this record's acceptance; no story is written until then.

### D3: The forged-ref residue is consumed, not closed

A phase holds Bash in the same clone whose `refs/chain/*` the seam writes, so it can forge a
phase ref, delete a `park*` or `refutation*` ref that conjuncts 5 and 6 read, or pre-plant a
merge record—the residues ADR-0001/D5, ADR-0002/D5, and ADR-0003/D2 defer here. Containment does
not close them: no in-process fence stops a phase from writing a ref in its own clone, and the
merge stage's tip-equality and phase-ref ancestry narrow the laziness, not the intent (ADR-0002/D5
consumed this and this record inherits its rule). This record consumes them the same way—named
open, bounded by D2. The bound is the whole point of D2: on an unhardened host the bound is the
operator's entire account, which is the argument for isolation; under D2's run-identity the bound
is the run-user's writable set, and the offline `refs/chain`-versus-event-log reconciliation
ADR-0003/D2 names as audit is the standing observation, honest that the event log is itself
agent-writable.

Covered-by: none—it consumes a residue rather than closing it; the audit it names is ADR-0003/D2's.

### D4: The trust boundary is the operator's own act at the trunk, per terminal posture, and it is unmechanizable acceptance rather than containment

What a phase produces reaches the real trunk only through a human act, and which act depends on
the terminal posture ADR-0002/D1 sets:

- under `merge-local`, the operator reads the chain-built commit's diff and cherry-picks it into
  the real checkout (the transplant the first production story used);
- under `open-pr`, the chain publishes the story branch and the operator merges the PR.

Neither act is forced and both can be rubber-stamped; nothing mechanically compels the read.
ADR-0002/D1 already states the trunk crossing is a judgment act by design, and this record keeps
it as exactly that—the residual acceptance of the risk the fence did not contain, honestly
labeled, not dressed as a mechanism. On an unhardened host this human act is stacked on a broken
blast-radius bound, so it is one thin layer over another, not one thin over one solid—the second
reason D2 is a precondition rather than a nicety.

Covered-by: none—it labels an existing human act as the acceptance of record, not a mechanism, so nothing is built.

### D5: The hardening is an install checklist the machine supplies and the kit cannot, each step carrying the measurement that says whether it took

`INSTALL-HARDENING.md` ships with the kit; the operator or the machine's admin applies it. Each
step names the measurement that discharges it, because a hardening step asserted but not measured
is the instrument reading clean because nothing looked:

- a dedicated unprivileged run-user, verified by `sudo -n true` failing for it and by the phase's
  measured uid not being the operator's;
- the pinned examiner material root-owned `0755` (files `0644`), verified by `stat` at unattended
  startup, refusing to run otherwise;
- `managed-settings.json` at `/etc/claude-code/`, a trust root only after passwordless sudo is
  removed, with `disableBypassPermissionsMode` set to the string `"disable"` and paired with
  `allowManagedPermissionRulesOnly`—verified present, and moot until the sudo precondition holds;
- the bubblewrap sandbox, which reaches inside `bash -c`, enabled at the kernel level (an
  AppArmor profile or a relaxed `apparmor_restrict_unprivileged_userns`), verified by a bwrap
  probe succeeding rather than failing the uid-map map.

On the reference host the checklist's honest output is that the two real-containment tiers
(managed settings, sandbox) are unavailable and the run-user is unhardened, so unattended
containment is not established and D2 refuses unattended operation—recorded as the machine's
measured state, not as a step deferred to someday.

Covered-by: none—INSTALL-HARDENING.md is the owed deliverable this record specifies, blocked on acceptance; no story is written until then.

### D6: Tool-availability deny and the environment scrub are hygiene the sequencer owns, counted as friction

The pinned settings deny the spawn tools (`Task`, `Agent`, `Workflow`—the third added after the
D5 probe found it an uncovered vector), and the sequencer scrubs every `CLAUDE`-prefixed variable
from the phase environment before spawning (STORY-0013; the invocation layer inherits-and-patches
the environment and does not scrub, so the sequencer is the layer that owns it). Both are kept as
defense-in-depth and counted under D1 as friction: tool-deny was measured stopping an
unmotivated spawn but does not close a determined path (`Workflow` behind its opt-in, or
bash-spawning another `claude`), and the scrub is session-hygiene that keeps a driving session's
identity out of the phase, not a containment boundary. The scrub carries one caveat for D5's
per-machine record: a machine that authenticated phases through a `CLAUDE`-named variable would
have it scrubbed and fail loudly; the reference host uses `ANTHROPIC_API_KEY`, which survives.

Covered-by: none—it labels the shipped deny list and the sequencer's environment scrub as friction; both already exist.

## Consequences

- Unattended operation is gated behind an OS-isolation precondition the reference host does not
  meet, so the chain stays attended there until the run-user, examiner ownership, and credential
  reach are fixed. This is a cost accepted deliberately: the alternative—unattended work over a
  host where a phase runs as the operator with passwordless root—is the configuration D2 exists
  to refuse.
- The unattended-run envelope record is blocked on D2's gate and inherits it as a precondition.
- The forged-ref and record-tamper residues stay open and disclosed in the merge record's
  `not-established` lines, now with a record that consciously owns them rather than a defer with
  no destination.
- The friction layers (hooks, tool-deny, scrub, zero-remote clones) stay in the build and stay
  honestly labeled; no future reader may cite them as containment, because this record says in D1
  they are not.
- The human trunk act stays the acceptance of record and is never presented as a mechanism, so a
  green chain run is never a reason to skip the diff read.

## Alternatives

- **The disposable-clone blast radius as the trust boundary** (the pre-draft framing): rejected
  because measured false on the reference host—the clone bounds only default-remote pushes from
  inside it, while the phase reaches the shared examiner root, the real checkout, and the publish
  token by absolute path and by sudo. It becomes true only under D2, so D2 is the decision and the
  clone is one friction layer within it.
- **In-process fencing as containment** (hooks or deny sufficient): rejected on the design's
  measurements—deny void under bypass, no sandbox on this host, `bash -c` evading every
  shell-string fence. Kept as friction under D1.
- **Closing the forged-ref residue by containment**: rejected as impossible—a phase writes refs
  in its own clone; the residue is consumed under D3, not closed.
- **A managed-settings or sandbox trust root on the reference host now**: rejected as unavailable
  today—managed settings is moot under passwordless sudo, and bwrap is AppArmor-blocked. Both are
  D5 checklist items whose measurement currently reads not-established.
- **Forcing the human read mechanically** (a gate that blocks the trunk act until a diff is
  acknowledged): rejected as theater—an acknowledgement click is as rubber-stampable as the merge
  it guards; ADR-0002/D1 already holds the crossing as a judgment act, and D4 keeps it honest
  rather than pretending a mechanism.

## Falsification condition

Per the house form, each falsifier names its court; where a court is not yet built it is named as
future, and where a condition is genuinely a judgment it is labeled review-watched rather than
dressed as mechanical.

- **D1**: a phase escaping a friction layer that the record had counted as containment—vacuous by
  construction, since D1 counts none; the standing check is that no downstream record or code
  comment cites a fence as containment. Court: review of any such citation; future, prose-watched.
- **D2**: an unattended run beginning on a host where `sudo -n true` succeeds for the run-user, or
  where a pinned examiner path is group- or other-writable. Court: the unattended-start gate—a
  fail-closed startup check that runs `sudo -n true` and `stat`s the examiner material and refuses
  to run otherwise—named here, built with the unattended-run envelope, and its absence is why
  unattended operation is refused until it exists.
- **D3**: a forged or deleted `refs/chain` ref reaching a signed outcome undetected. Court: the
  offline `refs/chain`-versus-event-log reconciliation ADR-0003/D2 names as audit; honest bound,
  the log is agent-writable, so the court narrows evidence, not capability—review-watched.
- **D4**: a chain-built commit reaching the real trunk with no human act. Under `merge-local` the
  chain never pushes and the transplant is a hand cherry-pick, so this is structurally refused;
  under `open-pr` the guard that the chain never pushes `main` (merge.py's composed-destination
  refusal, live) is the court, with the human PR merge the acceptance beyond it—review-watched.
- **D5**: an install step asserted applied whose measurement was not run. Court: each checklist
  step carries its own probe (`sudo -n true`, `stat`, a bwrap map attempt), and the startup gate
  re-runs the mechanical ones; a step with no measurement is the defect.
- **D6**: a spawn vector not covered by the deny list, or a `CLAUDE`-named auth variable broken by
  the scrub. Court: the D5 probe re-run on a harness version bump (ADR-0004/D5), which enumerates
  the phase's tool list; future, version-gated.

## Cross-references

- Supersedes: None. Consumes the forged-ref and fence-posture residues deferred by
  [ADR-0001](ADR-0001-advancement-re-derived.md)/D5,
  [ADR-0002](ADR-0002-merge-posture.md)/D5, and
  [ADR-0003](ADR-0003-sequencer-obligations.md)/D2. Inherits
  [ADR-0004](ADR-0004-substrate-choice.md)/D3 (the fence is the per-invocation pinned settings
  hooks) and ADR-0002/D1 (the trunk crossing is a judgment act). Promotes design §4.1–4.3 to
  decisions rather than treating them as a peer record.
- Superseded by: None.
- Related: `docs/probe/d5-limbs-probe-2026-08-15.md` (the spawn-surface and scrub measurements),
  `docs/probe/first-walk-2026-08-14.md` (the dedicated-clone model and repo-local identity), and
  the owed unattended-run envelope record (blocked on D2's gate). The `INSTALL-HARDENING.md` of
  D5 is the owed deliverable this record specifies.



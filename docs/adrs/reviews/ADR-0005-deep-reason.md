# ADR-0005 acceptance gate: the deep-reason record

Passes per `harness/skills/adr-write/SKILL.md`. Acceptance is reserved for the operator's own
read, because this record's subject is how much a phase can reach that the operator answers for;
the gate informs that read and substitutes for nothing.

## Pass 1 (pre-draft), 2026-08-15: the blast-radius bound measured false, the spine reset

A fresh-context adversary attacked the proposed framing (in-process fencing is friction; the
trust boundary is the disposable dedicated clone plus the human transplant). The directional half
held; the load-bearing half did not. Findings taken into the draft:

- **Blocker 1, taken as the spine.** The blast-radius bound was measured false on the reference
  host: the phase runs as the operator's uid with `(ALL) NOPASSWD: ALL`, the pinned examiner root
  is owner- and group-writable and shared across clones, the real checkout is reachable by
  absolute path with a public `origin`, and the gh push token is readable by absolute path (the
  HOME repoint defeats `~`-relative lookups, not an absolute read). So the clone bounds only
  default-remote pushes from inside it and bounds nothing reached by absolute path or sudo. The
  draft's D2 makes OS-level run-identity isolation the precondition that makes the bound true and
  refuses unattended operation absent it; D1 keeps the negative half (friction, not containment).
- **Blocker 2, taken.** The record must consume the forged-ref residue three prior records defer
  here, which the framing omitted. D3 consumes it explicitly—named open, bounded by D2—rather
  than leaving a defer with no destination.
- Refinements taken: the pinned-root sharing hole becomes D2's examiner-ownership clause and the
  startup gate (D2 falsifier); the credential/publish path becomes D2's no-publish-credential
  clause and D4's per-posture reconciliation (the kit's live posture is `open-pr`, where branches
  auto-publish, so the run-identity must hold no push token); "all in-process fencing is friction"
  is kept but the dedicated no-sudo run-user is named as the thing that actually changes the
  ceiling, filed as D2 rather than an optional checklist item; the human act is labeled
  unmechanizable acceptance, not a court (D4), matching ADR-0002/D1; supersession hygiene—cite
  ADR-0004/D3 and ADR-0002/D5, promote design §4.1–4.3—applied in Cross-references.
- Probe-verified by the gate and re-verified by the author: `sudo -n -l` = NOPASSWD ALL; bwrap
  uid-map denied under `apparmor_restrict_unprivileged_userns=1`; managed-settings absent; the
  examiner root and `~/.gitconfig` writable; the gh token readable by absolute path; the real
  checkout writable with a public origin.

The draft lands Proposed. The second deep-reason pass attacks the drafted record before the
operator's read; its verdict is recorded below this entry.

## Pass 2 (draft attack), 2026-08-15: REVISE, two blockers, all findings taken

A fresh-context adversary against the drafted record re-ran the host probes (all held) and
attacked the reasoning. Two blockers, both taken:

- **B1—D2 over-scoped its own bound.** The draft said run-identity isolation "makes any
  blast-radius bound true"; it does not, because with the sandbox unavailable a phase still reads
  world-readable files and reaches the network within the run-user's authority, and D5 itself
  names the sandbox a separate tier. D2 now scopes its bound to what run-identity buys
  (escalation, examiner, credential, cross-run) and states the read/network/exec bound rests on
  D5's sandbox, so unattended requires D2 and the sandbox together—reconciling the D2/D5
  disagreement the pass flagged.
- **B2—D4 misstated the trunk boundary and courted the wrong actor.** The draft said the trunk
  is reached "only through a human act"; on the reference host a phase pushes to `main` with the
  ambient token, no human act, independent of terminal posture. The D4 falsifier cited merge.py's
  guarded push, which binds the sequencer's terminal act, not a phase's own `git`. D4 now states
  the human act is the sole crossing only under D2's credential isolation, that the reference host
  is compromised at the trunk even attended, and the falsifier distinguishes the sequencer-push
  court from the phase-push path that only D2 closes. A Consequences line makes the attended-host
  trunk exposure explicit.

Refinements taken: the D2 court now enumerates all four conditions plus the sandbox probe (a
partial gate is worse than none); the D3 audit citation corrected to ADR-0003's D2/D3 falsifier
and called a future court; the Context examiner-root descriptor corrected to owner-writable
(measured `0755`, not group-writable). D1's prose-watched court is kept as a labeled review
discipline. The revised record lands Proposed for the operator's read.

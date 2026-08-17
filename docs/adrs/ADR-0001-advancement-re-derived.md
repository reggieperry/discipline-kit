# ADR-0001: Advancement is re-derived, never reported

**Status:** Accepted (2026-08-07).
Acceptance gate: three deep-reason passes, the third CLEAN against the staged slice, recorded
in [reviews/ADR-0001-deep-reason.md](reviews/ADR-0001-deep-reason.md).

## Context

The SDLC-chain design (`docs/sdlc-chain-design.md`) explores and does not decide; it names the
forks that need records before anything is built. This ADR fixes the one invariant every other
part of that design already leans on—§7 states it as the first of its three invariants:
"advancement is re-derived, never reported"—and fixes nothing else: not the sequencer
substrate, not the containment posture, not the merge posture.

Three measured facts force a decision here rather than a preference:

- A phase that could not act at all reports success on every field the harness exposes. The
  design's denial probe (§4.4) ran a phase with every write tool disabled: exit 0, `is_error`
  false, `subtype` "success", `permission_denials` empty—and the file it was told to create
  does not exist. Any advancement rule built on the harness's self-report passes that run.
- Phase agents own their own processes and files. The measured containment layers are friction:
  five of six deny-rule evasions succeeded (§4.1), and the PreToolUse backstop on the event log
  is "friction" by the design's own words (§4.5). Any completion token an agent can mint is
  therefore a self-report in different clothing.
- Position must survive process death between phases. A log's paired start/end records detect
  death inside a phase and cannot detect death between phases (§4.5): the store reads clean and
  complete while the run is neither.

The repository has paid for this defect class once already: the dev-ledger was removed
(2026-07-30) after its own record showed every signature cited the same mechanical check—a
claim by the party being judged carried no information the check did not already return. The
sequencer substrate is deliberately undecided and has flipped once already (the prior design's
Workflow sequencer to this document's shell proposal, §1.1), and §4.8 entertains flipping it
again—so every Decision below is written to hold under any substrate. "Sequencer" here means:
whatever runs outside the phase agents with filesystem access and decides advancement.

## Decisions

### D1: Chain position derives from git refs that only the sequencer writes

A story's position is the highest completed phase ref under
`refs/chain/<story-id>/attempt-<a>/phase-<n>`—a dedicated namespace, never under `refs/heads/`
(the ref/ref-directory collision is measured, §4.5). The sequencer creates the phase ref only
after that phase's postcondition passes at the seam, and the sequencer is the namespace's only
writer by rule—nothing enforces that rule against an agent holding Bash, and the Consequences
section carries that residue rather than hiding it. A bounce back to phase N deletes
`phase-{N..end}` of the current attempt in one atomic `git update-ref --stdin` batch, so
derived position can never disagree with the re-walk rule. Position is never read from the
event log, from story-spec `status:` frontmatter, or from the harness stream.

### D2: A verdict is a sequencer-run postcondition, evaluated at the seam, and it is three-valued

`phase_ok(story, n)` holds when the phase ref exists AND the phase's postcondition passed at
the seam—the point where the sequencer, not the phase, ran it against git and the filesystem
(§4.4). After the seam the ref is the only surviving evidence of the second conjunct, so on
resume the conjunction is operationally single-term; that is exactly the forged-ref residue
the Consequences section discloses. A verdict is pass, fail, or could-not-run—and
could-not-run never reads as pass.
Verdicts are evaluated once, at the seam; position is re-derived on every resume (D1), verdicts
are not re-litigated, because a postcondition need not be monotonic—the design's own
`red-proof` is a historical property of the tree it ran against, and a later tree can
legitimately fail it. Harness stream fields (`is_error`, `subtype`, `permission_denials`, exit
codes) are diagnosis and corroboration, never the verdict.

### D3: The examiner never comes from the judged tree

Postcondition scripts, the checks they call, the configuration they read, and the fixtures that
demonstrate them (D4) are pinned outside the phase agent's writable surface. A postcondition
that resolves any part of itself from the judged worktree—the tree's own copy of a check
script, a gitignored environment file—is a defect of exactly the class this ADR exists to
close: the judged party supplying the examiner. Both reachable instances are already measured
(§4.8: a check script that changes directory into its own tree; a verdict surface read from a
gitignored `.envrc`).

### D4: No postcondition's verdict counts before it has demonstrated red and green

Every postcondition ships with a known-bad fixture it fails and a known-good fixture it passes;
the fixtures are examiner material, pinned per D3. The sequencer treats an undemonstrated
postcondition's verdict as could-not-run. A predicate that always fails is indistinguishable
from a working fence from outside (§7); the demonstration is what tells them apart.

### D5: Harness-written state is admitted for resumption and liveness, never for position or verdicts

Session ids (for `--resume`) and liveness signals (a stream file with events and no `result`
line reads as in-phase death, bounded by the wall-clock SLO of §4.6) may be read from harness
output. Position and verdicts may not. The event log is sequencer-written, append-only audit
outside the working tree; agents writing it cannot be mechanically prevented (measured
friction-only), which is precisely why nothing is ever decided from it.

## Consequences

- A sequencer must exist as the sole advancement authority before any phase advances anything,
  and no phase can self-advance. Because no Decision names a substrate, the record survives the
  design's substrate flips, past and future.
- Postconditions run twice—once as the phase's own hygiene, once at the seam by the sequencer.
  The double execution is accepted; the seam run is the one that counts.
- Phase refs are per-instance run state: never pushed, never fetched. A remote refspec or
  mirror covering `refs/chain/*` is forbidden—a fetch refspec with `--prune` deletes every
  local phase and park ref on the normal path, silently restarting in-flight stories, and a
  push refspec publishes per-instance run state as shared truth. This is the one
  consequence with a court live today: `scripts/chain-refspec-check.sh`, wired into
  `scripts/check.sh` in the same commit as this ADR.
- D1's only-writer rule binds the sequencer, not the world: an agent with Bash can forge a
  phase ref, and a forged ref becomes derived position on the next resume. That residue is
  disclosed, not closed—it belongs to the containment-posture record and ultimately to the
  merge-posture record, both still owed.
- Still to do, and tracked by the Falsification section: the derivation function, the
  postcondition harness with D4's fixtures, and the future checks named below.

## Alternatives

- **The harness self-report conjunction** (`result` present, `is_error` false, `subtype`
  success, `permission_denials` empty): measured non-discriminating—returns PASS on a phase
  that did nothing (§4.4). This is the alternative the design's first draft chose and
  retracted.
- **The event log as authority**: cannot see death between phases (§4.5), and the log is
  agent-forgeable with friction-only protection. Kept as audit and diagnosis, never authority.
- **Story-spec `status:` frontmatter as authority**: advisory by the design's own conclusion
  ("status fields are advisory, git is authority", §4.5), and editable by every phase agent.
- **Phase-tagged commit trailers as the completion form** (§4.5 offers this alternative): a
  trailer is authored by the phase agent inside the commit—a self-report in git's clothing.
  Rejected on that count alone.
- **Agent-written phase refs**: one `git update-ref` forges completion with no work done. The
  same defect class the dev-ledger removal named: a claim by the party being judged.
- **A claim registry over chain state** (the dev-ledger pattern): retired 2026-07-30 on its own
  record; not reintroduced.

## Falsification condition

Per decision, each court named honestly—a future check is named as future, and an unwatched
condition reads as unwatched:

- **D1**: two derivations of one story's position disagree, or a resume advances past a phase
  whose artifact is absent. Court: a fixture repository where derived position must equal
  planted refs—buildable only when the derivation function exists; it lands with the
  sequencer's first commit. Until then this condition is unwatched except at its edge:
  `scripts/chain-refspec-check.sh` (live today) fails the build if any remote refspec or
  mirror configuration covers `refs/chain`, and exits could-not-run rather than clean when git
  itself is unreadable.
- **D2**: the denial probe replayed against the real sequencer—a did-nothing tree must FAIL, a
  known-good tree must PASS, a tools-disabled run must read could-not-run. Court: future; the
  check's shape is fully specified by the design's own measurement (§4.4).
- **D3**: a verdict that changes when only the judged tree's own scripts or ignored environment
  files change. Court: future examiner-pinning test; until then the standing observation is the
  pair of measured instances in §4.8.
- **D4**: a postcondition admitted to the set without its red and green fixtures. Court: the
  sequencer's loader refuses undemonstrated postconditions—future; until then review
  discipline, stated plainly as unwatched.
- **D5**: any sequencer source reading the log path, `status:` frontmatter, or stream verdict
  fields in a control-flow position. Court: a grep-shaped source check that activates with the
  first sequencer source; today it would grep nothing and prove nothing, so it is not claimed.

## Cross-references

- Supersedes: None (first ADR).
- Superseded by: None.
- Related: `docs/sdlc-chain-design.md` §4.4, §4.5, §4.7, §4.8, §7 (the invariant and its
  measurements); `docs/sdlc-chain-walkthrough.md`; `scripts/chain-refspec-check.sh` (D1's edge
  court). Three records are still owed and are not decided here: the sequencer model, the
  containment posture, and the merge posture (§2's struck invariant and §4.12's expiry
  conditions).

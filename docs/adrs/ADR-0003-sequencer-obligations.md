# ADR-0003: The sequencer's obligations, with the substrate left open pending one measurement

**Status:** Accepted (2026-08-08).
Acceptance gate: three deep-reason passes, the third CLEAN against the staged slice with the
adversary supporting acceptance, recorded in
[reviews/ADR-0003-deep-reason.md](reviews/ADR-0003-deep-reason.md).

## Context

ADR-0001 decided that advancement is re-derived and never reported; ADR-0002 (Proposed,
operator-directed in its hinge) decided where the chain stops. This record decides what the
thing that drives them—the sequencer—must be and do. It is the fork the design has flipped
twice without a record: the prior design chose a Workflow, this design's first draft chose a
shell driver reading `claude -p` output, and the walkthrough now asserts "the main loop
drives." None of that is decided anywhere.

The evidence rules out exactly two things. A Workflow script cannot be the spine: it has no
filesystem, no subprocess, and no clock, and a re-derived verdict is needed *between* phases
(measured; the walkthrough's surfaces table records it). And no sequencer may read verdicts
from harness self-reports: the denial probe showed every stream field reporting success while
the phase did nothing (ADR-0001/D2, accepted). The evidence does not choose among the
substrates that remain, and there are at least three: an interactive main-loop session
driving phases as subagents; an external process driving headless `claude -p` phases
directly; and an external process driving one-shot wrapper sessions that each spawn one
phase subagent—which keeps the measured session properties (the worktree handoff and hook
inheritance, both VERIFIED in-session; commit-as-handoff, VERIFIED; the worktree auto-clean,
DOCUMENTED only) while the sequencer itself holds no model context at all.

That third form exposes the real fork, and it is about disinterest rather than capability: a
main-loop sequencer is a model that has already read the phase agent's return string before
it decides which predicate to run and whether to write the ref—the self-report defect
relocated one level up—and it is also the longest-lived context in the system, with no
stated answer for what happens when it fills. Whether a headless or wrapper form retains the
session properties the design measured is unmeasured either way: every VERIFIED
session-property probe in §4.8 ran inside an interactive session (its remaining VERIFIED
items are source reads, not session behavior). A record that named the substrate today would be deciding
on a premise nobody has measured. So this record decides the obligations every admissible
substrate must satisfy—each one closes a measured or demonstrated hole—and specifies the
one measurement that settles the rest.

## Decisions

### D1: The sequencer runs in a real filesystem

Whatever sequences the chain has direct filesystem and subprocess access at every
advancement decision: it runs git, runs the pinned checks, and reads trees itself. This
retires Workflow-as-spine permanently (no filesystem, measured) without naming what remains.

Covered-by: none—it retires Workflow-as-spine; the surviving substrates satisfy it by construction.

### D2: The verdict channel is a pinned advance script's exit code, and nothing else

Every phase verdict the sequencer consumes is the exit code of a pinned advance script,
under one canonical contract at that boundary: 0 pass, 1 fail, 2 could-not-run—and any
other code (a missing or non-executable script, 127 or 126; a signal death, 137 or 143)
reads as could-not-run, never as a story verdict, because a broken instrument is not a fact
about the story. A predicate whose native contract differs—red-proof's exit 2 means the new
test cannot fail, a genuine fail—is adapted inside its advance script, never interpreted by
the sequencer. Never the script's stdout prose, never a phase agent's return string nor any
other agent's report, never a stream field. This is what makes the sequencer "holding no
judgment" true under any substrate: even a model-driven sequencer cannot interpret its way
past an exit code it did not produce. Stdout and stream fields remain diagnosis, per
ADR-0001/D5.

### D3: A phase ref is written only by the pinned advance script

The ref that records completion (ADR-0001/D1) is created as the last act of the same pinned
script whose exit code is the verdict—never by a discretionary act of whatever drives the
loop. The script writes the ref and only then exits 0, and a failed ref write forces a
nonzero exit, so the two advancement facts—the ref as position, the exit code as the seam
verdict—cannot diverge by the script's own act; divergence beyond it is the forgery residue
ADR-0001 disclosed, not a race this record leaves open. A sequencer that can write refs
freely is a self-report with better posture; one that can only invoke a pinned script whose
final line writes the ref is a dispatcher.

### D4: The sequencer's own definition is examiner material, pinned

ADR-0001/D3 pins postconditions, the checks they call, their configuration, and their
fixtures. This record extends the same rule to the sequencer's own definition—the driving
script, prompt, or skill, and the advance scripts of D2/D3: they are resolved from a pinned
copy outside any working tree (the machine-hardening layout: absolute paths, root-owned
where that hardening has landed), never from the judged repository. Listing their in-repo
sources under the profile's `trusted_base` is the merge-time backstop—a story touching them
parks regardless of green—and it is only a backstop: `trusted_base` prevents no edit, and
the design's own measurement has the hook bodies agent-writable. In a self-hosting
repository the pinned copy is the difference between a chain that grades work and one whose
work regrades the chain.

### D5: The sequencer starts fail-closed

It refuses to run—could-not-run, loudly—when the chain profile is absent or unparseable,
when no terminal act is declared, or when `trusted_base` is unset or omits the D4 paths.
The profile keys are read as ADR-0002 (Proposed) shapes them and follow that record wherever
the operator's read takes it. A sequencer that runs with no declared posture guards nothing while reporting
progress; the refuse-to-run obligation ADR-0002 named lands here as a decision.

### D6: A chain run owns a dedicated session and clone, and every phase's handoff is a commit

Chain runs do not share a session, working tree, or index with interactive operator work;
under ADR-0002's `merge-local` the chain merges the local `main` of its own clone, and the
operator's checkout sees it by pulling, never by sharing. Every phase's handoff is a
commit—the worker's commit-or-empty rule generalized to all phases, planner included—so
the seam precondition is mechanical and total: `git status --porcelain` empty at every seam
evaluation, with no partition between "the story's work" and "someone else's" left to
compute. Position re-derivation bounds interleaving damage but does not close it: verdicts
are evaluated once at the seam (ADR-0001/D2) and are not re-litigated, which is why the
precondition is a decision rather than advice. Its court lands with the sequencer build.

### D7: The substrate is open, and one measurement closes it

The substrate fork (main-loop session, external process over headless phases, external
process over one-shot wrapper sessions) stays open until this measurement runs, specified so
two people run the same probe: in a scratch repository carrying a project `.claude/` with
(i) an agent definition declaring `isolation: worktree`, (ii) a project-scope PreToolUse
hook that writes a marker file, and (iii) nothing else, invoke the installed harness
headlessly (`claude -p`, version recorded from `claude --version` in the result) with a
prompt instructing the main agent to spawn that subagent, which commits one file. Three
limbs, each PASS or FAIL on a named observable, raw outputs kept: (a) the subagent ran—its
completion appears in the stream output; (b) worktree isolation held—the completion's
reported worktree path or branch differs from the parent checkout, the committed file is
reachable from that branch, and the parent tree is untouched by `git status`; (c) hooks
fired headlessly—the marker file exists. Whichever substrates pass, the successor record
chooses among them on the two criteria this record's Context names—disinterest of the
looker and bounded context—since D1–D6 hold for every candidate by construction; the
choice lands as a one-Decision successor record or an amendment here before the sequencer's
first commit.

## Consequences

- The sequencer build cannot start with a substrate guess: its first commit is the D7
  measurement, recorded with the marks the design uses (a claim measured headlessly, not
  inferred from session behavior).
- D2/D3 oblige the advance scripts to exist as pinned artifacts before any phase runs—which
  is the same build item as ADR-0001's postcondition harness, now with the ref-write moved
  inside it.
- D4 obliges the profile schema to carry the sequencer's in-repo source paths in
  `trusted_base` as the merge-time backstop, and proposes the matching self-containment
  extension to ADR-0002/D3.2's list—that record is Proposed, so the extension rides its
  acceptance and supersedes nothing.
- Context lifetime and a killed phase's orphaned worktree are substrate-dependent and land
  with D7's successor record; a half-completed advance is already covered by D3's coupling
  (no ref without exit 0, no exit 0 without the ref), and position stays safe regardless, by
  re-derivation and the re-walk rule's attempt deletion.
- The unattended run envelope—cron start, per-story locking, concurrency bounded by a
  recorded tokens-per-minute figure rather than a guessed one—is deliberately not this
  record: it is substrate-agnostic and is named as the owed ADR-0004.

## Alternatives

- **A Workflow script as the spine**: refuted by measurement—no filesystem, no subprocess;
  a verdict cannot be re-derived between phases by a thing that cannot look.
- **Verdicts from the harness stream**: already rejected by ADR-0001/D2's accepted denial
  probe; cited, not re-decided.
- **Deciding main-loop-as-sequencer today** (the walkthrough's current assertion): rests on
  an unmeasured premise (headless equivalence of session properties) and leaves two holes
  its own argument never addresses—a sequencer that reads phase output before deciding is
  the self-report defect relocated, and a night-long session is the system's longest-lived
  context with no stated overflow behavior. D2/D3 close the first hole for whatever
  substrate wins; D7 buys the measurement instead of the guess.
- **An external shell driver running phases as bare `claude -p` calls**: loses the one
  session property that is verified and needed (the worktree handoff for attest-only
  phases); the wrapper-session form exists precisely to keep it, so the bare form is
  dominated and rejected.

## Falsification condition

Per decision, courts named honestly—future checks are future, unwatched conditions read as
unwatched:

- **D1**: a sequencer whose advancement path lacks filesystem access. Unwatched until the
  first sequencer source exists; then a grep-shaped source check. Stated as unwatched today.
- **D2/D3**: a phase ref created in a run where the pinned advance script did not exit 0.
  Court: future and buildable without violating ADR-0001/D5—an offline reconciliation of
  `refs/chain/*` against the event log's `predicate`/`verdict` records is audit, not a
  control-flow read; it lands with the sequencer and runs after each unattended batch. Its
  honest bound: it catches crashes and honest divergence, and the log it reads is
  agent-writable with friction-only protection, so forgery remains ADR-0001's disclosed
  residue, owed to the containment record—this court does not claim it.
- **D4**: a profile whose `trusted_base` omits the sequencer's definition path or the
  advance scripts. Court: the same future profile check ADR-0002/D3.2 owes, extended one
  path set; VOID while no profile exists, never a pass.
- **D5**: a sequencer observed running with no profile, no terminal act, or an unset
  `trusted_base`. Court: future, landing with the sequencer's start-up path;
  `merge-posture-check.sh`'s nothing-to-guard and could-not-run vocabulary is the template.
- **D6**: a seam verdict computed over a dirty tree, or a phase whose handoff was not a
  commit. Court: the porcelain-empty precondition at the seam, future; unwatched until it
  lands and stated so.
- **D7**: the substrate chosen without the named measurement, or the measurement's result
  contradicting the choice. Court: review of the sequencer's first commit, which must carry
  the measurement's record; not mechanical, and stated so.

## Cross-references

- Supersedes: None. Builds on [ADR-0001](ADR-0001-advancement-re-derived.md) (D2, D3, D5 are
  load points) and cites [ADR-0002](ADR-0002-merge-posture.md) (Proposed; the terminal act
  and the profile schema this record's D5 reads).
- Superseded by: None.
- Related: `docs/sdlc-chain-design.md` §4.2, §4.4, §4.6, §4.8, §6; the walkthrough's
  surfaces table (whose "the main loop drives" assertion this record deliberately does not
  ratify); the owed records this one names—the substrate choice (D7's successor), the
  containment posture (phase isolation), and ADR-0004, the unattended run envelope.

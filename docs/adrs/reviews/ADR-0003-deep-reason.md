# ADR-0003 acceptance gate: the deep-reason record

Passes per `harness/skills/adr-write/SKILL.md`.

## Pass 1 (pre-draft), 2026-08-08: right area, wrong boundary; the draft reshaped

Attacked the proposal to decide the sequencer as a main-loop session with cron, roster, and
budget decisions attached. Findings taken into the draft:

- **The sketch straddled two areas.** Cron start, per-story locking, and the
  tokens-per-minute budget survive any substrate flip unchanged, so by ADR-0001's own
  separability test they are not substrate decisions—they are the owed ADR-0004 (the
  unattended run envelope), and the draft names them as such rather than deciding them.
- **Three framing errors flagged and corrected**: ADR-0002 is Proposed and is cited, not
  leaned on; "the same shape invoked headlessly" was an unmeasured premise (every VERIFIED
  session property was measured interactively); and "never a shell driver" over-reached—the
  measured refutations kill Workflow-as-spine and stream-verdicts only.
- **An unconsidered third substrate found**: an external process driving one-shot wrapper
  sessions that each spawn one phase subagent—keeping every verified session property while
  the sequencer holds no model context. It beats the main-loop hypothesis on the design's
  own central property ("a sequencer holding no judgment"): a main-loop sequencer has read
  the phase's return string before deciding whether to advance, which is the self-report
  defect relocated, and it is the system's longest-lived context with no stated overflow
  behavior.
- **The honest record decides obligations, not the substrate**: filesystem access (D1), the
  exit-code-only verdict channel through pinned advance scripts (D2) with the ref written
  only by that script (D3), the sequencer's own definition pinned as examiner material (D4,
  the pass's named gap: the examiner-of-examiners in a self-hosting repository), fail-closed
  start (D5), a dedicated session with the clean-tree seam precondition owed (D6), and the
  substrate left open pending one specified headless measurement (D7).
- Tension adjudications recorded: running in the repo tree is not the D3 defect—resolving
  the examiner from the judged tree is, and the pinned-script rule is what makes the
  distinction enforceable; the operator-interleaving question has a clean answer (a dedicated
  session, D6) rather than an argued-away one.

## Pass 2 (draft attack), 2026-08-08: REVISE, five blockers, all taken

A fresh-context adversary against the draft. B1: D4's mechanism did not deliver its
property—`trusted_base` is a merge-stage diff conjunct that parks a story and prevents no
edit, while the design's own measurement has the hook bodies agent-writable; D4 now requires
resolution from a pinned out-of-tree copy, with `trusted_base` named as only the merge-time
backstop. B2: the draft's "house contract" was contradicted by the one predicate the design
specifies—red-proof's exit 2 is a genuine fail, not could-not-run; D2 now fixes the
canonical contract at the advance-script boundary and adapts differing native contracts
inside the script. B3: the codomain was open—126/127/137/143 now read as could-not-run,
never a story verdict. B4: the porcelain-empty precondition conflicted with the planner's
no-worktree handoff and carried an uncomputable escape clause; D6 now generalizes
commit-as-handoff to every phase and drops the partition. B5: the substrate measurement was
not runnable as specified; D7 now names the scratch-repo setup, the invocation with version
recording, and a PASS/FAIL observable per limb. Should-fixes taken: mark hygiene in Context
(commit-as-handoff and auto-clean marks; the VERIFIED-in-source items scoped out), the D3
ref-write/exit-code coupling stated, the reconciliation court's honest bound (it catches
crashes, not forgery), D2 excluding any agent's report rather than only the phase's, D5 and
the Consequences reading ADR-0002 as Proposed with the D3.2 extension riding its acceptance,
D7's tie-breaking criteria named, and the registry title matched verbatim to the H1.

## Pass 3 (fix confirmation), 2026-08-08: CLEAN, acceptance supported

All five blockers and every should-fix verified applied against the staged tree, each at its
line; checks green with no unstaged residue; the adversary supports Proposed to Accepted on
the grounds that the substance is internal runtime obligations, each closing a measured or
demonstrated hole, with the one operator-shaped question left open by D7's own design. Two
non-blocking nits taken at landing: the half-completed-advance consequence rewritten (D3's
coupling retires it), and an owed upstream correction recorded below.

## Follow-ups this gate created

1. The walkthrough's D1 stage ("no worktree... parks the plan") is stale under D6's
   every-phase-commits rule; the walkthrough inherits the correction when the sequencer is
   built, the same deferral ADR-0002's record uses for its wording corrections.
2. The D7 headless probe is the sequencer build's first commit; its result chooses the
   substrate on the named criteria and lands as the successor record.

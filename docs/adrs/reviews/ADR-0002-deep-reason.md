# ADR-0002 acceptance gate: the deep-reason record

Passes per `harness/skills/adr-write/SKILL.md`. Acceptance is reserved for the operator's own
read—this record's subject is how much leaves the operator's hands, so the gates inform that
reading rather than substitute for it.

## Pass 1 (pre-draft), 2026-08-07: scope right, decision set corrected in three places

Attacked the proposal to decide the merge posture as §4.12-plus-two-audit-obligations.
Findings taken into the draft:

- **§4.12's foundational premise is measured false here.** The section asserts no expiry
  condition applies on day one; the kit's `origin` is a public GitHub repository, CI fires on
  push to `main`, and story satisfaction reads `origin/main`. The revert backstop is unsound
  unless publication is severed from merging—which became D1, the record's hinge.
- §4.12 carries no evidence marks at all, so its conjunct set was not decision-eligible by
  reference; the conjuncts are decided explicitly (D3), with CI-green removed (not locally
  re-derivable) and source-set integrity left to the profile rather than cited to a §4.11
  mechanism that does not exist.
- The "one testimony conjunct" claim was refuted: the planner's declared path list is a
  second agent-authored input. D4 names and bounds both.
- The earlier audit's framing of the archived auto-merge blocker was a lineage error: the
  pinned-predicate half is discharged by ADR-0001/D3, the forgery-root object retired with
  the ledger; the real residue is narrower—a forged phase ref buys phase-skipping, since no
  merge conjunct reads a phase ref. D5 consumes it; closing it stays with the
  containment-posture record.
- The pre-draft sketch's tamper-evidence mechanism (cross-check phase refs against the event
  log at merge) violates ADR-0001/D5 and was dropped, not repaired.
- The veto window was shown to be silence-as-authority, which the design forbids for the
  reviewer in the same section that grants it to the operator; D6 drops it.
- Two missing decisions were added: does the chain push (D1), and per-repository posture
  (D2); a third finding (downstream consumes kit `main` via `--refresh-rules`) became D7.
- Trusted-base regression caught: the archived list contained itself, the CI workflows, and
  the check surface; the design's later example dropped all three. D3.2 restores the
  self-containment requirement.

## Pass 2 (draft attack), 2026-08-07: REVISE, three blockers, all taken

- B1: the revert court did not sanitize its git environment—with `GIT_DIR` exported (the
  environment of a pre-commit run from a linked worktree) it operated on the parent
  repository and reported the damage as a property failure. The probe demonstrated this
  against the real repository and restored it from reflog; the restoration was verified
  independently afterward (HEAD, branches, identity, staged slice, check green). The court
  now unsets every redirecting git variable on each call and implements its three-valued
  contract: setup failures exit could-not-run; only the property itself exits 1.
- B2: the profile court was a line grep with four measured fail-opens (section-blind key
  matches, duplicate keys, inline tables, and an unreadable file swallowed into a clean
  exit). Rewritten as a tomllib parse walking every table in the structure; unparseable or
  non-file profiles are could-not-run, never a pass.
- B3: D3 silently dropped two conjuncts the design calls mandatory—sha pinning and
  source-set integrity. Added as D3.7 and D3.8, the latter stated as owing its mechanism to
  the sequencer build rather than pretending one exists.
- Major, taken: D4's denominator was readable from the judged tree (a grade flip shrinks
  it)—now read from the pinned examiner copy per ADR-0001/D3, with D3.2 widened to paths
  the check reads, not only invokes. D1's consequence named one `origin/main` reader of
  three—now covers satisfaction, the graph read, and dependent unblocking, all moving to
  local `main`. D5's residue widened: the same namespace writability also buys park evasion
  and refutation deletion, both consumed by the same rule.
- Minor, taken: the trusted-base regression statement corrected to what the design's example
  actually drops; the revert court's proven scope stated (a HEAD merge, no conflicts); the
  lineage diagram realigned after the path fix.

## Pass 3 (re-verification), 2026-08-07: CLEAN-TO-PRESENT

The same adversary, against the revised tree, probes confined to throwaway directories. B1
verified closed: under hostile `GIT_DIR` and `GIT_WORK_TREE` aimed at a throwaway victim
repository, the court exits clean and the victim is byte-identical; a failing git on PATH
VOIDs instead of reading as a property failure. B2 verified closed across twelve profile
cases, including all four original fail-opens, the single-quote false-fail, and
directory-at-path. B3, the majors, and the minors confirmed taken. One mechanical blocker
caught before landing: the pass-2 revisions were unstaged, so a commit at that moment would
have shipped the fail-open court versions—staged before commit. Two residual one-word
wideings taken (the D3.2 and D4 falsifier courts now match their decisions' width). The
record lands as Proposed; acceptance is the operator's.

## Amendment (operator-directed), 2026-08-08

The operator directed the posture the record had put aside: the chain's terminal act should
be able to open a PR, with the trunk crossing governed by the PR-merge rules the operator
runs with their interactive instance. Amended before acceptance (the record was Proposed, so
this is a redraft, not a supersession): D1 became a per-repository terminal act—`open-pr`
(sequencer pushes the story branch and opens the PR, documenter's briefing as body) or
`merge-local` (the prior posture, kept for repositories with no forge)—with one invariant
under both: the chain never pushes `main`, anywhere. D6's veto window is done properly by
the PR surface where one exists; D5's blast radius under `open-pr` is an unearned PR, never
a trunk advance; `merge_ok` now gates the terminal act, evaluated against the trial merge of
the pinned sha. The finalizer does NOT return as an agent—PR-opening is mechanical and stays
the sequencer's, per the eleven-deleted-specs scar. `merge-posture-check.sh` reschematized:
each declared terminal act must pair with its push scope (`open-pr`/`branches-only`,
`merge-local`/`never`); unknown terminals fail. A fourth gate pass attacked the amended
record; its verdict is recorded below the pass-3 entry.

## Pass 4 (amendment attack), 2026-08-08: REVISE, two blockers, all findings taken

The same adversary, against the amended record; nineteen court cases probed in scratch,
eighteen correct. BL1: the court crashed on a `[chain.terminal]` table-valued key
(`TypeError`, exiting 1 by accident and mislabeling a crash as a finding)—fixed with a type
guard, so a non-string terminal is a named FAIL. BL2: satisfaction under `open-pr` had no
mechanism—the forge's default merge message carries no `Merged-Story:` trailer, so every PR
merge would have read unrecorded and dependents never unblocked; the consequence now names
the trailer's author (the operator-side merge rules, via a merge template or the forge merge
call's body) and defers the per-posture witness mechanics to the sequencer build. Should-fixes
taken: D6 no longer contradicts D1 on veto timers (silence merges nothing *by a chain act*);
the CI consequence and Alternatives entry rewritten in two-posture, temporal form (the
conjunct would wait on a signal its own act creates); D7 gained its `open-pr` arm; the
Context paragraph now states plainly that `open-pr` crosses expiry condition one for branch
content and scopes the backstop claim to the trunk; and the guard's opt-in-by-guarded-key
shape is disclosed, with the sequencer's refuse-to-run-without-a-terminal obligation named.

## Pass 5 (fix confirmation), 2026-08-08: CLEAN-TO-PRESENT

BL1 re-probed in scratch: a table-valued, integer, and list terminal each return a named FAIL
with no traceback; nine regression cases hold. BL2 and the four should-fixes confirmed
present. All checks green on the staged tree with nothing left unstaged. The amended record
is sound to land as Proposed for the operator's read.

## Follow-ups this gate created

1. Upstream path citations corrected in this slice: `docs/adr/` → `docs/adrs/` at the two
   design/walkthrough sites the pass found.
2. `scripts/check.sh` still resolves itself from its own tree (the ADR-0001/D3 defect, live
   in the script `merge_ok` would call)—owed to the sequencer build phase, where the pinned
   examiner layout lands.
3. The design doc's §4.12 and §3.10 inherit wording corrections (satisfaction witness moves
   to local `main` under D1) when the sequencer is built; not edited retroactively here.

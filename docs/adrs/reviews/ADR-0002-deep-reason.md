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

## Follow-ups this gate created

1. Upstream path citations corrected in this slice: `docs/adr/` → `docs/adrs/` at the two
   design/walkthrough sites the pass found.
2. `scripts/check.sh` still resolves itself from its own tree (the ADR-0001/D3 defect, live
   in the script `merge_ok` would call)—owed to the sequencer build phase, where the pinned
   examiner layout lands.
3. The design doc's §4.12 and §3.10 inherit wording corrections (satisfaction witness moves
   to local `main` under D1) when the sequencer is built; not edited retroactively here.

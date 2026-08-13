---
id: STORY-0005
title: The pinned advance script: one exit-code contract, and the ref write inside it
deps: [STORY-0001, STORY-0004]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0003
decisions: [D2, D3, D6]
group: A
---

# Problem / Context

No advance script exists: the canonical 0/1/2 contract, the adaptation of divergent native contracts (red-proof), the ref write as the script's last act, and the porcelain-empty seam precondition are all decided and unbuilt.

Grounding: `docs/adrs/ADR-0003-sequencer-obligations.md`, D2, D3, and D6. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

One advance script per phase seam wrapping its postcondition: canonical exit contract, every other code reading could-not-run, ref written then exit 0 with a failed write forcing nonzero, porcelain-empty checked first.

# Scope and non-goals

In scope:

- the advance scripts and their fixtures

Out of scope:

- the seam court replay (STORY-0010), position derivation (STORY-0006)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] a failed ref write forces a nonzero exit—verified by `an advance-script fixture with update-ref forced to fail`, which is `harness/fixtures/advance_test.py`'s `failed-update-ref-2` and `lying-update-ref-2` cases. The first plants `refs/chain/<story>/attempt-1/phase-2/sub` so the write of `phase-2` meets the ref-directory collision design §4.5 measured, and requires exit 2 naming git's "cannot lock ref" with no ref present; the second runs the seam with a `git` on PATH whose `update-ref` reports success and writes nothing, which is what the seam's read-back after the write is for
- [x] a dirty tree at the seam reads could-not-run—verified by `the porcelain-precondition fixture`, which is `advance_test.py`'s `dirty-tree-2`: an uncommitted file makes the seam exit 2 naming the file, with the postcondition's own marker required ABSENT, so the refusal is pinned to land before the examiner runs rather than after
- [x] red-proof's native exit 2 reads as fail, not could-not-run—verified by `the adaptation fixture`, which is `advance_test.py`'s three `red-proof-*` cases against a postcondition declaring the design's §5 contract (`0 pass`, `2 fail`): native 2 exits 1 with no ref, native 0 exits 0 with the ref written, and native 1—which that contract does not map—exits 2, since an unmapped code is a broken instrument and not a verdict
- [x] a parent repository holding a live phase worktree still reads porcelain-empty at the seam because the worktree is placed outside the parent (ADR-0004/D2 decided the arm)—verified by `a porcelain-precondition fixture case with a sequencer-created outside worktree materialized and the parent otherwise clean`, which is `advance_test.py`'s `worktree-outside-clean-0`: the worktree is created at a path outside the parent and its materialization is asserted rather than assumed, and the seam passes. `worktree-inside-parent-2` is the contrast that gives it meaning—`.claude/worktrees/` inside the parent shows in porcelain at 2.1.224 and reads could-not-run, so the seam is not blind to worktrees, it is blind to worktrees placed where D2 puts them
- [ ] the phase invocation pins its settings sources, so a user-scope hook cannot inject into a phase transcript—verified by `an invocation fixture run with a decoy user-scope SessionStart hook, asserting the hook's marker is absent from the phase transcript` (NOT this story: there is no invocation here to fence, and STORY-0012 carries this criterion verbatim—see Notes)
- [ ] a phase brief that does not resolve from pinned material fails closed before any invocation launches—verified by `an invocation fixture with the pinned brief absent, asserting a nonzero exit and no session started` (rewritten for ADR-0004/D1: there is no phase type to substitute; the brief is the composed prompt) (NOT this story, for the same reason—see Notes)

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: a wrapper that misroutes a broken instrument as a story fail—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- The last three acceptance criteria come from `docs/probe/D7-headless-probe-2026-08-12.md`, read
  at its correction, which measured all three facts rather than predicting them. Worktrees
  materialize under `.claude/worktrees/` INSIDE the parent repository, and the audit strengthened
  the ground: the design's §4.8 VERIFIED mark claiming they are git-excluded is measured FALSE at
  2.1.224—`.git/info/exclude` is the stock template and the parent's porcelain prints
  `?? .claude/worktrees/`—so the precondition cannot rely on an exclusion the harness does not
  write. The worktree criterion is written so either remedy discharges it, because that choice
  belongs to this story's builder and not to the probe. User-scope SessionStart hooks fire in
  headless runs: the operator's own startup hook injected machine-identity detail into both legs'
  transcripts. And leg 1 measured the fail-open the third criterion closes—the wrapper's main
  agent, meeting a phase type it could not resolve, improvised a substitute brief from the judged
  tree and carried on, which is ADR-0001/D3's defect reached by initiative inside the wrapper.
- The third part of that corrected rule is a phase-brief content rule rather than a check, so it
  is recorded here instead of as a criterion: the invoking prompt carries spawn-by-name only and
  never phase instructions, because a prompt relaying instruction content can override the pinned
  definition. STORY-0009 carries the judged-tree half.
- Discharged 2026-08-12 on `feat/chain-advance`: `harness/chain/advance.py` (the seam),
  `harness/chain/attempt.py` (the re-walk deletion and the attempt-start worktree clearing), and
  their 22-case fixture `harness/fixtures/advance_test.py`, wired into `scripts/check.sh`. The
  seam's order is itself the design, each step being what makes the next one meaningful: the ref
  components are well-formed, the repository is a working tree, porcelain is empty, the graded sha
  resolves and matches any `--tree-ref` the caller declared, the contract is readable, the
  postcondition demonstrates through the loader, the seam run happens, its native code maps to a
  verdict, the graded sha still resolves the same, and only then is the ref written and read back.
  Four of the six criteria above are discharged here; the two invocation criteria are not this
  story's, and the paragraph below says why rather than leaving them to read as missed.
- THE TWO INVOCATION CRITERIA BELONG TO STORY-0012, which carries the first of them verbatim
  ("a phase run with a decoy user-scope SessionStart hook shows no injected content in its
  transcript"). Nothing in this story launches a phase: the seam grades a tree that a phase has
  already left behind, and a settings-source fence with no invocation to fence is not a check but
  a stub. ADR-0004/D3's own Falsification section places both courts there—"the pre-phase
  filesystem assertion plus an invocation-audit fixture with a decoy user-scope hook, both in
  STORY-0012". The triage that allocated them here read the probe's three corrected facts as one
  story because they arrived in one document; two of the three are about the invocation and one is
  about the seam, and only the seam one is buildable without the invocation.
- The denial-probe replay is STORY-0010 and is deliberately not built here. This fixture exercises
  the seam's three verdicts against a postcondition it controls, which is a different court from
  ADR-0001/D2's: that one replays a did-nothing tree, a known-good tree and a tools-disabled run
  against the real sequencer, and it needs the sequencer.
- A seam defect between STORY-0004's loader and ADR-0003/D2's adaptation was found while building
  and is closed by one additive change rather than a fork. The loader demonstrates a postcondition
  in its NATIVE codes, requiring red to exit 1 and green to exit 0; a predicate whose native
  contract differs cannot satisfy that at all, since red-proof's own known-bad tree makes it exit 2
  and the loader would call the examiner broken. So `loader.load` takes an optional `adapt`,
  defaulting to identity, and the advance script supplies the map it read from pinned material. The
  adaptation therefore reaches the demonstration as well as the seam run, which is the property
  worth having: a demonstration read in codes the seam will never use is not evidence about the
  seam. `loader_test.py` stays 27 of 27, since identity is what every existing case declares.
- Two judgment calls, each a departure worth naming. A postcondition that FAILS its own
  demonstration exits 2 here, not 1: ADR-0001/D4 rules an undemonstrated postcondition's verdict
  could-not-run, and reporting a broken examiner as a story fail would bounce a story whose tree
  was never graded (`demonstration-failed-2` pins it). And `--tree-ref` is a declaration rather
  than an instruction: the seam grades the working tree at `--repo`, so a `--tree-ref` naming some
  other commit reads could-not-run (`declared-sha-mismatch-2`) instead of silently grading one
  tree and recording another sha.
- What the seam does not check, stated so it is not read as checked: porcelain is read once,
  before the seam run, and not again after it, so a postcondition that dirties the tree it grades
  is not caught—only one that moves the graded sha is. The worktree clearing refuses a path that
  is still on disk after its registration is gone rather than deleting it, because removing
  whatever a caller named is a destructive act on a mistyped argument. And nothing here closes the
  forged-ref residue ADR-0001 discloses: an agent holding Bash writes the same ref this script
  writes, and the containment record is still owed.
- Red-first: the 20 cases the suite opened with were run against a stub advance script that
  admitted everything and wrote nothing—0 of 20 passed. The three cases whose expected verdict is
  pass failed too, and on the ref rather than on the code, which is D3's coupling doing exactly
  what it is for: an always-admits seam returns the right exit code and records nothing.
- Eleven mutations, eleven killed, each with the mutant observed executing rather than reported
  killed:
  the ref write moved after the success print with its failure swallowed (killed by
  `failed-update-ref-2` and `lying-update-ref-2`); the sha re-verification removed
  (`moving-head-2`); the contract read replaced by the identity map (`red-proof-fail-1`,
  `red-proof-pass-0`, `malformed-contract-2`); the porcelain precondition dropped (`dirty-tree-2`,
  `worktree-inside-parent-2`); the `GIT_*` scrub dropped from git's own environment
  (`hostile-git-env`); an unmapped native code defaulted to pass (`unknown-native-code-2`,
  `red-proof-unmapped-2`); the batch delete replaced by a per-ref loop (`re-walk-batch`, on the
  spawn count); the ref-component check neutered (`bad-ref-component-2`, on the examiner having
  run rather than on the exit code, since git refuses the bad name itself); the demonstration
  failure mapped to fail (`demonstration-failed-2`); the could-not-run verdict returned silently
  instead of raised (`seam-void-2`, which discriminates on the reason line, since the exit code is
  2 either way); and the post-write read-back deleted, which survived the first battery and is
  what `lying-update-ref-2` was added to kill.
- The anti-weakening contract holds by measurement: the fixture is a net add of 22 cases, no
  assertion is removed, no suppression or skip marker is introduced, and the one edit to an
  existing file's behaviour (`loader.py`'s `adapt`) leaves `loader_test.py` at 27 of 27.
- `advance.py` and `attempt.py` are NOT on the commit path while the fixture is, for the reason
  the loader is not: both resolve examiner material through the loader, `pinned_root` names a
  directory the machine-hardening checklist has not created on any machine here, and a tool that
  VOIDs on the commit path blocks every commit rather than reporting a defect. The fixture needs
  no such root—it builds its own.

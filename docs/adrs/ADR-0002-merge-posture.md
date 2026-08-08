# ADR-0002: The merge posture—the chain stops short of the published trunk

**Status:** Proposed (2026-08-07).
Acceptance gate: pre-draft and draft deep-reason passes recorded in
[reviews/ADR-0002-deep-reason.md](reviews/ADR-0002-deep-reason.md). Acceptance is reserved for
the operator's own read: this record's subject is exactly how much leaves the operator's hands,
so no adversary pass substitutes for that reading.

## Context

ADR-0001 decided how the chain knows where it is and what passed; this record decides what
happens at the end—what reaches `main` without a human turn, and how it comes back out. It is
the missing fourth record the ADR-0001 gates flagged, and the walkthrough marks its build step
"build this first."

The design doc's §4.12 replaced the struck human-merge invariant with revert plus three expiry
conditions and asserted "none applies on day one." That assertion is measured false in this
repository: the kit's `origin` is a public GitHub repository, CI fires on push to `main`, and
the chain's own definition of a satisfied story reads `origin/main`—so the first expiry
condition (anything pushed to a public remote) is live today wherever the chain publishes. The
backstop—revert, or PR rejection—is therefore sound only if the trunk crossing is severed
from the chain's own acts. That severing is this record's first decision, and the rest follow
from it. Under the `open-pr` posture the record knowingly crosses that expiry for branch
content—story branches and their CI runs become public before any read—and scopes the
backstop claim to the trunk: what this record protects is `main`.

Two more measured facts bound the decisions. §4.12's conjunct set carries no evidence marks,
and two of its conjuncts fail on inspection: CI-green is not locally re-derivable (a local
merge triggers no CI run), and the sketch's "only one testimony conjunct" undercounts—the
planner's declared path list is a second agent-authored input. And the archived chain's
auto-merge blocker resolves narrower than earlier records stated: its pinned-predicate half is
discharged by ADR-0001/D3, its forgery-root object retired with the ledger; the surviving
residue is that a forged phase ref buys phase-skipping at the merge step, since the conjuncts
themselves read no phase ref.

## Decisions

### D1: The chain's terminal act is declared per repository, and the trunk is never the chain's

Two terminal acts are lawful, declared in the repository's chain profile:

- **`open-pr`** (a repository whose remote takes pull requests): when `merge_ok` holds, the
  sequencer pushes the story branch and opens the PR, with the documenter's briefing as the
  body. The chain then stops. What crosses onto `main` is governed by the PR-merge rules the
  operator runs outside the chain—their own review tiers, veto timers, and escalations,
  operated with their interactive instance. Branch publication is this posture's disclosed
  cost: story content and PR CI runs become public before any human read.
- **`merge-local`** (a repository with no forge, or an operator who wants nothing published):
  when `merge_ok` holds, the sequencer merges `--no-ff` into the local `main`. Publication of
  any kind is the operator's act.

Under both, the published trunk never advances by a chain act: with `open-pr` it advances
only through the operator-side merge rules; with `merge-local` only through the operator's
push. The chain never pushes `main`, anywhere, under any posture—that invariant is what
keeps revert (or PR rejection) a real backstop rather than an expired one. This amendment
was operator-directed (2026-08-08): the PR surface is where the operator's own merge
machinery already lives, and the record now routes the trunk crossing through it rather
than around it.

### D2: The merge posture is declared per repository, never per class

Each repository's chain profile declares its own posture facts (remote kind, publication rule,
trusted-base list). No repository-class default exists, because the class does not: the two
first targets differ on every posture fact—the kit public with CI, the lab on a local bare
remote that never gets GitHub.

### D3: The merge conjuncts are these, decided here rather than by reference

`merge_ok` gates the terminal act—opening the PR or merging locally—so a story that
cannot pass parks instead of surfacing. It holds when all of the following hold, evaluated by
the sequencer per ADR-0001/D2 against the trial merge of the pinned candidate sha into the
current local `main`:

1. the repository's own commit-path check is green at the merged tree, run at the seam—CI is
   a post-publication signal on the operator's push, never a merge conjunct;
2. the cumulative diff touches no trusted-base path, where the exclusion list contains its
   own file and every path the commit-path check invokes or reads, so a story can neither
   widen its own cage nor edit the check that clears it nor the inputs that check consumes;
3. the cumulative diff reconciles against the plan's declared path list;
4. the reviewer's coverage receipt is present and complete against a re-derived denominator
   (D4);
5. no undisposed refutation stands;
6. no park ref stands for the story;
7. every conjunct above was evaluated against one pinned merge-candidate sha, and the merge
   commits exactly that sha—a head that moved between evaluation and merge fails and
   re-walks (the design's own unsound-without condition, kept);
8. the tree the checks graded is the tree being merged—source-set integrity. Its mechanism
   (a manifest, a clean-checkout comparison) is decided at the sequencer build, where its
   court lands; stated here as a conjunct owed a mechanism, not as one that exists.

### D4: `merge_ok` has exactly two testimony inputs, and both are named and bounded

The per-lens findings inside the reviewer's receipt are testimony by design—they carry what
no check possesses (which dimensions were examined). Their denominator is not testimony: the
expected lens set is re-derived from the rules' declared grades, read from the pinned
examiner copy per ADR-0001/D3 and never from the judged tree—a grade edit in the judged
worktree must not be able to shrink the denominator—and a receipt shorter than the derived
set parks the story, so a skipped dimension cannot read as covered. The planner's
declared path list is the second testimony input: it is bounded by conjunct D3.2, which runs
against the whole diff independent of any declaration, and the declaration is carried verbatim
in the merge record so its width is visible to the operator afterward.

### D5: The forged-ref residue is consumed, not closed, and D1 confines it

ADR-0001 disclosed that an agent with Bash can forge a phase ref. The same namespace
writability cuts twice more here: conjuncts D3.5 and D3.6 read refutation and park state, so
an agent can also evade a park or a refutation by deleting its ref. Closing that path belongs
to the containment-posture record. Until it closes, the consumption rule is: the merge record
names the residue as open, and D1 confines its blast radius—under `merge-local` a forged
advance, an evaded park, or a deleted refutation can at worst produce a bad local merge,
which revert removes; under `open-pr` it can at worst open an unearned PR, which surfaces on
the review side of the operator's own merge rules and never advances the trunk by itself.

### D6: There is no veto window; the PR is the review surface where one exists

A silence-based window confers authority on an absent observer, which the design itself
forbids for the reviewer; on an unattended run the expected observer count is zero, so the
window costs nothing and buys nothing. Under `open-pr` the window's job is done properly by
the PR itself: it sits until the operator's merge rules dispose of it, and silence merges
nothing *by a chain act*—whether the operator's own rules let a timer merge in their name is
their rule, made outside this record. Under `merge-local` there is no window at all—an unattended merge is an unattended
merge, bounded by revert, and the positive acknowledgment where wanted is the operator's
push.

### D7: Downstream consumption pins tags, never `main`

`install.sh --refresh-rules` and every other downstream consumer resolve a tagged release. A
bad merge must not reach a consuming repository before the backstop can act—under
`merge-local`, a bad local merge or a published one before revert; under `open-pr`, a bad PR
merge the operator's rules let through—and the tag rule covers all of them: a tag is minted
only by the operator, on a tree they chose to publish.

## Consequences

- Three chain reads name `origin/main`—story satisfaction, the story-graph read, and
  dependent unblocking—and where they point now follows the terminal act. Under `open-pr`
  they keep reading the merged trunk: a story is satisfied when its PR merge lands carrying
  the `Merged-Story:` trailer—supplied by the operator-side merge rules (a merge template,
  or the body argument of the forge's merge call), since the forge's default message does not
  carry it—and a merge without the trailer reads loud as unrecorded rather than silently
  satisfied. Dependents unblock at that witness, so unattended throughput is bounded by how
  fast the operator's merge rules dispose of PRs, which is exactly the machinery the operator
  already runs. The witness's per-posture mechanics land with the sequencer build. Under
  `merge-local` all three move to local `main` and dependents unblock overnight, with
  cross-machine consumers seeing nothing until the operator pushes. Each posture's
  throughput bound is its disclosed price, not an oversight; the design's remote-reading
  wording inherits a per-posture correction when the sequencer is built.
- The CI-green conjunct is gone from `merge_ok`, honestly: in both postures CI does not
  exist at evaluation time—under `open-pr` the PR CI starts only when the terminal act
  itself pushes the branch, under `merge-local` no run exists until the operator publishes.
  A red PR CI is an input to the operator's merge rules; a red post-push CI is operator
  territory, answered by revert or fix-forward at the same authority level that pushed.
- The trusted-base self-containment requirement (D3.2) regresses nothing but obligates the
  profile author: the archived chain's list covered its own file, the CI workflows, and the
  check surface. The design's later example keeps `scripts/` and `.githooks/` but drops the
  list's own file, the CI workflows, and `harness/`, which the commit-path check invokes
  throughout—the profile must restore all three.
- Two courts are live from this commit: `scripts/revert-sufficiency-check.sh` (the revert
  premise proven on a throwaway repository every commit) and `scripts/merge-posture-check.sh`
  (a chain profile must pair its terminal act with its push scope—`open-pr` with
  `push = "branches-only"`, `merge-local` with `push = "never"`, any other pairing or an
  unknown terminal fails, and an unparseable profile is could-not-run; with no profile it
  prints that there is nothing to guard rather than passing silently). The guard is opt-in by
  the key it guards—a profile with no `terminal` reads nothing-to-guard—so the sequencer
  itself refuses to run without a declared terminal act, fail-closed at the runtime; that
  refusal is a sequencer-build obligation named here.
- Still open, and tracked by the Falsification section: the receipt-denominator court, the
  trusted-base self-coverage court, and the merge-record grep for undeclared testimony inputs.

## Alternatives

- **The chain pushes the trunk**: destroys the backstop in the first target repository on
  day one (public remote, CI on push, downstream consumption)—the measured refutation of
  §4.12's "none applies on day one." Rejected as unsound under every posture; branch
  publication under `open-pr` is the accepted, disclosed exception, and it advances no trunk.
- **The finalizer returns as an agent to open the PR**: PR-opening is mechanical (push plus
  one forge call with the documenter's briefing), and the design already paid for the lesson
  that the terminal act must not belong to an agent—a documenter once deleted eleven
  unrelated story specs in a commit that reached a PR. The terminal act stays the
  sequencer's, gated by `merge_ok`.
- **A repository-class posture** (§4.12's frame): the class has two members and they disagree
  on every posture fact. Rejected as reasoning about a set that does not exist.
- **CI-green as a merge conjunct**: not re-derivable at evaluation time—under
  `merge-local` no CI run exists, and under `open-pr` the PR CI begins only when the gated
  act itself pushes the branch, so the conjunct would wait on a signal its own act creates.
  CI's honest place is downstream: PR CI feeds the operator's merge rules.
- **The veto window** (§4.12's operator window): silence-as-authority, explicitly forbidden
  for the reviewer by the same section; theater when unattended. Replaced by D6.
- **A bare "no undisposed refutation" receipt** (the walkthrough's E1 form): cannot
  distinguish a review that covered every dimension from one that skipped a dimension
  entirely—the walkthrough says so itself three sections earlier. Replaced by D4's re-derived
  denominator.
- **Tamper-evidence for phase refs decided here** (this ADR's own pre-draft sketch): the
  suggested mechanism read the event log at merge time, which ADR-0001/D5 forbids—an
  accepted Decision cannot be superseded from a differently-scoped record. Moved to the
  containment-posture record; D5 carries the consumption rule meanwhile.
- **The human merge as the standing backstop** (the struck §2 invariant): not rejected so
  much as relocated. Under `open-pr` the trunk crossing runs through the operator's own
  merge rules—the invariant's substance, with better machinery; under `merge-local` what D1
  retains is the human *publication*, with the local merge releasable to the machine because
  revert covers the local blast radius.

## Falsification condition

Per decision, each court named honestly—a future check is named as future, and an unwatched
condition reads as unwatched:

- **D1**: a chain profile pairing `open-pr` with any push scope but `"branches-only"`, or
  `merge-local` with any but `"never"`, or declaring a terminal act this record does not
  name—watched today by `scripts/merge-posture-check.sh`. A chain push of `main` under any
  posture falsifies the invariant outright; its mechanical court (a push-scope guard in the
  sequencer's git wrapper) lands with the sequencer. The operator-side half (a human merging
  or pushing a tree they did not read) is unmechanizable and reads as such: the trunk
  crossing is a judgment act by design.
- **D1's premise**: if reverting a `--no-ff` merge fails to restore the pre-merge tree hash,
  the posture's foundation is wrong—watched today, every commit, by
  `scripts/revert-sufficiency-check.sh` on a throwaway repository, with its proven scope
  stated in the script: a HEAD merge with no conflicts; the older or conflicted case is
  operator judgment and is not claimed.
- **D3.2**: a profile whose trusted-base list omits its own file, the CI workflows, or any
  path the commit-path check invokes or reads—future check, shape fully specified; VOID
  while no profile exists, never a pass.
- **D4**: a reviewer emitting fewer lenses than the denominator derived from the pinned rules
  copy must park, and a receipt-completeness check with red and green fixtures per
  ADR-0001/D4 lands with the reviewer phase—future.
- **D5**: any `merge_ok` input that is agent-writable beyond the two D4 names—future,
  grep-shaped, activating with the first sequencer source.
- **D7**: a downstream consumer resolving kit `main` instead of a tag—future check on the
  installer; until it lands, the condition is watched only by review of `install.sh` changes,
  stated plainly as thin.

## Cross-references

- Supersedes: None. Builds on [ADR-0001](ADR-0001-advancement-re-derived.md) (D1, D2, D3, D5
  are load points; nothing here re-decides them).
- Superseded by: None.
- Related: `docs/sdlc-chain-design.md` §2, §4.9, §4.10, §4.12 (the section this record
  decides, correcting its unmarked premises); `docs/sdlc-chain-walkthrough.md` D7, E1, E2;
  `scripts/revert-sufficiency-check.sh`, `scripts/merge-posture-check.sh` (the live courts).
  Still owed: the sequencer-model and containment-posture records; the latter inherits the
  forged-ref closure D5 consumes.

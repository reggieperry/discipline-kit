# Decision coverage triage: a proposal

**This document decides nothing.** It is a recommendation for each of the eighteen Decisions
that `harness/chain_graph.py` currently reports as uncovered, written so the operator can
direct the batch in one pass. Nothing here is committed to an ADR, no story exists because of
it, and no check changes state until the operator says which decisions get stories and which
get waivers.

Measured against the branch, not recalled: `python3 harness/chain_graph.py` reports
`reverse coverage  19 decision(s) in 3 ADR(s): cited=1 waived=0 superseded=0 uncovered=18`.
The one covered Decision is ADR-0003/D7, cited by `stories/STORY-0001-headless-substrate-probe.md`.

## The rule these calls were made under

**STORY** where the Decision obligates an artifact that does not exist: a function, a script, a
schema, or a check with a red and a green case. **WAIVER** where the Decision removes a
mechanism or fixes a posture that every admissible implementation satisfies by construction, so
a story would have nothing to deliver.

One deliberate departure from the brief's framing. Where a Decision's obligation lands *inside*
a story recommended for a sibling Decision, this proposal recommends STORY and adds the
Decision to that story's `decisions:` list rather than waiving it. Citing is free, the checker
treats a multi-Decision story exactly as it treats a single-Decision one, and a waiver in that
position would record "nothing is owed" about an obligation that is in fact owed to a story that
might drop it. That is why sixteen of eighteen come out STORY and only seven stories carry them.

## The eighteen

| Decision | Subject | Call | Why |
|---|---|---|---|
| ADR-0001/D1 | position derives from sequencer-written refs | **STORY** (0006) | The derivation function and the atomic re-walk deletion do not exist; the ADR's own Consequences list them as still to do. `chain-refspec-check.sh` watches only the refspec edge. |
| ADR-0001/D2 | verdict is a sequencer-run postcondition at the seam, three-valued | **STORY** (0005) | Seam evaluation is an artifact, and D2's court is the denial probe replayed against a real sequencer: did-nothing FAIL, known-good PASS, tools-disabled could-not-run. |
| ADR-0001/D3 | the examiner never comes from the judged tree | **STORY** (0004) | The pinned resolution and the examiner-pinning test are artifacts, and both violations it names are already measured in the design's §4.8. Contestable, below. |
| ADR-0001/D4 | no verdict counts before red and green are demonstrated | **STORY** (0004) | Two fixtures per postcondition, and a loader that refuses an undemonstrated one, are code that does not exist. |
| ADR-0001/D5 | harness state for resumption and liveness, never position or verdicts | **STORY** (0006) | The resume path reads session ids and liveness, and D5's court is a grep-shaped source check that activates with the first sequencer source. Contestable, below. |
| ADR-0002/D1 | terminal act declared per repository; the trunk is never the chain's | **STORY** (0007) | Neither terminal act exists, and the push-scope guard in the sequencer's git wrapper is named as future by the ADR itself. |
| ADR-0002/D2 | posture declared per repository, never per class | **STORY** (0003) | The schema and the kit's own `.claude/chain/profile.toml` do not exist; `merge-posture-check.sh` reports nothing to guard today. Contestable, below. |
| ADR-0002/D3 | the eight merge conjuncts | **STORY** (0007) | None is evaluated anywhere, and conjunct 8 is stated as a conjunct owed a mechanism, decided at the sequencer build. |
| ADR-0002/D4 | two testimony inputs, denominator re-derived | **STORY** (0008) | The receipt, the derived denominator, and the completeness check with red and green fixtures all land with the reviewer phase, which is unbuilt. |
| ADR-0002/D5 | the forged-ref residue is consumed, not closed | **STORY** (0007) | The consumption rule has one deliverable: the merge record naming the residue as open. Closure belongs to the owed containment record. Contestable, below. |
| ADR-0002/D6 | there is no veto window | **WAIVER** | The decision removes a mechanism rather than obliging one: nothing is built, no timer is written, and the review surface it names under `open-pr` arrives with D1's terminal act. Its own Falsification section names no court for it, consistent with there being no artifact to watch. |
| ADR-0002/D7 | downstream consumption pins tags, never `main` | **STORY** (0002) | Measured against `install.sh`: `--refresh-rules` copies from whatever tree the checkout holds and reports a version scraped from `CHANGELOG.md`. No tag is resolved and no check watches it. |
| ADR-0003/D1 | the sequencer runs in a real filesystem | **WAIVER** | It retires Workflow-as-spine; all three surviving substrates hold filesystem and subprocess access by construction, so no artifact is owed. Contestable, below. |
| ADR-0003/D2 | the verdict channel is a pinned advance script's exit code | **STORY** (0005) | The canonical 0/1/2 contract, the adaptation of native contracts inside each advance script, and the scripts themselves are unbuilt. |
| ADR-0003/D3 | a phase ref is written only by the pinned advance script | **STORY** (0005) | ADR-0003's Consequences say D2 and D3 are the same build item as ADR-0001's postcondition harness, with the ref write moved inside it. |
| ADR-0003/D4 | the sequencer's own definition is examiner material, pinned | **STORY** (0003) | Its court is named as the profile check ADR-0002/D3.2 owes, extended one path set, so it lands with the profile and its check. |
| ADR-0003/D5 | the sequencer starts fail-closed | **STORY** (0006) | The refusal path is code: absent or unparseable profile, no terminal act, unset or incomplete `trusted_base`, each reading could-not-run and loudly. |
| ADR-0003/D6 | dedicated session and clone; every handoff is a commit | **STORY** (0005) | The porcelain-empty seam precondition is a check with a court, stated in the ADR as a decision rather than advice precisely because verdicts are not re-litigated. |

Split: **16 STORY, 2 WAIVER**, carried by **7 new stories** plus the existing STORY-0001.

## The proposed story set

Ids are the next seven free, allocated in the order below. `deps` follow the design's §6.1
ordering principle rather than the runtime order: build the verifier before the thing it
verifies, and build so an abandoned build leaves working tools.

### STORY-0002 · Resolve downstream consumption from a tagged release, and check it

- `adr: ADR-0002`, `decisions: [D7]`, `deps: []`, group B, milestone the operator's call.
- Walkthrough row: **none**. This is outside the 21 steps and needs no chain, which makes it
  §6.2-shaped: it pays whether or not the chain is ever built.
- Delivers: `install.sh` resolving a tag rather than the checkout's current tree, and a check
  that fails when a consumer would resolve `main`. The ADR calls the present watch thin, which
  is the argument for building it rather than against.

### STORY-0003 · The chain profile: schema, the kit's own instance, and its integrity check

- `adr: ADR-0002`, `decisions: [D2]` plus `ADR-0003/D4` (see the note below on cross-ADR cover),
  `deps: []`, group A.
- Walkthrough row: **none** directly; the nearest is D7's trusted-base exclusion conjunct.
- Delivers: `.claude/chain/profile.toml` for this repository, and a profile-integrity check that
  fails when `trusted_base` omits its own file, the CI workflows, any path the commit-path check
  invokes or reads, or the sequencer's definition and advance-script paths.
- Why early: two courts are VOID today for want of a profile, and `merge-posture-check.sh`
  currently prints that there is nothing to guard. This story converts both into live checks
  without a line of sequencer code.

### STORY-0004 · The postcondition loader: examiner material pinned, and no verdict before red and green

- `adr: ADR-0001`, `decisions: [D3, D4]`, `deps: []`, group A.
- Walkthrough row: **none**. The table's rows are phases; the instrument that grades them is
  assumed by "the main loop drives" and carries no row of its own.
- Delivers: resolution of postconditions, the checks they call, their configuration, and their
  fixtures from a pinned location outside any working tree; a loader that treats an
  undemonstrated postcondition's verdict as could-not-run; and the examiner-pinning test, where
  a verdict must not change when only the judged tree's own copies change.

### STORY-0005 · The pinned advance script: one exit-code contract, and the ref write inside it

- `adr: ADR-0003`, `decisions: [D2, D3, D6]` plus `ADR-0001/D2`,
  `deps: [STORY-0001, STORY-0004]`, group A.
- Walkthrough row: **none**. Every Stage D phase row assumes this seam without naming it.
- Delivers: the 0/1/2 contract at the boundary with every other code reading could-not-run; the
  ref written as the script's last act with a failed write forcing a nonzero exit; the
  porcelain-empty precondition at each seam evaluation; and the denial-probe replay as the
  court, per ADR-0001/D4's red-and-green rule applied to the seam itself.

### STORY-0006 · The sequencer core: fail-closed start-up and re-derived position

- `adr: ADR-0001`, `decisions: [D1, D5]` plus `ADR-0003/D5`,
  `deps: [STORY-0001, STORY-0003, STORY-0005]`, group A.
- Walkthrough row: **none**; C1 and C2 read position but do not build it.
- Delivers: the derivation function over `refs/chain/<story-id>/attempt-<a>/phase-<n>`, the
  re-walk rule's single atomic `git update-ref --stdin` deletion, the start-up refusal, and the
  resume path reading session ids and liveness and nothing else. Courts: a fixture repository
  where derived position must equal planted refs, and the grep-shaped source check for D5.

### STORY-0007 · The merge stage: `merge_ok`'s conjuncts and the declared terminal act

- `adr: ADR-0002`, `decisions: [D1, D3, D5]`, `deps: [STORY-0003, STORY-0006]`, group A.
- Walkthrough rows, all three existing: **D7 merge stage** (not built, marked "build this
  first"), **E1 the verdict** (not built), **E2 veto window, then merge** (partial: `--no-ff`
  works, the refusing wrapper and the `Merged-Story:` trailer do not).
- Delivers: the trial merge against one pinned candidate sha, the eight conjuncts with a
  per-conjunct receipt, conjunct 8's mechanism chosen here as the ADR reserves, the terminal act
  in both postures, the push-scope guard, and the merge record naming the forged-ref residue as
  open.
- Note on `deps`: shortening this to `[STORY-0003]` and building the merge stage as a standalone
  script is what the walkthrough's "build this first" implies. That tension is real and is named
  below rather than resolved here.

### STORY-0008 · The reviewer's coverage receipt and its re-derived denominator

- `adr: ADR-0002`, `decisions: [D4]`, `deps: [STORY-0004]`, group B.
- Walkthrough row: **D5 reviewer** (not built).
- Delivers: the receipt's shape, the denominator re-derived from the rules' declared grades read
  from the pinned examiner copy, the park on a receipt shorter than the derived set, and the
  receipt-completeness check with red and green fixtures.
- Depth: this is honestly a stub. The reviewer phase itself is a larger unit that no Decision in
  these three records obligates, so this story covers the receipt half only, which is the half
  `merge_ok` reads.

### Cross-ADR cover, and whether the schema allows it

Three of the proposed stories cover Decisions from two records at once: STORY-0003
(ADR-0002/D2 and ADR-0003/D4), STORY-0005 (ADR-0003/D2, D3, D6 and ADR-0001/D2), and STORY-0006
(ADR-0001/D1, D5 and ADR-0003/D5). **The story schema does not express that**: `adr:` is a single
value and `decisions:` is read against it, so a story cites Decisions of exactly one record.

Two ways out, and this is a call the operator should make before the stubs are written:

- **Split each of the three into two stories**, one per record. Ten new stories rather than
  seven, each with a single `adr:`, no schema change. The split is artificial at the build level
  and costs three extra files plus a `deps` edge joining each pair, which is cheap.
- **Extend the schema** so `decisions:` entries may carry an ADR prefix. That is a parser change
  and a fixture change in the same commit as the wiring, which is more moving parts on the
  commit that is meant to make coverage an invariant.

This proposal assumes the first, because the second changes the checker in the commit that
turns the checker into a gate. Under the split, the count becomes **ten new stories** and the
decision coverage is identical either way.

## The two draft waiver lines

Each goes in its Decision's own body, as the last line under that heading, in the ADR file. The
checker takes the reason from the waiver's first physical line, so each is one line. Closed
dashes, matching the ADR files, which are not on the em-dash exempt list.

Under `### D6: There is no veto window; the PR is the review surface where one exists` in
`docs/adrs/ADR-0002-merge-posture.md`:

```
Covered-by: none—the decision removes a window rather than adding one, so nothing is built.
```

Under `### D1: The sequencer runs in a real filesystem` in
`docs/adrs/ADR-0003-sequencer-obligations.md`:

```
Covered-by: none—it retires Workflow-as-spine; the surviving substrates satisfy it by construction.
```

Both parse as waivers with a reason. `Covered-by: none` with nothing after it is not a waiver
and reads as uncovered, which is the failure mode to avoid when editing these by hand.

## Contestable calls

Five, each with the case for the other side in one sentence.

- **ADR-0001/D3** (examiner never from the judged tree). Waiver: it is a prohibition on how
  postconditions resolve, and a story delivers no artifact the harness story would not deliver
  anyway. Story, recommended: the pinned copy and the examiner-pinning test are artifacts, and
  the design has already measured two reachable instances of the violation.
- **ADR-0001/D5** (harness state for resumption and liveness only). Waiver: the prohibition half
  is satisfied by construction if the sequencer is built as STORY-0006 describes. Story,
  recommended: the grep-shaped source check is a real deliverable, and "satisfied by
  construction" is the claim that check exists to test.
- **ADR-0002/D2** (posture per repository, never per class). Waiver: it forbids a default rather
  than obliging a mechanism. Story, recommended: its positive content is the profile's schema
  and this repository's instance, neither of which exists.
- **ADR-0002/D5** (forged-ref residue consumed, not closed). Waiver: the decision explicitly
  defers closure to the containment record and confines the blast radius through D1, so nothing
  is owed here. Story, recommended: the merge record naming the residue is a concrete
  acceptance criterion, and waiving it would record "nothing owed" about the one line that
  makes the consumption rule visible.
- **ADR-0003/D1** (real filesystem). Story: its Falsification names a grep-shaped source check,
  which is an artifact. Waiver, recommended: that check would be vacuous until a sequencer
  source exists and trivially true afterward, because the decision's work was eliminating a
  candidate.

## Two things this triage does not do

**Closing decision coverage does not mean the chain is decomposed.** Most of the walkthrough's
21 rows are obligated by no Decision in any of the three records—B1 `propose`, B3 `agree`,
C1 `ready`, C2, D1 planner, D2 worker, D3 the plan-to-code completeness check, D4 tester,
D6 documenter, and E3 archive among them. Reverse coverage is one bit per Decision, and it sees
none of those, because no Decision names them. A green checker after this closes means every
*Decision* has a story or a stated reason it needs none, not that the build is planned.

**The build order this proposal implies is not the walkthrough's.** The walkthrough marks D7
"build this first"; ADR-0003's Consequences make the D7 substrate measurement the sequencer's
first commit; and §6.1 says build the verifier before the thing it verifies. The `deps` edges
above follow §6.1, which puts the merge stage sixth. The walkthrough's line predates ADR-0003
and predates ADR-0002's `open-pr` amendment, under which the chain no longer merges the trunk at
all. Reconciling the two is the operator's, and it is a `deps` edit either way.

## How this closes

Once directed, one commit does all of it, and the commit is what makes the state an invariant
rather than a report:

1. **Add the directed waiver lines** to their Decisions' bodies in the ADR files.
2. **Write the directed story stubs** under `stories/`, all in the same commit. This matters
   mechanically: a `deps:` id naming a story that does not exist yet is a `DANGLING-DEP`
   finding, not a warning, so a partial batch fails the very check the commit is wiring.
   Stub depth is legitimate here by the walkthrough's own rule: full specs for imminent work,
   dep edges and rough scope for anything months out.
3. **Wire the checker** into `scripts/check.sh` beside its fixture, which is already there.

Six statements about the current state go stale in that same commit and belong in the same diff:

- `scripts/check.sh` line 31, the comment explaining why the checker is not wired.
- `docs/sdlc-chain-walkthrough.md` A5's build-state row, which reads "partial" and says the
  checker is NOT on the commit path.
- The build-state tally above the table, which reads "2 built, 4 partial, 1 operator action, 14
  not built" and becomes 3 built and 3 partial when A5 moves. That line has already been wrong
  once by arithmetic, so it is worth recounting off the table rather than adjusting by one.
- `docs/sdlc-chain-walkthrough.md` A5's prose, "BUILT, AND UNWIRED ON PURPOSE", including its
  18-of-19 figure.
- `stories/README.md`, which says the checker runs on demand and is not on the commit path.
- `harness/templates/story-template.md`'s guidance comment, which says the same thing to every
  author of a new story.

STORY-0001's Notes section also states that the other Decisions read UNCOVERED. That one is a
record of what was true when the story was written and can stay as written or gain a line; it is
a judgement call, not a stale assertion in a check's explanation.

**What the commit buys.** From then on, coverage is a commit-path invariant: a new ADR whose
Decisions have no story and no waiver fails the commit that adds it, as does a story naming an
ADR that is not registered, a `decisions:` entry that resolves to no heading, a `deps:` id that
does not exist, and a cycle. The cost is named plainly: every future ADR pays decomposition at
authoring time rather than deferring it, which is the discipline being bought and also the
friction being accepted.

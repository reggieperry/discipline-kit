# The SDLC chain, end to end

**Status: almost none of this is built** — see the build-state table below, which covers all 21 steps
and is checked against kit `main`. `docs/sdlc-chain-design.md` carries the reasoning; §6.1 of it
carries the principle that orders the work, and §6.2 the items that pay with no chain at all. This
document is the operational walk that design implies, written so the gaps are visible as gaps. Every
step names who runs it, what it reads, what it writes, and — where it matters — the predicate that
decides it happened.

Read `sdlc-chain-design.md` §3.10 (the story graph), §4.8 (the substrate), §4.9 (what the pack was
buying), §4.10 (the failure edge), and §4.11 (the completeness chain) for why any of it is shaped
this way. Nothing here re-argues those.

---

## The four surfaces

Everything below happens on one of four, and which one matters more than it looks.

| Surface | Can it check a fact? | Notes |
|---|---|---|
| **Operator** | yes | Decides, agrees, merges. The only surface with authority over what reaches main. |
| **Main loop** | **yes** | The interactive session. Holds context, runs git and the suite. Sequences the chain and computes every phase verdict. |
| **Subagent** | yes, but reports as testimony | Fresh context. Optional worktree. Must commit or its work is auto-cleaned. |
| **Workflow script** | **no** | No filesystem, no subprocess, no network. Deterministic control flow only. Admissible *inside* a phase, never as the spine. |
| **Git hook** | yes | Runs on the bytes being committed, fires inside subagent worktrees, regardless of which agent acts. |

The rule that follows from the table: **the main loop drives.** A workflow cannot sequence the
phases, because it runs to completion before returning and a re-derived verdict is needed *between*
them.

---

## Build state — all 21 steps

Checked against kit `main`, not recalled. **1 operator action, 4 partial, 16 not built.** Any step
not in this table is a step this document forgot; the count is written down so it cannot quietly
shrink.

| Step | State | What exists |
|---|---|---|
| A1 design doc | operator | — |
| A2 write the ADR | **partial** | `harness/templates/ADR-template.md`; still cites the retired ledger's `clm-NNNN` |
| A3 index it | **partial** | registry table in `docs/adrs/README.md`; **zero ADRs registered** |
| A4 decompose into stories | not built | no template, no schema, no parser |
| A5 commit-path integrity checks | not built | no `chain-graph` |
| B1 `propose` | not built | |
| B2 fix the coverage gap | not built | needs B1 |
| B3 `agree` | not built | |
| C1 `ready` | not built | |
| C2 take the first READY story | not built | needs C1 |
| D1 planner | not built | 0 chain agents on `main`; the five exist only on tag `archive/kit-chain` |
| D2 worker | not built | as above |
| D3 completeness check, plan→code | not built | |
| D4 tester | **partial** | the differential exists — `reference/sdlc-gate.py`, 1619 lines, Checks A/B/D, suppressions and skip markers — and is wired into no phase |
| D5 reviewer | not built | |
| D6 documenter | not built | |
| D7 merge stage (main loop, not an agent) | not built | **build this first** — incl. trusted-base exclusion and sha pinning |
| E1 the verdict | not built | the conjunct set of §4.12 |
| E2 veto window, then merge | **partial** | `git merge --no-ff` works; the refusing wrapper, the `Merged-Story:` trailer, and the window do not exist |
| E3 archive | not built | |
| E4 next `ready` unblocks dependents | not built | needs C1 |

Two things the table makes visible that prose hid. **The ADR machinery is the most nearly-complete
part and has zero instances** — a template and a registry with nothing in them, which is a scaffold
rather than a practice. And **the one substantial piece of working code, the differential gate, is
attached to nothing**; it is 1619 lines of exactly the check D4 needs, sitting unwired.

---

## Stage A — Deciding what to build

No chain. Operator only. This stage is why the chain can be checked at all: it produces the
declarations everything downstream is checked against.

### A1 · Write or extend the general design doc

`docs/design/<subject>.md`. What the system is to do. This is the root of the lineage and the source
the planner's completeness check reads.

### A2 · At a fork, write an ADR

A verdict-shaped, hard-to-reverse choice — a schema, a protocol, a fail posture. `docs/adr/ADR-NNNN-<slug>.md`,
id stable and never renumbered, with the fixed section order: **Context**, numbered **Decisions**
(D1, D2, …), **Consequences**, **Alternatives**, **Falsification condition**, **Cross-references**.

The falsification condition is the section that makes an ADR checkable rather than a memo: it states
what would show the decision wrong, and where that is mechanically checkable it names the check.
Decisions are superseded individually and never deleted — a superseded D keeps its text and gains a
banner naming its successor and what it **retains**.

### A3 · Index it in the same commit

One line in `docs/adr/README.md`'s registry. Committed with the ADR, so the file and its
discoverability cannot drift apart.

### A4 · Decompose each Decision into stories

One file per story under `stories/`, the only writer of its own node.

```yaml
---
id: STORY-0041
title: Parse the slot descriptor
adr: ADR-0007
decisions: [D1]
group: A
milestone: v1-slot-identity
deps: [STORY-0039]
cites:
  - docs/claim-algebra/claim-algebra.html#sec-1-4
acceptance:
  - A descriptor missing a field is rejected, naming the field.
---
```

Body: **Outcome** (one sentence, user-observable), **Acceptance criteria** (a checkbox list the
tester verifies), **Scope** (`In:` / `Out:`), **Notes**.

**Write to depth by proximity.** Full specs for imminent work; light stubs — dep edges and rough
scope — for anything months out. The graph must be complete; the specs need not be. A thin future
story is honestly `prose`-mode under §4.11 and is counted as such.

### A5 · Commit to main; the commit-path checks run

Six integrity checks read only trunk blobs and cover **every** story and ADR, not just agreed ones —
a cycle inside an unagreed ADR is still a cycle. Each prints its denominator so that finding nothing
is distinguishable from looking at nothing.

Parse (unknown key, duplicate key, duplicate id across files — all fatal, naming both) · dangling
`deps` ids (**its own exit code**, separate from cycles, because both produce the same Kahn residual
and send the operator to different remedies) · cycles · unresolvable `adr:`/`decisions:` references ·
`ADR-0000` orphan ratio, printed every run so the escape hatch is watched · reverse coverage, where
every non-superseded Decision must be cited by a story or carry `Covered-by: none — <reason>`, and
**an ADR yielding zero parsed decisions is an error**, because a zero-decision parse is otherwise
indistinguishable from full coverage.

**Every one of these checks is pinned by two fixtures — a known-good returning 0 and a known-bad
returning non-zero — and the pinning is not polish.** A predicate that always fails and a driver that
always halts are externally indistinguishable from a working fence; the kit's own archived
`postcondition.py` was exactly that for a month without anyone noticing. A check whose failing case
has never been demonstrated is not a check.

**NOT BUILT.** No `chain-graph` script exists.

---

## Stage B — Agreeing a set

### B1 · Propose

```
$ chain-graph propose ADR-0007
ADR-0007  Slot identity and the typed descriptor      (Accepted)
  D1  the slot is a typed descriptor        -> STORY-0041, STORY-0042
  D2  resolution is slot-indexed            -> STORY-0043
  D3  materialization compares              -> STORY-0044
  D4  the record commits once               -> NO STORY

  order (critical path first)
    1  STORY-0041  A  parse the slot descriptor      height 3
    2  STORY-0043  A  index resolution by slot       height 2   deps STORY-0041
    3  STORY-0044  A  compare at materialization     height 1   deps STORY-0043
    4  STORY-0042  A  the identity criterion         height 1   deps STORY-0041
  depth 4 -> at least 4 merge cycles.  external blockers: none.  closure: OK
```

Order is Kahn over the agreed subgraph, keyed `(-height, group, set-line-index, id)` — critical path
first, because depth costs human merge cycles and breadth does not. `tsort` runs on the same edges as
a second opinion **read only for its exit status**, since it prints an ordering even for cyclic input.

**Depth is printed before agreement, on purpose.** Nothing is satisfied until a human merges, so a set
worked in one session goes as *wide* as it allows and exactly *one deep*.

### B2 · Fix the coverage gap

`agree` refuses while D4 has no story. Write one, or write `Covered-by: none — <reason>` under the D4
heading. Neither is silent; waivers are counted and printed every run.

### B3 · Agree

```
$ chain-graph agree ADR-0007
+# 2026-08-02  slot identity, first pass
+ADR-0007
committed 8c41ee2  "chain: agree ADR-0007 (5 stories, depth 4)"
```

A `.chain/set` line is an ADR id (meaning all its stories) or a single story id. **The commit is the
agreement record** — author, timestamp, diff, revertable. Parking a story is deleting its line and
committing: a scope decision recorded like every other scope decision, not a ref and not a field.

---

## Stage C — The daily loop

### C1 · Ask what is workable

```
$ chain-graph ready
# trunk origin/main @ 3f2a1c9 (fetched 12s ago)
READY      STORY-0041  A  parse the slot descriptor   mode=enumerable (2 cites, 2 anchors)
BLOCKED    STORY-0042  A  deps STORY-0041
census: 1 READY | 0 IN-FLIGHT | 4 BLOCKED | 0 SATISFIED | 0 UNRECORDED
        ADR-0000 stories 0/5 | prose-mode stories 0/5 | waived decisions 0
```

**Satisfied means:** `origin/main` holds a merge commit carrying the trailer `Merged-Story: <ID>`
whose second parent is the story branch tip. Not a phase ref. Not a branch existing. Not a file the
merge stage wrote. Chosen because a chain-written record can go true by accident — an ordinary
`--ours` conflict resolution merges the record while dropping the code — and a content predicate can
go false by routine maintenance, since a `git mv` would un-land a merged story.

The strict witness decides; a loose scan exists only to catch it reading false. Disagreement is named
and loud: `SQUASHED`, or `MERGED-UNRECORDED` when a tip is an ancestor with no merge record.

**The main loop branches on the exit code, never the prose** — and treats exit 0 with empty stdout, or
a missing terminal OK line, as a **broken instrument** rather than "nothing to do". `git for-each-ref`
on an empty namespace and `git ls-tree` on a missing path both print nothing and exit 0.

### C2 · Take the first READY story

The main loop spawns phase 1. Stage D runs once per story.

---

## Stage D — One story through the chain

Five agent phases, then a main-loop merge stage. The pattern is identical each time and is the design's central property: **the main loop
spawns the subagent, the subagent returns, the main loop cuts its own scratch worktree from that
phase's ref and evaluates the predicate itself, then spawns the next.** No agent computes whether the
chain advances.

Two conditions hold on every main-loop verdict:

- **Pin the environment at the point of signing.** Scripts that read tunables from the environment,
  with a gitignored `.envrc` in play, mean the signing surface is weakenable by state no `git diff`
  can see.
- **Take the examiner from the base, not the judged branch.** A check script that resolves itself
  relative to its own path runs the *worktree's* copy — letting the judged party supply its own
  examiner. `git checkout $BASE -- scripts .githooks build.sbt` into the scratch tree first.
- **Pin the verdict against a phase that could not act, before trusting it.** Run a phase with every
  write path withheld and assert the main loop reports FAILURE. This is not optional and it is not
  defensive: measured, such a phase reports `subtype: "success"`, `is_error: false`, an empty
  `permission_denials`, and exit 0 while doing nothing at all. A verdict without this test is
  verified only by never having been given a phase that could not act.

### D1 · Planner

Subagent, no worktree. Reads the ADR and its cited sources; parks the plan and its obligation rows.

**Before it starts, the main loop derives the completeness mode** from what the story cites —
`enumerable` if it cites a document and a locus, `listed` if whole documents, `prose` if nothing.
Derived, never declared: a planner that chose its own mode would be the party judged picking its own
standard, and the incentive runs one way. Derivation is monotonic toward the strong end; nobody
reaches a weaker mode than their citations support.

**Completion:** every unit extracted from the source is accounted for by at least one plan row, with
the denominator printed — "47 numbered results in §8 examined, 0 unclaimed". Re-derived by the main
loop. **No source resolves → VOID, not a pass.**

**On failure:** not-plannable is a typed park, never a bounce. There is nothing upstream.

### D2 · Worker

Subagent **with worktree**, branched from the planner's tip. Builds through the gate, runs its own
mechanical self-audit queries over its diff, fixes what they return, and **commits** — the commit is
the handoff, and an uncommitted worktree is auto-cleaned.

The self-audit's output is an **artifact**, never a statement that it audited, and a query returning
nothing must print what it looked at: "no unexercised symbols" and "the query found no symbols to
check" are the same output and different facts.

The commit fires the repo's `pre-commit` hook, which runs the gate on the actual bytes. That makes a
commit partly self-certifying — but only partly, which is why the next step exists.

**Completion:** the commit exists, and the main loop **re-runs the gate on that tree** with a
base-provided examiner. The hook is not the verdict; it is a first line that runs in the right place.

**On failure:** back to the worker within the bounce budget.

### D3 · Completeness check — plan to code

Main loop, no agent. A set difference: did every obligation the plan parked get an answer? Mechanical
and re-derivable, and it runs **here**, before the tester, because it is grep-shaped and the tester is
a full suite run. Cheapest gate first.

This check is only as complete as the rows it reads — which is exactly why D1's seam matters. A thin
plan produces a chain where everything passes.

### D4 · Tester

Subagent with worktree from the worker tip. **Attest only; never touches production code.**

**Completion:** the diff touches test paths only, the gate is green, and the **differential** against
merge-base is clean — no new suppressions, no new skip markers, no deleted tests, no lost assertions.
"Gate green" is absolute where anti-weakening is a comparison: a deleted failing test makes an
absolute gate greener.

**On failure:** back to the worker, with the failing output.

### D5 · Reviewer

A **workflow inside the phase** — one subagent per lens, each committing its own findings to its own
branch. The main loop unions from refs, never from the workflow's return string.

Reads the specification against the code. **Never approves.** Three outputs, and they map one-to-one
onto three dispositions:

| Output | Disposition |
|---|---|
| refute | back to the worker, findings verbatim |
| absence, with a coverage receipt | advance |
| could-not-inspect | typed park for the operator; the chain stops |

The third state is why the output is three-valued. A reviewer restricted to refute-or-absence, when
blocked from reading, must either fabricate a rejection or emit a clean report — and the clean report
is likelier and worse. **The main loop enumerates the lenses it expected** rather than unioning
whatever refs it finds, which is what makes a lens that never ran visible.

### D6 · Documenter

Subagent. Writes the PR body and the operator's briefing — the derived brief that went missing when
auto-merge was dropped, and which matters *more* here than in the pack, since the pack could
auto-merge its glance tier and this chain never can.

Kept as its own step rather than folded into the merge stage: a documenter once shipped a clean feature
doc and silently deleted eleven unrelated story specs in the same commit, and it reached a PR.

### D7 · The merge stage — main loop, not an agent

**No subagent here.** The finalizer's warrant was *package and park for operator merge*; §4.12 retired
the parking, §4.9 moved the briefing to the documenter, and every verdict is the main loop's by
§4.2(a). What was left was integration plus predicates — an agent there is a shallow module that turns
mechanical facts into testimony on the way past, and the one non-mechanical case, a merge conflict, is
already a stale-baseline escalation (§4.10).

Fetch main and integrate, then on the **merged tree**, with a base-provided examiner:

| Conjunct | Why |
|---|---|
| the full gate | the merged tree exists nowhere else — the worker's gate ran on the worker's tree, the tester's on the tester's |
| cumulative scope reconciliation | against the planner's declared path list |
| source-set integrity | `sha256sum -c` against the vendored manifest, from the set's own directory |
| **trusted-base exclusion** | a diff touching `trusted_base` **parks regardless of green** — *a merger that can merge changes to its own judge is self-signing with a scheduler*. Path-prefix, symlinks resolved, moves-out blocked |
| **sha pinning** | re-read the head immediately before merging; abort if it moved, because every conjunct above was computed against a specific tree |

Each with a **per-conjunct receipt**, so a check that could not run never renders as green.

Hooks cannot cover any of it — git fires `pre-merge-commit` for an auto-committed merge, and the repo
ships only `pre-commit` and `post-commit`.

**NOT BUILT, and it is the first thing to build.** It was already the only unchecked artifact in the
chain; under §4.12 it is the only unchecked artifact that **ships by itself**. The last two conjuncts
are the conditions the archived `chain-finalizer.md` said autonomous merge would owe — written down
when merging was still deferred, and owed the moment it wasn't.

---

## The failure edge, across all of Stage D

**Triage before bouncing.** Three causes, three dispositions: a *worker fault* returns; an
*environment fault* parks, never bounces, because a worker cannot fix an absent dependency and
bouncing it is how a chain spends a night repairing something that was never broken; a *stale
baseline* re-integrates.

**The re-walk rule.** A return to the worker invalidates every verdict downstream of it. After the
fix, the tester and the reviewer run again — their prior findings describe a tree that no longer
exists.

**A bouncing step must commit before it returns.** An unchanged worktree is auto-cleaned, so a step
that stops without committing destroys its own account of why. The findings *are* the handoff.

**A bounce budget**, counting returns to the worker so a re-walk does not consume it. Two is a sane
default; then a typed park.

---

## Stage E — Merge

Formerly "the human merge". Under §4.12 the common path is unattended; the human is a *vetoer* rather
than a gate, and the escalation path is what their judgement is reserved for.

### E1 · The verdict

Every conjunct green — CI, the merged-tree gate, scope reconciliation, source-set integrity — and the
one testimony conjunct (no undisposed refutation) satisfied, is **`merge_ok`**. Anything else
escalates: a red conjunct, a reviewer that **could not inspect**, a check that could not run, or the
bounce budget exhausted. Size is reported, never branched on.

### E2 · The veto window, then merge

The documenter's briefing is posted and a short window opens. An objection during it stops the merge;
silence proceeds. The window is a property of `merge_ok`, not a second tier — it is what Elder's
`review_encouraged` actually bought, and it costs nothing when nobody is watching.

```
$ chain-graph merge STORY-0041
```

`--no-ff` by policy, writing the `Merged-Story: STORY-0041` trailer. The wrapper refuses if the branch
carries a merge commit (a story branch that merged a sibling), if the terminal phase ref is missing,
or if HEAD is not `main`. A forgotten `--no-ff` stalls loudly instead of releasing silently, which is
the direction allowed to be wrong.

**The safety argument is now revert, not review**, and it holds because this repository class has no
irreversible action — no capital, no live trade. It stops holding at three reachable points named in
§4.12: a push to a public remote, a consumed tag, and a change to the formal core documents. Until one
of those is in play, a bad merge costs a `git revert`.

### E3 · Archive

The story moves to `stories/_archive/` with `merged_pr`, `merged_sha`, `deviations`, and `lessons`
appended, so `git log -- stories/_archive/` becomes the searchable record of how the system was built.
`deviations` is the only place the acceptance criteria and what actually shipped get reconciled in
writing.

### E4 · The next `ready` unblocks the dependents

Satisfaction is now witnessed on trunk, so `chain-graph ready` returns the next story. Loop to C1.

---

## What this process does not do

- **A merge that drops the work still reads satisfied.** Parentage proves a human merged the branch;
  it does not prove the merge carried the diff. It belongs to re-running the story's named acceptance
  check against trunk afterward — a seam that is not placed.
- **Test quality has no reader.** With the slop rubric and mutation both out by decision, nothing
  detects an implementation-mirroring test, and the attest-only tester judged on "gate green" has an
  incentive pointing at it.
- **No step reads the finished code as code** against the project's own standards. Every reading step
  is defined by a different pairing.
- **Reverse coverage is one bit per decision.** It sees a decision with no story; never a decision
  that decomposed into four stories of which two were written.
- **Every check here is a drift detector, not a tamper barrier.** The phase agents hold Bash. The
  guards catch accident, crash and confusion — which is what actually happens — and under §4.12 the
  backstop is **revert**, not review. That is sound for this repository class and it expires at three
  named points: a public push, a consumed tag, and a change to the formal core documents.
- **Depth costs one merge cycle per level.** A four-deep set is a four-day set if the operator merges
  once a day.

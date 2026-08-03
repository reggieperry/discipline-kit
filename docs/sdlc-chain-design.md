# Design — a kit-local, language-pluggable, mostly-autonomous SDLC chain

**Status:** design doc. It explores; it does not decide. Per `docs/adrs/README.md`, the forks it
names — the sequencer model, the containment posture, the state authority — each warrant an ADR
before anything is built. None has been written.

**Supersedes:** the chain design on `feat/kit-chain`, archived as tag `archive/kit-chain`. That
branch's five agents and four support scripts exist only on the tag; `harness/chain/` is not on
`main`. So this revises a design that was never shipped, not one that is running.

**Provenance.** Produced 2026-08-01 by two multi-agent passes over the `sdlc-discipline-pack`, this
kit, and `claim-algebra-lab` as a second language instance, followed by a capability review of the
Claude Code documentation against a numbered list of the prior design's weaknesses, and three
adversarial verification passes. The verification passes rejected claims the first synthesis marked
verified on the strength of a documentation reading alone; the evidence convention below exists
because of that.

**Evidence convention.** Every mechanism carries one mark, and the marks are not decorative:

- **VERIFIED** — measured on a real machine, with the measurement named. Not "the docs say so."
- **DOCUMENTED** — stated in Claude Code documentation and checked against the installed 2.1.220
  binary where a flag or field name was involved, but not exercised end to end.
- **PROPOSED** — design invention. Not built, not measured. Some of it will be wrong.

Nothing is marked VERIFIED on a documentation reading. Where a measurement contradicts a document,
the measurement wins and the contradiction is recorded rather than smoothed.

**Two things a reader should carry into every section.** Containment of an agent holding Bash was
measured and largely does not hold — five of six deny-rule evasions succeeded. And the harness's own
success report is not a phase verdict — a phase that could do nothing reports success on every field
it exposes. Both are in §7, and both are the reason the human merge stays. A third, added after the
first draft: the chain detects the drift you can already detect, and not the kind that has actually
bitten this build — §3.

---

## 1. What changed, and why

### 1.1 Four things the prior design called impossible that are not

**The sequencer can run its own predicates.** The prior design's central constraint was "a Workflow script has no filesystem or shell access, so the sequencer cannot run its own predicate" — which forced an agent to mediate every phase transition and made the chain's central property (advancement decided by a mechanical predicate, re-derived from durable state, by a sequencer holding no judgment) unenforceable. That constraint was an artifact of choosing Workflow as the sequencer. A plain bash driver running `claude -p` once per phase is an OS process with a shell and a filesystem. Predicates become ordinary subprocess calls between invocations. **DOCUMENTED** (`claude --help` confirms `-p`, `--agents <json>`, `--output-format`, `--resume`); **VERIFIED** that real `claude -p` invocations complete and return parseable output.

**The chain can start without a human turn.** The prior design read `.claude/scheduled_tasks.lock` (`{sessionId, pid, procStart, acquiredAt}`, and it lives at *project* scope, not `~/.claude/` as the earlier draft said) and concluded correctly that `/loop` is session-scoped, therefore a human turn was structurally required. An OS cron entry invoking the bash driver needs no pre-existing session. **DOCUMENTED**, and trivially true of cron.

**There is a real filesystem partition for the attest-only grader.** `isolation: worktree` in subagent frontmatter puts the subagent's edits in a temporary git worktree and leaves the parent checkout untouched. The prior design enforced tester non-interference only by a post-hoc `git diff` from the driver. **DOCUMENTED** (sub-agents.md line 290). One caveat and its fix: the worktree branches from the *default branch*, not parent HEAD — set `worktree.baseRef: "head"`, documented for exactly this case ("Use this when isolating subagents that need to operate on in-progress work"). The prior draft's workaround (have the agent check out the worker's sha as its first Bash call) is unnecessary.

**Provider outages inside a run are survivable.** `CLAUDE_CODE_RETRY_WATCHDOG=1` retries capacity errors indefinitely; `system/api_retry` stream events carry `attempt`, `max_retries`, `retry_delay_ms`, `error_status`, and an error category. The prior design had no retry concept and treated an outage longer than a session as fatal. **DOCUMENTED**.

### 1.2 Six things the prior design assumed that turned out false

**Warrant containment by `tools:` list plus command grep does not contain a Bash holder.** Measured against the live deny rule `Bash(rm -rf*)`: `rm -fr` executed, `rm -r -f` executed, `/bin/rm -rf` executed, `python3 -c 'shutil.rmtree(...)'` executed, and `bash -c 'rm -rf <path>'` executed *carrying the literal banned string*. Only `R=rm; F="-rf"; $R $F` was denied, because the matcher resolves simple variable assignments. Five of six evaded. **VERIFIED**. The gap analysis's sentence "compound commands are split... so the trivial evasions are covered" is false: splitting and wrapper-stripping are real, but flag reorder, flag splitting, path qualification, and every interpreter argument go straight through. `bash -c` alone defeats the whole command-fence layer in one call.

**A tool-scoped hook is not a filesystem control.** The live `PreToolUse:Write` hook blocked a Write with exit 2 and its validator's reason on stderr — so hooks genuinely reach subagents, which is the design's central premise and is sound. Then the byte-identical content, written to the same path with `printf > file` through Bash, landed with no hook invocation. **VERIFIED**, both halves. An agent holding Bash never needs the instrumented tool.

**A denied tool call in headless mode does not fail.** `claude -p '...' --permission-mode dontAsk` with the call unapproved: the Bash call was denied, the file was never created, and the process **exited 0** with `is_error: false`, `subtype: "success"`, `stop_reason: "end_turn"`, and a `result` text asking permission of nobody. **VERIFIED**. A driver branching on `$?` reads a clean pass on a phase that did nothing. This is exactly the shape `craft-measurement.md` was written about, and it would have run every night.

**`--output-format json` is unusable for an unattended driver.** SIGKILL of a mid-turn `claude -p --output-format json` produced exit 137 and a **zero-byte** output file — a killed phase byte-identical to a phase that never started, with no `session_id` to resume and no cost. The same kill under `--output-format stream-json --verbose` left 16 usable event lines with no `result` event. **VERIFIED**. The absence of a `type: "result"` line is the clean completion signal the prior design said did not exist.

**User-scope settings are not out of the agent's reach, and neither are the hook scripts.** User-scope settings are owner-readable and owner-writable, and the phase agent runs as that same owner — measured by having a subagent touch the file and create a sibling. File modes are no barrier when the agent is the owner. The prior draft's "a project-scope deletion cannot remove the user-scope hook" protects against an adversary that was never the threat. Worse and unnamed anywhere before: the hook *bodies* are agent-writable too, being ordinary executable scripts owned by the same user. Pinning the config while leaving the script writable moves the recursion one file over. **VERIFIED**.

**The chain harness is not broken — it is not shipped.** `harness/chain/` does not exist on discipline-kit `main`. I confirmed this directly: `git ls-tree -r --name-only main | grep '^harness/'` returns twelve paths (rule grades, algebra validator, four skills, five templates) and nothing under `chain/`. All five chain agents and all four chain support files exist only under tag `archive/kit-chain`. So "a chain run today halts rather than advancing on a fake pass" describes a chain that cannot run at all. The prior gap analysis's claim of 34 ledger paths on the archive is correct for the `harness/ledger/` prefix (I measured 34); the verification lens's 28 counted a different prefix. Not a real disagreement.

Separately, the archived `postcondition.py` does `sys.path.insert(...); import model` at module scope (line ~34–36) and the ledger is gone, so it raises `ModuleNotFoundError` and exits **1**, not 2. Its docstring asserts exit 1 is "also fail-closed for the driver's purposes" — that is intent, not mechanism, and there is no driver to honor it.

### 1.3 What that adds up to

The prior design tried to buy containment from the harness's configuration surface and mostly bought labels. The revised design buys three things from the harness that it actually supplies — hooks that fire inside subagents, a worktree partition, and a parseable phase result — and puts everything else in the bash driver and in git, where it is re-derivable and where no agent mediates it.

---

## 2. The neutral core (unchanged)

Stated briefly because it survives intact.

**Five agents, one warrant each, and a main-loop merge stage.** planner (park the plan), worker (build through the gate, **then audit its own diff and fix what the audit returns before handing off** — §3.9), tester (attest only, never touches production code), reviewer (refute, report absence with a coverage receipt, or declare it could not inspect — never approves), documenter (the briefing, the feature doc, and the trigger entry that makes it findable — §4.9). Then the **main loop** integrates, re-derives the merged-tree conjuncts, and merges or escalates (§4.12).

Two changes from the archived agent files, both recorded where they were argued. The warrant is no longer claimed to be *enforced* by the frontmatter (§4). And **the finalizer is not an agent** — its warrant was *package and park for operator merge*, and with parking retired, the briefing moved to the documenter, and verdicts belonging to the main loop by §4.2(a), what was left was integration plus predicates (§4.12).

**~~The human merge is the transition-grade backstop.~~ RETIRED by §4.12 — and this entry is kept rather than deleted, because it was the load-bearing claim of the whole design and its removal should be visible.** It read: the chain is autonomous up to a merge-ready branch and no further; the finalizer does not merge; what reaches `main` rests on the human merge or a server-side gate, never on the local gate alone.

That held while the design assumed a sensitive-file list and a repository where a bad merge is expensive. Neither survives: the list is gone by operator decision (§4.9), and this repository class has no irreversible action — revert restores the prior state. **The backstop is now revert, and it has three named expiry conditions** (§4.12): a push to a public remote, a consumed tag, and a change to the formal core documents. When one of those enters play, this entry comes back rather than being re-argued from scratch.

**Review testifies; only a check signs.** A clean review is an absence report. A finding is real when its disposing check goes red.

**The operator writes the plan and the stories.** The chain does not decide what to build.

**No signing apparatus.** The dev-ledger is not coming back. Its obligation edges — `about`, `supersedes`, `discharged_by` — return as plain fields on a driver-written event log (§4.5). No claims, no hashes, no signatures, no `.hook-signed` forgery root.

**The two axes stay orthogonal.** Runtime (§4) names no language. Language (§5) supplies commands and scanners to a runtime that does not know what they are.

---

## 3. What work the chain suits, and what drift it catches

### 3.1 A slice is a story

The two words name the same thing. A slice of a layered build plan carries acceptance criteria, a
done-condition, and a scope, which is a story whose criteria happen to be structural rather than
user-facing. Feeding either to the chain works. The naming is not where the question lives.

The property that decides fit is this: **can you write the check before the work, such that the check
fails if the work is wrong?** The chain advances on a predicate re-derived from durable state, so it
works exactly as well as your ability to state, in advance and mechanically, what done means. Where
you can, it is excellent. Where you cannot, it is a machine for producing green builds.

That is the same test as red-first TDD, and the resemblance is not a coincidence — **the chain is TDD
lifted to the work-item level.** The planner writes the failing check and parks it; the worker
discharges it. Same cadence, one level up. Which means it inherits TDD's limits precisely: strong
where done is checkable, weak where the hard part is deciding what to build, and carrying the
identical blind spot that a passing check says nothing about whether the check could fail.

### 3.2 Three axes of fit, and they do not matter equally

**Is done mechanically checkable?** Decisive. If no, do not use the chain for that item.

**Is the check discriminating?** The trap, and the one no configuration surface reaches.

**Are the items independent?** This sets the size of the win, not whether it works. A strictly ordered
queue still gets role separation, re-derived advancement, and unattended operation; what it loses is
parallelism. "Grind through a sequence overnight and hand me merge-ready branches" is worth having on
its own.

### 3.3 The unit is smaller than a slice, so intake is decomposition

Slice 6 of the ClaimOS build shipped in one commit and split three ways under this standard
(**VERIFIED**, observed step by step):

| Part | Fit | Why |
|---|---|---|
| Rehabilitation results (Def 6.2.1, Thm 6.2.2, Cor 6.2.3) | good | the specification states the formula outright; the suites failed to compile against absent symbols, a genuine red |
| Safety theorems (6.1 – 6.5) | poor | conformance tests over already-shipped code, so red was never available; all twelve passed first run, and one did not test its own proposition |
| Adequacy (Prop 3.1, Prop 8.1) | good | "at a gap prior, normalize Replacement(ε, g) to Open(g)" is directly testable; the test went red and found a real conformance gap |

So the intake question is not "is this item statable" but **"which part of this item is statable."**
Intake is a decomposition step, not a scoring step. The operator splits the comprehension work out
and keeps it; the chain gets the remainder.

### 3.4 What the record says when the standard is applied backwards

Across the ClaimOS build, where the notable defects were actually caught. The slice-6 rows are
**VERIFIED** here; the earlier rows are as recorded in the lab's own history.

| Defect | Caught by |
|---|---|
| `Bytes` reference equality | inspection |
| The neutrality gate's own `grep -c` fail-open | inspection |
| ν̂ homomorphism untested | a compiling mutant surviving |
| Bilattice De Morgan and four-closure untested | an operator's question |
| N5 pentagon control invalid | a validity test written first |
| Per-candidate granularity in Thm 6.3 | a surviving mutant |
| Prop 8.1's gap-prior arm | red-first, from the specification text |
| A vacuous check on a struck member's `support` | the test failing, then reading why |

One of eight came from the ordinary red-first beat the chain automates. **The chain automates the
beat that caught the fewest defects in this build.** It would still have done substantial work — the
tests, the registry upkeep, a 73-file mechanical reorganization — but the value concentrated where it
does not reach, and a design that does not say so is selling something.

### 3.5 Three kinds of drift, and the chain covers one

**Structural drift — caught, and more reliably than by a person.** A promised symbol unshipped fails
the ship list. A row unmapped in a shipped slice fails the conformance map under `--strict`. A row
naming a test that no longer exists fails the test-existence arm. The chain runs these every phase
and never skips one because it is late.

**Semantic drift — not caught, with a worked example.** The conformance map verifies that a mapped row
names a test that *exists*. It cannot verify the test still tests the row's proposition. Row
`RESULT/C6.3` states "no pro evidence atom appears that no admitted event supplied **for that
candidate**," was mapped to a test that existed and passed, and that test compared a *global* token
set. Green registry, green suite, green row, and the test did not test its own statement — written by
the same author in the same sitting. **VERIFIED.** Only a mutant found it.

**Source drift — nothing catches it at all.** No script reads `claim-algebra.html` or
`claim-calculus.html`; the sole mention in `build.sbt` is inside a comment. Meanwhile the sources
carry **35** distinct `§` citations as scaladoc prose, checked by nobody (**VERIFIED**, both counts).
This has already happened once: v0.4.7 shifted §1.4→§1.5, Def 3.1→Def 3.2 and others, twelve stale
citations were corrected by hand, and the slice that corrected them introduced three more. If the
document moves again every test still passes and the map stays green.

### 3.6 What would catch semantic drift

**Do not write the law.** Where a proposition is a standard law, `checkAll` against a stock bundle
enforces it by construction — you cannot write a weaker version because you did not write a version.
This is the strongest mechanism available and it is underused; every row that could be a `discipline`
RuleSet and is not carries avoidable risk.

**Mutation, for vacuity and for weakness.** The only mechanism in the whole surveyed surface that asks
whether a test discriminates. Its limit is the mutant set: standard syntactic operators would likely
not have produced the mutation that caught the Thm 6.3 error, which was semantically motivated.

**Blind re-derivation, which is the chain's real structural edge.** The reason the author missed it is
that the author wrote the test and could no longer read it as anything but what was meant. A fresh
agent has no such problem. Give a reviewer the row's proposition, withhold the test, have it state
what a correct test must assert, and diff. **PROPOSED.** Two limits, both stated rather than hidden:
the seats are correlated, being the same model family with the same blind spots, and the output is
testimony — a disagreement flags a human, it does not decide.

### 3.7 What would catch a misread of the specification

The residue §3.6 leaves is a row whose own statement misreads the source. Every mechanism above then
agrees with it. This cannot be eliminated — the lab's own law-audit checklist, whose entire job was
preventing misreads, itself said supersession was `refute` when it is `strike`, and a second reading
caught it rather than the checklist. So the goal is detection and a bounded blast radius.

**Quote, do not paraphrase, and check the quote.** Require each row's statement to carry a verbatim
run from its cited section; the documents extract cleanly to text, so a substring check is mechanical.
**PROPOSED.** Honest limit: the Thm 6.3 test *did* quote §6.3 verbatim in its comment and was written
wrong anyway. Quoting did not prevent the error, but it made the diagnosis immediate once the mutant
fired.

**Read the document twice, not the registry twice.** This is a level correction to §3.6's reviewer,
which inherits the row statement and is therefore blind to exactly this failure. Hand a reader the
cited section cold, ask what obligations it imposes, and diff that list against the rows citing it.
Missing obligations surface as absent rows; misconstrued ones as a disagreement. **PROPOSED.**

**Mine the document's negative space.** The entire calculus contains **14** sentences carrying an
explicit qualifier — "not automatically", "does not", "outside this theorem", "only if", "unless"
(**VERIFIED**, counted). That is a tractable checklist, and those sentences are where misreads live
because they are what a fast reader drops. §6.5's "a mixed tree may lawfully recover and is outside
this theorem" is one, and its control exists only because the document said so. The §6 law table's
Status column is the same idea: the source naming which laws are false.

**An independent finite model, for the rows that matter.** How v0.4.7 was established in the first
place, applied one level down to our construal of it. Expensive per row, decisive where used.

**And one policy rather than a check: under ambiguity, implement the stronger reading.** Global versus
per-candidate was not a coin flip — per-candidate is strictly stronger and cannot be wrong in the
fail-open direction. This is the fail-closed default applied to construal, and it would have got §6.3
right by disposition rather than by insight.

**The triage that follows.** A row's risk is a function of whether its proposition has an external
anchor. A row discharged by a stock law bundle cannot drift. A row with a finite-model control is
checked against something outside the author's reading. A row that is a bespoke hand-written assertion
in the author's own prose has no anchor at all — which is exactly what `RESULT/C6.3` was. Count the
unanchored rows and spend the second reader on those; that set is identifiable mechanically, and it is
where every misread in this build has lived.

---

### 3.8 The three readers, and what belongs in each prompt

§§3.6 and 3.7 name what would catch semantic drift and a misread. This section is the operational
answer: which reader catches which class, and what each prompt has to contain to work rather than to
produce confident noise. Everything below is drawn from a single day's build in
`claim-algebra-lab`, where a green suite, a fully mapped registry and passing strict mode concealed
a blocking conformance hole.

**The three readers are complementary because they read DIFFERENT ARTIFACTS.**

| Reader | Reads | Catches |
|---|---|---|
| Planner | the specification | obligations nobody answered |
| Reviewer | the specification **against** the code | drift between them |
| Mutation | the code **against** the tests | tests that do not discriminate |

None of them reads what the others read. That is the whole argument for having all three, and it is
why a fourth reviewer lens adds less than the first mutation harness — a point that survives the
observation that reviewers are cheap and mutation harnesses are not.

Measured on nine real defects from that build: the planner class accounts for roughly four, the
reviewer class for three, and mutation for two that neither reading caught.

> **The chain installs two of these three.** Mutation is not a phase — operator decision, recorded
> with its reasoning in §4.9. The measurement above is left exactly as taken, because it is what
> makes the cost of that decision legible: the two defects in the mutation column are the ones the
> shipped chain no longer catches, and rounding them away would be the kind of comfortable
> bookkeeping this section exists to argue against. The reading survives as a worker habit
> (`craft-tdd.md` beat 3), which is testimony where a phase would have been re-derived.

#### What the planner prompt must contain

Each requirement traces to a specific defect, not to good practice in general.

- **Emit counts, always.** "Def 2.1 — four conjuncts." "The update table — nine rows." A count is
  checkable and a prose summary is not. Three of Def 2.1's four conjuncts and three of the table's
  nine rows shipped unimplemented under a green build.
- **Read the SECTION, never an existing statement.** A registry row that already carries a statement
  is a starting point for reading, never a substitute. One row said "evidence inclusion and common
  evidence are defined"; §6.1.2's very next clause says "this order is a distributive lattice", and
  the lattice laws went untested because the plan trusted the statement and never opened the
  section. **"Already stated" is not "stated completely."**
- **Enumerate the negative space.** The whole calculus contains **14** sentences carrying an explicit
  qualifier — "not automatically", "does not", "outside this theorem", "only if", "unless". That is
  small enough to require exhaustively, and it is where side conditions, deliberate non-theorems and
  non-implications live.
- **Split every conjunction into separate records**, one per independently fixable thing. A single
  failure name covering three binding clauses had to be split after the fact; so did a registry row
  whose id joined two obligations with "-and-".
- **State each obligation's QUANTIFIER explicitly.** This is the highest-value line in the prompt,
  because it is the only planner instruction that reaches the granularity class. A record reading
  "PER CANDIDATE: no pro atom appears that no admitted event supplied for THAT candidate" makes a
  test comparing a global set visibly answer a different question. The planner cannot write the
  test; it can pin the quantifier the test must carry.
- **Ask of every proposition: is this a standard algebraic law?** If yes, name the bundle. That one
  question would have caught two rows that were discharged by hand when a stock law suite was
  available — including one whose own suite already existed, unmapped.
- **Quote verbatim, cite the section, and flag math-bearing quotations**, so the citation check can
  read the output.
- **Output rows, not prose.** The planner's records must land in the conformance registry where the
  existing checks can fail on them — collective-family, compound-id, duplicate-needle,
  test-existence, strict mode. A planner producing a handsome markdown document produces prose that
  drifts.

#### Test kind is part of the plan, and it is mechanically checkable

A test kind is derivable from the proposition's shape: a named algebraic structure takes a law
bundle; a row the specification marks FALSE takes a witness that it fails; a side condition takes a
fails-when-violated test; a conjunction of N conjuncts takes N refusals and a control.

Stating the rule is not enough — the lab's build plan already stated exactly this rule in its
definition of done, and a row shipped hand-rolled anyway. So the kind goes in the registry as a
column, and two cheap checks fall out:

- `bundle` → the resolved test id must be a `checkAll(` call.
- `witness` → the resolved test must **not** be a `checkAll`, because a bundle proves a law holds
  and these rows exist because it does not. This is what stops a deliberate non-theorem being
  quietly "fixed" into a law.

The first check alone would have caught both hand-rolled rows. **This is the cheapest item in this
entire document and it needs no prompting at all.**

#### What the reviewer prompt must contain

The lab's audit found two blocking defects, so a well-prompted reviewer demonstrably works. Five
things made it work, and a prompt missing any of them produces noise instead:

1. **A paid-for checklist.** Every check was a defect that build had actually shipped and later
   found. A generic checklist reports generic findings.
2. **Six of ten checks required reading the specification**, not only the code.
3. **Adversarial verification of every finding.** Two of ten were refuted; without that pass they
   would have been reported as real.
4. **"Default to NOT reporting."** A finding that cannot be demonstrated costs more than it saves.
5. **Evidence rules**: cite `file:line`, quote the specification text, and state a concrete wrong
   outcome rather than a category.

**Two reviewer passes, with different reference points, and they are different prompts.**

| Pass | Reference | Blind to |
|---|---|---|
| plan vs specification | the section | nothing about the implementation |
| code vs plan | the plan | anything the plan itself missed |
| code vs specification | the section | whether the plan was honest |

Checking that the plan was FOLLOWED catches deviation — a planned obligation with no row, a wrong
test kind, a moved count, scope nobody planned. It does **not** catch incompleteness: asked whether
the plan was followed for the distributive-lattice row, a reviewer answers yes, because the plan
said "already stated" and the code matched the statement. The defect was upstream of the plan. This
is the same level error as a reviewer given a row statement and asked to derive its test: it
inherits the statement and is blind to the statement being wrong.

#### Reviewing is not transcribing

The audit reported that the fold implemented "6 of 9 update-table rows". A fourth row was also
wrong, and the audit did not name it — it was found by transcribing the table arm by arm, where
every row had to be handled or the compiler objected.

**Comparison is lossy; transcription is not.** Where the specification supplies a table, an
enumerated definition, or a fixed-priority list, converting it row-for-row into match arms beats
scrutinising it afterwards. That is a planner instruction — "emit this table as N records" — rather
than a reviewer one.

#### The pattern underneath all of it

The mechanisms that worked that day made omission **structurally impossible** rather than carefully
checked:

- `-Werror` on an unused parameter refused to compile when a gate conjunct was dropped, so the
  conjunct cannot be removed without a visible API change.
- Nine match arms over `(Belief, Event)` forced every update-table row to be handled.
- A stock law bundle supplied nineteen laws including the absorption law that hand-written
  assertions had missed.

None of those is a review. Prefer a construction that cannot omit over a check that looks for
omissions, and spend the readers on what no construction reaches.

### 3.9 The worker audits itself before handing off, and the audit is queries not judgment

The three readers in §3.8 are all downstream of the worker. That leaves a gap the operator found
empirically: across one build, **every single time the operator asked "is there anything we need to
fix before going on", there was something.** Four rounds, four hits, on work that was already
`sbt check` green with a fully mapped registry and passing strict mode.

That is not a reviewer problem. It means the worker was handing off incomplete work as finished, and
the plan's own requirements were the things going unmet.

**The obvious fix is the one that will not work.** "Have the worker check its work before handing
off" is already what the rules say. The repo carries `craft-measurement.md` on instruments that
cannot fail, `craft-tdd.md` on proving a test can fail, and a conformance rule on saying so at the
seam — and every defect below was found *after* those rules were in front of the author while the
work was written. An exhortation to be careful is discharged by feeling careful. The worker will
report that it audited, because it will believe it did.

**So the audit is a fixed list of QUERIES, each returning evidence, and none requiring the worker to
judge its own work.** That distinction is what makes self-audit viable at all: a worker asked "did I
cover everything?" consults the same understanding that produced the gap, and gets the same answer.
A worker asked "which symbols in this diff appear in no test file?" runs a grep and gets a list it
did not author. The first is introspection and inherits the blind spot; the second is measurement
and does not.

#### The queries, each traced to a defect it would have caught

Every row is a real finding from the build, in the round where the operator's question surfaced it.

| Query | The defect it catches |
|---|---|
| Which symbols does this diff add that no test file names? | Two of five shipped symbols in one slice had zero test references. A ship-list check counted them **present**, which is a different question from **read**. |
| For each record added or changed, which fields does no assertion mention? | Three of six fields of a new record were stored and asserted nowhere, so a constructor populating one from the wrong source would have shipped silently. |
| Does the specification's version of each structure have the same shape as mine — same field count, same nesting? | A record carried seven positions where the document writes six, having flattened a sub-record and dropped two of its fields. Nothing downstream needed them, which is why it survived. |
| Does every negative control have a positive half? | A control asserting an expression must not compile passed immediately, and was failing for an unrelated reason. The positive half went red and exposed it. |
| Did each mutation I ran actually COMPILE? | A mutation reported as "no test objected" had not compiled — `-Werror` rejected it. A build failure was read as a test result. Four times in one session. |
| Can each fixture vary each field independently? | One fixture drove two payload fields from a single argument, so neither could be varied alone and a dropped field survived. Another baked a value in as a constant, so no test could vary it. |
| Does any test name a family and enumerate fewer? | "Changing ANY of the six payload fields" listed five. "The four definition digests" built three. |
| Is any asserted count read from a constant rather than from the structure? | `fieldCount` was a value a human typed, compared against a literal a human typed. Deleting a real field left both untouched. |
| For each predicate, is there a case where it must be FALSE? | A predicate's suite was entirely positive. Weakening it to over-fire survived the module, because a predicate that fires too often is only caught by a case it should refuse. |
| Does every claim in a comment survive being tested? | A comment said a substitution "would break this pairing rather than pass silently." It would not. Another claimed a case "each conjunct alone would admit" — measured, and false. |

Ten queries. Eight are greps or one-line scripts; two need the mutation harness the slice should be
running anyway.

#### Three properties that make this a phase and not a habit

**It runs before handoff, and its output is an artifact.** The worker emits the query results, not a
statement that it audited. A reviewer then reads work that has already had its mechanical residue
removed, so what the reviewer finds is genuinely the part that needed a second reader — which makes
the reviewer's signal more informative, not less. A reviewer whose findings are dominated by
unasserted fields is a reviewer being spent on grep work.

**A query that returns nothing must say what it looked at.** "No unexercised symbols" and "the query
found no symbols to check" are the same output and different facts, and the second is the common one
when a pattern is wrong. Print the denominator.

**It does not replace the reviewer or the mutation pass, and the split is by artifact, not by
thoroughness.** These queries read the diff against itself. Only the reviewer reads the
specification against the code, and only mutation reads the code against the tests. A worker that
audits well still cannot catch a faithful implementation of a misread requirement, because nothing
in the diff disagrees with anything else in it.

#### The driver re-runs the mechanical half, because a self-report is a claim by the party judged

§4.2(a) says no agent computes whether the chain advances, and §4.4 shows the harness's own success
fields clearing a phase that could not act at all. An audit the worker merely *reports* having done
inherits that defect exactly: it is the same claim shape the dev-ledger was retired for.

So the queries split by whether a driver can re-derive them — and the split was **measured against a
real module rather than assumed**, because this design's own rule is to run a new check over the
existing corpus and count the false positives before wiring it in.

**Driver-enforced: one query, and it earned the place.**

- *`typeChecks` negative controls with no positive counterpart in the same file.* Measured over 46
  suites: two files use a negative compile-time control, one was correctly paired and one was not.
  Zero false positives, and the unpaired one was a real defect — a control asserting a constructor
  is closed, whose snippet named its fixtures unqualified, so it would have failed to compile for a
  resolution error and passed for the wrong reason. It was found by a query written for a *different*
  control in the same file, four tests away, committed twenty minutes earlier.

**Demoted to worker-judgment after measurement.**

- *Symbols the diff adds that appear in no test file.* This found two real gaps when run by hand over
  a slice-sized diff. Run as a gate over the whole module it flagged **25 of 291 symbols, of which
  roughly four were real** — the rest transitively exercised through a tested caller. Tightening it
  to "and called from no other file" still left nine, most of them used inside their own file. An
  85% false-positive rate is the shape that gets a check edited until it is quiet. It stays in the
  audit as a query the worker runs and *classifies*, over a diff-sized denominator, which is where
  it works.
- Whether a family's enumeration is complete, whether a fixture can vary each field independently,
  whether a comment's claim survives being tested, whether a structure's shape matches the
  document's. These need reading and cannot be a gate.

The one-to-nine ratio is the honest yield, and it is worth stating plainly so nobody budgets for
more. What can be re-derived is re-derived; what cannot is disclosed and left to a reader of a
different artifact. The enforced query is not the important half — it is the half a tired worker
skips, and it costs one grep.

#### What this does not fix

Four rounds is four data points, all from one build, one worker and one operator. The queries are
the recurring shapes *observed*, and a defect class that never happened to appear is not on the list
and would not be caught by it. Expect the table to grow, and treat a defect that reaches the
reviewer as a candidate row rather than as a reviewer success.

---

### 3.10 The story graph: ADRs, dependencies, and what "ready" means

§3.3 says intake is decomposition and stops there. This is the structure that carries it, restoring a capability the prior Gas City system had — an ADR maps to one or more stories, stories form a dependency graph, and the operator and the agent agree a *set* whose working order is then derived rather than negotiated. The machinery is files and git; there is no daemon, no database, and no bead.

**The lineage is three documents deep: a general design doc, the ADRs that decide how to realize it, and the stories that discharge each decision.**

```
docs/design/<subject>.md      what the system is to do
        ↓   decided by
docs/adr/ADR-NNNN-*.md        numbered Decisions D1, D2, …
        ↓   discharged by
stories/STORY-NNNN-*.md       adr: + decisions: + deps:
```

Each arrow points *down* in authorship order and each reference points *up*. A story names the ADR it was built from; an ADR names the design it realizes. Nothing points down, and that is the whole structural decision: ids upstream are stable and their documents are append-mostly, so a document that listed its consumers would be edited every time work was added, split, or re-pointed — turning the most stable artifact into the most churned one. It would also hand a worker its own supervision, since a `Status:` line that gates readiness sits in a file the worker's branch can edit.

**Stories own their edges.** One file per story, the only writer of its own node. Elder validated this in production before we chose it: *"Stories declare their dependencies via frontmatter; the dependency graph is derived, not declared centrally."*

```
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

**The parser enforces the key list** — an unknown key, a duplicate key, or the same `id` in two files is fatal, naming both. The admission rule: *a field may live here only if being wrong about it cannot produce a wrong readiness answer.* A new key is a reviewed diff to the parser. Elder is permissive here instead ("adding unknown fields is fine but won't be carried to bd metadata"); it can afford to be, because an unrecognized field still reaches a runtime substrate that might use it. With no such substrate, an unknown key is a typo that silently does nothing, so it is fatal.

#### What was dropped from Elder's schema, and why

Elder's story frontmatter is `story_id, title, phase, build_item, deps, parent, labels, sensitive_files, status, filed_as_bead`. Four of those do not survive the move, and the reasons differ.

**`build_item` — absorbed.** Elder's spine is `docs/build-plan.md`, a numbered enumeration that stories implement (`build_item: N`) and ADRs amend ("Amends build item #15"). Under the design-doc → ADR → story lineage it has no job left. Lineage runs through `adr:`. Order comes from the `deps:` graph. Coverage comes from two reverse-coverage seams one level apart — *does every design obligation have an ADR or a waiver*, and *does every ADR decision have a story or a waiver* — which compose to answer "is everything being built" without a fourth enumeration to keep in sync. Its amendment role splits cleanly: an ADR that changes *how* supersedes an earlier decision, which per-decision supersession already expresses more precisely than amending a deliverable; an ADR that changes *what* amends the design doc, which is the enumeration.

**`phase` → `milestone`, renamed for what it does.** This is the one job a dep graph genuinely cannot do. A graph gives a partial order; it never says where v1 ends. Release grouping is an operator judgment about shipping, not a fact about building, so it is carried as a label and is never an ordering input.

**`status` — replaced by derivation, and Elder's own repo is the argument.** The pack rule states the boundary plainly: *"Stories are the design-time artifact. bd is the runtime substrate… after filing, bd owns runtime state. Don't round-trip."* The story's `status` is therefore a *projection* of state living somewhere else, kept current by hand — and the cost is visible in Elder: a standing manual reconciliation rule in `CLAUDE.md` naming an "F1/F2/F3 zombie surface", a sweeper (`scripts/audit_zombie_specs.py`) for stale `status: filed` specs, a backfill story for a frontmatter-status sweep, and a projector daemon queued to fix it properly. **None of that is a defect in Elder's design; it is the price of having two substrates.** Here there is only one — git — so state is derived rather than projected and there is nothing to reconcile.

**`filed_as_bead` and `parent` — no substrate, no epics.** Both name Gas City machinery. `sensitive_files` is dropped by operator decision (§4.9).

**Retained from Elder unchanged:** stable never-reused ids, `deps:` as the derived graph, cycle detection in validation on the commit path, and the body sections — Outcome, Acceptance criteria as a checkbox list, Scope In/Out, Notes.

**`cites:` is the same field §4.11's completeness mode is derived from**, so a story's citations already decide the strength of its own planner check, and the count of `prose`-mode stories is printed on every run.

**The graph is read from `origin/main`, never from the worktree or the index.** A story edited on a branch does not change the graph until a human merges it — the same signature that governs everything else here.

**`.chain/set` is the agreement, and the commit is the agreement record.** One line per ADR id (meaning every story of that ADR) or per story id. It has an author, a timestamp, a diff, and it reverts. Parking a story is deleting its line and committing — a scope decision recorded like every other scope decision, not a ref and not a field. `agree` refuses a set whose ADR has a decision with no story, until a story exists or the decision carries `Covered-by: none — <reason>` under its heading.

**Order is Kahn over the agreed subgraph, critical path first** — keyed by `(-height, group, set-line-index, id)`, where height is the longest path to a sink. Depth costs human merge cycles and breadth does not, so the serial part is scheduled as early as possible. `tsort` runs on the same edges as a second opinion **read only for its exit status**, since it prints an ordering even for cyclic input.

#### What "satisfied" means, decided

**`origin/main` contains a merge commit carrying the trailer `Merged-Story: <ID>` whose second parent is the story branch's tip.** Not a phase ref, not a branch existing, not a file the finalizer wrote. Two questions decide it: *can it go true by accident?* — a finalizer-written record can, since an ordinary `--ours` conflict resolution merges the record while dropping the code. *Can it go false by routine maintenance?* — a content or path predicate can, since a `git mv` would un-land a merged story.

The witnesses are **not or-ed**; the strict one decides and a loose scan exists only to catch it reading false: strict and loose both true is `SATISFIED`, both false is `BLOCKED`, loose-true-strict-false is `SQUASHED` and exits loud, and a tip that is an ancestor with no merge record is `MERGED-UNRECORDED`. Chain merges are `--no-ff` by policy; a forgotten flag stalls loudly rather than releasing silently.

**Group B needs no second mechanism.** Its gate — "the predecessor feature has merged" — *is* an ordinary `deps:` edge under merge-satisfaction. The A/B distinction survives only as a scheduling tie-break.

#### Two practices taken from Elder wholesale

**Depth tiers.** Specs are written to three depths by proximity: full for imminent work, medium for the next milestone, and light stubs — dep edges and a rough scope, nothing more — for anything months out. Elder's reasoning is the part worth keeping: *"detailed acceptance criteria for stories we won't touch for months would speculate against constraints we don't yet have. The dep edges and rough scope are enough to keep the graph intact."* **The graph must be complete; the specs need not be.** This matters more here than it did there, because §4.11 derives a story's completeness mode from its `cites:` — so a thin future story is honestly `prose`-mode and is counted as such, rather than being dressed up with citations nobody checked.

**A closing record in `stories/_archive/`.** A merged story moves there with `merged_pr`, `merged_sha`, `deviations`, and `lessons` appended, so that — in Elder's words — *"`git log -- stories/_archive/` becomes the searchable record of how the system was built."* This is the write-forward record §4.9 found missing: the chain is otherwise amnesic across runs, and `deviations` in particular is the only place a story's acceptance criteria and what actually shipped are reconciled in writing. The move is an operator action after the merge, which is the same seam the merge witness already sits on.

**The throughput consequence, paid in the open.** Nothing is satisfied until a human merges, so a set worked in one session goes as *wide* as it allows and exactly *one deep*. A four-deep set takes four merge cycles. `propose` prints the depth before the operator agrees, and the finalizer ends each story by printing the exact merge command. What is explicitly rejected is a session-local mode where a terminal phase ref counts as satisfied for dependents: that puts a dependent's work on top of unreviewed code, and a bounce in the predecessor would cascade §4.10's re-walk rule across a story boundary, which nothing here defines.

#### The integrity checks

Twelve, each printing its denominator on success so that finding nothing is distinguishable from looking at nothing. Six read only trunk blobs and sit on the commit path — scoped to **every** story and ADR, not to the agreed set, because a cycle inside an unagreed ADR is still a cycle. Six need git state and run in `ready`. Parse, dangling ids (**separate exit code from cycles**, since both produce the same Kahn residual and send the operator to different remedies), cycles, unresolvable ADR references, orphan ratio, reverse coverage, set closure, trunk integrity, merge-record reconciliation, witness disagreement, branch hygiene, and the completeness-mode census.

Two rules make them fail closed. **An ADR yielding zero parsed decisions is an error**, because a zero-decision parse is otherwise indistinguishable from full coverage. And the main loop branches on the exit code, never the prose — treating **exit 0 with empty stdout, or a missing terminal OK line, as a broken instrument rather than as "nothing to do"**, since `git for-each-ref` on an empty namespace and `git ls-tree` on a missing path both print nothing and exit 0.

#### What it still cannot do

**A merge that drops the work still reads satisfied.** Parentage proves a human merged the branch; it does not prove the merge carried the diff. Not fixable at this layer — it belongs to re-running the story's named acceptance check against trunk after the merge. **Reverse coverage is one bit per decision**: it sees a decision with no story, never a decision that decomposed into four stories of which two were written; partial decomposition is the planner's source-to-plan seam. **Every check is a drift detector, not a tamper barrier** — the agent has Bash. And **only one working copy knows what is in flight**, deliberately, so a second clone reads an in-flight story as ready.

---

## 4. The runtime: containment, sequencing, and the autonomous loop

### 4.1 The tension, and the position

Containment and headless autonomy pull against each other, and the pull is specific rather than philosophical.

Autonomy requires that a phase not silently no-op. Measured: an unapproved tool call in `-p` exits 0 with `subtype: "success"`. To avoid a night of phases that "succeed" having done nothing, the phase must run with permissions effectively out of the way — `--dangerously-skip-permissions`, or an allow set wide enough to cover everything a build phase does, which for a worker holding Bash is nearly everything.

Containment, in the prior design, was `permissions.deny` rules plus a `tools:` allowlist. Both are weakened or void under that mode.

**The position: containment is hook-based, never `permissions.deny`-based, and the command-string layer is called friction rather than containment.**

Three measurements make this the only coherent choice:

- `--dangerously-skip-permissions` does **not** disable PreToolUse hooks. Control: a project-scope PreToolUse hook on Bash exiting 2 on a pattern, run under that flag — 1 denial recorded, file not created. **VERIFIED**.
- `--bare` disables hook discovery entirely. Identical invocation plus `--bare` — 0 denials, file created. **VERIFIED**. `--safe-mode` is a second one-flag hook bypass (`claude --help`: "Start with all customizations... disabled"), along with `--settings`, `--setting-sources`, `--agents`, and `--disable-slash-commands`. **DOCUMENTED**.
- A hook exiting 2 stops the tool call *before permission rules are evaluated* (permissions.md line 419). **DOCUMENTED**. This is why the hook layer survives a bypass mode and the deny layer does not.

And one measurement makes the "friction" label mandatory rather than modest: five of six deny-rule evasions succeeded, `bash -c` among them. A denylist over shell strings raises the cost of an accident by about one line and the cost of an intent by zero.

So the design says, in the doc and in the agent briefs: **the fence catches drift and accidents. It does not contain a phase agent that means to get out. What reaches main rests on the human merge.**

### 4.2 What is actually containment

Three things, in descending order of how much they carry.

**(a) The driver holds the decision, and re-derives it.** No agent computes whether the chain advances. The bash driver runs the predicate itself, between `claude -p` invocations, from git and the filesystem. This is the chain's central property and it is now structurally true rather than conventionally true. **PROPOSED** (the driver does not exist), but the enabling capability is **DOCUMENTED** and the shape is ordinary shell.

**(b) `isolation: worktree` on the tester and the reviewer.** Real filesystem partition for the two attest-only phases: their edits land in a temporary worktree, the parent checkout is untouched, and the worktree is auto-cleaned if they change nothing. With `worktree.baseRef: "head"` so they grade the worker's actual tree. **DOCUMENTED**. Keep the driver-side `git diff` re-derivation anyway, because it re-derives rather than trusts, and because it is the check that would fail if the isolation quietly stopped working.

**(c) PreToolUse hooks keyed on `agent_type`.** Subagent PreToolUse input carries `agent_id` and `agent_type` — now **VERIFIED**, by dumping the raw payload (§4.8). A single project hook can deny Write/Edit from `chain-tester` and `chain-reviewer`. That closes the instrumented path, which is the path an unmotivated model reaches for first. It does not close `printf > file`. Say so in the hook's own comment.

Three measured details change how that hook must be written. **The parent's payload omits both fields entirely** rather than sending a null or a sentinel, so the parent is identifiable only by their absence — which means the hook must key on the positive (`agent_type == "chain-tester"`) and never on "is this the parent?", because absence-as-signal reads clean the day the field is renamed. **A settings file added mid-session takes effect on the next tool call**, with no restart. And **the matcher's tool coverage must be complete, not representative**: a fence matching only `Bash` was measured letting a `Write` through untouched, after which reading the file back was an unremarkable `cat`. A hook is only as wide as its matcher list.

The fence pattern set, for the record, with the corrections the verification pass forced:

- `--no-verify`, `core.hooksPath`, `HUSKY=0`, `GIT_DIR=` — readable forms, worth denying.
- `claude .*(--bare|--safe-mode|--settings|--setting-sources|--dangerously-skip-permissions|--disable-slash-commands)` — the customization-bypass family. Note this is a denylist over another program's flag surface across releases, which is a moving target.
- Drop the bare `-n` alternative. It fires on `grep -n`, `sort -n`, `head -n 20`. Shipped as written it halts ordinary phase work constantly, and the predictable response is that someone widens or removes the hook. Anchor it to `git commit` or leave it out; `--no-verify` covers the readable form.
- `permissions.deny` as a secondary layer only, and spelled `Bash(* --no-verify *)` with a leading wildcard, because `Bash(git commit --no-verify *)` is prefix-anchored and misses `git commit -m x --no-verify`. **DOCUMENTED** (permissions.md: `Bash(* install)` matches any command ending in ` install`).
- Every fence hook bounds its own subprocess with `timeout` and exits 2 on expiry. Timeout polarity for a PreToolUse *command* hook is **undocumented** — HTTP hooks and UserPromptSubmit command hooks fail open, an Agent-SDK callback on PreToolUse fails closed and the docs say explicitly that it does so "because a callback there can be acting as a policy gate that must not fail open." You cannot rely on either. Bounding it yourself makes the polarity irrelevant.

### 4.3 What the machine has to supply, and what the kit cannot

Two hardening steps are real containment and neither is a kit deliverable. The kit ships the payload and an install checklist; the operator (or the machine's admin) applies them.

**Endpoint-managed settings at `/etc/claude-code/managed-settings.json`.** Highest precedence, not overridable by user, project, local, or CLI arguments (**DOCUMENTED**). Unprivileged `mkdir -p /etc/claude-code` from a subagent returned Permission denied (**VERIFIED**), so the earlier INFERRED flag on its write-protection can be discharged for the unprivileged case. But if passwordless non-interactive sudo is available, `sudo -n tee /etc/claude-code/managed-settings.json` is one Bash call away. **Test it on your own machine before relying on this tier:** `sudo -n true`; a zero exit means the tier is not a trust root for you. **The managed tier is a trust root only if passwordless sudo is removed first.** That is the precondition, it is stated in the install checklist, and without it this closes nothing.

Two corrections to what goes in the payload: `disableBypassPermissionsMode` is **not** managed-only — permissions.md line 510 says it "works from any scope" — and its value is the string `"disable"`, not a boolean. A design that writes `true` silently does not take. Pair it with `allowManagedPermissionRulesOnly`. Both are required, not optional: without them the fence is a setting the fenced agent owns, and a permissive `defaultMode` in an agent-writable settings file leaves the fence owned by the fenced agent. Check what your own default mode is before assuming otherwise.

Predicate scripts and the trusted-base list live at absolute paths outside any working tree, root-owned `0755`, with an absolute root-owned interpreter in the shebang. The archived `trusted-base-touched.sh` already names this in its provenance header; it was never done.

**The bubblewrap sandbox.** This is the only mechanism in the entire surveyed surface that reaches inside `python -c` and `bash -c`, because it is a kernel-enforced mount namespace and not a string match. permissions.md points at it ("For OS-level enforcement that blocks all processes from accessing a path, enable the sandbox") and the earlier analysis stopped at the pointer while declaring the residual irreducible. Strings from the running 2.1.220 binary show a `{allowWrite, denyWrite, denyRead}` filesystem policy, settings keys `sandboxDenyPaths` / `sandboxEnabled` / `sandbox.bwrapPath`, and a managed-policy key `areUnsandboxedCommandsForbiddenByPolicy`.

Marked **PROPOSED**, not DOCUMENTED, for two reasons. The capability was read out of binary strings rather than out of docs. And it does not currently work here: on the Linux host measured, bwrap failed with `setting up uid map: Permission denied` under the Ubuntu 24.04+ default `kernel.apparmor_restrict_unprivileged_userns=1` with no bwrap AppArmor profile installed, and a subagent could not relax the sysctl. Root-level enablement, same bar as managed settings, and it belongs in the same change.

If both land, the residual that W1/W3/W5/W9 share stops being irreducible. Until then it is irreducible in practice and the design says so.

### 4.4 The driver and the phase contract

One bash script. Per story, per phase:

```
claude -p "<phase prompt>" \
  --agents <chain agents json> \
  --output-format stream-json --verbose \
  --permission-mode manual|dontAsk \
  [--dangerously-skip-permissions for build phases] \
  --resume <session_id if resuming> \
  >> runs/<story>/<phase>.jsonl
```

Notes on the invocation, each marked:

- `--permission-mode default` **does not exist at the CLI**. `claude --help` on 2.1.220 lists exactly `acceptEdits, auto, bypassPermissions, manual, dontAsk, plan`. Frontmatter accepts `default` as an alias for `manual`; the CLI rejects it before the session starts. Use `manual`, or `dontAsk` for locked-down phases. **VERIFIED** against the installed help text.
- `stream-json` is appended incrementally, so a killed phase leaves a start-shaped file with no `result` line. **VERIFIED**.

**The phase verdict is a postcondition re-derived from git, not a reading of the harness's own
report.** This corrects the first draft of this design, which proposed a conjunction over stream
fields. That conjunction was measured and it does not discriminate.

The measurement, run against Claude Code 2.1.220 on 2026-08-01:

```
claude -p 'Create a file named denial-probe.txt ... You must use a tool to do it.' \
  --disallowedTools 'Bash' 'Write' 'Edit' 'NotebookEdit' --output-format json

EXIT=0                     file: NOT created  (the phase did nothing)
is_error: False            subtype: "success"        stop_reason: "end_turn"
permission_denials: 0      (empty)
```

Every field the harness exposes says success, and the phase could not act at all. The proposed
conjunction — result present, `is_error` false, `subtype` success, `permission_denials` empty —
returns PASS on that run. **VERIFIED.**

`permission_denials` covers the permission-*prompt* path: a tool call made and refused. It does not
cover a tool that is disabled, because the model then receives an ordinary tool error, handles it,
and explains itself in prose — which is exactly what a driver must not parse. There are at least two
"the phase could not act" paths and the field covers one of them. Assume there are more.

An earlier probe of the same question was itself a bad instrument and is recorded because the shape
recurs: denying only `Bash` did not reproduce the defect, because the model routed around the denial
and used `Write` instead. The task completed, the fields were honest, and a careless reading would
have cleared the mechanism. Deny every write path, or you are measuring the model's resourcefulness
rather than the harness's reporting.

So the driver decides advancement the way §4.2(a) already says it must:

```
phase_ok(story, n) :=
      git rev-parse --verify chain/<story>/phase-<n>     # the ref the phase had to create
  AND <the phase's own postcondition, run by the driver> # e.g. tester-clean, red-proof, the gate
```

Stream fields are corroboration and diagnosis, never the verdict. `permission_denials`, `is_error`
and `subtype` still get logged, because when a postcondition fails they are how you find out why —
and a non-empty `permission_denials` is a fast, specific explanation. But no phase advances on them.

This is the design's central property applied to the design itself. The first draft asserted that
the sequencer holds no judgment and re-derives from durable state, then had it read the harness's
self-report. The self-report is a claim by the party being judged, which is the same defect that
retired the dev-ledger.

Grounded exit-code map, since the docs call it undocumented: **0** = harness completed, including a denied no-op; **1** = harness error (`subtype: error_max_turns` measured, invalid model measured); **137** = SIGKILL; **143** = SIGTERM. **VERIFIED** for all four. The exit code separates harness failure from task failure and nothing else — it is never the phase verdict.

### 4.5 Durable state: git is the state machine, the log is an audit trail

The prior design's park rule (an unpaired start record means the phase died) is necessary and insufficient. It detects death *inside* a phase. It cannot detect death *between* phases: phase N's end record lands, the driver dies before phase N+1's start record, and the store reads as clean and complete. A resumed driver re-runs N+1 from scratch and duplicates any non-idempotent side effect. That state is also indistinguishable from "the run finished normally at N."

**So phase position is re-derived from git, every resume, always.** A phase completes by creating a ref — `refs/chain/<story-id>/attempt-<a>/phase-<n>` — or by a phase-tagged commit trailer. The resume path asks git "what is the highest completed phase for this story?" and never asks the log, and never asks a story spec's `status:` frontmatter. This generalizes W9's conclusion: **status fields are advisory, git is authority.**

> **Corrected: the phase ref lives in its own `refs/chain/` namespace, not under `refs/heads/`.** This section first wrote `chain/<story-id>/phase-<n>`, which is *impossible* alongside the story branch §4.7 creates at `git branch chain/<story-id>`. **VERIFIED**: with `refs/heads/chain/STORY-0041` present, `git update-ref refs/heads/chain/STORY-0041/phase-1` fails with `cannot lock ref … 'refs/heads/chain/STORY-0041' exists; cannot create`. A ref and a ref-directory cannot share a path. In a separate namespace the two coexist, which is also correct on the merits: phase refs are per-instance run state, never shared truth, so they are never pushed and a fresh clone reporting none is telling the truth. The `attempt-<a>` level exists for §4.10's re-walk rule — a return to phase N deletes `phase-{N..end}` of the current attempt in one `git update-ref --stdin` batch, so the git-derived resume answer cannot disagree with the rule that a bounce invalidates everything downstream.
>
> **And never configure a fetch refspec for that namespace.** `+refs/chain/*:refs/chain/*` with `--prune` deletes every local phase and park ref on the normal path, because nothing pushes them — which silently restarts in-flight stories from phase one and resurrects parked ones. Fetch only the trunk.

The unpaired-start rule stays as a secondary in-phase liveness alarm, and it now has a positive form: a `.jsonl` with events and no `result` line is in-phase death, detected rather than inferred.

**The event log** is driver-written, append-only, one record per phase transition, at an absolute path outside the repo working tree. Fields carry the ledger's obligation edges without its apparatus:

```
{ ts, story, phase, event, sha, session_id, wall_ms, total_cost_usd,
  retry_count, about, supersedes, discharged_by, predicate, verdict }
```

`about` names what the record concerns (a story, a phase, a predicate). `supersedes` points at a record this one replaces. `discharged_by` names the check that settled an obligation. No claims, no hashes, no signing. Agents never write it — the driver does, between invocations. Backstop with a PreToolUse hook denying any tool input naming the store path, and understand that the backstop is friction (§4.1).

Two cost facts, both **VERIFIED**, one of them a trap: `total_cost_usd` **does** aggregate nested subagent spend, while the `usage` token counts do **not**. A phase that spawned an Explore subagent reported $0.0340 against a `usage` block pricing to about $0.0050 — roughly one seventh. A driver estimating spend by summing `usage.output_tokens` undercounts fan-out by close to an order of magnitude. `total_cost_usd` is the only correct field, and on a trivial run it matched hand-computed API pricing to within a rounding step, so it is real pricing rather than an estimate. Keep wall time and cost as separate columns; wall time includes retry backoff and a blended number would confound provider capacity with work done.

### 4.6 Liveness, retry, and the SLO

`CLAUDE_CODE_RETRY_WATCHDOG=1` plus `CLAUDE_CODE_MAX_RETRIES` in the driver environment (**DOCUMENTED**). The watchdog covers capacity errors only; auth failures and non-retryable 4xx still end the run and need their own branch.

The retry watchdog and the stall SLO are in direct tension and the resolution has to be explicit: **the SLO bounds total phase wall-clock, not silence.** A run stuck retrying forever emits `system/api_retry` events, looks alive, and makes no progress — which is precisely the green that means nobody is looking. The supervisor kills a phase at N minutes regardless of activity, and separately counts `api_retry` events so the overrun can be attributed to provider capacity rather than to work.

A `SessionEnd` hook can write a death marker and does run on the SIGTERM path (**DOCUMENTED**: SIGTERM "aborts the in-progress turn, terminates the process tree of any running Bash command, runs SessionEnd hooks, and exits with code 143"). Set an explicit per-hook `timeout` on it — the default SessionEnd budget is 1.5 seconds and a disk write under contention can be cancelled inside it, indistinguishably from a clean exit. And never treat marker absence as evidence: SIGKILL runs no hooks at all. **VERIFIED** that SIGKILL gives 137 with a truncated but readable stream, which is the better signal anyway.

Resume uses `--resume <session_id>` from the same cwd, with the session id read off the result event. Background Bash and Monitor tasks are **not** restored on resume (**DOCUMENTED**), so no phase may park work in a background task.

### 4.7 Starting unattended, and not starting twice

**OS cron only.** The prior draft offered Routines as the durable option. Routines were refuted twice in the environment measured: the account's policy limits disallowed them, and routines.md states each run clones a **GitHub** repository, while this lab's only remote is a local bare path and the standing rule is that it never gets a GitHub remote. Not a preference — an account-level block plus a structural impossibility. The `/schedule` skill is not installed. **VERIFIED**.

**Concurrency ships in the same change as the cron start, not after it.** Removing the human turn removes the serialization the attended design got by accident. Mutual exclusion is ordinary OS and git in the driver: `flock` on a per-story lockfile held for the whole run, plus atomic `git branch chain/<story-id>` whose creation fails if the branch exists. The lock is not agent-proof (an agent with Bash deletes lockfiles), which is consistent with §4.1 and needs saying rather than hiding.

**The quota being spent is the metered API tier, not the Max subscription.** `claude -p` authenticates via an API key when one is set in the environment — the harness's own stderr says so ("claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth source is set and takes precedence over your claude.ai login"). **VERIFIED**. An overnight batch bills ITPM/OTPM/RPM. That is a cost decision the operator should make knowingly.

**Wall clock is the binding constraint, not budget.** Extrapolating from the 12-agent, 1.24M-token, 29-minute reference workflow: roughly $1.70–$6.60 per committee-scale fan-out on Opus 5, so an 8-story × 5-phase night lands near $40–$80. Throughput is the limit — about two hours for a five-phase story at that scale means a ten-hour window serializes roughly five stories. Parallelizing to fit more hits the concurrency exposure and the rate limit at the same time; a single workflow sustained about 43K tokens/min, so three concurrent stories needs about 128K TPM. **The tier's actual ITPM must be looked up before choosing a concurrency level.** I do not have it and will not guess it. Design the batch to a measured tokens-per-minute budget, not a story count.

### 4.8 If workflows and subagents replace `claude -p`

Everything above assumes a bash driver invoking `claude -p` between phases. The alternative is to run the chain inside one Claude Code session, with a `Workflow` script as the driver and subagents as the phases. That substrate was measured rather than assumed, because two rounds of documentation research had already returned answers that turned out to be wrong in both directions.

**The finding that decides it: a workflow script cannot re-derive anything.** It runs in a sandbox with no filesystem, no subprocess, and no network. `require` is not defined, `process` is not defined, `fetch` is undefined, and `eval` throws "Code generation from strings disallowed". The globals are exactly `log, phase, console, budget, setTimeout, clearTimeout, Date, agent, parallel, pipeline, workflow, args`. Standard built-ins (Math, JSON, RegExp, Set/Map, Promise) are present. **VERIFIED** by a zero-agent probe workflow that tried each and reported which threw.

`Date.now()`, `new Date()` and `Math.random()` are additionally rejected by a **static pre-run check** — the script is refused at submission with a determinism message, so a `try/catch` around them never executes. Note that `Date` itself is bound at runtime; the ban is on the source text, not the binding.

So §4.2(a) — *the driver holds the decision and re-derives it from git and the filesystem* — **cannot be implemented in a workflow script.** The script can enforce sequence, fan-out, and retry counts, but every fact about the repository reaches it as a string returned by a subagent, and it has no way to check that string. That is not a gap to be patched; it is the shape of the sandbox. A workflow orchestrator is structurally in the position the design spent §4.4 arguing the driver must never be in.

Three consequences, and one replacement:

- **Sequencing is safe to move into a workflow.** Phase order, per-item pipelining, budget-scaled fan-out, and loop-until-dry are pure control flow and need no filesystem.
- **Verdicts are not.** Any phase verdict computed inside the script is testimony from the agent that reported it. Structured output (`agent(..., {schema})`) makes the testimony well-formed; it does not make it true.
- **The re-derivation has to move somewhere that runs in the real filesystem.** On this repo that is already built: `core.hooksPath` → `.githooks/pre-commit`, running `scripts/check.sh` and gitleaks.

**Git hooks are the stronger containment primitive, and the contrast was measured back to back.** A PreToolUse fence matching command text was defeated on first attempt by ordinary shell — variable concatenation and `base64 -d` both passed the token through, and a `Write` deposited it on disk entirely outside a Bash-scoped matcher. That is 1 blocked of 4, and it confirms §4.1's "friction, not containment" rather than softening it. The same session's `pre-commit` hook, fired from inside a subagent's worktree, **blocked a planted secret and no commit landed** — because it inspects the bytes being committed rather than the text of the request. The gap a text fence cannot close is the gap between the string an agent sends and the effect the shell produces; a commit hook sits on the far side of it.

**The worktree handoff is real, and it has one requirement worth stating.** A subagent launched with `isolation: worktree` gets a full checkout at `.claude/worktrees/agent-<agentId>` on branch `worktree-agent-<agentId>`, with its own `--absolute-git-dir` under the parent's `.git/worktrees/`. The path is git-excluded via `.git/info/exclude`, so it never appears in the parent's `git status`. The parent reads the result with ordinary git — `git log worktree-agent-<id>`, `git -C <path> status` — and the completion notification reports `worktreePath` and `worktreeBranch` explicitly. **VERIFIED.** The requirement: **the worker must commit.** An uncommitted worktree is auto-cleaned when it ends unchanged, so a phase that edits without committing hands the next phase nothing. Untracked parent files are not copied into the worktree either, which is worth knowing before a phase depends on one.

Hooks configured in the parent still fire for subagent tool calls even though the worktree checkout does not contain the settings file that defines them — configuration is inherited from the session, not re-read from the agent's cwd. **VERIFIED.**

**The recommended shape, given all of the above: the MAIN LOOP drives.** It spawns phase N's subagent; the subagent returns, so control comes back naturally; the main loop cuts its own scratch worktree from that phase's ref and evaluates the predicate itself; then it spawns phase N+1. Subagents do the work in worktrees and commit. A workflow is admissible only *inside* a phase, for fan-out where the aggregation rule must be fixed before results are seen — and each fanned-out agent commits its own artifact to its own branch, so nothing crosses the workflow boundary as a string. That keeps §4.2(a) intact by relocating it rather than by trusting the orchestrator with it.

Two conditions on every main-loop verdict, both **VERIFIED** in source. **Pin the environment at the point of signing** — `conformance-map.sh:36` and `ship-list.sh:25` read `SHIPPED` from the environment and `.envrc` is gitignored, so the signing surface is weakenable by state no `git diff` can see. And **take the examiner from the base, not the judged branch** — `check.sh:15` is `cd "$(dirname "$0")/.."`, so it runs the *worktree's* copy of itself, letting the judged party supply its own examiner.

### 4.9 What the pack was buying, measured against this design

The `sdlc-discipline-pack` is a seven-agent chain built for Gas City. Its machinery is deliberately gone (§1). The question this section settles is whether its agents' *goals* survive, and it was answered by reading all seven templates rather than by recalling them.

**The honest grade: the forward path is carried and strengthened; the failure paths are not carried at all.** On a green run this design has strictly better epistemics than the pack, whose worker self-reported its own gate and whose auto-merge rubric read `test_status=green` and `review_verdict=pass` — both metadata a prior agent wrote, which the "only a check signs" invariant rejects on principle. What does not survive is everything that appears only when something goes wrong, or goes beyond what was asked.

**Nothing reads the code back against what was declared, and this is the design's structural blind spot.** Five of the seven per-agent reads found it from different angles. The reason none could see alone: every reading step here is defined by an input pair, and all the pairs point the same way — the worker is code against the compiler and the suite, the reviewer is specification against code. Spec-to-code finds *missing* work and structurally cannot find *surplus* work, because unrequested code violates no specification. The pack's `Scope In:/Out:` list ran the other direction, and both the declaration and its enforcing gate are absent here.

**The remedy is a declaration/enforcement PAIR, and half a pair is worse than none.** The planner parks a machine-readable in-scope path list; the finalizer reconciles the cumulative diff against it, because the finalizer is the only step that sees the whole change. Placing only the enforcement half yields a check that reads nothing and reports clean, which is the failure mode this entire document is written against. (The pack also ran a sensitive-files declaration through the same pair. **Dropped by operator decision** — it is not carried here, and this sentence exists so a later reader does not restore it as an oversight.)

**The delivered artifact is gated by nothing.** The terminal step merges sibling branches into a tree that exists nowhere else; the worker's gate ran on the worker's tree and the tester's on the tester's. Hooks cannot cover it: **VERIFIED** that `.githooks/` ships only `pre-commit` and `post-commit`, while git 2.43 documents `pre-merge-commit` as the hook `git merge` invokes. So the one artifact the chain exists to produce is the one tree no check has ever run on — and it is handed to the human whose merge the whole safety argument rests on. **This is the first thing to fix**, because it fails on green runs rather than on bad ones.

**There is no failure edge. VERIFIED** by search: the document has zero occurrences of bounce-back, re-entry, or on-failure handling, and its only retry concept is `CLAUDE_CODE_RETRY_WATCHDOG` for provider capacity. The pack bounces at two points — tester to worker when validation cannot be made green, reviewer to worker with a rejection reason. Detection is fully specified here and disposition is not specified at all. It compounds: a blocked subagent's worktree is auto-cleaned unless it commits, so it destroys its own account of why it stopped.

**"Could not look" reads identically to "found nothing"** — §4.4's measured trap, one level down. That trap is answered at *phase* granularity by re-deriving from git; there is no answer at *check* granularity, so a lens that never ran and a lens that ran clean emit the same absence report. The correct output shape is three-valued: **refute / absence-with-a-coverage-receipt / could-not-inspect**. Only the middle one is clean, and the third is not an approval, so it costs nothing against "the reviewer never approves."

**The differential axis is missing.** "Gate green" is absolute where anti-weakening is a comparison against merge-base. A worker deletes a failing test, the suite goes green, the gate goes green, and no step reports the deletion. `differential-gate.jar` already implements Check B and Check D and no phase names it.

#### Operator decisions on the two agents with no counterpart

**The slop-reviewer stays out, and this is a decision rather than an omission.** It was run and did not pay; the pack's own template says v1 shipped in shadow mode, annotate-only, pending a sample-size validation it never cleared. Recorded here so a later audit reading the pack does not re-propose it as an oversight.

**Mutation is not a chain step either. Operator decision, and it has a stated cost.** §3.8's own measurement over nine real defects splits them planner four, reviewer three, mutation two — and those two were defects *neither other reading caught*, because only mutation reads the code against the tests. Removing the step means the chain no longer catches that class. §7 already says detection power has to be bought separately and mostly is not; with this decision it is not bought at all, by choice rather than by oversight.

What survives is the habit, not the phase. `craft-tdd.md` beat 3 — perturb the *shipped* code and confirm the suite objects — remains a worker practice, and §3.9's self-audit already carries the query that catches its commonest failure (a mutant that did not compile, read as a test result, four times in one session). The difference is grade, and it should be said rather than blurred: a worker's perturbation is self-reported testimony, where a phase would have been re-derived. `phases` in §5 makes the step re-addable per repo if that ever bites.

Two residues now have no owner at all, and both were previously covered by the agents just removed. **Test quality has no reader**: an implementation-mirroring test parrots the production algorithm, and with the slop rubric gone and mutation gone, nothing detects it — the attest-only tester judged on "gate green" has an incentive pointing straight at it. And **no step reads the finished code as code** against the project's own standards; every remaining reading step is defined by a different pairing. Neither needs an agent to fix. Both need someone to decide they are acceptable, which is a different act from not noticing them.

**The documenter stays in, and it keeps its own job while gaining one.** An earlier draft of this paragraph said its value was "PR authorship, not feature documentation." That was wrong on both halves, and reading the pack's own prompt is what showed it: that documenter states plainly *"You do not open the PR or merge the branch… The finalizer handles the PR and the merge gate after you"*, so PR authorship was never its job — and the documentation it writes is the thing this design was missing.

It writes **four** things. The **feature doc**. The **conditional-docs trigger entry** — *"the trigger registry future planners read to know when to load this feature's full doc"* — which is what makes accumulated documentation findable instead of a growing pile nobody opens, and which had no counterpart here at all. The **briefing** that §4.12's veto window is read against, of which a PR body is one rendering; that distinction matters in a repo with no remote, where "PR authorship" has no object but a briefing always does. And it carries the **two-step scope gate**: stage exactly its own outputs, then refuse to commit if `git status --porcelain` shows anything else.

It keeps the **trivial-change short-circuit** too — under a threshold, record that documentation was skipped rather than manufacture prose about a typo fix.

> **One overlap left open deliberately.** There are now two write-forward records: this feature doc plus its trigger entry, and §3.10's `stories/_archive/` closing record with `deviations` and `lessons`. They are not redundant — the archive record is *per story, what happened*; the feature doc is *per feature, what exists* — but nobody has decided to have both, and two documentation systems is how each ends up half-maintained.

> **Superseded in part by §4.12.** This paragraph originally argued that dropping auto-merge was right and that the human merge mattered *more* here than in the pack. That was reasoned under two conditions since removed — a sensitive-file list, and a repository where a bad merge is expensive. Neither holds. The claim that the pack's rubric "reads agent-written metadata" was also too broad: it is true of one conjunct of four, and three are re-derivable. See §4.12.

Keep it a distinct step rather than folding it into the finalizer. The pack separated them and the separation earned its keep: a documenter once shipped a clean feature document and silently deleted eleven unrelated story specs in the same commit, and it reached a PR — which is a direct refutation of "the human merge will catch it," the proposition this design leans on hardest. Whichever step is terminal carries the merged-tree gate above; that is what makes the ordering safe rather than the ordering itself.

**The roster is per-repo.** Which steps are installed is an operator choice expressed in `profile.toml` (§5), not a property of the runtime.

### 4.10 The failure edge

Every step above states a pass condition. This section states what happens when one does not hold, which the design previously left unwritten — detection fully specified, disposition not specified at all.

**A refuted review returns to the worker, and the reviewer's three outputs give the three dispositions directly:**

| Reviewer output | Disposition |
|---|---|
| refute | back to the worker, findings verbatim |
| could-not-inspect | typed park for the operator; the chain stops |
| absence, with a coverage receipt | advance |

That one-to-one mapping is the reason the output shape is three-valued rather than two. A reviewer restricted to refute-or-absence, when blocked, must either fabricate a rejection or emit a clean report — and the clean report is the likelier and the worse. The third state is what makes "back to the worker" mean a real finding rather than a reader who could not look.

The same edge on the other steps. **Tester:** gate red returns to the worker with the failing output. **The merge stage:** a red gate on the merged tree, a failed scope reconciliation, or a source-set integrity failure returns to the worker; a **trusted-base touch parks regardless of green** and a moved head aborts (§4.12); everything else reaches `merge_ok`. **Planner:** not-plannable is a typed park, never a bounce, because there is nothing upstream of it.

**Triage before bouncing, because not every red is the worker's fault.** Three causes must be separated: a *worker fault* (return and fix), an *environment fault* (the check could not run — park, never bounce, since a worker cannot fix an absent `node_modules`), and a *stale baseline* (main moved — re-integrate, then re-derive). Returning an environment fault to the worker is how a chain spends a night failing to repair something that was never broken.

**The re-walk rule.** A return to the worker invalidates every verdict downstream of it. After the fix, the tester and the reviewer run again, because their prior findings describe a tree that no longer exists. This is the staleness problem and the failure edge being one defect: without the rule, the chain ships a review of a tree it did not build.

**A bouncing step must commit before it returns.** Measured: an unchanged worktree is auto-cleaned, so a step that stops without committing destroys its own account of why it stopped. The findings *are* the handoff. A bounce carrying no artifact is indistinguishable from a step that did nothing at all — the same non-discrimination §4.4 measured in the harness's own success fields, reappearing on the failure path.

**A bounce budget, or the chain loops.** N returns to the worker, then a typed park. Without it a reviewer and a worker can disagree indefinitely and burn a night on one story. The budget counts *returns to the worker*, so a re-walk does not consume it. The number is per-repo; two is a sane default.

### 4.11 The completeness chain: source → plan → code

Completeness is two checks at two seams, not one check in one place, and they compose into an unbroken chain of custody.

**Seam one, at the planner: does the plan account for everything the source says?** **Seam two, after the worker: did every obligation the plan parked get an answer?** The reviewer then re-derives the composition — specification against code — independently of both, so a reader is checking the chain rather than being the only thing holding it up.

Seam two is the easy one: a set difference against the planner's parked rows, mechanical and re-derivable, run by the main loop immediately after the worker and before the tester, because it is grep-shaped and the tester is a full suite run. Cheapest gate first.

**Seam one is the one that matters, because a registry cannot see what nobody wrote.** **VERIFIED** in the lab's own instrument: every loop in `scripts/conformance-map.sh` iterates the registry TSV or a derivation of it, and the script never opens `claim-algebra.html` or `claim-calculus.html` at all. Its completeness is bounded by its own contents. That is exactly how it read fully-mapped and strict-green while two shipped-slice objects did not exist. Seam two inherits that defect entirely: it can only be as complete as the rows it reads, so a thin plan produces a chain where everything passes.

**The mechanism is constant; the source is not.** Whatever the source, extract its units, require every unit to be accounted for by at least one plan row, and print the denominator. What changes is what a unit *is* and how reliably it can be extracted — so the profile declares a mode, and **the check reports which mode it ran in, because a weak extraction must never render as a strong pass.**

| Mode | Source shape | The unit | Strength |
|---|---|---|---|
| `enumerable` | a specification with numbered results; a story with `- [ ]` criteria | each Definition / Theorem / Proposition / Obligation, or each checkbox | **Strong.** A real set difference with a printed denominator: "47 numbered results in §8 examined, 0 unclaimed." |
| `listed` | a finite set of documents — operator memory files, an ADR directory | each document | **Partial.** Proves every in-scope source was read and cited by some row. Proves coverage of *sources*, never of *obligations inside them*. |
| `prose` | a story description with no enumerable criteria | a requirement-bearing clause | **Weak, and self-referential.** See below. |

#### The mode belongs to the work item, and is derived rather than declared

**The mode is not a property of the repo.** One repo produces all three: "implement slice 9 per calculus §9" is `enumerable`, "do what we discussed about the panel" is `listed`, "fix the flaky test in FooSuite" is `prose`. A per-repo setting would be at the wrong granularity, and pinning one would either over-claim on the thin items or under-claim on the whole corpus.

**Nor may the planner declare it**, for the reason the rest of this document keeps returning to: that is the party being judged choosing the standard it is judged by, and the incentive runs one way. A planner short of time declares `prose` and passes.

So the repo declares only what is *available* and how to extract units from it; the mode for a given run is **derived from what the work item cites**, by the main loop, before the planner starts:

- The item cites a document and a locus (`calculus §9`, an ADR number, a file path with an anchor) → `enumerable` against that locus, with the repo's extraction pattern.
- It cites whole documents with no internal structure to enumerate → `listed`.
- It cites nothing → `prose`.

**Derivation is monotonic toward the strong end.** Citing more strengthens the check; citing less weakens it, and the weakening is visible because the mode is reported. Nobody can reach a weaker mode than their citations support.

**An uncited item still gets a scope, and the scope becomes a refutable artifact.** When the work item names no locus, the planner reads the corpus, determines which sections are relevant, and *records that determination*. The enumerable check then runs against the sections it named. The planner's scope selection is now the weak link — but it is a narrow, stated claim ("§9 is the relevant section") that the reviewer can refute directly, rather than a diffuse judgment buried in a plan. That is the same move as everywhere else here: convert an implicit choice into a written one that a later reader can attack.

**Never average the modes.** A work item with a specification *and* operator memory gets two checks at two strengths, reported separately. Collapsing them to one grade hides the weaker one, which is the uncounted-family defect `craft-measurement.md` names — a plural row discharged on one mapping.

**What no downstream check can find: an item that cites nothing but should have.** No mechanism detects a missing citation to a document nobody mentioned. That is an intake defect and it bounds the whole chain. The mitigation is not a check but a number: the mode is recorded per run, so a repo steadily producing `prose`-mode plans is visibly running a weak chain, and that is a metric the operator can watch rather than a silence they cannot.

**Say the limit of `prose` plainly rather than letting the mode disguise it.** The pack's planner handled this by requiring at least three concrete acceptance criteria, each a check the suite can run — which converts `prose` into `enumerable` by having the planner *author* the structure. That is the right move and it should be kept, but it does not make the check strong, because the rows are then compared against criteria the same agent wrote in the same sitting. Internal consistency is not evidence. In `prose` mode the completeness check verifies form, not coverage, and coverage rests on the operator reading the plan or on the reviewer's independent read. The mode name is what tells a reader which of those they are relying on.

**No source at all is a VOID, not a pass.** If the profile declares no sources, or the declared ones resolve to nothing, the check reports that it examined nothing and the chain records a completeness verdict it did not obtain. A silent green here is the failure this document is most repetitively about: a check that could not run reading identically to one that passed.

### 4.12 `merge_ok` — when the chain merges without asking

Elder's chain had three tiers: `glance_merge` merged at once, `review_encouraged` parked then auto-merged after 24h unless a human objected in the PR comments, `human_required` parked indefinitely. The operator's own envelope sat on top and overrode the tier: auto-merge when code lines ≤ ~700 (excluding plan and registry files — *count what carries risk, not length*), mergeable CLEAN, CI green, `review_verdict=pass`, no sensitive file touched, and no architectural signal.

**Its sharpest lesson was that the tier is not the gate.** The chain bumped to `human_required` on size alone above 100 added lines, so a blanket "human_required escalates" rule escalated nearly every PR and the 700-line envelope never fired. The fix was to split by cause: size-only escalation auto-merges, for-cause escalation does not.

**Here the two merging tiers collapse into one `merge_ok` state**, for a reason specific to this repository class rather than a general preference. Elder's capital floor existed because it traded live: a bad merge moved money, and revert does not un-place a trade. A library and a platform have no such floor — revert genuinely restores the prior state — and the sensitive-file list that carried the distinction is gone by operator decision (§4.9).

**Three of Elder's four conjuncts survive as checks, and the fourth changes character.**

| Conjunct | Status here |
|---|---|
| mergeable CLEAN, CI green | git and CI facts — re-derived |
| the gate green **on the merged tree** | §4.9's first fix, now carrying real weight |
| scope reconciliation against the planner's declared paths | re-derived from the cumulative diff |
| **source-set integrity** (§4.11, and the handoff) | re-derived; new, and mandatory once merging is unattended |
| review verdict / signals | the one testimony conjunct — fails closed |
| size | **no longer a gate.** It was a proxy for risk; with no capital floor and cheap revert it carries no information the operator lacks. Report it, do not branch on it |

**What still escalates** is small and nearly all re-derivable: a red gate on the merged tree, scope reconciliation failing, a reviewer refutation not disposed, **reviewer could-not-inspect**, a check that could not run, or the bounce budget exhausted.

#### Two conditions without which `merge_ok` is unsound

Both come from the archived `chain-finalizer.md`, which parked rather than merged and wrote down what would have to hold before autonomous merge was ever switched on. This design switched it on; these are the conditions it owes.

**Trusted-base exclusion.** A diff touching the chain's own judge **parks regardless of green**. The prompt's phrasing is the argument: *"a merger that can merge changes to its own judge is self-signing with a scheduler."* Without it, a story that edits `.githooks/pre-commit` or the gate script merges itself on the verdict of the thing it just edited — the exact failure the rest of this document is written against. Match by **path prefix, with symlinks resolved and moves-out blocked**; a rename out of the protected set is the obvious evasion. The path list is per-repo and lives in `profile.toml` (§5), because the kit ships the mechanism and the repo names its own judge.

**Sha pinning.** Re-read the branch head immediately before merging and abort if it moved. Every conjunct was computed against a specific tree; merging a different one signs work nothing examined. This costs one `git rev-parse` and closes the whole window between verdict and merge.

A third condition from that prompt is already carried: the adversarial pass **may add a veto but its silence never confers authority** — which is §4.10's three-valued reviewer output, where absence is a coverage receipt rather than an approval.

**A short veto window is a property of `merge_ok`, not a second tier.** It is what `review_encouraged` actually bought, it costs nothing when nobody is watching, and it gives the documenter's briefing (§4.9) something to be read *during*.

**Where "we can always revert" stops being true**, stated now so nobody discovers it later: anything pushed to a public remote, where caches and forks outlive a revert; a tagged artifact someone has consumed; and a change to the formal core documents, where revert restores the bytes but not a conformance decision made against the wrong bytes in between. None applies on day one. All three are reachable.

**One dependency this creates.** Unattended merging makes the merged-tree gate the only thing standing between a story and `main`. It was already the first thing to build; it is now the single unchecked artifact that ships *by itself*.

**And it collapses the finalizer.** That step's warrant was *package and park for operator merge* — with the parking retired here, the briefing moved to the documenter (§4.9), and every verdict belonging to the main loop by §4.2(a), what remained was integration plus predicates. An agent there is a shallow module that converts mechanical facts into testimony on the way past, and the one genuinely non-mechanical case — a merge conflict — is already a stale-baseline escalation under §4.10. So the chain is **five agents and a main-loop merge stage**, and the contradiction of a step whose warrant said *park* while §4.12 says *merge* does not arise.
---

## 5. The per-language plug points

The runtime names no language. A per-repo profile does, and the kit already has most of the machinery.

**The profile** (`.claude/chain/profile.toml`, **PROPOSED**) supplies, per repo:

| Key | What it is | Example |
|---|---|---|
| `check` | the commit-path mechanical check | `bash scripts/check.sh` |
| `build` | compile only, for the fail-closed precondition | `sbt Test/compile` |
| `test_one` | run one named test | `sbt 'testOnly *FooSuite'` |
| `gate_toolchain` | forced toolchain for the differential gate | `scala` |
| `rules_glob` | which rule family injects | `scala-*.md` |
| `red_proof` | how to build old-impl-against-new-tests | (see below) |
| `phases` | which agent steps are installed, in order (the merge stage is the main loop's, not a phase) | `["planner","worker","tester","reviewer","documenter"]` |
| `trusted_base` | paths whose modification parks a story regardless of green (§4.12) | `[".githooks/", "scripts/", ".claude/rules/", ".claude/workflows/"]` |
| `sources` | the corpus available to the planner's completeness check, and how to extract units from each (§4.11) | see below |

**The profile declares availability and extraction. It does not declare the mode** — that is derived per work item from what the item cites, by the main loop, before the planner starts (§4.11). A repo produces all three modes across its stories, so pinning one here would be at the wrong granularity.

```toml
# The strong case: a specification with numbered results. An item citing a locus in
# this document ("calculus §9") derives `enumerable` against that section.
[[sources]]
path = "docs/claim-algebra/claim-calculus.html"
unit = '(Definition|Theorem|Proposition|Lemma|Obligation|Remark)\s+[0-9.]+'

# No internal structure to enumerate, so an item citing these derives `listed`:
# coverage of the documents, never of the obligations inside them.
[[sources]]
path = "~/.claude/projects/<project>/memory/*.md"

# A story with checkbox criteria is enumerable on the checkboxes.
[[sources]]
path = "story.md"
unit = '^- \[ \] '
```

A source with no `unit` pattern can never reach `enumerable`; that is the honest ceiling of a corpus with nothing countable in it, and it should be visible in the profile rather than discovered at run time.

**The phase roster is per-repo, and that is an operator decision rather than a property of the chain.** The runtime sequences whatever `phases` lists; it holds no opinion about which steps exist. The documenter's briefing renders as a PR body where a remote takes PRs and as a plain report where it does not, so the step earns its place either way (§4.9).

**`trusted_base` is the one entry with no safe default.** It names the paths that hold the chain's own judge, and it is repo-specific by nature — the kit cannot know where a given repo keeps its hooks, its gate, or its predicates. An empty or absent list means every path is mergeable including the checks themselves, so the mechanism must **fail closed on an unset list** rather than treating it as "nothing protected." That is the difference between a fence and a fence-shaped configuration key.

Two constraints on any roster, both from §4.9. The **terminal** step — whichever one `phases` ends with — carries the re-derived completion criterion on the merged tree, so removing a step must never orphan that check. And a roster is not a menu of independent items: dropping the documenter also drops the terminal scope gate it happened to carry, so the profile's own documentation has to say what each step is holding besides its name.

**The differential gate is already the language plug point and already has the right shape.** `reference/sdlc-gate.py` on kit main carries a scanner-plugin layer: one language-agnostic engine (baseline/diff worktree model, `(file, code)` multiset identity, rename tracking, relocation-advisory downgrade, waivers, verdict logic) with per-toolchain scanners for Check A (static-analysis identity), Check B (suppressions), and Check D (test weakening). Detection is by marker file, `--toolchain` forces it. I confirmed the toolchains present: **python** (ruff/mypy/bandit), **scala** (scalafix/wartremover, plus a fail-closed compile precondition and opt-in scoverage), **java** (checkstyle, jqwik parameter weakening, opt-in JaCoCo). **VERIFIED** by reading the source.

**Go is the remaining gap, and TypeScript was one until this slice.** `claude-project/rules/` ships eight `go-*.md` and nine `ts-*.md` rules. `sdlc-gate.py` now registers a TypeScript toolchain — eslint and `tsc` for Check A, the `eslint-disable`/`@ts-ignore` families for Check B, skip-marker and assertion-site counts plus istanbul coverage for Check D, and `tsc --noEmit` as the compile precondition — calibrated against a real 31-file suite. It has **no Go toolchain and no `go.mod` marker**. **VERIFIED against `_TOOLCHAINS`, not recalled.** So the language axis is five-on-rules and four-on-the-gate, one hole rather than the two this line previously undercounted to one: it said three-of-four and did not count TypeScript at all. A Go toolchain (golangci-lint for Check A, `//nolint` for Check B, `t.Skip` plus assertion-site counts for Check D) is the obvious next scanner and it lands standalone, independent of the chain.

**The scanner-exit-code hazard is a per-language plug-point audit item.** The lab's Scala `gate` module has a live instance: `gate/src/main/scala/gate/ScalafixScan.scala:33` runs `sbt scalafixAll --check` and never reads `r.exitCode`, where `WartScan` does read it and raises. **VERIFIED**. The fix is not to copy WartScan's polarity — scalafix `--check` returns non-zero *precisely when findings exist* — but a three-way discrimination: non-zero with parseable findings (normal), non-zero with no parseable findings or a compile-error stderr (operational, fail closed), clean. That needs a captured transcript of a genuinely failing scalafix run to ground it, per this repo's own standing rule that each scanner's format is captured from the real tool before its parser is written. Every toolchain the kit adds must be audited for the same shape: **does this scanner distinguish "clean" from "did not run"?** It belongs in the plug-point contract, not in a per-language footnote.

**Red-proof is language-parameterized and git-only.** The instrument existed and was thrown out with the ledger: `ledger/red-proof --test-cmd '<runs the new tests>'` built the implementation at the merge-base against HEAD's tests and required them to go red. Its substance is git plus a test command, so unlike the postconditions it survives the ledger's deletion. Reinstate it as a standalone script with no `model` import: exit 0 (went red, detection power shown), exit 2 (stayed green, the test cannot fail). The driver runs it as the worker→tester transition predicate. `test_one` and `test` come from the profile; the script names no language. **PROPOSED**, but the mechanism is recoverable verbatim from `archive/kit-chain`.

**Rules injection stays as it is.** `.claude/rules/*.md` with `paths:` globs, auto-injected on matching file opens. The chain does not touch this; it is already per-language and already works.

---

## 6. Build order

**The inventory now lives in `sdlc-chain-walkthrough.md`**, where every step carries its build state.
This section is only what a runtime walk cannot express: the principle that orders the work, and the
items that are not chain steps at all.

An earlier version of this section was a fourteen-step sequence written around a `claude -p` bash
driver. That driver is gone (§4.8), and re-numbering the list would have carried its assumptions
forward under new labels.

### 6.1 The ordering principle

**A build order is not the runtime order, and confusing the two is the trap.** The chain *runs*
planner-first; you would never *build* the planner first. Two rules put the work in order instead:

**Build the verifier before the thing it verifies.** The predicate that decides a phase must exist,
and must have been shown capable of failing, before the phase whose output it grades. Otherwise the
first thing built is an actor with nothing watching it, and every later step is added on the word of
an instrument nobody has tested.

**Build so you can stop anywhere.** Each step earns its keep alone, so an abandoned build leaves
working tools rather than half a chain. This is not tidiness — it is the only honest hedge on a
design where nothing is yet built, and it is why the independent items below are worth doing first if
the chain itself is ever deferred.

### 6.2 What pays with no chain at all

These need no phase, no driver, and no story graph. Several address where this build's defects
actually came from (§3.4), which makes them the highest-value-per-line work in the document.

- **A `test-kind` registry column, and its two checks.** A column recording the kind of test a row
  requires: `bundle` rows must resolve to a `checkAll(` call, `witness` rows must not. The cheapest
  item here, needing no prompting — it catches a row discharged by hand when a stock law suite was
  available, which happened twice in one build even though the plan stated the rule (§3.8).
- **The citation checker.** Extract every `§N.M` from the sources, confirm the cited document has
  that section, and confirm the cited section's text still contains the term the citation claims.
  Closes source drift (§3.5) mechanically, where twelve stale citations were corrected by hand and
  the correcting slice introduced three more.
- **The negative-space checklist.** Extract the qualifier-bearing sentences from each cited section
  and require the registry to account for each. Fourteen in the whole calculus, so it is small.
- **Blind re-derivation, as a workflow rather than a phase.** Two prompts, not one (§3.8):
  plan-versus-specification and code-versus-plan have different reference points and different blind
  spots. Two forms (§3.6, §3.7): derive the test from the row statement, and derive the row
  statements from the document section. An operator can invoke either on a slice today.
- **Red-proof, reinstated.** Git-only, `--test-cmd` from the profile, exit 0 or 2. A detection-power
  check for any TDD slice, chain or not.
- **A Go toolchain for the gate**, which closes the language axis (§5) and depends on nothing here.
- **The machine hardening checklist** (§4.3). Not code — an `INSTALL-HARDENING.md` the operator
  applies, each step carrying the measurement that says whether it took.

---

## 7. The honest ceiling

**Containment remains a label for every warrant that depends on a phase agent holding Bash.** Measured, not argued: `bash -c 'rm -rf <path>'` executed with the banned string in the inspected command, `printf > file` wrote content a PreToolUse hook had rejected seconds earlier, and five of six deny-rule evasions succeeded. The phase agents hold Bash by design. The warrant partition the design wants is not among the mechanisms available to it. `isolation: worktree` is real and is kept on its own merit; the command grep beside it must not be co-billed as a second layer.

**The path to real containment is two root-owned changes away and neither is done.** Endpoint-managed settings need passwordless sudo removed first; verify with `sudo -n true`. The bubblewrap sandbox — the only mechanism that reaches inside `python -c` and `bash -c` — fails on stock Ubuntu 24.04+ with `setting up uid map: Permission denied` unless an AppArmor profile for bwrap is installed, and the sysctl cannot be relaxed from a subagent. Until both are installed *and measured*, containment is friction. The sentence that used to close this item — *what reaches main rests on the human merge or a server-side gate* — is retired by §4.12; what reaches main now rests on revert, within the bounds that section names.

**Hooks enforce that a check ran. They never enforce that it discriminates.** This is the one weakness no configuration surface reaches. Red-proof establishes that a new test fails against the *old* implementation; it does not establish that it fails against a plausible *wrong new* implementation, which is the property actually wanted. That needs mutation testing, and mutation was **removed from the chain by operator decision** (§4.9) — so detection power is not merely unbought here, it is unowned by choice, with §3.8's own measurement putting the cost at two of nine defects that neither other reader caught. What survives is the worker's habit of perturbing shipped code, which is testimony where a phase would have been re-derived. Every mechanism above buys enforcement; detection power has to be bought separately and now is not.

**The harness's self-report is not a phase verdict, and this was measured rather than reasoned.** A
headless phase with no write-capable tool exits 0 with `is_error: false`, `subtype: "success"` and an
empty `permission_denials` having done nothing (§4.4). Any driver that branches on those fields runs
a night of phases that succeed at nothing. The mitigation — re-derive from git — is the design's own
central property, and the first draft of this document violated it. Assume the same failure exists in
any other place the design reads a self-report, and go looking.

**Four things are unmeasured and the design must not assume them.**

1. *PreToolUse command-hook timeout polarity.* Undocumented for the event that matters, documented both ways on adjacent events. Mitigation (bound your own subprocess) is mandatory rather than defensive. Measurement: run a PreToolUse command hook that sleeps past its timeout, record whether the Bash call proceeds.
2. *Compaction inside a phase.* The `-p` framing of this item is obsolete (§4.8), but the question is not: nothing describes what a **subagent** does when its context fills mid-phase, and a phase that compacts may lose the instructions that constrained it. Measurement: run a phase with a deliberately oversized context and record whether it completes, whether its output shows the loss, and whether the main loop's predicate still discriminates.
3. *SubagentStop's real blocking strength.* hooks.md documents it as blocking ("Prevents the subagent from stopping"); whether re-engagement can be refused indefinitely by the subagent is untested. The driver-side predicate is the authority regardless, which is why this does not change the design.
4. *The API tier's ITPM.* Unknown, and it decides the concurrency level against a measured ~43K tokens/min per workflow. Look it up; do not infer it from a story count.

**A green suite is not evidence that beliefs are current, and this was measured rather than feared.** Nine assumptions carried from a prior edition of the specification were checked against a clean-room reading of the current one: four were wrong, one of them a gate predicate short by two conjuncts that therefore **signs what the core blocks**. Every survivor was a claim about the carrier and its operations, each with a proof attached; every casualty was a claim about the envelope around it — which events exist, what the gate conjoins, what a person sees — and that envelope is exactly what a new edition rewrites. **A test suite exercising carrier behaviour would have gone green on all nine.** Two of the four failed identically, by remembering a *closed* vocabulary short. Hence the closed-set cardinality check: extract every set the documents declare closed and assert the implementation's members match by name and by count.

**An instrument whose denominator is derived from the artifact under test can be silenced by deleting the artifact.** A shipped document validator was run against its own corpus with a 108 KB formal-core document replaced by 189 bytes of stub. It reported `1609/1609 checks passed`, exit 0. Nothing failed — 18 checks *ceased to exist*, because its link and anchor checks are generated from the content being validated, and its pass line still read N/N. This is the third distinct shape in this document of the same defect, after the harness self-report and the always-failing predicate, and it is the one hardest to see, because the number that moved is the one nobody prints a baseline for.

**Two structural limits that no amount of building removes.**

The fence is a denylist over another program's flag surface and over arbitrary shell. Both move. `--bare` and `--safe-mode` are today's one-flag bypasses; the next release may add a third. A design that treats the evasion set as enumerable is wrong in a way that gets worse over time, which is the reason the word is friction.

And the sequencer's judgment-free property holds only as far as its predicates are honest. A predicate that always fails and a driver that always halts look exactly like a working fence from outside — which is what the archived `postcondition.py` has been for a month. The known-good fixture is not optional polish; without it the fence is verified only by never having been passed.

**What the chain is, stated without softening.** Three things, and they are stated as invariants rather than as a description of the build, because the first version of this paragraph described the build and every clause of it was false within a day — a bash driver, five phases, stopping at a merge-ready branch, a human doing the merging. What follows cannot change without this becoming a different design.

**Advancement is re-derived, never reported.** Nothing advances because an agent said so. Position comes from git and from predicates run by something that can actually look. This is the only clause of the original paragraph that survived, and it survived because it is the design rather than an account of how the design was assembled.

**It contains accidents and drift. It does not contain intent.** The phase agents hold Bash; the fence is friction and is labelled as such. Measured again while this document was being written: a text-matching hook blocked one attempt in four.

**It survives its own death**, because position lives in git rather than in the process.

What it rests on is now **revert**, not review — sound for a repository class with no irreversible action, and expiring at three named points (§4.12): a push to a public remote, a consumed tag, and a change to the formal core documents. When one of those enters play the human merge returns, and §2 keeps its struck entry so that return is a restoration rather than a rediscovery.

Everything else — who drives, how many phases, what merges — belongs to the sections that own it, and is expected to move.
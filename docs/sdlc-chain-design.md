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

**Five phases, one warrant each.** planner (park the plan), worker (build through the gate, **then audit its own diff and fix what the audit returns before handing off** — §3.9), tester (attest only, never touches production code), reviewer (refute or report absence, never approves), finalizer (package and park for the operator's merge). The archived agent files carry this vocabulary already and it is good. What changes is that the warrant is no longer claimed to be *enforced* by the frontmatter — see §4.

**The human merge is the transition-grade backstop.** The chain is autonomous up to a merge-ready branch and no further. The finalizer does not merge. This was right before, it is right now, and nothing measured in the review earns the right to retire it. The archived `chain-worker.md` says it plainly and should be kept verbatim: what reaches `main` rests on the human merge or a server-side gate, never on the local gate alone.

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

**So phase position is re-derived from git, every resume, always.** A phase completes by creating a ref — `chain/<story-id>/phase-<n>` — or by a phase-tagged commit trailer. The resume path asks git "what is the highest completed phase for this story?" and never asks the log, and never asks a story spec's `status:` frontmatter. This generalizes W9's conclusion: **status fields are advisory, git is authority.**

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

**The recommended shape, given all of the above:** a workflow drives sequence; subagents do the work in worktrees and commit; the phase verdict is a git hook plus a parent-side re-derivation done in Bash from the main session, never a field the workflow script computed from an agent's return value. That keeps §4.2(a) intact by relocating it rather than by trusting the orchestrator with it.

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

**The differential gate is already the language plug point and already has the right shape.** `reference/sdlc-gate.py` on kit main carries a scanner-plugin layer: one language-agnostic engine (baseline/diff worktree model, `(file, code)` multiset identity, rename tracking, relocation-advisory downgrade, waivers, verdict logic) with per-toolchain scanners for Check A (static-analysis identity), Check B (suppressions), and Check D (test weakening). Detection is by marker file, `--toolchain` forces it. I confirmed the toolchains present: **python** (ruff/mypy/bandit), **scala** (scalafix/wartremover, plus a fail-closed compile precondition and opt-in scoverage), **java** (checkstyle, jqwik parameter weakening, opt-in JaCoCo). **VERIFIED** by reading the source.

**Go is a gap.** `claude-project/rules/` ships eight `go-*.md` rules, and `sdlc-gate.py` has no Go toolchain and no `go.mod` marker — its own error message lists only scala, java, and python. **VERIFIED**. So the language axis is three-of-four on rules and three-of-four on the gate, with different holes. A Go toolchain (golangci-lint for Check A, `//nolint` for Check B, `t.Skip` plus assertion-site counts for Check D) is the obvious next scanner and it lands standalone, independent of the chain.

**The scanner-exit-code hazard is a per-language plug-point audit item.** The lab's Scala `gate` module has a live instance: `gate/src/main/scala/gate/ScalafixScan.scala:33` runs `sbt scalafixAll --check` and never reads `r.exitCode`, where `WartScan` does read it and raises. **VERIFIED**. The fix is not to copy WartScan's polarity — scalafix `--check` returns non-zero *precisely when findings exist* — but a three-way discrimination: non-zero with parseable findings (normal), non-zero with no parseable findings or a compile-error stderr (operational, fail closed), clean. That needs a captured transcript of a genuinely failing scalafix run to ground it, per this repo's own standing rule that each scanner's format is captured from the real tool before its parser is written. Every toolchain the kit adds must be audited for the same shape: **does this scanner distinguish "clean" from "did not run"?** It belongs in the plug-point contract, not in a per-language footnote.

**Red-proof is language-parameterized and git-only.** The instrument existed and was thrown out with the ledger: `ledger/red-proof --test-cmd '<runs the new tests>'` built the implementation at the merge-base against HEAD's tests and required them to go red. Its substance is git plus a test command, so unlike the postconditions it survives the ledger's deletion. Reinstate it as a standalone script with no `model` import: exit 0 (went red, detection power shown), exit 2 (stayed green, the test cannot fail). The driver runs it as the worker→tester transition predicate. `test_one` and `test` come from the profile; the script names no language. **PROPOSED**, but the mechanism is recoverable verbatim from `archive/kit-chain`.

**Rules injection stays as it is.** `.claude/rules/*.md` with `paths:` globs, auto-injected on matching file opens. The chain does not touch this; it is already per-language and already works.

---

## 6. Build order

Each step is useful standalone. Nothing later is required for anything earlier to pay.

**1. The phase runner, with a git-derived verdict.** A single shell function wrapping `claude -p --output-format stream-json --verbose`, appending to a per-phase `.jsonl`, and deciding the phase from a postcondition the runner evaluates itself (§4.4) — never from the stream fields. Stream fields are logged for diagnosis. Plus the pinning test, which is not optional: run a phase with every write path withheld and assert the runner reports FAILURE. Measured, that phase reports `subtype: "success"`, `is_error: false`, empty `permission_denials`, and exit 0 while doing nothing, so a runner without this test is verified only by never having been given a phase that could not act. *Standalone value:* anyone running headless Claude in CI gets a success predicate that is about the work rather than about the harness.

**2. Git-derived phase markers and the driver event log.** Phase refs (`chain/<story>/phase-<n>`), the resume path that asks git rather than the log, and the append-only log with `about` / `supersedes` / `discharged_by` / cost / wall time. *Standalone value:* an audit trail and a resumable position for any multi-step automation, chain or not.

**3. The predicate set, rebuilt over git.** Recover `postcondition.py` from `archive/kit-chain`, delete the module-scope `import model`, restore `tester-clean` (pure git already — `git rev-parse`, `git diff --name-only`, a removed-line scan), and re-express `worker-complete` and `no-open-refutation` over git-derivable state, since the obligation edges they folded over now live on the driver's log. Driver branches on `rc != 0`, never `rc == 2`. **Each predicate pinned by both a known-good fixture returning 0 and a known-bad fixture returning non-zero** — a predicate that always fails and a driver that always halts are externally indistinguishable from a working fence. *Standalone value:* runnable checks the operator can call by hand today.

**4. The language profile plus the existing gate.** `profile.toml`, and wire `sdlc-gate.py --toolchain <x>` in as the gate predicate. *Standalone value:* the gate already works; this makes it callable uniformly.

**5. Red-proof, reinstated.** Git-only, `--test-cmd` from the profile, exit 0/2. *Standalone value:* a detection-power check for any TDD slice, chain or not.

**6. The five agents and their phase prompts.** Recovered from `archive/kit-chain` with every ledger and claim reference stripped, warrant language kept, and the frontmatter honesty fix applied: the `tools:` list is a runtime allowlist for *tool* calls (**DOCUMENTED**) and is not containment for a Bash holder (**VERIFIED**) — say so in the brief. `isolation: worktree` plus `worktree.baseRef: "head"` on tester and reviewer.

**7. The fence hooks.** PreToolUse on `Bash` and `Write|Edit`, keyed on `agent_type`, with the corrected pattern set, each bounding its own subprocess with `timeout`. Header comment states plainly that this is friction. *Standalone value:* catches accidental `--no-verify` and accidental grader edits from day one.

**8. Cron start and the concurrency lock, in one change.** `flock` per story, atomic `git branch chain/<story>`, cron entry, stall SLO on total phase wall-clock, `CLAUDE_CODE_RETRY_WATCHDOG=1`. Never ship 8 without the lock.

**9. The machine hardening checklist.** Not code — an `INSTALL-HARDENING.md` the operator applies: remove passwordless sudo and re-measure with `sudo -n true`; install `/etc/claude-code/managed-settings.json` root-owned with `disableBypassPermissionsMode: "disable"` and `allowManagedPermissionRulesOnly`; move predicate scripts to a root-owned path with an absolute root-owned interpreter; attempt the bubblewrap sandbox and record whether it works. Each step has a measurement that says whether it took.

**10. A Go toolchain for the gate.** Independent of everything above.

**11. The `test-kind` registry column, and its two checks.** A column recording the kind of test a
row requires, plus: `bundle` rows must resolve to a `checkAll(` call, and `witness` rows must not.
*Standalone value:* the cheapest item in this document, needing no prompting at all — it catches a
row discharged by hand when a stock law suite was available, which happened twice in one build even
though the plan stated the rule (§3.8).

**12. The citation checker.** Extract every `§N.M` from the sources, confirm the cited document has that section, and confirm the cited section's text still contains the term the scaladoc claims. *Standalone value:* closes source drift (§3.5) mechanically, where twelve stale citations were previously corrected by hand and the correcting slice introduced three more.

**13. The negative-space checklist.** Extract the qualifier-bearing sentences from each cited section and require the registry to account for each. Fourteen in the whole calculus, so this is small. *Standalone value:* a review checklist grounded in the document rather than in memory.

**14. Blind re-derivation as a reviewer phase.** Two prompts, not one, per §3.8: plan-vs-specification and code-vs-plan have different reference points and different blind spots. Two forms, per §3.6 and §3.7: derive the test from the row statement, and derive the row statements from the document section. *Standalone value:* neither needs the chain to run; both are workflows an operator can invoke on a slice today.

Steps 1–3 are the chain's central property. Steps 4–6 make it do work. Steps 7–9 make it run unattended. Step 10 closes the language axis. Steps 11–14 are the drift instruments, and they are the ones that address where this build's defects actually came from (§3.4).

---

## 7. The honest ceiling

**Containment remains a label for every warrant that depends on a phase agent holding Bash.** Measured, not argued: `bash -c 'rm -rf <path>'` executed with the banned string in the inspected command, `printf > file` wrote content a PreToolUse hook had rejected seconds earlier, and five of six deny-rule evasions succeeded. The phase agents hold Bash by design. The warrant partition the design wants is not among the mechanisms available to it. `isolation: worktree` is real and is kept on its own merit; the command grep beside it must not be co-billed as a second layer.

**The path to real containment is two root-owned changes away and neither is done.** Endpoint-managed settings need passwordless sudo removed first; verify with `sudo -n true`. The bubblewrap sandbox — the only mechanism that reaches inside `python -c` and `bash -c` — fails on stock Ubuntu 24.04+ with `setting up uid map: Permission denied` unless an AppArmor profile for bwrap is installed, and the sysctl cannot be relaxed from a subagent. Until both are installed *and measured*, the correct sentence is the prior design's own: what reaches main rests on the human merge or a server-side gate.

**Hooks enforce that a check ran. They never enforce that it discriminates.** This is the one weakness no configuration surface reaches. Red-proof establishes that a new test fails against the *old* implementation; it does not establish that it fails against a plausible *wrong new* implementation, which is the property actually wanted. That needs mutation testing and nothing in the surveyed capability surface supplies it. Every mechanism above buys enforcement; detection power has to be bought separately and mostly is not.

**The harness's self-report is not a phase verdict, and this was measured rather than reasoned.** A
headless phase with no write-capable tool exits 0 with `is_error: false`, `subtype: "success"` and an
empty `permission_denials` having done nothing (§4.4). Any driver that branches on those fields runs
a night of phases that succeed at nothing. The mitigation — re-derive from git — is the design's own
central property, and the first draft of this document violated it. Assume the same failure exists in
any other place the design reads a self-report, and go looking.

**Four things are unmeasured and the design must not assume them.**

1. *PreToolUse command-hook timeout polarity.* Undocumented for the event that matters, documented both ways on adjacent events. Mitigation (bound your own subprocess) is mandatory rather than defensive. Measurement: run a PreToolUse command hook that sleeps past its timeout, record whether the Bash call proceeds.
2. *Compaction under `-p`.* Nothing in the readings describes what a headless phase does when its context fills. Measurement: run a phase with a deliberately oversized context, record whether a compaction event appears in the stream, whether the phase completes, and whether `--resume` recovers it.
3. *SubagentStop's real blocking strength.* hooks.md documents it as blocking ("Prevents the subagent from stopping"); whether re-engagement can be refused indefinitely by the subagent is untested. The driver-side predicate is the authority regardless, which is why this does not change the design.
4. *The API tier's ITPM.* Unknown, and it decides the concurrency level against a measured ~43K tokens/min per workflow. Look it up; do not infer it from a story count.

**Two structural limits that no amount of building removes.**

The fence is a denylist over another program's flag surface and over arbitrary shell. Both move. `--bare` and `--safe-mode` are today's one-flag bypasses; the next release may add a third. A design that treats the evasion set as enumerable is wrong in a way that gets worse over time, which is the reason the word is friction.

And the sequencer's judgment-free property holds only as far as its predicates are honest. A predicate that always fails and a driver that always halts look exactly like a working fence from outside — which is what the archived `postcondition.py` has been for a month. The known-good fixture is not optional polish; without it the fence is verified only by never having been passed.

**What the chain is, stated without softening.** A bash driver that runs five phases, decides advancement from git and from predicates it runs itself, logs what happened outside the tree, survives provider outages and its own death, and stops at a merge-ready branch. It contains accidents and drift. It does not contain intent. The human merge is not a placeholder for a mechanism that is coming — it is the mechanism, and everything above it is instrumentation for the person doing the merging.
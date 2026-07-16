# The ledger, operated — a user's manual

**For the operator. The skills pack teaches the instances; this document teaches you — what to say, what to run, what to read, and the small set of verbs that are yours alone. It assumes the six skills are installed and `ledger/board.sh` exists. Ten minutes a week of the rituals below is the difference between owning a ledger and being owned by a pile of JSON.** 2026-07-11.

## The five-minute quickstart

Three commands you can run yourself, any time, from the repo root:

```
ledger/board.sh open        # what the institution currently believes but hasn't proven
ledger/board.sh stale 30    # what it's been believing unexamined for a month
ledger/board.sh find <word> # has this ever come up, in any status
```

Two phrases that put the machinery to work for you: open any session with **"check the board first"**, and start any new effort with **"write the claim before the work."** Everything else in this manual is elaboration.

## What the ledger is to you

Four instruments in one file, and maximum effect means playing all four on purpose. It is your **memory**, the only participant that survives instance turnover, compaction, and sleep. It is your **to-do list**: the unverified column is, literally, the research program. It is your **bank**: a signed claim is capital you spend by citing instead of re-earning, which is why verification cost falls over time instead of rising. And it is your **court of precedent** — the graveyard of refuted claims is the list of roads nobody walks twice. The instances now carry the procedures; your job is direction, judgment, and the handful of verbs no one else may perform.

## You don't invoke skills — you speak, and they fire

The descriptions were written for triggering, so your natural phrasing is the interface. What to say, what fires, and what to expect back:

| You say | What fires | What comes back |
|---|---|---|
| "Check the board" / "what's open?" / "let's start on X" | `ledger-board` | The open list, a `find` on X, and any graveyard hit *before* design starts |
| "Should we record this?" / "log my authorization" | `ledger-write` | The three-question test applied aloud, then a correct entry (or a reasoned no) |
| "Write the claim first" / "pre-register this" | `ledger-preregister` | A verbatim claim with every clause checked for dischargeability, parked so nothing auto-signs |
| "Is this already established?" / "land it" | `ledger-discharge` | A citation instead of a re-check, or a proper landing with the `pushed:` line |
| "Correct claim X" / "clean up the board" | `ledger-retire` | A supersession, never an edit — and a refusal to late-sweep, with the reason |
| "Verify this report against the record" | `ledger-verify` | Outside-clone audit, recomputed arithmetic, and any report-versus-ledger divergence named |

The habit that makes the table work: **say the trigger phrase early in the session, not after work has started.** A board check after design begins is a seatbelt fastened mid-crash.

## The three rituals

**Session-open (thirty seconds).** "Check the board first." You're looking for two things: does anything open bear on today's work, and did anything land since you last looked that today's work should *cite* rather than redo.

**Before commissioning anything (one minute).** "Have we been here?" — a `find` on the topic plus a graveyard glance. A refutation hit ends the conversation and saves you days; a signed hit converts your task from "establish X" to "build on clm-NNNN." This ritual alone repays the entire skills build: the capacity conjecture's corpse once stopped a full re-litigation for the price of a grep.

**The weekly ten minutes (yours, calendared).** Run `open`, `stale 30`, and `checks`. For every stale item, ask exactly one question (*discharge it, park it properly, or retire it honestly?*) and give the instance the verdict. Discharge means the check exists and should just run. Park means the claim is real but its court isn't built yet: make sure it names its future check so it's waiting, not rotting. Retire means you no longer believe it enough to keep it on the books — supersede it with the reason and move on. A stale item with no verdict is the one failure mode the machinery can't fix, because it's a judgment call, and judgment is your column.

## The verbs that are yours alone

The instances write, discharge, and verify; five acts route through you and only you, and doing them *crisply* is most of what "maximum effect" means at the operator level:

1. **Authorize, loggably.** Out-of-band authorizations enter the record with principal, channel, and date, so give them in a form that can be logged verbatim: *"Authorized: the release cut. Alex, direct, 2026-07-11."* One sentence; a pronoun misread once cost the founding project a false accusation and a retraction, and this format is the cure.
2. **Place the bets.** Predictions are the campaign's honesty about itself, and they're yours to make or bless. A bet that can't die isn't a bet — insist every prediction entry has a court and a date it could lose in.
3. **Sign off what becomes belief.** Dissent enters freely — refutations and testimony from any source land on the record without your sign-off; what your sign-off gates is what becomes *institutional belief*: the successions and dispositions (a claim promoted, a bet adjudicated, a contest resolved), not what may be *said*. The record can hold anything; what the institution asserts passes through you.
4. **Set the ceilings.** Budgets, pause thresholds, and go-words are operator inputs by construction. Give them as numbers with a checkpoint rule, and the instances will honor them mechanically.
5. **Release the gates.** Pre-registered cells wait on your word. The word is one message; the discipline is that nothing runs before it.

## Reading the board like an owner

The numbers are management information if you read them as trends. **Open count rising month over month** means commitments are outpacing discharge: either you're minting claims too casually (tighten the three-question test) or you're short a check (build one). **Stale items clustering around one topic** means the institution is avoiding something; name it at the weekly review. **The checks histogram** tells you which verifiers earn their keep: a check cited thirty times is a crown jewel worth hardening; a check used once may have been ceremony. **The graveyard** is your best onboarding document, because any new collaborator, human or instance, should read the refutations first — knowing what's false and *why* transfers judgment faster than any tour of what's true.

## Anti-patterns — the short list of ways to lose

Never edit a line, including your own typos: supersede, or the immutability drill will flag you as the tamperer you technically were. Never ask an instance to "just mark it signed": a signature without its check is a forgery, and the instance will refuse, which is correct and should stay correct. Never let a report float free of ids: a document that cites no claims can't be checked against the record, and one that contradicts the record is a defect that must be named, not shrugged past. Never write diary entries — the three-question test applies to you too, and a board full of musings drowns the claims that matter. And never skip the `pushed:` glance when *you* were the one at the keyboard: a milestone that hasn't left the machine is drafted, not done, no matter who typed `git commit`.

## The four disclosure conventions

A report is checkable only if it says what it is *evidence of*, and by whom. Four one-sentence habits, carried verbatim in `ledger/report-conventions.md` (vendored into the repo on install) so they sit beside a repo's reports. **The semantics line:** every verify-family claim states what its signature actually certifies — a receipt reproduced, two legs agreeing, a mechanical check passing — and points at the leg that would carry *correctness* beyond that; a signature means only as much as the weakest provenance in its chain. **The authorship note:** a report discloses the true authoring order in one sentence — written fresh, adapted from a template, or produced by a prior session or another author — rather than dressing an outcome as sole fresh work. **The reliability boundary:** any retrospective account says at what granularity it is evidence versus memory (commit-anchored and re-readable versus recalled), and flags every context-compaction seam, across which recall is unverified testimony about the past. **The process paragraph:** per slice, four sentences — were the tests written before, alongside, or after the code; which new tests were *observed red* and by what route; was any assertion or golden *adjusted after seeing actual output* (the green-by-weakening disclosure, legitimate but owed a sentence); and was the refactor pass done or skipped. "I ran it and the tests passed" is an outcome, not the process; the `red-proof` check is the mechanical court for the observed-red claim. The reliability boundary governs all four — definitive statements only for direct-recall work.

## The development loop

Five beats per slice, and the harness enforces them so nobody has to be trusted about it: **claim** (the acceptance claim first, as its own ledger-only commit — the precedence timestamp `tdd-precedence` reads); **red receipt** (observe the test fail, by natural TDD red or a `red-proof` run that files a receipt); **green under the gate** (make it pass; the commit-path gate runs the checks, so green is the machine's verdict, not the author's); **refactor** (clean up under green, a separate `refactor:` commit); **disclose** (the process paragraph). The loop never asks whether TDD was followed — it arranges the world so the claim precedes the code in git, the red is a receipt on the board, the green passes a gate that watches the checks, and the rate is a number in the audit report.

**Court selection.** Red-first is *mandatory* for a **detector-class** slice — anything whose job is to catch something (a gate, check, tamper proof, fail-closed property, or discriminating mechanism), because a detector never observed red might catch nothing and a green suite would never tell you. Elsewhere — an IO shell, a report generator — it is *negotiable with disclosure*: declare build-then-verify in the process paragraph and name the verification that stood in for the red bar.

**One shape to keep straight.** In this dev-ledger, a defeated claim leaves the board by a `refutation` `about` it plus a **retirement** — never an in-place edit of the beaten claim — and a `signed` entry that is defeated retires with a pointer rather than being superseded in place: `signed → ∅` is retirement, not supersession. That is a deliberate divergence from the research ledger's shape (where a signed result can be superseded by a better one), stated here so it is never read as drift.

**Squash-merge compatibility.** Precedence is certified pre-merge and carried in-ledger as a verdict line; squash-merge freely — the audit trail is content, not commit topology. Rebase-merge keeps richer per-commit provenance and is preferred where you own the merge policy; a squash is fully supported via pre-merge certificates. Before a squash-merge, the author runs `ledger/audit.py --certify` on the intact branch to emit the certificate (CI verifies read-only; a policy that lets CI commit back can emit it there), and the main-side audit consumes it where the ancestry is gone. The old warning that "squashing destroys the loop's audit trail" is retired — it was true only before the certificate.

**SpotBugs is fail-closed and off the default path (the differential gate, `reference/sdlc-gate.py` — distinct from this ledger commit-path gate).** SpotBugs analyzes Java bytecode, and a source-snapshot differential cannot compile a tree, so it stays deliberately outside default Check A: it raises `SpotBugsOperationalError` when present without bytecode rather than scanning empty and passing. The enabling path is a compiled pilot repo, where FindSecBugs can ride the same SpotBugs engine and give `java-security` a mechanical enforcer.

**The memory/ledger boundary.** A memory is durable *discipline* — the judgment that survives instance turnover. Anything mechanically checkable is a *claim*, not a memory: it registers in the ledger under a named check, and the memory that references it cites the `clm-` id. A recheck recipe stored in a memory is a claim filed in the wrong courthouse — it will rot unwatched, because no gate reads a memory. When you find one, register the claim, annotate the memory with the id, and leave the memory standing. (Guarded mechanically: `audit.py`'s `memory-index` check fails `MEMORY.md` over its hard budget, so the memory layer cannot silently bloat past the point where it is read.)

**The fail-posture taxonomy — closed, quiet, strict, by role.** Three postures, and inverting one is a quiet catastrophe, so they are named. A **blocking control fails closed**: the commit-path gate and the write path deny on any doubt — an unverifiable state is treated as unsafe (mnemosyne D2). An **advisory nudge fails quiet**: a lint whose false alarm would train people to ignore it stays out of the blocking path until it has earned trust — a warn that cries wolf is worse than none (mnemosyne D3; this is why `tdd-precedence` and `red-proof` are warn-grade for a season). A **safety constraint fails strict**: an unparseable constraint reads as *forbidden*, never permissive — the deny-list and the sentinel guard default to the safe answer when they cannot parse (mnemosyne D5). The kit already practices all three; the names keep a future contributor from wiring a blocking check to fail quiet, or a constraint to fail open.

**The auto-park law.** A scheduled or repeatedly-run check that *could not run* N consecutive times (default 3 — a tool absent, a recipe broken, an environment gone) files a claim naming its own brokenness and removes itself from the rotation. A broken detector must become a visible parked obligation on the board, never daily noise that everyone learns to scroll past (the mnemosyne failure: five broken recipes erroring daily for weeks). This is doctrine now; the mechanical lint lands with the kit's first scheduled verifier, not before.

**The record-home rule, at every grain.** The same law that separates a memory from a claim separates a *decision* from its falsifier and a *spec* from its acceptance. An **ADR** lives in `docs/adrs/` as the repo's durable *why* — but its falsification condition does not get to live only in that prose: wherever the condition is mechanically checkable it registers as a ledger claim, and the ADR cites the `clm-` id, because a falsifier living only in prose is a court nobody convenes. An ADR's acceptance-gate verdict — the `deep-reason` attack, a committee ruling — lands as *testimony* about the ADR, and the Status line cites it: receipted, never self-reported. **Stories** are the prose parents of parked claims — the loop's claim-first step is a story's acceptance criteria entering the courthouse, one line each, before any code. Prose carries the reasoning at each grain; the ledger carries what a machine can check; and the citation between them is what keeps the reasoning honest.

## Options — the menu the Tour drives

Every operator-facing knob, one place, four fields each: what it is, its default, when to change it, and where the choice lands (a repo-owned file, a config key, or your own conduct). This is the menu the Tour prompt walks you through. The closing convention makes it durable: **configuration is a claim** — the Tour's final act appends one ledger assertion recording every choice you made, defaults included, `check: none`, so the board shows how this repo is armed and a future session never has to guess.

**Tier.** *What:* who the ledger defends against. *Default:* the single-user (private, local) tier — the only shipped mode; the gate keeps an automated collaborator and your own future carelessness honest, not a hostile local admin. *Change when:* never yet — shared/team mode (server-side signing, provenance-verifiable discharge) is a named roadmap, deferred, not a flag you can flip. *Lands in:* conduct — the single-user boundary is stated in full in the kit's own `SECURITY.md` (the trust model you install under; it is not dropped into your repo).

**`ledger/check.sh`.** *What:* the pinned mechanical check the commit-path gate runs; the sole thing that can sign. *Default:* absent — the gate auto-detects a single toolchain from a **build marker** (`build.sbt`, `pom.xml`/`build.gradle`, `pyproject.toml`/`setup.py`). *Change when:* the repo builds from more than one language, you want to pin the exact command, **or the repo has no build marker at all** — a bare-script repo (e.g. loose `.py` files with no `pyproject.toml`) auto-detects *nothing*, so absent a pinned `check.sh` a code change commits with only the forgery guard and audit and *nothing ever signs*. Pin `check.sh` there. Keep it hermetic — no network, no live services; it runs inside the pre-commit hook. *Lands in:* the repo-owned `ledger/check.sh` (never touched by `--upgrade`).

**`ledger/languages`.** *What:* the file extensions whose staged change fires the check. *Default:* auto-detected from the repo's build markers. *Change when:* a build marker is nested, a language is vendored, or the system builds from several languages and the gate must fire for all of them — because firing for a language `check.sh` does not check lets it weaken unseen. *Lands in:* the repo-owned `ledger/languages`.

**Audit mode.** *What:* how hard the warn-grade checks bite. *Default:* warn-grade — `contested`, `tdd-precedence`, a soft `memory-index`, and a coverage drop warn but do not block; `tdd-precedence` is C1 at development granularity (it subsumes the preregistration check's dev-side half, reading the claim-first commit's precedence). *Change when:* you want the season's warns to fail the run — `audit.py --strict` promotes every warn to a failure. *Lands in:* conduct (how you invoke `audit.py`).

**Memory-index budget.** *What:* the size ceiling on `memories/MEMORY.md`. *Default:* soft 16 KB (WARN), hard 24 KB (a genuine FAIL — a warn-only budget fires into a void). *Change when:* a repo legitimately carries a larger index — raise `LEDGER_MEM_SOFT_KB` / `LEDGER_MEM_HARD_KB`. *Lands in:* config (the env keys).

**Coverage opt-in.** *What:* the differential gate's per-toolchain statement-coverage-drop block. *Default:* off — it instruments and runs the full suite on both trees, so it is heavy. *Change when:* you want a coverage regression versus the merge-base to block — pass `--coverage` on both `baseline` and `diff` (scoverage for Scala, JaCoCo for Java); a failed scan exits 2, fail-closed. *Lands in:* conduct (the `sdlc-gate.py` differential gate, distinct from the ledger commit-path gate).

**`red-proof`.** *What:* the mechanical court for the observed-red disclosure. *Default:* advisory — you run it by hand (or with `--ledger` to file the receipt) and disclose the result; it does not block. *Change when:* a season of receipts has resolved the registered bet — then a repo may promote it to a hard gate for detector-class paths, per its own law: *a norm earns blocking power only after a season of receipts.* *Lands in:* conduct now; the graduation wiring is a commented block in `ledger/check.sh.example`.

**Waivers.** *What:* a sanctioned, mechanically-verified exception to a Check-D assertion-count loss (a real test migration, not a deletion dressed as one). *Default:* none — an assertion-count drop is a hard block. *Change when:* a spec-declared migration genuinely moved assertions to a sibling test; declare it as `--assertion-loss-waiver`, and the gate downgrades the loss to advisory only if the declared delta, the sibling's growth, and the moved predicates' text all check out. A waiver is a visible exception, never a quiet edit. *Lands in:* conduct (the differential gate flag), read from the story's metadata.

**The sweep.** *What:* the librarian's bulk retirement of superseded-but-live claims. *Default:* run deliberately, on its own. *Change when:* the board has accreted superseded entries and needs a cleanup pass — `ledger/librarian --sweep`. Run it as its own act, never bolted onto a landing where its whole-board scope would surprise you, and never piped to `head` (a SIGPIPE truncates the sweep mid-retire). *Lands in:* conduct.

**Escalation.** *What:* when a slice earns a fresh-context `deep-reason` adversary. *Default:* not invoked — most work does not need it. *Change when:* a high-stakes, verdict-shaped slice (a plan attack, a waiver adjudication, a contested claim, a detector-class change) warrants an independent attack whose findings land as `refutation` entries. *When not:* routine PR review — that is the `pr-review` skill; and never as a substitute for a mechanical check that already exists. *Lands in:* conduct.

**Authoring layer (ADRs and stories).** *What:* the design-and-spec grain of the discipline — Architecture Decision Records (`docs/adrs/`, with registered falsifiers) and work stories (`stories/`, whose acceptance criteria become parked claims), plus the four skills that write and score them (`adr-write`, `story-write`, `story-tighten`, `story-intake`). *Default:* **off** — the loop runs without it, and a code-first project need not carry it. *Change when:* the project is design-first, or decisions and specs are worth recording so later work cites them rather than re-deriving them — one word enables it. *Lands in:* the two template directories (`docs/adrs/`, `stories/`) and the four skills; the choice is recorded in the configuration claim like every other.

## Where this goes

This manual is the Enterprise computer's manual in miniature, which is not a metaphor. A taught skill will be a signed claim; the machine will check the board before acting; your authorizations will gate what it may do; the weekly review will be a conversation with a system that can show you exactly what it believes, on what evidence, and what it's still only claiming. You're not practicing for that system; you're operating it at lab scale, and the habits above are the ones that transfer whole. Read before writing, cite before re-checking, claim before building — and once a week, sit with the board and be the judgment it can't automate.

*End — 2026-07-11. Three commands, two phrases, three rituals, five verbs. The ledger remembers everything; this page is how you make it think.*

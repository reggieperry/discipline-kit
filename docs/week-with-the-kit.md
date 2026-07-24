# A week with the kit

A lifecycle walkthrough, day zero through payoff. One operator, one repo — a billing service with a stubborn invoice-reconciler module — adopting the dev-ledger and its commit-path gate.

Nothing here is aspirational. Every command and every mechanic is one the harness already ships; where a step is judgment rather than tooling, it is named as judgment. The operator drives all of it through the kit's README prompts — the kit's interface is the prompt, not a menu — so this walks what those copy-paste prompts set in motion. Read it as the shape of a first week, then keep the parts that fit your cadence.

## Day 0 — install and jurisdiction

The harness installs into a git repo, not a machine. The README's **Install** prompt is the one ceremony — it points the instance at the kit's docs, runs `install-harness.sh --dir . --verify` in a single move, and demands the full verify output back. The installer is idempotent by construction, so a re-run against an already-installed tree is a no-op rather than a second layer, and the **Upgrade** prompt (`install-harness.sh --upgrade`) later refreshes the kit-owned files when a newer kit ships while leaving your repo-owned check and languages untouched.

The install does several things in one pass. It tags the current commit `pre-harness-baseline` for one-move rollback. It drops `ledger/` — the `append` writer, `audit.py`, `gate.py`, `librarian`, `retire`, `board.sh`, `red-proof`, the fixtures, the README, and the operators-manual. It copies the six `ledger-*` skills into `.claude/skills/`, so the next Claude Code session loads the right ledger procedure at the right moment.

It also wires `.githooks/pre-commit` to the gate and installs a `.githooks/post-commit`, then points `core.hooksPath` at `.githooks`. It adds the demotion section to `CLAUDE.md`. And it bootstraps the ledger with a genesis line and a single `unverified` claim — "harness installed per brief and passes its own acceptance" — parked under the check named `harness-verify`.

The store itself is one append-only file, `ledger/claims.jsonl`, one JSON object per line. Each line carries an `id`, a timestamp, a `subject`, the `claim` text, a `source`, a `kind`, an optional `about` pointer, the `check` that could settle it, a `status`, and the supersession fields. The status vocabulary is the whole point in four words: `unverified` (asserted, no check ran), `signed` (a mechanical check discharged it), `refuted` (a check failed it, and it stays on the record), and `retired` (superseded or defeated, moved to `trace/`). Everything below is that vocabulary in motion.

That parked claim is the point of the next step. `./harness-verify.sh` is the installer acting as its own first customer, and it proves three things before it will sign.

First, `ledger/audit.py` exits 0 on the live ledger — the structural invariants hold. Second, hook-is-a-hook: on a scratch branch it appends a forged line with `status: signed` and a fabricated run reference, tries to commit it, and the commit must be *blocked*. A signature with no check behind it is a forgery, and the gate that lets one through is not a gate.

Third, the ledger tooling fixtures pass — retirement is immutability-safe, `red-proof` rejects a tautological test and passes a genuine one, and the precedence and coverage courts run. These are the same fixtures the kit's own CI runs on every push, so the acceptance you watch on Day 0 is the acceptance the kit holds itself to.

Only with all three green does `harness-verify` sign the installed claim and record its line-hash for the forgery guard. The scratch branch and its probe line are discarded; the pre-probe ledger is restored verbatim. If you ever want the tree back the way it was, `git checkout pre-harness-baseline` is the one move, and accumulated ledger contents are archived rather than destroyed.

What the harness governs from here is narrow and total: the commit path over this repo's own development record. The gate — forgery guard, check-discharge, audit — runs on every commit through the git hook.

`gate.py` is byte-identical across every repo that installs the kit; this repo's behavior comes from `ledger/languages` and `ledger/check.sh`, never from editing the gate. That separation is the jurisdiction — the machinery is shared and unforkable, the policy is yours.

The first policy call worth making on Day 0 is which languages fire the check. The gate must fire for every language that builds the system, and `ledger/check.sh` must in turn check every one of them, because firing for a language you do not check lets that language weaken unseen. A single-toolchain repo needs neither file — the gate auto-detects. A billing service with, say, a typed frontend beside the backend declares both extensions in `ledger/languages` and runs both checks in `ledger/check.sh`, so a change on either side meets a real gate rather than a green shrug.

Language coverage is the sharpest Day-0 call, but not the only one. The README's **Tour** prompt — the recommended step right after install — walks every option one at a time (the tier, the pinned check command, the audit's strict-versus-warn modes, the coverage opt-in, red-proof's advisory status) and records your choices, defaults included, as a single configuration claim on the ledger, so a later session reads how the repo is armed rather than guessing. One of those choices opens the next grain.

## The design grain — ADRs and stories

The loop so far runs on claims and code, and a code-first repo can stop there. A design-first repo turns on one more grain — the **authoring layer**, off by default and enabled with the README's **Enable authoring** prompt (a Tour choice). It lands two artifact kinds and the four skills that write and score them, and both kinds feed the same ledger.

An architecture decision is the first. When the reconciler team commits to a strategy — netting before rounding, say, rather than after — that is a verdict-shaped, hard-to-reverse fork, the kind that also earns a `deep-reason` pass. `adr-write` records it against the ADR template: the context, the numbered Decisions with stable ids that are never renumbered, the consequences and the rejected alternatives, and — non-negotiable — the falsification condition, the observable that would show the call wrong. That falsifier does not stay in prose wherever a check can reach it — it registers as a parked ledger claim the ADR cites by `clm-` id, so the day the observable fires the board raises it; where the condition is genuinely unmechanizable, the ADR says so in one line and names what would decide it instead. An ADR is a decision you can be held to precisely because its court is already on the docket.

A story is the second, and it is where the next section's acceptance claims come from. `story-write` drafts the reconciler slice against the story template — portable frontmatter, a problem grounded at `path:line` against HEAD, and acceptance criteria that carry the anti-weakening contract verbatim. `story-tighten` sharpens it until every criterion is one a check can reach. Then each acceptance criterion enters the courthouse as a pre-registered claim, one criterion, one line — which is exactly the claim-first move the next section walks.

A story you did not write arrives the same way through `story-intake`. A ticket pulled from your team's board — over an MCP tracker, or through a thin read-only client Claude Code builds against the board's API — is untrusted until scored, so intake scores it against the same rubric, parks one claim per acceptance criterion with the board id embedded verbatim so a signed `clm-` walks back to the ticket, and sends every gap back as a question rather than a silent guess. Whichever way the story arrives, `docs/stories-with-the-kit.md` walks both paths end to end.

## Claims before code

The habit that pays for everything downstream is writing the claim before the work. When you start a contestable slice — a milestone, an experiment, anything whose "done" someone could argue with — you draft the acceptance claim verbatim first: what will be true, and the exact check that will show it. When the authoring layer is on, that acceptance claim is usually a story's acceptance criterion; without it you write the claim directly, and the discipline from here is identical either way.

You append it through the one schema-validating writer, `echo '{...}' | ledger/append`, which assigns the id and timestamp and validates the shape. It lands `unverified` — the honest "I don't know yet," which read as a column is the entire research program. The `kind` is `assertion`; review output would be `testimony`, and a defect would be a `refutation` about a claim, but a fresh bet is an assertion.

Not everything earns a line. The three-question test gates the append: will anyone rely on this later, is there a mechanical discharge, and would a dispute be expensive? Two yeses and you write it; zero and you leave it out, because a ledger of everything is a diary and the noise costs more than the record. The reconciler's rounding-tolerance behavior clears the test on all three counts, so it earns its claim.

The precedence discipline is mechanical, not moral. That acceptance claim lands as its **own ledger-only commit before any code commit** — a commit that touches `ledger/claims.jsonl` and nothing that builds the system. That commit is git's record that the claim preceded the code, and it is exactly what the `tdd-precedence` audit check reads. Bundle the claim into the code commit and the timestamp is gone; the check warns, and rightly.

So for the reconciler slice the order is fixed: claim the rounding-tolerance behavior, commit the ledger line alone, then start building. Claim, commit, then code.

Before you commit that line, every clause gets checked for dischargeability. A clause that no check can ever settle is a wish, not a bet. If the court for a clause is not built yet, you park the claim under the name of its future check rather than pretending it is already provable, and you supersede it at landing once the check exists. A bet that can't die isn't a bet.

That park-then-supersede pattern leaves a recognizable shape in the record. A pre-registered landing adds ids in sequence — the manual supersede that moves the parked claim onto the real repo check, the gate's own verification-surface signature, and the gate's `signed` successor of the pre-registered claim. An auditor walks that chain rather than trusting the prose summary; a landing that does not show the shape is mis-reported, and the mismatch is a defect to name, not a wrinkle to smooth over.

## The inner loop

Five beats run per slice, and the harness arranges the world so nobody has to be trusted about them.

**Claim** — the acceptance claim first, as its own ledger-only commit, per the section above. **Red receipt** — you observe the test fail, either by natural TDD red or by a `ledger/red-proof` run that files the failure as a receipt on the board. **Green under the gate** — you make it pass, and the commit-path gate runs the checks, so green is the machine's verdict rather than the author's word. **Refactor** — you clean up under green, as a separate `refactor:` commit. **Disclose** — you write the process paragraph.

That process paragraph is four sentences per slice, and it is what makes the loop auditable rather than merely followed: were the tests written before, alongside, or after the code; which new tests were observed red and by what route; was any assertion adjusted after seeing actual output — the green-by-weakening disclosure, legitimate but owed a sentence; and was the refactor pass done or skipped. "I ran it and the tests passed" is an outcome, not a process.

The process paragraph is one of four disclosure conventions, and the other three are worth carrying in the same breath. The semantics line states what a verify-family signature actually certifies — a receipt reproduced, two legs agreeing, a check passing — and points at the leg that would carry correctness beyond that, because a signature means only as much as the weakest provenance in its chain. The authorship note discloses the true authoring order in one sentence: written fresh, adapted from a template, or produced by a prior session. And the reliability boundary flags where an account is memory rather than commit-anchored record, so a retrospective across a compaction seam is read as testimony, not fact.

The one rule that is not negotiable governs court selection. Red-first is *mandatory* for a **detector-class** slice — anything whose job is to catch something: a gate, a check, a tamper proof, a fail-closed property, a discriminating mechanism. A detector that was never observed red might catch nothing at all, and a green suite would never tell you, because a detector that fires on nothing is indistinguishable from a passing one.

When the reconciler slice adds a guard that must reject a mismatched total, that guard is detector-class, so you watch it go red against the old code first. `ledger/red-proof --test-cmd '<runs the new tests>'` builds a hybrid tree with the implementation at the merge-base and the tests from HEAD, and asserts the new tests *fail* against the old implementation — killing the tautology and the green-by-weakening in one move. The receipt lands on the board as the mechanical court for the "observed red" disclosure.

Elsewhere the bar is negotiable with disclosure. An IO shell, a report generator, a thin adapter — build-then-verify is legitimate, but you declare it in the process paragraph and name the verification that stood in for the red bar. The loop never asks whether TDD was followed. It arranges the world so the claim precedes the code in git, the red is a receipt on the board, the green passes a gate that watches the checks, and the rate is a number in the audit report.

## The red fork

Sooner or later the gate refuses a commit. This is the machinery working, not failing.

A blocking control fails closed: the commit-path gate denies on any doubt, because an unverifiable state is treated as unsafe. The check ran and the claim did not clear — the reconciler's tolerance guard rejected a total the test said it should accept, or coverage dropped past the floor — and the commit does not land. The claim stays on the board as the open obligation it is, unsigned, because no mechanical check discharged it.

The README's **When a commit blocks** prompt is the prompt for exactly this moment: show the refuted claim and the check output verbatim, then walk the honest moves before touching anything. There are exactly three of them, and naming them is most of the discipline.

Fix the code — the common case, where the claim was right and the implementation was not. Fix the test if the expectation itself was wrong, and disclose it — adjusting an assertion after seeing actual output is legitimate, but it is the green-by-weakening disclosure and it is owed a sentence in the process paragraph, so a later reader knows the goalpost moved and why. Or park the claim, if the honest problem is that the check to settle it is not built yet: supersede the claim into a parked state that names its future court, so it is waiting rather than rotting.

What you do not do is reach for the fourth move — asking an instance to "just mark it signed." A signature without its check is the forgery the install-day probe proved the gate blocks, and the instance will refuse, which is correct and should stay correct.

The fail posture generalizes, and it has names worth keeping straight. A blocking control fails closed. An advisory nudge fails quiet — a lint whose false alarm would train people to ignore it stays out of the blocking path until it has earned trust, which is why `tdd-precedence` and `red-proof` are warn-grade for a season. A safety constraint fails strict — an unparseable constraint reads as forbidden, never permissive. Inverting any one of the three is a quiet catastrophe, so a future contributor should never wire a blocking check to fail quiet.

There is a matching rule for a check that stops being able to run at all. A scheduled or repeatedly-run check that could not run several times in a row — a tool absent, a recipe broken, an environment gone — files a claim naming its own brokenness and removes itself from the rotation. A broken detector must become a visible parked obligation on the board, never daily noise that everyone learns to scroll past. A red fork you can see is the machinery working; a detector silently erroring in the corner is the machinery lying.

## The librarian

The record is append-only, and the whole retirement story follows from that. You never edit a line, including your own typos and your own beliefs. A changed finding is a *new* entry whose `supersedes` names the old one, and the old line stays exactly as written. Editing a line to match new understanding erases the fact that the understanding changed, which is often the most useful thing on the board.

When a claim is defeated rather than merely refined, it leaves the live board by retirement. `ledger/retire <id> <reason> <refuting-id>` does a verbatim-move plus sidecar: `ledger/trace/<id>.jsonl` receives the original claim line byte-identical, plus a separate retirement record carrying the `trace_reason` and a pointer to the refuting id.

The committed line survives unchanged, so the immutability audit still holds. And because the move rewrites nothing, a claim may now be retired safely in *any* later commit — the old same-commit-only constraint, which forced boards to accrete superseded entries forever, is lifted. `ledger/librarian` does this sweep for superseded claims and reports the contested ones. The live file never carries a claim whose defeat is on the record, and the graveyard entry always points at what defeated it.

Recovery is allowed — a traced entry can return via a new entry that cites it — but the traced original is immutable. You do not resurrect by editing; you resurrect by citing.

The librarian is worth running as part of the weekly ten minutes rather than only at a crisis. A contested claim it surfaces is a decision waiting for you; a superseded one it sweeps keeps the live board readable. A board that only grows is a board people stop reading, and a board people stop reading cannot do any of the four jobs it exists to do.

One demotion rule sits underneath all of this: generative review testifies, never signs. Two generative confirmers share their blind spots, so review output — a PR review, a deep-reason pass, a workflow verification — lands as `testimony` and moves nothing to `signed`. A reviewer who finds a defect appends a `refutation`. Only a mechanical check with a real run reference signs.

`signed` is terminal, and this is the one place the dev-ledger deliberately diverges from a research ledger. A signed claim is never superseded in place; the audit's transition table maps it to the empty set. If a signed result later proves premature but not wrong, a fuller restatement is a new, independent claim and the original stands. A signed line is defeated only by a `refutation` about it and then retired — `signed → ∅` is retirement, not supersession. Stated here so it is never read as drift.

## The session rhythm

Two phrases put the machinery to work, and you say them early — a board check after design has started is a seatbelt fastened mid-crash.

Open every session with **"check the board first."** Thirty seconds against `ledger/board.sh open` answers two questions: does anything open bear on today's work, and did anything land since you last looked that today's work should *cite* rather than redo. Start every new effort with **"write the claim before the work."** The README's **Orient** and **Work** prompts put both prompts in copy-paste form; everything else is elaboration.

Once a week, calendared, you spend ten minutes as the judgment the machine cannot automate. Run `ledger/board.sh open`, `ledger/board.sh stale 30`, and `ledger/board.sh checks`.

For every stale item, ask exactly one question — discharge it, park it properly, or retire it honestly? — and give the instance the verdict. Discharge means the check exists and should just run. Park means the claim is real but its court is not built; make sure it names its future check. Retire means you no longer believe it enough to keep it on the books.

A stale item with no verdict is the one failure mode the machinery cannot fix, because it is a judgment call, and judgment is your column. The instances can surface the item, walk its chain, and act on your call, but the call itself is the part that does not automate, and it is the part the whole apparatus exists to protect your attention for.

Read the numbers as trends, not snapshots. An open count rising month over month means commitments are outpacing discharge — either you are minting claims too casually or you are short a check. Stale items clustering on one topic mean the institution is avoiding something; name it at the review. The checks histogram tells you which verifier earns its keep: a check cited thirty times is a crown jewel worth hardening, a check used once may have been ceremony.

Five verbs route through you and only you. Authorize loggably — give an out-of-band authorization in one sentence that can be recorded verbatim, with principal, channel, and date, because a misread pronoun once cost a false accusation and a retraction. Place the bets — every prediction gets a court and a date it could lose in. Sign off what becomes belief — dissent enters freely, but a succession or a resolved contest becoming *institutional belief* passes through you.

The last two are ceilings and gates. Set the ceilings — budgets and thresholds as numbers with a checkpoint rule, which the instances then honor mechanically. Release the gates — a pre-registered cell waits on your word, and the discipline is that nothing runs before it. The instances write, discharge, and verify; these five acts are yours, and doing them crisply is most of what maximum effect means at the operator level.

One boundary keeps the two stores honest: a memory is durable *discipline*, the judgment that survives instance turnover, while anything mechanically checkable is a *claim* filed under a named check. A recheck recipe stored in a memory is a claim in the wrong courthouse — it will rot unwatched, because no gate reads a memory. When you find one, register the claim and cite its id from the memory.

A short list of ways to lose is worth keeping in view, because each one inverts a habit above. Never edit a line, including your own typos — supersede, or the immutability drill flags you as the tamperer you technically were. Never ask an instance to mark something signed. Never let a report float free of ids, because a document that cites no claims cannot be checked against the record. Never write diary entries — the three-question test applies to you too. And never skip the pushed glance when you were the one at the keyboard: a milestone that has not left the machine is drafted, not done.

## The kernel moment — the payoff

The ledger stops being overhead the first time it pays a bill you would otherwise have paid twice. Two shapes, and you feel both inside the first week.

The first is a citation in place of a re-check. Verification cost falls toward zero when a signature is spent instead of re-earned. Midweek someone needs to know the reconciler's rounding behavior is settled before building the export on top of it. Instead of re-running the suite, `ledger/board.sh find rounding` surfaces the signed claim, and you cite the `clm-` id and move on — the signature is the receipt.

Citation and audit are different moves, and the difference matters here. Citation spends a signature *within* a workflow: you trust the receipt and skip the re-check. An audit of a *report* still recomputes, because a report is a claim about the record and the auditor's stance is to check it, not cite it — `ledger/audit.py --report` run against a clean checkout, arithmetic recomputed rather than read. A month of citation turns the signed column into capital, and the checks histogram tells you which signatures are crown jewels worth hardening because they get spent over and over.

The second is a graveyard hit that ends an argument before it starts. Before commissioning anything, you ask "have we been here?" — a `find` on the topic plus a glance at `ledger/board.sh graveyard`, the standing do-not-rebuild list. When a proposal to rewrite the retry-backoff path surfaces its own refutation from three months back, the design conversation is over for the price of a grep: you cite the corpse, or you state explicitly what is different this time.

The graveyard is also the best onboarding document you have. Knowing what is false and *why* transfers judgment faster than any tour of what is true, so a new collaborator — human or instance — reads the refutations first. A prior refutation ends a design conversation; a prior signature converts a task from "establish X" to "build on the id."

None of this is threatened by how you merge. Precedence is certified pre-merge and carried in-ledger as a verdict line, so you squash-merge freely — the audit trail is content, not commit topology, and `ledger/audit.py --certify` emits the certificate on the intact branch before the ancestry is collapsed.

That is the compounding. Every signed claim is a re-check you never run again; every refutation is a road nobody walks twice; every pre-registered bet is honesty about a result before its outcome can flatter it. The board does not merely remember the week — it makes the next week cheaper, and the discipline is that the machine keeps the receipts so you can spend your ten minutes being the judgment it cannot.

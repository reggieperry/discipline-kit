---
name: adversarial-review
description: >-
  Load for a high-stakes adversarial review before or around a PR — "adversarial review", "attack this diff", "review before I open the PR", "red-team this change", "review this teammate's PR hard". Fans out fresh-context adversaries decorrelated by role (logic-and-state, abuse-and-boundaries), each under the deep-reason findings contract, and routes findings by mode: pre-pr | own-pr | foreign-pr. The tier-two review that sits above the mechanical every-PR pr-review.
auto_invoke: false
---

# /adversarial-review — N fresh-context adversaries against one diff

The `ledger-verify` doctrine — *escalation is an adversary, not a committee* — generalized from one attacker to N. Where `deep-reason` is a single fresh-context Opus adversary against a claim, this skill fans several out against a diff, each on the deep-reason pattern and under its findings contract, decorrelated **by role**. It sits one tier above `pr-review`: `pr-review` is the mechanical, every-PR read; this is the deliberate red-team reserved for the changes that earn it.

Three modes, named at invocation:

- **`pre-pr`** — attack `merge-base..working-tree` before any PR exists. Findings land in the tree, not on a record.
- **`own-pr`** — attack a PR you authored, after it is open.
- **`foreign-pr`** — attack a teammate's PR hard, producing a review artifact, not a ledger write.

## How it runs

1. **Scope the diff by mode.** `pre-pr` reads `git diff $(git merge-base HEAD <base>)..` on the working tree; `own-pr` and `foreign-pr` read `gh pr diff <N>` with `gh pr view <N> --json headRefName,baseRefName,title,body` for the base. Read the whole change set, and its base, before assigning any attack — a finding is relative to the base.
2. **Assemble the briefs.** One brief per adversary, each a filled `deep-reason` 6-section prompt: the goal sentence names the role's hunt, the environment lists the diff and the base, the discipline restates the findings contract. Default two roles (logic-and-state, abuse-and-boundaries); add roles by stakes.
3. **Launch and record the manifest.** Fire the adversaries — different model families where the harness allows — and record what was launched. This manifest is what the reconciliation checks against; a launch with no recorded expectation cannot be found missing.
4. **Reconcile launches against completions.** N launched, N verdicts or N explicit failures. A crash, a schema refusal, or a timeout is a failed run that blocks the verdict — resolve it before synthesizing (`feedback_reviewer_harness_fail_closed`).
5. **Merge and dedupe by lineage.** Collect the findings, drop the duplicates two adversaries both caught to one, and keep each surviving finding's evidence, repro, and disposing check intact.
6. **Render and route.** Emit through the adapter the environment supports, and route the findings by mode. Both are detailed below.

## The adversaries — decorrelated by role, not by sampling

Two brief templates ship by default, and the decorrelation is the **assignment**, not the temperature:

1. **Logic and state.** Does the code do what its claims say? Walk the state machine, the invariants, the fold, the ordering, the error paths. Hunt the divergence between the docstring's promise and the code's behavior.
2. **Abuse and boundaries.** What can an attacker or a malformed input make it do? Unbounded sizes, injection into a prompt or a query, error detail leaking outward, a destructive op with no refusal, a boundary the code trusts an upstream contract to hold.

N is configurable (1..N) — a detector-class slice may warrant a third role for the check's own fail-open surface. Prefer a **different model family** per adversary where the harness allows it; where it does not, the report header states the shared-lineage caveat so the reader grades the agreement correctly (the E2 disclosure, per `deep-reason`).

Each adversary runs the **findings contract** verbatim from `deep-reason`: every finding ships the raw quoted command and its output lines (never a summarized count), a paste-and-rerun repro, and the named mechanical check that would dispose it. A finding no check can dispose is labeled **pure interpretation**, not a defect.

## Agreement carries no weight (the E3 rules, encoded)

- **A clean pass is two absence reports, never an approval.** Each adversary that finds nothing reports the **attack surface it searched, with its queries quoted** — not "looks good." An absence report is one lineage under the agreement discount; two of them are not a second signature (`ledger-verify`, Axiom E3).
- **Dedupe by lineage.** Both adversaries catching the same bug is **one** finding, not two — merge them and count the lineage once. Corroboration is not confirmation.
- **A dead adversary is a loud could-not-run.** The launcher reconciles launches against completions: N launched, N verdicts or N explicit failures, no third state. A schema refusal, a crash, or a timeout marks the **run** failed and blocks the verdict until rerun or explicitly waived with the gap named — never a silently thinner review that reads as complete (`feedback_reviewer_harness_fail_closed`).
- **The harness fans out attacks and never votes.** Adversaries propose; mechanisms dispose. No adversary's verdict — and no headcount of them — signs anything. A finding is real when its disposing check goes red, not when two agents agree it is.

## Findings grammar, rendering adapters, degradation tiers

Every review opens with a **verdict-first overview** — the disposition and the count of surviving, deduped findings — then one block per finding:

- **`file:line` anchor** into the diff under review.
- **Quoted evidence** — the lines that carry the defect, read and quoted, never cited from memory.
- **Repro** — paste-and-rerun.
- **Disposing check** — the named mechanical check that turns red on the defect.
- **Severity** — blocking (correctness, security, a gate regression), should-fix, or nit.

One block, filled:

```
[blocking] logic-and-state · src/ledger/fold.scala:118
  A double Withdrawn on one token cancels via the involutive refute and
  resurrects the struck value — the fold signs a withdrawn figure.
  evidence:
    118  case Withdrawn(id) => acc.refute(id)   // refute is its own inverse
  repro: sbt "testOnly *FoldSemanticsSuite -- --tests=double-withdraw"
  disposing check: FoldSemanticsSuite "double Withdrawn stays struck"  (does not exist yet — authored red by this finding)
```

The disposing-check line is what separates a finding from a note: a finding names the red it turns, and a finding with no such red names the test it obligates.

**Rendering is an adapter, not the review.** The same findings render two ways:

- **Platform review comments** — inline threads via the platform review API (a GitHub PR API, the tracker's thread API) — where credentials and a background workflow exist. This is a documented capability tier, not a hidden fragility.
- **A paste-ready markdown review artifact** — everywhere else. A degraded environment gets the *same* review with manual placement, never silently less. The tier is stated in the report header so the reader knows which surface produced it.

**Ledger routing follows the mode:**

- `pre-pr` and `own-pr` — findings append as `kind: refutation` entries `about` the slice's claim id (`ledger-write`; refutations never sign, so the schema fits). An absence report lands as testimony, explicitly not an approval.
- `foreign-pr` — **no foreign ledger write.** You do not hold the record for a teammate's slice. The **artifact is the record**, and it is receipts-per-finding — the quoted evidence, repro, and disposing check on every line — that makes an AI review of someone else's code land as **evidence, not opinion**.

## The pre-PR mode's two properties (doctrine)

**(a) Findings arrive before the record does.** A refutation caught at `merge-base..working-tree` is fixed in the tree and discharges clean in the same slice — no public PR ever carries a review-caught defect, because the attack ran before the PR existed. This is the whole reason `pre-pr` is the default posture for a slice you control.

**(b) It completes the court ladder.** Each court catches a distinct class:

- the **gate** catches what the checks already encode;
- **red-proof** catches a test that does not actually detect its target;
- the **differential gate** catches verification weakened versus the merge-base;
- the **adversaries** catch what no check encodes *yet*.

That last court has a rule: **a finding whose disposing check does not exist is a new test, authored by the attack, red-first — the adversary writes the red.** The attack that found the hole also writes the failing test that proves it, so the next regression is caught by a mechanism instead of a re-run of the same attack. A defect with no disposing check is not closed; it is a test waiting to be written.

## Invocation doctrine

- **Tier by stakes, for all three modes.** Reach for this when the slice is **detector-class** (a gate, a check, a fail-closed property, a discriminating mechanism), touches a **sensitive file** (auth, capital, migrations, the signing path), lands a **contested claim**, or carries **hairy state** (a fold, an ordering invariant, concurrent writers). These are the changes where what-no-check-encodes-yet is where the bug lives.
- **Tier one stays every-PR.** The mechanical `pr-review` runs on every PR regardless — do not route a routine change here. Ritualizing the red-team dulls it; a harness fired on trivia stops finding the thing it exists to find.
- **Never a substitute for a mechanical check that exists.** If a check would dispose the question, run the check. The adversaries hunt the surface the checks do not cover, not the surface they do.

## Anti-patterns (refuse on sight)

- Decorrelating by temperature or seed instead of by role — same blind spot, twice, counted as two.
- Reporting a clean pass as an approval or a "LGTM" — it is an absence report with quoted queries or it is nothing.
- Proceeding to a verdict with an adversary that did not complete — reconcile launches against completions first (`feedback_reviewer_harness_fail_closed`).
- Writing a `foreign-pr` finding into a ledger you do not own — the artifact is the record.
- Closing a `pre-pr` finding without its red-first test — the attack that found it writes the check that keeps it found.
- Firing the skill on a routine diff `pr-review` already covers — spend the tier where the stakes are.

Cross-references: `deep-reason` (the single-adversary pattern and the findings contract this inherits), `pr-review` (the mechanical tier below), `ledger-verify` (escalation-is-an-adversary and the agreement discount), `ledger-write` (the refutation-append discipline), and the `feedback_reviewer_harness_fail_closed` memory (a dead lens is a dropped finding, not a quiet pass).

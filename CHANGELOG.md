# Changelog

Notable changes to the discipline kit. Versions follow [semantic versioning](https://semver.org); the format follows [Keep a Changelog](https://keepachangelog.com). This file supersedes the former `PACK_SOURCE_TAG`, folding its upstream-source provenance into the **Sources** section under each release.

## Unreleased

- **Sender-repo attestation (shared-tier roadmap).** Where cryptographic provenance is wanted, the sender's CI — on a green `harness-verify` — emits a keyless GitHub artifact attestation ("harness verified green at `<sha>`, kit `<VERSION>`", via the workflow's OIDC identity); the PR body links it, and the receiver's inbound workflow verifies it in one call. Bounded guarantee, stated so it never reads stronger: this proves a repo whose CI vouches for a green harness sent the contribution — it does not and cannot prove what kind of author wrote it, which is unprovable in principle and, under this constitution, unnecessary. Verify the claims, never the badge (memory `verify-claims-not-badges`).

## v1.5.0 — 2026-07-15

Inbound machinery for any adopting repo — the kit's own repo is the first customer. Organizing rule: inbound is claim-algebra traffic. A bug report is an attempted refutation of a claim, a feature request is an externally authored story, a foreign PR is a testimony-grade contribution. On a private, solo, local repo the machinery is inert and the Options section says so.

### Added
- **The inbound signed-line guard (detector-class, red-first).** `harness/ledger/inbound_guard.py` reads a diff and rejects any *added* signed ledger line — the forgery guard in `gate.py` is hook-local, and a fork PR is a commit path with no hook. `harness/templates/inbound-guard.yml` is the `pull_request` workflow, **scoped to fork PRs** (`head.repo.fork`), so the maintainer's own gate-signed same-repo PRs are exempt; the kit's `.github/workflows/inbound-guard.yml` is the filled instance. Message: *"signatures are minted only by this repo's gate; contribute the claim, not the verdict."* Red-first fixture `inbound_guard_test.py`.
- **The kit-interchange block + parser (detector-class, red-first).** `harness/ledger/interchange.py` parses a `kit-interchange: v1` PR/issue body block (sender, claim, disposing check, red line, `harness-verify` hash) and, under `--verify`, re-runs the disposing check to grade — DISCHARGEABLE / RECEIPT-FAILED / MALFORMED. **The block authenticates nothing; it makes contributions dischargeable** — a forged block whose check passes is still DISCHARGEABLE (verify the claims, never the badge). Red-first fixture `interchange_test.py` (valid / receipt-failing / forged-passing / malformed).
- **Receipt-demanding issue templates** (`harness/templates/.github-issue-templates/` + the kit's own `.github/ISSUE_TEMPLATE/`): the bug template asks for the `ledger/VERSION` receipt, the verification output, and the failing command verbatim; the feature template asks for the outcome and what would be accepted as done.
- **Triage doctrine** (operators-manual), an **Inbound Options choice-point** (default relevant only above the private-solo tier), **`CONTRIBUTING.md`** (external PRs welcome as testimony; the maintainer wraps them in the claim and the gate signs after merge; no contributor runs the full loop), the **`SECURITY.md`** private-disclosure line strengthened (the kit enables private vulnerability reporting), and `story-intake` gaining a public issue as a second board source. Two memories: `inbound-is-claim-traffic`, `verify-claims-not-badges`.

## v1.4.1 — 2026-07-15

The adversarial-review harness — one skill, three modes, N attackers that hunt and never vote. E3 poisons confirmation, not refutation-hunting: the harness fans attacks out and disposes them with mechanisms, never a headcount.

### Added
- **`adversarial-review` skill** (`claude-user/skills/`, a tier-two sibling of `deep-reason` and `pr-review`), modes `pre-pr` / `own-pr` / `foreign-pr`. Fresh-context agents on the deep-reason pattern under its findings contract; **default two adversaries decorrelated by role** (logic-and-state, abuse-and-boundaries), 1..N, cross-family with lineage disclosure. The E3 rules encoded — agreements weightless (a clean pass is two absence reports with quoted queries), dedupe by lineage, a dead adversary is a loud could-not-run (`feedback_reviewer_harness_fail_closed`), the harness fans out and never votes. Findings grammar (verdict-first, then `file:line` / quoted evidence / repro / disposing check / severity) with a platform-comment-or-markdown rendering adapter and documented degradation tiers; ledger routing by mode (`pre-pr`/`own-pr` → `refutation` about the slice's claims, `foreign-pr` writes no foreign ledger — the artifact is the record). The pre-PR court-ladder doctrine: a finding whose disposing check does not exist is a new test the attack authors, red-first.
- The `ledger-verify` "escalation is an adversary, not a committee" section **amended** from a single `deep-reason` attack to "one to N role-partitioned adversaries under the union-never-votes rules" — the singular was the anti-committee point, and the N-form honors it. README component table and "Using it" list updated. One memory: `adversaries-hunt-never-vote`.

### Tested (item 60)
- The harness run end to end on a toy `pre-pr` diff with two seeded defects, a shared plant, and a clean file: the logic-and-state adversary found the idempotency defect (and deferred the injection to the sibling), abuse-and-boundaries found the SQL injection, both caught the destructive-op plant which **deduped to one finding** (two lineages), the clean file yielded **absence reports with quoted queries** (not "LGTM"), the deduped finding routed as a `kind: refutation` about the parked slice claim, launches reconciled against completions (2 = 2, no dead lens), and every finding named a red-first authored check where none existed.

## v1.4.0 — 2026-07-15

The authoring layer — an optional, default-off layer that carries the discipline up to decision and spec grain. An ADR's falsifier and a story's acceptance criteria are the prose parents of registered ledger claims; the record-home rule (a falsifier living only in prose is a court nobody convenes) applies at every grain.

### Added
- **ADR and story templates** — `harness/templates/ADR-template.md` (fixed section order: Context, numbered Decisions, Consequences, Alternatives, a non-negotiable Falsification condition, Cross-references; stable never-renumbered ids; a Status line that cites the acceptance-gate verdict as testimony; per-Decision superseded-in-part-with-retains, never delete) with a `docs/adrs/README.md` registry; and `harness/templates/story-template.md` (portable frontmatter `id`/`title`/`deps`/`labels`/`sensitive_files`/`status`; six body sections; the problem grounded against HEAD at `path:line`; the anti-weakening contract carried verbatim in the acceptance criteria) with a `stories/README.md`.
- **Four authoring skills** (`harness/skills/`): `adr-write` (the pre-draft `deep-reason` gate whose verdict lands as Status-line testimony, the falsifier registered as a ledger claim, status flips gated on named artifacts, per-Decision supersession), `story-write` (the six sections, problem at HEAD, anti-weakening verbatim, a detector story declares its red), `story-tighten` (the six-dimension 0/1/2 readiness rubric, dispatch at 10+, the SSD rule — split on file-ownership and dependency seams, never conceptual boundaries, each child independently 10+), and `story-intake` (an incoming board story is untrusted until scored; one parked claim per acceptance criterion recording the board id; gaps surfaced as questions, never silent repairs).
- **The record-home rule and grain statement** in the operators-manual, and an **Options choice-point** for the authoring layer (default off, one word to enable). One memory: `specs-are-claim-parents`.

### Tested (item 55)
- Two fresh-instance acceptance runs, unaided: `adr-write` on a toy decision produced a gated ADR (Status citing testimony, falsifier registered and cited, six sections, a real Decision, audit 9/9); `story-intake` on a deliberately loose pasted story scored it 3/12, raised seven gap questions, parked a claim per criterion with the board id, and made no silent repairs. Both earned their keep — they caught two skill ambiguities (the vague-band vs park-each-criterion reconciliation, and the ADR acceptance testimony's `about` target), fixed in the same release.

### Note
- The `memory-index` check fired for real this release — adding the `specs-are-claim-parents` memory pushed `MEMORY.md` to 16.2 KB, over the soft budget; the index was pruned back to one terse line per memory (15.4 KB). The guard working as designed.

## v1.3.5 — 2026-07-15

The three defects the v1.3.4 front-door acceptance caught, fixed. The acceptance test refuted its own docs — the loop working on documentation — and this closes what it found.

### Fixed
- **Install-completeness (finding 2, detector-class).** The installed operators-manual, the `ledger-write` skill, and the ledger README reference `report-conventions.md` and `check.sh.example`, but the installer never vendored them — a fresh instance working from the installed repo alone could not find the conventions it was pointed at. `install-harness.sh` now copies both into the target's `ledger/`, and the four references point at the installed `ledger/` path. Red-first fixture `install_completeness_test.py` (a fresh install must leave both docs present).
- **The bare-script fail-open gloss (finding 1).** The operators-manual check.sh entry and the ledger README overstated auto-detection: a repo with source files but **no build marker** (loose scripts, no `pyproject.toml`) auto-detects *no* check, so a code change commits with only the forgery guard and audit and nothing ever signs. Both now say so and direct you to pin `ledger/check.sh`.
- **The dangling `SECURITY.md` reference (finding 3).** The Options "Tier" entry said the boundary "lands in `SECURITY.md`," but the installer does not drop `SECURITY.md` into the target. Reworded to reference the kit's own `SECURITY.md` (the trust model you install under), which does not dangle.

### Sources
- The §14.49 front-door acceptance run (2026-07-15): the fresh-instance Tour + Work test whose findings these three fixes close.

## v1.3.4 — 2026-07-15

The conversational front door. The kit's operator is Claude Code and its interface is the utterance, so the entry path is a first-class, tested artifact — not folklore.

### Added
- **README "Quick start — say this to Claude Code" (item 47)** — six verbatim, paste-ready prompts (Install, Orient, Work, When-a-commit-blocks, Upgrade, Tour), each read-first, receipt-demanding, and dual-audience. The two-stage model is stated plainly: the Install prompt is the only ceremony; after it the injected `CLAUDE.md` section and the auto-loaded `ledger-*` skills make the discipline ambient.
- **`install.md`** — a concise, accurate install guide (prerequisites, the idempotent installer, the correct `harness-verify` invocation, the tier, upgrade, rollback), so the Install prompt's doc triad (`README` / `install.md` / `SECURITY.md`) is real.
- **`docs/week-with-the-kit.md` (item 48)** — the day-zero-through-payoff lifecycle walkthrough (install and jurisdiction, claims before code, the inner loop, the red fork, the librarian, the session rhythm, the kernel moment), linked from the README as the second thing a curious reader opens.
- **The operators-manual "Options" section (item 50)** — every operator-facing knob with four fields each (what / default / when to change / where it lands): tier, `ledger/check.sh`, `ledger/languages`, audit warn-vs-`--strict`, the memory-index budget, the coverage opt-in, red-proof's advisory status, waivers, the sweep, and deep-reason escalation. Closing convention: **configuration is a claim** — the Tour's final act appends one `check: none` assertion recording every choice, defaults included.
- Two one-fact memories: `config-is-a-claim` and `prompts-are-the-api`.

### Tested (item 49) — the front door is itself acceptance-tested
- A fresh Claude Code instance in a clean scratch repo, given **only the Install prompt verbatim** with no further guidance, reached a **green `harness-verify`** (audit exit 0; forgery probe blocked; fixtures pass), signed the installed claim, and stamped `VERSION`. The kernel-moment test applied to the documentation.
- The test earned its keep: it **caught a real defect** in the just-written `install.md` — it instructed a bare `./harness-verify.sh`, but the installer never copies that script into the target (running it from the kit dir would silently verify the *kit's* ledger). Filed as a refutation (clm-0068), fixed (the documented invocation is now `install-harness.sh --dir . --verify`, or `cd <target> && <kit>/harness-verify.sh`), and re-verified green.

### Sources
- The agentic-TDD-loop build brief's §14 amendment (the conversational front door, 2026-07-14).

## v1.3.3 — 2026-07-15

The mnemosyne learnings. One-sentence diagnosis of the ancestor: it was detectors without a constitution — its measured failures (a contrary flag firing 33 days unresolved, five broken recipes erroring daily, an index that silently truncated past its own budget guard) are all the missing transitions-and-obligations layer, and its measured value (recall of durable discipline) is the layer the kit's memories already carry. This release ports the transitions the kit was missing.

### Added
- **The MEMORY.md index-size check with teeth (item 41).** `audit.py` gains `memory-index`: `memories/MEMORY.md` over a soft budget (16 KB) WARNs, over a hard budget (24 KB) is a genuine FAIL — because a warn-only budget fires into a void (the ancestor's index truncated at 38 KB past a working 24 KB guard). Config-keyed (`LEDGER_MEM_SOFT_KB` / `LEDGER_MEM_HARD_KB`); an absent index is a no-op. Red-first fixture `memory_index_test.py` (oversized FAILs where the shipped audit passed; soft WARNs and strict-fails; small is clean).
- **The memory/ledger boundary law (item 40)** — a memory carries durable discipline; a mechanically checkable assertion is a ledger claim with a named check, and the memory cites its `clm-` id (a recheck recipe in a memory is a claim in the wrong courthouse). One line in the `MEMORY.md` header and one in the operators-manual; on detection, register the claim, annotate the memory, never delete.
- **The fail-posture taxonomy (item 42)** — an operators-manual paragraph naming the three postures by role: a blocking control fails **closed**, an advisory nudge fails **quiet**, a safety constraint fails **strict**. The kit already practices all three; the names keep a contributor from inverting one.
- **The auto-park law (item 43)** — doctrine line: a scheduled or repeated check that could-not-run N (default 3) consecutive times files a claim naming its own brokenness and exits the rotation, so a broken detector is a visible parked obligation, not daily noise. The mechanical lint lands with the kit's first scheduled verifier, not before.
- **Recall telemetry via disclosure (item 44)** — `report-conventions.md`'s process paragraph gains an optional "memories consulted:" line, the recall numerator a memory layer otherwise never has, feeding the prune signal at the cost of a sentence.
- Two one-fact memories: `memory-ledger-boundary` and `fail-posture-taxonomy`.

### Candidates (not built)
- **SessionStart board-manifest (item 45)** — port the ancestor's M-SUMMARY pattern (computed independently, prepended, engineered to survive every loader failure) as an optional hook rendering the board's weakness-first summary (contested and needs-docket before signed counts) at session start. Per the ancestor's own D6 method, this ships only behind a season of item-44 recall telemetry showing session-start staleness actually bites — until then it is a named candidate, nothing more.

### Sources
- The mnemosyne postmortem (usefulness report) and its DECISIONS.md, 2026-05-30 → 2026-07-15, reconciled against the kit.

## v1.3.2 — 2026-07-15

Truth in labeling: no rule reads stronger than its gate, and no residue lives only in a report. Docs and ledger, no code — the §11.33–34 chain-aware counters this amendment set was written against already shipped in v1.3.1 (the clm-0030 fix).

### Added
- **Enforcement-grade labels on the five per-language security rules (§12.37).** Each states at the top whether the gate mechanically polices it: `python-security` names `bandit` as its wired enforcer (the only one of five with a scanner — it rides Check A, findings diff, `#nosec` policed); `go-security` (gosec), `ts-security` (`eslint-plugin-security`/`semgrep`), and `java-security` (FindSecBugs on the SpotBugs engine, pending a compiled pilot) state "review and convention until the toolchain is wired"; `scala-security` states the honest hard case — the wired Scala scanners (scalafix, WartRemover) are purity tools and no native `bandit`-equivalent exists.
- **A "Security-scanner parity" roadmap** in the README rule section (§12.38): the per-language wiring path, each detector-class when it lands, with the standing rule that the wiring commit deletes that rule's enforcement-grade disclaimer in the same diff — the label and the gate move together or not at all. The wirings are future slices, not this release.
- **Residue homes so findings outlive the done-report (§11.35).** The Scala toolchain's latent `forAllNoShrink` fail-open (emit-only-when-present, unlike Java's always-emit `shrinkingOff`) is filed as a tracked kit ledger claim under a check naming its future fixture, rather than living only in a report (the glut-laundering incident's shape). A standing doc line in the README and the operators-manual records that SpotBugs is fail-closed and deliberately outside default Check A until a compiled pilot exists, naming the enabling path.

### Deferred
- **The `D.scalacheck` → `D.property` display alias (§11.35c)** stays deferred: the label lives inside the shared `_check_scalacheck_params` engine helper, so a per-toolchain alias would touch the engine — the standing wager holds it until a reason to touch the engine arrives anyway.

### Sources
- The agentic-TDD-loop build brief's §§11–12 amendments (2026-07-14), and the v1.3.0 dogfooding residues (the Java-layer done report + clm-0030).

## v1.3.1 — 2026-07-15

Squash-safe precedence, and the clm-0030 discharge-chain fix it surfaced. The loop's precedence check reads per-commit ancestry; a squash-merge erases it. The fix is the gate's own pattern — verify where the history exists, persist the verdict as content.

### Added
- **`audit.py --certify` (PR mode)** — on the intact branch (pre-squash), emits a `precedence verified: …` certificate (a `testimony`, `source: hook`) for each verifiable park→supersede pair. The certificate rides a squash as content; the main-side `tdd-precedence`, where the two introducing commits collapse into one code-carrying commit (`xc == yc`), consumes the certificate in place of the erased ancestry. Rebase-merge and merge-commit keep the richer per-commit ancestry for free. `--certify` is an emitter (exit 0); the warn-grade `tdd-precedence` flags a pair with no certifiable precedence. New red-first fixture `squash_precedence_test.py`; a `pull_request` CI step runs `--certify`; `harness/ledger/README.md` and the operators-manual gain a "Squash-merge compatibility" paragraph.

### Fixed
- **clm-0030 (the three-link discharge chain), check-side.** `park_supersede_pairs` skips a parked claim that itself supersedes something — a `park → repo-check → signed` chain's repo-check *middle* link is a discharge step, not a claim-first event — so it no longer false-warns in `tdd-precedence`, false-fails in `--certify`, or miscounts coverage. `report_red_proof_coverage` walks the forward supersession chain, so a red-proof receipt filed about the signed 3rd link (the live claim) credits the slice: coverage read 0/3 before, 3/3 now. Surfaced during v1.3.0 as the first loop-built release's own dogfood; resolved here because §10's `--certify` wiring needs it.

### Sources
- The updated agentic-TDD-loop build brief's §10 amendment (squash-safe precedence, 2026-07-14) and the v1.3.0 dogfooding finding (clm-0030).

### Process
- Built under the kit's self-installed loop: claim-first, red-first for the detector-class slices (`squash_precedence_test.py`, the three-link `tdd_precedence` case), gate-signed, red-proof receipts filed. Disclosed deviations: the brief has CI emit+commit the certificate, but the kit's read-only/fork-safe CI can't push, so the author emits it pre-merge and CI verifies; and the "squashing destroys the trail" warning the brief asks to replace was never in a committed doc (PR bodies + commit messages), so the correct framing is established in the docs.

## v1.3.0 — 2026-07-15

The first language added under the loop, measured by the loop, and merged only where a human said so. Two waves by warrant grade: wave one is mechanism (the gate's Java toolchain and plumbing — detector-class, autonomous under the gate); wave two is judgment (the eight `java-*` rules — drafts for the operator's gavel, testimony until signed).

### Added
- **The Java toolchain in the differential gate** (`reference/sdlc-gate.py` `JavaToolchain`) — a scanner-plugin, no engine change: detection by `pom.xml` / `build.gradle(.kts)`; Checkstyle Check A (google_checks, source, DOCTYPE-rejecting parser); suppression Check B (`@SuppressWarnings` / `@SuppressFBWarnings` / `//CHECKSTYLE:OFF` / `//NOPMD`); test-weakening Check D (`@Disabled`/`@Ignore`, assertion sites, and jqwik parameter weakening — a `@Property(tries=N)` fall and a `ShrinkingMode.OFF` appearance, with the shrinking key ALWAYS emitted so 0→1 is caught through the shared parameter check); the shared fail-closed compile precondition (mvn/gradle); and opt-in JaCoCo coverage. SpotBugs (bytecode) fails CLOSED on a source-only tree rather than scanning empty and passing — its default-path wiring awaits a compiled pilot.
- **`gate.py` Java plumbing** — `check_command()` gains the Maven default (`mvn -B -q verify`) and the hermetic gradle-wrapper fallback (`--no-daemon --console=plain`); `code_exts()` auto-detects `.java` for `pom.xml`/`build.gradle(.kts)` roots, and a vendored `.java` under a non-Java root does not fire the gate.
- **Templates and `pr-review`** — `languages.example` notes `.java`; `check.sh.example` gains a hermetic Java stanza (`mvn -B -q -DskipITs test` in a hook, gradle via the no-daemon wrapper); `pr-review` maps `*.java` → Java, lists the Java gate commands, and loads `java-*` rules.
- **The eight `java-*` rules** (`java-style/errors/types/concurrency/modules/testing/security/llm`) — the modern-Java doctrine: google-java-format as a build gate; records/sealed/pattern-matching defaults; unchecked-by-default errors with try-with-resources and `Optional`-as-return-only; JSpecify nullness; virtual threads and structured concurrency at the Java 21 floor; package-by-feature with the ≤ 7-public-names cap; JUnit 5 + AssertJ + jqwik (one shared `Arbitraries` provider, `frequency` corner-pinning, a `Statistics` distribution property); OWASP-plus-JVM-first security (deserialization, XXE, path traversal, parameterized SQL, secrets) with a Spring Boot subsection gated on `spring-boot-starter` detection; and a `java-llm` skeleton. Delivered as drafts on a branch for the operator's gavel — testimony until signed; the instance does not merge them.

### Sources
- The operator's build brief (the Java layer, v1.3.0) and its parameter block: formatter google-java-format; testing JUnit 5 + AssertJ + jqwik; floor Java 21 LTS (virtual threads / structured concurrency by default); build tool Maven default, Gradle via the wrapper; static stack Checkstyle + SpotBugs standalone.
- Public canon only (the IP wall holds): *Effective Java* 3rd ed, *Java Concurrency in Practice*, the JUnit 5 / jqwik / AssertJ / google-java-format documentation, OWASP, and JSpecify. Nothing ported from employer material.

### Process
- The first release built under the agentic loop it ships: the kit self-installed its own dev-ledger (a top-level `ledger/`, separate from the shipped `harness/ledger/` template it vendors to adopters), so every wave-one slice was claim-first with a `red-proof` receipt and gate-signed, and each rule draft entered as a `testimony` ledger entry naming the operator's review as its court.

## v1.2.0 — 2026-07-14

The development loop as doctrine and its enforceable subset as mechanism. The loop never asks the agent whether it did TDD — it arranges the world so the claim precedes the code in git, the red is a receipt on the board, the green passes a gate that watches the checks, and the rate is a number in the audit report. Design rule throughout: authoring order is testimony, detection power is mechanical, precedence is git, coverage is counted.

### Added
- **The agentic TDD loop** (`craft-tdd` rule, `ledger-preregister`, `report-conventions`, `ledger-verify`, operators-manual): the five beats (claim → red-receipt → green under the gate → refactor → disclose), the order-vs-detection decomposition (order is testimony forever; detection is provable by `red-proof`), and court selection — red-first is **mandatory for detector-class slices** (gates, checks, tamper proofs, fail-closed properties, discriminating mechanisms) and negotiable-with-disclosure elsewhere. The claim-first ledger-only commit is the precedence timestamp; a discriminating mechanism states its contrast obligation.
- **`red-proof --about clm-NNNN --ledger`** — files a `testimony` receipt (red confirmed, or the not-red finding on a tautology) via `ledger/append`; no gate change, no schema change, no behavior change without the flags.
- **`audit.py` `tdd-precedence`** warn check (park→supersede pairs: the parked claim's commit is ledger-only and precedes the code — C1 at development granularity, subsuming the preregistration audit's dev-side half) and the **`red-proof coverage`** `--report` line (`k/n` test-bearing slices carrying a receipt, plus the detector-class subset).
- **The deep-reason adversary contract** (`deep-reason` skill + reference): findings ship the raw command+output, a paste-and-rerun repro, and the named check that would confirm them; findings route as `kind: refutation`; a clean pass is an absence report, not an approval; escalation-tier scope (routine PR review → `pr-review`); cross-family with lineage disclosure; the report carries its own reliability boundary.
- **`install-harness.sh --upgrade`** — overwrites kit-owned verbatim files (helpers, fixtures, skills) when the kit is newer, never touching repo-owned `check.sh` / `languages` / `claims.jsonl` / `trace/`; writes a `ledger/VERSION` stamp. Without it the v1.1.0 retire fix could never reach an existing install.
- **Two one-fact memories** (`retire-any-commit`, `adversary-not-second-opinion`), and the `check.sh.example` red-proof graduation block (documented, not enabled — a norm earns blocking power only after a season of receipts).

### Fixed / reconciled (the obsolescence audit of 2026-07-14)
- **The retire law** corrected in the three satellites still teaching the pre-v1.1.0 rewrite-in-place, same-commit-only rule (the `ledger-retire` skill, the `librarian` docstring, `CLAUDE-harness-section.md`) to the verbatim-move-plus-sidecar form (safe in any later commit); the `--sweep` scar kept as history.
- **The second-minter semantics line**: "the gate is the sole writer of `signed`" corrected everywhere (SECURITY.md, `harness/ledger/README.md`, `ledger-write`, `ledger-discharge`) — two paths mint, the commit-path gate and the installer's `harness-verify`, both recording their line-hashes for the forgery guard.
- Three one-sentence reconciles (`ledger-discharge` citation-vs-audit; operators-manual verb 3, dissent-enters-freely; `pr-review` Step 3, Scala + TypeScript gate commands); the dangling-reference memory annotated; the deep-reasoning-agent memory's "second opinion" framing marked superseded.

### Hardened (the automated party's cheap bypasses)
- **`git commit --no-verify` / `-n`** added to the settings deny-list, closing the hook bypass that sat inside the broad `git commit*` allow.
- **`gate.py` env overrides** (`LEDGER_CHECK_CMD` / `LEDGER_CODE_EXTS`) are honored only when the `ledger/.test-mode` sentinel exists (gitignored; only `harness-verify` and the fixtures create it), logging a stderr line when honored.
- New red-first fixtures wired into `harness-verify.sh` + CI: `tdd_precedence_test`, `install_upgrade_test` (kit-only), `gate_sentinel_test`; `red_proof_test` extended. red-proof stays advisory this release by its own docstring's law.

### Sources
- This build brief (the agentic-TDD-loop, the adversary contract, the v1.2 reconciliation), the TDD-loop design discussion, and the obsolescence audit of 2026-07-14.

## v1.1.1 — 2026-07-13

The ledger's conventions get their formal companion: a machine-checked note establishing which ledger moves are theorems of the claim algebra and which are new axioms, its validation script wired into CI, and the registration and render rules the note licenses.

### Added
- **`docs/ledger-dynamics-note.html`** — the formal note (22 machine-checked results). The dictionary: the two-entry refutation shape is the supersession pair (Def 2.14), retire is `strike` (Def 2.12), the contested board state is an unfolded glut. The new structure: the truth-join `∨ₜ` at testimony level with its dual-laundering hazard (Theorem L5) and the witness and totality rules that defeat it (Theorem L6); the interval-testimony sort the empirical courts use (Defs L8–L11); and the process axioms C1/D1/D2 and E3 with consistency, independence, and conservativity established.
- **`harness/algebra/validate_note.py`** — stdlib-only, re-proves the base laws and carries the two laundering exhibits: `⊗ₖ`'s glut-identity divergence (the running-system check owed since the 2026-07-08 glut-laundering correction — now a green fixture) and `∨ₜ`'s dual laundering. Wired into CI as a required check via a summary-line guard (the script prints its total but exits 0), so a future edit reintroducing either laundering fails CI by name.
- **Three registration conventions** (`ledger-write`, cross-referenced from `ledger-preregister`): name the composition connective (`∧ₜ` truth-meet / `∨ₜ` truth-join); existence claims register their habitats and inherit L6's witness and totality rules; interval claims register the L9 estimand-δ-exits template.
- **The agreement discount** (`ledger-verify`, Axiom E3): grade corroboration-class support by distinct lineages, not raw confirmations — two reviews of the same configuration are one lineage.

### Deferred (v1.2)
- Two `board.sh` lints — `needs-docket` (Axiom D1: a live prediction whose scope elapsed with no named future court) and the `needs-successor` deadline (Axiom D2: contested-beyond-a-window escalates to FAIL) — and the `preregistration` audit check (Axiom C1: parameters commit before the archives their verdict reads), config-gated. Tracked as issues.

### Sources
- The note and its validator originate from the founding project's claim-algebra work; the correction-doc's owed divergence check is discharged here as a portable fixture.

## v1.1.0 — 2026-07-12

Two yields in one release: a real ledger-integrity fix, and the portable lessons from a dual-leg cross-language discharge. The multi-writer **sharded ledger layout** (from the concurrency reconciliation) is intentionally **deferred** — it is inert for a single-writer repo (the legacy `claims.jsonl` is the one-shard degeneration, no migration), and ships when a real multi-writer deployment needs it.

### Fixed
- **The retire/immutability defect (verbatim-move + sidecar).** `ledger/retire` previously rewrote the moved entry in place (adding `status`/`trace_reason`/`retired_by`), so retiring any claim whose live form was committed in an *earlier* commit tripped `check_immutable` — forcing a same-commit-only discipline and making boards accrete superseded-in-place entries forever (the incident that fired). Now `ledger/trace/<id>.jsonl` receives the original claim line **byte-identical** plus a separate retirement record (`retire_of`/`trace_reason`/`retired_by`); `audit.py` partitions trace into claim entries and retirement records and its trace check reads the pair; `board.sh`'s graveyard excludes retired ids from the contested view. Legacy in-place retired entries stay valid. A claim may now be retired safely in any later commit.

### Added
- **`ledger/red-proof`** — the mechanical court for the "observed red" disclosure: builds a hybrid tree (implementation at the merge-base, tests from HEAD in a throwaway `git worktree`) and asserts the new tests FAIL against the old implementation, killing tautologies and green-by-weakening. Opt-in per slice + a done-report line, not a hard gate at first.
- **Two red-first ledger fixtures** (`harness/ledger/fixtures/{retire_immutable_test,red_proof_test}.py`), wired into `harness-verify.sh` (verify 3/3): the retire fixture is red on the old rewrite and green on the verbatim-move; the red-proof fixture rejects a tautological test and passes a genuine one.
- **Three durable memories** — `feedback_cross_language_dual_leg_primitives` (dual-leg legs diverge at language primitives, not logic; pin at the byte level, share an explicit PRNG), `feedback_golden_provenance` (label goldens hand-derived / computed-then-pinned / recorded-from-run), `feedback_reviewer_harness_fail_closed` (a dead review lens is a dropped finding — reconcile launches against completions).
- **`reference/dual-leg-checklist.md`** — the fifteen-minute primitives-diff pass for any computation implemented in two languages.
- **The four disclosure conventions** upstreamed: the semantics line (`ledger-discharge`), the authorship note (`ledger-write`), the reliability boundary (`ledger-verify`, already present), and the **process paragraph** (per-slice test-order / observed-red / green-by-weakening / refactor disclosure) — carried verbatim in the new `harness/templates/report-conventions.md` and summarized in the operators manual.

### Release readiness (public-release gate)
- **LICENSE** (Apache-2.0) and **SECURITY.md** — the trust model stated plainly: single-user mode trusts the local machine; a `signed` entry means only that a named check passed; team mode (server-side signing) is deferred and unshipped; what the kit does not defend against (a hostile repo admin, a compromised CI).
- **The kit's own CI** (`.github/workflows/ci.yml`, read-only, no secrets): runs the acceptance suite — scrub-gate, board selftest, the retire + red-proof fixtures, and the 20 differential-gate unit tests — on every push and PR.
- **README** gains the status/scope/license section: single-user shipped, multi-writer sharding + team mode deferred (not in this release).
- **Deferred with the sharding:** the GitHub team-reconcile runbook and its workflow/CODEOWNERS templates — they presuppose the sharded/team-mode layout, which is not shipped. They ship when multi-writer mode does.

### Sources
- `ledger-concurrency-reconciliation.md` (2026-07-12) — the retire/immutability fix (the salvage that applies to any layout); the sharded layout deferred.
- `kit-improvements-d2-yield.md` (2026-07-12) — the three memories, the dual-leg checklist, the disclosure conventions, and `red-proof`.
- `kit-public-release-gate.md` (2026-07-12) — the release gate (LICENSE, SECURITY, CI, scope); the team-mode GitHub runbook deferred with sharding.

## v1.0.0 — 2026-07-11

First stable release: portable engineering discipline for Claude Code, distilled and scrubbed from a personal SDLC pack, a Go/Python craft taxonomy, and a Scala dev-ledger harness. Scrubbed of every machine, project, and personal identifier (`scrub-gate.sh` PASS).

### Rules
- 42 auto-loading rules across four languages: a language-neutral `craft-*` core plus `go-*`, `python-*`, `scala-*`, and `ts-*` (TypeScript/React+Vite), with `decoupling` and `writing-style`.
- The `scala-*` layer states the scalafix `DisableSyntax` safe subset as build-failing hard bans (not soft preferences), enumerates the full ban set, frames scalafmt as a build gate, and carries the real testing practices (one shared `Generators` per module, `Gen.frequency` corner-pinning, the always-true distribution-report property, `withMaxSize`/serial-execution, the `RUN_LIVE_*` `munitIgnore` idiom).

### Guides
- 5 long-form principal-engineer guides (DDD, GOOS, modularity, refactoring, xunit-test-patterns), neutralized to a generic order/account/pipeline domain.

### The differential anti-weakening gate (`reference/sdlc-gate.py`)
- Multi-language: ruff / mypy / bandit (python) and scalafix / wartremover (scala); Check A (finding identity), B (suppressions), C (test deletions), D (test-weakening), plus the ScalaCheck-parameter value check.
- **Fail-closed compile precondition** (Check Build): a non-compiling branch or baseline now blocks on `Build/compile_error` (exit 1) rather than scanning empty and passing.
- **scoverage coverage-drop scan** (opt-in `--coverage`, Check D): a per-directory statement-coverage drop beyond 0.5pp blocks; a failed scan is operational (exit 2, fail-closed).
- A 20-test stdlib `unittest` suite (`reference/test_sdlc_gate.py`).

### The dev-ledger + commit-path gate harness (`harness/`, `install-harness.sh`)
- `append` / `audit.py` / `gate.py` (byte-identical across repos) / `librarian` / `retire`, plus `board.sh`, read-only board views (`open` / `graveyard` / `checks` / `stale` / `find` / `next-id`) with a `--selftest` against a committed fixture.
- Six `ledger-*` skills (read before writing, the entry discipline, claim before building, cite before re-checking, supersession safely, the auditor's stance) dropped into `.claude/skills/`.
- The operators manual (`ledger/operators-manual.md`).
- The `check.sh` / `languages` / hook templates.

### User-scoped skills
- `deep-reason` (fresh-context second opinion) and the language-aware `pr-review` (now loading `scala-*.md` / `ts-*.md`).

### Documentation
- Added this changelog and retired `PACK_SOURCE_TAG`; its provenance lives in **Sources** below.

### Sources (provenance)
The kit is a scrubbed derivative; each slice was distilled from:
- **SDLC pack `v2.43.0`** — the guides, `sdlc-gate.py`, the `decoupling` / `writing-style` rules, the voicing document.
- **Go-harness snapshot 2026-06-17** — the `craft-*` / `go-*` / `python-*` rules (scrubbed).
- **dev-ledger harness 2026-07-09** — `harness/`, `install-harness.sh`, `harness-verify.sh`, the `scala-*` rules, and the `sdlc-gate.py` Scala scanner-plugin port.
- **dev-ledger multi-language 2026-07-08** — `gate.py` fires the check for every build language via `ledger/languages`, the `GIT_*` clean-env fix, and the `languages` / `check.sh` templates.

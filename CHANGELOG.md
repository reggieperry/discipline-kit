# Changelog

Notable changes to the discipline kit. Versions follow [semantic versioning](https://semver.org); the format follows [Keep a Changelog](https://keepachangelog.com). This file supersedes the former `PACK_SOURCE_TAG`, folding its upstream-source provenance into the **Sources** section under each release.

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

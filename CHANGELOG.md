# Changelog

Notable changes to the discipline kit. Versions follow [semantic versioning](https://semver.org); the format follows [Keep a Changelog](https://keepachangelog.com). This file supersedes the former `PACK_SOURCE_TAG`, folding its upstream-source provenance into the **Sources** section under each release.

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

### Sources
- `ledger-concurrency-reconciliation.md` (2026-07-12) — the retire/immutability fix (the salvage that applies to any layout); the sharded layout deferred.
- `kit-improvements-d2-yield.md` (2026-07-12) — the three memories, the dual-leg checklist, the disclosure conventions, and `red-proof`.

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

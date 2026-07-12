# Changelog

Notable changes to the discipline kit. Versions follow [semantic versioning](https://semver.org); the format follows [Keep a Changelog](https://keepachangelog.com). This file supersedes the former `PACK_SOURCE_TAG`, folding its upstream-source provenance into the **Sources** section under each release.

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

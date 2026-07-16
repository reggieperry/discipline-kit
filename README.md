# Discipline kit

Portable engineering discipline for Claude Code — the auto-loading rules, principal-engineer guides, review skills, methodology memories, and the differential gate, packaged to drop into a fresh Claude Code install on another machine.

## Quick start — say this to Claude Code

The kit's operator is Claude Code; its interface is the utterance. Paste these prompts. Each is **read-first** (it points the instance at the docs before it acts), ends with a **receipt demand** (show me the output), and is **dual-audience** — the instance reading this README executes the prompt as its own checklist. There is one ceremony: the **Install** prompt. After it, the injected `CLAUDE.md` harness section and the auto-loaded `ledger-*` skills make the discipline ambient — the rest are orientation and recovery, not setup.

> **Install (one time):** "The discipline kit is at `<path>` (or: clone `<repo-url>` to a sibling directory). Read its `README.md`, `install.md`, and `SECURITY.md` first. Then install the harness into this repository and run its acceptance in one command — `install-harness.sh --dir . --verify` — the single-user (private) tier is the only shipped mode. Show me the full verify output, including the forgery-probe result and the `VERSION` stamp. After install, most users should run the Tour prompt next."
>
> **Orient (each new project, or when unsure):** "Read `ledger/operators-manual.md` and the six ledger skills, then give me the board — weaknesses first."
>
> **Work (a slice):** "Take on `<task>` as a kit slice: register the acceptance claim per `ledger-preregister` as its own ledger-only commit before any code, tell me the `clm` id, then proceed — red-first if this is detector-class, otherwise your declared allocation. Done-report per `report-conventions` when the gate signs."
>
> **When a commit blocks:** "Show me the refuted claim and the check output verbatim, then walk me through the three honest moves before touching anything."
>
> **Upgrade:** "Run `install-harness.sh --upgrade`, show me the `VERSION` delta, and re-run `harness-verify`."
>
> **Tour the options (recommended after install):** "Walk me through this kit's options for this repo, one at a time, from the operators-manual's Options section: the tier, the pinned check command, language coverage, the audit's strict-versus-warn modes and the preregistration check, the coverage opt-in, red-proof's advisory status, and the waiver rules. For each: the default, what changing it buys, and your recommendation for this repo. Apply what I choose to the repo-owned files, then append one configuration claim to the ledger recording every choice — including the defaults I kept — and show it to me."

This installs the private tier: your ledger is local and binds against re-narration, not against you. The full lifecycle is walked in [`docs/week-with-the-kit.md`](docs/week-with-the-kit.md); the trust model is `SECURITY.md`.

It is distilled from a personal SDLC discipline pack, a Go/Python craft taxonomy developed in a separate Go-harness repo, and an accumulated corpus of working memories, with every machine, project, and personal identifier removed. The rule layer is multi-language: a language-neutral `craft-*` core plus per-language `go-*`, `python-*`, `scala-*` (Scala 3 + cats-effect), `java-*` (Java 21 LTS), and `ts-*` (TypeScript/React+Vite) rules (the `pr-review` skill loads the reviewed repo's matching layer). What lands here is the *interactive discipline*: the part that makes a single Claude Code session reason and review better. It deliberately does **not** include the autonomous build chain (see below).

## Status, scope, and license

**v1.3.4.** Licensed under **Apache-2.0** (`LICENSE`). CI runs the kit's own acceptance suite — the scrub-gate, the ledger board selftest, the retire / red-proof / gate-sentinel / java-plumbing / squash-precedence / memory-index fixtures, the differential-gate unit tests, and the PR-mode precedence certifier — on every push and pull request (`.github/workflows/ci.yml`, read-only, no secrets). Security posture and trust boundaries: `SECURITY.md`.

**Shipped mode: single-user.** The dev-ledger runs with the legacy `claims.jsonl` as its one shard; the audit recognizes the sharded layout as the concurrency foundation, but real multi-writer sharding and **team mode** (server-side signing, provenance-verifiable discharge, the GitHub post-merge reconcile) are **deferred** — designed in the reconciliation, not shipped in this release. Single-user is the only supported mode today; multi-writer support ships when a real deployment needs it. Do not rely on any server-side or fork-PR guarantee here (`SECURITY.md` states this plainly). The latest releases add the Java coding-discipline layer (the gate's `JavaToolchain` and the eight `java-*` rules), squash-safe precedence (`audit.py --certify`), and enforcement-grade labels on the security rules — all built under the kit's own self-installed agentic loop; see `CHANGELOG.md`.

## What's in here

```
claude-user/            → installs into ~/.claude
  CLAUDE.md               deep-reason self-trigger criteria + review pointer
  settings.json           conservative permissions (local git only, no auto-bypass)
  skills/deep-reason/     fresh-context adversary and verdict subagent
  skills/pr-review/       language-aware collaborative PR/branch/diff review
claude-project/         → copies into each repo's .claude/
  rules/                  50 auto-loading rules in three layers:
                          craft-* (language-neutral: abstraction, complexity,
                            documentation, domain-modeling, refactoring, tdd, xunit)
                            + decoupling + writing-style
                          go-*     (8: style, errors, types, concurrency, modules,
                            testing, security, llm)
                          python-* (8: style, errors, types, concurrency, modules,
                            testing, security, llm)
                          scala-*  (8: style, errors, types, concurrency, modules,
                            testing, security, llm)
                          java-*   (8: style, errors, types, concurrency, modules,
                            testing, security, llm — Java 21 LTS floor; Checkstyle
                            + SpotBugs static stack)
                          ts-*     (9: style, errors, types, concurrency, modules,
                            testing, security, llm, react — TypeScript/React+Vite)
  sdlc-discipline/guides/ 5 long-form guides (ddd, goos, modularity, refactoring,
                          xunit-test-patterns) — the deep tier behind the craft-* rules
reference/
  sdlc-gate.py            the differential anti-weakening gate (stdlib + uv/git)
  review-checklist.md     the gate as a manual checklist (uv-absent fallback)
  deep-reasoning-agent.md the 6-section prompt template the deep-reason skill walks
  voicing-document.md     the human-prose writing register
harness/                → the dev-ledger + commit-path gate (per-repo; install-harness.sh)
  ledger/                 append / audit / gate / librarian / retire + board.sh (read-only board views)
  skills/                 six ledger-* skills: read before writing, claim before building, cite before re-checking
  templates/              check.sh / languages / hook snippets
memories/               → optional, per-project memory dir
  68 scrubbed methodology memories + MEMORY.md index
install.sh              user-level installer (guards existing config)
scrub-gate.sh           self-audit: fails if any private identifier survives
scripts/refresh-from-pack.sh   rebuild rules/guides/gate from a newer pack tag
```

### Security-scanner parity

A security rule states its **enforcement grade** at the top — no rule reads stronger than its gate. Today only one of the five is mechanically policed; the roadmap closes the gap, and each wiring is detector-class when it lands (red-first fixtures, and the wiring commit deletes that rule's enforcement-grade disclaimer in the same diff — the label and the gate move together or not at all):

- **Python** — wired now: `bandit` rides Check A (findings diff, `#nosec` suppressions policed). The reference point.
- **Go** — roadmap: `gosec` as a `GoToolchain` (bandit's exact analog, the same scanner-plugin exercise `java` proved); the rule's G-code citations become live finding identities.
- **Java** — roadmap: FindSecBugs on the existing SpotBugs engine, when the compiled pilot opens.
- **TypeScript** — roadmap: `eslint-plugin-security` or `semgrep`, with the TS toolchain.
- **Scala** — deferred: no native `bandit`-equivalent; options are bytecode-side FindSecBugs or `semgrep`.

## What this is NOT — the autonomous chain

The source system also runs an autonomous worker → tester → reviewer → documenter → finalizer chain under a supervisor with a durable work-item store. None of that is here, by design: it needs a long-running supervisor daemon, a database-backed queue, per-machine native builds, and an unattended-execution posture that a managed corporate laptop will not host and corporate policy will not allow. This kit is the discipline a human-in-the-loop session applies — not the robot that runs it.

## Install (user-level)

```
./install.sh
```

Copies the skills, the deep-reasoning template, and the gate into `~/.claude`. It will **not** overwrite an existing `~/.claude/CLAUDE.md` or `settings.json` — it backs them up and prints what to merge. Override the target with `CLAUDE_HOME=/path ./install.sh`.

## Per-project setup

Inside each repo you want the discipline to govern:

```
mkdir -p .claude/rules .claude/sdlc-discipline/guides
cp /path/to/discipline-kit/claude-project/rules/*.md                  .claude/rules/
cp /path/to/discipline-kit/claude-project/sdlc-discipline/guides/*.md .claude/sdlc-discipline/guides/
```

Rules auto-load by path glob (`**/*.go`, `**/*.py`, `**/*.scala`, `**/*.java`, `tests/**`, `docs/**`, …) when you edit a matching file: the `go-*` rules fire on Go files, `python-*` on Python, `scala-*` on Scala, `java-*` on Java, `craft-*` on all of them, no further wiring. To carry the methodology memories into a project, copy `memories/*.md` into that project's memory directory and keep the one-line-per-memory convention in its `MEMORY.md`.

## Using it

- **Rules** load themselves on edit. Nothing to invoke.
- **`/deep-reason`** spins up a fresh-context Opus subagent for verdict-shaped or hard-to-reverse decisions; the self-trigger criteria are in the installed `CLAUDE.md`.
- **`/pr-review`** reviews a PR, branch, or diff — it runs the gate first, loads the *reviewed repo's own* rules, then applies the language-neutral core.
- **The gate** enforces anti-weakening on a branch: no new ruff/mypy/bandit errors, no new suppressions, no new skipped tests, no assertion-count loss versus the merge-base.

  ```
  python3 ~/.claude/discipline/sdlc-gate.py baseline --sha $(git merge-base HEAD origin/main) --out /tmp/base
  python3 ~/.claude/discipline/sdlc-gate.py diff --baseline-dir /tmp/base
  ```

  It needs `uv` (for ruff/mypy) and `git`; without `uv`, follow `review-checklist.md` by hand.

- **SpotBugs (Java) is implemented fail-closed and deliberately outside default Check A** until a compiled pilot exists: it analyzes bytecode, and a source-snapshot differential cannot compile a tree, so wiring it into the default path would fail *open* on a source-only repo — instead it raises `SpotBugsOperationalError` when the tool is present but no `target/classes`/`build/classes` bytecode is found. The enabling path is a compiled pilot repo (bytecode on disk), where FindSecBugs can then ride the same SpotBugs engine as the Java security scanner.

## Refreshing and provenance

The rule layer has three upstreams: the SDLC pack (the guides, the gate, `decoupling`/`writing-style`), a Go-harness repo (the `craft-*`/`go-*`/`python-*` rules), and a Scala dev-ledger harness repo (the `scala-*` rules, authored there against the Scala canon rather than ported from the Go-harness). All of it is scrubbed of machine, project, and personal identifiers; `./scrub-gate.sh` enforces that across four checks (infra/PII anywhere, chain vocab and harness vocab in the scrubbed surfaces, and a dangling-cross-ref check) and is the last step before packaging.

Two house conventions are resolved in-kit where the sources disagreed: docstrings are **prose-only** (the source's Google-style `Args:/Returns:/Raises:` mandate was stripped from `python-style`), and **Pydantic is scoped to the validated LLM/external boundary** (no blanket ban). The long-form **guides have been fully neutralized**: all project-specific references have been rewritten to a generic order/account/pipeline domain, so the DDD/GOOS/Fowler/Liskov teaching stands on its own without assuming any particular system. A running example (an account evaluating proposed transactions against limits, approving or rejecting them, recording outcomes) carries the concrete illustrations where the patterns need one.

`scripts/refresh-from-pack.sh` rebuilds only the pack-sourced pieces from a pack tag today; the harness-sourced rules are not yet wired into an automated refresh (which upstream is canonical on collision is an open decision, deferred):

```
scripts/refresh-from-pack.sh <pack-checkout-dir> <tag>   # pack pieces; then: ./scrub-gate.sh
```

Per-release notes and upstream source provenance are in `CHANGELOG.md` (which superseded the former `PACK_SOURCE_TAG`).

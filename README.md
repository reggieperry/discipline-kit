# Discipline kit

Portable engineering discipline for Claude Code — the auto-loading rules, principal-engineer guides, review skills, methodology memories, and the differential gate, packaged to drop into a fresh Claude Code install on another machine.

It is distilled from a personal SDLC discipline pack, a Go/Python craft taxonomy developed in a separate Go-harness repo, and an accumulated corpus of working memories, with every machine, project, and personal identifier removed. The rule layer is multi-language: a language-neutral `craft-*` core plus per-language `go-*`, `python-*`, `scala-*` (Scala 3 + cats-effect), and `ts-*` (TypeScript/React+Vite) rules (the `pr-review` skill loads the reviewed repo's matching layer). What lands here is the *interactive discipline*: the part that makes a single Claude Code session reason and review better. It deliberately does **not** include the autonomous build chain (see below).

## What's in here

```
claude-user/            → installs into ~/.claude
  CLAUDE.md               deep-reason self-trigger criteria + review pointer
  settings.json           conservative permissions (local git only, no auto-bypass)
  skills/deep-reason/     fresh-context Opus second-opinion subagent
  skills/pr-review/       language-aware collaborative PR/branch/diff review
claude-project/         → copies into each repo's .claude/
  rules/                  42 auto-loading rules in three layers:
                          craft-* (language-neutral: abstraction, complexity,
                            documentation, domain-modeling, refactoring, tdd, xunit)
                            + decoupling + writing-style
                          go-*     (8: style, errors, types, concurrency, modules,
                            testing, security, llm)
                          python-* (8: style, errors, types, concurrency, modules,
                            testing, security, llm)
                          scala-*  (8: style, errors, types, concurrency, modules,
                            testing, security, llm)
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
  58 scrubbed methodology memories + MEMORY.md index
install.sh              user-level installer (guards existing config)
scrub-gate.sh           self-audit: fails if any private identifier survives
scripts/refresh-from-pack.sh   rebuild rules/guides/gate from a newer pack tag
```

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

Rules auto-load by path glob (`**/*.go`, `**/*.py`, `**/*.scala`, `tests/**`, `docs/**`, …) when you edit a matching file: the `go-*` rules fire on Go files, `python-*` on Python, `scala-*` on Scala, `craft-*` on all of them, no further wiring. To carry the methodology memories into a project, copy `memories/*.md` into that project's memory directory and keep the one-line-per-memory convention in its `MEMORY.md`.

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

## Refreshing and provenance

The rule layer has three upstreams: the SDLC pack (the guides, the gate, `decoupling`/`writing-style`), a Go-harness repo (the `craft-*`/`go-*`/`python-*` rules), and a Scala dev-ledger harness repo (the `scala-*` rules, authored there against the Scala canon rather than ported from the Go-harness). All of it is scrubbed of machine, project, and personal identifiers; `./scrub-gate.sh` enforces that across four checks (infra/PII anywhere, chain vocab and harness vocab in the scrubbed surfaces, and a dangling-cross-ref check) and is the last step before packaging.

Two house conventions are resolved in-kit where the sources disagreed: docstrings are **prose-only** (the source's Google-style `Args:/Returns:/Raises:` mandate was stripped from `python-style`), and **Pydantic is scoped to the validated LLM/external boundary** (no blanket ban). The long-form **guides have been fully neutralized**: all project-specific references have been rewritten to a generic order/account/pipeline domain, so the DDD/GOOS/Fowler/Liskov teaching stands on its own without assuming any particular system. A running example (an account evaluating proposed transactions against limits, approving or rejecting them, recording outcomes) carries the concrete illustrations where the patterns need one.

`scripts/refresh-from-pack.sh` rebuilds only the pack-sourced pieces from a pack tag today; the harness-sourced rules are not yet wired into an automated refresh (which upstream is canonical on collision is an open decision, deferred):

```
scripts/refresh-from-pack.sh <pack-checkout-dir> <tag>   # pack pieces; then: ./scrub-gate.sh
```

Source versions are recorded in `PACK_SOURCE_TAG`.

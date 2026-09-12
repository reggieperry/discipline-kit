# Discipline kit

Portable engineering discipline for Claude Code — the auto-loading rules, principal-engineer guides, review skills, methodology memories, and the differential gate, packaged to drop into a fresh Claude Code install on another machine.

## Quick start — say this to Claude Code

The kit's operator is Claude Code; the interface is the prompt. Use the prompts below to install the kit. Each is **read-first** (it points the instance at the docs before it acts), ends with a **receipt demand** (show me the output), and is **dual-audience** — the instance reading this README executes the prompt as its own checklist. There is one ceremony: the **Install** prompt. After it, the auto-loading rules make the discipline ambient — the rest are orientation and recovery, not setup.

> **Install (one time):** "The discipline kit is at `<path>` (or: clone `<repo-url>` to a sibling directory). Read its `README.md` and `SECURITY.md` first. Run `./install.sh` from the kit to place the user-level pieces, then run the per-project lines it prints inside this repository. Show me the installer's output and `git status` afterwards."
>
>
>
> **When a commit blocks:** "Show me the check that failed and its output verbatim, then walk me through the three honest moves before touching anything."
>
> **Upgrade:** "The kit is at `<path-to-kit>`. Do these five in order. (1) `git -C <path-to-kit> pull`, which brings the new release tag with it. (2) Read **Staying current** in `<path-to-kit>/README.md`, which the pull you just did is what puts there. (3) Confirm you now have the NEW installer *without running it*: `grep -c -- '--version' <path-to-kit>/install.sh` must print a count above zero. Do not probe by running the installer: every installer *before* v2.0.0 parses no arguments at all, so handed a flag it ignores it and performs a full user-level install from the stale tree instead (measured on v1.5.1: exit 0, eight files written into the home directory). v2.0.0 itself refuses an unknown flag safely but has no `--version` to ask with, so a zero count means the pull did not bring the new installer. (4) `<path-to-kit>/install.sh --refresh-rules --dir .` inside this repository, which takes the rules and the guides from the newest release tag; read what it says it copied aside. (5) `<path-to-kit>/install.sh` for the user-level pieces. Then show me `cat .claude/rules/.kit-version` and `cat ~/.claude/discipline/KIT-VERSION` as the receipt, including the `state:` line and the per-piece dispositions."
>
>
> **Enable authoring — ADRs and stories (a Tour choice, default off):** "Turn on the optional authoring layer for this repo. Read the four authoring skills under the kit's `harness/skills/` — `adr-write`, `story-write`, `story-tighten`, `story-intake`. Then vendor them in: copy those four skills into `.claude/skills/`, and the ADR and story template directories (`docs/adrs/`, `stories/`) together with the `ADR-template.md` and `story-template.md` they reference, into this repo — confirm each skill's template reference resolves in-tree. Show me the new files."

This installs the rules and the review skills. It installs no git hook: the gate section below shows how to run the gate, including as a pre-commit hook. Authoring stories and ADRs — written locally or pulled from your team's board over its API — is the optional authoring layer (a Tour choice, above); the opt-in build chain that runs them is documented below; the trust model is `SECURITY.md`.

It is distilled from a personal SDLC discipline pack, a Go/Python craft taxonomy developed in a separate Go-harness repo, and an accumulated corpus of working memories, with every machine, project, and personal identifier removed. The rule layer is multi-language: a language-neutral `craft-*` core plus per-language `go-*`, `python-*`, `scala-*` (Scala 3 + cats-effect), `java-*` (Java 21 LTS), and `ts-*` (TypeScript/React+Vite) rules (the `pr-review` skill loads the reviewed repo's matching layer). What lands here is the *interactive discipline*: the part that makes a single Claude Code session reason and review better. It also ships an **opt-in, attended-only build chain** (see below), off by default; the heavier autonomous robot the source system runs does not come along.

### Staying current

Two stamps say what a machine actually has, and both are plain text a session can `cat`:

- `~/.claude/discipline/KIT-VERSION` (or under `$CLAUDE_HOME`), written by the user-level
  install. It records a **state**, the kit path, the commit, `git describe`, the install time,
  and **a disposition per piece**. It names a **commit rather than a release**, and says so,
  because that mode copies `claude-user/` and `reference/` from the checkout's working tree. Read
  the dispositions, not only the commit: `installed` means this run wrote the kit's copy, while
  `kept-existing` means the file was already there and was left alone, so after an upgrade it
  still holds the previous release's text. `CLAUDE.md` and `settings.json` are the two that are
  never overwritten, which is why the stamp records them one by one instead of letting one commit
  speak for the whole install. The state works as the refresh stamp's does below: it is written
  before the first copy and rewritten after the last, so `complete` means every copy succeeded
  and `in-progress` or `partial` means a run died partway, with the dispositions naming the
  pieces it reached.
- `<repo>/.claude/rules/.kit-version`, written by `--refresh-rules`. It records a **state**, the
  **release tag** the rules and guides came from, that tag's commit, the kit path it was run
  from, the time, and the counts. It is a dotfile with no `.md` suffix, so no rule loader picks
  it up. The state is written *before* the first copy and rewritten after the last: `complete`
  means every copy succeeded, and `in-progress` or `partial` means a run died partway and some
  files here are the new tag while others are not. A stamp may be stale; it may not be wrong.

Compare either against `<path-to-kit>/install.sh --version`, which prints the kit path, the
commit, `git describe`, the newest release tag the checkout can see, and the flags this installer
supports. It creates no file and copies nothing, so it is safe to run before deciding to install.
(It is not a no-op on disk: `git describe --dirty` refreshes the checkout's git index, as any
status-like git read does. No tracked content changes.) `git describe` names the nearest ancestor
release tag plus the distance from it, so `v2.0.0-7-g1a2b3c4` means *seven commits past* v2.0.0,
not v2.0.0.

Two facts decide whether that comparison means anything:

- **Tags arrive by fetch.** A checkout whose tags were never fetched resolves the newest tag it
  has been *told* about, refreshes a repo from it, and reports success. A plain
  `git -C <path-to-kit> pull` brings new tags with it; `git -C <path-to-kit> fetch --tags` is the
  direct form.
- **An old installer ignores flags.** Every installer *before* v2.0.0, which is v1.0.0 through
  v1.5.1, parses no arguments: handed `--version` or `--refresh-rules` it ignores the flag and
  runs a full user-level install from whatever the checkout holds (measured on v1.5.1: exit 0,
  eight files into the home directory). v2.0.0 does parse flags and refuses an unknown one with
  usage and exit 2, writing nothing, but it carries no `--version` to ask with. Either way you
  cannot tell which you hold without looking, so probe with `grep`, never by running it.

What `--refresh-rules` does to a repository, so none of it is a surprise: it copies the tag's
rules over `.claude/rules/` and the tag's guides over `.claude/sdlc-discipline/guides/`. If that
guides directory does not exist it is reported and skipped, never created. **Rules and guides are
protected the same way**, since both are replaced wholesale: a file whose exact bytes match no
release tag the kit checkout can see is copied aside to `<name>.md.local-<timestamp>` before
being overwritten, what was preserved is listed, and a second backup in the same second is
numbered rather than allowed to overwrite the first. A kit-named rule the resolved tag no longer
ships is reported and left in place for you to retire. A rule that is a *symlink* is replaced by
a real file rather than written through, so the release's body lands inside the repository you
pointed at instead of wherever the link went, and each replacement is reported.

**What "matches no release" does and does not tell you.** The test is content: the file's bytes
against that path's blob at every `v*` tag **the kit checkout has**, and the run prints how many
tags that was. So the installer can see *that* a file matches nothing it read, and cannot see
*who wrote it* or *what it was never told about*. Three things produce a non-match, and they are
not distinguishable from the file alone: you edited it; you installed it by copying
`claude-project/rules/*.md` out of the checkout's working tree, which is exactly what
[Per-project setup](#per-project-setup) below, and the installer's own printed lines, tell you to
do; or the checkout's tag set is short, since tags arrive by fetch, and your file matches a
release this clone was never told about. A working-tree copy matches a release only if the
checkout sat exactly on a tag. The run names all three rather than calling your files modified,
points at `git -C <path-to-kit> fetch --tags` for the third, and when `.claude/rules/.kit-version`
was absent it adds that a first refresh has no record of what the earlier install took, so on
that run the first two are indistinguishable in principle. Backing the file up is the safe
direction, not a finding.

## Status, scope, and license

**v2.0.0.** Licensed under **Apache-2.0** (`LICENSE`). CI runs the kit's own acceptance suite — the scrub-gate, the rule-grade check and its fixture, the differential-gate unit tests, and the algebra-note validator — on every push and pull request (`.github/workflows/ci.yml`, read-only, no secrets). Security posture and trust boundaries: `SECURITY.md`.

**The dev-ledger was removed on 2026-07-30.** Its own record showed every signature it ever minted cited a single check — the repo's mechanical check — so the claim apparatus carried no information the check did not already return. What survives is the part that was catching things: the auto-loading rules, the review skills, the differential gate, and a commit-path check (`scripts/check.sh`). See `CHANGELOG.md`.

## What's in here

```
claude-user/            → installs into ~/.claude
  CLAUDE.md               deep-reason self-trigger criteria + review pointer
  settings.json           conservative permissions (local git only, no auto-bypass)
  skills/deep-reason/     fresh-context adversary and verdict subagent
  skills/pr-review/       language-aware collaborative PR/branch/diff review
  skills/adversarial-review/  N role-partitioned adversaries against a diff (pre-pr/own-pr/foreign-pr);
                          copy it by hand, install.sh places deep-reason and pr-review
claude-project/         → copies into each repo's .claude/
  rules/                  57 auto-loading rules in three layers:
                          craft-* (language-neutral: abstraction, complexity,
                            documentation, domain-modeling, logging, measurement,
                            refactoring, tdd, xunit)
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
  sdlc-gate.py            the differential anti-weakening gate (stdlib + git + toolchain tools)
  review-checklist.md     the gate as a manual checklist (when those tools are missing)
  deep-reasoning-agent.md the 6-section prompt template the deep-reason skill walks
  voicing-document.md     the human-prose writing register
harness/                → per-repo assets: rules, skills, agents, templates
  skills/                 authoring skills (ADRs, stories) — vendored in on request
                          before re-checking) + the optional authoring layer: adr-write,
                          story-write, story-tighten, story-intake (default off — a Tour choice)
  templates/              check.sh / languages / hook snippets + ADR + story templates
memories/               → optional, per-project memory dir
  72 scrubbed methodology memories + MEMORY.md index
install.sh              user-level installer (guards existing config; also --version
                        and --refresh-rules, which re-syncs a repo from a release tag)
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

## The build chain (opt-in, attended-only)

The kit's default is the *interactive* discipline above — the rules, skills, and gate that make one human-in-the-loop session reason and review better. It now also ships an **opt-in build chain**: a pinned Python driver (`harness/chain/`) that runs a story through graded, fail-closed phases — each a headless `claude -p` session whose advance is *re-derived from git refs, never self-reported* — and stops short of the published trunk, leaving a candidate a human crosses.

This is deliberately **not** the source system's full autonomous robot (a worker → tester → reviewer → documenter → finalizer chain under a supervisor daemon with a database-backed queue). That needs a long-running daemon, a DB, and an unattended-execution posture a managed corporate laptop will not host. The chain here is lighter and honest about its limits: its entire state is a **filesystem pinned root** (no daemon, no database), and it is **attended-only until the hardening lands** (`INSTALL-HARDENING.md`, ADR-0005) — it spends real API calls, and the human transplant to trunk is the trust boundary. `core.py` and the loader fail *closed* until the pinned root exists, which is the honest gate.

**Install the chain into a repository on this machine:**

```
./install-chain.sh --dir <target-repo> --terminal open-pr|merge-local
```

This mints a SHA-named immutable tool snapshot outside every target, vendors the kit's rules into the target, and writes a per-target chain profile — the *capability* only. Authoring the target's postconditions, briefs, phase table, fence settings, and pinned examiner copy; minting the dedicated clone; and provisioning the pinned root stay operator work, and the script prints that checklist on exit.

**Learn it.** The step-by-step tutorial with a worked example — install, author the pinned material, run a story, transplant the result — is [`docs/using-the-chain-in-another-repo.md`](docs/using-the-chain-in-another-repo.md). The design narrative, naming every phase, who runs it, and the predicate that decides it happened, is [`docs/sdlc-chain-walkthrough.md`](docs/sdlc-chain-walkthrough.md); the reasoning behind it lives as numbered decisions in [`docs/adrs/`](docs/adrs/) (start at the registry in [`docs/adrs/README.md`](docs/adrs/README.md)).

## Install (user-level)

```
./install.sh              # place the user-level pieces, and stamp what landed
./install.sh --version    # say what this checkout is, and write nothing
```

Copies the skills, the deep-reasoning template, and the gate into `~/.claude`. It will **not** overwrite an existing `~/.claude/CLAUDE.md` or `settings.json`: it backs them up and prints what to merge. Override the target with `CLAUDE_HOME=/path ./install.sh`. It also writes `~/.claude/discipline/KIT-VERSION`, the stamp a later session reads to tell what it has; see [Staying current](#staying-current).

### What the gate needs

Every toolchain needs `python3` (the gate is one standard-library file) and `git` 2.34 or later. `baseline` exits 2 unless `--root` (by default the directory it runs in) is a git checkout of `--sha` with no tracked changes under `--root` and no file there marked skip-worktree or assume-unchanged; untracked files are allowed. `diff` reads git in the directory it runs in. It compares the working tree with the baseline commit through a temporary copy of the index, where `git add --sparse --intent-to-add --pathspec-from-file` marks the untracked files git does not ignore; the repository's own index is not written. The gate picks the toolchain from a marker file at the project root, checked in this order: `build.sbt` (Scala), `pom.xml`, `build.gradle` or `build.gradle.kts` (Java), `pyproject.toml` or `setup.py` (Python), `go.mod` (Go), `package.json` or `tsconfig.json` (TypeScript). `baseline --toolchain` forces one. A full run also needs the tools below.

- **Python.** Check A: `uv`, with ruff and mypy where `uv run` finds them (the project environment or `PATH`), and bandit through `uvx`; mypy runs with `--strict` whatever the project configures, so a new untyped function blocks as `A.mypy`. Checks E and G: `uvx`, which fetches ruff 0.16.7 and complexipy 8.0.1 on first use. Check F: PMD 7.3 or later, and `java`. Check H needs nothing. A missing `uv`, `uvx` or PMD, a ruff or complexipy that `uvx` cannot fetch, or a ruff that `uv run` cannot run exits 2 and names the tool. A mypy that cannot run, or a bandit that fails, reads as no findings for that tool, so confirm `uv run ruff --version` and `uv run mypy --version` work before trusting Check A. bandit also scans the `.venv` that `uv run` creates in the tree; list it under `exclude_dirs` in `[tool.bandit]`.
- **TypeScript.** `node` on `PATH`, and in the project directory's own `node_modules` (the gate installs nothing, so declare them as devDependencies): eslint 9, typescript-eslint 8, typescript, eslint-plugin-sonarjs 4, jscpd 5 with its platform package, and knip 6. Check A also reads the repo's own eslint flat config; a config that fails to load reads as no eslint findings, and tsc is unaffected. Check A and the compile precondition need a root `tsconfig.json` that is not solution-style: without one, or with `"files": []` plus `references` (the Vite template's layout), a type error passes. `baseline` exits 2 when `node`, `node_modules` or one of those packages is missing, but at `diff` time a `tsc` that cannot run reads as "the tree does not compile" (exit 1), because the compile precondition runs before Checks E-H. knip reports eslint-plugin-sonarjs, and jscpd when no `package.json` script runs it, as unused devDependencies, so the branch that adds them blocks on Check E unless the same change lists them under knip's `ignoreDependencies`.
- **Scala 3.** `sbt` on `PATH` and a JDK. Check E runs `sbt clean Test/compile` with `-Wunused:all` forced on and `-Werror` stripped, and refuses a Scala 2 build (exit 2). Check F: PMD 7.3 or later. Checks G and H: `scala-cli` on `PATH` or at `~/.local/share/coursier/bin/scala-cli`; its first run downloads Scala 3.3.8 and scalameta 4.13.9. A missing sbt, PMD or scala-cli exits 2, but at `diff` time an `sbt` that cannot start reads as "the tree does not compile" (exit 1). On Scala 3, Check A reads two linters. scalafix needs the sbt-scalafix plugin and a `.scalafix.conf` with a linter rule that can flag something. DisableSyntax flags nothing until one of its options is on, so a config that lints is `rules = [DisableSyntax]` plus a line such as `DisableSyntax.noVars = true`; a configured rule that can flag nothing reads as zero findings and is not listed under `not_wired`. Only scalafix's linter findings in main sources are read, not rewrite rules such as OrganizeImports, and not test sources. wartremover needs the sbt-wartremover plugin and warts in `wartremoverWarnings`, or in its `Compile / compile` or `Test / compile` form, when sbt runs with `-Dgate.wartScan=true`; they may be on all the time or only under that property. Its findings are read in main and test sources; `wartremoverErrors` is not read. The wart scan compiles from `clean` with the property set, so a build that keeps `-Werror` or `-Xfatal-warnings` under it, or turns warts on as errors, fails that compile once the tree holds a wart, and the gate exits 2. A multi-project build that lists warts for some projects and none for others is read as set up, and the projects with none are not scanned. Without a plugin, with no scalafix rules configured, or with no warts in `wartremoverWarnings` under the property, `diff` lists `A.scalafix` or `A.wartremover` under `not_wired`. That listing leaves the exit code as it is, so a Scala pass with both listed covers only the compile precondition and Checks B-D and E-H. A branch that wires a linter the baseline did not run blocks on every existing finding of it, since the baseline recorded none. A scalafix or wart scan that fails for another reason, such as an unknown rule or a `.scalafix.conf` that does not parse, exits 2. A branch that removes a linter the baseline ran exits 2 too, or blocks as Build when the removal leaves a build that does not load. Checks E-H need no plugin. Check E and the wart scan compile one module at a time, since modules compiled in parallel interleave their warnings, and Check E exits 2 on a warning whose header and message it cannot pair. On a build that sets both `-Werror` and `-Wunused`, a new unused symbol fails the compile precondition before Check E runs, so it blocks as Build rather than E. A full run took about 187 to 193 s per phase on a 368-file, 9-module build (four phases); compiling one module at a time added 45 to 51 s per phase on average (two series).
- **Go.** `go` and golangci-lint 2.x on `PATH`. golangci-lint bundles the linters Checks E, F and G use (unused, unparam, revive, dupl, gocognit), and Check H runs a small program with `go run`. Check A runs `golangci-lint run ./...` with the repo's own config; a config it cannot load, such as a v1 `.golangci.yml` under 2.x, reads as no Check A findings with no message, so confirm `golangci-lint run ./...` works first. A missing `go` or golangci-lint exits 2, but a `go` on `PATH` that fails at `diff` time reads as "the tree does not compile" (exit 1). The compile precondition runs `go test -run=^$ ./...`, which runs each package's `TestMain`, so a `TestMain` that exits non-zero reads as a compile failure too. The flow under [Using it](#using-it) gives each gate command an empty golangci-lint cache, which cost about 130 to 160 s of golangci-lint per command on a 2,045-file module, against 20 s warm.
- **Java.** Check A needs `checkstyle` on `PATH`; without it, Check A prints a "skipping" line and records no findings. The compile precondition uses `mvn`, `./gradlew` or `gradle`. Checks E-H are not wired for Java, and the report lists them under `not_wired`.

PMD is found as `pmd` on `PATH`, else `$PMD_HOME/bin/pmd`, else under `~/.local/opt/pmd-bin-*/bin/pmd`. PMD ships as a zip on its GitHub releases page; unzip a single version there, since the Scala lookup sorts those names as strings and picks `pmd-bin-7.9.0` over `pmd-bin-7.27.0`. Measured with git 2.43.0, Python 3.12.3, uv 0.10.12, PMD 7.27.0, node 24.14.0 (eslint 9.39.4, typescript-eslint 8.63.0, typescript 6.0.3, eslint-plugin-sonarjs 4.2.0, jscpd 5.2.0, knip 6.35.1), sbt 1.12.11 with Scala 3.3.8 on OpenJDK 25, and golangci-lint 2.12.2.

`--no-static` needs only `python3` and `git`. It runs Checks B, C and D and skips Check A, the compile precondition and Checks E-H; the report lists each skipped E-H check under `not_wired` and sets `no_static` to true. `--coverage`, if given, still runs its tool. Pass the flag to both `baseline` and `diff`; a mismatch exits 2.

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
- **`/adversarial-review`** fans out N fresh-context adversaries decorrelated by role against a diff (modes `pre-pr` / `own-pr` / `foreign-pr`) — the tier-two red-team above `pr-review`, reserved for detector-class, sensitive, contested, or hairy-state changes; it hunts what no check encodes yet and never votes.
- **The gate** enforces anti-weakening on a branch: no new ruff/mypy/bandit errors (Check A; other linters on other toolchains), no new suppressions, no new skipped tests, no assertion-count loss versus the merge-base, and none of Checks E-H: new unreferenced code, a new clone, a function over cognitive complexity 15 that is new or grew, or a new single-implementor abstraction. Run it in the branch checkout, from the project directory (the top of the repository, or the subdirectory that holds the project); the work does not have to be committed:

  ```
  unset $(git rev-parse --local-env-vars)
  BASE=$(git merge-base HEAD origin/main)
  P=$(git rev-parse --show-prefix)
  WT=$(mktemp -d); OUT=$(mktemp -d); GC1=$(mktemp -d); GC2=$(mktemp -d)
  git worktree add --quiet --detach "$WT" "$BASE"
  if [ -d node_modules ]; then ln -s "$PWD/node_modules" "$WT/${P}node_modules"; fi
  (cd "$WT/$P" || exit 2; GOLANGCI_LINT_CACHE="$GC1" python3 ~/.claude/discipline/sdlc-gate.py baseline --sha "$BASE" --out "$OUT" >&2) &&
    GOLANGCI_LINT_CACHE="$GC2" python3 ~/.claude/discipline/sdlc-gate.py diff --baseline-dir "$OUT"
  rc=$?
  git worktree remove --force "$WT"; rm -rf "$OUT" "$GC1" "$GC2"
  (exit "$rc")
  ```

  Replace `origin/main` with the branch the work merges into, and if `CLAUDE_HOME` was set at install, use the gate path `install.sh` printed. `P` is the project's path in the repository, empty at the top. The first line unsets git's per-repository variables, the ones `git rev-parse --local-env-vars` lists, such as `GIT_DIR` and `GIT_INDEX_FILE`; a git hook inherits them, and pasted into a shell the line clears them there too. The last line returns the gate's exit code: 0 pass or advisory, 1 blocked, 2 could not run. Exit 1 is not always a finding: a Python traceback on stderr exits 1 with no report, and a compile tool that fails at `diff` time blocks as Build (see [What the gate needs](#what-the-gate-needs)). `baseline` scans the tree at `--root`, by default the directory it runs in, and exits 2 unless that tree is a checkout of `--sha` with no tracked changes under it and no file marked skip-worktree or assume-unchanged, which is why it runs in a worktree at `BASE`; untracked files there are allowed. A worktree added from a sparse checkout inherits its cone, so there `baseline` exits 2 until `git -C "$WT" sparse-checkout disable` runs after `git worktree add`; on a checkout made sparse with `git sparse-checkout set`, that left the checkout itself as it was. The worktree has no `node_modules`, hence the link for TypeScript. Each gate command gets its own empty golangci-lint cache because golangci-lint replays a cached finding under the path of whichever checkout first analyzed the same code, so with a shared cache the findings already in unchanged Go packages can block as new, pass under another checkout's paths, or exit 2 once that checkout is deleted. The baseline's own report goes to stderr, and a baseline that cannot run stops the block before `diff`, which would read the unfinished `$OUT` and exit 1 with a traceback. `diff` compares the working tree with `BASE`, uncommitted changes included: staged and unstaged changes, and untracked files. git's reads, the rename map and Check F's added lines, skip the files git ignores, and so do ruff's Check A run and TypeScript's knip, but the other scanners walk the whole project directory, ignored files included (measured on Python). The worktree at `BASE` holds no ignored files, so an ignored source file in the branch checkout, such as generated code, reads as new: on Python one blocked `A.mypy`, B, E and G, though not `A.ruff` or F. A move, committed or not, is followed as a rename only when git pairs the two paths, by default when they are at least 50 percent similar; a move with heavy edits reads as a deletion plus an addition, and the moved file's existing findings count as new. For a project in a subdirectory of its repository, run the block from that subdirectory: `P` carries the path into the worktree, and the report keys every path from the project directory. A project that does not exist at `BASE` has nothing to compare with, so the block exits 2 at the `cd`. A file moved into the project from elsewhere in the repository reads as added, so its findings count as new, and a file moved out reads as deleted. For the mode that needs only `python3` and `git`, add `--no-static` to both gate commands. What each toolchain needs is under [What the gate needs](#what-the-gate-needs); without those tools, follow `review-checklist.md` by hand.

  To run the block as a pre-commit hook, put it in a file named `pre-commit` in the directory `git rev-parse --git-path hooks` prints (`.git/hooks` unless `core.hooksPath` is set), after a `#!/usr/bin/env bash` line, and make the file executable; linked worktrees run the same hook. git runs a hook at the top of the working tree, so for a project in a subdirectory put `cd <project directory> || exit 2` before the block. git exports `GIT_INDEX_FILE` to a pre-commit hook, and `GIT_DIR` as well in a linked worktree. The gate leaves them out of its own git commands, and the block's first line clears them for its other commands: with `GIT_INDEX_FILE` set, a hook's `git worktree add` wrote `BASE`'s tree into the index `git commit -a` was about to commit, and with `GIT_DIR` set, `P` came out empty for a project in a linked worktree's subdirectory. The gate judges the working tree, not the index being committed. Unstaged changes and untracked files that the commit leaves out still count, so a smell in one of them blocks the commit, and a staged smell whose fix is unstaged passes and is committed. Before a commit that leaves changes out, set them aside with `git stash push --keep-index --include-untracked`, commit, and bring them back with `git stash pop`. That sequence was tested by hand around `git commit`, setting aside an unstaged edit and an untracked file; stashing from inside the hook is untested.

- **SpotBugs (Java) is implemented fail-closed and deliberately outside default Check A** until a compiled pilot exists: it analyzes bytecode, and a source-snapshot differential cannot compile a tree, so wiring it into the default path would fail *open* on a source-only repo — instead it raises `SpotBugsOperationalError` when the tool is present but no `target/classes`/`build/classes` bytecode is found. The enabling path is a compiled pilot repo (bytecode on disk), where FindSecBugs can then ride the same SpotBugs engine as the Java security scanner.

## Refreshing and provenance

The rule layer has three upstreams: the SDLC pack (the guides, the gate, `decoupling`/`writing-style`), a Go-harness repo (the `craft-*`/`go-*`/`python-*` rules), and a Scala harness repo (the `scala-*` rules, authored there against the Scala canon rather than ported from the Go-harness). All of it is scrubbed of machine, project, and personal identifiers; `./scrub-gate.sh` enforces that across four checks (infra/PII anywhere, chain vocab and harness vocab in the scrubbed surfaces, and a dangling-cross-ref check) and is the last step before packaging.

Two house conventions are resolved in-kit where the sources disagreed: docstrings are **prose-only** (the source's Google-style `Args:/Returns:/Raises:` mandate was stripped from `python-style`), and **Pydantic is scoped to the validated LLM/external boundary** (no blanket ban). The long-form **guides have been fully neutralized**: all project-specific references have been rewritten to a generic order/account/pipeline domain, so the DDD/GOOS/Fowler/Liskov teaching stands on its own without assuming any particular system. A running example (an account evaluating proposed transactions against limits, approving or rejecting them, recording outcomes) carries the concrete illustrations where the patterns need one.

`scripts/refresh-from-pack.sh` rebuilds only the pack-sourced pieces from a pack tag today; the harness-sourced rules are not yet wired into an automated refresh (which upstream is canonical on collision is an open decision, deferred):

```
scripts/refresh-from-pack.sh <pack-checkout-dir> <tag>   # pack pieces; then: ./scrub-gate.sh
```

Per-release notes and upstream source provenance are in `CHANGELOG.md` (which superseded the former `PACK_SOURCE_TAG`).

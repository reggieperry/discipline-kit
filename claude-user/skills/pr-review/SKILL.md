---
name: pr-review
description: "Collaborative PR / branch / diff review. Use whenever the operator asks to review a pull request, a branch, or a diff (\"review this PR\", \"/pr-review\", \"look over this branch\"). Language-aware: detects the target language from the repo, runs the gate first, LOADS THE REVIEWED REPO'S OWN .claude/rules (go-*.md / python-*.md / craft / rig rules) for the language and project specifics, then applies the embedded language-neutral review core. Works in any repo — Go, Python, or other."
auto_invoke: false
---

# /pr-review — language-aware collaborative review

The review the operator and I do together, made portable. The method is global; the language specifics come from the **reviewed repo's own rules**, not from this skill. So it works in a Go repo and a Python repo without carrying the wrong checklist into either.

If the operator typed `/pr-review [<PR# | branch | path>]`, run it now on that target. If they asked in prose ("review this PR / branch / diff"), run it. Default target: the current branch's diff against its base.

## Step 1 — Scope the diff

Get the exact change set under review, and its base:

- A GitHub PR: `gh pr view <N> --json headRefName,baseRefName,title,body` then `gh pr diff <N>`.
- A local branch: `git diff $(git merge-base HEAD origin/<base>)...HEAD` (base is usually `main`).
- A path or staged set: `git diff [--staged] -- <path>`.

Read the whole diff before judging any part of it. Note the base — findings are relative to it.

## Step 2 — Detect the target language(s)

The repo signals its primary language (`go.mod` → Go; `pyproject.toml` / `setup.py` → Python), but classify **each changed file by extension** and review it under the matching layer — a diff routinely mixes languages:

- `*.go` → **Go**
- `*.py` → **Python**
- `*.sh` / bash scripts → **Shell** (a first-class target here)
- otherwise infer from extension; if no layer fits, the neutral core + craft lens still apply.

## Step 3 — Run the gate first

Before reading the diff for taste, run the language-appropriate gate and read its **full output, causal-first** (compiler/type errors before test logs — do not summarize them). A red gate is finding #1; do not launder it.

- **Go:** `go build ./...` → `go vet ./...` → `golangci-lint run` → `go test ./...` (add `-race` for concurrent code).
- **Python:** `uv run ruff check .` → `uv run mypy .` → `uv run pytest`.
- **Shell:** `shellcheck <files>` and `bash -n <file>` (syntax-only parse).

If the repo ships a gate script (e.g. the pack's `sdlc-gate.py`, or a Go gate), prefer it — it encodes the anti-weakening baseline (no new suppressions, no skipped tests, no assertion-count loss versus merge-base).

## Step 4 — Load the reviewed repo's own rules (the language + project specifics)

This is the step that makes the skill language-aware. Find and read the rules the repo carries for itself:

```bash
ROOT="$(git rev-parse --show-toplevel)"
ls "$ROOT/.claude/rules/" "$ROOT/.claude/rules/project/" 2>/dev/null
```

Load, in priority order, whatever exists:

1. **Per-language rules matching each changed file's language** — `go-*.md` (`go-style`, `go-errors`, `go-types`, `go-concurrency`, `go-modules`, `go-testing`, `go-llm`); `python-*.md` (same shape). These carry the authoritative language idioms and the language-specific anti-weakening list — use them over the embedded baseline below. Note there may be **no dedicated shell layer** (in some repos, shell is covered by the craft rules plus the embedded shell baseline below).
2. **Craft-core rules** — `craft-*.md` (complexity / abstraction / tdd / refactoring / domain-modeling). These are language-neutral and glob across `**/*.go`, `**/*.sh`, and `**/*.py`, so they apply to every changed file regardless of language. If the repo ships none, the embedded craft lens below covers it.
3. **Rig-specific rules** — the *reviewed project's own* domain, architecture, security, and review rules (`*-<project>.md`, `architecture.toml`, `review-*.md`, `security-*.md`, a slop rubric). When reviewing a cloned target repo, this layer is the **target's** rules, not the reviewer's; the reviewing repo may ship none. These bind hardest: a repo may *specialize* the general discipline but never *weaken* it.

**Honor each rule's `paths:` glob** — apply a rule only to the changed files its glob covers. `go-llm.md` is scoped to LLM-call sites (globs like `*llm*`, `*schema*`), so it bites on an LLM-call file but not a plain helper. Rules auto-load by glob only when *editing*; during a review you are reading a diff, so load them explicitly here and match each to the files it governs. If the repo has no `.claude/rules/`, fall back to the embedded baselines at the end of this file and say so in the output.

## Step 5 — Apply the language-neutral review core (embedded below)

Run the diff against the neutral core: the defensive habits, the security subset, claims-need-tests, idempotency-invariant naming, and the craft lens. These hold in any language.

## Step 6 — Apply the language layer

Apply the per-language rules loaded in Step 4 (preferred), or the embedded per-language baseline (Go / Python) if the repo shipped none.

## Step 7 — Emit findings

Structured, severity-tiered, evidence-cited:

- Lead with the **gate result** (green, or the exact failures).
- Group findings: **blocking** (correctness, security, gate regression) → **should-fix** (design, missing test, leaky abstraction) → **nit** (style, naming).
- Each finding: `file:line` · what · why it matters · a one-line suggested fix.
- **Verify before asserting** — re-read the lines you cite; do not cite a line number from memory. Quote only what you read. Do not invent identifiers.
- Separate "this is wrong" from "I'd prefer" — label preferences as such.

---

## Embedded language-neutral core (fallback + baseline)

**Defensive habits** (reach for these when the surface appears):

1. **Validate at boundaries, not in the middle.** Untrusted or unbounded input gets explicit defense at the entry point — explicit timeouts on external calls, bounds on sizes, sanitized error messages out, identifiers from an external system validated against the source before use. Upstream contracts are hopes, not guarantees.
2. **Plan for cancellation and cleanup, not just exceptions.** Resource cleanup belongs on the abnormal-exit path (a `finally` / `defer` / teardown), not only the happy path. Shutdown is a normal exit. Don't lump cancellation in with error handling.
3. **Configuration is part of the public API.** A tunable an operator might change at runtime belongs in config, not as a literal at the call site — and document the invariant relationships between interdependent values. (But don't *invent* a knob a strong default would cover.)
4. **Migrations are symmetric.** Up and down get equal rigor; destructive downgrades refuse when they'd drop human/analyst data; a new table is registered in the validation list; tested up→down→up on a real DB.
5. **"Disabled" defaults need a visible re-enable hook.** Commented-out auth/CORS/guards rot silently — leave the production-correct value adjacent so re-enabling is a one-line diff that shows up in review.
6. **Concurrency invariants belong in the docstring.** "Idempotent" / "thread-safe" / "no-op on retry" are claims; name the lock or predicate that makes the claim true, with its `file:line`.

**Security subset** (language-neutral):

- Sanitize error detail that flows out through an API — class/category only outward, full detail to server-side logs.
- Bound every string and every array that came from an LLM or a document (max length, max items).
- Byte-budget anything concatenated into an LLM prompt, and mark untrusted data as data, not instructions.
- Refuse a destructive operation if sensitive data would be lost.
- Explicit timeout on every external call; bound every fan-out.
- Parameterize every SQL statement — no string interpolation into queries.

**Claims need tests.** "No-op" / "idempotent" / "handles X" in prose, untested, is aspirational. A test must *discriminate* — fail under the claim-false branch. Watch for assertions satisfied by every execution path (a returncode-only check that both branches pass).

**Craft lens** (the modularity/design read):

- **Depth** (Ousterhout): a module's interface should be much narrower than its implementation; a wrapper whose interface mirrors what it wraps is net-negative. Kill pass-through methods and pass-through variables.
- **Substitutability** (Liskov): a subtype must keep the supertype's semantics, not just its signatures; a leaked representation (a getter handing out an internal collection) is the bug.
- **Smells** (Fowler): duplication, long function, feature envy, primitive obsession, shotgun surgery — name the smell, propose the move.
- Define errors out of existence where you can; most scattered `try/except` (or swallowed errors) is an abdication.

## Embedded Go baseline (used only if the repo ships no `go-*.md`)

- Every goroutine has a clear, owned stop — no leak; a `context` is propagated and its cancellation honored.
- No swallowed errors (`_ = err`); wrap with `%w` to preserve the chain; sentinel errors compared with `errors.Is`.
- `defer` inside a loop piles up resources — scope it to a function.
- Loop-variable capture in closures/goroutines (pre-1.22 semantics) — bind explicitly.
- No writes to a nil map; watch slice aliasing across `append`.
- Shared mutable state is race-free (run `go test -race` on concurrent code); fan-out uses `errgroup`.
- Interfaces are narrow and accepted at the consumer; return concrete types.
- Table-driven tests; no test asserts implementation internals over observed behavior.

## Embedded Python baseline (used only if the repo ships no `python-*.md`)

- Pydantic: required `list[X]` accepts `[]` — add `min_length=1` if "required" means non-empty; cross-field rules in `model_validator(mode="after")`.
- SQLAlchemy: `sa.text(...)` for partial-index `postgresql_where` (the mapped column isn't resolvable in `__table_args__`); don't `commit()` between two writes that must be atomic; `with_for_update(of=...)` on outer joins.
- Async: sync `def` endpoints run in a threadpool — `asyncio.get_running_loop()` raises off the loop thread; `task.cancel()` does not stop an already-running `to_thread` worker (guard the write with a WHERE predicate); capture the loop at lifespan startup.
- Translate library exceptions at your module boundary — don't let `openpyxl.KeyError` escape a public function.
- `list.count(x)` inside a comprehension over the same list is O(n²) — use `Counter`/`set`.

## Embedded Shell baseline (no dedicated shell rule layer — pair with the craft core)

- `set -euo pipefail` at the top; a failed command, a broken pipe, or an unset variable must not pass silently.
- Quote every expansion (`"$var"`, `"${arr[@]}"`) — unquoted word-splitting and globbing is the most common shell bug.
- `[[ … ]]` over `[ … ]`; `(( … ))` for arithmetic.
- `local x; x=$(cmd)` on separate lines — combined, the `local` masks the command's exit code. Check exit codes where `set -e` won't catch (inside `if`, `||`, mid-pipeline).
- `trap '…' EXIT` for cleanup; `mktemp` for temp files; don't parse `ls`.
- ShellCheck-clean; any `# shellcheck disable=` carries a reason.

---

The canonical, fuller versions of the neutral core live in this kit's methodology memories (`feedback_pr_review_patterns`, `feedback_security_when_writing_code`, `reference_python_pr_gotchas`, `feedback_claims_need_tests`, `feedback_idempotency_semantics`, the craft canon). This skill embeds a working subset so it stands alone in any repo; the reviewed repo's `.claude/rules/` are authoritative where they exist.

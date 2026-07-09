# Differential review checklist (anti-weakening gate)

The manual form of `sdlc-gate.py`. Run the script when `uv` is available — it is exact and mechanical. Use this checklist when you cannot run the script, or as the human pass over its verdict.

The principle: **a branch may add capability but must not weaken the static-analysis floor it inherited.** Every check is differential — measured against the merge-base, not against zero. A pre-existing error is not this branch's problem; a *new* one is.

## Baseline

Establish the comparison point before reading the diff:

```
BASE=$(git merge-base HEAD origin/main)     # the target branch's tip the work forked from
```

All four checks compare the branch tip against `BASE`. Identity is the **(file, error-code) pair** — message text is ignored (type names and contextual detail legitimately change across edits). Renames are followed (`git diff --name-status -M`), so moving a file is not counted as deleting its asserts.

## Check A — no new ruff / mypy / bandit errors

Run each tool at `BASE` (in a scratch worktree) and at the branch tip; compare per (file, code):

```
uv run ruff check . --output-format=json
uv run mypy . --show-error-codes --no-error-summary
uvx bandit -c pyproject.toml -r . -f json
```

- A per-file count increase for a (file, code) pair where the **global** count for that code also rose → **block** (a genuinely new error).
- A per-file increase cancelled by a decrease elsewhere (same global count) → **advisory** (a relocation, not a new defect).

## Check B — no new suppressions

Scan all `.py` for suppression directives; none may be added versus `BASE`:

- `# type: ignore[code]`, `# type: ignore` (blanket), `# noqa: code`, `# noqa` (blanket), `# pyright: ignore`, `# nosec B###`.
- Targeted suppressions count under their specific code; blanket forms count under a `BLANKET` key. Replacing a targeted suppression with a blanket one registers as a new key — scope-broadening is caught, not laundered.
- Use the **space-separated** `# nosec B603 B607` form; bandit silently ignores the comma-separated form, so the comma form suppresses nothing at runtime.

## Check C — deleted test files (advisory)

Any file removed under `tests/` is surfaced as an advisory. Not an automatic block — a legitimate consolidation happens — but it must be explained in the PR, not silent.

## Check D — no pytest weakening

Per test file, compared across the rename map:

- **Skip markers** (`@pytest.mark.skip`, `@pytest.mark.xfail`, `@pytest.mark.skipif`) — the count must not increase. Any increase → **block**.
- **Assertion count** (`assert` keywords under `tests/`) — must not decrease. A drop → **block**, unless it is a declared, mechanically-verified migration: the lost assertions reappear verbatim in a named sibling test file (same predicate text, same or greater count). Absent that proof, a drop is a weakening.

## Verdict

- Any block → **fail** (return for rework).
- Blocks empty, advisories present → **advisory** (proceed, but address or explain).
- Both empty → **pass**.

## Notes

- The gate is differential, so it never punishes inherited debt — only regressions the branch introduces.
- Known v1 gap: within-(file, code) swaps (one error of a code replaced by a different error of the same code on another line in the same file) are not caught — that would need AST-anchored identity.
- The script lives at `sdlc-gate.py` (this directory). `baseline --sha <BASE> --out <dir>` captures; `diff --baseline-dir <dir>` compares and exits non-zero on fail.

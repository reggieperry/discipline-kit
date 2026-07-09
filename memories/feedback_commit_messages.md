---
name: Commit messages must be rich, multi-paragraph, with symptom + cause + fix + validation
description: Bug fix and refactor commits need explanatory bodies (why-not-what); one-liners are wrong for anything beyond trivial doc fixes; always include Co-Authored-By trailer; closes-#N keywords need care to avoid accidental umbrella closures
type: feedback
volatility: durable
---
Every non-trivial commit needs a structured commit message body, not just a subject line.

**Why:** The user has consistently asked for explanatory commits. Rich messages serve as a future-archaeologist diary — they show up in `git blame`, `git log`, GitHub PR views, and the verification-discipline rule ties to this (avoid composing "what happened" details from memory in future sessions; the commit message IS the artifact). When commits land via `gh pr merge --squash`, the squashed message inherits the title and body provided to `--body`, so even one-PR-many-commits work needs the rich form.

**How to apply:**
- **Subject line**: short, imperative, prefixed by area when useful (e.g., `fix(api): ...`, `docs: ...`, `settings: ...`, `tests: ...`, `chore: ...`). Under ~72 chars.
- **Body paragraphs** (always present for fixes, refactors, and design changes):
  1. *Symptom* — what failed at runtime, with the actual error message if available
  2. *Root cause* — why it failed, with file:line references
  3. *Fix* — what changed and why this is the right approach
  4. *Validation* — what was run to confirm (the gate/lint/typecheck, specific tests, manual run)
- **Trailer**: `Co-Authored-By: Claude <noreply@anthropic.com>`
- **Use heredoc** (`git commit -m "$(cat <<'EOF' ... EOF)"`) for multi-line messages — preserves formatting reliably.

**Closes-#N keyword caveats:**
- `closes #N` works as expected — auto-closes issue N on merge.
- `closes #N item X` does NOT preserve the "item X" qualifier — GitHub closes the entire umbrella issue. Pattern hit once: an umbrella issue closed prematurely by a partial-item commit. Workaround: use the keyword only on commits that fully close the issue, and reference partial work as descriptive prose ("addresses #N item A").
- For umbrella issues with multiple checkbox items, prefer to never use `closes #N` on partial-item commits and instead update the issue body or comment with status as items land.

**Squash-merge body**: when running `gh pr merge --squash --body "..."`, write the body explicitly. Don't rely on the default (which concatenates all commit messages and produces noise). The body should summarize the PR's intent and reference any relevant issues — that's what lands on main.

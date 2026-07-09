---
name: pr-closes-every-issue
description: "PR descriptions must list `Closes #N` for every tracked issue the PR fixes, including same-file adjacent issues; otherwise issues linger open and downstream automation can re-spawn redundant work"
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

When a PR fixes multiple tracked issues — typically because adjacent work touches the same file or class — every closed issue must appear as a `Closes #N` line in the PR description. GitHub's auto-close machinery reads these literally; an issue not named stays OPEN forever, regardless of whether the code change shipped the fix.

**Concrete failure mode:** a PR shipped fixes for two modules that each had a tracked issue, but the PR description named neither in a `Closes` line. Both issues stayed open.

Days later, an automation that re-spawns work from open labeled issues picked one up and slung a fresh work item. The worker's pre-flight correctly identified the fix as already-shipped and escalated rather than duplicating the work — exemplary behavior, but the time was wasted, and the duplicated work items compounded the attention cost.

**Why:** Two compounding effects:
1. **GitHub's auto-close is literal** — only `Closes #N` / `Fixes #N` / `Resolves #N` are honored. Mentioning `#N` in prose without one of those verbs does nothing.
2. **Re-spawn automation uses label + open-status as eligibility** — any open issue with the trigger label is fair game for re-spawn, even if the underlying fix is already on main.

**How to apply:**

1. **When committing or PR-ing work that fixes tracked issues**, do the grep yourself: `git diff main...HEAD --name-only` shows which files changed; for each, run `gh issue list --state open --search "<filename>"` to find issues targeting that file. List every match in the PR description as `Closes #N`.

2. **When manually labeling issues with a label that drives re-spawn eligibility**, grep against current main first: has the target file/line been modified since the issue was filed? If yes, read the diff — if the diff applies the suggested fix, close the issue with a `superseded by commit <SHA>` comment and skip the labeling.

3. **Future audit candidate**: scan all open labeled issues against current main for already-applied fixes. The audit is N issues × one `git log -p -- <path>` lookup each.

**Cross-references:**
- `[[feedback_subc_manual_invocation_only]]` — the sibling discipline that keeps re-spawn automation from firing unattended; this memory adds the upstream defense (close issues at PR time)

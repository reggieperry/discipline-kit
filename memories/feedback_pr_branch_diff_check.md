---
name: Verify PR branch contents before pushing
description: Before `gh pr create`, run `git log origin/<base>..HEAD --oneline` and read every line — confirm the branch contains only the commits the PR description claims.
type: feedback
volatility: durable
---
After `git push -u origin <branch>` and before `gh pr create`, enumerate every commit that will be in the PR via:

```bash
git log origin/<base-branch>..HEAD --oneline
```

Read every line. The list should match the PR description's stated scope. Any unexpected commits — especially commits authored by other actors (automated agents, prior incomplete work, foreign tooling) — are a red flag and must be resolved before the PR is opened.

**Why:** A workaround PR was once opened from a feature branch that had silently inherited nine commits from a prior automated run on the same working tree. `gh pr view --json mergeable,mergeStateStatus` returned CLEAN/MERGEABLE and the small-change auto-merge passed, so the merge proceeded — and the squash-merge captured all ten commits under the workaround's title. A size-bound review check (≤200 LOC, ≤10 files) would have caught it; the pre-push commit-list inspection would have caught it sooner and prevented the misleading squash-commit title from becoming permanent in `main`.

**How to apply:** Make this a fixed step between push and `gh pr create`. If unexpected commits appear, stop and choose: rebase the branch onto the right base, cut a fresh branch off the right base and cherry-pick only the intended commits, or fix the working-tree state that produced the contamination. Applies in particular when the same working tree was used by an automated run, a long-lived agent session, or any other tooling between the most recent merge to `main` and the workaround commit.

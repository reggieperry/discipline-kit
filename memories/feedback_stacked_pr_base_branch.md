---
name: stacked-pr-base-branch
description: "Before merging a stacked-on PR with --delete-branch, update the upper PR's base to main first. GitHub auto-closes stacked PRs when their base branch is deleted, and closed PRs can't be reopened after base-branch deletion."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

# Stacked PRs: update the upper's base before merging the lower

When PR-B is stacked on PR-A (base = PR-A's branch), and PR-A is about to merge with `--delete-branch`, **update PR-B's base to `main` FIRST**.

```bash
# Before merging PR-A:
gh pr edit <PR-B> --base main
gh pr merge <PR-A> --squash --delete-branch
```

Otherwise GitHub auto-closes PR-B when PR-A's branch is deleted, and **cannot reopen it** ("GraphQL: Cannot change the base branch of a closed pull request"). Recovery is creating a fresh PR with a new number, which fragments the review history.

**Why:** Observed after merging a lower PR with `--delete-branch` while an upper PR was stacked on its branch. The upper auto-closed. Trying to reopen it with base=main produced the GraphQL error. Recovery required:
1. Cherry-pick the upper's commit onto a fresh branch from main (rebase produced add/add conflicts because the squash-merge collapsed the lower's individual commits)
2. Force-push the rebased branch
3. Open a fresh PR replacing the closed one

The fix is preventive: change the upper's base BEFORE the lower merges. Then the lower merge proceeds, the upper's diff against main naturally narrows to just its own commits, and review continuity is preserved.

**How to apply:**

1. Before invoking `gh pr merge <lower>` with `--delete-branch`, check `gh pr list --search "base:<lower-branch>"` for stacked PRs.
2. For each one: `gh pr edit <upper> --base main`. (This is allowed while the upper is still OPEN.)
3. Proceed with the lower's merge.
4. The upper's diff now reads cleanly against main without rebasing — GitHub recomputes the merge-base.

If the upper's branch was actually built ON TOP of the lower's commits, a rebase IS still needed at some point (to drop the duplicated patches). But the rebase can happen on the upper's schedule, not as emergency recovery.

**Alternative if you don't want the rebase awareness up front:** don't use `--delete-branch` on the lower. Merge with `--squash` only, leave the branch in place. Then the upper's base branch isn't deleted; upper stays open; rebase + base-update can happen at leisure.

**Trade-off:** un-deleted branches accumulate on the remote and need separate cleanup. Worth it if stacked PRs are routine.

## When stacked PRs become routine

If stacked PRs become common (likely, for narrow sub-stories), the preventive base-update approach should become muscle memory.

Cross-references:
- [[pr-branch-diff-check]] — verify branch contents before pushing; same family of "look before destructive action"
- [[completion-state-vs-authorization]] — narrow interpretation of completion reports; "merge with --delete-branch" is narrow; doesn't authorize cascade effects on stacked PRs

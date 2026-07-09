---
name: Completion phrasing — "X is done" means the user's part is complete, not the whole pipeline
description: When the user reports completion, default to the narrower interpretation (their part finished) and confirm before taking large follow-on actions
type: feedback
volatility: durable
---
When the user says "X is done" / "X is good" / "X is approved" in the middle of a multi-step pipeline where their part and Claude's part overlap, default to the **narrower** interpretation: their part is complete, not the entire pipeline. Confirm before taking large follow-on actions on that basis.

**Why:** After recommending several PRs as "skim and merge," the user replied "the skim-and-merge ones are done." Read as "merged," this prompted purging the working copies on that basis. The user actually meant "I've reviewed them and they're good — you merge." Recoverable (remote branches survive; merges later succeeded with one merge-conflict batch), but it caused a confused exchange. Both sides can share the lift: the user uses clearer imperatives, Claude defaults to the narrower scope.

**How to apply:**
- "Merge them" / "Ship them" / "Reviewed, merge them" / "Approved, you merge" — these are explicit handoffs; act.
- "X is done" / "X is good" / "X is approved" — ambiguous; could mean state-of-the-thing or state-of-their-review. Default to "their review is done." Before taking the next destructive or visible step (merge, push, delete, comment, file), surface a quick "want me to merge those?" / "should I take the next step?" rather than assuming.
- The cost of one extra confirmation message is much lower than the cost of acting on the wrong scope and having to reconcile after.
- This is *especially* true for actions that are visible to others (merge, comment, push) or destructive (delete, purge).

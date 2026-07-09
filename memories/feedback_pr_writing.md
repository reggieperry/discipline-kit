---
name: PR writing — compact, no local doc refs
description: When drafting PR descriptions, keep prose compact and to the point. Do not reference documents generated only in local sessions (commit messages, plan memos, design notes, etc.).
type: feedback
volatility: durable
---
PR descriptions should stay compact and self-contained.

**Why:** PR readers don't have access to local
session artifacts — referencing them in the PR body produces dead links
and forces reviewers to take claims on faith. A PR's value is in the diff
+ a tight summary; long context-setting prose dilutes that.

**How to apply:**
- Lead with what changed and why; lean on the diff for the how.
- No links to or quotes from session-local docs (an orchestration plan
  memo, design notes, an engineering analysis if not in the repo, etc.).
- Cite only artifacts a reviewer can actually open: files in this repo,
  issue/ticket numbers, sibling PRs.
- Compact bullet lists over essays. Trim adjective ladders ("complete
  and robust and durable" → just say what it does).
- The "deferred work" callouts stay — but as one-line items,
  not paragraphs.
- Reviewer pointers to external code (a collaborator's branch source files) are
  fine — they exist and reviewers can fetch them.

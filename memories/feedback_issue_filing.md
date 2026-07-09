---
name: Umbrella GitHub issues for related-bug audits, separate issues for one-off bugs
description: When an audit surfaces multiple related bugs, file ONE umbrella issue with checklist items A/B/C/...; for individual bugs found outside an audit, file standalone issues
type: feedback
volatility: durable
---
When deciding how to track multiple bugs in GitHub, follow the umbrella-vs-standalone pattern.

**Why:** An umbrella issue ("audit — N bugs surfaced") collects related findings as a single issue with checkbox items A, B, C, …, which tracks the findings without cluttering the issue list. Standalone issues are used for individual bugs found outside an audit. This pattern keeps the project's issue list manageable across many iterations.

**How to apply:**
- If filing **2 or more related issues found in the same audit/exploration**, propose an umbrella with checkboxes. Include a "Status as of \<SHA\>" comment to track progress without closing the umbrella prematurely.
- If filing **1 standalone issue** for a single bug, just file it directly with title + body following the existing repo style.
- **Do not write commit messages with "closes #N item X"** — GitHub's keyword parser ignores the "item X" qualifier and closes the entire umbrella issue. (Observed once: an umbrella closed prematurely by a "closes #N item A" commit.) Instead use "(closes #N item X)" only as descriptive prose, and reopen + comment if the umbrella accidentally closes.
- The closure comment when reopening an umbrella should list each item's status, what fixed it (with commit SHA), and what remains.

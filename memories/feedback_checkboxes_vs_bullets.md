---
name: Use bullets, not checkboxes, for non-tracked lists
description: Markdown `- [ ]` checkboxes only when the items will literally be checked off; otherwise plain bullets
type: feedback
volatility: durable
---
When writing prose for human readers — PR descriptions, issue bodies, design docs, summaries — use plain bullets `-` for lists. Reserve markdown checkbox syntax `- [ ]` for places where the boxes are actually intended to be checked: acceptance criteria that someone verifies and ticks, explicit task lists with state tracking, kanban-style trackers.

**Why:** Empty checkboxes in a PR test-plan or feature-overview signal "this is being tracked as completable" but in practice no one ticks them. They become visual debt — a row of permanently-unchecked boxes that suggests work is unfinished when actually the items are just informational.

**How to apply:**
- PR test plan / description bullets: `-` (no brackets)
- Acceptance criteria someone verifies and ticks: `- [ ]`
- Design doc bullet lists: `-`
- Per-step runbook / setup instructions: `1.`, `2.`, ... (ordered)
- Explicit TODO lists where ticking matters: `- [ ]` is fine

If in doubt about a PR-style document, ask: will anyone actually edit this list and toggle boxes from `[ ]` to `[x]`? If no, use bullets.

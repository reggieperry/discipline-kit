---
name: feedback-reviewer-verify-docs-numerics-all-sources
description: reviewing citation-dense docs — verify a cited numeric against EVERY referenced source before flagging it as unsourced/fabricated
metadata: 
  node_type: memory
  type: feedback
---

When reviewing citation-dense docs (design records, research surveys, deployment dossiers), a numeric figure attributed to "X et al." may live in a *different* referenced source than the one the section's prose emphasizes. Grep every source the section cross-references — and the design records it points at — before raising an "unsourced figure" finding.

**Why:** On one docs PR, a validation-report section cited "the R² 0.34 drawdown metric that survives the transition per Wiecki et al." I checked the section's headline-citation survey and 0.34 was absent — looked like a candidate nit. It was actually in a design record the same section *also* cross-references (lines noting "max-drawdown R² 0.34"), and in a sibling research survey. Raising the nit would have been a fabricated finding. (Same run: a set of validation thresholds — PBO ≤ 0.05 / DSR ≥ 0.95 / a t-statistic gate / a multi-fold CSCV gate — all verified verbatim against the design record; note "PBO ≤ 0.05" as a pass criterion is the correct complement of the record's "PBO > 0.05" reject recommendation.)

**How to apply:** For a docs PR, treat the substance as "do the cross-references resolve and are the cited numbers accurate." Before flagging a figure as unsourced, grep ALL of: the section's cross-reference targets, every design record it names, and the sibling research surveys. Numeric thresholds in cutover/validation docs tend to live in the design record or a focused analysis survey, not the broad methodology survey that scaffolds the artifact list. Don't manufacture a nit to look useful on a clean additive docs scaffold — a zero-findings PASS is the honest verdict when every claim resolves. A related discipline: don't fabricate findings on deletion or docs PRs, and watch the claim-vs-substance gap.

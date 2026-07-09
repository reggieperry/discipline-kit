---
name: reference_story_decomposition_methodology
description: "SSD — analyze/decompose a unit of work before filing; run after backlog-audit, before the tightness rubric"
metadata: 
  node_type: memory
  type: reference
---

Story size-and-shape decomposition methodology (SSD). Authored from a 5-lens workflow grounded in real precedents.

**Pipeline position:** backlog-audit ([[reference_backlog_coverage_audit]]) → **SSD** → tightness rubric ([[reference_story_tightness_rubric]]). SSD scores SIZE-AND-SHAPE (one story or several, where to cut); the tightness rubric scores READINESS (each child must independently hit 10+). Orthogonal — both must pass before filing.

**Five steps:** (1) size-smell — weighted signals, trigger at total ≥4 or any weight-3 (≥2 sensitive paths = weight-3); line count alone never triggers. (2) find-seams — 7 finders; finders 4 (shared-mutable-file) and 7 (sensitive-file) are VETO gates. (3) split-or-keep — payoff buckets (a) throughput / (b) gate-tightness-revert-safety / (c) pure-granularity, weighed vs the per-story chain tax. (4) shape-the-set — predecessor-first deps, separate-invocation filing, dormant-then-promote, walking-skeleton-first. (5) validate — file-touch matrix + sensitive footprint + co-location WARN + tightness on each child.

**Central rule:** split along file-ownership and dependency seams, NOT conceptual feature boundaries. A shared-hot-file seam (e.g. an orchestration spine like a `loop.py`/`composition.py` module) does NOT parallelize — it serializes into a predecessor-first chain at full chain cost, so the only gain is review/revert granularity. Real throughput needs file-disjoint AND dep-disjoint (`deps: []`).

**Peel-off rule:** even when the bulk stays together, peel one slice if it is premature (consumer is a not-yet-built sibling), optional (optimization), a different risk class, or sensitive. Worked example: keep the stories that co-write the same shared modules together; peel off the slice whose collaborator doesn't exist yet (premature, its writer story isn't built).

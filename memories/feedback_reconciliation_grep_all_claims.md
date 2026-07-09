---
name: reconciliation-grep-all-claims
description: "Doc-reconciliation work must grep deliverable files for ALL spec claims, not just the citation paths. A reconciliation once fixed stale file-path citations but missed that the column names a referenced spec named didn't match the actual schema migration."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

When authoring or executing a doc-reconciliation task — one that brings stale doc/spec content into alignment with current code — verify every concrete claim the spec makes, not just the file-path citations.

**Why:** Drift accumulates across multiple dimensions. A spec might cite the wrong file path, *and* the wrong column names, *and* the wrong function signatures, *and* the wrong test fixture names. A reconciliation that only fixes the most-obvious dimension (the path) leaves the others as landmines for the next worker.

**How to apply:**

For any spec edit touching docs that reference code/data structures, the verification step should be:

1. **Grep the deliverable for each named identifier** (column names, function names, class names, file names, constant values). For each identifier:
   - Confirm it exists in the deliverable.
   - Confirm the *shape* (column type, function signature, etc.) matches what the spec claims.
2. **Spot-check enumerations**. If the spec lists five things, grep for all five in the deliverable. Don't trust counts; check identities.
3. **Cross-reference adjacent docs**. If the spec amendment touches several docs (a project guide, a build plan, and a story spec), the same drift may have spread to other docs, design records, or other specs. List them out, then either include in scope or explicitly defer with a new follow-up.

**The illustrating incident:**

A story was authored to reconcile schema-management docs to a migrations-based layout. Scope was four files: a project guide, a database README, a build plan, and one referenced spec. The worker correctly fixed citation paths (a single monolithic schema file → the per-migration files) and marked the referenced spec's table-creation acceptance criteria as already done. But that spec also named specific columns — a set of `*_z` score columns and a snapshot-date column — that didn't match the actual baseline migration, which used different column names. The reviewer didn't catch the column mismatch; only a subsequent pre-dispatch validation pass did.

Result: the referenced spec stayed un-dispatchable despite the reconciliation having "reconciled" it. A follow-up amendment had to be authored to actually fix the column-name shape.

**Where this could have caught earlier:**

- In the planning step: when listing the files to edit, also grep the deliverables those files cite. The spec said the table lived in a specific migration file — fine, but the column-name list should have been verified against that file at plan time, not just declared done.
- In the reviewer phase: the reviewer verified "the citations were correctly updated"; it should also have spot-checked the column-list claims against the baseline file. The reviewer prompt could grow a "for spec amendments that cite tables/classes/functions, verify three named identifiers from each deliverable exist as claimed" instruction.

**Future application:**

For any task (or amendment) whose acceptance criteria include "the spec now correctly describes <X>":

- Write down the X (column list, function signature, class hierarchy, file tree, command flags).
- Grep the *current source-of-truth* for each item in X.
- Mismatches go in the acceptance criteria as "the spec claims <Y>, the source has <Z>; the spec is the thing that should change."
- A reconciliation that does not enumerate X is incomplete.

**Cross-references:**

- [[feedback-read-source-before-guessing]] — the general discipline; this memory is a specific instance.

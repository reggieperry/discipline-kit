---
name: memory-ledger-boundary
description: "A memory carries durable discipline; any mechanically checkable assertion is a ledger claim with a named check, not a memory — a recheck recipe in a memory file is a claim in the wrong courthouse. On detection: register the claim, annotate the memory with the clm id, never delete."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Checkable assertions are claims, not memories (the boundary law)

A memory is the judgment that survives instance turnover — durable *discipline*, not a fact a machine could check. Anything mechanically checkable belongs in the dev-ledger as a claim under a named check; the memory that references it cites the `clm-` id. A recheck recipe stored in a memory file is a claim filed in the wrong courthouse: no gate reads a memory, so the "check" never runs and the assertion rots unwatched.

**Why:** this is the mnemosyne diagnosis — that tool was detectors without a constitution, and one failure mode was a checkable claim living only in a recall note, firing (or not) into a void. The ledger is where a claim gets a court; a memory is where a lesson gets remembered. Keep them separate and each does its job.

**How to apply:** when you find a memory asserting a checkable mechanical fact (a threshold, an invariant, a "this always holds"), **register the claim** in the ledger with the check that would verify it, **annotate the memory** with the `clm-` id, and **never delete** the memory — its judgment half stands. The index itself is guarded: `audit.py`'s `memory-index` check fails `MEMORY.md` over its hard budget, so the layer cannot bloat past the point where it is read. See [[fail-posture-taxonomy]], [[chain-aware-counters]].

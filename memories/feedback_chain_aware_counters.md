---
name: chain-aware-counters
description: "The unit the loop's counters measure is the full supersedes-chain, not a two-link pair — tdd-precedence walks each chain to its first ledger-only ancestor, and coverage credits a red-proof receipt about ANY id on the chain (the clm-0030 fix, v1.3.1)."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# The discharge chain is the unit; counters walk chains, not pairs (v1.3.1)

The `ledger-preregister`/`ledger-discharge` skills teach a three-link discharge chain — park under a non-runnable check → supersede to `repo-check` → gate-sign — and the `repo-check` *middle* link necessarily lands with code (it is the green commit). The v1.3.0 run surfaced the grain mismatch (clm-0030's finding): the counters walked two-link park→supersede pairs, so honest slices false-warned and carried receipts went uncounted.

**Why:** the checks must follow the ledger's data model, not the reverse. The slice is the whole chain, not any one link.

**How to apply:** `tdd-precedence` treats a parked claim that itself supersedes something as a discharge middle-link and skips it — only the chain's first ledger-only ancestor is judged for precedence (a chain whose *root* landed with code still warns, e.g. the slice-zero bootstrap). `report_red_proof_coverage` walks the forward supersession chain, so a red-proof receipt `about` any id on the chain — including the gate-signed final link, which is the live claim a receipt usually names — credits the slice. Fixed in kit v1.3.1 (`park_supersede_pairs` guard + `_slice_ids` forward-walk); coverage went 0/3 → 3/3 on the kit's own ledger. See [[squash-safe-precedence]] (the amendment this fix rode with).

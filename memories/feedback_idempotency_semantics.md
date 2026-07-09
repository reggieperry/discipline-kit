---
name: Name the idempotency invariant explicitly
description: "Idempotent" covers three distinct invariants. Pick the right one for the retry semantic and don't conflate.
type: feedback
volatility: durable
---
"Idempotent" is shorthand for three different invariants. Pick the one that matches the retry semantic you need, not the one that's easy to implement.

**Why:** A change once used `ON CONFLICT DO NOTHING` to make a status-initialization step idempotent. That's correct for "don't crash on duplicate insert" but wrong for "after retry, the field set is in a fresh state." A retry left stale `failed` rows visible to readers until the retry's persist overwrote them. Two different invariants; one word covered both ambiguously.

**How to apply:**
- When reaching for a retry-tolerance mechanism, explicitly name the invariant in the docstring:
  - *Don't crash on duplicate* → `ON CONFLICT DO NOTHING` (or set-with-IfNotExists, etc.). Use when re-running with the same input shouldn't error but the existing state is correct as-is.
  - *Last writer wins on identity* → `ON CONFLICT DO UPDATE` with the new values. Use when the new attempt's data should supersede the old.
  - *Reset to pristine state on retry* → `ON CONFLICT DO UPDATE` with explicitly cleared columns (error_message=NULL, finished_at=NULL, etc.). Use when "retry the whole stage" is the caller-facing semantic.
- The choice is rarely "any of the above will do." Ask: if a row exists with stale failure state and we re-run, what does a reader observe during the retry? If "stale failure," the answer is wrong.
- This applies beyond UPSERTs. The same three patterns show up in file writes (skip vs replace vs truncate-then-write), HTTP POSTs (skip vs replace vs reset), and message-queue handlers (ack-and-skip vs replay vs reset).

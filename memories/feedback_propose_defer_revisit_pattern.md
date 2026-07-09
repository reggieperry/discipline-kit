---
name: feedback-propose-defer-revisit-pattern
description: "Core working loop — propose an idea, work it out in detail, defer the implement decision, revisit later (often finding a prior worked-out record). Capture deferred thinking durably; search for the prior record on revisit."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

The operator works by **propose → work out → defer → revisit**. He proposes an idea; we work it out in detail; he may defer the decision to implement; and some time later — if the problem keeps bugging him — he brings it back, and *sometimes there is already a prior record of the worked-out thinking* (a design doc, an ADR, an archived spec set, a memory). He named this explicitly as "a pattern of mine."

**Why:** deferral is deliberate, not abandonment. The worked-out thinking is an asset he returns to, not throwaway conversation. The system's job is to preserve intent and surface what's deferred so future-him can resume without re-deriving.

**How to apply:**
1. When we work out a non-trivial idea that he then defers, **capture the worked-out thinking durably** — a design doc under `docs/`, an ADR, or an archived-deferred-work directory — not just in the conversation. The detail and the rationale are what he comes back for.
2. When he **revisits** a topic ("I'm ready to hear X", "didn't we discuss Y", "do we have a record of Z"), **search for a prior record first** (`docs/`, the ADR directory, the archive, the memory dir) before regenerating — there is often one. Build on it; don't reinvent.
3. A prior record anchored at an old HEAD is a starting point, not gospel — re-verify its load-bearing claims against current state on revisit.

This is the reason a coverage/reconciliation audit and a clean separation between the long-lived plan and the broader backlog matter: they are the machinery that keeps the deferred-thinking record findable.

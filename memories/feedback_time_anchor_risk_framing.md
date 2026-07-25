---
name: feedback-time-anchor-risk-framing
description: "Risk arguments must specify when the risk surfaces. \"Operationally catastrophic\" framings without a time anchor overstate risk that is dormant today; let the failure mode time-anchor itself (\"when X is wired, Y becomes the failure mode\") rather than reaching for emphasis-words on gaps that have no current consumer."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

When arguing about a gap in a safety-critical system, anchor the risk to *when* it surfaces. Don't reach for emphasis-words ("operationally catastrophic," "every position becomes unmanaged," "silent corruption") on gaps that are dormant because no production consumer exists yet.

**Why:** Caught by a fresh-context reasoning agent during review of a long-lived monitor loop. The argument was that the loop's missing failure isolation was "operationally catastrophic — silent death means every active position becomes unmanaged." The correction: there is no caller of the loop today; the entry-point module it would run under is on the project's "deferred infrastructure (DO NOT modify or extend)" list. The "silent death" scenario requires (a) the real event-source wiring, (b) a real entry point, and (c) a process supervisor — none of which exist. The risk-framing was time-dislocated from when the risk actually surfaces.

The error is overstating risk for emphasis. Three problems with it:

1. It misallocates urgency — pulls operator attention onto a dormant gap that doesn't need hardening today
2. It causes wrong sequencing decisions — argues for landing fixes in the wrong story (the policy belongs in the story that wires the real exception taxonomy, not pre-emptively)
3. It loses calibration trust — once the operator has caught one overstated framing, they reasonably discount the next one

**How to apply:**

- For any gap in a not-yet-consumed module, phrase the risk with an explicit time anchor: "when the real event source is wired, a raised exception kills the loop" — not "the loop dies on a raised exception"
- Reach for emphasis-words only when the gap is live in production-risk territory now, not when reaching for them would convey urgency you can't substantiate with a current consumer
- If unsure whether a gap is current or dormant, grep for callers / imports / production wiring before framing the risk
- Acceptable framings for dormant risks: "this becomes a problem when X" / "today inert; risk surfaces at consumer wiring" / "follow-on where the risk-shape becomes central"
- Unacceptable framings for dormant risks: superlatives ("worst-case," "catastrophic," "silently corrupts"), absolutes ("any caller will," "every active position"), urgency-words ("immediately blocks," "must be fixed")

Related: [[feedback_credibility_gestures]] — same shape (reaching for emphasis to compensate for weaker evidence). Related: [[feedback_analysis_discipline]] — hold positions with evidence; if the evidence requires a time-anchor, name it.

---
name: Label every golden's provenance — computed-then-pinned certifies agreement, not correctness
description: A golden produced by running one implementation and pinning its output proves future runs agree with that run, not that the run was right. Label goldens hand-derived, computed-then-pinned, or recorded-from-run, and keep at least one hand-derivable case per metric where feasible.
type: feedback
volatility: durable
---
Fixture goldens have three provenances with three different evidential weights: hand-derived (a human worked the answer independently — the strongest), computed-then-pinned (one implementation was run and its output frozen — proves stability and cross-leg agreement, nothing about correctness), and recorded-from-run (an artifact of a real execution — proves reproducibility of that execution). Suites silently mix these, and a reader who assumes hand-derived everywhere over-trusts the green.

**Why:** In a two-leg statistical discharge, the per-metric tuples on a synthetic game were hand-computed (strong), but the bootstrap interval golden was produced by running the Python leg on the two-game dataset and pinning the result in both legs — disclosed plainly in an authorship writeup as "computed-then-pinned, not reasoned." Both legs agreeing on that golden certifies the shared algorithm and PRNG, and would equally certify a shared mistake. Neither author nor reviewer was positioned to hand-derive a cluster-bootstrap percentile, and the honest record of that limit is what made the suite's actual guarantee legible.

**How to apply:** (a) Tag each golden in the fixture or its adjacent comment with its provenance word; (b) where a metric admits a small hand-derivable case, include one at hand-derived grade even if larger cases are computed-then-pinned; (c) in any discharge or report that leans on a suite, state the weakest provenance in the chain — the signature's meaning is bounded by it; (d) treat an all-computed-then-pinned suite as reproducibility evidence awaiting an independent correctness leg, and say so rather than letting the green imply more.

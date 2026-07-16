---
name: rule-grade-matches-gate
description: "A coding rule states its enforcement grade — whether the gate mechanically polices it or it is review-and-convention; a scanner wiring and the removal of that rule's disclaimer share one commit, so the label and the gate move together or not at all."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# A rule states its enforcement grade; the label and the gate move together (v1.3.2)

A rule that reads stronger than its gate is a quiet lie: the reader trusts a mechanical guarantee that does not exist. So each security rule states its **enforcement grade** at the top — mechanically enforced (a scanner rides the differential gate's Check A, findings diff, suppressions policed) or review-and-convention (no scanner wired yet, named). Measured asymmetry (2026-07-14): of the five per-language security rules, only `python-security` had a wired enforcer (`bandit`); `go`/`ts`/`scala`/`java` cited tool catalogs as *canon* but no gate ran them.

**Why:** the named genus per language — a rule citing gosec/eslint-plugin-security/FindSecBugs codes reads like those tools run, when they do not. The label closes the gap between what the rule *teaches* and what the gate *enforces*.

**How to apply:** when wiring a new scanner (e.g. `gosec` as a `GoToolchain`, FindSecBugs on the SpotBugs engine), the wiring commit **deletes that rule's enforcement-grade disclaimer in the same diff** — the label and the gate move together or not at all, so a rule is never left claiming enforcement a half-landed scanner doesn't yet provide. Each such wiring is detector-class (red-first fixtures per the loop). See [[chain-aware-counters]], and the SpotBugs residue note (fail-closed, off default Check A until a compiled pilot).

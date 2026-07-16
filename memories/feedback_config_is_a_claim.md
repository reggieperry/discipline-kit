---
name: config-is-a-claim
description: "A repo's configuration choices (tier, check command, languages, audit mode, coverage, red-proof status, waivers, escalation) are recorded as one ledger assertion — defaults included, check:none — so the board shows how the repo is armed and a future session never guesses."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Configuration is a claim

Every operator-facing knob the kit exposes (the tier, the pinned `ledger/check.sh` command, `ledger/languages`, the audit's warn-vs-`--strict` mode, the memory-index budget, the differential gate's coverage opt-in, red-proof's advisory status, waivers, escalation) is a *choice*, and an unrecorded choice is one a future session has to reverse-engineer. So the configuration is recorded as a claim: after walking the manual's Options section (the "Tour"), the final act appends **one ledger assertion enumerating every choice made — defaults kept included — under `check: none`**.

**Why:** the board's job is to show how this repo is armed. A choice that lives only in a config file (or worse, only in someone's memory) is invisible to the record that is supposed to answer "why is it set up this way?" Recording defaults too matters: "we kept the default" is itself a decision, and its absence reads as "nobody looked."

**How to apply:** when you configure a repo — at install, or whenever a knob changes — append a `check: none` assertion listing the choices (tier, check command, languages, audit mode, coverage, red-proof, waivers, escalation), and show it to the operator. It never signs (there is nothing mechanical to verify about a preference), but it stands on the board as the durable answer to how the repo is set up. See [[memory-ledger-boundary]] (this is the boundary's other side — a preference is a claim, not a memory), and the operators-manual "Options" section it records.

---
name: specs-are-claim-parents
description: "ADR falsification conditions and story acceptance criteria are the prose parents of registered ledger claims; the record-home rule (a falsifier or criterion living only in prose is a court nobody convenes) applies at every grain — decision, spec, and memory."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Specs are the prose parents of claims (the record-home rule, every grain)

The memory/ledger boundary generalizes: prose carries the reasoning at each grain, the ledger carries what a machine can check, and the citation between them keeps the reasoning honest. An **ADR** records a decision's *why* in `docs/adrs/`, but its **falsification condition** registers as a ledger claim wherever mechanically checkable, and the ADR cites the `clm-` id. A **story** records a spec's intent, but its **acceptance criteria** become the loop's parked claims — the claim-first step is a story's criteria entering the courthouse, one line each, before any code.

**Why:** a falsifier or an acceptance criterion living only in prose is a court nobody convenes — nothing runs it, nothing watches it, and the day it fires there is no bell (the ADR scar: "revisit if throughput regresses" cited no check, and a two-cycle regression shipped unread). The same failure the mnemosyne index and the glut-laundering incident showed, at decision and spec grain.

**How to apply:** when you write an ADR, register its falsifier as a parked claim (`ledger-preregister`) and cite the id in the Falsification section; its acceptance-gate verdict (deep-reason, committee) lands as testimony the Status line cites. When you take in or write a story, each acceptance criterion becomes a parked claim (carry the anti-weakening contract verbatim). The authoring layer (`adr-write`, `story-write`, `story-tighten`, `story-intake`) is a default-off Tour choice. See [[memory-ledger-boundary]], [[config-is-a-claim]].

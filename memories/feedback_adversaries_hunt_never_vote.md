---
name: adversaries-hunt-never-vote
description: "The adversarial-review harness fans N fresh-context attackers out against a diff decorrelated BY ROLE and never votes — agreements are weightless, duplicate findings dedupe by lineage, a dead adversary is a loud could-not-run, and a finding is real when its disposing check goes red, not when attackers agree."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Adversaries hunt, they never vote (roles partition; agreement is weightless)

An adversarial review is not a committee. The `adversarial-review` harness fans several fresh-context attackers out against a diff, each on the `deep-reason` pattern under its findings contract, and it **never counts a vote** — adversary proposes, mechanism disposes. Four rules make that real:

- **Roles partition, not samples.** The decorrelation is the *assignment* — one attacker hunts logic and state, one hunts abuse and boundaries — not a temperature or a seed. Decorrelating by sampling gives you the same blind spot twice and calls it two.
- **Agreement is weightless.** A clean pass is two absence reports with their search queries quoted, never an approval; two adversaries catching one bug is *one* finding (dedupe by lineage), because corroboration is not confirmation (the E3 discount).
- **A dead adversary is loud.** The launcher reconciles launches against completions — N launched, N verdicts or N explicit failures, no silent third state; a crash or refusal blocks the verdict until rerun or waived with the gap named ([[reviewer-harness-fail-closed]]).
- **A finding is real when its disposing check goes red**, not when attackers agree. A finding whose check does not exist is a new test the attack authors, red-first — the adversaries catch what no check encodes *yet*, completing the court ladder below the gate, red-proof, and the differential gate.

**Why:** E3 poisons *confirmation*, not refutation-hunting. Fanning out attackers buys decorrelated coverage of what-no-check-encodes-yet; letting them vote would reintroduce the correlated-approval failure the whole discipline exists to avoid.

**How to apply:** reach for `adversarial-review` (modes `pre-pr` / `own-pr` / `foreign-pr`) at tier two — detector-class, sensitive files, contested claims, hairy state — above the mechanical every-PR `pr-review`; route `pre-pr`/`own-pr` findings as refutations about the slice's claims, and let `foreign-pr` be its own artifact (no foreign ledger write). Acceptance-verified end to end (two roles, a deduped shared plant, an absence report, a pre-pr refutation). See [[reviewer-harness-fail-closed]], [[adversary-not-second-opinion]].

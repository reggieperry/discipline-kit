---
name: reference_module_decomposition_test
description: Validated per-file module-decomposition test (code-level analog of SSD); themes detect, abstractions decide; sequenced vs bound
metadata:
  node_type: memory
  type: reference
---

Per-file module-decomposition test. A mechanical triage tool can rank all modules worst-first as a pre-filter (ruff/mypy clean). Code-level analog of [[reference_story_decomposition_methodology]] (SSD is story-level at filing; this is module-level at coding/review). Built and validated via blind workflows against a codebase's own history.

**Field guide:** themes DETECT (count reasons-to-change), abstractions DECIDE (a theme earns a module only if it's a deep, substitutable abstraction). A composer that merely SEQUENCES independent helpers is hiding modules; one whose helpers are BOUND to its per-call state is a legitimate spine (KEEP).

**Stages:** 0 triage (mechanical: public names imported by other modules [strongest decompose signal], runtime import-spread, fragmentation; demote single-dominant-composer spines) → 1 conjunction test (single-act carve-out) → 2 classify Abstraction/Fold/Spine (substitutability+independence veto last; seam-is-own-contract→Fold) → **2.5 anti-escape-hatch fire rule** (the crux: SEQUENCED≠BOUND; consumer-partition for TYPES; cardinality backstop) → 3/4 compose+validate.

**Validated both directions.** Two hard lessons: (1) an eyeballed "decompose this orchestrator module" call was WRONG — the blind test held it KEEP-SPINE (its two methods thread the same per-call state object, so they're bound, not merely sequenced; the package was already split by knowledge domain). Theme-counting over-fires; the abstraction test corrected it. (2) An always-KEEP test passes a no-false-positive record — a first calibration that returns all-KEEP can hide systematic conservatism (SPINE/TYPES escape hatches) until the Stage 2.5 fire rule; a both-directions check (known god-files must fire DECOMPOSE) is mandatory. Known bias: over-fragments thin once-bound adapters.

**Rollout:** pre-filter (triage tool) → judgment pass worst-first (expect mostly KEEP; many DECOMPOSEs = reverted to triage-loudness) → gate cuts as behavior-preserving REFACTOR work or direct-with-discipline; never on a behavior-adding branch (two hats).

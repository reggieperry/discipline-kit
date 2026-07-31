---
name: fail-posture-taxonomy
description: "Three fail postures by role — a blocking control fails CLOSED (deny on doubt), an advisory nudge fails QUIET (stay out of the blocking path until trusted), a safety constraint fails STRICT (unparseable reads as forbidden). Inverting one is a quiet catastrophe; name them so no one does."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Fail closed, quiet, or strict — by the control's role

Three postures, and which one a control takes is decided by what it is *for*, not by taste:

- **Blocking control → fails CLOSED.** The commit-path gate and the write path deny on any doubt; an unverifiable state is treated as unsafe. (mnemosyne D2)
- **Advisory nudge → fails QUIET.** A lint whose false alarm would train people to ignore it stays out of the blocking path until it has earned trust — a warn that cries wolf is worse than none. Measured 2026-07-30, and the rule predicted its own case: a repo's warn tier reached 26 standing findings while the gate passed no `--strict`, so nothing acted on any of them and the checks that produced them were removed. A warn nobody acts on is not a soft guardrail; it is output. (mnemosyne D3)
- **Safety constraint → fails STRICT.** An unparseable constraint reads as *forbidden*, never permissive; the deny-list and the sentinel guard default to the safe answer when they cannot parse. (mnemosyne D5)

**Why:** the postures are easy to invert by accident — wiring a blocking check to fail quiet (so it never blocks), or a constraint to fail open (so a parse error permits) — and each inversion silently removes the protection while leaving it apparently present. The kit already practices all three; the names exist so a future contributor cannot invert one without noticing.

**How to apply:** before adding a control, decide its role, then match the posture. If it blocks, it denies on doubt; if it advises, it stays quiet until trusted; if it constrains, an unreadable input is forbidden. See [[memory-ledger-boundary]], and the operators-manual "fail-posture taxonomy" paragraph.

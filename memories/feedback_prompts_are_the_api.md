---
name: prompts-are-the-api
description: "The kit's operator is Claude Code and the interface is the prompt, so docs carry verbatim paste-ready prompts (read-first, receipt-demanding, dual-audience); the conversational path is a TESTED front door — a fresh instance given only the prompts must reach green — not folklore."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# The prompts are the API — and the front door is tested

The kit has no GUI and no CLI a human drives directly; its operator is Claude Code, and the interface is what a user *says*. So the conversational path is a first-class, versioned artifact: the README carries verbatim, paste-ready prompts (Install, Orient, Work, recover-from-a-block, Upgrade, Tour), and each obeys three laws — **read-first** (point the instance at the docs before it acts), **receipt-demand** (end with "show me the output"), and **dual-audience** (the instance reading the README executes the prompt as its own checklist).

**Why:** a prompt is a specification the way a function signature is, and an untested spec drifts. The kit proved this the hard way — the §14 front-door acceptance (a fresh instance in a scratch repo given only the Install prompt) reached green `harness-verify` unaided, *and* caught a real defect the same day: `install.md` told the user to run `./harness-verify.sh`, but the installer never copies that script into the target, so the literal instruction failed and running it from the kit dir silently verified the wrong ledger. Folklore would have shipped that; a test caught it.

**How to apply:** when you add or change a conversational path, treat it as code — write the prompt read-first and receipt-demanding, and **test it with a fresh instance given only the prompt, no further guidance**; a gap the instance has to reconcile is a finding (file the refutation, fix the doc, re-verify). See [[config-is-a-claim]] (the Tour's output) and [[memory-ledger-boundary]].

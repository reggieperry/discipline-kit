---
name: squash-safe-precedence
description: "Precedence certificates are content, not commit topology — squash-merge is supported (audit.py --certify emits a pre-merge certificate the main-side audit consumes); ancestry is the richer path where available (rebase/merge)."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Squash-merge is supported: precedence is certified as content (v1.3.1)

A squash-merge collapses a branch to one commit on main, which destroys exactly the per-commit ancestry `tdd-precedence` reads (the ledger-only claim-first commit preceding its code) while every ledger line survives as content. The fix is the gate's own pattern — verify where the history exists, persist the verdict as content: `audit.py --certify`, run on the intact branch (pre-squash), emits a `precedence verified: …` testimony (a certificate, `source: hook`) for each verifiable park→supersede pair; the certificate rides the squash as content, and the main-side `tdd-precedence`, where the two introducing commits collapse into one code-carrying commit (`xc == yc`), consumes the certificate instead of the erased ancestry.

**Why:** the claim once made — "squashing destroys the loop's audit trail" — was true only before the certificate. The certificate is squash-proof because it is a line, not a topology.

**How to apply:** rebase-merge and merge-commit keep the richer per-commit ancestry for free and are preferred where you own the merge policy. Where a repo squashes, run `--certify` before the merge and commit the certificate (CI verifies read-only; a policy that lets CI commit back can emit it there). `--certify` is an emitter (exit 0); the warn-grade `tdd-precedence` flags a pair with no certifiable precedence. GitHub's `refs/pull/N/head` is a documented recovery path, never relied on.

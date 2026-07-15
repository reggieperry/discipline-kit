---
name: retire-any-commit
description: "Retire is verbatim-move + sidecar (v1.1.0), so a claim is immutability-safe to retire in ANY later commit — the same-commit-only rule is history; the --sweep scar's incident stands, its constraint no longer binds."
metadata:
  node_type: memory
  type: feedback
  volatility: durable
---

# Retire is safe in any later commit (the v1.1.0 sidecar form)

Retirement moves a defeated or superseded claim to `ledger/trace/<id>.jsonl` as the **original line byte-identical plus a separate retirement record** (`retire_of` / `trace_reason` / `retired_by`). Because the committed line is preserved unchanged, the immutability check is satisfied even when the claim was first committed in an *earlier* commit. So a claim may be retired safely in **any later commit**, and a late sweep at a landing is legal.

**Why:** the older rewrite-in-place mechanics edited the moved line, which tripped `check_immutable` for any claim whose live form was committed earlier — forcing a same-commit-only discipline. The v1.1.0 fix (verbatim-move + sidecar) lifted it. Cite the v1.1.0 changelog and `harness/ledger/fixtures/retire_immutable_test.py` (red on the old rewrite, green on the verbatim-move).

**How to apply:** retire whenever the board should shed a defeated claim; do not defer to the supersession's commit. This **supersedes the lesson half of the `--sweep` over-reach scar** (in the `ledger-retire` skill) — the incident (a sweep at a landing that tried to move long-committed lines) stands as history, but its taught constraint, "retire only in the same commit," no longer binds. The durable caveat is narrower: `--sweep` retires the *whole* superseded-but-live backlog, so run it as a deliberate cleanup pass, not bolted onto a landing.

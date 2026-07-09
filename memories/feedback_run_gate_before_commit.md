---
name: feedback_run_gate_before_commit
description: Run the gate (ruff/tests/mypy) as its own step and read the result before committing — never bundle verify with commit/push
metadata: 
  node_type: memory
  type: feedback
---

When a commit's correctness depends on a gate, run the gate as its OWN tool call, READ the result, and only then commit in a SEPARATE call. Never put the gate and the commit/push in one command (no `ruff check && git commit && git push`, no verify+commit in a single Bash invocation).

**Why:** a bundled `verify && commit` commits whatever state exists when the commit step runs, regardless of what the gate reported — and bundling removes the pause where I'd actually read the gate output, so the gate stops being a gate. Seen twice in one session: (1) a test suite — committed+pushed on a flaky "9 errors" run because the suite+commit+push were one command and I only captured `tail -3`; (2) a ruff fix — pushed a `pyproject.toml` change before seeing it surfaced 5 latent I001 errors, leaving the main branch briefly dirty and forcing a fix-forward. Both times the result was visible only after the irreversible step.

**How to apply:** sequence is gate → read → commit, as distinct steps. If the gate is non-green, fix first; commit only the green state. This is the same discipline as [[feedback_deep_reason_command_output_confabulation]] (read the command output, don't assume it) applied to my own commits rather than a subagent's claims. Pairs with [[feedback_commit_messages]] and the verification-discipline section of the project instructions.

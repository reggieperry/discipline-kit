---
name: feedback_fetch_before_asserting_remote_state
description: "Before asserting what's merged/upstreamed or any branch topology, git fetch first — local remote-tracking refs go stale"
metadata: 
  node_type: memory
  type: feedback
---

Before asserting git *remote* state — what's merged upstream, what's un-upstreamed, how a branch sits relative to `origin/main` — run `git fetch` first. Local remote-tracking refs (`origin/main`) reflect the last fetch, not reality, and `git log origin/main..HEAD` against a stale ref invents work that's already landed.

**Why:** While diagnosing a bug, I read `git log origin/main..HEAD` on a deploy branch and concluded a fix was "deployed but never contributed upstream." A plan was chosen on that basis. It was wrong: a `git fetch origin` showed the fix was already merged upstream (refactored into a shared helper). The local `origin/main` was simply behind. The whole premise of the plan collapsed. A session-start warning had explicitly flagged re-checking inherited state; I didn't fetch. Seen the same day across two machines: one host's `origin/main` was *ahead* of another host's just-fetched ref — two machines, two fetch horizons.

**How to apply:** Any claim of the form "X is/isn't merged," "this commit is upstream," "the branch is N ahead," or a chosen base for a PR → `git fetch <remote>` immediately before, on the machine you're acting from. Cross-machine work compounds it: each host has its own fetch horizon, so fetch on the host you'll branch/push from. Pairs with [[feedback_read_source_before_guessing]] (read the function, not memory) and the verification-discipline rule against composing identifiers from memory.

---
name: feedback_research_subagent_no_skill_fanout
description: Research subagents must search directly with WebSearch/WebFetch — never let them invoke a fan-out research skill or spawn their own sub-agents; a deep-research skill is itself a fan-out harness and recursive invocation produces a dozens-deep agent swarm that rate-limits the whole session
metadata:
  node_type: memory
  type: feedback
---

When delegating research to subagents via the Agent tool, constrain each to **search directly (WebSearch/WebFetch) and NOT invoke any skill or spawn sub-agents.**

Observed failure: six general-purpose research agents were spawned for a documentation sweep. Three silently called a deep-research skill, which is itself a fan-out harness (it spawns several parallel WebSearch agents, each of which recursively fanned out again into their own topic swarms). Net: dozens of concurrent background agents that tripped a server-side rate limit ("Server is temporarily limiting requests · Rate limited") and then drained into the session for many turns. The content still arrived (the deep-research adversarial-verify produced genuinely good cited claims), but the loss of control plus the rate-limit storm were severe and avoidable.

**Why:** a general-purpose agent has both the Agent and Skill tools, so it reaches for the most powerful research path (the deep-research skill) unless told not to — turning one delegated search into an uncontrolled recursive swarm.

**How to apply:** in every research-agent prompt add an explicit line — "do the web research YOURSELF with WebSearch/WebFetch directly; do NOT invoke any skill (especially a deep-research skill) and do NOT spawn sub-agents." If a large multi-source fan-out is genuinely wanted, run ONE controlled workflow with a fixed agent count rather than free Agent calls that can self-fan-out. And note the recovery gap: orphaned grandchildren of a dead parent agent are **not stoppable** — the task list shows only TODO items (not background agents), and the parents have already exited so a kill can't cascade; you can only wait them out, which is why prevention up front is the only real lever. Related: [[reference_chain_failure_modes]].

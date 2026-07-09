---
name: deep_reasoning_prompt_improvement_candidates
description: "Candidate edits to the deep-reasoning prompt template from real use — quote exact commands behind absence claims, double-search absences, keep \"say vs does\", drop preamble"
metadata: 
  node_type: memory
  type: project
---

Candidate revisions to the deep-reasoning prompt template (the fresh-context reasoning-subagent prompt and skill), noted after a scoping run that was high-quality but exposed friction. Revisit next time the template is edited; these are refinements, not a rewrite.

1. **Make absence claims re-runnable.** The verdict rested on "X is absent / grep returned nothing" findings (a symbol not present in the source tree; no production producer for a given type). Verifying them per [[feedback_deep_reason_command_output_confabulation]] meant *reconstructing* the search — and one of my own greps errored on the rebuild. Fix: require the agent to quote the **exact command and its raw output** for every absence claim, so verification is paste-and-rerun.

2. **Double-search load-bearing absences.** Absence is the most failure-prone claim for an LLM (a narrow pattern misses a real hit). Instruct ≥2 differently-phrased searches per absence claim, both reported, and label absence findings "verify before acting."

3. **Keep "say vs does" as a standing line.** The ad-hoc prompt line "distinguish what the docs/specs SAY from what the code DOES; the gap is the point" was the highest-yield instruction — it surfaced that a feature was already shipped while my plan assumed it unbuilt. Promote it into the template permanently.

4. **No preamble in output.** The agent prepended a chatty "ground truth is complete… writing the verdict" block before the requested sections. Add "first line is the VERDICT, no preamble" to the output spec.

**Why:** the run's value came from a strong 6-section prompt (explicit uncertainties-to-verify + verify-every-identifier), but the absence-claim friction and confabulation risk recur every run. **How to apply:** fold 1–4 into the deep-reasoning prompt template before the next verdict-shaped invocation. Related: [[feedback_deep_reasoning_agent]], [[feedback_deep_reason_command_output_confabulation]].

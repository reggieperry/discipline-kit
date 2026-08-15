# The D5 extended-probe limbs, run 2026-08-15

ADR-0004/D5 scopes the enabling facts to the measured harness version and names the limbs a
version bump must re-run. Three of them were open as honest-but-unmeasured bounds after the first
walk: whether the pinned settings' spawn denial holds headlessly, what a compaction record looks
like in a `-p` stream, and whether a project-scope `settings.local.json` loads beside the fence.
All three were driven at harness **2.1.224** (the profile's pin) in the walk's dedicated clone.
The streams are retained under `/var/lib/discipline-chain/streams/PROBE-*/`.

## Limb A—spawn denial holds; a denied attempt leaves no trace

A phase whose brief instructed exactly one subagent spawn, run under the pinned
`settings.json` (`permissions.deny: ["Task", "Agent"]` at probe time). Measured, from the phase's
own committed report and the retained stream:

- **The deny holds.** No `Agent` or `Task` tool was callable; the attempt returned "Agent exists
  but is not enabled in this context," and no child artifact was created. The spawn tool is
  disabled headlessly by the pinned settings, as ADR-0004/D3 intends.
- **A denied attempt is invisible to the audit, as disclosed.** The stream carries no
  `task_started` or `task_notification` record—the audit's actual patterns—and
  `transcript_audit.py --dir` over it reads clean (38 records, 0 findings). This is the audit's
  own disclosed bound made measured: it sees tasks that ran, not attempts that were refused. A
  refused spawn is caught at the settings fence, not by the post-batch audit, and that is the
  right division.
- **FINDING (spawn surface wider than the deny list): the `Workflow` tool was present in the
  phase's tool list and can spawn subagents.** The phase disclosed it and did not call it —
  `Workflow` is gated behind an explicit opt-in the phase never gave—but a deny list naming
  only `Task` and `Agent` does not cover every spawn vector. The pinned settings deny list was
  hardened in this pass to `["Task", "Agent", "Workflow"]`. Full closure of the spawn surface,
  and whether the gate itself can be relied on, belong to the containment-posture record; this is
  the measured input to it.

## Limb B—a `-p` compaction record could not be forced; the net catches every real shape

Two endurance phases were run to force auto-compaction. The first let the model shortcut a
repetitive brief after 9 turns and never approached its context window. The second used a
nonce-chain—each of 40 turns embedded the previous turn's random token, so the model could not
batch or skip—with ~24 KB of padding per turn. It ran the full 40 turns and completed cleanly:
`is_error` false, `result` "success", **2,545,679 cache-read tokens** accumulated across the run,
and **no compaction record in the stream**. Across both heavy phases, past the point an
interactive session compacts, the `-p --output-format stream-json` stream emitted zero compaction
records.

So the `-p` compaction record shape stays unmeasured—not for lack of load, but because a phase
heavy enough to compact interactively instead completed. What that leaves:

- **The net catches every compaction shape that actually occurs.** Tested `core.admitted_signals`
  against the compaction records in this machine's own session transcripts: **all 29 genuine
  `subtype: compact_boundary` records carry a `compactMetadata` top-level key**, which the net's
  key-name scan matches, so every one reads `compacted`. The blind spot the code documents (a
  marker living only in the `subtype` value, which the net never reads because `subtype` is not
  in `ADMITTED_KEYS`) is **not exercised by any of the 29 real records**—none is subtype-only.
- **A measurement artifact, corrected, worth recording as the method.** An initial pass reported
  that 16 of 45 compaction records lacked the caught key—a 36% miss rate. That was a grep
  artifact: the check ran over raw lines merely *containing* the string `compact_boundary` (in a
  `logicalParentUuid` or a text field) rather than over records whose `subtype` field equals it.
  Parsing the records properly, the count is 0 of 29—every real compaction boundary carries the
  key, and the 18 string-matches are non-compaction records the net correctly does not flag. The
  alarm was the instrument, not the net.
- **Disposition: no change to the detection logic.** Widening the net to read the `subtype` value
  would cross the ADR-0001/D5 admitted-keys boundary (`session_id` and `type` only, enforced by
  `sequencer_source_check.py`) to catch a shape that does not occur in 29 real records, while
  risking false `compacted` readings on the 18 string-match records. The fail-closed backstop
  stands regardless: a `-p` phase that dies mid-stream from any cause, including a hypothetical
  silent compaction, leaves an incomplete stream and reads `in-phase`/`unreadable`, which is
  phase-death by the liveness arm. If a future harness ever emits a `-p` compaction record that
  is subtype-only, that observation—not this hypothetical—reopens the admitted-keys decision.

## Limb C—a project-scope `settings.local.json` loads headlessly

A scratch tree carrying a committed `.claude/settings.local.json` (a `SessionStart` hook writing
a marker), invoked with `HOME` and `CLAUDE_CONFIG_DIR` repointed exactly as the invocation layer
repoints them. The hook **fired** (the marker was written), so the second project-scope settings
file loads under a fully repointed home at 2.1.224. This makes `invoke.py`'s F1 refusal—the
pre-phase assertion that no `settings.local.json` stands in the judged tree or the workspace —
a guard over a live channel, not a hypothetical one: absent that refusal, a committed
`settings.local.json` in a judged tree would reach the phase beside the materialized fence.

## What these limbs settle, and what stays open

Settled at 2.1.224: the spawn denial holds; a denied attempt is a fence event, not an audit
event; the compaction net catches every real compaction shape; the `settings.local.json` channel
is real and F1 guards it. Version-scoped per ADR-0004/D5—a harness bump re-runs all three.

Still open, and pointed at their records: the full spawn surface and the reliability of the
opt-in gate (containment-posture record); the `-p` compaction record shape, unmeasured because it
could not be forced (re-attempt on a version bump, or accept the mid-stream-death backstop as
sufficient); and the auth posture per machine, since the `CLAUDE`-prefix environment scrub would
break a phase that authenticated through a `CLAUDE`-named variable (this machine uses
`ANTHROPIC_API_KEY`, which survives).

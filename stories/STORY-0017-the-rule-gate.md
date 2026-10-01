---
id: STORY-0017
title: Build the rule gate, a PreToolUse hook that refuses a write until its path-scoped rules are in context
deps: []
labels: [rules, install]
sensitive_files: [install.sh, claude-user/settings.json]
status: draft
adr: ADR-0008
decisions: [D1, D2, D3, D4, D5]
cites:
  - docs/adrs/ADR-0008-rule-gate.md
---

# Problem / Context

Claude Code 2.1.286 loads a path-scoped rule only when a matching file is Read or @-mentioned. Write, Edit and Bash never load one, so a file the model writes without reading a
matching file first is written without its rules, and nothing records the miss. One measured
session ran 12 of 37 writes without their language's rules. ADR-0008 decides the remedy: a
user-level PreToolUse hook that reads the calling agent's own transcript, refuses a write whose
rules are not loaded, and puts the rules' text in the refusal.

Grounding against HEAD (before this story):

- No hook exists. `claude-user/settings.json` carries `permissions` only; there is no `hooks` key.
- `install.sh:632`: for a kept settings.json the installer says only "merge the permissions you
  want", so a hook added to the kit's settings.json would never reach an existing install, and
  the stamp would not say so.
- `harness/rule_coverage.py:43,72,80`: the coverage check matches globs with `fnmatch`, where `*`
  crosses `/`, so it can pass a glob Claude Code never matches.
- `README.md:206`: says rules "auto-load by path glob ... when you edit a matching file", which
  is false.

# Proposed approach

- `reference/rule_gate.py`, stdlib only, Python 3.8 grammar, installed to
  `~/.claude/discipline/rule_gate.py`, following `reference/sdlc-gate.py`'s placement. The pieces:
  - `parse_paths_frontmatter` and `match`: the frontmatter reader and a port of the node-ignore
    matcher bundled in 2.1.286;
  - `applicable_rules`: the rule walk;
  - `transcript_for` and `window_lines`: transcript selection and the backward scan to the last
    boundary;
  - `loaded_rules`: D1's counting;
  - `decide`: D2's refusal and D3's pending set;
  - `main`: always exits 0.
- `harness/fixtures/rule_gate_vectors.json`: golden vectors from the bundled node-ignore, carrying
  the generator's source and a provenance line with no home path.
- `harness/fixtures/rule_gate_test.py`: synthetic transcripts in the measured entry shapes, under
  a temp directory, with the environment passed explicitly; listed in `scripts/check.sh`.
- `harness/rule_coverage.py` loads the gate's reader and matcher by file path, replacing `fnmatch`.
- `claude-user/settings.json` gains the `hooks.PreToolUse` block. `install.sh` copies the gate,
  reads a kept settings.json as JSON, prints the PreToolUse entry (and writes a merged copy beside
  the file) when no hook there runs the gate, and records a `rule_gate:` disposition in
  `KIT-VERSION`. `harness/fixtures/install_test.py` adds the gate to `USER_PAYLOAD` and a case
  for the wiring.

# Scope and non-goals

In scope:

- the gate, its vectors and fixture, the shared matcher in `rule_coverage.py`, and the user-level
  install and stamp

Out of scope:

- gating Bash (ADR-0008/D4)
- gating chain phases, which exclude user-scope settings (ADR-0004/D3); a phase gate would be a
  change to the phase's pinned settings and its own decision
- installing rules into consumer repositories, or re-syncing ones that drifted
- a live test on the commit path (ADR-0008, Falsification condition)
- the glob fixes to the rules themselves, which ship in the same change but are not this story's
  criteria

# Acceptance criteria

Story-specific criteria, each dischargeable by a named check:

- [x] every glob and path pair the bundled node-ignore produced, and every multi-glob set,
      matches the same way in the port, and a shipped glob with no vectors fails, verified by
      `rule_gate_test.py` `GoldenVectors` (13,755 pairs, 11 sets), and globs where JavaScript's
      regex dialect differs from Python's match as node-ignore does, verified by `Matcher` (D1)
- [x] a rule counts as loaded through `nested_memory`, `instructions` and `file` attachments, a
      full Read with or without `toolUseResult`, the gate's own marker, and `file_unchanged` after
      a prior load, verified by `rule_gate_test.py` `Counting` (D1)
- [x] a partial Read, a result reporting a partial file, an errored or unanswered Read, the
      compaction summary, a load before the last boundary, and `file_unchanged` with no prior load
      do not count, verified by `rule_gate_test.py` `Counting` (D1)
- [x] a subagent is judged by its own transcript at any depth under `subagents/` and does not
      inherit the parent's loads, verified by `rule_gate_test.py` `TranscriptSelection` (D1)
- [x] a result answering another call of the checked call's own response does not count, the
      gate's refusal and a Read alike, and a later call of that response is a sibling however long
      it waited, verified by `rule_gate_test.py` `SameResponse` (D1, D3)
- [x] `paths:` given as a scalar on the next line, a block scalar or under a quoted key is read,
      verified by `rule_gate_test.py` `Frontmatter` (D1)
- [x] user-scope rules are skipped, a target outside the project gets no rules, a nested
      `.claude` matches relative to its own directory, a symlinked rules directory is followed
      inside the project and skipped outside it, a worktree nested in its repository does not get
      the main checkout's rules, and two copies of one rule count once, verified by
      `rule_gate_test.py` `ApplicableRules` (D1)
- [x] a miss is refused with each rule's marker line and full text, ending with the retry line,
      and the unconditional rule is not inlined; above the cap the refusal lists paths and
      inlines nothing, verified by `rule_gate_test.py` `Decision` (D2)
- [x] Write, Edit, MultiEdit and NotebookEdit are gated; Read, Bash, Agent and Glob produce no
      output and no log line, verified by `rule_gate_test.py` `Decision` and `EndToEnd` (D2, D4)
- [x] a sibling inside 120 seconds gets a short refusal without the text; a counted rule clears
      from pending; after 120 seconds the call is allowed with a warning, logged `BLIND` once, and
      never refused again; an entry from before a compaction is inlined again; state is per session
      and agent, written atomically, pruned after seven days, and read as empty when corrupt,
      verified by `rule_gate_test.py` `PendingAndBreaker` (D3)
- [x] a refusal whose text another hook's refusal replaced is given again in full, not called a
      sibling, until three such refusals open the breaker; the gate's text on disk where it does not
      read is BLIND at once, verified by `rule_gate_test.py` `AnotherHooksRefusal` (D3)
- [x] a missing or unreadable transcript, a tool input without its path, garbage on stdin and an
      internal error each allow with a warning and a `FAIL-OPEN` log line, and the process exits 0;
      `DISCIPLINE_RULE_GATE=off` disables it, verified by `rule_gate_test.py` `Decision` and
      `EndToEnd` (D3)
- [x] run as a subprocess, the hook refuses, and the same write is allowed once the refusal is in
      the transcript, verified by `rule_gate_test.py` `EndToEnd` (D1, D2)
- [x] a fresh install wires the gate and the stamp says so; a kept settings.json without the hook
      gets the exact entry printed and the stamp says NOT wired; one that runs the gate is wired
      and gets no entry; the installed command exits 0 on garbage and with the gate file deleted,
      verified by `install_test.py` case `rule-gate-wired-0` (D3, D5)
- [x] a kept settings.json with its own hooks gets a merged copy holding both and is not written;
      a permissions entry naming the gate, a repeated `"hooks"` key and invalid JSON are NOT wired;
      a fresh install outside `~/.claude` is NOT confirmed wired, verified by `install_test.py`
      case `rule-gate-kept-settings-shapes-0` (D5)
- [x] `rule_coverage.py` matches with the gate's code, and every shipped rule still fires, verified
      by `rule_coverage_test.py` and `python3 harness/rule_coverage.py` in `scripts/check.sh` (D1)

Anti-weakening contract: the change does not weaken the suite versus the merge-base. Confirm each
before hand-off:

- [x] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [x] No new skipped tests versus the merge-base.

The suppression box is open on purpose: `install.sh` gains two `# shellcheck disable=SC2016`
lines. One is on the printed PreToolUse entry, because `$HOME` there is for the hook's shell to
expand when Claude Code runs it, not for `install.sh`. The other is on the Python source that
checks the wiring, where `$HOME` is text the check rewrites. They are new suppressions, and each
carries its reason inline. The operator decides whether they stand.

# Risks and rollback

- Risk: a Claude Code upgrade changes the transcript shapes or the matcher, and the fixture, built
  on 2.1.286's shapes, stays green. Mitigation: the gate fails open with `FAIL-OPEN` or `BLIND`
  log lines, and the probes are re-run on an upgrade (ADR-0008, D1's falsifier).
- Risk: a crash or a deleted gate file blocks every write. Mitigation: `main` always exits 0, the
  command ends in `|| true`, and `rule-gate-wired-0` runs both.
- Risk: the model ignores the inlined text and loops. Mitigation: the BLIND breaker allows once
  the gate's text is seen and still not counted, after 120 seconds with no result for the refused
  call, or after three refusals whose text never reached the model, and logs it.
- Rollback: `DISCIPLINE_RULE_GATE=off` in the environment, or remove the `hooks` block from
  `~/.claude/settings.json`. Reverting the change removes the gate file from future installs; an
  installed copy stays until deleted, and the `|| true` keeps a deleted one harmless.

# Notes

- A review ran the gate live in 35 headless sessions on 2.1.286; none of that is on the commit
  path, and the log is where to look in a real session.
- Fork subagents are untested (ADR-0008, Consequences); the breaker is their only cover.
- Python 3.8 is checked by parsing with the 3.8 grammar only; no 3.8 interpreter has run it.

# ADR-0008 acceptance gate: the deep-reason record

Passes per `harness/skills/adr-write/SKILL.md`. Acceptance is the operator's; the pass below informs
that read and substitutes for nothing. This record was written after the build, from the design's
second draft (which lists what the pass forced) and the probe files the pass produced. The pass's
own transcript is not kept in this repository, so what follows is the session's account of it, and
where a number is quoted it is one the pass or a later build measured.

## Pass 1 (pre-build attack on the design), 2026-09-30: SOUND-WITH-CHANGES, six changes folded in

A fresh-context adversary read the first design draft and the verified fact sheet (Claude Code
2.1.286, Haiku 4.5, headless probes) and ran a simulation of the draft's counting rules over real
transcripts. The simulation modeled the Reads a refusal would prompt and matched globs with an
approximate matcher; the transcripts predate the gate, so they hold no real refusals. Its charge was to find a case where the gate refuses forever, allows a write it should have
refused, or costs more than it saves.

**Verdict: the design holds, with six changes.** The gate's premise, that only a refusal changes
content a PreToolUse hook sees after generation, was not attacked successfully. The changes:

- **A subagent's Read would never count.** Draft 1 counted a full Read only through the
  `toolUseResult` field, and subagent transcripts mostly lack it: in the newest 400 subagent
  transcripts on the operator's machine, 214 of 225 Read results had none (counted later, during
  review). The simulation's loop of refusals for a subagent restated that assumption rather than
  observing it. Fixed (ADR-0008/D1): a Read counts when its `tool_use` (no offset, no
  limit) pairs by id with a `tool_result` that is not an error, with or without `toolUseResult`.
- **The refusal should carry the rule, not a reading list.** Draft 1 listed the rule paths to
  Read. A probe sent a refusal of about 61 KB with an instruction placed at its end; the model wrote
  the file with that instruction applied (1 of 1). Fixed (ADR-0008/D2): the refusal inlines each
  missing rule after a marker line, and the marker makes the refusal itself count as a load. Above
  400,000 bytes the refusal falls back to the list.
- **A refusal counter is the wrong breaker.** Draft 1 allowed the third attempt after two
  refusals for one missing set. Parallel writes in one assistant message all reach the hook before
  any refusal reaches the model, so a counter of two lets a third sibling through unchecked. Fixed
  (ADR-0008/D3): a pending set keyed by rule content, a 120-second
  window inside which a sibling gets a short refusal, and a BLIND allow, logged, once the gate has
  given a rule and still cannot see it.
- **Bash checking produced only false refusals.** Of 3,024 code-file write targets found in
  34,340 real Bash commands, 71 were literal paths inside the repository. Replayed against one
  session, the draft's Bash parser refused 6 times, all wrongly. Fixed (ADR-0008/D4): Bash is not
  gated, and the limit is documented.
- **The target set needed a boundary.** Draft 1 checked any target with a `.claude/rules` above
  it. Claude Code's loader, as read in the binary later, loads no path-scoped rule for a file
  outside every working directory (not measured), so the gate now checks only targets under
  `CLAUDE_PROJECT_DIR` (else the hook's `cwd`), and the matcher's required behaviors are listed
  one by one so the golden vectors can pin each.
- **The cost estimate was low.** Draft 1 said a refused Python write pulls about 8 rules (60 to
  90 KB). Measured against the kit's rules, a Python file matches 14 (113,453 bytes) and a Scala
  file 15 (165,483 bytes). The simulation of a three-day session gave 3 refusals and about 35k
  tokens, an estimate from modeled Reads.

Three questions the fact sheet had already settled, and the pass left standing: compaction does
not deadlock the remedy (after an in-process compaction that dropped the rule, a Read of the rule
returned full text); `InstructionsLoaded` cannot be the record (it carries no `agent_id` and does
not fire on a direct Read or a compaction restore); and fail-closed is not the safer posture (a
Claude Code format change would block every write on the machine).

## Found during the build, after the pass

- **The hook command must not exit 2 when the gate file is gone.** `python3` exits 2 for a
  missing script, and exit 2 from a PreToolUse hook blocks the call. The wired command is
  `python3 "$HOME/.claude/discipline/rule_gate.py" || true`, and `harness/fixtures/install_test.py`
  case `rule-gate-wired-0` runs it with the file deleted.
- **A pending entry must remember its compaction window.** Refused, then compacted before the
  retry, a rule would otherwise go BLIND. An entry from before the current boundary is stale, and
  its text is inlined again.
- **An allow with a warning sets only `additionalContext`.** Setting
  `permissionDecision: "allow"` would skip the user's own permission prompts.

## Found in review, after the build

A later review ran the built gate live in 35 headless sessions on 2.1.286 and read it against the
binary. Each finding was reproduced before it was fixed, and each fix has a fixture case that
fails without it.

- **A later call of the same response got through.** The gate counted its own refusal as soon as
  the refusal was on disk, which for a call waiting behind a slow tool is before the model has
  seen it. The second Write of one response landed without its rules and the log said nothing.
  Fixed (ADR-0008/D1): a result counts only for a later response, found by `message.id`.
- **Another hook's refusal can replace the gate's.** Claude Code keeps one reason per refused
  call. The gate then told the next call the text had been given, and after 120 seconds went
  BLIND. Fixed (ADR-0008/D3): the gate checks the refused call's own result, and gives the rule
  again when its text is not there.
- **Smaller gaps against Claude Code's own loader:** a symlinked rules directory, a worktree
  nested in its repository, YAML shapes in `paths:` the parser did not read, and globs where
  JavaScript's regex dialect differs from Python's. **And in the installer:** the printed block
  made a duplicate `"hooks"` key when pasted, and the wiring stamp came from a grep.

## Not settled by either

- The review's live runs are the only end-to-end evidence, and none runs on the commit path. The
  fixture drives the real gate against synthetic transcripts.
- Fork subagents copy the parent's read state; whether their transcripts show the parent's loads
  is untested. The BLIND breaker is the only cover.

# ADR-0008: The rule gate refuses a write until the path-scoped rules for its file are in the writing agent's context

**Status:** Proposed (2026-09-30; D5 amended in place 2026-10-01, before acceptance, to add the
repository-level copy and the deferral).
Acceptance gate: deep-reason pass, recorded in [reviews/ADR-0008-deep-reason.md](reviews/ADR-0008-deep-reason.md)
(SOUND-WITH-CHANGES; the six changes are folded into D1 to D4). Acceptance is the operator's read.

## Context

The kit ships 57 rules under `claude-project/rules/`, and every one is path-scoped: its `paths:`
frontmatter names the files it governs. Claude Code 2.1.286 loads such a rule only after a Read
of a matching file, or an @-mention of one. Write and Edit never load a rule, and neither does
Bash. A Write in the same assistant message as the Read that would load the rule runs before the
rule is attached. These facts were measured in the probes on 2.1.286 and confirmed again in a
re-measurement pass. Every probe's triggering Read was whole; whether a Read with `offset` or
`limit` of a matching file loads the rule was not measured.

So a rule is present when code is written only if something happened to read a matching file
first. An earlier audit measured this in one real session: 12 of 37 writes ran without their
language's rules. Nothing said so, because a rule that is absent and a rule that is followed
leave the same silence. The kit's own globs made it worse: until this change an ADR at
`docs/adrs/ADR-0001-x.md` reached one rule and a story at `stories/STORY-0001-x.md` reached none
(fixed in the same change; see `CHANGELOG.md`).

The constraints the gate has to live with, all measured on 2.1.286 unless marked:

- A PreToolUse hook runs after the model has generated the tool input. Whatever the hook adds,
  the content it would have shaped already exists.
- A `deny` decision, in JSON or by exit 2, holds under `bypassPermissions` and for subagent
  writes (16 runs). With an actionable reason the model Read the rule and retried (8 of 8). With
  a bare "Denied." it stopped after at most three attempts. The reason reaches the model with a
  prefix (`PreToolUse:Write hook error: `), so nothing may depend on its exact text.
- A subagent's hook input carries `agent_id`, but `session_id` and `transcript_path` are the
  parent's. The subagent's own transcript is at
  `<transcript_path minus .jsonl>/subagents/**/agent-<agent_id>.jsonl`. A fresh subagent starts
  with no path rules and inherits none (3 of 3).
- Compaction clears the loaded set and restores at most five files under a 50,000-token budget
  (read from the binary). In the one measurement the choice followed file modification time, not
  read order, and a rule file is usually old, so a rule is dropped once five newer files have
  been read. The compaction summary can paraphrase a rule without carrying it.
- At PreToolUse the transcript holds everything up to the previous turn, including that turn's
  rule loads. The current call's own entry may not be written yet: Claude Code writes a model
  response's entries when the response ends. A call that runs after the response has ended, as
  one waiting behind a slow tool does, finds the earlier calls' results of its own response on
  disk, results the model had not seen when it generated the call (measured in live runs of the
  gate itself). Every entry of one response carries its `message.id`, and the hook input carries
  the call's `tool_use_id`.
- When several PreToolUse hooks refuse one call, Claude Code keeps one reason (read from the
  binary), so a refusal's text can be replaced by another hook's.
- The `InstructionsLoaded` hook carries no `agent_id`, does not fire for a direct Read of the
  rule or for a compaction restore, and is fire-and-forget.

## Decisions

### D1: The calling agent's own transcript, after its last compaction boundary, is the only evidence of what is loaded

For each Write, Edit, MultiEdit or NotebookEdit, the gate computes the rules that apply to the
target and checks each against the calling agent's transcript: `transcript_path` for the main
thread, the subagent's own file when the hook input carries `agent_id`. It scans backward to the
last `compact_boundary` and no further. A rule counts as loaded on any of:

- a `nested_memory` attachment naming it (`attachment.path`);
- an `instructions` attachment listing it (`attachment.files[].path`);
- a `file` attachment naming it (`attachment.filename`), which is a compaction restore;
- a full Read of the rule: the `Read` tool_use with no `offset` and no `limit`, paired by
  `tool_use_id` with a `tool_result` that is not an error, whether or not `toolUseResult` is
  present (subagent transcripts mostly lack it);
- the gate's own refusal, recognized by the line `rule-gate: inlined sha256=<hex> path=<abs>`;
- a `file_unchanged` result, only after a counted load of the same path in the same window.

The compaction summary never counts, a partial Read never counts, and `InstructionsLoaded` is not
read at all. A rule also counts when any loaded file has the same sha256 as its content, which
covers a worktree copy of the same rule. A `tool_result`, the Read's or the gate's own, counts only
once the model has seen it, which is in its next response: a result answering another call of the
response the checked call belongs to does not count. That response is found by `message.id`, from
the checked call's own entry when it is on disk, else from the newest response on disk when one of
its calls has no result yet (the model cannot start a new response before then). Otherwise the
call is taken to open a new response.

Which rules apply is decided the way Claude Code decides it. The gate walks up from the target's
directory collecting `.claude/rules/**/*.md`, skipping `$HOME/.claude/rules` (user scope, matched
differently). As Claude Code's walker does, it follows a symlinked directory or file whose target
is inside the project and skips one whose target is outside it, and in a git worktree nested in
its own repository (Claude Code puts them under `.claude/worktrees/`) it skips the main checkout's
directories around the worktree. These two are read from the binary, not measured. Each rule's globs are matched against the target's path relative to the directory
that holds that `.claude`, with a port of the node-ignore matcher bundled in 2.1.286: case
insensitive, one trailing `/**` stripped, a slash-free pattern matching at any depth, a pattern
with a slash anchored, a pattern that matches a directory matching every file under it, and a
path starting with `..` never matching. A rule with no `paths:` loads at session start and is
skipped. A target outside the project root (`CLAUDE_PROJECT_DIR`, else the hook's `cwd`) is not
checked. That follows Claude Code's loader as read in the binary, not a measurement: it loads no
path-scoped rule for a file outside every working directory. A directory added with `--add-dir`
is a working directory too, and the gate does not check files there.

The scan took 0.024 s on a 54 MB transcript with a boundary and 0.50 s on one without.

### D2: On a miss the gate refuses the call and puts the full text of each missing rule in the refusal

The gate returns `permissionDecision: "deny"`. The reason holds, for each missing rule, the marker
line and then the rule's full text, and ends: "These rules are now in your context. Apply them and
retry the write in your NEXT message, not in this one." Because the marker counts as a load under
D1, the retry passes without a separate Read. If the inlined text would exceed
`DISCIPLINE_RULE_GATE_MAX_INLINE` bytes (default 400,000), the reason lists the paths instead and
says to Read each one whole, which counts under D1.

The gate does not add context and allow. By the time the hook runs, the content exists, so added
context could only shape the next write, not this one. A refusal is the one output that makes the
model generate the content again with the rule in view. In a probe, a refusal of about 61 KB with
an instruction at its very end produced a file carrying that instruction (1 of 1, Haiku 4.5).

The gate never returns `permissionDecision: "allow"`. Where it lets a call through with a warning,
it sets only `additionalContext`, so the user's own permission prompts still apply.

### D3: The gate fails open, never silently, and a pending set stops a refusal loop

When the gate cannot check (no transcript for the calling thread, a transcript in which nothing
parses, a tool input without its path, any internal error), it allows the call, appends a line to
`~/.claude/discipline/rule-gate.log` (`DISCIPLINE_RULE_GATE_LOG` overrides), and adds a one-line
warning as `additionalContext`. The log also records each `DENY`, `DENY-SIBLING` and `BLIND`, so it
shows when the gate was checking as well as when it was not. The process always exits 0, and the
wired command ends in `|| true`, because exit 2 from a PreToolUse hook blocks the call and
`python3` exits 2 when the script file is missing. `DISCIPLINE_RULE_GATE=off` disables the gate.

Per session and agent, a JSON state file under `~/.claude/discipline/state/` records each rule the
gate has given, keyed by content hash, with the time, the compaction window and the `tool_use_id`
of the call it refused. It is written through a temporary file and a rename, and files untouched
for seven days are pruned. When a later call needs a pending rule, the gate looks for the refused
call's result:

- the transcript now counts the rule: the entry is cleared;
- the result holds the rule but answers a call of this same response: a sibling, refused with a
  short reason that does not repeat the text, however long it waited;
- the result is there without the rule: another hook's refusal took its place, so the rule is
  given again, in full;
- the result is not on disk yet: a sibling, until 120 seconds have passed;
- the gate's text is on disk and seen and the gate still cannot count it, or the result has been
  missing for 120 seconds, or the rule has been given three times without the model seeing it:
  the gate cannot see its own remedy. The call is allowed, a `BLIND` line is logged, the warning
  names the rule, and that rule is never refused again in that state file;
- the entry was made before the current compaction boundary: compaction dropped the text, so the
  entry is stale and the text is given again.

A format change in Claude Code must not block every write on the machine, which is why the gate
fails open. The log is what keeps "the gate was not looking" apart from "nothing was wrong".

### D4: Bash is not gated

The gate's matcher is `Write|Edit|MultiEdit|NotebookEdit`, and it returns nothing for any other
tool. Across the operator's transcripts, 34,340 real Bash commands held 3,024 write targets with a
code-file extension, and 71 of them were literal paths inside the repository. The rest were in
temporary directories, named by variables, relative to a `cd` earlier in the command, or text
inside a heredoc body that a parser misreads as a redirect. Replayed against one session, the
first draft's Bash parser refused 6 times, and all 6 were wrong. A gate that refuses wrongly
teaches the model to work around it, or the user to turn it off, and either loses the checks
that work.

So a file written by Bash is written without this check. This is a known limit, not a solved
case, and it has a second half: in bypass mode the system prompt suggests Bash for file changes,
which steers writes away from the gate.

### D5: The gate runs from the user's settings or from a repository's own, a user-level copy defers to a repository's wired copy, and it does not run in chain phases

**The user-level copy.** `install.sh` copies `reference/rule_gate.py` to
`~/.claude/discipline/rule_gate.py` on every run. `claude-user/settings.json` carries the hook: a
`PreToolUse` entry with matcher `Write|Edit|MultiEdit|NotebookEdit` (MultiEdit is absent from
2.1.286's tool list but present in its hook code) and command
`python3 "$HOME/.claude/discipline/rule_gate.py" || true`. A fresh
install writes that settings.json and so wires the gate. An existing settings.json is backed up
and left in place, as it always was. The installer reads it as JSON, as Claude Code does (a
repeated key keeps its last value), and calls the gate wired only when a PreToolUse entry whose
matcher covers Write and Edit runs the copy this install wrote. Otherwise it prints the PreToolUse
entry, says where in the file it goes, and, for a file that parses with no repeated key, writes a
copy with the entry added beside it for the user to compare and move into place. It never prints
a whole `"hooks"` key, because pasted beside an existing one it would replace it. The
`KIT-VERSION` stamp gains a `rule_gate:` line saying "installed and wired", "installed but NOT
wired" with the reason, or, when `CLAUDE_HOME` is not `~/.claude`, "installed but NOT confirmed
wired", since the command names `~/.claude`'s copy.

User level because the rules live in each repository but the check must run in every one, with
one copy and one log. The gate reads whatever `.claude/rules` it finds above the target, so a
repository with no kit rules costs one directory walk and nothing else.

**The repository-level copy.** `install.sh --refresh-rules` also vendors the gate into the
repository it refreshes, so a repository can carry the check itself and pin it to the release its
rules came from. It reads `reference/rule_gate.py` from the same release tag, in the same
`git archive` call, as `claude-project`. A tag without that file, which is every tag cut before
this decision, skips the gate: the run says so, the `.claude/rules/.kit-version` stamp records
`rule_gate: not in tag <tag>`, and the repository's `.claude/hooks` and settings are left as they
were; a gate an earlier tag vendored stays, and the stamp says so and whether a settings file
runs it. A `.claude` or `.claude/hooks` that is a symlink gets no gate and no wiring
(`in tag <tag>, NOT vendored`), since the file would land outside the repository. Otherwise the
file lands at `<repo>/.claude/hooks/rule_gate.py` under the refresh's existing
rules for a rule file: a copy whose bytes match no release tag the checkout holds is copied aside
first, a symlink is replaced rather than written through, and an unreadable copy stops the run
before anything is copied. Then the refresh wires it in `<repo>/.claude/settings.json` with the
PreToolUse entry whose command is `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/rule_gate.py" ||
true`. Claude Code sets `CLAUDE_PROJECT_DIR` for a hook command to the directory the session
started in (measured once on 2.1.286, with a project hook logging its environment). The JSON work
is done by `python3` from the installer, never by text substitution, and it follows these cases
in order:

- `settings.local.json` or `settings.json` already has a PreToolUse command hook that runs this
  repository's copy, by the deferral's test below, under a matcher selecting all four write
  tools: nothing changes (`vendored+already-wired`). A copy in `settings.json` beside one in
  `settings.local.json` would run the gate twice. One that runs it under a matcher selecting
  fewer is named and nothing is written (`vendored, NOT wired`), for the same reason.
- `settings.json` is absent: it is created holding only the hooks block (`vendored+wired`),
  whether or not the repository is a git work tree.
- `settings.json` is tracked by git with no uncommitted changes, parses with no repeated key, and
  is laid out exactly as a JSON writer would lay it out at its own indent: the entry is appended
  to `hooks.PreToolUse`, every other key and hook kept, so `git diff` shows the addition and
  `git checkout` takes it back (`vendored+wired`). The new text goes to a temporary file in
  `.claude/` that replaces `settings.json` only once written whole, so a failed write leaves the
  file as it was.
- anything else (untracked, modified, invalid JSON, outside a git work tree, a symlink, or a
  layout a rewrite would change): the file is left alone, and the run prints the entry and where
  it goes (`vendored, NOT wired: <reason>`).

`settings.local.json` is only ever read. Rewriting a file git can restore is the line this
decision draws: the user-level `settings.json` has no such undo, so it is still never edited.

**Two copies, one check.** With both wired, each copy would refuse the same write. So a copy that
is not the project's own allows the call with no output and logs one `DEFER` line when a project
rule applies to the target and the project's `.claude/settings.json` or
`.claude/settings.local.json` has a PreToolUse command hook whose matcher selects the tool and
whose command runs that project's `.claude/hooks/rule_gate.py`, and that file exists. The
project root is `CLAUDE_PROJECT_DIR`, else the hook's `cwd`. A command runs the file when its
script, after an optional python interpreter, is `$CLAUDE_PROJECT_DIR/.claude/hooks/rule_gate.py`,
the relative `.claude/hooks/rule_gate.py` (hooks run in the project directory), or an absolute
path to the same file; one that only mentions the path, such as another checkout's copy,
`rule_gate.py.orig` or an `echo`, runs something else or nothing. A command reaching the file
through `$CLAUDE_PROJECT_DIR` counts only while that variable is set, since otherwise the
project's command cannot find it. The project's copy never defers, so the gate that runs is the
one pinned to the repository's rules. A copy knows it is the project's by the path it was run
from and by file identity, not by where symlinks resolve: through a `.claude/hooks` linked out of
the repository the project copy resolves outside the root, and judged by that it deferred to
itself. A settings file that does not parse wires nothing and leaves the
user-level copy checking: when the two copies cannot agree, the cost is a second refusal, never a
write with no check.

Chain phases are outside it. ADR-0004/D3 makes every phase invocation exclude user-scope settings
and carry the sequencer's pinned settings as its only project source, so neither copy runs there:
a phase does not read the repository's own `.claude/settings.json` either. Whether rules are in
context when a phase writes code is not established; gating it would belong in the phase's
pinned settings, and that is a separate decision this record does not take.

## Consequences

- A write to a file with rules now carries those rules, or is refused, or is allowed with a log
  line saying why not. Silence in the log does not prove the gate looked: it writes nothing when
  it checked and found nothing missing, and also nothing when the gate file is missing (the
  `|| true` hides the error), when `DISCIPLINE_RULE_GATE=off` is set, or when the target is outside
  the project. The log separates a gate that ran and could not see from one that saw nothing
  missing; it cannot show a gate that did not run.
- The cost is context. A Python file matches 14 of the kit's rules (113,453 bytes, about 28k
  tokens); a Scala file matches 15 (165,483 bytes). The text arrives once per context window,
  because compaction usually drops it and the next write brings it back. A simulation of a
  three-day session, with the Reads modeled and an approximate glob matcher, gave 3 refusals and
  about 35k tokens; it is an estimate, not a replay of what happened.
- A refused write throws away the content the model generated for it, and the retry generates it
  again.
- Each gated call inside a project costs a read of every rule file in each `.claude/rules`
  directory above the target, and, when any rule applies, a backward scan of the transcript
  (D1's timings).
- `harness/rule_coverage.py` now loads the gate's frontmatter reader and matcher by file path, so
  the coverage check and the gate cannot disagree about what a glob matches.
- A new glob shape in a shipped rule needs new golden vectors. The fixture fails until they are
  regenerated from the matcher bundled in Claude Code, by the generator recorded in
  `harness/fixtures/rule_gate_vectors.json`. Its provenance says how to recreate the matcher it
  needs: the npm package `ignore` at 7.0.5, which gave the same file byte for byte, or the text
  cut from the binary.
- Every fact this rests on is scoped to Claude Code 2.1.286. A new version can change the
  transcript shapes, the loading rules or the bundled matcher with no commit here.
- Known limits, stated so nobody reads the gate as covering them: Bash writes are not gated (D4);
  the bypass-mode prompt steers toward Bash; fork subagents copy the parent's read state, and
  whether their transcripts show the parent's loads is untested, so the BLIND breaker is their
  only cover; a rule loaded on a branch that was later rewound still counts; two sibling calls
  racing on the state file may both inline the full text; the gate does not run in chain phases;
  a call whose own entry is not on disk, in a response whose calls on disk all have results, is
  taken to open a new response, so if Claude Code ever wrote an earlier call's refusal to disk
  before a later call of the same response, that later call would be let through (not seen in
  the live runs, where a response's entries reach disk together when it ends); the deferral
  trusts the project's settings files as written, so a session that does not load project hooks
  while the files still wire the gate leaves neither copy checking, and nothing here detects it.
  One CLI flag is enough: `--setting-sources` without `project` (measured twice on 2.1.286 with
  Haiku 4.5: one `DEFER`, no `DENY`, the write landed without the rule), as are
  `disableAllHooks` and a managed policy allowing only managed hooks. The user copy cannot see
  whether the project copy ran for the same call, since the two hooks run in parallel, so the
  `DEFER` line says only that this copy did not check the write.
- Loading a rule is not evidence that it is followed. Probes found a loaded rule followed for one
  or two short rules (8 of 8, 6 of 6, Haiku 4.5, headless). Whether 14 rules competing in one
  context are followed is not measured, and this gate does not measure it.

## Alternatives

- **Read `InstructionsLoaded` instead of the transcript.** It is cheaper, but it carries no
  `agent_id`, so a subagent's load and the main thread's look the same, and it does not fire for
  a direct Read of a rule or a compaction restore. It would refuse writes whose rules are in
  context and could not tell which agent loaded what.
- **Add the rules as context and allow.** Simpler, never blocks, and does nothing for the write
  in hand, whose content already exists when the hook runs (D2).
- **Refuse with a list of paths to Read.** The first draft. It costs a round of Reads per refusal,
  and it relied on counting a Read through `toolUseResult`, which subagent transcripts mostly
  lack: in the newest 400 subagent transcripts on the operator's machine, 214 of 225 Read results
  had none, against 0 of 459 in 374 main-thread transcripts. Kept as the fallback above the
  inline cap.
- **Allow after two refusals.** The first draft's breaker. Sibling writes in one message all reach
  the hook before any refusal reaches the model, so a counter lets the third sibling through
  unchecked. Replaced by the pending set (D3).
- **Fail closed.** A Claude Code change to the transcript format would block every write in every
  repository on the machine until the gate was fixed or removed.
- **Gate Bash on a best-effort parse.** Rejected on D4's numbers.
- **Make every rule unconditional.** Dropping `paths:` loads each rule at session start. The 57
  rules are 594,939 bytes, about 150k tokens, in every session whatever it touches, against
  113 KB once per window for a Python file under the gate.
- **Keep `fnmatch` in the coverage check.** It differs from node-ignore (`*` crosses `/` in
  `fnmatch`), so the coverage check could pass a glob Claude Code never matches.

## Falsification condition

Each decision names its court. Where the court is a fixture, it runs on every commit through
`scripts/check.sh`; where it is not, the record says so.

- **D1**: the gate counts a rule as loaded when the agent does not have it, or misses a load it
  does have, or matches a glob differently from Claude Code. Court:
  `harness/fixtures/rule_gate_test.py`. Its counting cases drive each way a rule counts and each
  near miss (a partial Read, an errored Read, an unanswered Read, a load before the boundary, the
  summary text, `file_unchanged` with no prior load) through synthetic transcripts in the entry
  shapes 2.1.286 wrote; its selection cases cover the subagent's own file and its non-inheritance;
  and it replays 13,755 glob and path pairs plus 11 multi-glob sets generated by the bundled
  node-ignore, failing when a shipped glob has no vectors. Its same-response cases put a refused
  call's result on disk ahead of a later call of the same response, and its rule-selection cases
  cover a symlinked rules directory and a worktree nested in its repository. What the fixture cannot see is Claude
  Code changing under it: the shapes and the vectors are 2.1.286's. That half is watched by the
  log, where a format change shows as `FAIL-OPEN` or `BLIND` lines, and by re-running the probes
  when Claude Code is upgraded. That is review-watched, with no court.
- **D2**: a refusal that inlines the rules is not followed by a retry that applies them: the model
  ignores the text, loops, or gives up. Not mechanical. The evidence is 8 of 8 retries after an
  actionable reason and 1 of 1 for a 61 KB inlined reason, Haiku 4.5 only. The standing
  observation is the log: a `DENY` followed by a `BLIND` for the same rule means the remedy did
  not land. The fixture holds the shape of the refusal (marker, full text, closing line, the cap
  fallback) and that the retry passes once the refusal is in the transcript.
- **D3**: the gate blocks a write because of its own failure, or allows a write unchecked with no
  log line. Court: `harness/fixtures/rule_gate_test.py` (garbage on stdin, a planted internal
  error, a missing or unreadable transcript and a tool input without a path each exit 0 and log
  `FAIL-OPEN`; the sibling, clear, BLIND, stale-after-compaction and replaced-by-another-hook
  paths each have a case) and `harness/fixtures/install_test.py` case `rule-gate-wired-0`, which
  runs the installed hook command on garbage and with the gate file deleted and requires exit 0.
- **D4**: Bash turns out to carry a real share of rule-scoped writes that a parser can check
  without false refusals. Not mechanical; the standing observation is re-running the transcript
  scan behind D4's numbers. The fixture holds the decision itself: Bash, Read, Agent and Glob
  produce no output and no log line.
- **D5**: an install leaves the gate unwired without saying so, a refresh vendors a gate other
  than the tag's or edits a settings file it should have left alone, the user-level copy defers
  to a project copy that will not run (or does not defer to one that will), or the gate runs
  inside a chain phase. Court: `install_test.py` cases `rule-gate-wired-0`, which checks the
  stamp says wired or NOT wired for a fresh home, a kept settings.json and one that already runs
  the gate, and that the printed entry equals the one in `claude-user/settings.json`, and
  `rule-gate-kept-settings-shapes-0`, which holds a kept file with its own hooks, a permissions
  entry naming the gate, a repeated `"hooks"` key, invalid JSON and a fresh install outside
  `~/.claude` to NOT wired, and the merged copy to both hooks. The repository-level copy's
  courts are the `install_test.py` cases named `gate-*`: a tag without the gate is skipped and
  stamped; the vendored file holds the tag's bytes, not HEAD's; an absent settings.json is
  created; a tracked, clean one is merged with `git diff` showing only the addition and
  `git checkout` reverting it; an already-wired one, in either settings file, is unchanged byte
  for byte; a modified, untracked, invalid, non-git or hand-laid-out one is untouched and the
  entry printed; `settings.local.json` is never written; a second refresh changes nothing; the
  copy-aside, symlink and unreadable-file rules hold for the gate as for a rule; a hook that
  names another file, or runs this one under a Bash matcher, is not counted as wired, each answer
  checked against the gate's own deferral; a write cut off partway leaves `settings.json` byte for
  byte; a linked `.claude` or `.claude/hooks` gets nothing written through it; and a link to
  nothing is reported as a link. The deferral's court is `rule_gate_test.py` `Deferral`: the
  user-level copy defers through either settings file, for each spelling that runs the project
  copy, past a stray non-object in the hooks list, and as a subprocess, and does not defer when
  the project file is missing, the matcher leaves out the tool, the settings do not parse,
  `CLAUDE_PROJECT_DIR` is unset, or the command only mentions the path; a write no rule covers
  logs nothing; the project's copy, run as a subprocess, refuses, including through a
  `.claude/hooks` linked out of the repository. `scripts/tag-consumption-check.sh` fails a
  refresh region that reads `$KIT/reference/`, and `install_test.py` case
  `court-gate-from-checkout-1` plants one.
  The phase exclusion is ADR-0004/D3's, and its court is that record's.

**No live test is on the commit path.** `scripts/check.sh` runs offline, in minutes, with no
`claude` binary and no credentials, and must give the same answer twice. A live session needs all
three, spends money, and varies with the model. So the fixture tests the gate against synthetic
transcripts in the measured shapes, and runs the hook as a subprocess end to end. Two things only
a live session shows are not re-checked by any commit: that Claude Code still writes those shapes,
and that the model follows the refusal. A review ran the gate live in 35 headless sessions on
2.1.286 (Haiku 4.5 in all but three, Opus in those), and found the same-response defect D1 now
covers; those runs are not part of any commit check.

## Cross-references

- Supersedes: None.
- Superseded by: None.
- Related: [ADR-0004](ADR-0004-substrate-choice.md)/D3 (phase invocations exclude user-scope
  settings, so this gate does not run in a phase) and /D5 (version-scoped facts);
  `reference/rule_gate.py`; `harness/fixtures/rule_gate_test.py`;
  `harness/fixtures/rule_gate_vectors.json`; `harness/rule_coverage.py`; `install.sh`;
  `scripts/tag-consumption-check.sh` (ADR-0002/D7's court, which now watches the gate's path);
  `claude-user/settings.json`; `stories/STORY-0017-the-rule-gate.md`.

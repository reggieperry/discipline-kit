# The D7 headless substrate probe, run 2026-08-12

The measurement ADR-0003/D7 specifies and STORY-0001 carries, run against the installed
harness. Two legs; raw outputs retained beside this record as `probe-stream.jsonl`,
`probe-stderr.txt`, `probe2-stream.jsonl`, `probe2-stderr.txt`. Harness version, recorded
from the run: **2.1.224 (Claude Code)**. One mechanical redaction in the retained raws: the
operator home path is substituted `/home/OPERATOR` throughout (the harness's init events leak
it; this repository's scrub gate forbids it), and nothing else is altered. Authentication: the stderr carries the design's own
§4.7 line verbatim—API key precedence over the subscription login—so the metered tier is
what a headless run bills, as the design stated.

## Setup, exactly as D7 specifies

A scratch repository (one base commit) whose project `.claude/` holds exactly two files: an
agent definition (`agents/probe-worker.md`, declaring `isolation: worktree`, instructing the
worker to commit one file named `probe.txt`) and a project-scope PreToolUse hook on Bash
appending to a marker file outside the repository. Invocation:
`claude -p "<spawn instruction>" --output-format stream-json --verbose
--dangerously-skip-permissions`.

## Leg 1: repo-level agent definition

| Limb | Verdict | Observable |
|---|---|---|
| (a) subagent ran | **PASS**, with a decisive registration finding below | `task_started`/`task_notification` events in the stream; the completion present |
| (b) worktree isolation | **PASS** | `worktreePath` reported under `.claude/worktrees/agent-a9d2…`; `probe-commit` (`bd9a9fe`) on branch `worktree-agent-a9d2…` with `probe.txt` containing `probe`; parent `main` untouched at the setup commit |
| (c) hooks fired headlessly | **PASS** | the marker file carried 6 firings after leg 1, under `--dangerously-skip-permissions` |

**The registration finding, which is the probe's sharpest result:** the repo-level
`.claude/agents/probe-worker.md` was **not registered** in headless `-p` mode—the harness
offered only the five built-in agent types, and `Agent(subagent_type: "probe-worker")`
failed with "Agent type 'probe-worker' not found." The headless main agent disclosed this,
substituted `general-purpose` with the definition's instructions and `isolation: worktree`
as a tool parameter, and independently verified its own subagent's work against the
repository ("a report of success is not the same as success"—the epistemics held without
being asked for). So the limb's capability half passes; the repo-registration half fails at
2.1.224.

## Leg 2: the same definition supplied via `--agents`

The design's §4.4 invocation always carried `--agents <json>`; leg 2 measures whether that
route closes leg 1's gap. It does: `subagent_type: "probe-worker"` resolved and ran, its own
worktree branch (`worktree-agent-af74…`) carries a `probe-commit` (`24fe34e`), parent `main`
untouched, and the marker rose to 9 firings.

**One further finding:** with the `--agents` JSON *and* the repo definition file both
present, the worker received two instruction sources (the JSON named `probe2.txt`; the repo
file named `probe.txt`) and followed the repo file's, disclosing the conflict. The sequencer
rule this implies: **phase definitions come from exactly one source**—the pinned `--agents`
payload per ADR-0003/D4, with no same-named repo-level definition present in the judged
tree.

## What the measurement settles

The three session properties the chain requires all hold headlessly at 2.1.224: subagent
spawning (via `--agents`, not via repo auto-registration), worktree isolation with the
measured handoff behavior, and project-scope PreToolUse hooks under bypass permissions. All
three candidate substrates therefore remain *capable*; the choice among them falls to
ADR-0003/D7's named criteria—disinterest of the looker and bounded context—and lands as
the successor record, through the same gate cycle as every other record.

Three operational facts for the sequencer stories, found rather than sought—the third
found by this repository's own scrub gate refusing to admit the raws: worktrees
materialize under `.claude/worktrees/` inside the parent repository, which appears as an
untracked directory—STORY-0005's porcelain-empty seam precondition must account for that
path or the worktrees must be placed outside; the `--agents` payload is the natural
pinned home for phase definitions, which is exactly where ADR-0003/D4 wants them; and
**user-scope SessionStart hooks fire in headless runs**—the operator's own startup hook
injected machine-identity and infrastructure details into both legs' transcripts (redacted
in the retained raws, marked in place). An unattended phase therefore inherits whatever the
operator's user-level hooks inject unless the sequencer's invocation pins its settings
sources—a requirement for STORY-0005/0006, and a second reason the event log lives outside
any tree that gets packaged.

## Correction and leg 3, same day—the successor record's pre-draft gate audited this record

The gate verified every citation against the raws and the surviving scratch tree, and three
statements above do not survive it. Corrected here rather than edited away:

- **The one-source finding above is confounded, and its mechanism was misread.** The leg-2
  worker's own account reads "my original task named `probe2.txt` … the follow-up named
  `probe.txt` … I followed the later one"—the follow-up being the *invoking prompt*, whose
  content the parent had relayed from the repo definition file. Repo file and prompt agreed,
  so the observation could not separate them. **Leg 3 discriminates**: with the repo
  definition removed and a neutral invoking prompt ("its definition knows"), the `--agents`
  JSON's instruction executed—`probe3.txt`, commit `19afee2`, its own worktree branch,
  marker at 11. The corrected rule set: the pinned `--agents` definition governs when it is
  the sole source; the invoking prompt's relayed content can override it; and leg 1's
  fallback shows the wrapper's main agent improvising a substitute brief **from the judged
  tree**—ADR-0001/D3's defect reached by initiative inside the wrapper. The sequencer rule
  is therefore three-part: the judged tree carries no `.claude/agents/` at all (asserted from
  the filesystem), the wrapper fails closed on a missing pinned type, and the invoking prompt
  carries spawn-by-name only, never phase instructions.
- **The redaction disclosure above was wrong twice.** There are two redactions, not one (the
  home path substitution, and the SessionStart hook output replaced by a marked line), and
  the substitution was not "throughout": the operator's username survived 28 times via the
  scratch path's *slug* form and `ls -l` ownership columns, which the scrub gate's
  slash-anchored TIER-1 pattern is blind to—the gate read clean on files carrying the
  identifier. All retained raws are now redacted in all three forms (path, slug, bare
  username); widening the gate's pattern and pinning it with a fixture case is queued with
  the in-flight hygiene slice.
- **A design VERIFIED mark is measured false at 2.1.224.** §4.8 states worktrees are
  "git-excluded via `.git/info/exclude`, so it never appears in the parent's `git status`.
  VERIFIED." The scratch repo's `.git/info/exclude` is the stock template and the parent's
  porcelain prints `?? .claude/worktrees/` (retained in `probe-artifacts.txt`). The
  operational fact above stands with a stronger ground: the porcelain-empty precondition
  cannot rely on an exclusion the harness does not write.

`probe-artifacts.txt` retains what STORY-0001's criteria 1 and 7 name and the first
commit of this record did not keep: the `.claude` listings at both setup states, the find
output, the full ref list, the hook marker verbatim, the stock exclude file, and the parent
porcelain. Raw leg-3 outputs retained beside the others, same redactions.

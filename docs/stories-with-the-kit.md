# Stories with the kit

Two ways a story reaches the loop — you write it, or you pull it from the board your team already
uses — and both end in the same place: one pre-registered claim per acceptance criterion, on the
ledger, before any code. This walks both paths, and the small read client that bridges the second
one.

**Prerequisite: the authoring layer is on.** It ships default-off; the **Enable authoring** prompt
in the README turns it on (the four skills land in `.claude/skills/`, and the `docs/adrs/` and
`stories/` directories with their templates land in the repo). Everything below assumes
`story-write`, `story-tighten`, and `story-intake` are loadable.

## The shape both paths share

A story is a prose spec whose **acceptance criteria** are the payload. The loop does not build
against the prose; it builds against the criteria once each has become a parked claim
(`ledger-preregister`). "Parked" means the claim is appended `unverified` under a check name the
gate cannot yet run, so nothing auto-signs; at landing you supersede it to a real check
(`repo-check`) and the commit-path gate signs that successor. The story's job is to produce good
criteria; the ledger's job is to hold you to them.

Keep that in view through both paths — the only thing that differs is where the story text comes
from.

## Path A — write the story with Claude Code

Four moves, each a prompt to Claude Code.

1. **Draft it.** "Write a story for `<the work>` with `story-write`." The skill fills the
   story template — the portable frontmatter (`id`, `title`, `deps`, `labels`, `sensitive_files`,
   `status`) and the six body sections (Context, Problem, Approach, Acceptance criteria, Test plan,
   Out of scope). The Problem is grounded at `path:line` against HEAD, and the Acceptance section
   carries the anti-weakening contract verbatim: assertion count not reduced, no new suppressions,
   no new skipped tests, all versus the merge-base. The file lands at `stories/<id>-<slug>.md` in
   `draft`.

2. **Tighten it.** "Tighten it with `story-tighten`." The skill scores the draft against a
   six-dimension readiness rubric, splits a story too big for one red-first slice, cuts any
   acceptance line no check can reach, and re-grounds a stale `path:line`. When the story turns on a
   decision chosen among alternatives, that decision is an ADR — write it with `adr-write` and have
   the story cite it. The story turns `ready` only when every section survives this pass.

3. **Pre-register the criteria.** "Register the acceptance criteria as parked claims per
   `ledger-preregister`, claim-first as their own ledger-only commit." Each acceptance criterion
   becomes one appended claim, and that commit touches `ledger/claims.jsonl` and nothing that builds
   the system — the precedence timestamp the `tdd-precedence` audit reads. One criterion, one claim:

   ```
   echo '{"claim":"<acceptance criterion, verbatim>","subject":"<slice>","source":"claude-code","kind":"assertion","status":"unverified","check":"<non-runnable-name>"}' | ledger/append
   ```

4. **Build against the claims.** Red-first per slice where the work is detector-class, green under
   the gate, then supersede each parked claim to `check: repo-check` at landing and let the
   commit-path gate sign it. The chain reads `parked → repo-check successor → gate-signed`; the
   mechanics are the `ledger-discharge` skill.

The through-line: the story's acceptance criteria *are* the claims, written before the code, so a
green suite can never be read wider than the criteria it discharged.

## Path B — pull the story from your team's board

The kit is tracker-agnostic on purpose. Its frontmatter "carries no tracker-specific fields, so a
story travels to any board without rewriting," which is the same reason it ships **no board
connector**: it gives you the intake discipline, and you bring the fetch. Two ways to bring it.

### Option 1 — a ready MCP server (fastest, when it exists)

If your tracker already has an MCP server, wire it into Claude Code. Then `story-intake` fetches the
ticket and its board id together over MCP — "an MCP fetch from a tracker hands you the story and its
board id together" — and you skip straight to intake (below). Nothing to build. This is the right
first thing to check.

### Option 2 — have Claude Code build a thin read client

When there is no MCP for your board, or you want a scriptable bridge you own, have Claude Code write
a small read client against your board's REST API. Most work trackers expose one — an endpoint that
returns an issue by id as JSON. This is the "build code to talk to the board" step, and it is
ordinary kit work: the client is code, so it goes through the gate red-first like anything else.

**a. Least-privilege token, outside the repo.** Mint a *read-scoped* API token on your board. Put it
in the environment, never in the tree — the connector reads `os.environ`, and the value lives in a
gitignored env file or your shell profile, exactly as the kit handles any secret. A leaked board
token is a real incident; treat it like an API key.

```
export BOARD_URL=https://your-board.example.com
export BOARD_TOKEN=…            # read-scoped, in an env file the repo ignores
```

**b. Build the client as a slice.** Prompt Claude Code:

> "Build a read-only board client as a kit slice. It takes a story id and returns the story
> normalized to our story-template shape — `id`, `title`, `body`, and the acceptance-criteria list.
> Read the API base URL from `BOARD_URL` and the token from `BOARD_TOKEN`; never hardcode either and
> never write either to disk. Read-only — GET the issue, no mutation. Register the acceptance claim
> per `ledger-preregister` first, go red-first with a fixture against a recorded sample response,
> then add the fetch. Show me the parked claim and the red run."

**c. The client's one job is normalization.** Input: a board id such as `PROJ-1234`. Output: the
story mapped onto the template's fields — the board's summary to `title`, its description to `body`,
its acceptance-criteria field (or a parsed checklist) to the criteria list. Keep that mapping in one
place; a board that names its fields differently is a config change, not a rewrite. The client does
not score and does not build — it hands `story-intake` something to score.

**d. Intake the fetched story.** "Intake `PROJ-1234` via the board client." `story-intake` treats
the incoming story as untrusted until scored, runs the same six-dimension rubric, and parks one
claim per acceptance criterion — with the **board id embedded verbatim in the claim text**, because
the ledger schema has no external-reference field and the text is where the id lives durably:

   ```
   echo '{"claim":"<acceptance criterion, verbatim> (board: PROJ-1234)","subject":"<slice>","source":"claude-code","kind":"assertion","status":"unverified","check":"<non-runnable-name>"}' | ledger/append
   ```

   Every dimension that scores low becomes an explicit question back to the author — never a silent
   repair. Intake scores, parks, and questions; it does not build and it does not rewrite the story.

**e. Interact — the write-back is opt-in.** Intake's gap questions are meant to reach the author. If
you want them posted as a board comment instead of pasted by hand, add *one* write path to the
client — a `post-comment` call that needs a comment-scoped token — and keep it separate from the
read path, so reading never depends on holding a write grant. Least privilege: do not take a scope
you will not use.

## Where the two paths converge

By now both paths have produced the same two artifacts: a story — yours or the board's — and one
parked claim per acceptance criterion. From here it is the ordinary loop. Build each slice
red-first, supersede its parked claim to `repo-check` at landing, and let the commit-path gate sign.
Nothing signs except the gate; a `deep-reason` or review pass is testimony that attests and signs
nothing.

For Path B the embedded board id keeps traceability running both ways. A signed `clm-NNNN` names the
ticket it discharges, and the ticket finds its claims with a grep:

```
grep 'PROJ-1234' ledger/claims.jsonl
```

When the ticket changes after intake — a criterion tightened, added, or struck — re-run intake on
the new version rather than editing parked claims in place: a changed criterion supersedes its
claim, a struck one retires it, an added one is scored and parked like any other. The board id stays
the anchor across the revision, so the trail from the current ticket to the live claims never goes
cold.

## Keep the connector honest

- **Read-first, least-privilege.** A read token for the fetch; a separate, opt-in token only if you
  post questions back. Never one over-scoped token doing both by default.
- **The board id byte-exact.** A paraphrased or reconstructed id breaks the return trip; a claim
  that cannot trace to its source is a claim that lost its story.
- **The connector is code, held to the same bar.** It rides the gate red-first — no new
  suppressions, no assertion-count loss versus the merge-base. A bridge you did not test is a bridge
  that silently returns the wrong story, and the loop would then build the wrong thing with a clean
  conscience.

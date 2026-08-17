# Using the SDLC chain in another repository on this machine

These instructions are written for a Claude Code instance that has been handed a repository on
this machine and asked to upgrade it with the discipline kit's latest work, including the SDLC
chain, and then run a story through the chain. Follow them in order. Where a step is the
operator's judgment or spends money, it says so; do not guess past those.

## What this gives you, and what it does not

The chain builds a change to a repository as a sequence of headless phases, each graded by a
mechanical postcondition, then evaluated by an eight-conjunct merge stage, and it advances a
dedicated throwaway clone rather than the real repository. It exists because an AI's output is
not trustworthy on its own; the chain is the machinery that grades each phase and refuses to
advance on anything but a mechanical pass.

Read this ceiling before you start, because it governs everything below:

- **The chain is attended-only on an unhardened host.** A human authors the phase briefs and
  watches the run. In-process fencing is friction, not containment (ADR-0005); what reaches the
  real trunk rests on the human who transplants it. Do not run a brief you did not read, and do
  not present a green chain run as a reason to skip reading the diff.
- **Every phase spends real API calls.** A phase is a live `claude -p` session. Do not run a
  story you were not asked to run.
- **The chain does not touch the real repository's trunk.** It advances a dedicated clone; a
  human transplants the result. Under the `merge-local` posture used here the chain never pushes
  anything.
- **You author the per-project material.** The tools are shared and generic; the postconditions,
  briefs, phase tables, and the fence are yours to write for this repository. This document gives
  a complete worked example you can adapt.

## Prerequisites

- The discipline-kit checkout on this machine, on branch `docs/sdlc-chain-design`. Call its path
  `KIT`. The operator will tell you where it is; do not guess.
- `python3` (3.11+), `git`, and an `ANTHROPIC_API_KEY` in the environment (the phases bill the
  metered tier).
- The target repository you were handed. Call its path `TARGET`. It must be a git working tree.

Throughout, shell variables stand for paths you fill in:

```
KIT=<the discipline-kit checkout>          # ask the operator
TARGET=<the repository to upgrade>         # the repo you were handed
```

## Step 1—upgrade the target with the chain capability

Run the kit's `install-chain.sh` against the target. It snapshots the chain tools from the branch
into a machine-wide immutable cache, vendors the kit's rules into the target, and writes a
per-target chain profile. It changes no chain code and copies no tool into the target's tree.

```
"$KIT/install-chain.sh" --dir "$TARGET" --terminal merge-local --provision-root
```

- `--terminal merge-local` is the no-forge posture: the chain advances the clone's local `main`
  and never pushes. This is the right choice for a first run and for a repository with no forge
  set up. The alternative, `--terminal open-pr`, pushes a story branch and opens a pull request;
  it needs a forge and its own review, and is out of scope here.
- `--provision-root` creates the empty pinned-root scaffold (the directories the chain reads and
  writes). Without it the method creates nothing and prints what to create.

Read the command's output. It prints:

- the tools snapshot path, of the form `<cache>/discipline-chain/tools/<sha>/`—call it `SNAP`;
- the per-target pinned root, of the form `/var/lib/discipline-chain/<slug>-<hash>/`—call it
  `ROOT`. This root is unique to this repository; two repositories never share one.
- an operator checklist of what stays your work (the rest of this document).

Capture the two paths it prints:

```
SNAP=<the tools snapshot path from the output>
ROOT=<the pinned root path from the output>
```

Confirm the upgrade landed and the tools resolve the target's profile:

```
# The pinned root exists but is empty of content; startup must fail closed until you provision it,
# then pass once the root is a directory. First, before authoring anything:
python3 "$SNAP/harness/chain/core.py" startup --root "$TARGET"
# expect: "core: posture: terminal merge-local, push never, ... pinned root <ROOT>"  (exit 0)
```

If `startup` prints a `VOID` line and a nonzero exit, read which condition it names and fix that
before continuing; the chain is fail-closed by design and will not run until its posture is
sound.

## Step 2—author the pinned material (the worked example)

The chain reads its graders, phase prompts, and phase plan from the pinned root. This example sets
up a trivial but complete two-phase story called `HELLO` that the chain can run end to end: a
build phase that writes a file, and a review phase that emits a coverage receipt. Adapt it to a
real change once you have seen it run.

A note on why two phases: the merge stage's fourth conjunct grades a coverage receipt through a
`receipt-complete` postcondition, so a runnable story needs a phase that produces one. This is the
minimum complete shape.

### 2a. The fence settings

The phase runs with `--dangerously-skip-permissions`, so the spawn-tool denial must live in the
pinned settings the harness materializes into each phase. Write it once:

```
cat > "$ROOT/settings/settings.json" <<'JSON'
{
  "permissions": {
    "deny": ["Task", "Agent", "Workflow"]
  }
}
JSON
```

### 2b. The pinned rules copy (the receipt denominator)

The review phase's receipt is graded against the coding rules. Seed the pinned copy from the
kit's rules that `install-chain.sh` already vendored into the target:

```
cp "$TARGET"/.claude/rules/*.md "$ROOT/rules/"
```

### 2c. The two postconditions

A postcondition is a directory with an executable `run` script and two fixture trees, `red` and
`green`. On load the chain demonstrates the postcondition: it runs `run` against a copy of the
`red` tree (which must exit 1) and against the `green` tree (which must exit 0). At grading time it
runs `run <tree>` with one argument, the absolute path of the tree to judge, and reads the exit as
0 pass / 1 fail / anything else could-not-run. The `run` script's working directory is its own
pinned directory, not the tree.

Phase 1's grader—the build artifact exists:

```
mkdir -p "$ROOT/postconditions/hello-artifact/fixtures/red" \
         "$ROOT/postconditions/hello-artifact/fixtures/green"
cat > "$ROOT/postconditions/hello-artifact/run" <<'SH'
#!/bin/sh
tree="$1"
[ -d "$tree" ] || exit 2
[ -f "$tree/hello.txt" ] || exit 1
grep -qx 'the chain ran here' "$tree/hello.txt"
SH
chmod +x "$ROOT/postconditions/hello-artifact/run"
echo "a tree with no artifact" > "$ROOT/postconditions/hello-artifact/fixtures/red/README"
echo "the chain ran here"      > "$ROOT/postconditions/hello-artifact/fixtures/green/hello.txt"
```

Phase 2's grader—the coverage receipt is present and complete. This wrapper hands the merged
tree to the kit's receipt court, which lives in the shared snapshot. Note the `--root` argument:
it points the court at the target so it reads the same pinned rules:

```
mkdir -p "$ROOT/postconditions/receipt-complete/fixtures/red" \
         "$ROOT/postconditions/receipt-complete/fixtures/green/chain"
cat > "$ROOT/postconditions/receipt-complete/run" <<SH
#!/bin/sh
exec python3 "$SNAP/harness/chain/receipt.py" \\
  --receipt "\$1/chain/receipt.txt" \\
  --root "$TARGET"
SH
chmod +x "$ROOT/postconditions/receipt-complete/run"
echo "a tree with no receipt" > "$ROOT/postconditions/receipt-complete/fixtures/red/README"
# The green fixture pins the currently receipt-owed rule set; regenerate it if the rules change:
python3 "$SNAP/harness/chain/receipt.py" --receipt /dev/null --root "$TARGET" 2>&1 \
  | sed -n 's/^.*receipt-owed rule(s) from rules\/: //p' | tr ', ' '\n\n' | sed '/^$/d' \
  | while read -r r; do printf '%s covered\n' "$r"; done \
  > "$ROOT/postconditions/receipt-complete/fixtures/green/chain/receipt.txt"
```

Confirm both postconditions demonstrate (red exits 1, green exits 0) before going further:

```
python3 "$SNAP/harness/chain/loader.py" hello-artifact  --root "$TARGET"
python3 "$SNAP/harness/chain/loader.py" receipt-complete --root "$TARGET"
# each must end: "postcondition-loader: loadable '...' ... (demonstrated: green 0, red 1)"  (exit 0)
```

### 2d. The phase briefs

A brief's bytes are the phase's entire prompt. The build brief tells the phase to write the
artifact and commit only it; the review brief tells it to emit the receipt. Both forbid touching
`.claude/` (the harness materializes the fence there) and forbid staging anything else.

```
cat > "$ROOT/briefs/HELLO-phase-1.md" <<'MD'
You are the build phase of chain story HELLO, running headlessly in a git worktree, which is your
current working directory.

Your entire task:
1. Create a file `hello.txt` at the worktree root containing exactly one line, no leading or
   trailing spaces:

   the chain ran here

2. Stage and commit ONLY that file:
   git add hello.txt
   git commit -m "HELLO phase 1: the artifact"

Hard rules: stage only hello.txt (never git add -A or git add .); never create, modify, or stage
anything under .claude/ (a settings file placed there by the harness must remain, uncommitted); do
not push, branch, tag, or spawn any subagent. After the commit, verify with git status --porcelain
that the only untracked path is .claude/settings.json, then stop.
MD

cat > "$ROOT/briefs/HELLO-phase-2.md" <<MD
You are the review phase of chain story HELLO, running headlessly in a git worktree (your current
working directory), which holds the story's work.

Your entire task: produce the reviewer's coverage receipt and commit it.
1. The pinned rules copy is at $ROOT/rules/*.md. A rule is receipt-owed when its
   "**Enforcement grade:**" line's grade begins with "partly mechanical" or "review and
   convention"; rules beginning "mechanically enforced" are excluded.
2. Write chain/receipt.txt in this worktree (create chain/), one line per receipt-owed rule:
   <rule-file-name> covered
3. Verify before committing:
   python3 $SNAP/harness/chain/receipt.py --receipt chain/receipt.txt --root $TARGET
   This must exit 0; if not, fix the receipt and re-run.
4. Stage and commit ONLY the receipt:
   git add chain/receipt.txt
   git commit -m "HELLO phase 2: the coverage receipt"

Hard rules: stage only chain/receipt.txt; never touch .claude/; do not push, branch, tag, or spawn
a subagent. After the commit, verify git status --porcelain shows only .claude/settings.json
untracked, then stop.
MD
```

### 2e. The phase table

The phase table maps each phase number to its brief and its postcondition. One line per phase,
`<number> <brief-name> <postcondition-name>`:

```
cat > "$ROOT/phases/HELLO" <<'TABLE'
# HELLO: a two-phase example story
1 HELLO-phase-1.md hello-artifact
2 HELLO-phase-2.md receipt-complete
TABLE
```

### 2f. The plan file

The merge stage's third conjunct checks that every file the story changed was declared. List the
story's paths, one per line, in a file outside every tree (put it under the pinned root):

```
printf 'hello.txt\nchain/receipt.txt\n' > "$ROOT/sequencer/HELLO-plan.txt"
```

## Step 3—mint the dedicated clone

The chain grades and advances a throwaway clone, never the real repository. Make one, sever every
remote so nothing it does can leave the machine, give it a local identity (the phase's repointed
HOME hides the operator's git config), and give it a local `main` for the merge-local act to
advance.

```
# Commit the profile and vendored rules install-chain wrote, so the clone carries them:
git -C "$TARGET" add .claude/ && git -C "$TARGET" commit -m "chain: profile and rules" || true

CLONE=<a throwaway path outside the target, e.g. a sibling dir>
git clone --no-hardlinks "$TARGET" "$CLONE"
git -C "$CLONE" remote remove origin        # zero remotes: a push has nowhere to go
git -C "$CLONE" checkout -B main            # a local main for merge-local to advance
git -C "$CLONE" config user.name  "Chain Runner"
git -C "$CLONE" config user.email "chain@localhost"
git -C "$CLONE" config commit.gpgsign false
git -C "$CLONE" config tag.gpgsign false
git -C "$CLONE" remote -v                    # confirm: no output (zero remotes)
```

## Step 4—run the story

One invocation drives the whole story: the posture and identity gates, each phase's spawn and
seam and grading, the merge stage, and the post-batch audit. The `--commit-check` is a
tree-relative script in the clone that runs the repository's own commit-path check (the merge's
first conjunct runs it against the merged tree); if the repository has no such check, point it at
a script that exits 0, and understand that conjunct is then a no-op.

```
python3 "$SNAP/harness/chain/sequencer.py" run \
  --root "$CLONE" --repo "$CLONE" --story HELLO \
  --commit-check <tree-relative check script, e.g. scripts/check.sh> \
  --plan "$ROOT/sequencer/HELLO-plan.txt" \
  --timeout 1800
```

Watch it. It prints each gate, each phase's spawn and grading, the eight merge conjuncts, and the
merge-local act. Exit 0 means the story ran to a completed merge; exit 1 means a phase or the merge
parked (a real refusal, read what it names); exit 2 means a precondition could not run (fix it and
re-invoke—a dead phase re-runs cleanly).

On success the clone's `main` carries the merged story, and the pinned root holds the run's record
under `$ROOT/records/HELLO/`.

## Step 5—transplant the result (the human act)

Under `merge-local` the chain advanced only the throwaway clone. Bringing the result into the real
repository is the human act the whole design rests on: read the diff, then transplant it. This is
the operator's judgment, not a mechanical step, and it is where responsibility for the change sits.

```
# Inspect what the chain built:
git -C "$CLONE" log --oneline -3 main
git -C "$CLONE" diff main~1 main            # or the story branch; read it

# When satisfied, transplant the story's commit(s) into the target (operator's call):
git -C "$TARGET" cherry-pick -x <the story commit sha from the clone>
```

Do not automate this away. A green run is not a substitute for reading the change.

## Adapting the example to real work

Once `HELLO` runs, a real story is the same shape with real content:

- Write a postcondition whose `run` script mechanically decides your acceptance criterion, with a
  `red` fixture it fails and a `green` fixture it passes. The grader is the point; make it check
  the thing that matters, not a proxy.
- Write phase briefs that are the actual prompts, and read them before running.
- Keep `receipt-complete` as the last phase's grader unless you deliberately change the merge
  conjuncts.
- List the real changed paths in the plan.
- Author each brief and postcondition yourself; the chain grades honestly only if its graders are
  honest.

## What is not covered here, and stays operator or root work

- **Hardening for unattended operation.** Running the chain unattended (by cron, no human
  watching) requires the machine hardening in `INSTALL-HARDENING.md` (a dedicated no-sudo
  run-user, root-owned pinned material, the sandbox), and the start gate and envelope runner
  refuse until it holds. Until then the chain is attended-only, which is the correct posture for
  everything above. Do not attempt an unattended run.
- **The open-pr posture.** Pushing branches and opening pull requests needs a forge and its own
  merge rules; run merge-local first.
- **Provisioning the pinned root as root.** The scaffold above is a plain writable directory,
  correct for attended runs. Hardening changes its ownership; that is root work, deferred.

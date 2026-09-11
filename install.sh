#!/usr/bin/env bash
#
# install.sh — place the user-level discipline into ~/.claude.
#
# Copies the portable skills, the deep-reasoning template, the review gate, and
# (guarded) the user CLAUDE.md and settings.json. Existing CLAUDE.md / settings.json
# are never clobbered — they are backed up and a merge note is printed instead.
#
# Project-level pieces (rules, guides, memories) are NOT auto-installed — they go
# per-repo; the instructions are printed at the end.

set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_HOME:-$HOME/.claude}"
stamp="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo backup)"

# --- args ---
REFRESH_RULES=0
TARGET="."
TAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --refresh-rules) REFRESH_RULES=1; shift ;;
    --dir) TARGET="$2"; shift 2 ;;
    --tag) TAG="$2"; shift 2 ;;
    *) echo "usage: install.sh [--refresh-rules [--dir <repo>] [--tag <tag>]]" >&2; exit 2 ;;
  esac
done
if [ -n "$TAG" ] && [ "$REFRESH_RULES" = 0 ]; then
  echo "usage: install.sh [--refresh-rules [--dir <repo>] [--tag <tag>]]" >&2
  exit 2
fi

# g: git confined to the kit checkout, immune to the redirecting variables an inherited hook
# environment may carry. `-C` re-scopes the working directory and NOT the gitdir, so a run
# inheriting GIT_DIR (a pre-commit hook exports it, absolute in a linked worktree) would read
# another repository's tags while appearing to operate on the kit. Same helper as
# scripts/refresh-from-pack.sh, same reason. versionsort.suffix pins pre-release ordering:
# without it `--sort=-version:refname` ranks v2.0.0-rc1 ABOVE v2.0.0, so an rc tag would win
# a plain refresh until a newer final release landed.
g() {
  env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_OBJECT_DIRECTORY \
    -u GIT_COMMON_DIR -u GIT_CONFIG_GLOBAL -u GIT_CONFIG_SYSTEM \
    git -c versionsort.suffix=- -C "$KIT" "$@"
}

# --- --refresh-rules: re-sync the kit-shipped rules into an ALREADY-installed repo ---
# Existing installs do not pick up rule updates on their own — the per-project rules copy is a manual
# step. This re-copies claude-project/rules/*.md into the repo's .claude/rules/, overwriting the
# kit-shipped rules (a rule the repo authored under another name is untouched, and CLAUDE.md is never
# touched). Run it inside the repo, or point at one with --dir.
#
# The rules come from a RELEASE TAG's tree, never from whatever the checkout's working tree holds:
# ADR-0002/D7 — consumers resolve tags the operator mints, so a bad merge on main cannot reach a
# consuming repo before the backstop acts. The tag is the newest v-prefixed tag by VERSION sort,
# or the one named with --tag. Chosen over `git describe --tags --abbrev=0` because the kit
# carries non-release tags (archive/kit-chain, pre-harness-baseline) that describe could resolve,
# and because version sort does not depend on which commit the consumer's clone happens to sit
# on. The tag's tree is read with `git archive`, never checked out, so the working tree is
# untouched. A checkout with no .git, or none of the release tags, is refused by name — there is
# no working-tree fallback, because the fallback would be exactly the path D7 removes.
if [ "$REFRESH_RULES" = 1 ]; then
  cd "$TARGET"
  if [ ! -d .claude/rules ]; then
    echo "✖ no .claude/rules in $(pwd) — run the per-project rules install first (see install.sh with no args)." >&2
    exit 1
  fi
  if ! g rev-parse --git-dir >/dev/null 2>&1; then
    echo "✖ $KIT is not a git checkout, so no release tag can be resolved — refusing to copy from a bare tree (ADR-0002/D7). Clone the kit repository instead." >&2
    exit 1
  fi
  if [ -n "$TAG" ]; then
    if ! g rev-parse --verify --quiet "refs/tags/$TAG" >/dev/null; then
      echo "✖ tag '$TAG' does not exist in $KIT." >&2
      exit 1
    fi
  else
    TAG="$(g tag --list 'v[0-9]*' --sort=-version:refname | head -n 1)"
    if [ -z "$TAG" ]; then
      echo "✖ no release tag (v*) in $KIT — refusing to copy from the working tree (ADR-0002/D7). Fetch tags (git fetch --tags) or name one with --tag." >&2
      exit 1
    fi
  fi
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  if ! g archive "$TAG" claude-project/rules | tar -x -C "$tmp"; then
    echo "✖ could not read claude-project/rules from tag $TAG." >&2
    exit 1
  fi
  if ! compgen -G "$tmp/claude-project/rules/*.md" >/dev/null; then
    echo "✖ tag $TAG carries no rules (no claude-project/rules/*.md in its tree) — nothing copied." >&2
    exit 1
  fi
  cp "$tmp"/claude-project/rules/*.md .claude/rules/
  echo "refreshed .claude/rules/ in $(pwd) from discipline-kit $TAG"
  exit 0
fi

echo "Installing user-level discipline into $DEST"
mkdir -p "$DEST/skills" "$DEST/discipline"

# --- skills (safe: additive, distinct dirs) ---
cp -R "$KIT/claude-user/skills/deep-reason" "$DEST/skills/"
cp -R "$KIT/claude-user/skills/pr-review" "$DEST/skills/"
echo "  skills: deep-reason, pr-review"

# --- reference artifacts ---
cp "$KIT/reference/deep-reasoning-agent.md" "$DEST/deep-reasoning-agent.md"
cp "$KIT/reference/sdlc-gate.py" "$DEST/discipline/sdlc-gate.py"
cp "$KIT/reference/review-checklist.md" "$DEST/discipline/review-checklist.md"
cp "$KIT/reference/voicing-document.md" "$DEST/discipline/voicing-document.md"
echo "  reference: deep-reasoning-agent.md, discipline/{sdlc-gate.py,review-checklist.md,voicing-document.md}"

# --- CLAUDE.md (guarded) ---
if [[ -e "$DEST/CLAUDE.md" ]]; then
  cp "$DEST/CLAUDE.md" "$DEST/CLAUDE.md.bak-$stamp"
  echo "  CLAUDE.md EXISTS — backed up to CLAUDE.md.bak-$stamp; NOT overwritten."
  echo "    Merge the deep-reason section from $KIT/claude-user/CLAUDE.md by hand."
else
  cp "$KIT/claude-user/CLAUDE.md" "$DEST/CLAUDE.md"
  echo "  CLAUDE.md installed"
fi

# --- settings.json (guarded) ---
if [[ -e "$DEST/settings.json" ]]; then
  cp "$DEST/settings.json" "$DEST/settings.json.bak-$stamp"
  echo "  settings.json EXISTS — backed up to settings.json.bak-$stamp; NOT overwritten."
  echo "    Review $KIT/claude-user/settings.json and merge the permissions you want."
else
  cp "$KIT/claude-user/settings.json" "$DEST/settings.json"
  echo "  settings.json installed (conservative: local git only, no auto-bypass)"
fi

GATE_PATH="$(printf %q "$DEST/discipline/sdlc-gate.py")"

cat <<EOF

User-level install done.

Per-project step (run inside each repo you want the discipline to govern):

  mkdir -p .claude/rules .claude/sdlc-discipline/guides
  cp $KIT/claude-project/rules/*.md                     .claude/rules/
  cp $KIT/claude-project/sdlc-discipline/guides/*.md    .claude/sdlc-discipline/guides/

The rules auto-load by path glob (e.g. **/*.py) when you edit matching files.

To refresh the rules in an already-installed repo after updating the kit:

  $KIT/install.sh --refresh-rules            # run inside the repo (or add --dir <repo>)

Methodology memories (optional, per project): copy into the project's memory dir
so they load each session, keeping one-line-per-memory in MEMORY.md:

  cp $KIT/memories/*.md  <your-project-memory-dir>/

Run the differential gate on a branch in its checkout, from the project directory (the top of
the repository, or the subdirectory that holds the project); the work does not have to be
committed. The baseline is captured in a worktree checked out at the merge-base:

  unset \$(git rev-parse --local-env-vars)
  BASE=\$(git merge-base HEAD origin/main)
  P=\$(git rev-parse --show-prefix)
  WT=\$(mktemp -d); OUT=\$(mktemp -d); GC1=\$(mktemp -d); GC2=\$(mktemp -d)
  git worktree add --quiet --detach "\$WT" "\$BASE"
  if [ -d node_modules ]; then ln -s "\$PWD/node_modules" "\$WT/\${P}node_modules"; fi
  (cd "\$WT/\$P" || exit 2; GOLANGCI_LINT_CACHE="\$GC1" python3 $GATE_PATH baseline --sha "\$BASE" --out "\$OUT" >&2) &&
    GOLANGCI_LINT_CACHE="\$GC2" python3 $GATE_PATH diff --baseline-dir "\$OUT"
  rc=\$?
  git worktree remove --force "\$WT"; rm -rf "\$OUT" "\$GC1" "\$GC2"
  (exit "\$rc")

Replace origin/main with the branch the work merges into. The block ends with the gate's exit
code: 0 pass or advisory, 1 blocked, 2 could not run. For what else exits 1, and for running
the block as a pre-commit hook, see "Using it" in $KIT/README.md.

What each toolchain needs installed: see "What the gate needs" in $KIT/README.md.
EOF

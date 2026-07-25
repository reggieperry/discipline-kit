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
while [ $# -gt 0 ]; do
  case "$1" in
    --refresh-rules) REFRESH_RULES=1; shift ;;
    --dir) TARGET="$2"; shift 2 ;;
    *) echo "usage: install.sh [--refresh-rules [--dir <repo>]]" >&2; exit 2 ;;
  esac
done

# --- --refresh-rules: re-sync the kit-shipped rules into an ALREADY-installed repo ---
# Existing installs do not pick up rule updates on their own — the per-project rules copy is a manual
# step. This re-copies claude-project/rules/*.md into the repo's .claude/rules/, overwriting the
# kit-shipped rules (a rule the repo authored under another name is untouched, and CLAUDE.md is never
# touched). Run it inside the repo, or point at one with --dir.
if [ "$REFRESH_RULES" = 1 ]; then
  cd "$TARGET"
  if [ ! -d .claude/rules ]; then
    echo "✖ no .claude/rules in $(pwd) — run the per-project rules install first (see install.sh with no args)." >&2
    exit 1
  fi
  cp "$KIT"/claude-project/rules/*.md .claude/rules/
  ver="$(grep -m1 -oE 'v[0-9]+\.[0-9]+\.[0-9]+' "$KIT/CHANGELOG.md" 2>/dev/null || echo v0.0.0)"
  echo "refreshed .claude/rules/ in $(pwd) from discipline-kit $ver"
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

Run the differential gate on a branch:

  python3 ~/.claude/discipline/sdlc-gate.py baseline --sha \$(git merge-base HEAD origin/main) --out /tmp/base
  python3 ~/.claude/discipline/sdlc-gate.py diff --baseline-dir /tmp/base
EOF

#!/usr/bin/env bash
#
# install-chain.sh -- upgrade another repository ON THIS MACHINE to the SDLC chain capability,
# sourced from THIS branch of the discipline kit.
#
# THE MODEL, three moves and zero chain-code changes:
#
#   1. A SHARED, SHA-named, immutable TOOL SNAPSHOT. The chain runtime is archived out of the
#      branch (git archive of the resolved commit, so it is the committed tree and never the
#      working tree's untracked __pycache__) into a machine-wide cache OUTSIDE every target. The
#      chain runs as `python3 <snapshot>/harness/chain/sequencer.py run --root <target> ...`, so
#      the grader lives outside the judged tree, where a phase's committed diff cannot reach it.
#      The snapshot is a copy, not a live pointer, and honours the kit's copy-not-share rule; it
#      differs from `install.sh --refresh-rules` only in WHERE the copy lands.
#
#   2. The kit's rules VENDORED into the target's .claude/rules/, exactly as --refresh-rules does.
#
#   3. A per-target chain PROFILE written into the target's .claude/chain/profile.toml. The tools
#      resolve their own siblings by layout and read the target's posture from ITS profile, so a
#      per-target pinned_root dissolves the cross-target story-id collision with no runtime edit.
#
# This upgrades the CAPABILITY only. Authoring the target's postconditions, briefs, phase tables,
# the fence settings and the pinned examiner copy; minting the dedicated clone; and provisioning
# or hardening the pinned root stay operator work, printed as a checklist at the end. The target's
# chain is ATTENDED-ONLY until INSTALL-HARDENING lands (ADR-0005); this method never implies
# unattended readiness. core.py startup and loader.py fail CLOSED until the pinned root exists,
# which is the honest gate.

set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
stamp="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo backup)"

usage() {
  echo "usage: install-chain.sh --dir <target> --terminal open-pr|merge-local" >&2
  echo "                        [--branch <ref>] [--pinned-root <path>]" >&2
  echo "                        [--tools-dir <path>] [--provision-root]" >&2
}

# --- args ---
DIR=""
TERMINAL=""
BRANCH="docs/sdlc-chain-design"
PINNED_ROOT=""
TOOLS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/discipline-chain/tools"
PROVISION_ROOT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --terminal) TERMINAL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --pinned-root) PINNED_ROOT="$2"; shift 2 ;;
    --tools-dir) TOOLS_DIR="$2"; shift 2 ;;
    --provision-root) PROVISION_ROOT=1; shift ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$DIR" ] || [ -z "$TERMINAL" ]; then
  usage; exit 2
fi
if [ ! -d "$DIR" ]; then
  echo "✖ target '$DIR' is not a directory." >&2; exit 1
fi
DIR="$(cd "$DIR" && pwd)"

# The terminal act and its paired push scope (ADR-0002/D1). The pairing is a genuine per-repo fact
# supplied by the operator, never invented here: open-pr pushes story and PR branches, merge-local
# pushes nothing. core.py startup rejects any other pairing, so an inverted map fails at the gate.
case "$TERMINAL" in
  open-pr) PUSH="branches-only" ;;
  merge-local) PUSH="never" ;;
  *) echo "✖ --terminal must be 'open-pr' or 'merge-local', got '$TERMINAL'." >&2; exit 2 ;;
esac

# The per-target pinned root, default derived so no two repositories share one story-id space.
slug="$(basename "$DIR")"
slug="${slug//[^A-Za-z0-9._-]/-}"
if [ -z "$PINNED_ROOT" ]; then
  PINNED_ROOT="/var/lib/discipline-chain/$slug/"
fi

# g: git confined to the kit checkout, immune to the redirecting variables an inherited hook
# environment carries. `-C` re-scopes the working directory and NOT the gitdir, so a run inheriting
# GIT_DIR (a pre-commit hook exports it, absolute in a linked worktree) would otherwise read
# another repository. Same helper and same reason as install.sh.
g() {
  env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_OBJECT_DIRECTORY \
    -u GIT_COMMON_DIR -u GIT_CONFIG_GLOBAL -u GIT_CONFIG_SYSTEM \
    git -C "$KIT" "$@"
}

# One cleanup for every scratch directory this run mints. A staging dir renamed into place no
# longer exists, so removing it again is a harmless no-op.
TMPDIRS=()
cleanup() {
  local d
  for d in "${TMPDIRS[@]:-}"; do
    [ -n "$d" ] && rm -rf "$d"
  done
}
trap cleanup EXIT

# The chain runtime the snapshot carries: the eight sequencer sources (they import each other, so
# no cherry-pick), the transcript audit the sequencer spawns, the rule grades receipt imports, and
# the two unattended-run modules that complete the capability. NAMED PATHS ONLY -- never the kit's
# .git, never the kit's own profile.toml (its pinned_root and trusted_base are wrong for a target).
TOOL_PATHS=(
  harness/chain/core.py
  harness/chain/advance.py
  harness/chain/attempt.py
  harness/chain/invoke.py
  harness/chain/loader.py
  harness/chain/merge.py
  harness/chain/receipt.py
  harness/chain/sequencer.py
  harness/transcript_audit.py
  harness/rule_grades.py
  harness/unattended_run.py
  harness/unattended_start_gate.py
)

# --- Act 1: resolve the branch to a commit ---
if ! g rev-parse --git-dir >/dev/null 2>&1; then
  echo "✖ $KIT is not a git checkout, so no branch can be resolved -- clone the kit repository." >&2
  exit 1
fi
if ! SHA="$(g rev-parse --verify --quiet "${BRANCH}^{commit}")"; then
  echo "✖ branch '$BRANCH' does not resolve to a commit in $KIT." >&2
  exit 1
fi
short="${SHA:0:12}"
echo "install-chain: kit $KIT at $BRANCH ($short)"

# The harness version the enabling facts are scoped to, copied from the branch's own profile so the
# target does not carry a version the kit never measured. Fail closed if the branch declares none.
if ! HARNESS_VERSION="$(g show "${SHA}:.claude/chain/profile.toml" \
      | sed -n 's/^harness_version[[:space:]]*=[[:space:]]*"\(.*\)"[[:space:]]*$/\1/p' | head -n1)" \
   || [ -z "$HARNESS_VERSION" ]; then
  echo "✖ could not read harness_version from ${BRANCH}:.claude/chain/profile.toml." >&2
  exit 1
fi

# --- Act 2: materialize the shared tool snapshot, SHA-named and immutable ---
mkdir -p "$TOOLS_DIR"
SNAPSHOT="$TOOLS_DIR/$SHA"
if [ -d "$SNAPSHOT" ] && [ ! -f "$SNAPSHOT/PROVENANCE" ]; then
  # A partial snapshot from a crashed run: clear it so the rename below lands cleanly.
  rm -rf "$SNAPSHOT"
fi
if [ -f "$SNAPSHOT/PROVENANCE" ]; then
  echo "install-chain: tools snapshot $short already present at $SNAPSHOT (no-op)"
else
  staging="$(mktemp -d "$TOOLS_DIR/.staging.XXXXXX")"
  TMPDIRS+=("$staging")
  if ! g archive "$SHA" -- "${TOOL_PATHS[@]}" | tar -x -C "$staging"; then
    echo "✖ could not archive the chain runtime from $short." >&2
    exit 1
  fi
  {
    echo "branch: $BRANCH"
    echo "sha: $SHA"
    echo "created: $(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
    echo "tools: ${TOOL_PATHS[*]}"
  } > "$staging/PROVENANCE"
  mv "$staging" "$SNAPSHOT"
  echo "install-chain: tools snapshot written to $SNAPSHOT"
fi

# --- Act 3: vendor the kit's rules into the target ---
mkdir -p "$DIR/.claude/rules"
rulestmp="$(mktemp -d)"
TMPDIRS+=("$rulestmp")
if ! g archive "$SHA" -- claude-project/rules | tar -x -C "$rulestmp"; then
  echo "✖ could not read claude-project/rules from $short." >&2
  exit 1
fi
if ! compgen -G "$rulestmp/claude-project/rules/*.md" >/dev/null; then
  echo "✖ $short carries no rules (no claude-project/rules/*.md) -- nothing vendored." >&2
  exit 1
fi
cp "$rulestmp"/claude-project/rules/*.md "$DIR/.claude/rules/"
echo "install-chain: rules vendored into $DIR/.claude/rules/"

# --- Act 4: write the per-target chain profile (guarded, never clobbered) ---
mkdir -p "$DIR/.claude/chain"
profile="$DIR/.claude/chain/profile.toml"
if [ -e "$profile" ]; then
  cp "$profile" "${profile}.bak-${stamp}"
  echo "install-chain: profile EXISTS -- backed up to profile.toml.bak-${stamp}; NOT overwritten."
  echo "    Merge the derived posture by hand: terminal=\"$TERMINAL\", push=\"$PUSH\","
  echo "    harness_version=\"$HARNESS_VERSION\", pinned_root=\"$PINNED_ROOT\"."
else
  cat > "$profile" <<EOF
# The chain profile for '$slug', written by install-chain.sh from discipline-kit
# $BRANCH ($short) on $stamp. It declares THIS repository's chain posture -- the keys
# harness/chain/core.py startup and harness/chain/loader.py read at run time.

# ADR-0002/D1: the chain's terminal act and the push scope it pairs with. Supplied by the operator
# as --terminal, a genuine per-repository fact. core.py startup rejects any other pairing.
terminal = "$TERMINAL"
push = "$PUSH"

# ADR-0004/D5: the Claude Code version the enabling facts are scoped to, copied from the kit's
# branch profile at install. A version bump is a re-probe obligation, watched by a reviewer.
harness_version = "$HARNESS_VERSION"

# ADR-0004/D3: a phase invocation pins the sequencer's settings as its only project source.
settings_sources = "pinned"

# ADR-0001/D3: the absolute out-of-tree root the examiner material resolves from. Per-target, so no
# two repositories share a story-id space. ONE ROOT PER REPO; never point two repositories at one
# root. The directory does not exist until the machine-hardening checklist (INSTALL-HARDENING
# Step 3) creates it root-owned 0755; until then loader.py VOIDs and core.py startup refuses, which
# is the honest fail-closed gate rather than an aspiration.
pinned_root = "$PINNED_ROOT"

# ADR-0002/D3.2: the path prefixes a chain story may not touch. Seeded with the settings root and
# the sequencer's own sources, so core.py startup's trusted-base check passes. This is NOT the
# complete cage: extend it with this repository's CI workflows, its commit-path check script, and
# its graded rule corpus before running a chain.
# TODO(operator): complete trusted_base for this repository's real cage.
trusted_base = [
  ".claude/",
  "harness/chain/",
]
EOF
  echo "install-chain: profile written to $profile"
fi

# --- Act 5: the pinned root (opt-in scaffold only; default creates nothing) ---
if [ "$PROVISION_ROOT" = 1 ]; then
  for sub in postconditions briefs phases rules settings worktrees streams records sequencer; do
    mkdir -p "$PINNED_ROOT/$sub"
  done
  echo "install-chain: pinned-root scaffold created (empty) under $PINNED_ROOT"
  echo "    NOTE: a scaffold is not a hardened root. INSTALL-HARDENING Step 3 makes it root-owned"
  echo "    0755 and outside every working tree; until then the chain stays ATTENDED-ONLY."
else
  echo "install-chain: pinned root NOT provisioned (default). To harden it, as root:"
  echo "    mkdir -p $PINNED_ROOT{postconditions,briefs,phases,rules,settings,worktrees,streams,records,sequencer}"
  echo "    then apply INSTALL-HARDENING Step 3 (root-owned 0755, outside every working tree)."
fi

# --- Act 6: the run wrapper (a generated pointer to the shared snapshot) and the checklist ---
run_wrapper="$DIR/.claude/chain/run.sh"
if [ -e "$run_wrapper" ]; then
  echo "install-chain: run.sh EXISTS -- the snapshot is $SNAPSHOT; update it if you re-pinned."
else
  cat > "$run_wrapper" <<EOF
#!/usr/bin/env bash
# Generated by install-chain.sh. Runs the chain from the SHARED, immutable tool snapshot against
# this repository. Re-run install-chain.sh to re-pin a newer branch tip (it mints a new snapshot).
#
# usage: run.sh <dedicated-clone> <story-id> <commit-check-cmd> [extra sequencer args...]
set -euo pipefail
SNAPSHOT="$SNAPSHOT"
ROOT="$DIR"
CLONE="\${1:?usage: run.sh <dedicated-clone> <story-id> <commit-check-cmd> [args...]}"
STORY="\${2:?usage: run.sh <dedicated-clone> <story-id> <commit-check-cmd> [args...]}"
CHECK="\${3:?usage: run.sh <dedicated-clone> <story-id> <commit-check-cmd> [args...]}"
shift 3
exec python3 "\$SNAPSHOT/harness/chain/sequencer.py" run \\
  --root "\$ROOT" --repo "\$CLONE" --story "\$STORY" --commit-check "\$CHECK" "\$@"
EOF
  chmod +x "$run_wrapper"
  echo "install-chain: run wrapper written to $run_wrapper"
fi

cat <<EOF

install-chain done. The CAPABILITY is upgraded; a real chain run is a separate exercise.

WHAT STAYS OPERATOR WORK (this method does not do it, and does not fake it):
  - Author the target's own examiner material: postconditions (run + red/green fixtures),
    briefs, the phase table per story, the fence settings.json, and the pinned rules copy.
  - Complete trusted_base in the profile with this repo's CI, its check script, and its rules.
  - Mint the dedicated clone: git clone --local, remove its remotes, set the terminal/push
    posture, turn repo-local identity signing off.
  - Provision and OWN the pinned root: INSTALL-HARDENING Step 3 (root-owned, outside every tree).
  - Apply INSTALL-HARDENING in full, required ONLY for UNATTENDED operation.

POSTURE: the target's chain is ATTENDED-ONLY until INSTALL-HARDENING lands (ADR-0005). core.py
startup and loader.py fail CLOSED until the pinned root exists -- that refusal is the honest gate,
not a defect. Nothing here implies unattended readiness.

Tools snapshot:  $SNAPSHOT
Target profile:  $profile
Pinned root:     $PINNED_ROOT   (one root per repo; never point two repos at one root)
EOF

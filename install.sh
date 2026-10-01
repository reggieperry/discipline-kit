#!/usr/bin/env bash
#
# install.sh — place the user-level discipline into ~/.claude.
#
# Copies the portable skills, the deep-reasoning template, the review gate, the rule gate, and
# (guarded) the user CLAUDE.md and settings.json. Existing CLAUDE.md / settings.json
# are never clobbered — they are backed up and a merge note is printed instead.
#
# Project-level pieces (rules, guides, memories) are NOT auto-installed — they go
# per-repo; the instructions are printed at the end.
#
# `--refresh-rules [--dir <repo>] [--tag <tag>]` re-syncs a repo that already has
# .claude/rules: the rules, the guides, and the rule gate, all read from ONE release tag. The
# gate lands at .claude/hooks/rule_gate.py and is wired in the repo's .claude/settings.json:
# created when absent, merged in place only when git tracks the file with no uncommitted changes
# (so git diff shows the entry and git checkout takes it back), and otherwise left alone with the
# entry printed. settings.local.json is never touched. A tag cut before the gate existed skips
# it, says so, and leaves the repo's hooks as they were. The user-level copy steps aside for a
# repo's own wired copy, so wiring both is safe while Claude Code loads project hooks; a session
# that does not (--setting-sources without project, disableAllHooks) leaves neither copy checking
# (ADR-0008, Consequences).
#
# Both install modes leave a version stamp, because an instance that cannot name what it has
# cannot tell whether it is current: discipline/KIT-VERSION for the user-level pieces (a COMMIT,
# since they come from the working tree, plus a disposition per piece, because two of them are
# never overwritten) and .claude/rules/.kit-version for a repo's rules and guides (a TAG). BOTH
# carry a STATE, so an install or a refresh that died partway cannot read as one that finished.
# `--version` prints the same facts for the checkout itself; it creates no file and copies
# nothing.

set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_HOME:-$HOME/.claude}"
stamp="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo backup)"

# --- args ---
# EVERY INSTALLER BEFORE v2.0.0 PARSED NO ARGUMENTS AT ALL. v1.0.0 through v1.5.1 ignore any flag
# handed to them and run a full user-level install from whatever the checkout holds (measured on
# v1.5.1: exit 0, eight files into the home directory), which is how an audit probe wrote into a
# real home directory. v2.0.0 does parse flags and refuses an unknown one with usage and exit 2,
# but it carries no --version to ask with. So anything wanting to know whether it has a NEW
# installer must ask WITHOUT running it: grep this file for the flag, or check the checkout moved.
USAGE="usage: install.sh [--refresh-rules [--dir <repo>] [--tag <tag>]] | install.sh --version"
REFRESH_RULES=0
SHOW_VERSION=0
TARGET="."
DIR_GIVEN=0
TAG=""

# A flag whose value is missing used to die on "$2: unbound variable", which names a line number
# in this script and not the mistake the caller made.
need_value() {
  if [ "$1" -lt 2 ]; then
    echo "✖ $2 needs a value." >&2
    echo "$USAGE" >&2
    exit 2
  fi
}
while [ $# -gt 0 ]; do
  case "$1" in
    --refresh-rules) REFRESH_RULES=1; shift ;;
    --dir) need_value "$#" --dir; TARGET="$2"; DIR_GIVEN=1; shift 2 ;;
    --tag) need_value "$#" --tag; TAG="$2"; shift 2 ;;
    --version) SHOW_VERSION=1; shift ;;
    *) echo "$USAGE" >&2; exit 2 ;;
  esac
done
# --version asks what this checkout is; every other flag makes the script ACT. Asked together,
# --version won and the run exited 0 having refreshed nothing, which in a log is indistinguishable
# from a refresh that worked. --tag was already refused this way; the rest were not. The test is
# whether --dir was GIVEN, not whether TARGET still holds its default: comparing the value let
# '--version --dir .' through while refusing '--version --dir anywhere-else', which is one rule
# with two answers.
if [ "$SHOW_VERSION" = 1 ] && { [ "$REFRESH_RULES" = 1 ] || [ -n "$TAG" ] || [ "$DIR_GIVEN" = 1 ]; }; then
  echo "✖ --version only reports what this checkout is; it cannot be combined with --refresh-rules, --dir or --tag. Run them separately." >&2
  echo "$USAGE" >&2
  exit 2
fi
# --dir and --tag are arguments TO --refresh-rules, and without it they were not refused but
# IGNORED, while this script's OTHER mode is the one that writes: '--dir <repo>' ran a full
# user-level install into the home directory and exited 0, having put nothing at all in <repo>
# (measured: nine files into the home directory). The README's upgrade prompt teaches the --dir
# form, so one dropped word turned a repository refresh into a home-directory install that reads
# as success in a log.
if [ "$REFRESH_RULES" = 0 ] && { [ -n "$TAG" ] || [ "$DIR_GIVEN" = 1 ]; }; then
  echo "✖ --dir and --tag are arguments to --refresh-rules. Without that flag this script installs the user-level pieces into $DEST and would ignore them, so it is refusing rather than doing the other thing." >&2
  echo "$USAGE" >&2
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

# WHAT THIS CHECKOUT IS. Each fact degrades to a named unknown rather than killing the run: a kit
# unpacked from a tarball has no .git, and under `set -e` an unguarded git call there would abort
# an install that has already copied half its files. `log -1` reads the commit without naming a
# rev the tag-consumption court forbids anywhere on this script's consumer path.
kit_commit() { g log -1 --format=%H 2>/dev/null || echo "unknown (not a git checkout)"; }
kit_describe() { g describe --tags --always --dirty 2>/dev/null || echo "unknown (not a git checkout)"; }
kit_newest_tag() { g tag --list 'v[0-9]*' --sort=-version:refname 2>/dev/null | head -n 1 || true; }

# --- --version: say what this checkout is, and install nothing ---
# The stamps below say what a MACHINE has; this says what the KIT is, and the pair is what makes
# "am I current" answerable. It creates no file and copies nothing, so it is safe to run against
# a kit before deciding to install it—which is the whole point, since the mode that does install
# is the one an old installer falls into when handed a flag it cannot parse. It is not a no-op on
# disk, and saying so is cheaper than a reader discovering it: `git describe --dirty` refreshes
# the checkout's git index, as every status-like git read does. No tracked content changes.
if [ "$SHOW_VERSION" = 1 ]; then
  newest_tag="$(kit_newest_tag)"
  echo "discipline-kit checkout"
  echo "  kit_path:                 $KIT"
  echo "  kit_commit:               $(kit_commit)"
  echo "  kit_describe:             $(kit_describe) (git's name for kit_commit: the nearest"
  echo "                            ancestor release tag plus the distance from it, which is NOT"
  echo "                            a claim that this checkout is that release)"
  if [ -n "$newest_tag" ]; then
    echo "  newest_local_release_tag: $newest_tag"
  else
    echo "  newest_local_release_tag: none, this checkout holds no release tag (v*)"
  fi
  echo "  installer_flags:          --refresh-rules [--dir <repo>] [--tag <tag>], --version"
  echo "  TAGS ARRIVE BY FETCH: the tag above is the newest this checkout has been TOLD about,"
  echo "  not the newest the kit has published, so a checkout whose tags were never fetched both"
  echo "  reports an old tag here and refreshes a repo from it, reporting success either way."
  echo "  Run 'git -C $KIT fetch --tags' first if that distinction matters to what you do next."
  exit 0
fi

# --- --refresh-rules: re-sync the kit-shipped rules AND guides into an ALREADY-installed repo ---
# Existing installs do not pick up kit updates on their own; the per-project copy is a manual
# step. This re-copies the tag's claude-project/rules/*.md into the repo's .claude/rules/ and its
# claude-project/sdlc-discipline/guides/*.md into .claude/sdlc-discipline/guides/, so the deep
# tier cannot silently rot a release behind the rules that cite it. A file the repo authored
# under a name the kit never shipped is untouched; a rule OR GUIDE whose content matches no
# release tag THIS CHECKOUT HOLDS is copied aside before being overwritten (see the classification
# below, and be careful what a non-match does and does not establish, since tags arrive by fetch);
# CLAUDE.md is never touched. The tag's reference/rule_gate.py, when it has one, goes to
# .claude/hooks/rule_gate.py the same way and is wired in .claude/settings.json: created when
# absent, merged only where git tracks the file cleanly, and otherwise printed (see THE GATE, then
# its wiring, below). Run it inside the repo, or point at one with --dir.
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
# A destination nothing already occupies. Backups here are named from a per-RUN timestamp with
# one-second resolution, so two runs in the same second chose the SAME name and the second copy
# destroyed the first preserved file (measured on the rules refresh: three edits, two surviving
# backups). Numbering keeps both, and a numbered name still does not end in .md. Nothing this
# script writes as a backup may overwrite another backup.
unique_path() {
  candidate="$1"
  suffix=2
  while [ -e "$candidate" ]; do
    candidate="$1.$suffix"
    suffix=$((suffix + 1))
  done
  printf '%s' "$candidate"
}

# Where a printed rule-gate entry goes in a settings.json, for both modes. One text, because a
# reader who sees the instruction twice should not have to work out whether the two differ.
print_entry_placement() {
  echo "    Where it goes: if the file has a \"hooks\" object holding a \"PreToolUse\" array, add the"
  echo "    entry to that array. If \"hooks\" has no \"PreToolUse\", add \"PreToolUse\": [ <entry> ]"
  echo "    inside \"hooks\". With no \"hooks\" at all, add \"hooks\": { \"PreToolUse\": [ <entry> ] }"
  echo "    at the top level. Separate it from its neighbors with a comma. Never add a second"
  echo "    \"hooks\" key: Claude Code keeps only the last one, and the other's hooks stop running."
}

# THE PROJECT-LEVEL ENTRY, which --refresh-rules wires into a repository's own settings.json. It
# names the vendored copy through $CLAUDE_PROJECT_DIR, which Claude Code sets for hook commands to
# the directory the session started in (measured on 2.1.286: a project hook logged it, and the
# hook's working directory, as that directory). `|| true` for the user-level entry's reason: a
# missing script exits 2, and exit 2 from a PreToolUse hook blocks the call.
# install_test.py holds this text equal to the entry it writes out by hand.
# shellcheck disable=SC2016  # $CLAUDE_PROJECT_DIR is for the hook's shell to expand
PROJECT_GATE_ENTRY='{
  "matcher": "Write|Edit|MultiEdit|NotebookEdit",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/rule_gate.py\" || true"
    }
  ]
}'

# Decides, and where it may, makes the project-level wiring. Prints a state word and a detail
# line: already-wired (and where), created, merged, or not-wired (and why). The order is the
# point. A settings.local.json that runs the gate already wires it, and a second copy in
# settings.json would run it twice, but this never writes settings.local.json. Next an already
# wired settings.json is left alone whatever git says about it. Only then is a file merged, and
# only one the caller found tracked and clean (why_not empty), whose keys are not repeated, and
# whose text a JSON writer reproduces exactly at its own indent: rewriting any other file would
# change lines besides the entry, and git diff would no longer show just the addition.
#
# "Runs the gate" means what reference/rule_gate.py's own deferral means, because the user-level
# copy steps aside on exactly that test and a stamp saying "wired" on any looser one leaves a write
# nobody checks. A command hook whose matcher selects every write tool (an empty or "*" matcher,
# a plain A|B list naming all four, or else a regular expression matching each) and whose command
# runs THIS repository's file: its script, after an optional python interpreter, is
# $CLAUDE_PROJECT_DIR/.claude/hooks/rule_gate.py, the relative .claude/hooks/rule_gate.py, or an
# absolute path to the same file. A command that only mentions the path (another checkout's copy,
# rule_gate.py.orig, an echo) runs nothing here. A hook that does run it but for fewer than the
# four tools is reported, never merged beside: a second entry would run the gate twice for the
# tools both select. The write goes to a temporary file in .claude/ that replaces settings.json
# only once it is whole, so a write that fails partway leaves the original as it was.
# With a fifth argument "check" it only answers already-wired or not-wired, creating and writing
# nothing: the report for a gate an earlier tag vendored.
# shellcheck disable=SC2016  # $CLAUDE_PROJECT_DIR here is a spelling Python compares, not expands
RULE_GATE_PROJECT_WIRE='
import json, os, re, shlex, stat, sys, tempfile
settings, local, entry_text, why_not = sys.argv[1:5]
check_only = sys.argv[5:6] == ["check"]
entry = json.loads(entry_text)
tools = ("Write", "Edit", "MultiEdit", "NotebookEdit")
copy = os.path.join(".claude", "hooks", "rule_gate.py")
def say(state, detail=""):
    print(state)
    print(detail)
    sys.exit(0)
def selects(m, tool):
    if m is None or m in ("", "*"):
        return True
    if not isinstance(m, str):
        return False
    if re.fullmatch(r"[A-Za-z0-9_|]+", m):
        return tool in m.split("|")
    try:
        return re.search(m, tool) is not None
    except re.error:
        return False
def runs_copy(cmd):
    try:
        words = shlex.split(cmd) if isinstance(cmd, str) else []
    except ValueError:
        return False
    if words and re.fullmatch(r"python[0-9.]*", os.path.basename(words[0])):
        words = words[1:]
    if not words:
        return False
    if words[0] in ("$CLAUDE_PROJECT_DIR/" + copy, "${CLAUDE_PROJECT_DIR}/" + copy, copy, "./" + copy):
        return True
    try:
        return os.path.isabs(words[0]) and os.path.samefile(words[0], copy)
    except OSError:
        return False
partial = []
def runs_gate(data, name):
    hooks = data.get("hooks") if isinstance(data, dict) else None
    entries = hooks.get("PreToolUse") if isinstance(hooks, dict) else None
    for e in entries if isinstance(entries, list) else []:
        for h in e.get("hooks", []) if isinstance(e, dict) and isinstance(e.get("hooks"), list) else []:
            if not (isinstance(h, dict) and h.get("type") == "command" and runs_copy(h.get("command"))):
                continue
            left_out = [t for t in tools if not selects(e.get("matcher"), t)]
            if not left_out:
                return True
            partial.append("a PreToolUse hook in %s runs .claude/hooks/rule_gate.py under the matcher %s, which leaves out %s, so the gate does not run for those writes; widen that matcher to the one in the entry below rather than adding a second entry"
                           % (name, json.dumps(e.get("matcher")), ", ".join(left_out)))
    return False
try:
    with open(local, encoding="utf-8") as f:
        if runs_gate(json.load(f), ".claude/settings.local.json"):
            say("already-wired", ".claude/settings.local.json")
except (OSError, ValueError):
    pass
if check_only:
    try:
        with open(settings, encoding="utf-8") as f:
            if runs_gate(json.load(f), ".claude/settings.json"):
                say("already-wired", ".claude/settings.json")
    except (OSError, ValueError):
        pass
    say("not-wired", partial[0] if partial else "no settings file here runs it")
if os.path.islink(settings) and not os.path.exists(settings):
    say("not-wired", why_not or "it is a symlink to nothing")
if not os.path.lexists(settings):
    if partial:
        say("not-wired", partial[0])
    try:
        with open(settings, "x", encoding="utf-8") as f:
            f.write(json.dumps({"hooks": {"PreToolUse": [entry]}}, indent=2) + "\n")
    except OSError as e:
        say("not-wired", "it could not be created: %s" % e)
    say("created")
repeated = []
def pairs(kv):
    seen = set()
    for k, _ in kv:
        if k in seen:
            repeated.append(k)
        seen.add(k)
    return dict(kv)
try:
    with open(settings, encoding="utf-8", newline="") as f:
        text = f.read()
    data = json.loads(text, object_pairs_hook=pairs)
except (OSError, ValueError) as e:
    say("not-wired", "it could not be read as JSON (%s)" % e)
if runs_gate(data, ".claude/settings.json"):
    say("already-wired", ".claude/settings.json")
if partial:
    say("not-wired", partial[0])
if why_not:
    say("not-wired", why_not)
if repeated:
    say("not-wired", "it repeats the key(s) %s, and rewriting it would keep only the last of each"
        % ", ".join(sorted(set(repeated))))
hooks = data.get("hooks", {}) if isinstance(data, dict) else None
if not isinstance(hooks, dict) or not isinstance(hooks.get("PreToolUse", []), list):
    say("not-wired", "its \"hooks\" or \"hooks.PreToolUse\" is not the shape an entry is added to")
body = text[:-1] if text.endswith("\n") else text
style = None
for indent in (2, 4, "\t"):
    for ascii_only in (False, True):
        if style is None and json.dumps(data, indent=indent, ensure_ascii=ascii_only) == body:
            style = (indent, ascii_only)
if style is None:
    say("not-wired", "its layout is not one a JSON writer reproduces, so rewriting it would change "
        "lines besides the entry")
data.setdefault("hooks", hooks).setdefault("PreToolUse", []).append(entry)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(settings), prefix=".settings.json.", suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(data, indent=style[0], ensure_ascii=style[1]) + text[len(body):])
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, stat.S_IMODE(os.stat(settings).st_mode))
    os.replace(tmp, settings)
except OSError as e:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    say("not-wired", "writing it failed (%s), and the half-written copy was discarded" % e)
say("merged")
'

if [ "$REFRESH_RULES" = 1 ]; then
  # THE SHELL FLOOR, NAMED IN THE SCRIPT THAT NEEDS IT. This path used associative arrays and
  # mapfile, both bash 4.0, in the one script whose whole job is landing on someone else's
  # machine, and macOS still ships bash 3.2. Those constructs are gone; sorted temporary files do
  # the same work. What remains is checked here, so an old shell fails with a sentence instead of
  # a syntax error. harness/fixtures/install_test.py pins the ABSENCE of the bash-4 constructs,
  # because a floor stated in a comment and enforced nowhere is the failure class this kit is
  # built against. No bash 3.2 was available to run this against: the claim is construct-absence
  # plus this guard, not a measurement on that shell.
  if [ "${BASH_VERSINFO[0]:-0}" -lt 3 ] ||
    { [ "${BASH_VERSINFO[0]:-0}" -eq 3 ] && [ "${BASH_VERSINFO[1]:-0}" -lt 2 ]; }; then
    echo "✖ --refresh-rules needs bash 3.2 or newer; this shell is bash ${BASH_VERSION:-unknown}." >&2
    exit 2
  fi
  # A --dir that names nothing used to die on the shell's own "cd: No such file or directory".
  if [ ! -d "$TARGET" ]; then
    echo "✖ --dir $TARGET: no such directory, so there is nothing to refresh." >&2
    exit 1
  fi
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
  tag_commit="$(g rev-list -n 1 "$TAG")"
  tmp="$(mktemp -d)"

  # WHAT THIS DIRECTORY SAID IT HELD BEFORE THIS RUN, read before anything can overwrite it. The
  # stamp is the only record of what an earlier install took, and its ABSENCE is itself an answer
  # the report at the end needs.
  had_stamp=0
  prior_stamp="none: this directory carried no .kit-version before this run"
  if [ -f .claude/rules/.kit-version ]; then
    had_stamp=1
    prior_stamp="$(sed -n 's/^tag: //p' .claude/rules/.kit-version | head -n 1)"
    if [ -z "$prior_stamp" ]; then
      prior_stamp="present, but it named no tag"
    fi
  fi

  rules_copied=0
  guides_copied=0
  aside_count=0
  refresh_state=unstarted

  # THE RULE GATE RIDES THE SAME TAG, and only a tag that has it. Every release before the gate
  # existed lacks reference/rule_gate.py, and `git archive` naming a path the tree lacks dies, so
  # the path is asked about first and the archive below names it only when it is there. A tag
  # without it changes nothing about the repo's hooks: an older gate already vendored here stays,
  # and the stamp says so, since the user-level copy may be deferring to it.
  gate_dst=.claude/hooks/rule_gate.py
  gate_in_tag=0
  rule_gate_state="not in tag $TAG"
  if g cat-file -e "$TAG:reference/rule_gate.py" 2>/dev/null; then
    gate_in_tag=1
    rule_gate_state="unfinished: this refresh stopped before .claude/hooks/rule_gate.py was placed"
  fi
  # NEVER VENDOR THROUGH A LINKED DIRECTORY. place_one replaces a linked FILE, but a linked
  # .claude/hooks (or .claude) carried the gate out of the repository, and the copy run through
  # it once resolved outside the root and deferred to itself, so nothing checked a write. The
  # gate is not placed or wired, and the run says why.
  gate_link=""
  if [ "$gate_in_tag" = 1 ]; then
    for d in .claude .claude/hooks; do
      if [ -L "$d" ] && [ -z "$gate_link" ]; then
        gate_link="$d"
      fi
    done
  fi

  # THE STAMP IS WRITTEN BEFORE THE FIRST COPY AND REWRITTEN AFTER THE LAST. Writing it only
  # after every copy succeeded left new rule bodies on disk under the PREVIOUS run's stamp
  # whenever one died partway: measured, 9 of 52 rules carried the new content while the stamp
  # still named the old tag. This is the artifact a later session trusts, so it is allowed to be
  # stale and never allowed to be wrong.
  write_rules_stamp() {
    {
      echo "# discipline-kit rules stamp for this directory."
      echo "# Written by 'install.sh --refresh-rules'. NOT A RULE: the leading dot and the absent"
      echo "# .md suffix keep the rule loader off it."
      echo "#"
      echo "# WHAT LANDED: the kit-shipped rules here, the guides under"
      echo "# .claude/sdlc-discipline/guides/, and, when rule_gate below begins \"vendored\", the"
      echo "# rule gate at .claude/hooks/rule_gate.py were read from the kit's RELEASE TAG below"
      echo "# with 'git archive', never from the kit checkout's working tree. rule_gate says"
      echo "# whether the tag had the gate, whether .claude/settings.json runs it, and whether a"
      echo "# gate some earlier tag vendored was left in place."
      echo "#"
      echo "# STATE. complete: every copy this refresh planned succeeded. in-progress: a refresh"
      echo "# is running, or died before it could say otherwise. partial: it died partway, so"
      echo "# some files here came from the tag below and some are whatever preceded them. On"
      echo "# anything but complete, re-run the refresh and read what it reports."
      echo "#"
      echo "# AM I CURRENT? Run 'install.sh --version' in the kit at kit_path below, and compare"
      echo "# its newest_local_release_tag with the tag here. Tags arrive by fetch, so a checkout"
      echo "# that never fetched reports an old one; fetch the kit's tags before trusting it."
      echo "state: $1"
      echo "tag: $TAG"
      echo "tag_commit: $tag_commit"
      echo "kit_path: $KIT"
      echo "refreshed_at: $(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
      echo "rules_copied: $rules_copied"
      echo "guides_copied: $guides_copied"
      echo "files_copied_aside: $aside_count"
      echo "rule_gate: $rule_gate_state"
      echo "prior_stamp: $prior_stamp"
    } > .claude/rules/.kit-version
  }

  # One cleanup for two jobs: the scratch tree, and a stamp that must not outlive its truth.
  # shellcheck disable=SC2317  # reached through the EXIT trap below, which shellcheck cannot see
  cleanup_refresh() {
    rm -rf "$tmp"
    if [ "$refresh_state" = started ]; then
      write_rules_stamp partial
    fi
  }
  trap cleanup_refresh EXIT

  # claude-project WHOLE, and the gate beside it, in ONE archive: the rules, the guides and the
  # gate are one payload from one release, and reading them from separate archives would let a
  # consumer end up holding rules from one tag and guides or a gate from another.
  archive_paths=(claude-project)
  if [ "$gate_in_tag" = 1 ]; then
    archive_paths+=(reference/rule_gate.py)
  fi
  if ! g archive "$TAG" "${archive_paths[@]}" | tar -x -C "$tmp"; then
    echo "✖ could not read ${archive_paths[*]} from tag $TAG." >&2
    exit 1
  fi
  src_rules="$tmp/claude-project/rules"
  src_guides="$tmp/claude-project/sdlc-discipline/guides"
  if ! compgen -G "$src_rules/*.md" >/dev/null; then
    echo "✖ tag $TAG carries no rules (no claude-project/rules/*.md in its tree) — nothing copied." >&2
    exit 1
  fi

  # A SHIPPED NAME CARRYING WHITESPACE CAN NEVER MATCH ITS OWN BLOB. The lookups this path builds
  # are whitespace-delimited, one key and one blob per line, so such a rule is classified as
  # matching no release on every run and copied aside forever: measured on a kit shipping "my
  # rule.md" against a byte-identical consumer, three refreshes left three backups. The kit ships
  # no such name today, so this refuses the day it does rather than growing someone's directory.
  for f in "$src_rules"/*.md "$src_guides"/*.md; do
    [ -f "$f" ] || continue
    shipped_name="${f##*/}"
    case "$shipped_name" in
      *[[:space:]]*)
        echo "✖ tag $TAG ships '$shipped_name', whose name contains whitespace: this refresh classifies files by a whitespace-delimited lookup, so it would copy that one aside on every run. Nothing has been copied." >&2
        exit 1
        ;;
    esac
  done

  # WHICH FILES HERE MATCH SOMETHING THE KIT RELEASED, AND WHICH MATCH NOTHING. Until this test
  # existed a refresh overwrote every kit-named rule with no backup, so an edit to one was lost
  # silently, while the home CLAUDE.md two modes down has been backed up since the first version
  # of this script. GUIDES ARE CLASSIFIED THE SAME WAY, for the same reason: the refresh replaces
  # them wholesale too, and protecting one set while silently overwriting the other is a promise
  # kept in one place and broken in the next.
  #
  # The test is by CONTENT, never by timestamp: a file whose bytes match that path's blob at any
  # release tag THIS CHECKOUT HOLDS is a copy some release shipped, so overwriting it loses
  # nothing. What a NON-match means is not decidable here, and the report below says so rather
  # than guessing: it is a local edit, or an install copied from the kit's working tree (which is
  # what this script's own per-project lines tell a consumer to do), or a tag set that is
  # incomplete on this machine, since tags arrive by fetch. A file that can be neither read nor
  # addressed is not classified at all: note_present below refuses it by name, because the
  # copy-aside "safe direction" does not exist for a file this script cannot read.
  #
  # TWO BATCHED GIT CALLS, never one per file: cat-file answers every (tag, file) pair in one
  # process, and hash-object hashes every present file in one more. Measured on the real kit,
  # 14 tags by 57 rules: 798 pairs in about 0.11 s. The lookups are sorted temporary files rather
  # than associative arrays, which need bash 4.0 (see the floor check at the top of this block).
  : > "$tmp/present-keys"
  : > "$tmp/present-paths"
  newline=$'\n'
  note_present() {
    kind="$1"
    dir="$2"
    [ -d "$dir" ] || return 0
    for f in "$dir"/*.md; do
      [ -f "$f" ] || continue
      # A FILE THIS RUN CANNOT CLASSIFY STOPS IT, BY NAME. The hash step below feeds these paths
      # to one 'git hash-object --stdin-paths', which addresses ONE PATH PER LINE and opens each:
      # a name carrying a newline names a file that does not exist, and an unreadable file cannot
      # be opened. Either ended the run in git's own fatal, naming neither the cause nor the fix
      # (measured: exit 128, "could not open ... Permission denied", nothing copied). There is no
      # copy-aside fallback here and there cannot be one, because a file this script cannot READ
      # it cannot BACK UP either, and overwriting one after a failed backup is the single outcome
      # that loses work.
      case "$f" in
        *"$newline"*)
          echo "✖ cannot classify $PWD/$f: its name contains a newline, and the release lookup addresses one path per line. Rename it and re-run; nothing has been copied." >&2
          exit 1
          ;;
      esac
      if [ ! -r "$f" ]; then
        echo "✖ cannot read $PWD/$f, so this run cannot tell whether it matches a release, and a file it cannot read it cannot copy aside either. Fix its permissions or move it out of the way, then re-run; nothing has been copied." >&2
        exit 1
      fi
      printf '%s/%s\n' "$kind" "${f##*/}" >> "$tmp/present-keys"
      printf '%s/%s\n' "$PWD" "$f" >> "$tmp/present-paths"
    done
  }
  note_present rules .claude/rules
  note_present guides .claude/sdlc-discipline/guides
  # The vendored gate is classified the way a rule is, under the key hooks/rule_gate.py, which the
  # query below maps to reference/rule_gate.py in each release tag. Only when this run will place
  # one: a tag without the gate leaves the file alone, so there is nothing to classify.
  if [ "$gate_in_tag" = 1 ] && [ -z "$gate_link" ] && [ -f "$gate_dst" ]; then
    if [ ! -r "$gate_dst" ]; then
      echo "✖ cannot read $PWD/$gate_dst, so this run cannot tell whether it matches a release, and a file it cannot read it cannot copy aside either. Fix its permissions or move it out of the way, then re-run; nothing has been copied." >&2
      exit 1
    fi
    printf 'hooks/rule_gate.py\n' >> "$tmp/present-keys"
    printf '%s/%s\n' "$PWD" "$gate_dst" >> "$tmp/present-paths"
  fi
  : > "$tmp/present-blobs"
  if [ -s "$tmp/present-paths" ]; then
    # --no-filters hashes the bytes on disk, which is what the tag's blob holds and what
    # git archive wrote; a clean filter would hash something neither side stores.
    if ! g hash-object --no-filters --stdin-paths < "$tmp/present-paths" > "$tmp/present-hashes"; then
      echo "✖ could not hash the rules and guides already in $(pwd), so no release lookup can be built; nothing has been copied." >&2
      exit 1
    fi
    # paste pairs BY POSITION, so a hash list short by one would pair every later key with another
    # file's blob and misclassify the whole directory: a wrong answer that reads like an answer.
    # Counting the two files is cheaper than trusting they match.
    keys_n="$(wc -l < "$tmp/present-keys" | tr -d ' ')"
    hashes_n="$(wc -l < "$tmp/present-hashes" | tr -d ' ')"
    if [ "$keys_n" != "$hashes_n" ]; then
      echo "✖ hashed $hashes_n of $keys_n file(s) in $(pwd); refusing to classify from a partial lookup. Nothing has been copied." >&2
      exit 1
    fi
    paste -d' ' "$tmp/present-keys" "$tmp/present-hashes" > "$tmp/present-blobs"
  fi

  # Every name either side knows: what the tag ships, plus what is already here (a name that is
  # here and no longer shipped is what the obsolete report reads).
  : > "$tmp/names"
  for f in "$src_rules"/*.md; do
    [ -f "$f" ] || continue
    printf 'rules/%s\n' "${f##*/}" >> "$tmp/names"
  done
  if [ -d "$src_guides" ]; then
    for f in "$src_guides"/*.md; do
      [ -f "$f" ] || continue
      printf 'guides/%s\n' "${f##*/}" >> "$tmp/names"
    done
  fi
  if [ "$gate_in_tag" = 1 ]; then
    printf 'hooks/rule_gate.py\n' >> "$tmp/names"
  fi
  cut -d' ' -f1 "$tmp/present-blobs" >> "$tmp/names"
  sort -u -o "$tmp/names" "$tmp/names"

  # THE TAG SET IS WHATEVER THIS CHECKOUT HAS, and its size is carried to the report, because
  # tags arrive by fetch: a clone told about one release classifies against one release, and no
  # run may call that "every release the kit ever shipped".
  g tag --list 'v[0-9]*' > "$tmp/reltags"
  tags_read="$(wc -l < "$tmp/reltags" | tr -d ' ')"

  : > "$tmp/query"
  while IFS= read -r reltag; do
    while IFS= read -r key; do
      case "$key" in
        rules/*) path="claude-project/rules/${key#rules/}" ;;
        hooks/*) path="reference/${key#hooks/}" ;;
        *) path="claude-project/sdlc-discipline/guides/${key#guides/}" ;;
      esac
      printf '%s:%s %s\n' "$reltag" "$path" "$key" >> "$tmp/query"
    done < "$tmp/names"
  done < "$tmp/reltags"

  : > "$tmp/shipped"
  if [ -s "$tmp/query" ]; then
    # git answers a found pair "<oid> <name>" and a missing one "<input> missing", so a strict
    # 40-hex test on the first field is what tells the two apart.
    g cat-file --batch-check='%(objectname) %(rest)' < "$tmp/query" |
      while read -r oid key; do
        [ "${#oid}" -ge 40 ] || continue
        [ -z "${oid//[0-9a-f]/}" ] || continue
        printf '%s %s\n' "$key" "$oid" >> "$tmp/shipped"
      done
  fi
  cut -d' ' -f1 "$tmp/shipped" | sort -u > "$tmp/ever-shipped"

  # The copy. A file matching no release is copied aside first. The backup keeps the file's name
  # in front so it sorts beside it, and ends in the timestamp (or a number) so it does NOT end in
  # .md: a rule loader globbing *.md must not pick it up. install_test.py asserts that.
  : > "$tmp/aside"
  : > "$tmp/relinked"
  relinked_count=0
  # One file from the tag onto its place here, under its lookup key: the rules, the guides and the
  # gate all go through this, so each gets the same backup and the same symlink handling.
  place_one() {
    key="$1"
    f="$2"
    dst="$3"
    if [ -e "$dst" ]; then
      here="$(awk -v k="$key" '$1 == k {print $2; exit}' "$tmp/present-blobs")"
      if [ -z "$here" ] || ! grep -qxF "$key $here" "$tmp/shipped"; then
        backup="$(unique_path "$dst.local-$stamp")"
        cp "$dst" "$backup"
        printf '%s\n' "$backup" >> "$tmp/aside"
        aside_count=$((aside_count + 1))
      fi
    fi
    # NEVER WRITE THROUGH A SYMLINK. cp follows one, so a rule symlinked to a file outside the
    # repository carried the tag's body OUT of the repository this run was pointed at, and left
    # the link in place to do it again on the next refresh. Whatever the link pointed at is
    # already preserved above when it matched no release; the link itself is replaced by a real
    # file here, and the run says so, because changing the shape of someone's directory is not
    # a thing to do quietly.
    if [ -L "$dst" ]; then
      rm -f "$dst"
      printf '%s\n' "$dst" >> "$tmp/relinked"
      relinked_count=$((relinked_count + 1))
    fi
    cp "$f" "$dst"
  }
  copy_kind() {
    kind="$1"
    src="$2"
    dstdir="$3"
    for f in "$src"/*.md; do
      [ -f "$f" ] || continue
      name="${f##*/}"
      place_one "$kind/$name" "$f" "$dstdir/$name"
      case "$kind" in
        rules) rules_copied=$((rules_copied + 1)) ;;
        guides) guides_copied=$((guides_copied + 1)) ;;
      esac
    done
  }

  refresh_state=started
  write_rules_stamp in-progress
  copy_kind rules "$src_rules" .claude/rules

  guides_note=""
  if [ -d .claude/sdlc-discipline/guides ]; then
    if compgen -G "$src_guides/*.md" >/dev/null; then
      copy_kind guides "$src_guides" .claude/sdlc-discipline/guides
    else
      guides_note="tag $TAG ships no guides, so none were copied"
    fi
  else
    guides_note="this repo has no .claude/sdlc-discipline/guides, so the guides were SKIPPED; the directory is deliberately not created here, because a repo that never took the guides should not silently start carrying five long documents (the per-project lines printed by 'install.sh' with no arguments add them)"
  fi

  # THE GATE, then its wiring. The file goes through place_one, so a copy the repo changed is
  # copied aside and a symlink is replaced rather than written through, exactly as for a rule.
  # The wiring is decided by RULE_GATE_PROJECT_WIRE above, after git says whether settings.json
  # is tracked and clean; the git here is the REPO's, scrubbed of inherited redirects as g is.
  wire_state=""
  wire_detail=""
  if [ "$gate_in_tag" = 1 ] && [ -n "$gate_link" ]; then
    wire_state=not-vendored
    rule_gate_state="in tag $TAG, NOT vendored: $gate_link is a symlink, and this refresh never writes through one; .claude/hooks and .claude/settings.json were left as they were"
  elif [ "$gate_in_tag" = 1 ]; then
    mkdir -p .claude/hooks
    place_one hooks/rule_gate.py "$tmp/reference/rule_gate.py" "$gate_dst"
    rule_gate_state="unfinished: .claude/hooks/rule_gate.py was placed, but this refresh stopped before .claude/settings.json was examined"
    cg() {
      env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_OBJECT_DIRECTORY \
        -u GIT_COMMON_DIR -u GIT_CONFIG_GLOBAL -u GIT_CONFIG_SYSTEM git -C "$PWD" "$@"
    }
    why_not=""
    if [ -L .claude/settings.json ]; then
      why_not="it is a symlink, and this refresh never writes through one"
    elif [ -e .claude/settings.json ]; then
      if [ "$(cg rev-parse --is-inside-work-tree 2>/dev/null)" != true ]; then
        why_not="$(pwd) is not a git work tree, so a change to it could not be reviewed with git diff or taken back with git checkout"
      elif ! cg ls-files --error-unmatch -- .claude/settings.json >/dev/null 2>&1; then
        why_not="git does not track it, so a change to it could not be taken back with git checkout"
      elif [ -n "$(cg status --porcelain -- .claude/settings.json 2>/dev/null)" ]; then
        why_not="it has uncommitted changes, which a merge would mix with this one"
      fi
    fi
    if command -v python3 >/dev/null 2>&1; then
      wiring="$(python3 -c "$RULE_GATE_PROJECT_WIRE" .claude/settings.json .claude/settings.local.json "$PROJECT_GATE_ENTRY" "$why_not" 2>/dev/null)" ||
        wiring=$'not-wired\nthe wiring step could not run'
    else
      wiring=$'not-wired\npython3 was not found, and the gate needs it too'
    fi
    wire_state="${wiring%%$'\n'*}"
    case "$wiring" in *$'\n'*) wire_detail="${wiring#*$'\n'}" ;; esac
    case "$wire_state" in
      created) rule_gate_state="vendored+wired (this refresh created .claude/settings.json holding only the PreToolUse entry)" ;;
      merged) rule_gate_state="vendored+wired (this refresh added the PreToolUse entry to the tracked .claude/settings.json; git diff shows it, and git checkout -- .claude/settings.json takes it back)" ;;
      already-wired) rule_gate_state="vendored+already-wired (a PreToolUse hook in $wire_detail already runs .claude/hooks/rule_gate.py; nothing was changed)" ;;
      *)
        wire_state=not-wired
        rule_gate_state="vendored, NOT wired: .claude/settings.json was left as it was because $wire_detail; the refresh printed the entry to add"
        ;;
    esac
  elif [ -e "$gate_dst" ] || [ -L "$gate_dst" ]; then
    # The tag predates the gate, but an earlier tag's gate is here. Left alone, and named with
    # whether a settings file runs it, because the user-level copy steps aside for a wired one.
    earlier="not-wired"
    if command -v python3 >/dev/null 2>&1; then
      earlier="$(python3 -c "$RULE_GATE_PROJECT_WIRE" .claude/settings.json .claude/settings.local.json "$PROJECT_GATE_ENTRY" "" check 2>/dev/null)" || earlier="not-wired"
    fi
    case "$earlier" in
      already-wired*) earlier="wired in ${earlier#*$'\n'}" ;;
      *) earlier="not wired" ;;
    esac
    wire_state=left-in-place
    rule_gate_state="not in tag $TAG; a .claude/hooks/rule_gate.py vendored by an earlier tag was left in place ($earlier)"
  fi

  write_rules_stamp complete
  refresh_state=complete

  # Kit-named rules the resolved tag no longer ships. REPORTED, NEVER DELETED: a dropped rule
  # keeps loading in the consumer's sessions until someone retires it, and this script cannot
  # tell one they still want from one they forgot. A name the kit never shipped is the
  # consumer's own and is not reported at all.
  : > "$tmp/obsolete"
  while IFS= read -r key; do
    case "$key" in
      rules/*) name="${key#rules/}" ;;
      *) continue ;;
    esac
    if [ -f "$src_rules/$name" ]; then
      continue
    fi
    if grep -qxF "$key" "$tmp/ever-shipped"; then
      printf '%s\n' "$name" >> "$tmp/obsolete"
    fi
  done < <(cut -d' ' -f1 "$tmp/present-blobs")

  echo "refreshed from discipline-kit $TAG: $rules_copied rule file(s) into .claude/rules/, $guides_copied guide file(s) into .claude/sdlc-discipline/guides/ (in $(pwd))"
  echo "  stamp: .claude/rules/.kit-version (state complete, tag $TAG, tag commit $tag_commit)"
  if [ -n "$guides_note" ]; then
    echo "  guides: $guides_note"
  fi
  case "$wire_state" in
    "")
      echo "  rule gate: not in tag $TAG, so it was skipped. The tag predates the gate; .claude/hooks and .claude/settings.json were left as they were."
      ;;
    left-in-place)
      echo "  rule gate: not in tag $TAG, so it was skipped, and .claude/hooks and .claude/settings.json"
      echo "    were left as they were. The .claude/hooks/rule_gate.py an earlier tag vendored is still"
      echo "    here ($earlier): an earlier tag's gate beside this tag's rules. Delete it, or refresh"
      echo "    from a tag that ships the gate."
      ;;
    not-vendored)
      echo "  rule gate: in tag $TAG, but NOT vendored: $gate_link is a symlink, and this refresh never"
      echo "    writes through one. .claude/hooks and .claude/settings.json were left as they were."
      echo "    Replace the link with a real directory and refresh again."
      ;;
    created | merged)
      echo "  rule gate: .claude/hooks/rule_gate.py from $TAG, wired in .claude/settings.json ($wire_state)."
      if [ "$wire_state" = merged ]; then
        echo "    The file was tracked with no uncommitted changes, so 'git diff .claude/settings.json'"
        echo "    shows the entry and 'git checkout -- .claude/settings.json' takes it back."
      fi
      ;;
    already-wired)
      echo "  rule gate: .claude/hooks/rule_gate.py from $TAG; $wire_detail already runs it, so no settings file was changed."
      ;;
    *)
      echo "  rule gate: .claude/hooks/rule_gate.py from $TAG, but NOT wired: .claude/settings.json was left"
      echo "    as it was because $wire_detail."
      echo "    To turn it on, add this rule-gate PreToolUse entry to $(pwd)/.claude/settings.json:"
      echo ""
      echo "$PROJECT_GATE_ENTRY"
      echo ""
      print_entry_placement
      ;;
  esac
  if [ "$aside_count" -gt 0 ]; then
    echo "  copied aside $aside_count file(s) whose bytes match no release tag this checkout has, before overwriting:"
    sed 's/^/    /' "$tmp/aside"
    echo "    WHAT THAT MEANS, and what it does not. The test is content: these bytes against that"
    echo "    path's blob in each of the $tags_read release tag(s) this checkout holds, in $KIT."
    echo "    Three things produce a non-match and this run cannot tell them apart: a local edit;"
    echo "    an install copied from the kit's WORKING TREE, which is what this installer's own"
    echo "    per-project lines and the README tell you to do; or a tag set that is incomplete on"
    echo "    this machine, since tags arrive by fetch and a file can match a release this"
    echo "    checkout was never told about. Run 'git -C $KIT fetch --tags' and refresh again to"
    echo "    rule the third one out. The copy is kept whichever it was; it is the safe direction,"
    echo "    not a finding about your work."
    if [ "$had_stamp" = 0 ]; then
      echo "    This directory carried no .claude/rules/.kit-version before this run, so there is"
      echo "    no record of what the earlier install took: on a first refresh the first two are"
      echo "    indistinguishable in principle, not merely unchecked."
    fi
  fi
  if [ "$relinked_count" -gt 0 ]; then
    echo "  replaced $relinked_count symlink(s) with a real file, so the tag's body landed inside this repository rather than through the link:"
    sed 's/^/    /' "$tmp/relinked"
  fi
  if [ -s "$tmp/obsolete" ]; then
    echo "  kit-named rule(s) here that $TAG no longer ships (NOT deleted; retire them deliberately):"
    sed 's/^/    /' "$tmp/obsolete"
  fi
  exit 0
fi

echo "Installing user-level discipline into $DEST"
mkdir -p "$DEST/skills" "$DEST/discipline"

# WHAT THIS RUN HAS PLACED SO FAR, in the same shape as the rules stamp and for the same measured
# reason. Written only after every copy, this stamp left NEW bodies on disk under the PREVIOUS
# commit's stamp whenever a run died partway: measured, the deep-reason skill rewritten from a
# newer kit, the stamp still naming the commit before it, and no field in the file to say the run
# had not finished. Each piece starts unfinished and is named as it lands, so a partial stamp says
# which pieces this run reached.
user_state=unstarted
unfinished="unfinished: this run stopped before this piece was placed"
skills_state="$unfinished"
reference_state="$unfinished"
rule_gate_state="$unfinished"
claude_md_state="$unfinished"
settings_state="$unfinished"
kit_commit_now="$(kit_commit)"
kit_describe_now="$(kit_describe)"

write_user_stamp() {
  {
    echo "# discipline-kit user-level install stamp. Written by install.sh."
    echo "#"
    echo "# WHAT LANDED: the skills, the deep-reasoning template and this discipline/ directory"
    echo "# were copied from the kit checkout's WORKING TREE at the commit below. They are NOT"
    echo "# pinned to a release tag. Only 'install.sh --refresh-rules', which places a repository's"
    echo "# rules and guides, reads a tag's tree."
    echo "#"
    echo "# STATE. complete: every copy this install planned succeeded. in-progress: an install is"
    echo "# running, or died before it could say otherwise. partial: it died partway, so some"
    echo "# pieces here came from the commit below and some are whatever preceded them. On"
    echo "# anything but complete, read the dispositions for which is which, then re-run."
    echo "#"
    echo "# READ THE DISPOSITIONS, NOT ONLY kit_commit. 'installed' means this run wrote the kit's"
    echo "# copy, so kit_commit describes that piece. 'kept-existing' means the file was already"
    echo "# here and was LEFT ALONE: it still holds whatever it held before, which after an upgrade"
    echo "# is the PREVIOUS release's text. kit_commit is what this run BROUGHT; it is never a"
    echo "# claim about a kept-existing piece, and a machine can be current and old at once."
    echo "#"
    echo "# kit_describe is git's name for kit_commit: the nearest ancestor release tag plus the"
    echo "# distance from it. It does not mean these files are that release."
    echo "#"
    echo "# AM I CURRENT? Run 'install.sh --version' in the kit at kit_path below, and compare"
    echo "# kit_commit."
    echo "state: $1"
    echo "kit_path: $KIT"
    echo "kit_commit: $kit_commit_now"
    echo "kit_describe: $kit_describe_now"
    echo "installed_at: $(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
    echo "skills: $skills_state"
    echo "reference: $reference_state"
    echo "rule_gate: $rule_gate_state"
    echo "CLAUDE.md: $claude_md_state"
    echo "settings.json: $settings_state"
  } > "$DEST/discipline/KIT-VERSION"
}

# A stamp must not outlive its truth: if this run dies between the copies, the trap says so.
# shellcheck disable=SC2317  # reached through the EXIT trap below, which shellcheck cannot see
user_install_incomplete() {
  if [ "$user_state" = started ]; then
    write_user_stamp partial
  fi
}
trap user_install_incomplete EXIT

user_state=started
write_user_stamp in-progress

# --- skills (safe: additive, distinct dirs) ---
cp -R "$KIT/claude-user/skills/deep-reason" "$DEST/skills/"
cp -R "$KIT/claude-user/skills/pr-review" "$DEST/skills/"
skills_state="installed (deep-reason, pr-review; rewritten from the working tree every run)"
echo "  skills: deep-reason, pr-review"

# --- reference artifacts ---
cp "$KIT/reference/deep-reasoning-agent.md" "$DEST/deep-reasoning-agent.md"
cp "$KIT/reference/sdlc-gate.py" "$DEST/discipline/sdlc-gate.py"
cp "$KIT/reference/review-checklist.md" "$DEST/discipline/review-checklist.md"
cp "$KIT/reference/voicing-document.md" "$DEST/discipline/voicing-document.md"
reference_state="installed (deep-reasoning-agent.md, discipline/{sdlc-gate.py,review-checklist.md,voicing-document.md}; rewritten every run)"
echo "  reference: deep-reasoning-agent.md, discipline/{sdlc-gate.py,review-checklist.md,voicing-document.md}"

# --- the rule gate ---
# A PreToolUse hook that refuses a Write or Edit whose path-scoped project rules are not in the
# session's context, because Claude Code loads such a rule only when a matching file is READ.
# The file lands every run; whether it RUNS depends on settings.json naming it, which the guarded
# block below may not touch, so its disposition is decided there.
cp "$KIT/reference/rule_gate.py" "$DEST/discipline/rule_gate.py"
rule_gate_state="unfinished: discipline/rule_gate.py was copied, but this run stopped before settings.json was examined"

# The PreToolUse entry claude-user/settings.json carries, printed for a settings.json this script
# will not overwrite. It is the entry, not a whole "hooks" key: pasted beside an existing "hooks"
# key, a second one would make the file hold the key twice, and a JSON reader keeps only the last,
# so either the gate or the user's own hooks would vanish without an error. `|| true` is there
# because python3 exits 2 when the script is missing, and exit 2 from a PreToolUse hook blocks the
# call: without it, a deleted gate file would refuse every write.
# install_test.py holds this text equal to the entry in claude-user/settings.json.
# shellcheck disable=SC2016  # $HOME is for the hook's shell to expand when Claude Code runs it
RULE_GATE_ENTRY='{
  "matcher": "Write|Edit|MultiEdit|NotebookEdit",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"$HOME/.claude/discipline/rule_gate.py\" || true"
    }
  ]
}'

# Whether a settings.json runs THIS install's gate on Write and Edit, read as JSON the way Claude
# Code reads it (a repeated key keeps its last value). A grep for the file name was the earlier
# test, and it called a permissions entry naming the file, or a "hooks" key a later duplicate
# replaced, wired. Prints a state (wired, named, absent, invalid) and a detail line: the
# repeated keys, or the parse error.
# shellcheck disable=SC2016  # Python source: the $HOME spellings in it are text it rewrites
RULE_GATE_CHECK='
import json, os, re, sys
path, home, dest = sys.argv[1:4]
want = os.path.normpath(os.path.join(dest, "discipline", "rule_gate.py"))
repeated = []
def pairs(kv):
    seen = set()
    for k, _ in kv:
        if k in seen:
            repeated.append(k)
        seen.add(k)
    return dict(kv)
try:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    data = json.loads(text, object_pairs_hook=pairs)
except (OSError, ValueError) as e:
    print("invalid")
    print(str(e))
    sys.exit(0)
def covers(m):
    if m is None or m in ("", "*"):
        return True
    if not isinstance(m, str):
        return False
    if re.fullmatch(r"[A-Za-z0-9_|]+", m):
        return {"Write", "Edit"} <= set(m.split("|"))
    try:
        return all(re.search(m, t) for t in ("Write", "Edit"))
    except re.error:
        return False
def runs_gate(cmd):
    for spelling in ("${HOME}", "$HOME"):
        cmd = cmd.replace(spelling, home)
    cmd = re.sub(r"(^|[\s\"=])~/", lambda m: m.group(1) + home + "/", cmd)
    return want in cmd.replace("//", "/")
hooks = data.get("hooks") if isinstance(data, dict) else None
entries = hooks.get("PreToolUse") if isinstance(hooks, dict) else None
state = "named" if "rule_gate.py" in text else "absent"
for e in entries if isinstance(entries, list) else []:
    if isinstance(e, dict) and covers(e.get("matcher")):
        for h in e.get("hooks") if isinstance(e.get("hooks"), list) else []:
            if isinstance(h, dict) and isinstance(h.get("command"), str) and runs_gate(h["command"]):
                state = "wired"
print(state)
print(", ".join(sorted(set(repeated))))
'

# The kept settings.json with the gate's entry added, written to a NEW file beside it for the
# user to review and move into place. The live file is never touched.
RULE_GATE_MERGE='
import json, sys
src, out, entry = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
with open(src, encoding="utf-8") as f:
    data = json.load(f)
hooks = data.setdefault("hooks", {})
hooks.setdefault("PreToolUse", []).append(entry)
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
'

# The state word, a newline, and the detail line; "unchecked" when python3 cannot run the check.
rule_gate_wiring() {
  if ! command -v python3 >/dev/null 2>&1; then
    printf 'unchecked\npython3 was not found, and the gate needs it too\n'
    return 0
  fi
  python3 -c "$RULE_GATE_CHECK" "$1" "$HOME" "$DEST" 2>/dev/null ||
    printf 'unchecked\nthe check could not run\n'
}

# --- CLAUDE.md (guarded) ---
if [[ -e "$DEST/CLAUDE.md" ]]; then
  claude_md_backup="$(unique_path "$DEST/CLAUDE.md.bak-$stamp")"
  cp "$DEST/CLAUDE.md" "$claude_md_backup"
  claude_md_state="kept-existing (yours was left in place and copied to ${claude_md_backup##*/}; the kit's version was NOT merged, so this piece is whatever it was before this run)"
  echo "  CLAUDE.md EXISTS—backed up to ${claude_md_backup##*/}; NOT overwritten."
  echo "    Merge the deep-reason section from $KIT/claude-user/CLAUDE.md by hand."
else
  cp "$KIT/claude-user/CLAUDE.md" "$DEST/CLAUDE.md"
  claude_md_state="installed (this run wrote the kit's copy)"
  echo "  CLAUDE.md installed"
fi

# --- settings.json (guarded) ---
if [[ -e "$DEST/settings.json" ]]; then
  settings_backup="$(unique_path "$DEST/settings.json.bak-$stamp")"
  cp "$DEST/settings.json" "$settings_backup"
  settings_state="kept-existing (yours was left in place and copied to ${settings_backup##*/}; the kit's permissions were NOT merged, so this piece is whatever it was before this run)"
  echo "  settings.json EXISTS—backed up to ${settings_backup##*/}; NOT overwritten."
  echo "    Review $KIT/claude-user/settings.json and merge the permissions you want."
  wiring="$(rule_gate_wiring "$DEST/settings.json")"
  wiring_state="${wiring%%$'\n'*}"
  wiring_detail=""
  case "$wiring" in *$'\n'*) wiring_detail="${wiring#*$'\n'}" ;; esac
  repeated_note=""
  if [ "$wiring_state" != invalid ] && [ -n "$wiring_detail" ]; then
    repeated_note="; it also repeats the key(s) $wiring_detail, and Claude Code keeps only the last of each"
  fi
  case "$wiring_state" in
    wired)
      rule_gate_state="installed and wired (discipline/rule_gate.py, rewritten every run; your kept settings.json runs it as a PreToolUse hook on Write and Edit$repeated_note)"
      echo "    Your settings.json runs discipline/rule_gate.py as a PreToolUse hook, so the rule gate is wired."
      ;;
    unchecked)
      rule_gate_state="installed; wiring NOT checked (discipline/rule_gate.py is in place, but $wiring_detail, so this run cannot say whether your kept settings.json runs it)"
      echo "    The rule gate is installed, but its wiring was not checked: $wiring_detail."
      ;;
    invalid)
      rule_gate_state="installed but NOT wired (discipline/rule_gate.py is in place, but your kept settings.json is not valid JSON: $wiring_detail)"
      echo "    The rule gate is installed, but your settings.json is not valid JSON ($wiring_detail),"
      echo "    so Claude Code cannot be running it. Fix the file, then add the entry below."
      ;;
    named)
      rule_gate_state="installed but NOT wired (discipline/rule_gate.py is in place; your kept settings.json names rule_gate.py, but not in a PreToolUse hook on Write and Edit that runs $DEST/discipline/rule_gate.py$repeated_note)"
      ;;
    *)
      rule_gate_state="installed but NOT wired (discipline/rule_gate.py is in place, but your kept settings.json does not name it, so the gate does not run until the PreToolUse entry install.sh prints is added$repeated_note)"
      ;;
  esac
  if [ "$wiring_state" = named ] || [ "$wiring_state" = absent ] || [ "$wiring_state" = invalid ]; then
    echo "    The rule gate is installed but NOT wired. To turn it on, add this rule-gate PreToolUse entry"
    echo "    to $DEST/settings.json:"
    echo ""
    echo "$RULE_GATE_ENTRY"
    echo ""
    print_entry_placement
    if [ -n "$repeated_note" ]; then
      echo "    Your file already repeats the key(s) $wiring_detail; merge each pair into one first."
    fi
    # No merged copy from a file that repeats a key: reading it keeps the last value, so the
    # copy would silently drop what the earlier one held.
    if [ "$wiring_state" != invalid ] && [ -z "$repeated_note" ] && command -v python3 >/dev/null 2>&1; then
      merged="$(unique_path "$DEST/settings.json.with-rule-gate-$stamp")"
      if python3 -c "$RULE_GATE_MERGE" "$DEST/settings.json" "$merged" "$RULE_GATE_ENTRY" 2>/dev/null; then
        echo "    A copy of your settings.json with the entry added is at ${merged##*/}. Compare it with"
        echo "    yours (diff -u settings.json ${merged##*/}) and move it into place if it is right."
      fi
    fi
  fi
else
  cp "$KIT/claude-user/settings.json" "$DEST/settings.json"
  settings_state="installed (conservative: local git only, no auto-bypass)"
  wiring="$(rule_gate_wiring "$DEST/settings.json")"
  if [ "${wiring%%$'\n'*}" = wired ]; then
    rule_gate_state="installed and wired (discipline/rule_gate.py, rewritten every run; the settings.json this run wrote carries its PreToolUse hook)"
  else
    rule_gate_state="installed but NOT confirmed wired (the settings.json this run wrote runs \$HOME/.claude/discipline/rule_gate.py, and this install put the gate in $DEST/discipline; it runs only if Claude Code reads $DEST/settings.json and the command names that path)"
  fi
  echo "  settings.json installed (conservative: local git only, no auto-bypass; wires the rule gate)"
fi
if [ "$DEST" != "$HOME/.claude" ]; then
  echo "    NOTE: the rule gate's hook command names \$HOME/.claude/discipline/rule_gate.py, and this"
  echo "    install went to $DEST. Edit the command's path to match if Claude Code reads $DEST."
fi

# --- the version stamp for the user-level pieces ---
# Nothing this installer placed recorded a version until this file existed, so a later session
# could not tell a current install from a year-old one. It records a COMMIT and says why: unlike
# --refresh-rules, this mode copies claude-user/* and reference/* from whatever the checkout
# holds, so naming a release tag here would claim a provenance these files do not have. The
# in-progress stamp written above is rewritten here, once every piece has reported what it did.
write_user_stamp complete
user_state=complete
echo "  stamp: discipline/KIT-VERSION (state complete)"
echo "    kit_commit $kit_commit_now"
echo "    kit_describe $kit_describe_now (the nearest ancestor release tag plus the distance from"
echo "      it; these files are the working tree at kit_commit, not that release)"
echo "    CLAUDE.md and settings.json carry their own disposition in the stamp: an upgrade leaves"
echo "      an existing one alone, so kit_commit does not speak for it."

GATE_PATH="$(printf %q "$DEST/discipline/sdlc-gate.py")"

cat <<EOF

User-level install done.

Per-project step (run inside each repo you want the discipline to govern):

  mkdir -p .claude/rules .claude/sdlc-discipline/guides
  cp $KIT/claude-project/rules/*.md                     .claude/rules/
  cp $KIT/claude-project/sdlc-discipline/guides/*.md    .claude/sdlc-discipline/guides/

A rule loads when Claude reads a file matching its path globs (e.g. **/*.py) with the Read
tool, or when such a file is @-mentioned. Write, Edit and Bash do not load it. Once
settings.json wires the rule gate, it refuses a Write or Edit until the matching rules are in
context.

Those two cp lines copy from THIS CHECKOUT'S WORKING TREE, so what lands matches a release tag
only if the checkout sits exactly on one. The first --refresh-rules in that repo will therefore
find files matching no release tag it can see and copy them aside before overwriting. That is the
safe direction, not a finding that anyone edited them.

To refresh the rules AND the guides in an already-installed repo after updating the kit, always
naming the kit's path (a bare "install.sh --refresh-rules" has no path to resolve). It also
vendors the rule gate into the repo from the same tag and wires it in the repo's
.claude/settings.json (created when absent, merged only where git tracks the file with no
uncommitted changes, otherwise printed for you to add); this user-level copy then defers to it:

  $KIT/install.sh --refresh-rules --dir <repo>

To ask what this checkout is without installing anything:

  $KIT/install.sh --version

Which version is where, for a later session to read: $DEST/discipline/KIT-VERSION records the
commit these user-level pieces came from, and <repo>/.claude/rules/.kit-version records the
release tag a repository's rules and guides came from.

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

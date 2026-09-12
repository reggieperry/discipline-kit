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
# CLAUDE.md is never touched. Run
# it inside the repo, or point at one with --dir.
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
      echo "# WHAT LANDED: the kit-shipped rules here, and the guides under"
      echo "# .claude/sdlc-discipline/guides/, were read from the kit's RELEASE TAG below with"
      echo "# 'git archive', never from the kit checkout's working tree."
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

  # claude-project WHOLE, in ONE archive: the rules and the guides are one payload from one
  # release, and reading them from two archives would let a consumer end up holding rules from
  # one tag and guides from another.
  if ! g archive "$TAG" claude-project | tar -x -C "$tmp"; then
    echo "✖ could not read claude-project from tag $TAG." >&2
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
  copy_kind() {
    kind="$1"
    src="$2"
    dstdir="$3"
    for f in "$src"/*.md; do
      [ -f "$f" ] || continue
      name="${f##*/}"
      dst="$dstdir/$name"
      if [ -e "$dst" ]; then
        here="$(awk -v k="$kind/$name" '$1 == k {print $2; exit}' "$tmp/present-blobs")"
        if [ -z "$here" ] || ! grep -qxF "$kind/$name $here" "$tmp/shipped"; then
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
else
  cp "$KIT/claude-user/settings.json" "$DEST/settings.json"
  settings_state="installed (conservative: local git only, no auto-bypass)"
  echo "  settings.json installed (conservative: local git only, no auto-bypass)"
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

The rules auto-load by path glob (e.g. **/*.py) when you edit matching files.

Those two cp lines copy from THIS CHECKOUT'S WORKING TREE, so what lands matches a release tag
only if the checkout sits exactly on one. The first --refresh-rules in that repo will therefore
find files matching no release tag it can see and copy them aside before overwriting. That is the
safe direction, not a finding that anyone edited them.

To refresh the rules AND the guides in an already-installed repo after updating the kit, always
naming the kit's path (a bare "install.sh --refresh-rules" has no path to resolve):

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

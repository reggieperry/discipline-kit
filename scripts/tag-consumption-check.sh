#!/usr/bin/env bash
# scripts/tag-consumption-check.sh
#
# ADR-0002/D7's court, named future there ("a downstream consumer resolving kit `main` instead
# of a tag — future check on the installer") and live from this commit. Downstream consumption
# pins tags the operator mints: `install.sh --refresh-rules` must resolve a release tag and copy
# from that tag's tree, so a bad merge on `main` cannot reach a consuming repository before the
# backstop acts.
#
# THE PATTERNS ARE GROUNDED IN A DEFECT THAT SHIPPED, not a guessed one. The pre-fix refresh
# path copied `cp "$KIT"/claude-project/rules/*.md` from whatever tree the checkout held,
# scraped a version out of the checkout's CHANGELOG.md, and invoked git nowhere at all. Those
# three shapes are what the refresh-region patterns fail on, plus D7's named falsifier: a git
# consumption verb resolving `main` (or `HEAD`, or `master` — a rev that is not a tag), checked
# across every consumer script.
#
# THE CORPUS. `install.sh` is the consumer path this court is named on and is REQUIRED — a root
# without it is could-not-run, never clean. `scripts/refresh-from-pack.sh` is scanned for the
# non-tag-rev pattern when present: it consumes the upstream pack rather than this kit, and its
# tag arrives as an explicit argument, so the refresh-region patterns do not apply to it.
#
# WHAT IS DISCLOSED AS UNWATCHED, so the clean verdict is read at its true width: the user-level
# install mode (install.sh with no arguments) copies claude-user/* and reference/* from the
# checkout's working tree, and the first-install per-repo instructions it prints do the same —
# both are working-tree consumers no pattern here judges. D7 is watched on the refresh path
# alone today; widening it to the install modes is a future story's work, recorded in
# STORY-0002's notes.
#
# GREP-SHAPED, AND SAYS SO. Comment-only lines are dropped, then literals are matched: a rev
# composed at runtime greps clean, and the region extraction is anchored on the refresh guard's
# own line. Both limits fail closed rather than open — a refresh region the extractor cannot
# find, like an absent corpus, is could-not-run — and the patterns are pinned by
# harness/fixtures/install_test.py, whose known-bad plant is the pre-fix region verbatim. A
# rewrite of the refresh mechanism (say, a worktree checkout instead of `git archive`) lands
# here as a FAIL and updates the pattern in the same commit, which is the intended cost: the
# court must never read a mechanism it does not know as clean.
#
# Exit contract, matching the kit's other courts: 0 clean, 1 finding, 2 the check could not run
# (no root, no install.sh, or no refresh region to judge) — never a pass. Denominators are
# printed on every run: a clean report over nothing must not look like a clean report over
# something.
#
# Usage: tag-consumption-check.sh [root-dir]   (default: the repository holding this script)
#
# The optional root is what lets harness/fixtures/install_test.py point the court at throwaway
# trees with planted defects, which is the only way to observe it failing.
set -euo pipefail

ROOT="$(cd "${1:-$(dirname "${BASH_SOURCE[0]}")/..}" 2>/dev/null && pwd)" || {
  echo "tag-consumption-check: VOID: root directory '${1:-}' does not exist; nothing checked" >&2
  exit 2
}

installer="$ROOT/install.sh"
if [ ! -f "$installer" ]; then
  echo "tag-consumption-check: VOID: no install.sh at $ROOT — the consumer path this court is named on is absent; not a pass" >&2
  exit 2
fi

corpus=("$installer")
if [ -f "$ROOT/scripts/refresh-from-pack.sh" ]; then
  corpus+=("$ROOT/scripts/refresh-from-pack.sh")
fi

fail=0
finding() {
  echo "tag-consumption-check: FAIL: $*" >&2
  fail=1
}

# Executed lines only: a comment explaining why `main` may not be resolved must not itself be
# the resolution the court reports.
executed() { grep -vE '^[[:space:]]*#' "$1" || true; }

# A git consumption verb applied to a rev that is not a tag. `g` is the corpus scripts' own
# env-scrubbed git helper, so it counts as git here.
nontag_rev='\b(git|g)\b.*\b(archive|checkout|clone|fetch|reset|rev-parse|show|worktree)\b.*\b(main|master|HEAD)\b'
for f in "${corpus[@]}"; do
  hits="$(executed "$f" | grep -E "$nontag_rev" || true)"
  if [ -n "$hits" ]; then
    finding "${f#"$ROOT"/}: resolves a non-tag rev where a tag is owed: $hits"
  fi
done

# The refresh region: from the guard that opens the refresh path to the column-zero `fi` that
# closes it. Everything below is judged against that region alone, so the first-install mode's
# printed per-repo instructions (a heredoc naming $KIT paths) are not in scope.
region="$(awk '/^if \[ "[$]REFRESH_RULES" = 1 \]/{r=1} r{print} r && /^fi$/{exit}' "$installer")"
if [ -z "$region" ]; then
  echo "tag-consumption-check: VOID: no refresh region found in install.sh — the path this court judges has changed shape underneath it; not a pass" >&2
  exit 2
fi
region_exec="$(printf '%s\n' "$region" | grep -vE '^[[:space:]]*#' || true)"
region_lines="$(printf '%s\n' "$region" | wc -l)"

if printf '%s\n' "$region_exec" | grep -qE 'cp[[:space:]].*[$]KIT.*claude-project'; then
  finding "install.sh refresh path copies rules from the checkout tree (\$KIT/claude-project), not from a tag's tree"
fi
if printf '%s\n' "$region_exec" | grep -q 'CHANGELOG'; then
  finding "install.sh refresh path scrapes a version from the checkout's CHANGELOG; the version a consumer gets is the tag itself"
fi
if ! printf '%s\n' "$region_exec" | grep -qE '\b(git|g)\b.*\b(describe[[:space:]]+--tags|tag[[:space:]]+(--list|-l)\b)'; then
  finding "install.sh refresh path has no tag resolution — nothing pins what the consumer receives to a release the operator minted"
fi
if ! printf '%s\n' "$region_exec" | grep -qE '\b(git|g)\b.*\barchive\b'; then
  finding "install.sh refresh path never reads a tag's tree (git archive) — whatever it copies is not pinned to the resolved tag"
fi

echo "tag-consumption-check: scanned ${#corpus[@]} consumer script(s); refresh region $region_lines line(s); 1 corpus-wide + 4 refresh-region patterns"
if [ "$fail" -ne 0 ]; then
  exit 1
fi
echo "tag-consumption-check: clean (consumption resolves a tag; no consumer path reads main or the working tree)"

#!/usr/bin/env bash
#
# trusted-base-touched.sh <base-ref> [<list-file>]
#
# The chain's trusted-base fence, as a mechanical predicate the /chain driver shells out to — the
# enforced form of a phase-agent's "touched no trusted-base path" postcondition. It reports every path
# that a phase changed under a trusted-base prefix (the judge that grades the chain: the gate, the
# hooks, the CI config, the chain's own agents/commands/rules — see the sibling `trusted-base` list)
# and exits 2; it exits 0 only when the phase touched no trusted path at all.
#
# It looks at BOTH (a) every commit in <base-ref>..HEAD — not just the endpoints, so a mid-phase
# "disable the gate, land damage, restore the gate" is caught even though the net tree diff is clean —
# and (b) the working tree, so an uncommitted trusted-path edit is caught too. Rename-aware; match is
# by path-PREFIX.
#
# FAIL CLOSED on its own inputs: a base ref that does not resolve, or an empty effective list, exits 2
# (a fence that cannot read its inputs is not a pass). Entries are whitespace-trimmed.
#
# PROVENANCE (important): for the mechanical guarantee the driver must invoke a PRISTINE copy of this
# script AND pass a pristine <list-file> from a location the branch under review cannot edit — a phase
# that rewrites its own in-tree list/predicate would otherwise weaken the fence that grades it. The
# in-tree `.claude/chain/` copy is convenient but branch-editable; running it unguarded makes the fence
# only as strong as the human who reviews the PR (the base tier's intended backstop). The pinned-copy
# wiring is the auto-merge tier's requirement (same as the differential gate).
#
# Exit: 2 = a trusted-base path was touched, or an input failed closed (the phase must halt / escalate);
#       0 = clean; 1 = usage.
set -euo pipefail

base="${1:-}"
if [ -z "$base" ]; then
  echo "usage: trusted-base-touched.sh <base-ref> [list-file]" >&2
  exit 1
fi
list="${2:-$(cd "$(dirname "$0")" && pwd)/trusted-base}"
if [ ! -f "$list" ]; then
  echo "trusted-base: list not found: $list" >&2
  exit 1
fi

# F3 — the base must resolve to a commit, else fail CLOSED.
if ! git rev-parse --verify --quiet "${base}^{commit}" >/dev/null 2>&1; then
  echo "trusted-base: base ref does not resolve to a commit: $base — failing closed" >&2
  exit 2
fi

# prefixes — drop #-comments and blank lines, trim surrounding whitespace (F5).
prefixes=()
while IFS= read -r raw; do
  entry="${raw#"${raw%%[![:space:]]*}"}"   # ltrim
  entry="${entry%"${entry##*[![:space:]]}"}"  # rtrim
  [ -n "$entry" ] || continue
  case "$entry" in \#*) continue ;; esac
  prefixes+=("$entry")
done < "$list"

# F4 — an empty effective list protects nothing; fail CLOSED.
if [ "${#prefixes[@]}" -eq 0 ]; then
  echo "trusted-base: the list is empty (protects nothing) — failing closed" >&2
  exit 2
fi

under_base() {  # print $1 if it falls under any trusted prefix
  local p="$1" pre
  for pre in "${prefixes[@]}"; do
    case "$p" in "$pre"*) printf '%s\n' "$p"; return 0 ;; esac
  done
  return 1
}

hits=()

# (a) every path changed in ANY commit of base..HEAD — catches touch-then-revert (F2), not endpoints.
# Captured (not process-substituted) so a git failure trips set -e rather than passing silently.
committed="$(git log -M --name-status --format='' "${base}..HEAD")"
while IFS=$'\t' read -r status p1 p2; do
  [ -n "${status:-}" ] || continue
  for p in "${p1:-}" "${p2:-}"; do
    [ -n "$p" ] || continue
    under_base "$p" >/dev/null && hits+=("$p") || true
  done
done <<< "$committed"

# (b) the working tree — an uncommitted trusted-path edit left dirty (F2/C). --no-renames avoids the
# "old -> new" arrow so the path field is a single token.
dirty="$(git status --porcelain --no-renames)"
while IFS= read -r line; do
  [ -n "$line" ] || continue
  p="${line:3}"
  [ -n "$p" ] || continue
  under_base "$p" >/dev/null && hits+=("$p") || true
done <<< "$dirty"

if [ "${#hits[@]}" -gt 0 ]; then
  printf '%s\n' "${hits[@]}" | sort -u
  exit 2
fi
exit 0

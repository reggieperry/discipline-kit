#!/usr/bin/env bash
# scripts/chain-refspec-check.sh
#
# ADR-0001/D1's edge court, and the only chain check that can run before a sequencer exists.
# refs/chain/* is per-instance run state, never shared truth: nothing pushes it, so a remote
# refspec or mirror covering that namespace, combined with --prune, deletes every local phase
# and park ref on the normal path, silently restarting in-flight stories and resurrecting
# parked ones (docs/sdlc-chain-design.md, the section-4.5 blockquote). Nothing may configure
# one.
#
# Exit contract, matching shellcheck_all.sh: 0 clean, 1 finding, 2 the check could not run.
# A could-not-run is never a pass (ADR-0001/D2).
#
# As the kit's own commit-path hygiene this runs from its own tree, like every other line in
# check.sh. A sequencer using it as a court must run a pinned copy instead (ADR-0001/D3).
set -euo pipefail
cd "$(dirname "$0")/.."

rc=0
entries="$(git config --get-regexp '^remote\..*\.(fetch|push|mirror)$' 2>/dev/null)" || rc=$?
if [ "$rc" -gt 1 ]; then
  echo "chain-refspec-check: VOID: git config unreadable (exit $rc); not a pass" >&2
  exit 2
fi

# refs/chain literally, a bare-wildcard refspec (refs/*), or a mirror remote all cover the
# namespace; refs/heads/* and refs/remotes/* forms do not and pass.
if printf '%s\n' "$entries" | grep -E 'refs/chain|refs/\*|\.mirror true$'; then
  echo "chain-refspec-check: FAIL: a remote refspec or mirror covers refs/chain (ADR-0001/D1)" >&2
  exit 1
fi
echo "chain-refspec-check: clean (no remote refspec or mirror covers refs/chain)"

#!/usr/bin/env bash
# scripts/merge-posture-check.sh
#
# ADR-0002/D1's edge court. The chain merges locally and never publishes: a chain profile
# that enables autonomous merge must also declare that the chain never pushes, because
# publication is what turns a bad merge from a local revert into a public event (the kit's
# origin is a public GitHub repository with CI on push, so the design's "no expiry condition
# applies on day one" was measured false here). Until a chain profile exists there is
# nothing to guard, and the check says so rather than failing on a world with no chain.
#
# The profile is PARSED (python3 tomllib), never line-grepped: a grep court was measured
# fail-open four ways (section-blind key matches, duplicate keys, inline tables, and an
# unreadable file swallowed by `|| true`). The declaration is checked wherever it appears in
# the parsed structure, so a nested or inline-table `autonomous_merge = true` cannot hide.
#
# Exit contract, matching shellcheck_all.sh: 0 clean, 1 finding, 2 the check could not run
# (unreadable or unparseable profile, or a directory at the path -- never a pass).
set -euo pipefail
cd "$(dirname "$0")/.."

profile=".claude/chain/profile.toml"
if [ ! -e "$profile" ]; then
  echo "merge-posture-check: no chain profile at $profile; autonomous merge not enabled; nothing to guard"
  exit 0
fi
if [ ! -f "$profile" ]; then
  echo "merge-posture-check: VOID: $profile exists but is not a regular file; not a pass" >&2
  exit 2
fi

python3 - "$profile" <<'PY'
import sys
import tomllib

path = sys.argv[1]
try:
    with open(path, "rb") as f:
        data = tomllib.load(f)
except (OSError, tomllib.TOMLDecodeError) as e:
    print(f"merge-posture-check: VOID: cannot parse {path}: {e}; not a pass", file=sys.stderr)
    sys.exit(2)


def tables(node):
    """Every dict anywhere in the parsed structure, so no section or inline table hides one."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from tables(v)
    elif isinstance(node, list):
        for v in node:
            yield from tables(v)


enabled = [t for t in tables(data) if t.get("autonomous_merge") is True]
if not enabled:
    print("merge-posture-check: chain profile present, autonomous merge not enabled; nothing to guard")
    sys.exit(0)

for t in enabled:
    if t.get("push") != "never":
        print(
            'merge-posture-check: FAIL: autonomous merge enabled without push = "never" '
            "in the same table (ADR-0002/D1)",
            file=sys.stderr,
        )
        sys.exit(1)
print('merge-posture-check: clean (autonomous merge declares the chain never pushes)')
PY

#!/usr/bin/env bash
# scripts/merge-posture-check.sh
#
# ADR-0002/D1's edge court. The chain's terminal act is declared per repository, and the
# trunk is never the chain's: a profile declaring `terminal = "open-pr"` must pair it with
# `push = "branches-only"` (story branches and the PR are the chain's; main is not), and
# `terminal = "merge-local"` must pair with `push = "never"`. Any other pairing, or a
# terminal act the record does not name, fails. Until a chain profile exists there is
# nothing to guard, and the check says so rather than failing on a world with no chain.
#
# The profile is PARSED (python3 tomllib), never line-grepped: a grep court was measured
# fail-open four ways (section-blind key matches, duplicate keys, inline tables, and an
# unreadable file swallowed into a clean exit). The declaration is checked wherever it
# appears in the parsed structure, so a nested or inline-table declaration cannot hide.
#
# Exit contract, matching shellcheck_all.sh: 0 clean, 1 finding, 2 the check could not run
# (unreadable or unparseable profile, or a directory at the path -- never a pass).
set -euo pipefail
cd "$(dirname "$0")/.."

profile=".claude/chain/profile.toml"
if [ ! -e "$profile" ]; then
  echo "merge-posture-check: no chain profile at $profile; no terminal act declared; nothing to guard"
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

REQUIRED_PAIR = {"open-pr": "branches-only", "merge-local": "never"}


def tables(node):
    """Every dict anywhere in the parsed structure, so no section or inline table hides one."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from tables(v)
    elif isinstance(node, list):
        for v in node:
            yield from tables(v)


declaring = [t for t in tables(data) if "terminal" in t]
if not declaring:
    print("merge-posture-check: chain profile present, no terminal act declared; nothing to guard")
    sys.exit(0)

for t in declaring:
    terminal = t.get("terminal")
    if not isinstance(terminal, str) or terminal not in REQUIRED_PAIR:
        print(
            f"merge-posture-check: FAIL: terminal act {terminal!r} is not one ADR-0002/D1 names",
            file=sys.stderr,
        )
        sys.exit(1)
    if t.get("push") != REQUIRED_PAIR[terminal]:
        print(
            f'merge-posture-check: FAIL: terminal = "{terminal}" requires '
            f'push = "{REQUIRED_PAIR[terminal]}" in the same table (ADR-0002/D1)',
            file=sys.stderr,
        )
        sys.exit(1)
print("merge-posture-check: clean (every declared terminal act pairs with its push scope)")
PY

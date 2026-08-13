#!/usr/bin/env bash
# scripts/profile-check.sh
#
# ADR-0002/D3.2's court, named there as future and live from this commit. The merge stage
# excludes the trusted base from what a story may touch, so a `trusted_base` list that omits a
# path is a hole in the cage the merge stage cannot see: the list is the only statement of what
# is protected, and nothing else re-derives it. D3.2 names three omissions that make the list
# self-defeating, and this checks all three: the list's own file, the CI workflows, and any path
# the commit-path check invokes or reads.
#
# THE REQUIRED SET IS DERIVED, NEVER HAND-KEPT. A second list of "what check.sh runs" would drift
# from check.sh the first time a check is added, and would drift silently, since both lists are
# prose to every reader. So the invocations are extracted from `scripts/check.sh` itself: every
# `bash <path>` and `python3 <path>` line. What cannot be derived that way is the read inputs,
# which no invocation names, so `docs/adrs/` and `stories/` are stated here as the story graph's
# two inputs (harness/chain_graph.py reads both, and re-derives nothing else from outside its own
# tree). `.githooks/` is stated for a reason of the same kind one step upstream: D3.2's text names
# what the check invokes or reads, and the hook is what invokes the check, so a story able to edit
# it can stop the check running at all.
#
# WHAT IS DELIBERATELY NOT REQUIRED is the corpus each check grades. `scrub-gate.sh` scans the
# whole tree, `em-dash-check.sh` scans every tracked markdown file, `shellcheck_all.sh` scans every
# tracked shell file, and `rule_grades.py` reads `claude-project/rules/`. Requiring a graded corpus
# would put the whole repository in the trusted base and park every story ever written. The
# distinction is configuration versus subject matter: `scripts/em-dash-exempt.txt` decides what the
# em-dash check will tolerate and is inside `scripts/`; the markdown it reads is what the check is
# for. The rules directory's integrity is carried by ADR-0002/D4 instead, which re-derives the
# reviewer's denominator from the pinned examiner copy and never from the judged tree.
#
# The profile is PARSED (python3 tomllib), never line-grepped, for the reasons measured at
# merge-posture-check.sh: a grep court was fail-open four ways.
#
# Exit contract, matching the kit's other courts: 0 clean, 1 finding, 2 the check could not run
# (unreadable or unparseable profile, no check to derive from, an extraction that produced
# nothing, or a declaration this court cannot read) -- never a pass.
#
# Usage: profile-check.sh [root-dir]   (default: the repository holding this script)
#
# The optional root is what lets harness/fixtures/profile_check_test.py point the court at
# throwaway trees with planted holes, which is the only way to observe it failing.
set -euo pipefail

ROOT="$(cd "${1:-$(dirname "${BASH_SOURCE[0]}")/..}" 2>/dev/null && pwd)" || {
  echo "profile-check: VOID: root directory '${1:-}' does not exist; nothing checked" >&2
  exit 2
}

profile="$ROOT/.claude/chain/profile.toml"
check="$ROOT/scripts/check.sh"

if [ ! -e "$profile" ]; then
  echo "profile-check: no chain profile at .claude/chain/profile.toml; no trusted base declared; nothing to guard"
  exit 0
fi
if [ ! -f "$profile" ]; then
  echo "profile-check: VOID: $profile exists but is not a regular file; not a pass" >&2
  exit 2
fi
if [ ! -f "$check" ]; then
  echo "profile-check: VOID: no commit-path check at scripts/check.sh, so the required set cannot be derived; not a pass" >&2
  exit 2
fi

python3 - "$ROOT" <<'PY'
import re
import sys
import tomllib
from pathlib import Path

root = Path(sys.argv[1])
PROFILE = ".claude/chain/profile.toml"
CHECK = "scripts/check.sh"

# Read, never invoked, so no extraction can find them: harness/chain_graph.py walks both.
READ_INPUTS = ("docs/adrs/", "stories/")
# The list's own file and the CI workflows are D3.2 verbatim; the hook is what runs the check.
ALWAYS = (PROFILE, ".github/workflows/", ".githooks/", CHECK)


def void(msg: str) -> None:
    print(f"profile-check: VOID: {msg}; not a pass", file=sys.stderr)
    sys.exit(2)


try:
    with open(root / PROFILE, "rb") as f:
        data = tomllib.load(f)
except (OSError, tomllib.TOMLDecodeError) as e:
    void(f"cannot parse {PROFILE}: {e}")


def tables(node):
    """Every dict anywhere in the parsed structure, so no section or inline table hides one."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from tables(v)
    elif isinstance(node, list):
        for v in node:
            yield from tables(v)


# The invocation set, extracted from the check itself. A token starting with `-` is a shell
# option or a heredoc's stdin marker (`python3 - <<'PY'`), never a path.
INVOCATION = re.compile(r"^\s*(?:bash|python3)\s+(\S+)")
invoked: list[str] = []
for line in (root / CHECK).read_text(encoding="utf-8").splitlines():
    m = INVOCATION.match(line)
    if not m:
        continue
    token = m.group(1)
    if token.startswith("-"):
        continue
    if any(c in token for c in "$\"'`"):
        void(f"{CHECK} invokes a path this court cannot resolve statically ({token!r})")
    invoked.append(token)

invoked = sorted(set(invoked))
if not invoked:
    # Zero extracted invocations is the shape of a court reporting green because it stopped
    # looking: an empty requirement set is satisfied by any trusted_base at all.
    void(f"no bash or python3 invocation was extracted from {CHECK}, so nothing was required")

absent = [p for p in invoked if not (root / p).exists()]
if absent:
    # A token naming no file is a mis-parse or a stale check, either way not a coverage question.
    void(f"{CHECK} invokes path(s) absent from the tree: {', '.join(absent)}")

required = sorted(set(ALWAYS) | set(READ_INPUTS) | set(invoked))

declaring = [t for t in tables(data) if "trusted_base" in t]
entry_count = 0
if declaring:
    for t in declaring:
        value = t["trusted_base"]
        if not isinstance(value, list):
            void(
                f"trusted_base is {type(value).__name__}, not a list of paths; coercing it would "
                "be a guess"
            )
        for entry in value:
            if not isinstance(entry, str):
                void(f"trusted_base holds a non-string entry ({entry!r})")
            s = entry.strip()
            if not s or s.rstrip("/") in ("", "."):
                void(f"trusted_base entry {entry!r} covers the whole tree, so it declares nothing")
            if s.startswith("/"):
                void(f"trusted_base entry {entry!r} is not repository-relative")
            if ".." in s.split("/"):
                void(f"trusted_base entry {entry!r} escapes the repository")
        entry_count += len(value)


def covered(path: str) -> bool:
    r = path.rstrip("/")
    for t in declaring:
        for entry in t["trusted_base"]:
            e = entry.strip().rstrip("/")
            if r == e or r.startswith(e + "/"):
                return True
    return False


print(
    f"profile-check: {len(invoked)} invocation(s) extracted from {CHECK}, "
    f"{entry_count} trusted_base entry(ies), {len(required)} required path(s)"
)

if not declaring:
    print(
        "profile-check: FAIL: the profile declares no trusted_base, so it protects none of the "
        f"{len(required)} required path(s) (ADR-0002/D3.2)",
        file=sys.stderr,
    )
    sys.exit(1)

uncovered = [p for p in required if not covered(p)]
if uncovered:
    print(
        f"profile-check: FAIL: trusted_base does not cover {len(uncovered)} required "
        f"path(s) (ADR-0002/D3.2):",
        file=sys.stderr,
    )
    for p in uncovered:
        print(f"    {p}", file=sys.stderr)
    sys.exit(1)

print("profile-check: clean (every required path is covered by a declared trusted_base prefix)")
PY

#!/usr/bin/env bash
# Runs shellcheck over every tracked shell file, and says how many that was.
#
# (This header deliberately does not open with the tool's own name: a comment beginning
# `# shellcheck` is parsed as a directive, and an unparseable one is itself an error — SC1073.)
#
# The kit's own instruments are shell (scripts/check.sh, scrub-gate.sh, install.sh, the
# pre-commit hook), so a defect here lands in the instrument rather than in the subject. This
# is what makes shell-style.md and shell-security.md "partly mechanical" rather than aspiration.
#
# WHAT IT DOES NOT CHECK, stated because a grade that overclaims is the failure this kit is
# built against: shellcheck reads syntax and never runs anything. It does not require
# `set -euo pipefail` — measured, against a script that had none, and it reported nothing —
# and it does not flag `eval`. Those stay review and convention.
#
#   exit 0   every tracked shell file is clean, and the count is printed
#   exit 1   at least one finding, reported in full
#   exit 2   THE CHECK COULD NOT RUN — shellcheck absent, or no shell files found. Never a pass.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v shellcheck >/dev/null 2>&1; then
  echo "✖ shellcheck not installed — cannot check shell sources (apt install shellcheck)." >&2
  exit 2
fi

# Tracked files only, so node_modules and build output never enter the set. Two ways in: the
# .sh extension, and a shell shebang on a file that has no extension — .githooks/pre-commit is
# the case that matters, and an extension-only scan would silently skip the commit gate itself.
files=()
while IFS= read -r f; do
  [[ -f "$f" ]] || continue
  if [[ "$f" == *.sh || "$f" == *.bash ]]; then
    files+=("$f")
  elif [[ "$(head -c 2 "$f" 2>/dev/null)" == "#!" ]] && head -1 "$f" | grep -qE '(ba)?sh$'; then
    files+=("$f")
  fi
done < <(git ls-files)

if (( ${#files[@]} == 0 )); then
  echo "✖ no shell files found — the scan matched nothing, which is not a pass." >&2
  exit 2
fi

if ! shellcheck -f gcc "${files[@]}"; then
  echo "✖ shellcheck findings above, across ${#files[@]} shell files." >&2
  exit 1
fi

echo "shellcheck: 0 findings across ${#files[@]} shell files"

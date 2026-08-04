#!/usr/bin/env bash
# The voicing document's em-dash rule, enforced for NEW prose only.
#
# `docs/voicing-document.md` says "Em dashes (—) set closed, with no space on either side", and
# `CLAUDE.md` repeats it. Measured 2026-08-01: 146 of 148 tracked markdown files write them SPACED,
# including both documents that state the rule. `CLAUDE.md` alone is 193 spaced and 0 closed.
#
# So this is a rule that has never been enforced and that practice diverged from entirely — the same
# shape as the build plan's test-kind rule, which was stated in a definition of done and still let a
# row ship hand-rolled. A stated rule nothing checks is a preference, and this one had drifted so far
# that the memory describing it had the convention backwards.
#
# THE EXISTING CORPUS IS NOT CONVERTED. Rewriting ~1,500 dashes across 146 files would be a large
# diff with no reader benefit and a real chance of mangling a table or a list. Instead every file
# tracked at baseline is exempt, and a file NOT on that list must comply.
#
# Whole files, never changed lines. A document with old spaced dashes and new closed ones reads worse
# than one that is consistently either — so the unit is the file, and converting one means converting
# it entirely and deleting its line from the exempt list. That is how a conversion gets recorded.
#
# THE EXEMPT COUNT IS PRINTED ON EVERY RUN. An exemption list that grows quietly is an amnesty; one
# that announces its size is a debt.
#
# Markdown only. The formal core (`claim-algebra.html`, `claim-calculus.html`) is externally authored
# and held byte-identical to the adopted package — it must never be rewritten for house style, and it
# is not scanned at all.
#
# `docs/ClaimOS/` is excluded for the SAME reason, and the exclusion is by path because that set
# ships markdown as well as HTML. It is a vendored, externally authored platform document set held
# as received; its own writing register is its business, and rewriting its prose would break the
# checksums it ships and the byte-identity that makes it auditable. This is a SCOPE statement, not
# an amnesty: the rule was always about prose this repo authors, and a vendored corpus is not that.
# An exemption list entry would have been the wrong instrument — that list means "tracked before the
# rule existed", and these files postdate it.
set -euo pipefail

EXEMPT="scripts/em-dash-exempt.txt"
[ -f "$EXEMPT" ] || { echo "em-dash: exempt list $EXEMPT not found" >&2; exit 2; }

exempt_count=$(grep -cv '^\s*\(#\|$\)' "$EXEMPT" || true)
violations=0
declare -a BAD=()

while IFS= read -r f; do
  grep -qxF -- "$f" "$EXEMPT" && continue
  n=$(grep -o ' — ' "$f" 2>/dev/null | grep -c . || true)
  if [ "${n:-0}" -gt 0 ]; then
    violations=$((violations + 1))
    BAD+=("$f ($n spaced em dash(es))")
  fi
# Tracked markdown only. An UNTRACKED file is invisible here, which is correct on the commit path
# (pre-commit runs after staging, and a staged file is in the index) and a real limit anywhere else
# — running this by hand on a new file reports nothing until the file is added.
done < <(git ls-files '*.md')

echo "== em-dash check =="
echo "  $exempt_count file(s) exempt — tracked before the rule was enforced, not converted"

if [ "$violations" -gt 0 ]; then
  echo "  DEFECT: new or unexempted file(s) use SPACED em dashes; the rule is closed (no spaces):"
  printf '    %s\n' "${BAD[@]}"
  echo "  Fix the file, or — if it is legitimately old prose — add its path to $EXEMPT and say why."
  exit 1
fi

echo "  every unexempted markdown file sets em dashes closed"
exit 0

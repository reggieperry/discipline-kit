#!/usr/bin/env bash
#
# scrub-gate.sh — fail if any private identifier survives in the kit.
#
# Two tiers:
#   TIER-1 (infra / PII / secrets) — forbidden ANYWHERE in the kit.
#   TIER-2 (chain / host vocabulary) — forbidden in memories/ and claude-user/,
#           where it would mislead; allowed in rules/ and guides/ as illustrative
#           teaching examples.
#
# Exits 0 clean, 1 if any forbidden token is found, 2 if it COULD NOT SCAN. Run before
# producing a tarball.
#
# Usage: scrub-gate.sh [target-dir]   (default: the directory holding this script)
#
# The optional target is what lets a fixture point the gate at a throwaway tree with a planted
# violation, which is the only way to observe the gate failing. Until it existed the gate had
# never been seen to fire, and an instrument never observed failing is not known to be watching.
#
# THE ARGUMENT IS ALSO WHAT MAKES EXIT 2 NECESSARY. The tier-2 and tier-3 scans name specific
# subdirectories, and grep answers "no match" for a directory that is not there — so a target
# missing them reported three clean tiers and printed PASS having examined nothing. In the kit's
# own tree all three exist and the default run is unchanged; a target lacking one is now told
# apart from a target that is clean.

set -euo pipefail

KIT="$(cd "${1:-$(dirname "${BASH_SOURCE[0]}")}" 2>/dev/null && pwd)" || {
  echo "SCRUB GATE: VOID — target directory '${1:-}' does not exist; nothing scanned." >&2
  exit 2
}
SELF="$(basename "${BASH_SOURCE[0]}")"
fail=0

# The surfaces the tier-2 and tier-3 scans name. A scan is a verdict only about what it read.
for surface in memories claude-user claude-project/rules; do
  if [[ ! -d "$KIT/$surface" ]]; then
    echo "SCRUB GATE: VOID — '$KIT/$surface' is absent, so its tier was never scanned." >&2
    exit 2
  fi
done

# TIER-1: infra hostnames, home paths, personal data, private-store tech.
tier1='t7920|trane|/home/reggie|/Users/|ghostdogsamurai|fastmail|DU[0-9]{6,}|\bPwC\b|\bCBO\b|gascity|bright-lights|\bdolt\b|msmtp'

# TIER-1, the operator's username in its NON-PATH forms. The pattern above is slash-anchored,
# and the D7 probe's own audit measured what that misses: the username survived 28 times in the
# retained raws through the scratch path's SLUG form (`-home-reggie-coding-...`) and through the
# ownership columns of `ls -l`, on files the gate read as clean. A word-bounded match catches
# every form, the slash-anchored one included.
#
# LICENSE IS EXCLUDED FROM THIS PATTERN AND ONLY THIS ONE. Its copyright line names the
# copyright holder, which is the license's content rather than a leak, and a licence that cannot
# say who holds the copyright is not one. The exclusion is narrow on purpose: LICENSE is still
# scanned by every other TIER-1 token, the path form included, so the carve-out cannot become a
# quiet hole. Both halves are pinned by cases in harness/fixtures/scrub_gate_test.py.
tier1user='\breggie\b'

# TIER-3: adw-harness project identifiers (the go-*/python-* rules were sourced
# from adw-harness). Forbidden in the scrubbed surfaces (memories/, claude-user/,
# rules/); allowed in guides/ as illustrative teaching examples, the same
# treatment elder/chain vocab gets in TIER-2.
tier3='adw-harness|\badw\b|chainkit|\bNodeEnv\b|StoryRepo|StoryID|ADW-[0-9]|gas city'

# TIER-2: chain / story / host operational vocabulary.
tier2='\belder\b|EL-[0-9]|ADR-[0-9]{3}|ssh t7920|\bsling\b|reconciler|kickoff|\bgc bd\b|\bbd update\b'

# The gate and the refresh script must name the forbidden tokens to detect and
# scrub them — they are tooling, not content, so they are excluded from the scan.
# `.git/` is VCS metadata (committer identity, object logs) — never shipped in a
# tarball and not kit content, so it is excluded from the scan. In a LINKED WORKTREE
# `.git` is a FILE rather than a directory, holding the absolute gitdir path, so
# `--exclude-dir` alone misses it and TIER-1's home-path pattern fires on VCS metadata
# the exclusion already intends to skip. The chain runs its phases in worktrees with
# this gate on the commit path, so without the file exclusion every subagent commit
# blocks on the gate's own blind spot.
echo "== TIER-1 (forbidden anywhere) =="
tier1_hit=0
if grep -rniE "$tier1" "$KIT" --exclude="$SELF" --exclude="refresh-from-pack.sh" \
    --exclude=.git --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.mypy_cache ; then
  tier1_hit=1
fi
if grep -rniE "$tier1user" "$KIT" --exclude="$SELF" --exclude="refresh-from-pack.sh" \
    --exclude=LICENSE --exclude=.git --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.mypy_cache ; then
  tier1_hit=1
fi
if [[ "$tier1_hit" -ne 0 ]]; then
  echo "  ^^ TIER-1 violations" ; fail=1
else
  echo "  clean"
fi

echo "== TIER-2 (forbidden in memories/ + claude-user/) =="
if grep -rniE "$tier2" "$KIT/memories" "$KIT/claude-user" --exclude="$SELF" ; then
  echo "  ^^ TIER-2 violations" ; fail=1
else
  echo "  clean"
fi

echo "== TIER-3 (adw vocab — forbidden in memories/ + claude-user/ + rules/) =="
if grep -rniE "$tier3" "$KIT/memories" "$KIT/claude-user" "$KIT/claude-project/rules" --exclude="$SELF" ; then
  echo "  ^^ TIER-3 violations (adw-harness specifics; allowed in guides/ only)" ; fail=1
else
  echo "  clean"
fi

# Dangling cross-references: a rule must not point at a rule file the new
# craft/go/python taxonomy removed or renamed. Patterns chosen so they cannot
# false-match a new name (e.g. go-security.md is not matched by ddd.md).
echo "== Dangling rule cross-references =="
removed='\bddd\.md|\bmodularity\.md|code-structure\.md|\bpython\.md|llm-app-patterns\.md|xunit-patterns\.md'
# No `-d` guard here: the precondition above already refused a target without the directory, and
# a second guard covering the same condition would only mask the first under mutation.
if grep -rniE "$removed" "$KIT/claude-project/rules" --exclude="$SELF" ; then
  echo "  ^^ references to removed/renamed rules — remap to the craft/go/python names" ; fail=1
else
  echo "  clean"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "SCRUB GATE: FAIL — fix the hits above before packaging."
  exit 1
fi
echo "SCRUB GATE: PASS — no private identifiers found."

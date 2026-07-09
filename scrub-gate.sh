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
# Exits 0 clean, 1 if any forbidden token is found. Run before producing a tarball.

set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELF="$(basename "${BASH_SOURCE[0]}")"
fail=0

# TIER-1: infra hostnames, home paths, personal data, private-store tech.
tier1='t7920|trane|/home/reggie|/Users/|ghostdogsamurai|fastmail|DU[0-9]{6,}|\bPwC\b|\bCBO\b|gascity|bright-lights|\bdolt\b|msmtp'

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
# tarball and not kit content, so it is excluded from the scan.
echo "== TIER-1 (forbidden anywhere) =="
if grep -rniE "$tier1" "$KIT" --exclude="$SELF" --exclude="refresh-from-pack.sh" \
    --exclude-dir=.git --exclude-dir=__pycache__ ; then
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
if [[ -d "$KIT/claude-project/rules" ]] && grep -rniE "$removed" "$KIT/claude-project/rules" --exclude="$SELF" ; then
  echo "  ^^ references to removed/renamed rules — remap to the craft/go/python names" ; fail=1
else
  echo "  clean"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "SCRUB GATE: FAIL — fix the hits above before packaging."
  exit 1
fi
echo "SCRUB GATE: PASS — no private identifiers found."

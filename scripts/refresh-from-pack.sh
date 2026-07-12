#!/usr/bin/env bash
#
# refresh-from-pack.sh — rebuild the kit's rules, guides, and gate from a pack tag.
#
# Run this on the AUTHORING machine (the one that has the source pack checkout),
# not on the work laptop. It refreshes only the pack-sourced pieces:
#   - claude-project/rules/        (minus the two non-portable rules)
#   - claude-project/sdlc-discipline/guides/
#   - reference/sdlc-gate.py       (with its one project-specific comment scrubbed)
#
# It does NOT touch memories/ (those come from a separate scrub pass) or the
# hand-authored files (README, install.sh, CLAUDE.md, settings.json, checklist).
#
# Usage:  scripts/refresh-from-pack.sh <pack-checkout-dir> <tag>
# Example: scripts/refresh-from-pack.sh ~/code/sdlc-discipline-pack v2.43.0
#
# After running, re-run ./scrub-gate.sh and re-tar.

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <pack-checkout-dir> <tag>" >&2
  exit 2
fi

PACK_DIR="$1"
TAG="$2"
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OVERLAY="$PACK_DIR/overlay/per-provider/claude/.claude"

if [[ ! -d "$OVERLAY/rules" ]]; then
  echo "error: $OVERLAY/rules not found — is $PACK_DIR a pack checkout?" >&2
  exit 1
fi

echo "Checking out $TAG in $PACK_DIR"
git -C "$PACK_DIR" fetch --tags --quiet
git -C "$PACK_DIR" checkout --quiet "$TAG"

echo "Refreshing rules"
rm -f "$KIT"/claude-project/rules/*.md
cp "$OVERLAY"/rules/*.md "$KIT"/claude-project/rules/
# Drop the two non-portable rules (chain story-spec schema + pack architecture-config).
rm -f "$KIT"/claude-project/rules/architecture-config.md "$KIT"/claude-project/rules/stories.md

echo "Refreshing guides"
rm -f "$KIT"/claude-project/sdlc-discipline/guides/*.md
cp "$OVERLAY"/sdlc-discipline/guides/*.md "$KIT"/claude-project/sdlc-discipline/guides/
# Scrub real private identifiers that appear in pack example prose
# (a real hostname and an account-shaped example string). The illustrative
# trading-domain examples are intentionally left in place.
sed -i 's/for account DU1234567//' "$KIT"/claude-project/sdlc-discipline/guides/goos-guide.md
sed -i 's/deployable unit + T7920 setup/deployable unit + production-host setup/' \
  "$KIT"/claude-project/sdlc-discipline/guides/refactoring-guide.md

echo "Refreshing gate"
# WARNING: this overwrites reference/sdlc-gate.py from the pack. The kit's copy carries
# kit-LOCAL work NOT in the pack — the Scala scanner-plugin port and the fail-closed compile
# precondition + scoverage coverage-drop scan (shipped in v1.0.0). Copying the pack version
# REVERTS them (and reference/test_sdlc_gate.py would then fail). Reconcile by hand until the
# "which upstream is canonical on collision" decision lands (README, Refreshing and provenance).
cp "$OVERLAY"/sdlc-discipline/sdlc-gate.py "$KIT"/reference/sdlc-gate.py
# Scrub the one project-specific code-comment example.
sed -i 's/Hit on Elder REFACTOR-001 tester/Observed in practice:/; s/# 2026-05-11: same line/# same line/' \
  "$KIT"/reference/sdlc-gate.py

echo "Done. Refreshed from pack tag: $TAG"
echo "Next: reconcile reference/sdlc-gate.py (see the WARNING above), add a CHANGELOG.md entry"
echo "      for the refreshed version, run ./scrub-gate.sh, then re-tag."

#!/usr/bin/env bash
# scripts/revert-sufficiency-check.sh
#
# ADR-0002's foundational premise, proven on every commit rather than assumed: reverting a
# --no-ff merge restores the pre-merge tree, byte for byte. The merge posture (merge locally,
# publish by operator act, come back out by revert) is sound only if this git property holds
# on the machine running the checks. A throwaway repository is built, merged, reverted, and
# the pre-merge and post-revert tree hashes compared.
#
# The throwaway is throwaway ONLY if the git environment says so: a pre-commit hook run from
# a linked worktree exports an absolute GIT_DIR, and an unsanitized git here would operate on
# the PARENT repository (measured -- it merged and reverted on the real repo and reported the
# damage as a property failure). Every git call therefore runs with the redirecting variables
# unset.
#
# Exit contract, matching shellcheck_all.sh: 0 the property holds, 1 the property FAILED,
# 2 the harness could not run (setup failure is never a verdict on the property, and never a
# pass -- ADR-0001/D2).
set -euo pipefail

void() { echo "revert-sufficiency: VOID: $1; not a pass" >&2; exit 2; }

work="$(mktemp -d)" || { echo "revert-sufficiency: VOID: mktemp failed; not a pass" >&2; exit 2; }
trap 'rm -rf "$work"' EXIT

# g: git confined to the throwaway, immune to GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE from the
# caller's environment. Setup steps run through try_g so a harness failure exits 2, not 1.
g() {
  env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_OBJECT_DIRECTORY \
    -u GIT_COMMON_DIR -u GIT_CONFIG_GLOBAL -u GIT_CONFIG_SYSTEM \
    git -C "$work" "$@"
}
try_g() { g "$@" >/dev/null 2>&1 || void "git ${1:-} failed during setup"; }

try_g init -q -b main
try_g config user.email t@example.com
try_g config user.name t
echo base > "$work/a.txt" || void "write failed"
try_g add -A
try_g commit -qm base
pre_merge_tree="$(g rev-parse 'HEAD^{tree}')" || void "rev-parse failed"
try_g checkout -qb story
echo change > "$work/b.txt" || void "write failed"
try_g add -A
try_g commit -qm story
try_g checkout -q main
try_g merge -q --no-ff -m merge story
try_g revert -m 1 --no-edit HEAD
post_revert_tree="$(g rev-parse 'HEAD^{tree}')" || void "rev-parse failed"

# The one exit-1 path: the property itself. Scope stated honestly: this proves revert of a
# HEAD merge with no conflicts; reverting an older merge, or one that conflicts, is operator
# judgment and is not claimed here.
if [ "$pre_merge_tree" != "$post_revert_tree" ]; then
  echo "revert-sufficiency: FAIL: revert of a --no-ff merge did not restore the pre-merge tree (ADR-0002)" >&2
  exit 1
fi
echo "revert-sufficiency: clean (revert restores the pre-merge tree hash)"

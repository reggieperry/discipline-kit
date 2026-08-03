#!/usr/bin/env python3
"""Scope reconciliation — the cumulative diff against the scope the story declared.

The chain's readers all run code against something *upstream*: the compiler, the tests, the
specification. Every one of those finds work that is MISSING and none of them can find work
that is SURPLUS, because unrequested code violates no specification. This is the check that
runs the other way, and it is the last one before a story merges.

  exit 0   every changed path is covered by a declared path
  exit 1   at least one changed path is covered by none of them, and they are named
  exit 2   THE CHECK COULD NOT RUN — no story on the base, no `**In:**` section, or no
           machine-readable path in it. Never a pass.

THE STORY IS READ FROM THE BASE REF, NOT THE WORKING TREE. §3.10 commits stories to main
before a set is agreed and reads the graph from `origin/main`; the consequence shows up here,
because a branch that supplied its own story would declare whatever scope its own diff
happened to have. A story absent from the base is exit 2, including the case where the branch
authored one.

RENAMES ARE READ FROM BOTH SIDES, and this is the reason the tool exists rather than a
`git diff --name-only` one-liner. Measured on git 2.43: moving `scripts/check.sh` to
`other/check.sh` reports ONLY the destination under `--name-only`. A check reading that sees
one path, finds it undeclared or declared as the case may be, and never learns that a file
LEFT the scope that governed it. `-M --name-status` reports `R<score> <old> <new>` and both
sides are examined here.

The denominator is printed on every run, including the passing ones. "No drift" and "nothing
was examined" are otherwise the same output, and the second is what a wrong path pattern
produces.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from fnmatch import fnmatch

# `**In:**` opens the list; the next bold marker or blank line closes it.
IN_OPEN = re.compile(r"^\*\*In:\*\*\s*(.*)$")
BOLD = re.compile(r"^\*\*")
BACKTICKED = re.compile(r"`([^`]+)`")


def git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True
    )


def declared_paths(body: str) -> list[str]:
    """Every backticked token under the story's `**In:**` marker, in order.

    Prose without backticks yields nothing, which the caller treats as could-not-run rather
    than as an empty allowlist. An empty allowlist would fail every path and read as drift;
    the honest answer is that no machine-readable scope was declared.
    """
    out: list[str] = []
    capturing = False
    for line in body.splitlines():
        if not capturing:
            m = IN_OPEN.match(line)
            if m:
                capturing = True
                out += BACKTICKED.findall(m.group(1))
            continue
        if BOLD.match(line) or not line.strip():
            break
        out += BACKTICKED.findall(line)
    return out


def covered(path: str, declared: list[str]) -> bool:
    """Is `path` covered by any declared entry?

    A declared entry ending in `/` is a directory prefix and covers everything beneath it.
    The trailing separator is required and is not cosmetic: `scripts` as a bare prefix also
    matches `scripts-old/legacy.sh`, which parks a story that never touched the protected
    tree — and a check that halts ordinary work is one somebody eventually widens.

    Anything else is matched as a glob, so `src/*.py` and an exact filename both work.
    """
    for d in declared:
        if d.endswith("/"):
            if path == d.rstrip("/") or path.startswith(d):
                return True
        elif path == d or fnmatch(path, d):
            return True
    return False


def changed_paths(repo: str, base: str) -> list[str] | None:
    """Every path the branch touched, with BOTH sides of every rename.

    Returns None if git could not answer, which is could-not-run rather than an empty diff —
    a bad ref and a clean branch must not produce the same green.
    """
    r = git(repo, "diff", "-M", "--name-status", f"{base}...HEAD")
    if r.returncode != 0:
        return None
    paths: list[str] = []
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0]
        if status.startswith(("R", "C")) and len(fields) >= 3:
            paths += [fields[1], fields[2]]  # a move is a change to both ends
        elif len(fields) >= 2:
            paths.append(fields[1])
    return sorted(set(paths))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--story", required=True, help="story path, relative to the repo root")
    ap.add_argument("--base", default="origin/main", help="base ref the diff is taken against")
    ap.add_argument("--repo", default=".", help="repository directory")
    a = ap.parse_args()

    show = git(a.repo, "show", f"{a.base}:{a.story}")
    if show.returncode != 0:
        print(
            f"scope: could not read '{a.story}' from '{a.base}' — the scope a branch declares "
            f"for itself is not a declaration. No check performed.",
            file=sys.stderr,
        )
        return 2

    declared = declared_paths(show.stdout)
    if not declared:
        print(
            f"scope: '{a.story}' on '{a.base}' carries no backticked path under '**In:**'. "
            f"No machine-readable scope, so no check performed.",
            file=sys.stderr,
        )
        return 2

    changed = changed_paths(a.repo, a.base)
    if changed is None:
        print(f"scope: could not diff '{a.base}...HEAD'. No check performed.", file=sys.stderr)
        return 2

    drift = [p for p in changed if not covered(p, declared)]
    print(
        f"scope: {len(declared)} declared path(s), {len(changed)} changed path(s) examined, "
        f"{len(drift)} outside scope"
    )
    if drift:
        for p in drift:
            print(f"  outside scope: {p}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Scope reconciliation — the cumulative diff against the scope the story declared.

The chain's readers all run code against something *upstream*: the compiler, the tests, the
specification. Every one of those finds work that is MISSING and none of them can find work
that is SURPLUS, because unrequested code violates no specification. This is the check that
runs the other way, and it is the last one before a story merges.

  exit 0   every changed path is covered by a declared path
  exit 1   at least one changed path is covered by none of them, and they are named
  exit 2   THE CHECK COULD NOT RUN. Never a pass, and NAMED: `NO STORY`, `NO SCOPE SECTION`,
           `NO PATH DECLARATIONS`, or a diff that did not answer.

THE SCOPE SECTION IS WRITTEN TWO WAYS AND BOTH ARE READ. The walkthrough's A4 sketch writes
`**In:**` / `**Out:**`; `harness/templates/story-template.md` writes `In scope:` / `Out of
scope:` with the bullet list a blank line below the opener, and every story under `stories/`
follows the template. The two need separate windows rather than one union: the bold form puts
free prose under it and is terminated BY a blank line, and terminating the template form there
would end its list before the first bullet ever arrived.

THE THREE COULD-NOT-RUN STATES ARE NAMED APART, because they send the operator to three
different remedies and an unnamed exit 2 sends them to none. A missing story is a base-ref or
a filing problem. A story with no scope section at all is malformed. A story whose scope is
PROSE is neither: the walkthrough's proximity rule says a story months out is a light stub
with rough scope, and ten of this repository's eleven stories are legitimately that shape. The
third state prints how many changed paths went UNEXAMINED, so a stub cannot read as a quiet
green — the check that found nothing and the check that looked at nothing say so differently.

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
import os
import re
import subprocess
import sys
from fnmatch import fnmatch

# `**In:**` opens the list; the next bold marker or blank line closes it.
IN_BOLD = re.compile(r"^\*\*In:\*\*\s*(.*)$")
# `In scope:` opens a bullet list a blank line below it; the first line that is neither a
# bullet nor a bullet's continuation closes it, which is what `Out of scope:` is.
IN_PROSE = re.compile(r"^In scope:\s*(.*)$", re.IGNORECASE)
HEADING = re.compile(r"^#")
BULLET = re.compile(r"^\s*[-*+]\s")
BOLD = re.compile(r"^\*\*")
BACKTICKED = re.compile(r"`([^`]+)`")


def clean_env() -> dict[str, str]:
    """The environment with git's own variables dropped.

    THIS TOOL IS RUN FROM HOOKS AND FROM PHASE SEAMS, both of which export `GIT_DIR` and
    `GIT_INDEX_FILE`. A subprocess inherits them, and `git -C <other repo>` then reads and
    writes the EXPORTING repository's gitdir and index while appearing to operate on the repo
    named by `-C`. The scope check is a read, so the visible symptom is a verdict computed
    against the wrong tree rather than corruption; the fixture beside it, which writes, took
    the corruption. Do not rely on `-C` to re-scope what the environment already decided.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, env=clean_env()
    )


def bold_form_paths(rest: str, below: list[str]) -> list[str]:
    """The `**In:**` window: the opener's own text, then lines up to a blank or a bold marker.

    Blank-line termination is kept exactly as it was. This form writes prose freely underneath
    the section, and a wider window would admit backticks that are not scope — every one of
    which would ENLARGE the allowlist, which is the failure direction this tool exists to catch.
    """
    out = BACKTICKED.findall(rest)
    for line in below:
        if not line.strip() or BOLD.match(line) or HEADING.match(line):
            break
        out += BACKTICKED.findall(line)
    return out


def declaring_part(line: str) -> str:
    """The part of a scope bullet that declares: everything before its first em dash.

    Matched on the character rather than on ` — ` or `—`, so it holds under either spacing. The
    kit sets em dashes closed and the corpus this reads is mixed, and a separator rule that
    depended on the spacing would be a rule about house style rather than about scope.
    """
    return line.split("—", 1)[0]


def prose_form_paths(rest: str, below: list[str]) -> list[str]:
    """The `In scope:` window: the bullet list, across the blank line that separates it.

    Blank lines are skipped rather than closing the window, so the list is bounded instead by
    what a list ends at: a heading, a bold marker, or any line in column 0 that is not a bullet.

    THE WINDOW IS NARROWER THAN THE SECTION, in the two ways a scope bullet mentions a path it
    is not declaring. Both were MEASURED admitting a non-declaration before they were closed.

      A CONTINUATION LINE DECLARES NOTHING. A bullet may wrap — `stories/STORY-0001` wraps its
      in-scope bullet — and the wrapped remainder is prose about the declaration rather than
      more of it. Reading it admitted `other/b.py` from a line whose own words said it was
      declaring nothing. A continuation is therefore SKIPPED and does not close the window
      either, because the bullets after it are still declarations.

      NOTHING AFTER A BULLET'S EM DASH DECLARES. The dash is where a scope bullet turns to
      commentary — the pattern to mirror, the sibling that stays behind, the file to read
      first — and every path named there is one the branch must NOT touch. Reading past it
      admitted a path from `` `src/` — mirror the pattern in `tests/legacy/old.py` ``.

    Both narrowings can only LOSE a declaration, never invent one, so the failure they can
    cause is a path reported as drift that the story meant to allow. That is the direction this
    tool is allowed to be wrong in; the direction it is not is the allowlist growing on its own.

    THE OUT-OF-SCOPE LIST IS NEVER ENTERED, and the column-0 rule is the whole of what keeps it
    out: `Out of scope:` is a line in column 0 that is not a bullet, so the window closes on it.
    That matters more than it looks, because the out-of-scope list holds paths in exactly the
    same shape as the in-scope one — a window running past its opener hands the branch an
    allowlist containing what the story forbade, which widens scope silently. A separate
    `Out of scope:` pattern was tried here and REMOVED: two guards covering one condition mask
    each other under mutation, and each survived alone while the pair together failed the
    fixture. One guard, with a case that goes red when it goes.
    """
    out = BACKTICKED.findall(declaring_part(rest))
    for line in below:
        if not line.strip():
            continue
        if HEADING.match(line) or BOLD.match(line):
            break
        if BULLET.match(line):
            out += BACKTICKED.findall(declaring_part(line))
            continue
        if line[:1].isspace():
            continue
        break
    return out


def declared_paths(body: str) -> tuple[list[str], bool]:
    """Every backticked token under the story's in-scope opener, and whether one was found.

    The two are returned separately because "no scope section" and "a scope section written in
    prose" are different findings with different remedies, and collapsing them into an empty
    list loses the distinction. Prose without backticks yields no paths, which the caller
    treats as could-not-run rather than as an empty allowlist: an empty allowlist would fail
    every path and read as drift, and the honest answer is that no path was declared.
    """
    lines = body.splitlines()
    for i, line in enumerate(lines):
        bold = IN_BOLD.match(line)
        if bold:
            return bold_form_paths(bold.group(1), lines[i + 1:]), True
        prose = IN_PROSE.match(line)
        if prose:
            return prose_form_paths(prose.group(1), lines[i + 1:]), True
    return [], False


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
            f"scope: NO STORY — could not read '{a.story}' from '{a.base}'. The scope a branch "
            f"declares for itself is not a declaration. No check performed.",
            file=sys.stderr,
        )
        return 2

    declared, has_section = declared_paths(show.stdout)
    if not has_section:
        print(
            f"scope: NO SCOPE SECTION — '{a.story}' on '{a.base}' carries neither an '**In:**' "
            f"marker nor an 'In scope:' opener. The story is malformed against "
            f"harness/templates/story-template.md, so no check performed.",
            file=sys.stderr,
        )
        return 2

    changed = changed_paths(a.repo, a.base)
    if changed is None:
        print(f"scope: could not diff '{a.base}...HEAD'. No check performed.", file=sys.stderr)
        return 2

    if not declared:
        print(
            f"scope: NO PATH DECLARATIONS — '{a.story}' on '{a.base}' has a scope section that "
            f"names no backticked path: the scope carries no path declarations; nothing to "
            f"reconcile lexically. {len(changed)} changed path(s) went UNEXAMINED. This is the "
            f"walkthrough's stub depth, not a defect in the story — tighten the scope to paths "
            f"before hand-off if the work is imminent. No check performed.",
            file=sys.stderr,
        )
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

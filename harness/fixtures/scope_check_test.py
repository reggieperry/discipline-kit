#!/usr/bin/env python3
"""Red-first fixture for `harness/scope_check.py`.

Scope reconciliation is the chain's implementation-to-declaration check: every path the
cumulative diff touches must be covered by the scope the story declared before any code was
written. It is the one direction the reviewer structurally cannot cover, because spec-to-code
finds missing work and never surplus work.

Each case builds a throwaway git repository, writes a story file, makes a diff, and asserts
the checker's exit code:

  in-scope        every changed path is under a declared path        -> 0
  drift           a changed path is under none of them               -> 1
  rename-out      a declared path is MOVED OUT of the declared set   -> 1
  rename-in       a file moves INTO scope from outside it            -> 1
  no-story        the story file does not exist                      -> 2 (never a pass)
  no-in-section   the story carries no `**In:**` section             -> 2 (never a pass)
  no-paths        `**In:**` exists but names no backticked path      -> 2 (never a pass)
  empty-diff      nothing changed at all                             -> 0, denominator 0
  prefix-boundary a SIBLING of a declared directory is touched        -> 1

RENAME-OUT IS THE CASE THIS TOOL EXISTS FOR, and it is why the tool cannot use
`git diff --name-only`. Measured on git 2.43: moving `scripts/check.sh` to `other/check.sh`
reports ONLY the destination under `--name-only`, so a prefix check against the declared set
sees one unprotected path and passes — while the file has left the scope that governed it.
`-M --name-status` reports `R100 <old> <new>` and both sides can be examined.

The three `2` cases matter as much as the failing one: a checker that passes when it found
nothing to check reports the same green as one that verified everything.

Run: python3 harness/fixtures/scope_check_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "scope_check.py"

STORY = """\
---
id: STORY-0001
title: A worked example
---

# STORY-0001 A worked example

## Scope

**In:** `src/`, `docs/note.md`

**Out:**
- everything else
"""

STORY_NO_IN = """\
---
id: STORY-0001
title: A worked example
---

# STORY-0001 A worked example

## Notes

No scope section at all.
"""

STORY_PROSE_IN = """\
---
id: STORY-0001
title: A worked example
---

# STORY-0001 A worked example

## Scope

**In:** the source tree and the note, described in prose with no backticks.
"""


def git(repo: Path, *args: str) -> str:
    """Run git in `repo`, returning stdout. Raises on non-zero so a broken fixture is loud."""
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout


def new_repo(tmp: Path, story: str | None = STORY) -> Path:
    """A repository whose `main` carries the story, with a `feature` branch checked out.

    THE STORY LANDS ON MAIN, not on the branch. §3.10 commits stories to main before a set is
    agreed and reads the graph from `origin/main`, and the reason shows up here: a branch that
    supplied its own story could declare whatever scope its diff happened to have.
    """
    repo = tmp / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main", ".")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "fixture")
    (repo / "src").mkdir()
    (repo / "src-old").mkdir()
    (repo / "other").mkdir()
    (repo / "docs").mkdir()
    (repo / "src" / "a.py").write_text("baseline\n")
    (repo / "src-old" / "legacy.py").write_text("baseline\n")
    (repo / "other" / "b.py").write_text("baseline\n")
    (repo / "docs" / "note.md").write_text("baseline\n")
    if story is not None:
        (repo / "STORY-0001.md").write_text(story)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "baseline")
    git(repo, "checkout", "-q", "-b", "feature")
    return repo


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", message)


def run_tool(repo: Path, story: str = "STORY-0001.md") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--story", story, "--base", "main", "--repo", str(repo)],
        capture_output=True,
        text=True,
    )


def case(name: str, want: int, build, story: str | None = STORY) -> bool:
    """Build a repository via `build`, run the tool, and compare the exit code."""
    with tempfile.TemporaryDirectory() as td:
        repo = new_repo(Path(td), story)
        build(repo)
        got = run_tool(repo)
        ok = got.returncode == want
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want}, got {got.returncode}")
        if not ok:
            print(f"       stdout: {got.stdout.strip()[:300]}")
            print(f"       stderr: {got.stderr.strip()[:300]}")
        return ok


def build_in_scope(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("changed\n")
    (repo / "docs" / "note.md").write_text("changed\n")
    commit_all(repo, "work inside the declared scope")


def build_drift(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("changed\n")
    (repo / "other" / "b.py").write_text("changed — outside the declared scope\n")
    commit_all(repo, "work outside the declared scope")


def build_rename_out(repo: Path) -> None:
    """A declared file leaves the declared set. `--name-only` cannot see this."""
    git(repo, "mv", "src/a.py", "other/a.py")
    commit_all(repo, "move a declared file out of scope")


def build_rename_in(repo: Path) -> None:
    """A file enters scope from outside it; the source path was never declared."""
    git(repo, "mv", "other/b.py", "src/b.py")
    commit_all(repo, "move an undeclared file into scope")


def build_no_story(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("changed\n")
    commit_all(repo, "work with no story file at all")


def build_no_in_section(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("changed\n")
    commit_all(repo, "work with a story carrying no scope section")


def build_no_paths(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("changed\n")
    commit_all(repo, "work with a prose-only scope section")


def build_empty_diff(repo: Path) -> None:
    """The branch has diverged but touched no path. Vacuously in scope, denominator 0."""
    git(repo, "commit", "-q", "--allow-empty", "-m", "a commit that changes nothing")


def build_prefix_boundary(repo: Path) -> None:
    """`src-old/` is a SIBLING of the declared `src/`, not a child of it.

    Added after a surviving mutant: dropping the trailing-separator requirement from
    `covered()` left all nine cases green, because no fixture had a sibling directory whose
    name merely starts with a declared one. A bare `startswith("src")` swallows this path and
    the drift goes unreported.
    """
    (repo / "src-old" / "legacy.py").write_text("changed — a sibling, not a child\n")
    commit_all(repo, "touch a directory that merely shares a prefix")


def build_story_on_branch(repo: Path) -> None:
    """A branch that authors its own story does NOT get to declare its own scope."""
    (repo / "STORY-0001.md").write_text(STORY)
    (repo / "other" / "b.py").write_text("changed — would be drift under any honest scope\n")
    commit_all(repo, "branch supplies its own story")


def main() -> int:
    if not TOOL.is_file():
        print(f"scope_check_test: tool not found at {TOOL}", file=sys.stderr)
        return 2
    results = [
        case("in-scope", 0, build_in_scope),
        case("drift", 1, build_drift),
        case("rename-out", 1, build_rename_out),
        case("rename-in", 1, build_rename_in),
        case("no-story", 2, build_no_story, story=None),
        case("no-in-section", 2, build_no_in_section, story=STORY_NO_IN),
        case("no-paths", 2, build_no_paths, story=STORY_PROSE_IN),
        case("empty-diff", 0, build_empty_diff),
        case("prefix-boundary", 1, build_prefix_boundary),
        case("story-only-on-branch", 2, build_story_on_branch, story=None),
    ]
    failed = results.count(False)
    print(f"scope_check_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

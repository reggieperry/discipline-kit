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
  no-story        the story file does not exist                      -> 2, NO STORY
  no-in-section   the story carries NEITHER scope opener             -> 2, NO SCOPE SECTION
  no-paths        `**In:**` exists but names no backticked path      -> 2, NO PATH DECLARATIONS
  empty-diff      nothing changed at all                             -> 0, denominator 0
  prefix-boundary a SIBLING of a declared directory is touched        -> 1

The five `template-*` cases and `template-file` cover the OTHER scope form, which is the one
every real story is written in. `harness/templates/story-template.md` writes `In scope:` /
`Out of scope:` with the bullets a blank line below the opener; the tool read only `**In:**`,
so all eleven files under `stories/` reported could-not-run and the check had never run once on
the corpus it governs. `template-file` reads the template itself rather than a transcription of
it, because a transcription cannot catch the template renaming its opener.

  bold-window-narrow        `**In:**` does NOT read past its blank line    -> 1
  template-in-scope         the template form, paths declared and honored  -> 0
  template-drift            the template form, a path outside them         -> 1
  continuation-survives     a wrapped bullet does not END the list         -> 0
  continuation-not-declared a backtick on a CONTINUATION line declares nothing -> 1
  post-dash-not-declared    a backtick after a bullet's em dash likewise   -> 1
  template-out-not-declared a path named under `Out of scope:` is touched  -> 1
  template-no-paths         the template form, prose bullets, no paths     -> 2, NO PATH DECL.
  template-file             the shipped template parses as a scope section -> 2, NO PATH DECL.

`template-out-not-declared` is the one whose failure would be silent: the out-of-scope list is
a list of paths in the same shape as the in-scope one, so a window that runs past its opener
hands the branch an allowlist containing what the story forbade.

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

import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "scope_check.py"

# The names the tool must give its two non-story could-not-run states. Asserted as strings so a
# state that stops being named, or starts being named as the other one, is a failure rather
# than an indistinguishable exit 2.
NO_STORY_MARKER = "NO STORY"
NO_SECTION_MARKER = "NO SCOPE SECTION"
NO_PATHS_MARKER = "NO PATH DECLARATIONS"

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

# The bold form's window is narrower than the template form's ON PURPOSE, and this is the story
# that shows the difference. `**In:**` puts free prose under it, so the window is terminated by
# the first blank line; the template form cannot use that rule, because a blank line is what
# separates its opener from its own first bullet. Reading the bold form with the wider window
# picks up `other/` from the note below and ENLARGES the allowlist. Measured: with no case of
# this shape, giving both forms the wide window left every case green.
STORY_BOLD_WITH_NOTES = """\
---
id: STORY-0001
title: A worked example
---

# STORY-0001 A worked example

## Scope

**In:** `src/`

- a note below the blank line, mentioning `other/` without declaring it

**Out:**
- everything else
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

# The five below are the TEMPLATE's scope form: `In scope:` / `Out of scope:` openers with a
# blank line between the opener and its bullet list. `harness/templates/story-template.md`
# writes that form and all eleven files under `stories/` follow it, while the tool read only
# `**In:**` — so every real story reported could-not-run and the check had never once run on
# the corpus it governs. The blank line is why the two forms need separate windows: the bold
# form is terminated BY a blank line, and terminating this one there would end the list before
# its first bullet.
TEMPLATE_STORY = """\
---
id: STORY-0001
title: A worked example
---

# STORY-0001 A worked example

# Scope and non-goals

In scope:

- the source tree `src/` and the note `docs/note.md`

Out of scope:

- everything else

# Acceptance criteria
"""

# A wrapped bullet, whose CONTINUATION line carries a backticked path. Two things must both
# hold and they pull in opposite directions: the continuation must not declare anything, and it
# must not end the list either — the bullets after it are still declarations. `stories/
# STORY-0001` wraps its in-scope bullet, so the wrap itself is real; what is not real is the idea
# that everything under the opener is a path declaration.
TEMPLATE_STORY_CONTINUATION = """\
---
id: STORY-0001
title: A worked example
---

# STORY-0001 A worked example

# Scope and non-goals

In scope:

- the source tree, described across a wrapped line that happens to mention
  `other/b.py` while declaring nothing
- `src/`
- `docs/note.md`

Out of scope:

- everything else

# Acceptance criteria
"""

# A bullet that declares a path and then, after an em dash, POINTS AT another one. The pattern to
# mirror, the file that stays behind, the sibling that must not be touched: all of them are named
# in exactly this position, and none of them is a declaration. The bold window's docstring has
# always disclosed this hazard for its own form; the prose window admitted it until measured.
TEMPLATE_STORY_POST_DASH = """\
---
id: STORY-0001
title: A worked example
---

# STORY-0001 A worked example

# Scope and non-goals

In scope:

- `src/` — mirror the pattern already in `other/b.py`, which stays as it is

Out of scope:

- everything else

# Acceptance criteria
"""

TEMPLATE_STORY_OUT_PATHS = """\
---
id: STORY-0001
title: A worked example
---

# STORY-0001 A worked example

# Scope and non-goals

In scope:

- `src/`

Out of scope:

- `other/`, which an implementer must not touch even though it is adjacent

# Acceptance criteria
"""

TEMPLATE_STORY_PROSE = """\
---
id: STORY-0001
title: A worked example
---

# STORY-0001 A worked example

# Scope and non-goals

In scope:

- the advance scripts and their fixtures

Out of scope:

- the seam court replay

# Acceptance criteria
"""

# The real template, read from the tree rather than transcribed. A transcription cannot catch
# the template changing its opener, which is the drift this whole reconciliation was.
TEMPLATE_FILE = (
    Path(__file__).resolve().parent.parent / "templates" / "story-template.md"
)


def clean_env() -> dict[str, str]:
    """The environment with git's own variables dropped.

    A `pre-commit` hook runs with `GIT_DIR` and `GIT_INDEX_FILE` exported, and a subprocess
    inherits them, so `git -C <throwaway> commit` writes into the REAL repository's index
    instead of the fixture's. In an ordinary checkout `GIT_DIR` is the relative `.git`, which
    `-C` accidentally re-resolves onto the throwaway; in a LINKED WORKTREE it is absolute and
    the fixture dies. The chain's phases commit from worktrees, so the accident is not a
    footing to stand on.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> str:
    """Run git in `repo`, returning stdout. Raises on non-zero so a broken fixture is loud."""
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=clean_env(),
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
        env=clean_env(),
    )


def case(name: str, want: int, build, story: str | None = STORY, marker: str | None = None) -> bool:
    """Build a repository via `build`, run the tool, and compare the exit code.

    `marker` is a substring the run's output must carry. The three could-not-run states share
    exit 2 and are NOT the same finding — a missing story, a story with no scope section, and a
    story whose scope is prose send the operator to three different remedies — so an exit code
    alone cannot tell whether the tool named the state it actually met. Where a case supplies a
    marker, the exit code and the naming are asserted together.
    """
    with tempfile.TemporaryDirectory() as td:
        repo = new_repo(Path(td), story)
        build(repo)
        got = run_tool(repo)
        said = got.stdout + got.stderr
        ok = got.returncode == want and (marker is None or marker in said)
        want_txt = f"exit {want}" + (f" naming '{marker}'" if marker else "")
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: want {want_txt}, got exit {got.returncode}")
        if not ok:
            print(f"       stdout: {got.stdout.strip()[:300]}")
            print(f"       stderr: {got.stderr.strip()[:300]}")
        return ok


def hostile_env_case() -> bool:
    """The tool must read the repo it was POINTED at, not the one the environment names.

    Every case above scrubs `GIT_*` before invoking the tool, which is right for isolating the
    fixture and wrong as the only coverage: it means the suite cannot see whether the TOOL
    scrubs. It did not, and the fixture's own scrub is what hid that. Here the tool is invoked
    with `GIT_DIR` and `GIT_INDEX_FILE` pointing at a DECOY repository, exactly as a hook or a
    phase seam would export them, and the verdict must be the drift the target repo actually
    contains.
    """
    with tempfile.TemporaryDirectory() as td:
        repo = new_repo(Path(td), STORY)
        build_drift(repo)
        decoy = Path(td) / "decoy"
        decoy.mkdir()
        git(decoy, "init", "-q", "-b", "main", ".")
        env = clean_env()
        env["GIT_DIR"] = str(decoy / ".git")
        env["GIT_INDEX_FILE"] = str(decoy / ".git" / "index")
        got = subprocess.run(
            [sys.executable, str(TOOL), "--story", "STORY-0001.md", "--base", "main",
             "--repo", str(repo)],
            capture_output=True,
            text=True,
            env=env,
        )
        ok = got.returncode == 1
        print(f"  {'ok  ' if ok else 'FAIL'} hostile-env: want exit 1 (the drift in --repo), got {got.returncode}")
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


def build_out_of_scope_touched(repo: Path) -> None:
    """A path named under `Out of scope:` is touched, and must read as drift.

    The out-of-scope list is a list of paths in exactly the same shape as the in-scope one, so
    a window that runs past the `Out of scope:` opener swallows it and hands the branch an
    allowlist containing the very paths the story forbade. That widens scope silently, which is
    the one direction this tool exists to catch.
    """
    (repo / "other" / "b.py").write_text("changed — named under Out of scope\n")
    commit_all(repo, "touch a path the story declared out of scope")


def template_file_case() -> bool:
    """The tool must find a scope section in `harness/templates/story-template.md` itself.

    This is the reconciliation, pinned at its source. The template ships placeholder bullets
    with no backticked path, so the honest verdict is the named no-path-declarations state —
    NOT the no-scope-section state, which is what the tool returned for every story written to
    this template before the fix. If the template renames its opener, this case goes red at the
    template rather than silently on eleven stories.
    """
    if not TEMPLATE_FILE.is_file():
        print(f"  FAIL template-file: {TEMPLATE_FILE} not found")
        return False
    body = TEMPLATE_FILE.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as td:
        repo = new_repo(Path(td), body)
        build_in_scope(repo)
        got = run_tool(repo)
        said = got.stdout + got.stderr
        ok = got.returncode == 2 and NO_PATHS_MARKER in said and NO_SECTION_MARKER not in said
        print(
            f"  {'ok  ' if ok else 'FAIL'} template-file: want exit 2 naming "
            f"'{NO_PATHS_MARKER}' and not '{NO_SECTION_MARKER}', got exit {got.returncode}"
        )
        if not ok:
            print(f"       stdout: {got.stdout.strip()[:300]}")
            print(f"       stderr: {got.stderr.strip()[:300]}")
        return ok


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
        case("no-story", 2, build_no_story, story=None, marker=NO_STORY_MARKER),
        case("no-in-section", 2, build_no_in_section, story=STORY_NO_IN,
             marker=NO_SECTION_MARKER),
        case("no-paths", 2, build_no_paths, story=STORY_PROSE_IN, marker=NO_PATHS_MARKER),
        case("empty-diff", 0, build_empty_diff),
        case("prefix-boundary", 1, build_prefix_boundary),
        case("story-only-on-branch", 2, build_story_on_branch, story=None,
             marker=NO_STORY_MARKER),
        case("bold-window-narrow", 1, build_out_of_scope_touched, story=STORY_BOLD_WITH_NOTES),
        case("template-in-scope", 0, build_in_scope, story=TEMPLATE_STORY),
        case("template-drift", 1, build_drift, story=TEMPLATE_STORY),
        case("continuation-survives", 0, build_in_scope, story=TEMPLATE_STORY_CONTINUATION),
        case("continuation-not-declared", 1, build_out_of_scope_touched,
             story=TEMPLATE_STORY_CONTINUATION),
        case("post-dash-not-declared", 1, build_out_of_scope_touched,
             story=TEMPLATE_STORY_POST_DASH),
        case("template-out-not-declared", 1, build_out_of_scope_touched,
             story=TEMPLATE_STORY_OUT_PATHS),
        case("template-no-paths", 2, build_no_paths, story=TEMPLATE_STORY_PROSE,
             marker=NO_PATHS_MARKER),
        template_file_case(),
        hostile_env_case(),
    ]
    failed = results.count(False)
    print(f"scope_check_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

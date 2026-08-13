#!/usr/bin/env python3
"""Attempt tooling: the re-walk deletion, and the worktree clearing an attempt starts with.

Two decisions become mechanism here, and neither of them is a verdict, which is why this module
has no exit code 1 at all.

ADR-0001/D1's re-walk: a bounce back to phase N deletes `phase-{N..end}` of the current attempt in
ONE atomic `git update-ref --stdin` batch, so derived position can never disagree with the rule
that a bounce invalidates everything downstream. The batch is the decision and not an
optimization: a per-ref loop that dies halfway leaves a position that is neither the old one nor
the new one, and position is re-derived from exactly these refs on every resume. The batch carries
each ref's old value, so a ref that moved between the read and the write aborts the whole delete
rather than removing something the caller never saw.

ADR-0004/D2's attempt start: the sequencer creates phase worktrees at a pinned path outside the
parent, and every attempt start first clears that path — `git worktree remove --force` where the
path is registered, then `git worktree prune`. The measured failure this closes is a worktree
whose directory is gone while git still holds the registration, where `git worktree add` refuses
and the retry cannot start.

WHAT THE CLEARING DELIBERATELY DOES NOT DO is delete a directory git does not know about. A path
still on disk after the registration is gone reads could-not-run, naming it: removing whatever a
caller happened to name is a destructive act on a mistyped argument, and refusing costs an
operator one command where the alternative costs them a directory.

THAT REFUSAL IS IN TENSION WITH D2'S LETTER, and the tension is recorded rather than resolved
here. D2 says every attempt start clears the pinned path so that a dead phase cannot block a
retry; a phase that crashed leaving an unregistered directory behind meets a refusal instead, and
every retry of that story then stops at the same place until an operator intervenes. The safety
reading and the availability reading disagree, and the question belongs to whoever owns the
sequencer's authority to act unattended: the sequencer clearing the path under its own authority
after diagnosing what is there, against the blind force-delete D2's letter implies. STORY-0006
(the sequencer core) and STORY-0011 (its fail-closed start-up) are where that is settled, and
this module changes when it is.

    0   done, with what was deleted or cleared printed
    2   could-not-run, naming what stopped it. Never a story verdict either way.

Usage:
    python3 harness/chain/attempt.py rewalk --repo <r> --story <id> --attempt <n> --from-phase <n>
    python3 harness/chain/attempt.py clear-worktree --repo <r> --path <worktree>
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import loader  # noqa: E402  (resolved from this file's own directory, beside it)

DONE = 0
COULD_NOT_RUN = 2

CouldNotRun = loader.CouldNotRun

COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PHASE_REF = re.compile(r"/phase-([1-9][0-9]*)$")


def say(line: str) -> None:
    print(line, flush=True)


def component(kind: str, value: str) -> str:
    if not COMPONENT.match(value or "") or ".." in value:
        raise CouldNotRun(f"the {kind} {value!r} is not a single ref component")
    return value


def positive(kind: str, value: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]*", value or ""):
        raise CouldNotRun(f"the {kind} {value!r} is not a positive integer")
    return value


def git(repo: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run git against `repo` with the caller's own git environment dropped.

    The scrub is `loader.child_env(None)`, shared with every other child this runtime spawns: git
    reads `GIT_DIR` in preference to `-C`, so a seam invoked from a hook would otherwise delete
    refs in the caller's repository rather than in the one it was pointed at.
    """
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=loader.child_env(None),
        )
    except OSError as e:
        raise CouldNotRun(f"git could not be run against {repo}: {e}") from e


def working_tree(repo: Path) -> Path:
    if not repo.is_dir():
        raise CouldNotRun(f"{repo} is not a directory")
    done = git(repo, "rev-parse", "--is-inside-work-tree")
    if done.returncode != 0 or done.stdout.strip() != "true":
        raise CouldNotRun(f"{repo} is not a git working tree: {done.stderr.strip()}")
    return repo


def attempt_refs(repo: Path, story: str, attempt: str) -> list[tuple[str, str]]:
    """Every ref under one attempt, as (refname, sha)."""
    prefix = f"refs/chain/{story}/attempt-{attempt}/"
    done = git(repo, "for-each-ref", "--format=%(refname) %(objectname)", prefix)
    if done.returncode != 0:
        raise CouldNotRun(f"the refs under {prefix} could not be listed: {done.stderr.strip()}")
    out = []
    for line in done.stdout.splitlines():
        name, _, sha = line.partition(" ")
        if name and sha:
            out.append((name, sha))
    return out


def rewalk(a: argparse.Namespace) -> int:
    """ADR-0001/D1's deletion, in one batch, over the current attempt only."""
    repo = working_tree(Path(a.repo).resolve())
    story = component("story id", a.story)
    attempt = positive("attempt", a.attempt)
    first = int(positive("from-phase", a.from_phase))

    present = attempt_refs(repo, story, attempt)
    doomed = [(name, sha) for name, sha in present
              if (m := PHASE_REF.search(name)) and int(m.group(1)) >= first]
    other = [name for name, _ in present if not PHASE_REF.search(name)]
    say(f"advance-attempt: {len(present)} ref(s) under attempt-{attempt} of {story}, "
        f"{len(doomed)} at phase {first} or above")
    for name in other:
        say(f"advance-attempt: not a phase ref, left alone: {name}")
    if not doomed:
        say("advance-attempt: nothing to delete")
        return DONE

    batch = "".join(f"delete {name} {sha}\n" for name, sha in sorted(doomed))
    done = git(repo, "update-ref", "--stdin", stdin=batch)
    if done.returncode != 0:
        raise CouldNotRun(
            f"the batch delete of {len(doomed)} ref(s) failed, and git applies the batch or "
            f"none of it: {done.stderr.strip()}"
        )
    left = [name for name, _ in attempt_refs(repo, story, attempt)
            if name in {n for n, _ in doomed}]
    if left:
        raise CouldNotRun(f"the batch reported success and these refs remain: {', '.join(left)}")
    for name, _ in sorted(doomed):
        say(f"advance-attempt: deleted {name}")
    return DONE


def registered_worktrees(repo: Path) -> list[Path]:
    done = git(repo, "worktree", "list", "--porcelain")
    if done.returncode != 0:
        raise CouldNotRun(f"the worktree list could not be read: {done.stderr.strip()}")
    return [Path(line.split(" ", 1)[1]) for line in done.stdout.splitlines()
            if line.startswith("worktree ")]


def same_path(one: Path, two: Path) -> bool:
    """Path identity that survives a symlinked prefix, since a scratch root is often one."""
    return one.resolve() == two.resolve()


def clear_worktree(a: argparse.Namespace) -> int:
    """ADR-0004/D2: the pinned worktree path is cleared before an attempt starts."""
    repo = working_tree(Path(a.repo).resolve())
    path = Path(a.path)
    was = [w for w in registered_worktrees(repo) if same_path(w, path)]
    if was:
        removed = git(repo, "worktree", "remove", "--force", str(path))
        say(f"advance-attempt: worktree remove exited {removed.returncode}"
            f"{': ' + removed.stderr.strip() if removed.returncode != 0 else ''}")
    pruned = git(repo, "worktree", "prune")
    if pruned.returncode != 0:
        raise CouldNotRun(f"worktree prune failed: {pruned.stderr.strip()}")

    still = [w for w in registered_worktrees(repo) if same_path(w, path)]
    if still:
        raise CouldNotRun(f"{path} is still a registered worktree of {repo} after remove and prune")
    if path.exists():
        raise CouldNotRun(
            f"{path} is no longer registered but still exists on disk, and a directory git does "
            "not know about is not this tool's to delete"
        )
    say(f"advance-attempt: {path} is clear and a worktree can be created there "
        f"(registered before: {'yes' if was else 'no'})")
    return DONE


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="act", required=True)

    walk = sub.add_parser("rewalk", help="delete phase-{N..end} of one attempt, in one batch")
    walk.add_argument("--repo", required=True)
    walk.add_argument("--story", required=True)
    walk.add_argument("--attempt", required=True)
    walk.add_argument("--from-phase", required=True)
    walk.set_defaults(run=rewalk)

    clear = sub.add_parser("clear-worktree", help="clear the pinned worktree path for an attempt")
    clear.add_argument("--repo", required=True)
    clear.add_argument("--path", required=True)
    clear.set_defaults(run=clear_worktree)

    a = ap.parse_args()
    try:
        return a.run(a)
    except CouldNotRun as e:
        print(f"advance-attempt: VOID: {e}", file=sys.stderr)
        return COULD_NOT_RUN
    except OSError as e:
        print(f"advance-attempt: VOID: a filesystem read failed: {e}", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    raise SystemExit(main())

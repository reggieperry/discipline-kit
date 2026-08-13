#!/usr/bin/env python3
"""The phase seam: one canonical exit contract, and the ref write inside it.

Three decisions of `docs/adrs/ADR-0003-sequencer-obligations.md` become mechanism here, over the
pinned resolution `harness/chain/loader.py` already provides.

D2, the verdict channel is a pinned advance script's exit code and nothing else: 0 pass, 1 fail,
2 could-not-run, and every other observation reads could-not-run rather than as a fact about the
story. A predicate whose native contract differs is adapted HERE, never interpreted by whatever
drives the loop.

D3, the ref is written only by this script and only as its last act: the ref goes in and only
then does the script exit 0, and a failed write forces a nonzero exit. So the two advancement
facts, the ref as position and the exit code as the verdict, cannot diverge by this script's own
act. A failed write exits 2 rather than 1, because nothing was recorded and a recording failure
is not a fact about the story.

D6, the seam precondition is mechanical: `git status --porcelain` empty in the graded tree, read
before the examiner runs. Under ADR-0004/D2 phase worktrees are created by the sequencer OUTSIDE
the parent, so plain porcelain-empty is the whole rule; the harness's own placement inside
`.claude/worktrees/` is measured non-excluded at 2.1.224 and reads dirty here, which is that
record's arm landing rather than a gap.

THE ORDER IS ITSELF THE DESIGN, because each step is what makes the next one meaningful:

    the ref components are well-formed        else nothing is touched at all
    the repository is a working tree          else there is nothing to grade
    porcelain is empty                        ADR-0003/D6, before the examiner runs
    the graded sha resolves, and matches      the caller's --tree-ref declaration, if given
    the contract is readable                  before anything is demonstrated
    the postcondition demonstrates            through the loader, ADR-0001/D3 and D4
    the postcondition runs on the tree        the seam run, one native exit code
    the native code maps to a verdict         the adaptation, an unmapped code being void
    the graded sha still resolves the same    ADR-0002/D3.7's pinning, read at this seam
    the ref is written and read back          and only then exit 0

THE CONTRACT FILE, optional, in the postcondition's own pinned directory beside `run`:

    <pinned_root>/postconditions/<name>/contract

One mapping per line, `<native-exit-code> <verdict>`, with `#` comments and blank lines ignored;
the verdicts are `pass`, `fail` and `could-not-run`. Absent, the identity map applies: 0 pass,
1 fail, 2 could-not-run. A native code the file does not map is could-not-run naming the code,
which is the fail-closed reading and the one that keeps a new code from silently signing. The
worked example is the design's §5 red-proof, whose exit 0 means the new test went red and whose
exit 2 means it stayed green, a genuine fail:

    0 pass
    2 fail

The adaptation reaches the demonstration as well as the seam run, and that is deliberate: read
in native codes, red-proof's own known-bad fixture exits 2 and the loader would call the examiner
broken, and a demonstration in codes the seam will never use would not be evidence about the seam.

WHAT THIS DOES NOT CHECK, stated so it is not mistaken for checked. The porcelain read is taken
once, before the seam run, and is not repeated after it: a postcondition that dirties the tree it
grades is not caught here, only one that moves the graded sha is (the re-verification before the
write). The judged tree is the working tree at `--repo` rather than a fresh checkout of the sha,
so `--tree-ref` is a DECLARATION the seam refuses to proceed against when it disagrees with HEAD,
not an instruction to grade some other commit. And nothing here closes the forged-ref residue
ADR-0001 discloses: an agent holding Bash can write the same ref this script writes, and the only
thing standing against that is the containment posture, still owed.

Usage:
    python3 harness/chain/advance.py --repo <graded> --story <id> --attempt <n> --phase <n>
        --postcondition <name> [--profile-root <repo>] [--tree-ref <ref>] [--timeout <seconds>]

`--profile-root` is the repository whose `.claude/chain/profile.toml` declares the pinned root,
and it defaults to the repository holding this file rather than to `--repo`: the party that grades
declares where the examiner comes from, since a judged tree naming its own examiner root is the
defect ADR-0001/D3 exists to close.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import loader  # noqa: E402  (resolved from this file's own directory, beside it)

PASS = 0
FAIL = 1
COULD_NOT_RUN = 2

CONTRACT = "contract"
VERDICTS = {"pass": PASS, "fail": FAIL, "could-not-run": COULD_NOT_RUN}
IDENTITY = {PASS: PASS, FAIL: FAIL, COULD_NOT_RUN: COULD_NOT_RUN}
NAMED = {PASS: "pass", FAIL: "fail", COULD_NOT_RUN: "could-not-run"}

# A ref component that cannot leave the namespace: no separator, no leading dash or dot, no walk
# through a parent. `git update-ref` refuses a bad name too (measured, exit 128), but that refusal
# arrives after the examiner has run, and a seam that grades a tree before noticing it cannot
# record the result has spent the run to learn what its arguments already said.
COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

CouldNotRun = loader.CouldNotRun


def say(line: str) -> None:
    print(line, flush=True)


def component(kind: str, value: str) -> str:
    """One ref component, or could-not-run naming what is wrong with it."""
    if not COMPONENT.match(value or "") or ".." in value:
        raise CouldNotRun(
            f"the {kind} {value!r} is not a single ref component, so the ref it would build is "
            "not inside refs/chain/ (ADR-0001/D1)"
        )
    return value


def positive(kind: str, value: str) -> str:
    """An attempt or phase number. The re-walk rule deletes phase-{N..end}, which needs an order."""
    if not re.fullmatch(r"[1-9][0-9]*", value or ""):
        raise CouldNotRun(f"the {kind} {value!r} is not a positive integer, and the re-walk rule "
                          "of ADR-0001/D1 orders phases by number")
    return value


def phase_ref(story: str, attempt: str, phase: str) -> str:
    """ADR-0001/D1's ref, in its own namespace and never under refs/heads/."""
    return (f"refs/chain/{component('story id', story)}"
            f"/attempt-{positive('attempt', attempt)}"
            f"/phase-{positive('phase', phase)}")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git against `repo` with the caller's own git environment dropped.

    `loader.child_env(None)` is that scrub and is shared with the postcondition's environment on
    purpose: one definition of what a child may inherit. A seam invoked from a hook runs with
    `GIT_DIR` and `GIT_INDEX_FILE` exported, and git reads them in preference to `-C`, so the
    verdict would be computed against the caller's repository and the ref written there.
    """
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            env=loader.child_env(None),
        )
    except OSError as e:
        raise CouldNotRun(f"git could not be run against {repo}: {e}") from e


def working_tree(repo: Path) -> Path:
    """The graded repository, or could-not-run: a path that is not a working tree grades nothing."""
    if not repo.is_dir():
        raise CouldNotRun(f"the graded repository {repo} is not a directory")
    done = git(repo, "rev-parse", "--is-inside-work-tree")
    if done.returncode != 0 or done.stdout.strip() != "true":
        raise CouldNotRun(f"{repo} is not a git working tree: {done.stderr.strip()}")
    return repo


def porcelain_empty(repo: Path) -> None:
    """ADR-0003/D6's precondition, naming the dirt when it is not met."""
    done = git(repo, "status", "--porcelain")
    if done.returncode != 0:
        raise CouldNotRun(f"git status failed in {repo}: {done.stderr.strip()}")
    dirt = [line for line in done.stdout.splitlines() if line.strip()]
    if dirt:
        listed = "; ".join(dirt[:20])
        more = "" if len(dirt) <= 20 else f" (and {len(dirt) - 20} more)"
        raise CouldNotRun(
            f"the graded tree {repo} is not clean at the seam, so what the postcondition would "
            f"grade is not what any sha records: {listed}{more} (ADR-0003/D6)"
        )
    say(f"advance: porcelain empty in {repo}")


def resolve(repo: Path, ref: str) -> str:
    """The commit `ref` names, or could-not-run. Nothing downstream reads a moving name."""
    done = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    sha = done.stdout.strip()
    if done.returncode != 0 or not sha:
        raise CouldNotRun(f"{ref!r} does not resolve to a commit in {repo}")
    return sha


def read_contract(path: Path) -> dict[int, int]:
    """The postcondition's declared native-to-canonical map, or the identity map when absent."""
    if not path.is_file():
        return dict(IDENTITY)
    mapping: dict[int, int] = {}
    try:
        lines = path.read_text().splitlines()
    except OSError as e:
        raise CouldNotRun(f"the contract at {path} could not be read: {e}") from e
    for number, raw in enumerate(lines, start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 2 or not re.fullmatch(r"-?[0-9]+", fields[0]):
            raise CouldNotRun(
                f"{path}:{number}: {raw.strip()!r} is not '<native-exit-code> <verdict>'"
            )
        code, word = int(fields[0]), fields[1]
        if word not in VERDICTS:
            raise CouldNotRun(
                f"{path}:{number}: {word!r} is not one of {', '.join(sorted(VERDICTS))}"
            )
        if code in mapping:
            raise CouldNotRun(f"{path}:{number}: native code {code} is mapped twice")
        mapping[code] = VERDICTS[word]
    if not mapping:
        raise CouldNotRun(f"{path} declares no mapping, so no native code has a verdict")
    return mapping


def contract_for(root: Path, name: str) -> tuple[dict[int, int], bool]:
    """Resolve the contract from pinned material, before anything is demonstrated.

    The resolution reuses the loader's own refusals rather than re-deriving them, so a contract
    reached through a symlink out of the pinned root is refused for the reason every other piece
    of examiner material is (ADR-0001/D3).
    """
    pinned = loader.declared_pinned_root(root)
    loader.refuse_judged_root(pinned)
    path = pinned / loader.POSTCONDITIONS / name / CONTRACT
    loader.refuse_escaping_material(pinned, path)
    declared = path.is_file()
    return read_contract(path), declared


def seam_run(found: loader.Postcondition, repo: Path, timeout: int) -> tuple[int, str]:
    """The postcondition, run by the sequencer against the graded tree (ADR-0001/D2's seam)."""
    try:
        done = subprocess.run(
            [str(found.run), str(repo)],
            cwd=str(found.home),
            env=loader.child_env(found.config),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise CouldNotRun(f"{found.run} did not return within {timeout}s against {repo}") from e
    except OSError as e:
        raise CouldNotRun(f"{found.run} could not be executed against {repo}: {e}") from e
    return done.returncode, done.stdout + done.stderr


def record(repo: Path, ref: str, sha: str) -> None:
    """Write the phase ref and read it back, or could-not-run naming git's own refusal.

    The read-back is not ceremony: `update-ref` exiting 0 is a report by the tool being used, and
    the property this seam owes is that the ref EXISTS at the graded sha before exit 0 is returned.
    """
    done = git(repo, "update-ref", ref, sha)
    if done.returncode != 0:
        raise CouldNotRun(
            f"the phase ref {ref} could not be written at {sha}: "
            f"{done.stderr.strip() or done.stdout.strip()} (ADR-0003/D3: no exit 0 without the ref)"
        )
    written = git(repo, "rev-parse", "--verify", "--quiet", ref).stdout.strip()
    if written != sha:
        raise CouldNotRun(
            f"the phase ref {ref} reads {written or 'absent'} after the write, not {sha}"
        )


def advance(a: argparse.Namespace) -> int:
    """The seam itself. Returns the canonical verdict; raises CouldNotRun with the reason."""
    ref = phase_ref(a.story, a.attempt, a.phase)
    repo = working_tree(Path(a.repo).resolve())
    porcelain_empty(repo)

    sha = resolve(repo, "HEAD")
    if a.tree_ref:
        declared_sha = resolve(repo, a.tree_ref)
        if declared_sha != sha:
            raise CouldNotRun(
                f"--tree-ref {a.tree_ref} resolves to {declared_sha}, and the graded tree is at "
                f"{sha}: the seam grades the working tree, so a disagreement means the sequencer "
                "and the tree are not talking about the same commit (ADR-0002/D3.7)"
            )
    say(f"advance: graded sha {sha}, ref {ref}")

    root = Path(a.profile_root).resolve()
    mapping, declared = contract_for(root, a.postcondition)
    shape = ", ".join(f"{code}->{NAMED[v]}" for code, v in sorted(mapping.items()))
    say(f"advance: contract {'declared' if declared else 'identity (no contract file)'}: {shape}")

    found = loader.load(root, a.postcondition, timeout=a.timeout, say=say, adapt=mapping.get)

    code, transcript = seam_run(found, repo, a.timeout)
    for line in transcript.splitlines():
        say(f"advance: seam| {line}")
    verdict = mapping.get(code)
    if verdict is None:
        raise CouldNotRun(
            f"the postcondition {found.name!r} returned exit {code} against {repo}, which its "
            "contract does not map, so what it meant is not decided anywhere"
        )
    say(f"advance: seam run: exit {code} reads {NAMED[verdict]}")

    if verdict == COULD_NOT_RUN:
        raise CouldNotRun(
            f"the postcondition {found.name!r} exited {code} against {repo}, which its contract "
            "reads as could-not-run, so the seam observed no verdict"
        )
    if verdict == FAIL:
        return FAIL

    if resolve(repo, "HEAD") != sha or (a.tree_ref and resolve(repo, a.tree_ref) != sha):
        raise CouldNotRun(
            f"the graded sha {sha} no longer resolves the same after the postcondition ran, so "
            "the ref would record a commit that was never graded (ADR-0002/D3.7)"
        )
    record(repo, ref, sha)
    print(f"advance: PASS: {ref} = {sha}, recorded before exit 0")
    return PASS


def main() -> int:
    ap = argparse.ArgumentParser(description="Grade one phase seam and record its ref.")
    ap.add_argument("--repo", required=True, help="the graded repository")
    ap.add_argument("--story", required=True, help="the story id, one ref component")
    ap.add_argument("--attempt", required=True, help="the attempt number")
    ap.add_argument("--phase", required=True, help="the phase number")
    ap.add_argument("--postcondition", required=True, help="the pinned postcondition to run")
    ap.add_argument(
        "--profile-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="the repository whose chain profile declares the pinned root; the grader's own, "
             "never the graded tree",
    )
    ap.add_argument("--tree-ref", help="the sha or ref the caller believes it is grading")
    ap.add_argument("--timeout", type=int, default=loader.DEFAULT_TIMEOUT,
                    help="seconds the postcondition may take before it reads could-not-run")
    a = ap.parse_args()

    try:
        verdict = advance(a)
    except loader.DemonstrationFailed as e:
        # ADR-0001/D4 rules an undemonstrated postcondition's verdict could-not-run, and a
        # postcondition that failed its own fixtures is undemonstrated. Exit 1 here would report a
        # broken examiner as a story fail and bounce a story whose tree was never graded.
        print(f"advance: VOID: {e}; the examiner is broken, which is not a fact about the story",
              file=sys.stderr)
        return COULD_NOT_RUN
    except CouldNotRun as e:
        print(f"advance: VOID: {e}; not a pass", file=sys.stderr)
        return COULD_NOT_RUN
    except OSError as e:
        print(f"advance: VOID: a filesystem read failed at the seam: {e}", file=sys.stderr)
        return COULD_NOT_RUN
    if verdict == FAIL:
        print("advance: FAIL: the postcondition did not pass; no ref written", file=sys.stderr)
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())

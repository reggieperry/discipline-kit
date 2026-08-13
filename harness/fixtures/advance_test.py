#!/usr/bin/env python3
"""Red-first fixture for `harness/chain/advance.py` and `harness/chain/attempt.py`.

The advance script is the seam. ADR-0003/D2 makes its exit code the only verdict channel, under
one canonical contract at that boundary: 0 pass, 1 fail, 2 could-not-run, with every other code
and every broken instrument reading could-not-run rather than as a fact about the story. D3 puts
the ref write inside the same script and couples the two: the ref is written and only then does
the script exit 0, and a failed write forces a nonzero exit. D6 makes `git status --porcelain`
empty the precondition of every seam evaluation. ADR-0001/D1 gives the ref its own namespace and
makes a re-walk delete `phase-{N..end}` in one atomic batch; ADR-0004/D2 puts phase worktrees
outside the parent and clears the pinned path at every attempt start.

Each case builds throwaway repositories, runs the tool as a CLI against them, and asserts the exit
code, a marker string, AND the ref state. The exit code alone cannot tell a refusal that named the
dirt from one that could not find the postcondition, and a code without the ref state cannot see
the one coupling D3 exists to force: exit 0 with no ref, or a ref with a nonzero exit, are both
the divergence the record forbids, and both read as a plain exit code.

  pass-writes-ref-then-0     a passing seam, ref at the graded sha  -> 0, ref = sha
  fail-writes-nothing-1      the postcondition fails                -> 1, no ref
  postcondition-void-2       the loader refuses (fixture absent)    -> 2, no ref
  demonstration-failed-2     the postcondition fails its own red    -> 2, no ref
  dirty-tree-2               porcelain not empty at the seam        -> 2, no ref, no run
  worktree-outside-clean-0   a live worktree outside the parent     -> 0, ref written
  worktree-inside-parent-2   a worktree path inside the parent      -> 2, naming it
  moving-head-2              the graded ref moves during the run    -> 2, no ref
  declared-sha-mismatch-2    --tree-ref disagrees with HEAD         -> 2, no ref, no run
  failed-update-ref-2        a ref-directory collision at the write -> 2, no ref
  lying-update-ref-2         update-ref reports 0 and writes nothing -> 2, no ref
  red-proof-fail-1           native 2 under red-proof's contract    -> 1, no ref
  red-proof-pass-0           native 0 under red-proof's contract    -> 0, ref = sha
  red-proof-unmapped-2       native 1, which that contract omits    -> 2, no ref
  unknown-native-code-2      native 3 under the identity contract   -> 2, naming the code
  seam-void-2                native 2, which the identity map voids -> 2, saying so
  malformed-contract-2       a contract line that is not a mapping  -> 2, no run
  bad-ref-component-2        a story id that escapes the namespace  -> 2, no run, no ref
  not-a-repo-2               --repo names no working tree           -> 2
  hostile-git-env            GIT_DIR in the caller's environment    -> 0, ref in the right repo
  re-walk-batch              delete phase-{3..5} of one attempt     -> exactly 3,4,5, one spawn
  worktree-clear             registered-but-missing, then re-added  -> cleared, re-creatable

THE ORDERING CASES ASSERT AN ABSENCE, and that is what makes them discriminate. `dirty-tree-2`,
`declared-sha-mismatch-2`, `bad-ref-component-2` and `malformed-contract-2` all require the
postcondition's own marker to be ABSENT from the transcript: the refusal must land before the
examiner runs, not after. Without that assertion each case passes against a script that runs the
whole seam and then notices, which is a different script with the same exit code.

`failed-update-ref-2` is D3's coupling read at its own boundary. The collision is the measured one
of design §4.5 — a ref and a ref-directory cannot share a path, so planting
`refs/chain/<story>/attempt-1/phase-2/sub` makes the write of `phase-2` fail with git's "cannot
lock ref" — and the requirement is exit 2 with the failure named. Never 0, because nothing was
recorded; never 1, because a failed write is not a fact about the story.

`red-proof-*` is ADR-0003/D2's named divergent predicate. Its native contract is the design's §5:
exit 0 went red (pass), exit 2 stayed green (a genuine fail). The adaptation is declared in the
postcondition's own pinned `contract` file, so the sequencer never interprets a native code, and
it applies to the demonstration as well as to the seam run: a postcondition demonstrated in codes
the seam will not read has not demonstrated the thing the seam uses. The third limb pins the
fail-closed half — native 1 is not in red-proof's map, and an unmapped code is could-not-run.

Run: python3 harness/fixtures/advance_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

CHAIN = Path(__file__).resolve().parent.parent / "chain"
TOOL = CHAIN / "advance.py"
ATTEMPT = CHAIN / "attempt.py"

PASS_MARKER = "advance: PASS"
FAIL_MARKER = "advance: FAIL"
VOID_MARKER = "advance: VOID"
EXAMINER = "PINNED-EXAMINER"

NAME = "demo"
STORY = "STORY-0042"

# The demonstration postcondition. It reads the verdict the tree it was handed declares, so the
# fixture trees drive the exit codes and the invocation contract is observable: no tree argument
# and no verdict file both read as a broken instrument rather than as a story verdict. `native2`
# and `native3` exist for the adaptation cases, where the code the postcondition returns is not
# the verdict the seam reports.
RUN_TEMPLATE = """#!/usr/bin/env bash
set -uo pipefail
echo "{marker}"
if [ "$#" -lt 1 ]; then echo "run: no tree argument"; exit 2; fi
if [ -n "${{GIT_DIR:-}}" ]; then echo "run: GIT_DIR reached the postcondition"; exit 2; fi
{extra}
case "$(cat "$1/verdict" 2>/dev/null)" in
  fail) exit 1 ;;
  pass) exit 0 ;;
  native2) exit 2 ;;
  native3) exit 3 ;;
  *) echo "run: no verdict in $1"; exit 2 ;;
esac
"""

# A run that commits into the tree it was handed, for `moving-head-2`. The graded repository
# carries its own identity, and the redirection is tolerated because the same script runs against
# the fixture copies during the demonstration, which are not repositories.
MOVES_HEAD = """
git -C "$1" commit --allow-empty -qm "the examiner moved the head" >/dev/null 2>&1 || true
"""

RED_PROOF_CONTRACT = """# red-proof's native contract, design §5: 0 went red, 2 stayed green.
0 pass
2 fail
"""

# A git wrapper that records every invocation, for the one-batch assertion of `re-walk-batch`. The
# log path is baked in rather than passed through the environment, and that is the tool's doing: a
# `GIT_SPY_LOG` variable is dropped by the same `GIT_*` scrub the seam applies to every child, so
# the spy wrote nowhere and logged nothing while the refs were deleted correctly.
GIT_SPY = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> {log}
exec {real} "$@"
"""

# A git whose `update-ref` reports success and writes nothing, for `lying-update-ref-2`. Everything
# else passes through, so the seam reaches the write on a tree it genuinely graded.
GIT_LIAR = """#!/usr/bin/env bash
for arg in "$@"; do
  if [ "$arg" = "update-ref" ]; then exit 0; fi
done
exec {real} "$@"
"""


def clean_env() -> dict[str, str]:
    """The environment with git's own variables dropped.

    A `pre-commit` hook runs with `GIT_DIR` and `GIT_INDEX_FILE` exported and a subprocess
    inherits them, so a fixture that builds a throwaway repository writes into the REAL one
    instead. The tool under test scrubs the same variables for its own children; the
    `hostile-git-env` case is what shows that, and it deliberately does not use this helper.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=clean_env(),
    )
    return done.stdout.strip()


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main", ".")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "fixture")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "baseline", "--allow-empty")


def graded_repo(td: Path, *, verdict: str = "pass", name: str = "graded") -> Path:
    """The tree under judgement: a repository whose committed `verdict` drives the postcondition."""
    repo = td / name
    repo.mkdir(parents=True)
    (repo / "verdict").write_text(verdict + "\n")
    (repo / "README.md").write_text("the graded tree\n")
    init_repo(repo)
    return repo


def postcondition(
    root: Path,
    *,
    name: str = NAME,
    marker: str = EXAMINER,
    red: str | None = "fail",
    green: str | None = "pass",
    run_extra: str = "",
    contract: str | None = None,
) -> Path:
    """One postcondition under `<root>/postconditions/<name>/`, well-formed unless told otherwise.

    `red` and `green` are the verdicts the fixture trees declare, in the postcondition's own native
    vocabulary; `contract` is the optional native-to-canonical declaration the seam reads.
    """
    home = root / "postconditions" / name
    home.mkdir(parents=True)
    run = home / "run"
    run.write_text(RUN_TEMPLATE.format(marker=marker, extra=run_extra))
    run.chmod(0o755)
    if contract is not None:
        (home / "contract").write_text(contract)
    for limb, verdict in (("red", red), ("green", green)):
        if verdict is None:
            continue
        tree = home / "fixtures" / limb
        tree.mkdir(parents=True)
        (tree / "verdict").write_text(verdict + "\n")
    return home


def kit_tree(td: Path, pinned: Path) -> Path:
    """A repository-shaped tree carrying nothing but the chain profile the loader reads.

    This is the SEQUENCER's profile, never the graded repository's: the root the examiner resolves
    from is declared by the party doing the grading (ADR-0001/D3, ADR-0003/D4).
    """
    kit = td / "kit"
    chain = kit / ".claude" / "chain"
    chain.mkdir(parents=True)
    (chain / "profile.toml").write_text(
        'terminal = "open-pr"\npush = "branches-only"\n' f'pinned_root = "{pinned}"\n'
    )
    return kit


def pinned_root(td: Path, **kw) -> Path:
    root = td / "pinned"
    root.mkdir()
    postcondition(root, **kw)
    return root


def bench(td: Path, *, verdict: str = "pass", **kw) -> tuple[Path, Path]:
    """The standard pair: a pinned root with one postcondition, and a clean graded repository."""
    kit = kit_tree(td, pinned_root(td, **kw))
    return kit, graded_repo(td, verdict=verdict)


def run_advance(
    kit: Path,
    repo: Path,
    *,
    story: str = STORY,
    attempt: str = "1",
    phase: str = "2",
    name: str = NAME,
    extra: tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, str(TOOL),
            "--repo", str(repo),
            "--story", story,
            "--attempt", attempt,
            "--phase", phase,
            "--postcondition", name,
            "--profile-root", str(kit),
            *extra,
        ],
        capture_output=True,
        text=True,
        env=clean_env() if env is None else env,
    )


def phase_ref(story: str = STORY, attempt: str = "1", phase: str = "2") -> str:
    return f"refs/chain/{story}/attempt-{attempt}/phase-{phase}"


def ref_value(repo: Path, ref: str) -> str | None:
    """The sha a ref names, or None when it does not exist. Never an exception at the call site."""
    done = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True,
        text=True,
        env=clean_env(),
    )
    return done.stdout.strip() or None


def judge(
    name: str,
    got: subprocess.CompletedProcess[str],
    *,
    want: int,
    marker: str,
    repo: Path | None = None,
    ref: str | None = None,
    want_ref: str | None = None,
    absent: str | None = None,
) -> bool:
    """Compare exit code, marker, an optional absent marker, and the ref state.

    `want_ref` is a sha the ref must equal, or the string "none" for a ref that must not exist.
    """
    said = got.stdout + got.stderr
    ok = got.returncode == want and marker in said
    detail = ""
    if absent is not None and absent in said:
        ok = False
        detail += f" (found '{absent}', which must not have run)"
    if repo is not None and ref is not None:
        have = ref_value(repo, ref)
        if want_ref == "none":
            if have is not None:
                ok = False
                detail += f" (ref exists at {have[:8]}, and nothing was recorded)"
        elif have != want_ref:
            ok = False
            detail += f" (ref is {have}, wanted {want_ref})"
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want} naming '{marker}', "
          f"got exit {got.returncode}{detail}")
    if not ok:
        print(f"       stdout: {got.stdout.strip()[:500]}")
        print(f"       stderr: {got.stderr.strip()[:500]}")
    return ok


def pass_case() -> bool:
    """A passing seam records the ref at the sha it graded, and only then exits 0."""
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td))
        sha = git(repo, "rev-parse", "HEAD")
        got = run_advance(kit, repo)
        ok = judge("pass-writes-ref-then-0", got, want=0, marker=PASS_MARKER,
                   repo=repo, ref=phase_ref(), want_ref=sha)
        if EXAMINER not in (got.stdout + got.stderr):
            print("       the postcondition transcript is absent from the seam's output")
            ok = False
        return ok


def fail_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td), verdict="fail")
        return judge("fail-writes-nothing-1", run_advance(kit, repo), want=1, marker=FAIL_MARKER,
                     repo=repo, ref=phase_ref(), want_ref="none")


def void_case() -> bool:
    """The loader refuses the postcondition: could-not-run, and nothing is recorded."""
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td), red=None)
        return judge("postcondition-void-2", run_advance(kit, repo), want=2, marker=VOID_MARKER,
                     repo=repo, ref=phase_ref(), want_ref="none")


def demonstration_failed_case() -> bool:
    """A postcondition that passes its own known-bad fixture has no detection power.

    ADR-0001/D4 rules an undemonstrated postcondition's verdict could-not-run, and that is what
    this asserts: the loader calls it a demonstration failure, which is a fact about the examiner,
    and a fact about the examiner is not a fact about the story (ADR-0003/D2).
    """
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td), red="pass")
        return judge("demonstration-failed-2", run_advance(kit, repo), want=2, marker=VOID_MARKER,
                     repo=repo, ref=phase_ref(), want_ref="none")


def dirty_case() -> bool:
    """ADR-0003/D6: porcelain empty at the seam, checked before the examiner runs."""
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td))
        (repo / "uncommitted.txt").write_text("work in progress\n")
        return judge("dirty-tree-2", run_advance(kit, repo), want=2, marker="uncommitted.txt",
                     repo=repo, ref=phase_ref(), want_ref="none", absent=EXAMINER)


def worktree_outside_case() -> bool:
    """ADR-0004/D2's arm: a sequencer worktree lives outside the parent, so porcelain stays empty.

    The story's criterion is that a parent holding a LIVE phase worktree still reads porcelain
    empty at the seam. The worktree is created here as the sequencer would create it, at a path
    outside the parent repository, and the seam must pass with it registered and materialized.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit, repo = bench(tmp)
        git(repo, "worktree", "add", "-q", "-b", "phase-tester", str(tmp / "wt"))
        live = (tmp / "wt" / "verdict").is_file()
        sha = git(repo, "rev-parse", "HEAD")
        ok = judge("worktree-outside-clean-0", run_advance(kit, repo), want=0, marker=PASS_MARKER,
                   repo=repo, ref=phase_ref(), want_ref=sha)
        if not live:
            print("       the worktree was not materialized, so the case was not constructed")
            ok = False
        return ok


def worktree_inside_case() -> bool:
    """The harness's own placement, measured non-excluded, is the shape D2 rejects.

    `.claude/worktrees/` inside the parent shows in the parent's porcelain at 2.1.224, so a seam
    evaluated there reads could-not-run. This is the contrast that gives the case above its
    meaning: the seam is not blind to worktrees, it is blind to worktrees placed outside.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit, repo = bench(tmp)
        settings = repo / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{}\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "the project settings root")
        inside = repo / ".claude" / "worktrees" / "tester"
        inside.mkdir(parents=True)
        (inside / "marker").write_text("a phase worktree inside the parent\n")
        return judge("worktree-inside-parent-2", run_advance(kit, repo), want=2,
                     marker=".claude/worktrees", repo=repo, ref=phase_ref(), want_ref="none")


def moving_head_case() -> bool:
    """The graded sha is pinned at entry and re-verified before the write.

    ADR-0002/D3.7 fails a head that moved between evaluation and merge; the same rule at this seam
    is that a ref recording a sha the postcondition did not grade is a false record. The examiner
    itself moves the head here, which is the shape that needs no race to reproduce.
    """
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td), run_extra=MOVES_HEAD)
        before = git(repo, "rev-parse", "HEAD")
        got = run_advance(kit, repo)
        after = git(repo, "rev-parse", "HEAD")
        ok = judge("moving-head-2", got, want=2, marker=VOID_MARKER,
                   repo=repo, ref=phase_ref(), want_ref="none")
        if before == after:
            print("       the head did not move, so the case was not constructed")
            ok = False
        return ok


def declared_sha_case() -> bool:
    """`--tree-ref` is the sequencer's declaration of what it believes it is grading."""
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td))
        first = git(repo, "rev-parse", "HEAD")
        (repo / "later.txt").write_text("a second commit\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "second")
        return judge("declared-sha-mismatch-2", run_advance(kit, repo, extra=("--tree-ref", first)),
                     want=2, marker=VOID_MARKER, repo=repo, ref=phase_ref(), want_ref="none",
                     absent=EXAMINER)


def failed_write_case() -> bool:
    """A ref-directory collision at the write: exit 2 naming it, never 0 and never 1."""
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td))
        sha = git(repo, "rev-parse", "HEAD")
        git(repo, "update-ref", phase_ref() + "/sub", sha)
        got = run_advance(kit, repo)
        ok = judge("failed-update-ref-2", got, want=2, marker="cannot lock ref",
                   repo=repo, ref=phase_ref(), want_ref="none")
        if EXAMINER not in (got.stdout + got.stderr):
            print("       the postcondition never ran, so the write was not what failed")
            ok = False
        return ok


def red_proof_cases() -> list[bool]:
    """ADR-0003/D2's divergent predicate, adapted inside the advance script and nowhere else."""
    out = []
    for label, verdict, want, marker, want_ref in (
        ("red-proof-fail-1", "native2", 1, FAIL_MARKER, "none"),
        ("red-proof-pass-0", "pass", 0, PASS_MARKER, "sha"),
        ("red-proof-unmapped-2", "fail", 2, VOID_MARKER, "none"),
    ):
        with tempfile.TemporaryDirectory() as td:
            kit, repo = bench(Path(td), verdict=verdict, red="native2", green="pass",
                              contract=RED_PROOF_CONTRACT)
            sha = git(repo, "rev-parse", "HEAD")
            out.append(judge(label, run_advance(kit, repo), want=want, marker=marker,
                             repo=repo, ref=phase_ref(),
                             want_ref=sha if want_ref == "sha" else "none"))
    return out


def unknown_code_case() -> bool:
    """An unmapped native code is a broken instrument, not a verdict (ADR-0003/D2)."""
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td), verdict="native3")
        return judge("unknown-native-code-2", run_advance(kit, repo), want=2, marker="exit 3",
                     repo=repo, ref=phase_ref(), want_ref="none")


def seam_void_case() -> bool:
    """A native code the contract READS as could-not-run still owes the operator a reason line.

    The identity map sends 2 to could-not-run, and a seam that returned that code while saying
    nothing would be a verdict with no account of itself: exit 2 and silence is what a killed
    process looks like. Measured before this case existed, the refusal path printed nothing.
    """
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td), verdict="native2")
        return judge("seam-void-2", run_advance(kit, repo), want=2, marker=VOID_MARKER,
                     repo=repo, ref=phase_ref(), want_ref="none")


def malformed_contract_case() -> bool:
    """A contract the seam cannot read is could-not-run, refused before the examiner runs."""
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td), contract="0 pass\nwhatever the author meant\n")
        return judge("malformed-contract-2", run_advance(kit, repo), want=2, marker=VOID_MARKER,
                     repo=repo, ref=phase_ref(), want_ref="none", absent=EXAMINER)


def bad_component_case() -> bool:
    """A story id that walks out of the namespace is refused before anything runs.

    git refuses the bad ref name itself, so the exit code alone does not discriminate: what does
    is that the examiner never ran and that no ref appeared anywhere outside `refs/chain/`.
    """
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td))
        got = run_advance(kit, repo, story="S/../../heads")
        ok = judge("bad-ref-component-2", got, want=2, marker=VOID_MARKER, absent=EXAMINER)
        strays = git(repo, "for-each-ref", "--format=%(refname)", "refs/heads/")
        if strays != "refs/heads/main":
            print(f"       refs/heads/ holds {strays!r}, so something escaped the namespace")
            ok = False
        return ok


def not_a_repo_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit, _ = bench(tmp)
        bare = tmp / "not-a-repo"
        bare.mkdir()
        return judge("not-a-repo-2", run_advance(kit, bare), want=2, marker=VOID_MARKER)


def hostile_env_case() -> bool:
    """The seam must not hand its caller's git environment to git or to the postcondition.

    Every other case scrubs `GIT_*` before invoking the tool, which isolates the fixture and is the
    wrong coverage on its own: the suite cannot then see whether the TOOL scrubs. Here `GIT_DIR`
    and `GIT_INDEX_FILE` name a decoy repository exactly as a pre-commit hook or a phase seam would
    export them. The postcondition exits 2 if either reaches it, and the ref must land in the
    graded repository rather than in the decoy.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit, repo = bench(tmp)
        decoy = graded_repo(tmp, name="decoy")
        sha = git(repo, "rev-parse", "HEAD")
        env = clean_env()
        env["GIT_DIR"] = str(decoy / ".git")
        env["GIT_INDEX_FILE"] = str(decoy / ".git" / "index")
        ok = judge("hostile-git-env", run_advance(kit, repo, env=env), want=0, marker=PASS_MARKER,
                   repo=repo, ref=phase_ref(), want_ref=sha)
        if ref_value(decoy, phase_ref()) is not None:
            print("       the decoy repository holds the phase ref, so the seam judged the wrong tree")
            ok = False
        return ok


def real_git() -> str:
    return subprocess.run(["bash", "-c", "command -v git"], capture_output=True, text=True,
                          env=clean_env()).stdout.strip()


def shim(td: Path, body: str, **kw) -> Path:
    """A directory holding a `git` wrapper, first on PATH for the tool under test."""
    bindir = td / "shim-bin"
    bindir.mkdir()
    wrapper = bindir / "git"
    wrapper.write_text(body.format(real=real_git(), **kw))
    wrapper.chmod(0o755)
    return bindir


def spy_path(td: Path) -> tuple[Path, Path]:
    """A directory holding a `git` wrapper that logs every invocation, and the log it writes."""
    log = td / "git-invocations.log"
    return shim(td, GIT_SPY, log=log), log


def lying_write_case() -> bool:
    """`update-ref` exiting 0 is a report by the tool being used, and D3 owes the ref itself.

    The seam reads the ref back after writing it, and this is the case that makes that read
    discriminate: a `git` whose `update-ref` reports success and writes nothing leaves the seam
    with an exit code that says recorded and a namespace that holds nothing. Exit 2, because
    nothing was recorded and a recording failure is not a fact about the story.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit, repo = bench(tmp)
        env = clean_env()
        env["PATH"] = f"{shim(tmp, GIT_LIAR)}{os.pathsep}{env['PATH']}"
        return judge("lying-update-ref-2", run_advance(kit, repo, env=env), want=2,
                     marker=VOID_MARKER, repo=repo, ref=phase_ref(), want_ref="none")


def rewalk_case() -> bool:
    """ADR-0001/D1's re-walk: `phase-{N..end}` of the current attempt, deleted in ONE batch.

    The batch is the decision, not an optimization: a per-ref loop that dies halfway leaves derived
    position disagreeing with the rule that a bounce invalidates everything downstream. So the
    invocation count is asserted, through a `git` wrapper on PATH that logs what it was called
    with. Refs of another attempt and of another story are planted to pin the selection.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = graded_repo(tmp)
        sha = git(repo, "rev-parse", "HEAD")
        for phase in ("2", "3", "4", "5"):
            git(repo, "update-ref", phase_ref(phase=phase), sha)
        git(repo, "update-ref", phase_ref(attempt="2", phase="4"), sha)
        git(repo, "update-ref", phase_ref(story="STORY-0099", phase="4"), sha)

        bindir, log = spy_path(tmp)
        env = clean_env()
        env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
        got = subprocess.run(
            [sys.executable, str(ATTEMPT), "rewalk", "--repo", str(repo), "--story", STORY,
             "--attempt", "1", "--from-phase", "3"],
            capture_output=True, text=True, env=env,
        )

        survived = [p for p in ("2", "3", "4", "5") if ref_value(repo, phase_ref(phase=p))]
        others = [
            ref_value(repo, phase_ref(attempt="2", phase="4")),
            ref_value(repo, phase_ref(story="STORY-0099", phase="4")),
        ]
        logged = log.read_text().splitlines() if log.is_file() else []
        spawns = [line for line in logged if "update-ref" in line]
        ok = (
            got.returncode == 0
            and survived == ["2"]
            and all(v == sha for v in others)
            and len(spawns) == 1
        )
        print(f"  {'ok  ' if ok else 'FAIL'} re-walk-batch: want exit 0, only phase-2 surviving, "
              f"other attempts and stories untouched, and exactly one update-ref spawn; got exit "
              f"{got.returncode}, survivors {survived}, {len(spawns)} spawn(s)")
        if not ok:
            print(f"       spawns: {spawns}")
            print(f"       stdout: {got.stdout.strip()[:400]}")
            print(f"       stderr: {got.stderr.strip()[:400]}")
        return ok


def worktree_clear_case() -> bool:
    """ADR-0004/D2: every attempt start clears the pinned worktree path, registration included.

    The measured failure this closes is a worktree whose directory is gone while git still holds
    the registration: `git worktree add` at that path then refuses, and a retry cannot start. The
    case is only constructed if the re-add fails BEFORE the clear, so the fixture checks that too
    rather than assuming it.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = graded_repo(tmp)
        wt = tmp / "phase-worktree"
        git(repo, "worktree", "add", "-q", "-b", "phase-tester", str(wt))
        subprocess.run(["rm", "-rf", str(wt)], check=True)
        blocked = subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "phase-tester"],
            capture_output=True, text=True, env=clean_env(),
        )
        got = subprocess.run(
            [sys.executable, str(ATTEMPT), "clear-worktree", "--repo", str(repo), "--path", str(wt)],
            capture_output=True, text=True, env=clean_env(),
        )
        readded = subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "phase-tester"],
            capture_output=True, text=True, env=clean_env(),
        )
        ok = got.returncode == 0 and readded.returncode == 0 and blocked.returncode != 0
        print(f"  {'ok  ' if ok else 'FAIL'} worktree-clear: want the stale registration blocking "
              f"a re-add first, the clear exiting 0, and the re-add then succeeding; got "
              f"blocked {blocked.returncode}, clear {got.returncode}, re-add {readded.returncode}")
        if not ok:
            print(f"       clear stdout: {got.stdout.strip()[:400]}")
            print(f"       clear stderr: {got.stderr.strip()[:400]}")
            print(f"       re-add stderr: {readded.stderr.strip()[:400]}")
        return ok


def main() -> int:
    missing = [str(p) for p in (TOOL, ATTEMPT) if not p.is_file()]
    if missing:
        print(f"advance_test: tool not found at {', '.join(missing)}", file=sys.stderr)
        return 2
    results = [
        pass_case(),
        fail_case(),
        void_case(),
        demonstration_failed_case(),
        dirty_case(),
        worktree_outside_case(),
        worktree_inside_case(),
        moving_head_case(),
        declared_sha_case(),
        failed_write_case(),
        lying_write_case(),
        *red_proof_cases(),
        unknown_code_case(),
        seam_void_case(),
        malformed_contract_case(),
        bad_component_case(),
        not_a_repo_case(),
        hostile_env_case(),
        rewalk_case(),
        worktree_clear_case(),
    ]
    failed = results.count(False)
    print(f"advance_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

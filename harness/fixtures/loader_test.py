#!/usr/bin/env python3
"""Red-first fixture for `harness/chain/loader.py`.

The loader is where two of ADR-0001's decisions become mechanism. D3 says the examiner never
comes from the judged tree: postconditions, the checks they call, their configuration and their
fixtures resolve from a pinned copy outside any working tree. D4 says no postcondition's verdict
counts before it has demonstrated red and green, because a predicate that always fails and a
working fence are indistinguishable from outside.

Each case builds throwaway trees, runs the loader as a CLI against them, and asserts BOTH the
exit code and a marker string. The exit code alone cannot tell a refusal that named the missing
fixture from one that could not find the pinned root at all, and those send the operator to two
different remedies. The three verdicts are the canonical contract of ADR-0003/D2, read here for
the loader's own act rather than for a story: 0 loadable, 1 the demonstration failed, 2
could-not-run.

  loadable              a well-formed postcondition demonstrates    -> 0, loadable
  config-exported       `config/` reaches the run through the env   -> 0, loadable
  relative-resolution   a relative read reaches the pinned home     -> 0, loadable
  fixture-is-a-repo     a fixture tree that is itself a repository  -> 0, loadable
  root-symlink-legitimate a symlinked root outside worktrees   -> 0, loadable
  fixtures-not-mutated  a run that writes cannot poison the pinned  -> 0, digests equal
  hostile-git-env       GIT_DIR in the caller's environment         -> 0, loadable
  root-symlink-escape   pinned_root symlinked into a worktree       -> 2, VOID (D3)
  material-symlink-escape postconditions/ symlinked into one        -> 2, VOID (D3)
  unreadable-ancestor   a directory above the root at mode 000      -> 2, VOID
  missing-red-fixtures  no fixtures/red directory                   -> 2, VOID naming both
  missing-green-fixtures no fixtures/green directory                -> 2, VOID naming both
  red-passes            the fixture that should fail did not        -> 1, FAIL
  green-fails           the fixture that should pass did not        -> 1, FAIL
  demonstration-exit-2  a limb exits outside the 0/1 contract       -> 2, VOID naming the code
  demonstration-timeout a run that never returns                    -> 2, VOID
  run-not-executable    `run` present, execute bit absent           -> 2, VOID
  run-absent            no `run` at all                             -> 2, VOID
  postcondition-absent  no directory of that name under the root    -> 2, VOID
  pinned-root-unset     the profile declares no pinned_root         -> 2, VOID
  pinned-root-nested    pinned_root declared in a nested table      -> 2, VOID
  pinned-root-relative  a relative pinned_root                      -> 2, VOID
  pinned-root-absent    an absolute pinned_root naming nothing      -> 2, VOID
  pinned-root-in-worktree the root sits inside a git working tree   -> 2, VOID (D3)
  no-profile            no chain profile at all                     -> 2, VOID
  unparseable-profile   a profile that is not valid TOML            -> 2, VOID
  judged-tree-shadow    the examiner-pinning test, both limbs       -> see below

JUDGED-TREE-SHADOW IS ADR-0001/D3'S NAMED COURT, and it is the one case here that is about a
verdict rather than about a refusal. Its falsification condition is "a verdict that changes when
only the judged tree's own scripts change", so the case changes only that and requires the
verdict to stay put: a judged git repository carries `postconditions/demo/run` under the same
name as the pinned one, well-formed and printing a different marker, and the loader runs with
that repository as its working directory. The pinned marker must appear, the shadow marker must
not, and a second run against a further-mutated shadow must return the identical exit code. The
converse limb points `pinned_root` at the judged tree's own copy: resolution from inside a
working tree is refused outright, which is why the first limb cannot be defeated by moving the
shadow somewhere the loader would look.

THE TWO SYMLINK CASES ARE THE SAME COURT AS `pinned-root-in-worktree` READ AT THE RIGHT WIDTH,
and both shapes were measured loadable before they existed. A path check that walks lexically from
the declared root sees the names in the string and not the directories they reach: a `pinned_root`
symlinked into a subdirectory of a judged repository never brings that repository's root into the
walk, and a clean root whose `postconditions/` is a symlink into one never has it examined at all.
The remedy is to resolve before deciding, and to require every resolved material path to sit under
the resolved root. `fixture-is-a-repo` is what keeps that remedy from over-reaching: a fixture tree
is the SUBJECT of a postcondition, and a postcondition over a tree's porcelain needs a fixture that
is a git repository, so a rule refusing material with a repository at or under it would refuse the
one shape D4 most needs. Containment refuses the escape without refusing the subject.

`unreadable-ancestor` is the inversion ADR-0003/D2 forbids. A `PermissionError` while inspecting
the path escaped as a traceback, and an uncaught Python exception exits 1, so a broken instrument
was reported as a demonstration failure. It was measured firing at the `is_dir()` probe rather
than inside the walk, which is why the guard is a net around every filesystem read on the
resolution path and not a wrapper on one loop.

THE TWO MISSING-FIXTURE CASES ASSERT THE STATE AND NOT ONLY THE EXIT CODE, and the difference is
measured rather than stylistic: with the both-fixtures requirement deleted, the loader runs the
postcondition against a directory that does not exist, the run cannot find its verdict file and
exits 2, and could-not-run comes back with the postcondition's name in it. Exit 2 naming `demo`
therefore survives the mutation; exit 2 naming "'demo' has no red fixture" does not.

THE INVOCATION CONTRACT IS PINNED BY THE FIXTURE TREES THEMSELVES, not by an assertion about
argv. Every demonstration script reads `$1/verdict` to decide its exit code, so a loader that
passes the wrong tree, or no tree, cannot produce the expected codes for both limbs; and the
scripts exit 2 when `GIT_DIR` reaches them, so the environment scrub is observable rather than
asserted. That is deliberate: the four defects this repository has paid for in this class were
all a git environment inherited by a subprocess that then judged the wrong repository.

Run: python3 harness/fixtures/loader_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "chain" / "loader.py"

LOADABLE_MARKER = "postcondition-loader: loadable"
VOID_MARKER = "postcondition-loader: VOID"
FAIL_MARKER = "postcondition-loader: FAIL"

NAME = "demo"

# The demonstration postcondition. It reads the verdict the tree it was pointed at declares, so
# the fixture trees drive the exit codes and the invocation contract is observable: no tree
# argument and no verdict file both read as a broken instrument rather than as a story verdict.
RUN_TEMPLATE = """#!/usr/bin/env bash
set -uo pipefail
echo "{marker}"
if [ "$#" -lt 1 ]; then echo "run: no tree argument"; exit 2; fi
if [ -n "${{GIT_DIR:-}}" ]; then echo "run: GIT_DIR reached the postcondition"; exit 2; fi
{extra}
case "$(cat "$1/verdict" 2>/dev/null)" in
  fail) exit 1 ;;
  pass) exit 0 ;;
  *) echo "run: no verdict in $1"; exit 2 ;;
esac
"""

# A run that never returns, for the timeout limb.
RUN_HANGS = """#!/usr/bin/env bash
echo "PINNED-EXAMINER"
sleep 30
"""

# The config check, used only by `config-exported`: the postcondition's own configuration is
# pinned material too (ADR-0001/D3), so the loader hands it over rather than leaving the run to
# find it relative to whatever tree it is judging.
CONFIG_EXTRA = """
if [ ! -f "${CHAIN_POSTCONDITION_CONFIG:-/nonexistent}/threshold" ]; then
  echo "run: no pinned config"; exit 2
fi
"""

# A RELATIVE read, used only by `relative-resolution`. The file it names exists under the
# postcondition's pinned home and nowhere else, so the case fails unless the working directory the
# loader hands the run is that home. Without it the confinement is a claim in a docstring: a
# mutant setting the working directory to the judged tree left every other case green.
RELATIVE_EXTRA = """
if [ ! -f pinned-marker ]; then echo "run: a relative read missed the pinned home"; exit 2; fi
cat pinned-marker
"""

# A run that WRITES into the tree it was handed, for `fixtures-not-mutated`.
POISON_EXTRA = """
: > "$1/poison"
"""


def clean_env() -> dict[str, str]:
    """The environment with git's own variables dropped.

    A `pre-commit` hook runs with `GIT_DIR` and `GIT_INDEX_FILE` exported and a subprocess
    inherits them, so a fixture that builds a throwaway repository writes into the REAL one
    instead. The tool under test scrubs the same variables for its own children; the
    `hostile-git-env` case is what shows that, and it deliberately does not use this helper.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=clean_env(),
    )


def write_run(path: Path, *, marker: str = "PINNED-EXAMINER", body: str | None = None,
              extra: str = "", executable: bool = True) -> None:
    path.write_text(body if body is not None else RUN_TEMPLATE.format(marker=marker, extra=extra))
    path.chmod(0o755 if executable else 0o644)


def postcondition(
    root: Path,
    *,
    name: str = NAME,
    marker: str = "PINNED-EXAMINER",
    red: str | None = "fail",
    green: str | None = "pass",
    run_body: str | None = None,
    run_extra: str = "",
    run_executable: bool = True,
    run_present: bool = True,
    config: bool = False,
    home_files: dict[str, str] | None = None,
    fixtures_are_repos: bool = False,
) -> Path:
    """One postcondition under `<root>/postconditions/<name>/`, well-formed unless told otherwise.

    `red` and `green` are the verdicts their fixture trees declare, so `red="pass"` is the
    postcondition without detection power and `green="fail"` the one that fails its own
    known-good tree. `None` omits the fixture directory entirely.
    """
    home = root / "postconditions" / name
    home.mkdir(parents=True)
    if run_present:
        write_run(home / "run", marker=marker, body=run_body, extra=run_extra,
                  executable=run_executable)
    if config:
        (home / "config").mkdir()
        (home / "config" / "threshold").write_text("1\n")
    for rel, body in (home_files or {}).items():
        (home / rel).write_text(body)
    for limb, verdict in (("red", red), ("green", green)):
        if verdict is None:
            continue
        tree = home / "fixtures" / limb
        tree.mkdir(parents=True)
        (tree / "verdict").write_text(verdict + "\n")
        if fixtures_are_repos:
            init_repo(tree)
    return home


def init_repo(path: Path) -> None:
    """Make `path` a git repository with one commit."""
    git(path, "init", "-q", "-b", "main", ".")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "fixture")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "baseline")


def tree_digest(root: Path) -> str:
    """A digest over every path and file body under `root`, for the poisoning case."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        h.update(p.relative_to(root).as_posix().encode())
        if p.is_file() and not p.is_symlink():
            h.update(p.read_bytes())
    return h.hexdigest()


def kit_tree(root: Path, *, pinned: str | None, nested: bool = False,
             raw_profile: str | None = None, profile: bool = True) -> Path:
    """A repository-shaped tree carrying nothing but the chain profile the loader reads."""
    kit = root / "kit"
    kit.mkdir(parents=True)
    if not profile:
        return kit
    chain = kit / ".claude" / "chain"
    chain.mkdir(parents=True)
    if raw_profile is not None:
        body = raw_profile
    else:
        head = 'terminal = "open-pr"\npush = "branches-only"\n'
        if pinned is None:
            body = head
        elif nested:
            body = head + f'\n[sequencer]\npinned_root = "{pinned}"\n'
        else:
            body = head + f'pinned_root = "{pinned}"\n'
    (chain / "profile.toml").write_text(body)
    return kit


def run_tool(kit: Path, *, name: str = NAME, cwd: Path | None = None,
             env: dict[str, str] | None = None,
             extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), name, "--root", str(kit), *extra],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=clean_env() if env is None else env,
    )


def report(name: str, want: int, marker: str, got: subprocess.CompletedProcess[str]) -> bool:
    said = got.stdout + got.stderr
    ok = got.returncode == want and marker in said
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want} naming '{marker}', "
          f"got exit {got.returncode}")
    if not ok:
        print(f"       stdout: {got.stdout.strip()[:400]}")
        print(f"       stderr: {got.stderr.strip()[:400]}")
    return ok


def case(name: str, want: int, marker: str, build, **kw) -> bool:
    """Build a pinned root and a kit tree via `build`, run the loader, compare code and marker."""
    with tempfile.TemporaryDirectory() as td:
        kit = build(Path(td))
        return report(name, want, marker, run_tool(kit, **kw))


def pinned_root(td: Path, **kw) -> Path:
    """A pinned root outside every git working tree, holding one postcondition."""
    root = td / "pinned"
    root.mkdir()
    postcondition(root, **kw)
    return root


def standard(td: Path, **kw) -> Path:
    return kit_tree(td, pinned=str(pinned_root(td, **kw)))


def judged_repo(td: Path, *, marker: str = "SHADOW-EXAMINER", name: str = "judged",
                at: str | None = None) -> Path:
    """A git working tree carrying its own copy of the same-named postcondition.

    Well-formed on purpose: a shadow that could not demonstrate would be refused for that
    reason instead of for being in the judged tree, and the case would pass for the wrong
    reason. `at` puts the material in a subdirectory, which is what the root-symlink case needs.
    """
    repo = td / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main", ".")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "fixture")
    postcondition(repo / at if at else repo, marker=marker)
    (repo / "README.md").write_text("the judged tree\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "baseline")
    return repo


def build_loadable(td: Path) -> Path:
    return standard(td)


def build_config(td: Path) -> Path:
    return standard(td, config=True, run_extra=CONFIG_EXTRA)


def build_missing_red(td: Path) -> Path:
    return standard(td, red=None)


def build_missing_green(td: Path) -> Path:
    return standard(td, green=None)


def build_red_passes(td: Path) -> Path:
    """The known-bad fixture the postcondition does not fail: detection power absent."""
    return standard(td, red="pass")


def build_green_fails(td: Path) -> Path:
    """The known-good fixture the postcondition does not pass: the always-fails fence of D4."""
    return standard(td, green="fail")


def build_exit_two(td: Path) -> Path:
    """A limb outside the 0/1 contract. A broken instrument is not a fact about the story."""
    return standard(td, red="confused")


def build_hangs(td: Path) -> Path:
    return standard(td, run_body=RUN_HANGS)


def build_not_executable(td: Path) -> Path:
    return standard(td, run_executable=False)


def build_run_absent(td: Path) -> Path:
    return standard(td, run_present=False)


def build_postcondition_absent(td: Path) -> Path:
    return standard(td, name="other")


def build_pinned_unset(td: Path) -> Path:
    pinned_root(td)
    return kit_tree(td, pinned=None)


def build_pinned_nested(td: Path) -> Path:
    """The schema puts every key at top level. A nested declaration is not read, and reading it
    as unset is the fail-closed answer; naming it is what keeps the remedy findable."""
    return kit_tree(td, pinned=str(pinned_root(td)), nested=True)


def build_pinned_relative(td: Path) -> Path:
    pinned_root(td)
    return kit_tree(td, pinned="pinned")


def build_pinned_absent(td: Path) -> Path:
    return kit_tree(td, pinned=str(td / "nowhere"))


def build_pinned_in_worktree(td: Path) -> Path:
    """ADR-0001/D3 mechanically: material inside a working tree is not pinned material, whatever
    its path says. The root here is a subdirectory of a real repository."""
    repo = judged_repo(td, name="host")
    return kit_tree(td, pinned=str(repo))


def build_relative_resolution(td: Path) -> Path:
    """A run reading a relative path that exists only under its own pinned home."""
    return standard(td, run_extra=RELATIVE_EXTRA,
                    home_files={"pinned-marker": "PINNED-HOME-REACHED\n"})


def build_fixture_is_a_repo(td: Path) -> Path:
    """Fixture trees that are themselves git repositories, which is the shape a postcondition
    over a tree's porcelain requires. Containment must admit it where an up-walk would not."""
    return standard(td, fixtures_are_repos=True)


def build_root_symlink_legitimate(td: Path) -> Path:
    """A pinned root that is a symlink to a real directory outside every working tree.

    The deployment shape this is: a stable `/var/lib/discipline-chain` pointing at a versioned
    release directory, swapped atomically. It must LOAD, and the case exists because nothing
    else here requires it to: with the root's resolution removed the suite stayed 26 of 26 while
    every material path resolved out from under an unresolved prefix and this shape was refused.
    A machine whose temporary directory is itself a symlink meets the same refusal for the same
    reason, which is the general form of the defect.
    """
    real = pinned_root(td)
    link = td / "current"
    link.symlink_to(real)
    return kit_tree(td, pinned=str(link))


def build_root_symlink_escape(td: Path) -> Path:
    """`pinned_root` is a symlink into a SUBDIRECTORY of a judged repository.

    The subdirectory matters. A symlink naming the repository's own root is already refused,
    because the first probe of the walk resolves through the link and meets `.git` there; a
    symlink one level down never brings the repository's root into a lexical walk at all. That
    second shape was measured loadable, with the judged tree's examiner running.
    """
    judged = judged_repo(td, at="chain")
    link = td / "link"
    link.symlink_to(judged / "chain")
    return kit_tree(td, pinned=str(link))


def build_material_symlink_escape(td: Path) -> Path:
    """A pinned root outside every worktree whose `postconditions/` is a symlink into one.

    Nothing about the root is wrong, so a check that only examines the root reports nothing;
    every path below it reaches the judged tree. Measured loadable, shadow examiner running.
    """
    judged = judged_repo(td)
    clean = td / "pinned"
    clean.mkdir()
    (clean / "postconditions").symlink_to(judged / "postconditions")
    return kit_tree(td, pinned=str(clean))


def build_no_profile(td: Path) -> Path:
    pinned_root(td)
    return kit_tree(td, pinned=None, profile=False)


def build_unparseable(td: Path) -> Path:
    return kit_tree(td, pinned=None, raw_profile='terminal = "open-pr\npinned_root = [\n')


def shadow_case() -> bool:
    """The examiner-pinning test of ADR-0001/D3's Falsification section.

    Limb one: the verdict does not change when only the judged tree's copy changes. The loader
    runs with the judged repository as its working directory, that repository holds a same-named
    postcondition, and the pinned one must be the one that ran; then the shadow is changed again
    and the exit code must be identical. Limb two: pointing the pinned root at the judged tree's
    own copy is refused, so the shadow cannot be reached by relocating it either.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit = standard(tmp)
        judged = judged_repo(tmp)
        first = run_tool(kit, cwd=judged)
        said = first.stdout + first.stderr
        pinned_ran = "PINNED-EXAMINER" in said and "SHADOW-EXAMINER" not in said
        ok_one = first.returncode == 0 and pinned_ran

        write_run(judged / "postconditions" / NAME / "run", marker="SHADOW-EXAMINER-MUTATED")
        (judged / "postconditions" / NAME / "fixtures" / "red" / "verdict").write_text("pass\n")
        second = run_tool(kit, cwd=judged)
        unchanged = second.returncode == first.returncode and "PINNED-EXAMINER" in (
            second.stdout + second.stderr
        )

        shadow_kit = kit_tree(tmp / "second", pinned=str(judged))
        third = run_tool(shadow_kit, cwd=judged)
        ok_two = third.returncode == 2 and VOID_MARKER in (third.stdout + third.stderr)

    ok = ok_one and unchanged and ok_two
    print(f"  {'ok  ' if ok else 'FAIL'} judged-tree-shadow: want the pinned examiner to run "
          f"(exit 0), the verdict unchanged when only the shadow changes, and the shadow's own "
          f"root refused (exit 2); got {first.returncode}/{second.returncode}/{third.returncode}")
    if not ok:
        print(f"       pinned ran: {pinned_ran}; unchanged: {unchanged}")
        print(f"       first: {(first.stdout + first.stderr).strip()[:400]}")
        print(f"       third: {(third.stdout + third.stderr).strip()[:400]}")
    return ok


def fixtures_not_mutated_case() -> bool:
    """A postcondition that writes into the tree it judges must not reach the pinned fixtures.

    Fixtures are examiner material (ADR-0001/D3), and a demonstration that runs a postcondition
    against the pinned trees themselves lets any postcondition edit the evidence every later
    demonstration is judged by. The loader therefore judges a copy. The digest is taken over both
    fixture trees before and after the load; the run appends a file to whatever tree it is given,
    so an in-place demonstration changes the digest and this case fails.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit = standard(tmp, run_extra=POISON_EXTRA)
        home = tmp / "pinned" / "postconditions" / NAME
        before = {limb: tree_digest(home / "fixtures" / limb) for limb in ("red", "green")}
        got = run_tool(kit)
        after = {limb: tree_digest(home / "fixtures" / limb) for limb in ("red", "green")}
        changed = sorted(limb for limb in before if before[limb] != after[limb])
        ok = got.returncode == 0 and LOADABLE_MARKER in (got.stdout + got.stderr) and not changed
        print(f"  {'ok  ' if ok else 'FAIL'} fixtures-not-mutated: want exit 0 with both pinned "
              f"fixture trees byte-identical, got exit {got.returncode} with "
              f"{len(changed)} tree(s) changed")
        if not ok:
            print(f"       changed: {changed}")
            print(f"       stdout: {got.stdout.strip()[:300]}")
            print(f"       stderr: {got.stderr.strip()[:300]}")
        return ok


def unreadable_ancestor_case() -> bool:
    """A directory above the pinned root at mode 000 reads could-not-run, not a verdict.

    The condition is constructed rather than assumed: if the fixture can still traverse the
    directory it just locked, it has not built the case, and it says so and fails rather than
    reporting a pass it did not earn. That happens when the suite runs as root, where mode bits
    do not bind.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        locked = tmp / "locked"
        locked.mkdir()
        postcondition(locked / "pinned")
        kit = kit_tree(tmp, pinned=str(locked / "pinned"))
        locked.chmod(0o000)
        try:
            if os.access(locked, os.R_OK | os.X_OK):
                print("  FAIL unreadable-ancestor: the locked directory is still traversable, so "
                      "the condition was not constructed (running as root?)")
                return False
            got = run_tool(kit)
        finally:
            locked.chmod(0o755)
        return report("unreadable-ancestor", 2, VOID_MARKER, got)


def hostile_env_case() -> bool:
    """The loader must not hand its own caller's git environment to a postcondition.

    Every other case scrubs `GIT_*` before invoking the loader, which isolates the fixture and
    is the wrong coverage on its own: the suite cannot then see whether the TOOL scrubs. Here
    `GIT_DIR` and `GIT_INDEX_FILE` name a decoy repository exactly as a pre-commit hook or a
    phase seam would export them, and the demonstration scripts exit 2 if either reaches them.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit = standard(tmp)
        decoy = judged_repo(tmp, name="decoy")
        env = clean_env()
        env["GIT_DIR"] = str(decoy / ".git")
        env["GIT_INDEX_FILE"] = str(decoy / ".git" / "index")
        return report("hostile-git-env", 0, LOADABLE_MARKER, run_tool(kit, env=env))


def main() -> int:
    if not TOOL.is_file():
        print(f"loader_test: tool not found at {TOOL}", file=sys.stderr)
        return 2
    results = [
        case("loadable", 0, LOADABLE_MARKER, build_loadable),
        case("config-exported", 0, LOADABLE_MARKER, build_config),
        case("relative-resolution", 0, "PINNED-HOME-REACHED", build_relative_resolution),
        case("fixture-is-a-repo", 0, LOADABLE_MARKER, build_fixture_is_a_repo),
        case("root-symlink-legitimate", 0, LOADABLE_MARKER, build_root_symlink_legitimate),
        fixtures_not_mutated_case(),
        hostile_env_case(),
        case("root-symlink-escape", 2, VOID_MARKER, build_root_symlink_escape),
        case("material-symlink-escape", 2, VOID_MARKER, build_material_symlink_escape),
        unreadable_ancestor_case(),
        case("missing-red-fixtures", 2, "'demo' has no red fixture", build_missing_red),
        case("missing-green-fixtures", 2, "'demo' has no green fixture", build_missing_green),
        case("red-passes", 1, FAIL_MARKER, build_red_passes),
        case("green-fails", 1, FAIL_MARKER, build_green_fails),
        case("demonstration-exit-2", 2, "exit 2", build_exit_two),
        case("demonstration-timeout", 2, VOID_MARKER, build_hangs, extra=("--timeout", "1")),
        case("run-not-executable", 2, VOID_MARKER, build_not_executable),
        case("run-absent", 2, VOID_MARKER, build_run_absent),
        case("postcondition-absent", 2, VOID_MARKER, build_postcondition_absent),
        case("pinned-root-unset", 2, VOID_MARKER, build_pinned_unset),
        case("pinned-root-nested", 2, VOID_MARKER, build_pinned_nested),
        case("pinned-root-relative", 2, VOID_MARKER, build_pinned_relative),
        case("pinned-root-absent", 2, VOID_MARKER, build_pinned_absent),
        case("pinned-root-in-worktree", 2, VOID_MARKER, build_pinned_in_worktree),
        case("no-profile", 2, VOID_MARKER, build_no_profile),
        case("unparseable-profile", 2, VOID_MARKER, build_unparseable),
        shadow_case(),
    ]
    failed = results.count(False)
    print(f"loader_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Red-first fixture for ADR-0001/D2's court: the denial probe replayed against the real seam.

The design's §4.4 measurement is why this court exists: a phase run with every write tool
disabled reported success on every field the harness exposes—exit 0, `is_error` false, `subtype`
"success", `permission_denials` empty—while the file it was told to create did not exist. D2's
falsification condition names the replay: a did-nothing tree must FAIL, a known-good tree must
PASS, and a tools-disabled run must read could-not-run, never a pass.

The replay drives the REAL `harness/chain/advance.py` as a CLI, because the trap the story names
is a replay that passes against a stub seam. A stub that admits everything and writes nothing
satisfies any case that reads only an exit code, so each case couples to the seam three ways:
the exit code, a named output string, and the ref consequence read DIRECTLY from the ref store
on disk rather than asked of any tool. Two further couplings discriminate the stub: the
postcondition's own marker must arrive through the seam's `advance: seam|` relay in the cases
where the examiner runs, and must be absent entirely in the case where nothing could run.

Unlike `advance_test.py`'s postcondition, which reads a verdict the graded tree declares, this
one grades WORK: the artifact the phase was told to produce must exist with its declared
content. A did-nothing tree is clean and committed and simply lacks the artifact, which is
exactly the tree the §4.4 probe left behind. The tools-disabled condition is simulated
mechanically: the postcondition's `run` is present and executable, and its interpreter is a
file with no execute permission, so the exec is denied—the examiner looks fine on every static
surface and cannot act, which is the probe's shape moved to the seam.

  did-nothing-fails-1      clean committed tree, no artifact  -> 1, FAIL, seam ran, no ref
  known-good-passes-0      the artifact present and committed -> 0, PASS, ref = graded sha
  tools-disabled-void-2    the examiner's interpreter denied  -> 2, VOID, nothing ran, no ref
  self-sabotage-void-2     demonstrates, then drops its x bit -> 2, VOID naming the graded run

`tools-disabled-void-2` grades the KNOWN-GOOD tree, and that is deliberate: a tree that would
pass cannot pass when nothing could examine it, so could-not-run is demonstrably not derived
from the tree, and the pass marker is required absent rather than merely unexpected.

THE SEAM HAS TWO EXEC SITES and a denial at each must read could-not-run: the loader's
demonstration, and `seam_run`'s own exec against the graded tree. `tools-disabled-void-2`
denies the first, so it proves nothing about the second—a `seam_run` whose OSError arm returned
a pass would sign a phase no examiner examined, and it would survive every case whose denial
lands at the demonstration. `self-sabotage-void-2` is the examiner that reaches the second
site: it demonstrates red and green correctly and then drops its own exec bit, so the one exec
that is denied is the graded run, and the VOID reason must name the graded repository rather
than a fixture copy.

Run: python3 harness/fixtures/seam_court_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "chain" / "advance.py"

PASS_MARKER = "advance: PASS"
FAIL_MARKER = "advance: FAIL"
VOID_MARKER = "advance: VOID"
EXAMINER = "SEAM-COURT-EXAMINER"
SEAM_RELAY = f"advance: seam| {EXAMINER}"
DENIED = "could not be executed"

NAME = "work-was-done"
STORY = "STORY-0040"
ARTIFACT = "artifact.txt"
WORK = "the artifact the phase was told to produce"

# The postcondition grades work, not a declared verdict: the artifact must exist and carry its
# declared content. Absence is handled explicitly because grep exits 2 on a missing file, and 2
# is could-not-run at the seam where absence here is a plain FAIL about the story.
RUN_SCRIPT = f"""#!/usr/bin/env bash
set -uo pipefail
echo "{EXAMINER}"
if [ "$#" -lt 1 ]; then echo "run: no tree argument"; exit 2; fi
if [ ! -f "$1/{ARTIFACT}" ]; then echo "run: the artifact does not exist"; exit 1; fi
if grep -qF "{WORK}" "$1/{ARTIFACT}"; then
  echo "run: the artifact carries its declared content"
  exit 0
fi
echo "run: the artifact exists without its declared content"
exit 1
"""

# The tools-disabled examiner: present, executable, and pointing at an interpreter the kernel
# refuses. The body would pass everything if it ever ran, so a transcript carrying its exit is
# proof the case was not constructed.
DENIED_RUN = """#!{interpreter}
exit 0
"""

# The self-sabotaging examiner: demonstrates red and green correctly, then drops its own exec
# bit once both limbs have run, so the one exec that is denied is the graded run. Its working
# directory is its own pinned home for every invocation, which is where the seen markers land;
# the judged copy's basename is the fixture limb's name during a demonstration and the graded
# directory's name at the seam.
SABOTEUR_RUN = f"""#!/usr/bin/env bash
set -uo pipefail
echo "{EXAMINER}"
if [ "$#" -lt 1 ]; then echo "run: no tree argument"; exit 2; fi
touch "seen-$(basename "$1")"
if [ -e seen-green ] && [ -e seen-red ]; then chmod 0644 "$0"; fi
if [ ! -f "$1/{ARTIFACT}" ]; then echo "run: the artifact does not exist"; exit 1; fi
if grep -qF "{WORK}" "$1/{ARTIFACT}"; then
  echo "run: the artifact carries its declared content"
  exit 0
fi
echo "run: the artifact exists without its declared content"
exit 1
"""


def clean_env() -> dict[str, str]:
    """The environment with git's own variables dropped.

    A pre-commit hook runs with `GIT_DIR` and `GIT_INDEX_FILE` exported and a subprocess
    inherits them, so a fixture that builds a throwaway repository writes into the real one
    instead. Every git spawn and every tool invocation here goes through this scrub.
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
    git(path, "init", "-q", "-b", "main", ".")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "fixture")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "baseline", "--allow-empty")


def graded_repo(td: Path, *, work: bool) -> Path:
    """The tree under judgement: committed and porcelain-clean either way, the work optional."""
    repo = td / "graded"
    repo.mkdir()
    (repo / "README.md").write_text("the graded tree\n")
    if work:
        (repo / ARTIFACT).write_text(WORK + "\n")
    init_repo(repo)
    return repo


def pinned_root(td: Path, *, run_text: str) -> Path:
    root = td / "pinned"
    home = root / "postconditions" / NAME
    home.mkdir(parents=True)
    run = home / "run"
    run.write_text(run_text)
    run.chmod(0o755)
    red = home / "fixtures" / "red"
    red.mkdir(parents=True)
    (red / "README.md").write_text("a tree the phase did nothing to\n")
    green = home / "fixtures" / "green"
    green.mkdir(parents=True)
    (green / ARTIFACT).write_text(WORK + "\n")
    return root


def kit_tree(td: Path, pinned: Path) -> Path:
    """The SEQUENCER's profile, never the graded repository's (ADR-0001/D3)."""
    kit = td / "kit"
    chain = kit / ".claude" / "chain"
    chain.mkdir(parents=True)
    (chain / "profile.toml").write_text(
        'terminal = "open-pr"\npush = "branches-only"\n' f'pinned_root = "{pinned}"\n'
    )
    return kit


def bench(td: Path, *, work: bool, run_text: str = RUN_SCRIPT) -> tuple[Path, Path]:
    kit = kit_tree(td, pinned_root(td, run_text=run_text))
    return kit, graded_repo(td, work=work)


def run_advance(kit: Path, repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, str(TOOL),
            "--repo", str(repo),
            "--story", STORY,
            "--attempt", "1",
            "--phase", "2",
            "--postcondition", NAME,
            "--profile-root", str(kit),
        ],
        capture_output=True,
        text=True,
        env=clean_env(),
    )


def phase_ref() -> str:
    return f"refs/chain/{STORY}/attempt-1/phase-2"


def stored_ref(repo: Path, ref: str) -> str | None:
    """The sha the ref store holds, read from the filesystem and never asked of git.

    The seam's own confirmation reads the store for the reason `advance.py` records; the fixture
    reads it the same way so the consequence it asserts is the store's state rather than any
    tool's report of it. The fixture repositories are ordinary checkouts, so `.git` is a
    directory and the loose file with a packed-refs fallback is the whole read.
    """
    loose = repo / ".git" / ref
    if loose.is_file():
        return loose.read_text().strip() or None
    packed = repo / ".git" / "packed-refs"
    if packed.is_file():
        for line in packed.read_text().splitlines():
            if not line or line.startswith(("#", "^")):
                continue
            sha, _, name = line.partition(" ")
            if name.strip() == ref:
                return sha.strip()
    return None


def judge(
    name: str,
    got: subprocess.CompletedProcess[str],
    *,
    want: int,
    markers: tuple[str, ...] = (),
    absent: tuple[str, ...] = (),
    repo: Path | None = None,
    want_ref: str | None = None,
) -> bool:
    """Compare exit code, required and forbidden markers, and the ref store's state.

    `want_ref` is a sha the stored ref must equal, or the string "none" for a ref that must not
    exist in the store at all.
    """
    said = got.stdout + got.stderr
    problems = []
    if got.returncode != want:
        problems.append(f"exit {got.returncode}, wanted {want}")
    for m in markers:
        if m not in said:
            problems.append(f"'{m}' absent from the transcript")
    for m in absent:
        if m in said:
            problems.append(f"'{m}' present, and it must not be")
    if repo is not None:
        have = stored_ref(repo, phase_ref())
        if want_ref == "none":
            if have is not None:
                problems.append(f"the ref store holds {have[:8]}, and nothing was recorded")
        elif have != want_ref:
            problems.append(f"the ref store holds {have}, wanted {want_ref}")
    ok = not problems
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want}; "
          + ("as required" if ok else "; ".join(problems)))
    if not ok:
        print(f"       stdout: {got.stdout.strip()[:600]}")
        print(f"       stderr: {got.stderr.strip()[:600]}")
    return ok


def did_nothing_case() -> bool:
    """A phase that produced no work must FAIL, which is the probe's exact tree.

    The graded repository is clean, committed, and missing the artifact—every surface the
    harness self-report exposed read success on this shape, and the seam must read exit 1 with
    the failure named and nothing in the ref store. The seam relay marker is required so the
    verdict is the real examiner's reading of the real tree, not a stub's exit code.
    """
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td), work=False)
        got = run_advance(kit, repo)
        ok = judge("did-nothing-fails-1", got, want=1,
                   markers=(FAIL_MARKER, SEAM_RELAY),
                   absent=(PASS_MARKER, VOID_MARKER),
                   repo=repo, want_ref="none")
        if (repo / ARTIFACT).exists():
            print("       the artifact exists, so the tree is not a did-nothing tree")
            ok = False
        return ok


def known_good_case() -> bool:
    """A known-good tree must PASS, with the ref in the store at the graded sha and only then."""
    with tempfile.TemporaryDirectory() as td:
        kit, repo = bench(Path(td), work=True)
        sha = git(repo, "rev-parse", "HEAD")
        got = run_advance(kit, repo)
        return judge("known-good-passes-0", got, want=0,
                     markers=(PASS_MARKER, SEAM_RELAY),
                     absent=(FAIL_MARKER, VOID_MARKER),
                     repo=repo, want_ref=sha)


def tools_disabled_case() -> bool:
    """An examiner that cannot execute reads could-not-run: exit 2, VOID, never a pass.

    The tree is the KNOWN-GOOD one, so a seam that read the verdict off the tree rather than off
    an examiner it actually ran would pass here and be caught. The interpreter is a real file
    with no execute permission, so `run` clears every static check the loader makes and the exec
    itself is denied; the examiner's marker is required absent because nothing ran.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        interpreter = tmp / "denied-interpreter"
        interpreter.write_text("#!/bin/sh\nexit 0\n")
        interpreter.chmod(0o644)
        kit, repo = bench(tmp, work=True,
                          run_text=DENIED_RUN.format(interpreter=interpreter))
        got = run_advance(kit, repo)
        ok = judge("tools-disabled-void-2", got, want=2,
                   markers=(VOID_MARKER, DENIED),
                   absent=(PASS_MARKER, FAIL_MARKER, EXAMINER),
                   repo=repo, want_ref="none")
        run = tmp / "pinned" / "postconditions" / NAME / "run"
        if not os.access(run, os.X_OK):
            print("       run is not executable, so the resolver refused before any exec was denied")
            ok = False
        if os.access(interpreter, os.X_OK):
            print("       the interpreter is executable, so nothing was denied")
            ok = False
        return ok


def self_sabotage_case() -> bool:
    """The seam run is its own exec site, and a denial there must read could-not-run.

    The examiner demonstrates red and green correctly and then drops its own exec bit, so the
    demonstration proves nothing about the one exec that is denied: the graded run. The VOID
    reason must name the graded repository rather than a fixture copy, the seam relay must be
    absent because nothing ran against the graded tree, and the store must hold nothing—a seam
    whose denied graded exec read as a pass would sign a phase no examiner examined.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        kit, repo = bench(tmp, work=True, run_text=SABOTEUR_RUN)
        got = run_advance(kit, repo)
        ok = judge("self-sabotage-void-2", got, want=2,
                   markers=(VOID_MARKER, f"could not be executed against {repo.resolve()}"),
                   absent=(PASS_MARKER, FAIL_MARKER, SEAM_RELAY),
                   repo=repo, want_ref="none")
        home = tmp / "pinned" / "postconditions" / NAME
        if not ((home / "seen-green").is_file() and (home / "seen-red").is_file()):
            print("       a demonstration limb never ran, so the sabotage was never reached")
            ok = False
        if os.access(home / "run", os.X_OK):
            print("       run is still executable, so the graded exec was never denied")
            ok = False
        return ok


def main() -> int:
    if not TOOL.is_file():
        print(f"seam_court_test: tool not found at {TOOL}", file=sys.stderr)
        return 2
    results = [
        did_nothing_case(),
        known_good_case(),
        tools_disabled_case(),
        self_sabotage_case(),
    ]
    failed = results.count(False)
    print(f"seam_court_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

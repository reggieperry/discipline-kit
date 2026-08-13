#!/usr/bin/env python3
"""Red-first fixture for `harness/chain/merge.py`, the merge stage.

The stage is where ADR-0002's D3, D5 and the terminal-act half of D1 become mechanism: the trial
merge of one pinned candidate sha into the current local `main`, the eight `merge_ok` conjuncts
each with a receipt line, the merge record naming the forged-ref residue as OPEN, and the two
terminal acts behind the declared posture. Every case here asserts exit code AND marker AND
state — refs read back from throwaway clones and bare local remotes, record content read back
from disk — and no case invokes a real forge or a real harness: the forge and git commands are
injectable seams pointed at stubs written here, and every git spawn scrubs the caller's own
`GIT_*` environment first.

  CANDIDATE PINNING (call A: position, tip-equality, ancestry)
  pin-premature-2            two phase refs, three declared          -> 2, premature-invocation
  pin-gap-2                  phases 1 and 3, a hole at 2             -> 2, gap named, no verdict
  pin-tip-diverged-1         story branch one commit past the ref    -> 1, candidate-diverged
  pin-non-ancestor-1         a phase ref off the story's history     -> 1, phase-ref-ancestry
  forged-chain-residue-0     a chain planted wholesale passes, and   -> 0, the record's residue
                             the record says exactly that               line asserted VERBATIM

  THE TRIAL MERGE
  trial-conflict-1           the story's diff conflicts with main    -> 1, trial-merge-conflict,
                                                                        conjunct 1 never ran,
                                                                        remote untouched
  git-too-old-2              the git seam reports 2.30               -> 2, git-too-old

  CONJUNCT 2 (trusted base, both rename sides visible)
  c2-trusted-touch-1         the diff adds scripts/extra.sh          -> 1, and the check UNRUN:
                                                                        the late-check ordering
  c2-rename-delete-1         scripts/tool.sh renamed out             -> 1, the delete side seen

  CONJUNCT 3 (plan reconciliation, declaration carried verbatim)
  c3-undeclared-1            a diff path the plan never declared     -> 1, declaration verbatim
                                                                        in the record
  c3-plan-absent-2           no declared path list supplied          -> 2, plan-absent

  CONJUNCT 4 (the reviewer's receipt through the loader)
  c4-receipt-red-1           merged tree without the receipt         -> 1
  c4-receipt-pc-absent-2     no receipt-complete postcondition       -> 2

  CONJUNCTS 5 AND 6 (refutation and park refs)
  c5-refutation-1            refs/chain/<story>/refutation-1 stands  -> 1
  c6-park-1                  refs/chain/<story>/park stands          -> 1
  c56-foreign-note-0         an attempt note ref alongside           -> 0, named left alone

  CONJUNCT 1 (the commit-path check, inside the scratch, last)
  c1-check-red-1             the check exits 1 at the merged tree    -> 1, ran inside the scratch
  c1-check-exit-3-2          the check exits 3                       -> 2, no verdict observed
  c1-check-dirties-1         the check drops a file and exits 0      -> 1, graded-tree-dirtied
  c1-check-commits-1         the check commits an edit and exits 0   -> 1, graded-tree-moved
  c1-check-untrusted-2       a check path outside trusted_base       -> 2, check-untrusted

  MERGE-LOCAL (the CAS advance and the revert premise)
  local-cas-and-revert-0     the CAS advance carries the graded      -> 0, parents and trailer
                             tree and old value; revert restores        asserted, revert -m 1
                                                                        restores the base tree
  local-main-moved-1         the check moves main mid-evaluation     -> 1, conjunct 7, no CAS
  local-checked-out-2        main checked out in the clone           -> 2, main-checked-out

  OPEN-PR (push by sha, the forge seam, the push-scope guard)
  pr-green-0                 push story ref, one stubbed forge call  -> 0, remote main unmoved
  pr-briefing-absent-2       no briefing supplied                    -> 2, nothing pushed
  pr-forge-fails-2           the forge stub exits 1 after the push   -> 2, the record's act line
  push-main-uncomposable     guarded_push in-process: '/' and '..'   -> refused; scope 'never'
                             refused; 'main' lands at story/main        and remote main unmoved

  THE RECORD
  record-in-worktree-2       a record path inside a working tree     -> 2, nothing written
  record-preexists-2         a pre-planted file at the path          -> 2, bytes untouched
  hostile-gitdir-0           GIT_DIR naming a decoy repository       -> 0, derived from --repo

Run: python3 harness/fixtures/merge_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
MERGE = HARNESS / "chain" / "merge.py"

STORY = "STORY-0042"
VOID = "merge: VOID"
FINDING_TOKEN = "RECEIPT-FINDING-TOKEN"

PAIRED = {"open-pr": "branches-only", "merge-local": "never"}

PROFILE = """terminal = "{terminal}"
push = "{push}"
pinned_root = "{pinned}"
trusted_base = [".claude/", "harness/", "scripts/"]
"""

# The judged repository's own commit-path check, committed at the baseline so it is part of the
# merged tree. It logs the directory it ran in, so where the check executed is an observation.
SELFCHECK = """#!/usr/bin/env bash
printf 'selfcheck %s\\n' "$PWD" >> "__LOG__"
__BEHAVIOR__
"""

CHECK_GREEN = "exit 0"
CHECK_RED = "exit 1"
CHECK_BROKEN = "exit 3"
CHECK_DIRTIES = "printf 'dirt\\n' > check-dropping.txt\nexit 0"
CHECK_COMMITS = ("printf 'edited\\n' >> src/app.txt\n"
                 "git add -A\ngit commit -qm edited-by-check\nexit 0")
CHECK_MOVES_MAIN = 'git update-ref refs/heads/main "$(git rev-parse HEAD^2)"\nexit 0'

# The pinned receipt reader: exit 0 with per-lens findings where the receipt file is present in
# the judged tree, exit 1 where it is absent. Its red and green fixture trees demonstrate both.
RECEIPT_RUN = """#!/usr/bin/env bash
tree="$1"
if [ -f "$tree/review-receipt.txt" ]; then
  printf 'lens architectural: no finding\\n'
  printf 'lens adversarial: __TOKEN__\\n'
  exit 0
fi
printf 'the coverage receipt is absent from the judged tree\\n'
exit 1
"""

FORGE_STUB = """#!/usr/bin/env bash
printf 'forge %s\\n' "$*" >> "__LOG__"
exit __CODE__
"""

# A git whose version predates merge-tree --write-tree. Anything past the version read reaching
# it is itself a defect, so every other subcommand fails loudly.
OLD_GIT = """#!/usr/bin/env bash
if [ "${1:-}" = "version" ]; then
  printf 'git version 2.30.0\\n'
  exit 0
fi
printf 'old-git reached for %s\\n' "$*" >&2
exit 97
"""

GIT_SPY = """#!/usr/bin/env bash
printf 'git %s\\n' "$*" >> "__LOG__"
exec "__REAL__" "$@"
"""


def clean_env() -> dict[str, str]:
    """The environment with git's own variables dropped.

    A pre-commit hook exports `GIT_DIR` and `GIT_INDEX_FILE`, and a subprocess that inherits
    them operates on the REAL repository rather than on the throwaway one a case built.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True, env=clean_env(),
    )
    return done.stdout.strip()


def ref_value(repo: Path, ref: str) -> str | None:
    done = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True, text=True, env=clean_env(),
    )
    return done.stdout.strip() or None


def executable(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


@dataclass(frozen=True)
class Rig:
    clone: Path
    kit: Path
    pinned: Path
    remote: Path | None
    check_log: Path
    base: str
    main_sha: str
    candidate: str
    tip: str
    record: Path
    plan: Path
    briefing: Path


def build_rig(td: Path, *, terminal: str = "open-pr", check: str = CHECK_GREEN,
              with_receipt: bool = True, receipt_pc: bool = True,
              story_extra: tuple[str, ...] = (), phases: tuple[int, ...] = (1, 2, 3),
              tip_past: bool = False, conflict: bool = False, rename_tool: bool = False,
              checkout_main: bool = False, remote: bool = False,
              declared: tuple[str, ...] | None = None) -> Rig:
    """One scenario: a dedicated clone with a graded story, a kit tree, and pinned material.

    The clone ends detached at the baseline unless a case needs `main` checked out, because the
    merge-local act refuses a checked-out `main` and the green path must construct the state the
    stage requires rather than trip over the fixture's own checkout.
    """
    clone = td / "clone"
    clone.mkdir(parents=True)
    check_log = td / "check.log"
    (clone / "README.md").write_text("value: one\nother line\n")
    (clone / "src").mkdir()
    (clone / "src" / "app.txt").write_text("app\n")
    executable(clone / "scripts" / "selfcheck",
               SELFCHECK.replace("__LOG__", str(check_log)).replace("__BEHAVIOR__", check))
    executable(clone / "scripts" / "tool.sh", "#!/usr/bin/env bash\nexit 0\n")
    executable(clone / "loosecheck", "#!/usr/bin/env bash\nexit 0\n")
    git(clone, "init", "-q", "-b", "main", ".")
    git(clone, "config", "user.email", "fixture@example.invalid")
    git(clone, "config", "user.name", "fixture")
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "baseline")
    base = git(clone, "rev-parse", "HEAD")

    if conflict:
        (clone / "README.md").write_text("value: two\nother line\n")
        git(clone, "add", "-A")
        git(clone, "commit", "-qm", "main moves the value")
    main_sha = git(clone, "rev-parse", "HEAD")

    git(clone, "checkout", "-q", "-b", "work", base)
    (clone / "src" / "feature.txt").write_text("the feature\n")
    if with_receipt:
        (clone / "review-receipt.txt").write_text("lens architectural\nlens adversarial\n")
    if conflict:
        (clone / "README.md").write_text("value: three\nother line\n")
    for name in story_extra:
        target = clone / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("story-supplied\n")
    if rename_tool:
        git(clone, "mv", "scripts/tool.sh", "src/tool.sh")
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "story work")
    candidate = git(clone, "rev-parse", "HEAD")
    tip = candidate
    if tip_past:
        (clone / "src" / "after.txt").write_text("ungraded\n")
        git(clone, "add", "-A")
        git(clone, "commit", "-qm", "past the graded ref")
        tip = git(clone, "rev-parse", "HEAD")
    git(clone, "update-ref", f"refs/heads/story/{STORY}", tip)
    if checkout_main:
        git(clone, "checkout", "-q", "main")
    else:
        git(clone, "checkout", "-q", "--detach", base)
    git(clone, "branch", "-qD", "work")
    for n in phases:
        git(clone, "update-ref", f"refs/chain/{STORY}/attempt-1/phase-{n}", candidate)

    pinned = td / "pinned"
    pinned.mkdir()
    if receipt_pc:
        home = pinned / "postconditions" / "receipt-complete"
        executable(home / "run", RECEIPT_RUN.replace("__TOKEN__", FINDING_TOKEN))
        (home / "fixtures" / "red").mkdir(parents=True)
        (home / "fixtures" / "red" / "placeholder.txt").write_text("no receipt here\n")
        (home / "fixtures" / "green").mkdir(parents=True)
        (home / "fixtures" / "green" / "review-receipt.txt").write_text("receipt\n")

    kit = td / "kit"
    chain = kit / ".claude" / "chain"
    chain.mkdir(parents=True)
    (chain / "profile.toml").write_text(
        PROFILE.format(terminal=terminal, push=PAIRED[terminal], pinned=pinned))

    bare = None
    if remote:
        bare = td / "remote.git"
        bare.mkdir()
        git(bare, "init", "-q", "--bare", ".")
        git(clone, "remote", "add", "origin", str(bare))
        git(clone, "push", "-q", "origin", "main")

    if declared is None:
        listed = ["src/feature.txt"]
        if with_receipt:
            listed.append("review-receipt.txt")
        if conflict:
            listed.append("README.md")
        if rename_tool:
            listed += ["scripts/tool.sh", "src/tool.sh"]
        listed += list(story_extra)
        declared = tuple(listed)
    plan = td / "plan.txt"
    plan.write_text("".join(f"{p}\n" for p in declared))
    briefing = td / "briefing.md"
    briefing.write_text(f"# {STORY}\n\nThe documenter's briefing body.\n")
    return Rig(clone=clone, kit=kit, pinned=pinned, remote=bare, check_log=check_log,
               base=base, main_sha=main_sha, candidate=candidate, tip=tip,
               record=td / "records" / "merge.record", plan=plan, briefing=briefing)


def run_merge(rig: Rig, act: str = "evaluate", *, plan: bool = True, record: Path | None = None,
              use_record: bool = True, gitcmd: Path | None = None, forge: Path | None = None,
              briefing: bool = False, check_arg: str = "scripts/selfcheck",
              expected: str = "3", env: dict[str, str] | None = None
              ) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(MERGE), act,
            "--root", str(rig.kit), "--repo", str(rig.clone), "--story", STORY,
            "--expected-phases", expected, "--commit-check", check_arg]
    if plan:
        argv += ["--plan", str(rig.plan)]
    if use_record:
        argv += ["--record", str(record if record is not None else rig.record)]
    if gitcmd is not None:
        argv += ["--git", str(gitcmd)]
    if act == "merge":
        if forge is not None:
            argv += ["--forge", str(forge)]
        if briefing:
            argv += ["--briefing", str(rig.briefing)]
    return subprocess.run(argv, capture_output=True, text=True,
                          env=clean_env() if env is None else env)


def judge(name: str, got: subprocess.CompletedProcess[str], *, want: int, marker: str,
          absent: str | tuple[str, ...] = (), present: tuple[str, ...] = (),
          faults: tuple[str, ...] = ()) -> bool:
    """Compare exit code, required markers, forbidden markers, and caller-established state.

    `faults` arrives already worded: whatever the caller measured on the filesystem, the refs or
    the record before judging. It lands here so the verdict line is the verdict rather than a
    first word a later complaint contradicts.
    """
    said = got.stdout + got.stderr
    ok = got.returncode == want and marker in said
    detail = ""
    for wanted in present:
        if wanted not in said:
            ok = False
            detail += f" (expected '{wanted}' in the output)"
    for forbidden in (absent,) if isinstance(absent, str) else absent:
        if forbidden in said:
            ok = False
            detail += f" (found '{forbidden}', which must not appear)"
    for fault in faults:
        ok = False
        detail += f" ({fault})"
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want} naming '{marker}', "
          f"got exit {got.returncode}{detail}")
    if not ok:
        print(f"       stdout: {got.stdout.strip()[:600]}")
        print(f"       stderr: {got.stderr.strip()[:600]}")
    return ok


def record_lines(rig: Rig) -> list[str]:
    return rig.record.read_text().splitlines() if rig.record.is_file() else []


def record_faults(rig: Rig, *, contains: tuple[str, ...] = (), exact: tuple[str, ...] = (),
                  testimony_pair: bool = True) -> list[str]:
    """What the record on disk must carry: existence, the two testimony lines, named content."""
    lines = record_lines(rig)
    if not lines:
        return [f"no record was written at {rig.record}"]
    faults = []
    if testimony_pair:
        n = sum(1 for line in lines if line.startswith("testimony:"))
        if n != 2:
            faults.append(f"{n} testimony line(s) in the record, wanted exactly 2")
    for piece in contains:
        if not any(piece in line for line in lines):
            faults.append(f"the record lacks '{piece[:70]}'")
    for line in exact:
        if line not in lines:
            faults.append(f"the record lacks the exact line '{line[:70]}...'")
    return faults


def residue_expected(terminal: str) -> str:
    """The record's forged-ref residue line, character for character, per declared act."""
    radius = {"open-pr": "an unearned PR, never a trunk advance",
              "merge-local": "a bad local merge, removed by revert"}[terminal]
    return ("residue: forged-ref OPEN (ADR-0001/D1, ADR-0002/D5): the candidate was selected by "
            f"position over refs/chain/{STORY}/*, a namespace any Bash-holding phase can write; "
            "conjuncts 5 and 6 read the same forgeable namespace, so a deleted refutation or "
            "park ref is invisible here; narrowed by tip-equality and phase-ref ancestry, not "
            "closed; closure is the containment-posture record's. Blast radius under terminal = "
            f"{terminal}: {radius}.")


def pin_premature_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), phases=(1, 2))
        got = run_merge(rig)
        return judge("pin-premature-2", got, want=2, marker="premature-invocation",
                     faults=tuple(record_faults(rig)))


def pin_gap_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), phases=(1, 3))
        got = run_merge(rig)
        return judge("pin-gap-2", got, want=2, marker="gap:",
                     faults=tuple(record_faults(rig)))


def pin_tip_diverged_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), tip_past=True)
        got = run_merge(rig)
        faults = list(record_faults(rig, contains=("candidate-diverged",)))
        if rig.check_log.exists():
            faults.append("the commit-path check ran on a diverged candidate")
        return judge("pin-tip-diverged-1", got, want=1, marker="candidate-diverged",
                     faults=tuple(faults))


def pin_non_ancestor_case() -> bool:
    """A phase ref pointing off the story's history is the forged shape ancestry narrows."""
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td))
        orphan_tree = git(rig.clone, "rev-parse", f"{rig.base}^{{tree}}")
        orphan = git(rig.clone, "commit-tree", orphan_tree, "-m", "off-history")
        git(rig.clone, "update-ref", f"refs/chain/{STORY}/attempt-1/phase-1", orphan)
        got = run_merge(rig)
        return judge("pin-non-ancestor-1", got, want=1, marker="phase-ref-ancestry",
                     faults=tuple(record_faults(rig)))


def forged_chain_residue_case() -> bool:
    """Criterion 3: every ref here was planted by this fixture, which IS the forged chain, and
    the stage passes it AS DESIGNED with the record naming the open residue verbatim."""
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), terminal="open-pr")
        got = run_merge(rig)
        faults = list(record_faults(
            rig,
            exact=(residue_expected("open-pr"),),
            contains=("merge_ok: true", FINDING_TOKEN,
                      "testimony: plan-declaration: src/feature.txt review-receipt.txt")))
        scratch = rig.pinned / "worktrees" / STORY / "merge-1"
        if scratch.exists():
            faults.append("the scratch worktree survived past the record")
        return judge("forged-chain-residue-0", got, want=0, marker="merge_ok holds",
                     faults=tuple(faults))


def trial_conflict_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), terminal="open-pr", conflict=True, remote=True)
        assert rig.remote is not None
        before = ref_value(rig.remote, "refs/heads/main")
        forge_log = Path(td) / "forge.log"
        forge = executable(Path(td) / "forge-stub",
                           FORGE_STUB.replace("__LOG__", str(forge_log)).replace("__CODE__", "0"))
        got = run_merge(rig, "merge", forge=forge, briefing=True)
        faults = list(record_faults(rig, contains=("trial-merge-conflict",)))
        if rig.check_log.exists():
            faults.append("the commit-path check ran over a conflicted trial merge")
        if ref_value(rig.remote, "refs/heads/main") != before:
            faults.append("remote main moved on a conflicted merge")
        if ref_value(rig.remote, f"refs/heads/story/{STORY}") is not None:
            faults.append("the story branch was pushed on a conflicted merge")
        if forge_log.exists():
            faults.append("the forge was called on a conflicted merge")
        return judge("trial-conflict-1", got, want=1, marker="trial-merge-conflict",
                     present=("README.md", "check-green: could-not-run"),
                     faults=tuple(faults))


def git_too_old_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td))
        old = executable(Path(td) / "old-git", OLD_GIT)
        got = run_merge(rig, gitcmd=old)
        return judge("git-too-old-2", got, want=2, marker="git-too-old",
                     present=("2.30",), absent="old-git reached for")


def c2_trusted_touch_case() -> bool:
    """The late-check rule made visible: conjunct 2 reads FAIL and the check never runs."""
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), story_extra=("scripts/extra.sh",))
        got = run_merge(rig)
        faults = list(record_faults(rig, contains=("conjunct 2 trusted-base: FAIL",)))
        if rig.check_log.exists():
            faults.append("the commit-path check ran although conjunct 2 read FAIL")
        return judge("c2-trusted-touch-1", got, want=1, marker="scripts/extra.sh",
                     present=("check-green: could-not-run",), faults=tuple(faults))


def c2_rename_delete_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), rename_tool=True)
        got = run_merge(rig)
        return judge("c2-rename-delete-1", got, want=1, marker="scripts/tool.sh",
                     present=("conjunct 2 trusted-base: FAIL",),
                     faults=tuple(record_faults(rig)))


def c3_undeclared_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), declared=("review-receipt.txt",))
        got = run_merge(rig)
        faults = record_faults(
            rig, contains=("conjunct 3 plan-paths: FAIL",),
            exact=("testimony: plan-declaration: review-receipt.txt",))
        return judge("c3-undeclared-1", got, want=1, marker="src/feature.txt",
                     present=("the plan never declared",), faults=tuple(faults))


def c3_plan_absent_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td))
        got = run_merge(rig, plan=False)
        faults = list(record_faults(rig, contains=("testimony: plan-declaration: (none read",)))
        if rig.check_log.exists():
            faults.append("the commit-path check ran although conjunct 3 could not")
        return judge("c3-plan-absent-2", got, want=2, marker="plan-absent",
                     faults=tuple(faults))


def c4_receipt_red_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), with_receipt=False)
        got = run_merge(rig)
        return judge("c4-receipt-red-1", got, want=1, marker="conjunct 4 receipt: FAIL",
                     faults=tuple(record_faults(rig)))


def c4_receipt_pc_absent_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), receipt_pc=False)
        got = run_merge(rig)
        return judge("c4-receipt-pc-absent-2", got, want=2, marker="receipt-complete",
                     present=("conjunct 4 receipt: could-not-run",),
                     faults=tuple(record_faults(rig)))


def c5_refutation_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td))
        git(rig.clone, "update-ref", f"refs/chain/{STORY}/refutation-1", rig.candidate)
        got = run_merge(rig)
        return judge("c5-refutation-1", got, want=1, marker="refutation-1",
                     present=("conjunct 5 no-refutation: FAIL",),
                     faults=tuple(record_faults(rig)))


def c6_park_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td))
        git(rig.clone, "update-ref", f"refs/chain/{STORY}/park", rig.candidate)
        got = run_merge(rig)
        return judge("c6-park-1", got, want=1, marker=f"refs/chain/{STORY}/park",
                     present=("conjunct 6 no-park: FAIL",),
                     faults=tuple(record_faults(rig)))


def c56_foreign_note_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td))
        git(rig.clone, "update-ref", f"refs/chain/{STORY}/attempt-1/notes", rig.candidate)
        got = run_merge(rig)
        faults = record_faults(rig, contains=("foreign ref(s) left alone",
                                              f"refs/chain/{STORY}/attempt-1/notes"))
        return judge("c56-foreign-note-0", got, want=0, marker="merge_ok holds",
                     faults=tuple(faults))


def c1_check_red_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), check=CHECK_RED)
        got = run_merge(rig)
        faults = list(record_faults(rig, contains=("conjunct 1 check-green: FAIL",)))
        logged = rig.check_log.read_text() if rig.check_log.is_file() else ""
        if "merge-1" not in logged:
            faults.append("the check did not run inside the scratch worktree")
        return judge("c1-check-red-1", got, want=1, marker="conjunct 1 check-green: FAIL",
                     faults=tuple(faults))


def c1_check_broken_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), check=CHECK_BROKEN)
        got = run_merge(rig)
        return judge("c1-check-exit-3-2", got, want=2, marker="outside the canonical contract",
                     faults=tuple(record_faults(rig)))


def c1_check_dirties_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), check=CHECK_DIRTIES)
        got = run_merge(rig)
        return judge("c1-check-dirties-1", got, want=1, marker="graded-tree-dirtied",
                     present=("check-dropping.txt",),
                     faults=tuple(record_faults(rig, contains=("conjunct 8 source-set: FAIL",))))


def c1_check_commits_case() -> bool:
    """Porcelain alone misses a check that commits its edit; the tree re-assert does not."""
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), check=CHECK_COMMITS)
        got = run_merge(rig)
        return judge("c1-check-commits-1", got, want=1, marker="graded-tree-moved",
                     faults=tuple(record_faults(rig, contains=("conjunct 8 source-set: FAIL",))))


def c1_check_untrusted_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td))
        got = run_merge(rig, check_arg="loosecheck")
        faults = list(record_faults(rig))
        if rig.check_log.exists():
            faults.append("an untrusted check was executed")
        return judge("c1-check-untrusted-2", got, want=2, marker="check-untrusted",
                     faults=tuple(faults))


def local_cas_and_revert_case() -> bool:
    """The CAS advance carries the graded tree, the old value and the trailer; revert restores."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rig = build_rig(tmp, terminal="merge-local")
        spy_log = tmp / "git-spy.log"
        real = subprocess.run(["bash", "-c", "command -v git"], capture_output=True, text=True,
                              env=clean_env()).stdout.strip()
        spy = executable(tmp / "git-spy",
                         GIT_SPY.replace("__LOG__", str(spy_log)).replace("__REAL__", real))
        got = run_merge(rig, "merge", gitcmd=spy)

        faults = list(record_faults(rig, exact=(residue_expected("merge-local"),),
                                    contains=("act: merge-local:",)))
        trial = next((line.split(": ", 1)[1] for line in record_lines(rig)
                      if line.startswith("trial-commit: ")), "")
        tree = next((line.split(": ", 1)[1] for line in record_lines(rig)
                     if line.startswith("trial-tree: ")), "")
        main_now = ref_value(rig.clone, "refs/heads/main")
        if not trial or main_now != trial:
            faults.append(f"main is {main_now}, not the recorded trial commit {trial[:12]}")
        if ref_value(rig.clone, "refs/heads/main^1") != rig.main_sha:
            faults.append("the merge commit's first parent is not the old main")
        if ref_value(rig.clone, "refs/heads/main^2") != rig.candidate:
            faults.append("the merge commit's second parent is not the candidate")
        if git(rig.clone, "rev-parse", "refs/heads/main^{tree}") != tree:
            faults.append("the tree on main is not the recorded merged tree")
        message = git(rig.clone, "log", "-1", "--format=%B", "refs/heads/main")
        if f"Merged-Story: {STORY}" not in message:
            faults.append("the merge commit carries no Merged-Story trailer")
        spied = spy_log.read_text() if spy_log.is_file() else ""
        if f"update-ref refs/heads/main {trial} {rig.main_sha}" not in spied:
            faults.append("the update-ref was not a compare-and-swap against the old main")

        git(rig.clone, "checkout", "-q", "main")
        git(rig.clone, "revert", "-m", "1", "--no-edit", "refs/heads/main")
        base_tree = git(rig.clone, "rev-parse", f"{rig.main_sha}^{{tree}}")
        if git(rig.clone, "rev-parse", "HEAD^{tree}") != base_tree:
            faults.append("revert -m 1 did not restore the pre-merge tree")
        return judge("local-cas-and-revert-0", got, want=0, marker="act: merge-local",
                     faults=tuple(faults))


def local_main_moved_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), terminal="merge-local", check=CHECK_MOVES_MAIN)
        got = run_merge(rig, "merge")
        faults = list(record_faults(rig, contains=("conjunct 7 pinned-sha: FAIL",)))
        trial = next((line.split(": ", 1)[1] for line in record_lines(rig)
                      if line.startswith("trial-commit: ")), "")
        if trial and ref_value(rig.clone, "refs/heads/main") == trial:
            faults.append("main advanced to the trial commit although the pin moved")
        if ref_value(rig.clone, "refs/heads/main") != rig.candidate:
            faults.append("main is not where the check stub moved it, so the case is not built")
        return judge("local-main-moved-1", got, want=1, marker="moved from",
                     faults=tuple(faults))


def local_checked_out_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), terminal="merge-local", checkout_main=True)
        got = run_merge(rig, "merge")
        faults = []
        if ref_value(rig.clone, "refs/heads/main") != rig.main_sha:
            faults.append("main moved although it was checked out")
        faults += record_faults(rig)
        return judge("local-checked-out-2", got, want=2, marker="main-checked-out",
                     faults=tuple(faults))


def pr_green_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rig = build_rig(tmp, terminal="open-pr", remote=True)
        assert rig.remote is not None
        before = ref_value(rig.remote, "refs/heads/main")
        forge_log = tmp / "forge.log"
        forge = executable(tmp / "forge-stub",
                           FORGE_STUB.replace("__LOG__", str(forge_log)).replace("__CODE__", "0"))
        got = run_merge(rig, "merge", forge=forge, briefing=True)
        faults = list(record_faults(rig, contains=("act: open-pr:",)))
        if ref_value(rig.remote, f"refs/heads/story/{STORY}") != rig.candidate:
            faults.append("the remote story ref is not at exactly the candidate")
        if ref_value(rig.remote, "refs/heads/main") != before:
            faults.append("remote main moved, which no chain act may do")
        forged = forge_log.read_text() if forge_log.is_file() else ""
        if f"pr create --head story/{STORY}" not in forged:
            faults.append("the forge seam did not receive the pr-create call")
        if "--body-file" not in forged:
            faults.append("the forge call carries no briefing body")
        return judge("pr-green-0", got, want=0, marker="act: open-pr", faults=tuple(faults))


def pr_briefing_absent_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), terminal="open-pr", remote=True)
        assert rig.remote is not None
        got = run_merge(rig, "merge", briefing=False)
        faults = []
        if ref_value(rig.remote, f"refs/heads/story/{STORY}") is not None:
            faults.append("the story branch was pushed with no briefing to open the PR")
        return judge("pr-briefing-absent-2", got, want=2, marker="briefing-absent",
                     faults=tuple(faults))


def pr_forge_fails_case() -> bool:
    """The act failing after a true verdict: exit 2, the act line in the record, re-entry safe."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rig = build_rig(tmp, terminal="open-pr", remote=True)
        assert rig.remote is not None
        forge_log = tmp / "forge.log"
        forge = executable(tmp / "forge-stub",
                           FORGE_STUB.replace("__LOG__", str(forge_log)).replace("__CODE__", "1"))
        got = run_merge(rig, "merge", forge=forge, briefing=True)
        faults = list(record_faults(rig, contains=("act: open-pr FAILED",)))
        if ref_value(rig.remote, f"refs/heads/story/{STORY}") != rig.candidate:
            faults.append("the push did not land; the forge failure should follow the push")
        if ref_value(rig.remote, "refs/heads/main") != rig.main_sha:
            faults.append("remote main moved, which no chain act may do")
        return judge("pr-forge-fails-2", got, want=2, marker="act-failed", faults=tuple(faults))


def push_main_uncomposable_case() -> bool:
    """The push-scope guard, called directly: main is not a destination any argument composes."""
    name = "push-main-uncomposable"
    sys.path.insert(0, str(HARNESS / "chain"))
    try:
        import merge as merge_mod
        merge_mod.guarded_push
        merge_mod.CouldNotRun
    except (Exception, AttributeError) as e:
        print(f"  FAIL {name}: harness/chain/merge.py does not carry the guard: {e}")
        return False
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td), terminal="open-pr", remote=True)
        assert rig.remote is not None
        before = ref_value(rig.remote, "refs/heads/main")
        faults = []
        for hostile in ("heads/main", "..", "refs/heads/main"):
            try:
                merge_mod.guarded_push(rig.clone, "origin", rig.candidate, hostile,
                                       "branches-only")
                faults.append(f"story id {hostile!r} was accepted as a push destination")
            except merge_mod.CouldNotRun:
                pass
        try:
            merge_mod.guarded_push(rig.clone, "origin", rig.candidate, STORY, "never")
            faults.append("a push went through under push scope 'never'")
        except merge_mod.CouldNotRun:
            pass
        try:
            where = merge_mod.guarded_push(rig.clone, "origin", rig.candidate, "main",
                                           "branches-only")
            if where != "refs/heads/story/main":
                faults.append(f"the composed destination was {where!r}")
        except merge_mod.CouldNotRun as e:
            faults.append(f"the shape-valid id 'main' was refused: {e}")
        if ref_value(rig.remote, "refs/heads/story/main") != rig.candidate:
            faults.append("the composed story/main push did not land where composed")
        if ref_value(rig.remote, "refs/heads/main") != before:
            faults.append("remote main moved: the guard is a hole")
        ok = not faults
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: main is structurally uncomposable"
              + "".join(f" ({f})" for f in faults))
        return ok


def record_in_worktree_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td))
        inside = rig.clone / "merge.record"
        got = run_merge(rig, record=inside)
        faults = () if not inside.exists() else ("the record was written inside a working tree",)
        return judge("record-in-worktree-2", got, want=2, marker="record-refused",
                     faults=faults)


def record_preexists_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        rig = build_rig(Path(td))
        rig.record.parent.mkdir(parents=True)
        rig.record.write_text("PLANTED-BEFORE-THE-RUN\n")
        got = run_merge(rig)
        faults = ()
        if rig.record.read_text() != "PLANTED-BEFORE-THE-RUN\n":
            faults = ("the pre-planted record was overwritten",)
        return judge("record-preexists-2", got, want=2, marker="already exists", faults=faults)


def hostile_gitdir_case() -> bool:
    """`GIT_DIR` names a decoy: the stage must operate on --repo and derive the same verdict."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rig = build_rig(tmp)
        decoy = tmp / "decoy"
        decoy.mkdir()
        (decoy / "README.md").write_text("decoy\n")
        git(decoy, "init", "-q", "-b", "main", ".")
        git(decoy, "config", "user.email", "fixture@example.invalid")
        git(decoy, "config", "user.name", "fixture")
        git(decoy, "add", "-A")
        git(decoy, "commit", "-qm", "decoy")
        env = clean_env()
        env["GIT_DIR"] = str(decoy / ".git")
        env["GIT_WORK_TREE"] = str(decoy)
        env["GIT_INDEX_FILE"] = str(decoy / ".git" / "index")
        got = run_merge(rig, env=env)
        return judge("hostile-gitdir-0", got, want=0, marker="merge_ok holds",
                     faults=tuple(record_faults(rig)))


def main() -> int:
    if not MERGE.is_file():
        print(f"merge_test: tool not found at {MERGE}", file=sys.stderr)
        return 2
    results = [
        pin_premature_case(),
        pin_gap_case(),
        pin_tip_diverged_case(),
        pin_non_ancestor_case(),
        forged_chain_residue_case(),

        trial_conflict_case(),
        git_too_old_case(),

        c2_trusted_touch_case(),
        c2_rename_delete_case(),

        c3_undeclared_case(),
        c3_plan_absent_case(),

        c4_receipt_red_case(),
        c4_receipt_pc_absent_case(),

        c5_refutation_case(),
        c6_park_case(),
        c56_foreign_note_case(),

        c1_check_red_case(),
        c1_check_broken_case(),
        c1_check_dirties_case(),
        c1_check_commits_case(),
        c1_check_untrusted_case(),

        local_cas_and_revert_case(),
        local_main_moved_case(),
        local_checked_out_case(),

        pr_green_case(),
        pr_briefing_absent_case(),
        pr_forge_fails_case(),
        push_main_uncomposable_case(),

        record_in_worktree_case(),
        record_preexists_case(),
        hostile_gitdir_case(),
    ]
    failed = results.count(False)
    print(f"merge_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

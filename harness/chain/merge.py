#!/usr/bin/env python3
"""The merge stage: merge_ok's eight conjuncts, the merge record, and the declared terminal act.

Three decisions of `docs/adrs/ADR-0002-merge-posture.md` become mechanism here, over the pinned
resolution `loader.py` provides, the position derivation `core.py` carries, and the seam pieces
`advance.py` already owns. Nothing here parses JSON, reads a harness stream, or writes any ref
under `refs/chain/` — that namespace is position's, and a self-written park would wedge
conjunct 6 against itself.

D3, THE EIGHT CONJUNCTS, evaluated against the trial merge of ONE pinned candidate sha into the
current local `main`. The candidate is the FINAL phase ref's graded sha, never a branch tip:
`core.position` must be consistent and must equal the caller's declared `--expected-phases`
exactly — fewer graded phases is premature invocation, which is could-not-run and never a
verdict. The story branch must stand at exactly the candidate (a tip past it is ungraded work
riding along, one behind it is a stale ref — either way the named block `candidate-diverged`),
and every phase ref of the current attempt must be an ancestor of the candidate or the
candidate itself. Every conjunct then receives that one sha and the one `refs/heads/main` sha,
resolved once; nothing downstream re-reads a moving name.

THE TRIAL MERGE writes no ref and touches nobody's working tree: `git merge-tree --write-tree`
computes the merged tree in memory from two committed objects (git 2.38 is the floor, gated at
the seam), `git commit-tree` wraps it in a dangling two-parent trial commit — parents
(main-target, candidate), message carrying the `Merged-Story:` trailer, so `revert -m 1`
applies and the revert-sufficiency premise holds — and a scratch worktree is materialized at
the composed path `<pinned_root>/worktrees/<story>/merge-<attempt>` under the same ownership
conditions every other composed path carries: composed, never accepted; not a symlink; no
working tree above. A conflicted trial merge is FAIL, not could-not-run: the instrument ran and
read evidence — the story's diff conflicts with current `main`, reproducible from the two shas
— and the conjuncts that needed the merged tree read could-not-run naming the conflict.

D3.8, SOURCE-SET INTEGRITY, is identity rather than comparison: one tree OID carried through
asserted equalities — the merge-tree output equals the trial commit's tree, equals the scratch
worktree's `HEAD^{tree}` at materialization, equals the same AFTER the commit-path check
completes (porcelain re-read and tree re-assert both, so a check that mutates what it grades is
the named FAIL `graded-tree-dirtied` or `graded-tree-moved`), and under merge-local the commit
written to `main` IS the trial commit, so the tree that advances is that same object. No
per-phase working tree is an input anywhere, so phase-tree dirt cannot reach the merged tree.

THE CONJUNCT ORDER is the cost order, and the expensive one runs last: the pinning, the trial
merge and conjuncts 2 through 6 are cheap reads, and conjunct 1 — the repository's own
commit-path check, judged code executing — runs only when every one of them already passed. An
unevaluated conjunct reads could-not-run naming the upstream reason, never pass. Conjunct 7
re-resolves the two pinned names last of all, immediately before any terminal act, and the
merge-local act is a compare-and-swap against the main-target sha, so a race between that
re-read and the write loses rather than signs.

D5, THE FORGED-REF RESIDUE is consumed rather than closed: the record names it OPEN, with the
blast radius D1 confines it to under the declared terminal act. Tip-equality and phase-ref
ancestry narrow laziness, not capability — both read the same forgeable namespace plus objects
a Bash-holding phase can mint — and a chain forged wholesale that satisfies every conjunct is
this stage passing AS DESIGNED, with the record saying exactly that.

THE MERGE RECORD is written on EVERY exit path once its path is validated: the path is refused
if it sits inside any git working tree (a filesystem walk, spawning no git) and refused if it
already exists, so nothing can pre-plant authorship; before validation the stage speaks on
stderr only. Line-oriented text, never JSON — the future undeclared-testimony court needs a
greppable format. Exactly two `testimony:` lines, ADR-0002/D4's names: the plan declaration
verbatim, and the receipt's per-lens findings. A `not-established:` block names what this stage
does not pin. The scratch worktree is removed only after the record is written.

THE TERMINAL ACTS. merge-local: refuse if `refs/heads/main` is checked out in any worktree of
the clone, then `git update-ref refs/heads/main <trial-commit> <main-target>` — an atomic
compare-and-swap on the sha conjunct 7 just re-read, confirmed from the ref store. open-pr:
push the CANDIDATE by sha through `guarded_push`, then one forge call through an injectable
command seam, with the documenter's briefing required. A chain push of `main` is structurally
uncomposable: every push this stage can perform goes through `guarded_push`, whose destination
is composed as `refs/heads/story/<component-validated-id>` — the component rule forbids `/` and
`..`, so no argument reaches `refs/heads/main` — and which refuses any push at all unless the
declared scope is `branches-only`. The standing courts (merge-posture-check, the start-up
pairing, chain-refspec-check) are the layers behind it; a source court requiring every push
argument to sit inside `guarded_push` is named future, not built here.

WHAT THIS DOES NOT CHECK, stated so it is not mistaken for checked: that any per-phase working
tree matched its recorded sha when graded — phase verdicts stay evaluated-once testimony, and
history-dependent phase properties are never re-derived; under open-pr, the tree the
operator-side merge eventually produces; a liar git on the sequencer's PATH, the
unhardened-checklist gap ADR-0003/D4 names. Each is named in the record's not-established
block, and the phase-level porcelain-once remainder stays disclosed in `advance.py`.

THE EXIT CONTRACT:

    0   merge_ok held, and under `merge` the terminal act completed
    1   merge_ok is false — the park, verdict-shaped; the stage writes no ref on this path
    2   could-not-run, naming the condition — including an act failing after a true verdict
        (push rejected, forge down), which is re-entry safe: the push is by sha and the
        compare-and-swap still guards. An evaluation the instruments could not finish reads
        could-not-run even where a conjunct had already read FAIL — the loader's own dominance
        rule — and the record carries whatever was established either way.

Usage:
    python3 harness/chain/merge.py evaluate --root <kit> --repo <clone> --story <id>
        --expected-phases <n> --commit-check <path> [--plan <path>] [--record <path>]
        [--git <cmd>] [--timeout <seconds>]
    python3 harness/chain/merge.py merge ... the same ... [--remote <name>] [--forge <cmd>]
        [--briefing <file>]

`--root` is the repository whose profile declares the posture; `--repo` is the dedicated clone
holding the story's refs, its branch and `main`. `--commit-check` is the judged repository's
own commit-path check, tree-relative and required under `trusted_base`. `--git` and `--forge`
are injectable command seams; fixtures point them at stubs and never at a real forge.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import advance  # noqa: E402  (resolved from this file's own directory, beside it)
import attempt  # noqa: E402
import core  # noqa: E402
import invoke  # noqa: E402
import loader  # noqa: E402

DONE = 0
FAIL = 1
COULD_NOT_RUN = 2

CouldNotRun = loader.CouldNotRun

GIT_FLOOR = (2, 38)
GIT_VERSION = re.compile(r"([0-9]+)\.([0-9]+)")
OID = re.compile(r"^[0-9a-f]{40,64}$")
RECEIPT = "receipt-complete"
RECORDS = "records"
TRAILER = "Merged-Story"
LISTED = 20
SEAM_TIMEOUT = 120

CONJUNCTS = {
    1: "check-green",
    2: "trusted-base",
    3: "plan-paths",
    4: "receipt",
    5: "no-refutation",
    6: "no-park",
    7: "pinned-sha",
    8: "source-set",
}

RADIUS = {
    "open-pr": "an unearned PR, never a trunk advance",
    "merge-local": "a bad local merge, removed by revert",
}

# The injectable git seam, set once by the CLI before anything runs. Fixtures point it at stubs
# — the old-git arm is testable in no other way — and a liar here is inside the ADR-0003/D4
# checklist gap the record's not-established block already names.
GIT = "git"


class Blocked(Exception):
    """A named block: merge_ok is false for a reason outside the conjunct receipts."""


def say(line: str) -> None:
    print(line, flush=True)


@dataclass(frozen=True)
class Pin:
    """Call A's product: the one candidate sha and the one main sha every conjunct receives."""

    story: str
    attempt: int
    ref: str
    candidate: str
    main: str


@dataclass(frozen=True)
class Trial:
    """The trial merge: the merged tree, the dangling trial commit, the scratch worktree."""

    tree: str
    commit: str
    scratch: Path


@dataclass(frozen=True)
class Conjunct:
    """One receipt line: id, verdict, the evidence read, and where it was read from."""

    number: int
    verdict: str
    evidence: str
    source: str


@dataclass
class State:
    """Everything the record renders, accumulated so every exit path can write it."""

    stage: str
    story: str
    terminal: str = "(undeclared)"
    repo: Path | None = None
    record_path: Path | None = None
    pin: Pin | None = None
    trial: Trial | None = None
    trial_note: str | None = None
    scratch: Path | None = None
    blocks: list[str] = field(default_factory=list)
    conjuncts: dict[int, Conjunct] = field(default_factory=dict)
    plan_testimony: str | None = None
    receipt_testimony: str | None = None
    foreign: tuple[str, ...] = ()
    act_line: str | None = None
    stop: str | None = None


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the seam's git against `repo` with the caller's own git environment dropped.

    `loader.child_env(None)` is the shared scrub: git reads `GIT_DIR` in preference to `-C`, so
    a stage invoked from a hook would otherwise evaluate the caller's repository and advance a
    ref there.
    """
    try:
        return subprocess.run(
            [GIT, "-C", str(repo), *args],
            capture_output=True,
            text=True,
            env=loader.child_env(None),
        )
    except OSError as e:
        raise CouldNotRun(f"git could not be run against {repo}: {e}") from e


def git_version_gate() -> str:
    """The trial merge needs `merge-tree --write-tree`; a git that predates it runs nothing."""
    try:
        done = subprocess.run([GIT, "version"], capture_output=True, text=True,
                              errors="replace", env=loader.child_env(None),
                              timeout=SEAM_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError) as e:
        raise CouldNotRun(f"git-unread: {GIT} version could not be read: {e}") from e
    found = GIT_VERSION.search(done.stdout)
    if done.returncode != 0 or not found:
        raise CouldNotRun(f"git-unread: {GIT} version exited {done.returncode} printing "
                          f"{done.stdout.strip()[:80]!r}, which carries no version number")
    pair = (int(found.group(1)), int(found.group(2)))
    if pair < GIT_FLOOR:
        raise CouldNotRun(
            f"git-too-old: {GIT} is {found.group(0)}, and the trial merge needs merge-tree "
            f"--write-tree, which arrived in {GIT_FLOOR[0]}.{GIT_FLOOR[1]}; nothing was merged "
            "and nothing was judged"
        )
    return found.group(0)


def resolve(repo: Path, ref: str) -> str | None:
    """The commit `ref` names right now, or None: the pinning decides what absence means."""
    done = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    sha = done.stdout.strip()
    return sha if done.returncode == 0 and sha else None


def porcelain(repo: Path) -> list[str]:
    done = git(repo, "status", "--porcelain")
    if done.returncode != 0:
        raise CouldNotRun(f"the tree state of {repo} could not be read: {done.stderr.strip()}")
    return [line for line in done.stdout.splitlines() if line.strip()]


def capped(items: list[str]) -> str:
    """A named cap: the first LISTED entries, with the remainder counted rather than dropped."""
    listed = "; ".join(items[:LISTED])
    more = "" if len(items) <= LISTED else f" (and {len(items) - LISTED} more)"
    return f"{listed}{more}"


def trusted(path: str, base: tuple[str, ...]) -> bool:
    """The prefix semantics `core.declared_trusted_base` applies to the sequencer's sources."""
    return any(path == prefix or path.startswith(prefix) for prefix in base)


def flat(text: str) -> str:
    """A transcript flattened onto one greppable record line, its cap named at the cut."""
    joined = " | ".join(line.strip() for line in text.splitlines() if line.strip())
    return joined if len(joined) <= 2000 else joined[:2000] + " (capped at 2000 characters)"


def armed_record(path: Path) -> Path:
    """The record path, validated before anything else touches the world.

    Inside a working tree is refused because a judged or grading tree could carry the record
    away or diff against it; an existing file is refused because a pre-planted record is
    authorship nobody ran. The walk spawns no git: the tool being defended against must not be
    the tool that answers.
    """
    holder = loader.working_tree_above(path.parent)
    if holder is not None:
        raise CouldNotRun(
            f"record-refused: {path} sits inside the git working tree at {holder}, and the "
            "record never lands inside a tree any judged party can write"
        )
    if path.exists():
        raise CouldNotRun(f"record-refused: {path} already exists, and a pre-planted record is "
                          "authorship nobody ran; the stage writes each record exactly once")
    return path


def pinned_candidate(repo: Path, story: str, expected: int) -> Pin:
    """Call A: position, the final phase ref, tip-equality, and phase-ref ancestry."""
    here = core.position(repo, story)
    core.report(here)
    core.consistent(here)
    if here.attempt == 0 or here.phase < expected:
        raise CouldNotRun(
            f"premature-invocation: position reads attempt {here.attempt} phase {here.phase} "
            f"and the caller declared {expected} phase(s); fewer graded phases than declared is "
            "premature invocation, never a verdict (ADR-0002/D3)"
        )
    if here.phase > expected:
        raise CouldNotRun(
            f"phase-declaration-stale: position reads phase {here.phase} of attempt "
            f"{here.attempt} where the caller declared {expected}; the declaration must equal "
            "the chain exactly, so one of the two is about the wrong story"
        )
    ref = f"refs/chain/{story}/attempt-{here.attempt}/phase-{expected}"
    candidate = resolve(repo, ref)
    if candidate is None:
        raise CouldNotRun(f"{ref} does not resolve to a commit in {repo}")
    main = resolve(repo, "refs/heads/main")
    if main is None:
        raise CouldNotRun(f"refs/heads/main does not resolve in {repo}, so there is nothing to "
                          "merge into")
    branch = f"refs/heads/story/{story}"
    tip = resolve(repo, branch)
    if tip is None:
        raise CouldNotRun(f"story-branch-absent: {branch} does not resolve in {repo}, so "
                          "tip-equality cannot be established")
    if tip != candidate:
        raise Blocked(
            f"candidate-diverged: {branch} stands at {tip} and the final phase ref {ref} "
            f"graded {candidate}; a tip past the candidate is ungraded work riding along, one "
            "behind it is a stale ref, and neither is mergeable (ADR-0002/D3.7)"
        )
    ancestry(repo, story, here.attempt, candidate)
    return Pin(story=story, attempt=here.attempt, ref=ref, candidate=candidate, main=main)


def ancestry(repo: Path, story: str, number: int, candidate: str) -> None:
    """Every phase ref of the current attempt sits on the story's own history.

    With tip-equality this is ADR-0002/D5's cheap structural narrowing, and its honest bound is
    stated where the record names the residue: both read the same forgeable namespace plus
    objects a Bash-holding phase can mint, so they narrow laziness, not capability.
    """
    for name, sha in attempt.attempt_refs(repo, story, str(number)):
        if not core.PHASE_REF.match(name) or sha == candidate:
            continue
        done = git(repo, "merge-base", "--is-ancestor", sha, candidate)
        if done.returncode == 0:
            continue
        if done.returncode == 1:
            raise Blocked(
                f"phase-ref-ancestry: {name} at {sha} is not an ancestor of the candidate "
                f"{candidate}, so it grades something off the story's history (ADR-0002/D5)"
            )
        raise CouldNotRun(f"the ancestry of {name} could not be read: {done.stderr.strip()}")


def merged_tree(repo: Path, pin: Pin) -> str:
    """Step one of the trial merge: the merged tree OID, in memory, or the named conflict.

    The parse is grounded in the measured output shape at git 2.43: exit 0 prints the tree OID
    alone; exit 1 prints the OID, then one conflicted filename per line under `--name-only`,
    then a blank line before the informational messages.
    """
    done = git(repo, "merge-tree", "--write-tree", "--name-only", pin.main, pin.candidate)
    lines = done.stdout.splitlines()
    if done.returncode == 0:
        oid = lines[0].strip() if lines else ""
        if not OID.match(oid):
            raise CouldNotRun(f"merge-tree exited 0 printing {done.stdout.strip()[:80]!r}, "
                              "which is not a tree OID")
        return oid
    if done.returncode == 1:
        names: list[str] = []
        for line in lines[1:]:
            if not line.strip():
                break
            if line.strip() not in names:
                names.append(line.strip())
        raise Blocked(
            f"trial-merge-conflict: the story's diff conflicts with current main at "
            f"{len(names)} path(s): {capped(names)} — reproducible from {pin.main} and "
            f"{pin.candidate}"
        )
    raise CouldNotRun(f"merge-tree exited {done.returncode}: {done.stderr.strip()[:200]}; "
                      "neither a merge nor a conflict was observed")


def trial_commitment(repo: Path, pin: Pin, tree: str) -> str:
    """Step two: the dangling trial commit, its tree asserted equal to the merge-tree output."""
    message = f"Merge story/{pin.story} into main\n\n{TRAILER}: {pin.story}"
    done = git(repo, "commit-tree", tree, "-p", pin.main, "-p", pin.candidate, "-m", message)
    sha = done.stdout.strip()
    if done.returncode != 0 or not OID.match(sha):
        raise CouldNotRun(f"commit-tree over {tree} exited {done.returncode}: "
                          f"{done.stderr.strip()[:200]}")
    seen = git(repo, "rev-parse", f"{sha}^{{tree}}").stdout.strip()
    if seen != tree:
        raise CouldNotRun(f"the trial commit {sha} carries tree {seen}, not the merged {tree}, "
                          "so the identity chain broke at its first link")
    return sha


def scratch_path(pinned: Path, story: str, number: int) -> Path:
    """Where the scratch worktree lives: composed from the pinned root, never accepted."""
    return invoke.worktree_root(pinned) / story / f"merge-{number}"


def cleared_scratch(repo: Path, path: Path) -> Path:
    """The composed scratch path, cleared under the sequencer's own authority.

    The conditions are `core.owned`'s, re-stated at this composed path for the reason
    `invoke.cleared_home` re-states them: that function is attempt-shaped and this leaf is
    merge-shaped, and the authority argument does not change with the leaf's name. The
    structural retry after `attempt.clear_worktree`'s one refusal is `core.clear_owned`'s.
    """
    if path.is_symlink():
        raise CouldNotRun(f"{path} is a symlink, and what a link names is not the sequencer's "
                          "to clear")
    holder = loader.working_tree_above(path.parent)
    if holder is not None:
        raise CouldNotRun(f"{path} sits inside the git working tree at {holder}, so clearing "
                          "it could remove graded or examiner material (ADR-0004/D2)")
    try:
        attempt.clear_worktree(argparse.Namespace(repo=str(repo), path=str(path)))
        return path
    except CouldNotRun as refused:
        registered = [w for w in attempt.registered_worktrees(repo)
                      if attempt.same_path(w, path)]
        if registered or not path.exists():
            raise
        say(f"merge: clearing {path} under the sequencer's own authority, which held "
            f"{core.inventory(path)}")
        shutil.rmtree(path)
        if path.exists():
            raise CouldNotRun(f"{path} survived the clearing ({refused})") from refused
        attempt.clear_worktree(argparse.Namespace(repo=str(repo), path=str(path)))
        return path


def materialized_scratch(repo: Path, pinned: Path, pin: Pin, commit: str, tree: str,
                         state: State) -> Path:
    """Step three: the scratch worktree, its tree and cleanliness asserted at materialization."""
    path = cleared_scratch(repo, scratch_path(pinned, pin.story, pin.attempt))
    path.parent.mkdir(parents=True, exist_ok=True)
    done = git(repo, "worktree", "add", "--detach", "-q", str(path), commit)
    if done.returncode != 0:
        raise CouldNotRun(f"scratch-uncreated: git worktree add at {path} exited "
                          f"{done.returncode}: {done.stderr.strip()}")
    state.scratch = path
    seen = git(path, "rev-parse", "HEAD^{tree}").stdout.strip()
    if seen != tree:
        raise CouldNotRun(f"scratch-tree-mismatch: {path} materialized tree {seen} where the "
                          f"merged tree is {tree}, so what would be judged is not what would "
                          "merge")
    dirt = porcelain(path)
    if dirt:
        raise CouldNotRun(f"scratch-dirty: {path} is not clean at materialization: "
                          f"{capped(dirt)}")
    say(f"merge: scratch worktree at {path}, tree {tree}")
    return path


def story_diff(repo: Path, pin: Pin) -> tuple[str, ...]:
    """The cumulative story diff, merge-base to candidate, both rename sides visible."""
    based = git(repo, "merge-base", pin.main, pin.candidate)
    mb = based.stdout.strip()
    if based.returncode != 0 or not OID.match(mb):
        raise CouldNotRun(f"the merge-base of {pin.main} and {pin.candidate} could not be "
                          f"read: {based.stderr.strip()}")
    done = git(repo, "diff", "--no-renames", "--name-only", mb, pin.candidate)
    if done.returncode != 0:
        raise CouldNotRun(f"the cumulative diff could not be read: {done.stderr.strip()}")
    return tuple(line.strip() for line in done.stdout.splitlines() if line.strip())


def conjunct_trusted_base(diff: tuple[str, ...], base: tuple[str, ...]) -> Conjunct:
    """D3.2: the cumulative diff touches no trusted-base path, rename sides included."""
    source = "git diff --no-renames --name-only, merge-base to candidate"
    touched = [p for p in diff if trusted(p, base)]
    if touched:
        return Conjunct(2, "FAIL", "the cumulative diff touches trusted-base path(s) "
                        f"{capped(touched)} (ADR-0002/D3.2)", source)
    return Conjunct(2, "pass", f"{len(diff)} diff path(s) against {len(base)} trusted "
                    "prefix(es), none trusted", source)


def conjunct_plan(diff: tuple[str, ...], plan: str | None, state: State) -> Conjunct:
    """D3.3: the declaration covers the diff, and is carried verbatim as testimony."""
    source = "the declared path list, reconciled against the same diff conjunct 2 read"
    if plan is None:
        return Conjunct(3, "could-not-run", "plan-absent: no declared path list was supplied, "
                        "and a reconciliation with no declaration is not evidence (fail-closed "
                        "until a plan-paths producer exists)", source)
    path = Path(plan)
    if not path.is_file():
        return Conjunct(3, "could-not-run", f"plan-absent: {path} is not a file", source)
    declared = tuple(line.strip() for line in path.read_text(errors="replace").splitlines()
                     if line.strip() and not line.strip().startswith("#"))
    state.plan_testimony = " ".join(declared) if declared else "(an empty declaration)"
    undeclared = [p for p in diff if p not in declared]
    if undeclared:
        return Conjunct(3, "FAIL", f"the diff touches {len(undeclared)} path(s) the plan never "
                        f"declared: {capped(undeclared)} (ADR-0002/D3.3)", source)
    return Conjunct(3, "pass", f"the declaration of {len(declared)} path(s) covers all "
                    f"{len(diff)} diff path(s)", source)


def conjunct_receipt(root: Path, trial: Trial | None, note: str | None, timeout: int,
                     state: State) -> Conjunct:
    """D3.4: the reviewer's receipt, read by a pinned postcondition at the merged tree."""
    source = f"the pinned postcondition {RECEIPT!r}, demonstrated red and green on load"
    if trial is None:
        return Conjunct(4, "could-not-run", f"the merged tree does not exist ({note}), so the "
                        "receipt was not read against it", source)
    try:
        found = loader.load(root, RECEIPT, timeout=timeout, say=say)
    except CouldNotRun as e:
        return Conjunct(4, "could-not-run", str(e), source)
    except loader.DemonstrationFailed as e:
        return Conjunct(4, "could-not-run", f"the examiner is broken, which is not a fact "
                        f"about the story: {e}", source)
    try:
        code, transcript = advance.seam_run(found, trial.scratch, timeout)
    except CouldNotRun as e:
        return Conjunct(4, "could-not-run", str(e), source)
    state.receipt_testimony = flat(transcript) or "(the receipt reader printed nothing)"
    if code == 0:
        return Conjunct(4, "pass", "the coverage receipt is present and complete at the merged "
                        "tree (exit 0)", source)
    if code == 1:
        return Conjunct(4, "FAIL", "the coverage receipt is absent or short at the merged tree "
                        "(exit 1) (ADR-0002/D3.4, D4)", source)
    return Conjunct(4, "could-not-run", f"the receipt reader exited {code}, outside the 0/1 "
                    "contract", source)


def ref_court(repo: Path, story: str, state: State) -> tuple[Conjunct, Conjunct]:
    """D3.5 and D3.6: refutation and park refs, with foreign refs named and left alone."""
    source = f"git for-each-ref over refs/chain/{story}/"
    names = core.story_refs(repo, story)
    refutations = [n for n in names if n.startswith(f"refs/chain/{story}/refutation")]
    parks = [n for n in names if n.startswith(f"refs/chain/{story}/park")]
    claimed = set(refutations) | set(parks)
    state.foreign = tuple(n for n in names
                          if n not in claimed and not core.PHASE_REF.match(n))
    five = (Conjunct(5, "FAIL", f"undisposed refutation ref(s) stand: {capped(refutations)} "
                     "(ADR-0002/D3.5)", source)
            if refutations else Conjunct(5, "pass", "no refutation ref stands", source))
    six = (Conjunct(6, "FAIL", f"park ref(s) stand: {capped(parks)} (ADR-0002/D3.6)", source)
           if parks else Conjunct(6, "pass", "no park ref stands", source))
    return five, six


def unrun(number: int, reason: str, source: str) -> Conjunct:
    return Conjunct(number, "could-not-run", reason, source)


def conjunct_check(check: str, base: tuple[str, ...], trial: Trial | None, hold: str | None,
                   timeout: int, state: State) -> tuple[Conjunct, bool]:
    """D3.1, evaluated last: the repository's own commit-path check, inside the scratch.

    Returns the receipt and whether the check actually executed, because conjunct 8's
    post-check half is meaningful exactly when it did — a check that returned any exit code may
    have written into the tree it graded, and one that never ran cannot have.
    """
    source = f"the repository's own commit-path check {check!r}, run inside the scratch"
    if trial is None:
        return unrun(1, f"the merged tree does not exist ({state.trial_note}); nothing was "
                     "judged", source), False
    if hold is not None:
        return unrun(1, f"not run: {hold}; judged code executes only over a tree everything "
                     "cheaper already cleared", source), False
    if Path(check).is_absolute() or ".." in Path(check).parts:
        return unrun(1, f"check-untrusted: {check!r} is not a tree-relative path", source), False
    if not trusted(check, base):
        return unrun(1, f"check-untrusted: {check!r} is under no trusted-base prefix, so the "
                     "story could have supplied the check that clears it (ADR-0002/D3.2)",
                     source), False
    target = trial.scratch / check
    if not target.is_file():
        return unrun(1, f"check-absent: the merged tree carries no {check}", source), False
    try:
        done = subprocess.run([str(target)], cwd=str(trial.scratch),
                              env=loader.child_env(None), capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return unrun(1, f"the check did not return within {timeout}s", source), False
    except OSError as e:
        return unrun(1, f"the check could not be executed: {e}", source), False
    for line in (done.stdout + done.stderr).splitlines():
        say(f"merge: check| {line}")
    if done.returncode == 0:
        return Conjunct(1, "pass", "the commit-path check is green at the merged tree (exit 0) "
                        "(ADR-0002/D3.1)", source), True
    if done.returncode == 1:
        return Conjunct(1, "FAIL", "the commit-path check reads FAIL at the merged tree "
                        "(exit 1) (ADR-0002/D3.1)", source), True
    return unrun(1, f"the check exited {done.returncode}, outside the canonical contract, so "
                 "the seam observed no verdict (ADR-0003/D2)", source), True


def conjunct_source_set(trial: Trial | None, ran: bool, hold: str | None,
                        state: State) -> Conjunct:
    """D3.8: the identity chain's post-check half — porcelain re-read AND tree re-assert."""
    source = "one tree OID asserted at each link of the identity chain"
    if trial is None:
        return unrun(8, f"the merged tree does not exist ({state.trial_note})", source)
    if not ran:
        return unrun(8, f"the post-check half of the chain never happened: "
                     f"{hold or 'the check did not run'}", source)
    dirt = porcelain(trial.scratch)
    if dirt:
        return Conjunct(8, "FAIL", f"graded-tree-dirtied: the check left the scratch dirty at "
                        f"{capped(dirt)}, so the tree it graded is not the tree that would "
                        "merge (ADR-0002/D3.8)", source)
    seen = git(trial.scratch, "rev-parse", "HEAD^{tree}").stdout.strip()
    if seen != trial.tree:
        return Conjunct(8, "FAIL", f"graded-tree-moved: the scratch reads tree {seen} after "
                        f"the check where the merged tree is {trial.tree} (ADR-0002/D3.8)",
                        source)
    return Conjunct(8, "pass", f"tree {trial.tree} carried through merge-tree = commit-tree = "
                    "scratch at materialization = scratch after the check", source)


def conjunct_pinned(repo: Path, pin: Pin) -> Conjunct:
    """D3.7: the two pinned names re-resolve unchanged, read immediately before any act."""
    source = "the two pinned names re-resolved immediately before any act"
    moved = []
    now_candidate = resolve(repo, pin.ref)
    now_main = resolve(repo, "refs/heads/main")
    if now_candidate != pin.candidate:
        moved.append(f"{pin.ref} moved from {pin.candidate} to {now_candidate or 'nothing'}")
    if now_main != pin.main:
        moved.append(f"refs/heads/main moved from {pin.main} to {now_main or 'nothing'}")
    if moved:
        return Conjunct(7, "FAIL", "; ".join(moved) + " between evaluation and the act, which "
                        "fails and re-walks (ADR-0002/D3.7)", source)
    return Conjunct(7, "pass", f"candidate {pin.candidate} and main {pin.main} re-resolve "
                    "unchanged", source)


def checked_out_main(repo: Path) -> str | None:
    """Where `refs/heads/main` is checked out in any worktree of the clone, if anywhere."""
    done = git(repo, "worktree", "list", "--porcelain")
    if done.returncode != 0:
        raise CouldNotRun(f"the worktree list of {repo} could not be read: "
                          f"{done.stderr.strip()}")
    where = str(repo)
    for line in done.stdout.splitlines():
        if line.startswith("worktree "):
            where = line.split(" ", 1)[1]
        if line.strip() == "branch refs/heads/main":
            return where
    return None


def guarded_push(repo: Path, remote: str, sha: str, story: str, push_scope: str) -> str:
    """THE ONE PUSH PATH, and `main` is not a destination any argument composes.

    Layer one is the refspec shape: the destination is composed as
    `refs/heads/story/<component-validated-id>`, and `attempt.component` forbids `/` and `..`,
    so no story id reaches `refs/heads/main` — the worst a hostile id can name is a story
    branch. Layer two is the declared scope: nothing pushes unless the posture says
    `branches-only`, which under merge-local means nothing pushes at all. Layer three is the
    standing courts outside this function. The push is by sha with a full explicit refspec, so
    a configured push default cannot widen it and a remote already at another sha refuses the
    non-fast-forward rather than moving.
    """
    if push_scope != "branches-only":
        raise CouldNotRun(
            f"push-refused: the declared push scope is {push_scope!r}, and nothing pushes "
            "under it; only 'branches-only' pushes at all, and only story branches "
            "(ADR-0002/D1)"
        )
    where = f"refs/heads/story/{attempt.component('story id', story)}"
    done = git(repo, "push", remote, f"{sha}:{where}")
    if done.returncode != 0:
        raise CouldNotRun(
            f"push-failed: the push of {sha} to {remote} {where} exited {done.returncode}: "
            f"{done.stderr.strip()[:200]}; re-entry is safe — the push is by sha, and a remote "
            "at another sha refuses the non-fast-forward"
        )
    return where


def act_merge_local(repo: Path, pin: Pin, trial: Trial, state: State) -> None:
    """The merge-local act: a compare-and-swap advance of the local main, confirmed."""
    held = checked_out_main(repo)
    if held is not None:
        raise CouldNotRun(
            f"main-checked-out: refs/heads/main is checked out at {held}, so advancing it "
            "would desynchronize a live working tree; detach it and re-run"
        )
    done = git(repo, "update-ref", "refs/heads/main", trial.commit, pin.main)
    if done.returncode != 0:
        state.act_line = (f"act: merge-local FAILED: the compare-and-swap exited "
                          f"{done.returncode}: {done.stderr.strip()[:200]}")
        raise CouldNotRun(
            f"act-failed: update-ref refs/heads/main {trial.commit} against old value "
            f"{pin.main} exited {done.returncode}: {done.stderr.strip()[:200]}; re-entry is "
            "safe, the trial commit is reproducible from the two pinned shas"
        )
    written = advance.stored_ref(repo, "refs/heads/main")
    if written != trial.commit:
        state.act_line = (f"act: merge-local FAILED: the ref store holds "
                          f"{written or 'nothing'} after the write")
        raise CouldNotRun(f"act-failed: the ref store of {repo} holds {written or 'nothing'} "
                          f"for refs/heads/main after the write, not {trial.commit}")
    state.act_line = (f"act: merge-local: refs/heads/main advanced {pin.main} -> {trial.commit} "
                      f"by compare-and-swap; the committed tree is {trial.tree} and the message "
                      f"carries {TRAILER}: {pin.story}")


def act_open_pr(repo: Path, pin: Pin, push_scope: str, remote: str, forge: str,
                briefing: Path, state: State) -> None:
    """The open-pr act: push the candidate by sha, then one forge call through the seam."""
    where = guarded_push(repo, remote, pin.candidate, pin.story, push_scope)
    say(f"merge: pushed {pin.candidate} to {remote} {where} by explicit refspec")
    argv = [forge, "pr", "create", "--head", f"story/{pin.story}",
            "--title", f"{pin.story}: the chain's merge candidate",
            "--body-file", str(briefing)]
    say(f"merge: forge: {' '.join(argv)}")
    try:
        done = subprocess.run(argv, capture_output=True, text=True,
                              env=loader.child_env(None), timeout=SEAM_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError) as e:
        state.act_line = (f"act: open-pr FAILED: pushed {pin.candidate} to {remote} {where}, "
                          f"then the forge call could not run: {e}")
        raise CouldNotRun(f"act-failed: the forge call could not run after the push: {e}; "
                          "re-entry is safe, the push is by sha and the PR can be opened by "
                          "hand") from e
    if done.returncode != 0:
        state.act_line = (f"act: open-pr FAILED: pushed {pin.candidate} to {remote} {where}, "
                          f"then the forge call exited {done.returncode}: "
                          f"{(done.stderr or done.stdout).strip()[:200]}")
        raise CouldNotRun(f"act-failed: the forge call exited {done.returncode} after the "
                          "push; re-entry is safe, the push is by sha and the PR can be opened "
                          "by hand")
    state.act_line = (f"act: open-pr: pushed {pin.candidate} to {remote} {where} by explicit "
                      "refspec, then one forge call opened the PR against it")


def residue_line(story: str, terminal: str) -> str:
    """The record's forged-ref line, ADR-0002/D5's consumption rule made verbatim and greppable."""
    radius = RADIUS.get(terminal, "no terminal act is declared, so no act can run")
    return ("residue: forged-ref OPEN (ADR-0001/D1, ADR-0002/D5): the candidate was selected "
            f"by position over refs/chain/{story}/*, a namespace any Bash-holding phase can "
            "write; conjuncts 5 and 6 read the same forgeable namespace, so a deleted "
            "refutation or park ref is invisible here; narrowed by tip-equality and phase-ref "
            "ancestry, not closed; closure is the containment-posture record's. Blast radius "
            f"under terminal = {terminal}: {radius}.")


def not_established(state: State) -> list[str]:
    foreign = ", ".join(state.foreign) if state.foreign else "none seen"
    return [
        "not-established: that any per-phase working tree matched its recorded sha when graded "
        "— phase verdicts stay evaluated-once testimony, merge-relevant content is re-graded "
        "by conjunct 1 at the merged tree, and history-dependent phase properties are never "
        "re-derived",
        "not-established: under open-pr, the tree the operator-side merge eventually produces "
        "(a moved main, a squash) — the operator court, ADR-0002/D1",
        "not-established: a liar git on the sequencer's PATH — the unhardened-checklist gap "
        "ADR-0003/D4 names; not re-claimed here",
        "not-established: the phase-level porcelain-once remainder stays disclosed in "
        "harness/chain/advance.py; this stage re-reads porcelain only in its own scratch",
        f"not-established: foreign ref(s) left alone, neither phase nor park nor refutation: "
        f"{foreign}",
        "not-established: the record itself sits on an unhardened path until the operator "
        "checklist runs; pre-planting is refused, and no agent runs during or after the merge "
        "stage within an attempt",
    ]


def merge_ok_word(state: State) -> str:
    if state.blocks or any(c.verdict == "FAIL" for c in state.conjuncts.values()):
        return "false"
    if len(state.conjuncts) == 8 and all(c.verdict == "pass"
                                         for c in state.conjuncts.values()):
        return "true"
    return "not-established"


def render(state: State, code: int) -> str:
    lines = [f"merge-record: {state.story} ({state.stage}, terminal {state.terminal})"]
    if state.pin is not None:
        lines.append(f"candidate: {state.pin.candidate} from {state.pin.ref}")
        lines.append(f"main-target: {state.pin.main} from refs/heads/main")
    else:
        why = state.stop or "the stage stopped before the pinning"
        lines.append(f"candidate: none pinned ({why})")
        lines.append("main-target: none pinned")
    if state.trial is not None:
        lines.append(f"trial-tree: {state.trial.tree}")
        lines.append(f"trial-commit: {state.trial.commit}")
    else:
        note = state.trial_note or state.stop or "the stage stopped before the trial merge"
        lines.append(f"trial-tree: none ({note})")
        lines.append(f"trial-commit: none ({note})")
    for block in state.blocks:
        lines.append(f"block: {block}")
    for n in range(1, 9):
        held = state.conjuncts.get(n)
        if held is None:
            why = state.stop or (state.blocks[0] if state.blocks else "not evaluated")
            lines.append(f"conjunct {n} {CONJUNCTS[n]}: could-not-run — not evaluated: {why}")
        else:
            lines.append(f"conjunct {n} {CONJUNCTS[n]}: {held.verdict} — {held.evidence} "
                         f"[source: {held.source}]")
    lines.append(f"merge_ok: {merge_ok_word(state)}")
    lines.append("testimony: plan-declaration: "
                 + (state.plan_testimony or "(none read; conjunct 3 could not run)"))
    lines.append("testimony: receipt-findings: "
                 + (state.receipt_testimony or "(none read; conjunct 4 could not run)"))
    lines.append(residue_line(state.story, state.terminal))
    lines += not_established(state)
    if state.act_line is not None:
        lines.append(state.act_line)
    elif state.stage == "evaluate":
        lines.append("act: none (evaluate evaluates; no act was requested)")
    else:
        lines.append("act: none (no act ran)")
    lines.append(f"exit: {code}")
    return "\n".join(lines) + "\n"


def body(a: argparse.Namespace, do_act: bool, story: str, expected: int, state: State) -> int:
    root = Path(a.root).resolve()
    posture = core.startup(root)
    state.terminal = posture.terminal
    repo = attempt.working_tree(Path(a.repo).resolve())
    state.repo = repo
    if do_act and posture.terminal == "open-pr":
        if not a.briefing or not Path(a.briefing).is_file():
            raise CouldNotRun(
                "briefing-absent: open-pr opens the PR with the documenter's briefing as its "
                "body, and none was supplied; could-not-run until the documenter exists"
            )
    git_version_gate()
    pin = pinned_candidate(repo, story, expected)
    state.pin = pin
    if state.record_path is None:
        state.record_path = armed_record(
            posture.pinned_root / RECORDS / story / f"merge-{pin.attempt}.record")
    say(f"merge: candidate {pin.candidate} from {pin.ref}; main-target {pin.main}")

    trial: Trial | None = None
    try:
        tree = merged_tree(repo, pin)
    except Blocked as conflicted:
        state.blocks.append(str(conflicted))
        state.trial_note = "trial-merge-conflict"
        say(f"merge: {conflicted}")
    else:
        commit = trial_commitment(repo, pin, tree)
        scratch = materialized_scratch(repo, posture.pinned_root, pin, commit, tree, state)
        trial = Trial(tree=tree, commit=commit, scratch=scratch)
        state.trial = trial

    diff = story_diff(repo, pin)
    state.conjuncts[2] = conjunct_trusted_base(diff, posture.trusted_base)
    state.conjuncts[3] = conjunct_plan(diff, a.plan, state)
    state.conjuncts[4] = conjunct_receipt(root, trial, state.trial_note, a.timeout, state)
    five, six = ref_court(repo, story, state)
    state.conjuncts[5] = five
    state.conjuncts[6] = six

    hold = state.blocks[0][:120] if state.blocks else None
    if hold is None:
        for n in (2, 3, 4, 5, 6):
            if state.conjuncts[n].verdict != "pass":
                hold = (f"conjunct {n} {CONJUNCTS[n]} read "
                        f"{state.conjuncts[n].verdict}")
                break
    one, ran = conjunct_check(a.commit_check, posture.trusted_base, trial, hold, a.timeout,
                              state)
    state.conjuncts[1] = one
    state.conjuncts[8] = conjunct_source_set(trial, ran, hold, state)
    state.conjuncts[7] = conjunct_pinned(repo, pin)

    for n in range(1, 9):
        held = state.conjuncts[n]
        say(f"merge: conjunct {n} {CONJUNCTS[n]}: {held.verdict} — {held.evidence}")

    word = merge_ok_word(state)
    if word == "false":
        print("merge: FAIL: merge_ok is false — the story parks; no ref written",
              file=sys.stderr)
        return FAIL
    if word == "not-established":
        held_back = [f"conjunct {n}" for n in range(1, 9)
                     if state.conjuncts[n].verdict == "could-not-run"]
        print(f"merge: VOID: merge_ok is not established — {', '.join(held_back)} could not "
              "run; not a pass and not a park", file=sys.stderr)
        return COULD_NOT_RUN
    say("merge: merge_ok holds: all eight conjuncts pass against the pinned candidate")
    if not do_act:
        return DONE
    if posture.terminal == "merge-local":
        if trial is None:
            raise CouldNotRun("the merged tree is gone although all eight conjuncts passed, "
                              "which conjunct 8 exists to make impossible; nothing acted")
        act_merge_local(repo, pin, trial, state)
    else:
        act_open_pr(repo, pin, posture.push, a.remote, a.forge, Path(a.briefing), state)
    say(f"merge: {state.act_line}")
    return DONE


def write_record(state: State, code: int) -> None:
    if state.record_path is None:
        return
    state.record_path.parent.mkdir(parents=True, exist_ok=True)
    state.record_path.write_text(render(state, code))
    say(f"merge: record written to {state.record_path}")


def cleanup_scratch(state: State) -> None:
    """The scratch worktree goes, AFTER the record: a leftover is loud, never verdict-shaped."""
    if state.scratch is None or state.repo is None:
        return
    try:
        attempt.clear_worktree(argparse.Namespace(repo=str(state.repo),
                                                  path=str(state.scratch)))
        say(f"merge: scratch worktree at {state.scratch} removed after the record")
    except CouldNotRun as e:
        print(f"merge: the scratch worktree at {state.scratch} was not removed: {e}; the "
              "record is already written and the verdict stands", file=sys.stderr)


def run_stage(a: argparse.Namespace, do_act: bool) -> int:
    story = attempt.component("story id", a.story)
    expected = int(attempt.positive("expected-phases", a.expected_phases))
    state = State(stage="merge" if do_act else "evaluate", story=story)
    if a.record:
        state.record_path = armed_record(Path(a.record).resolve())
    code = COULD_NOT_RUN
    wrote = True
    try:
        code = body(a, do_act, story, expected, state)
    except Blocked as e:
        state.blocks.append(str(e))
        state.stop = str(e)[:160]
        print(f"merge: FAIL: {e}; merge_ok is false and the story parks; no ref written",
              file=sys.stderr)
        code = FAIL
    except CouldNotRun as e:
        state.stop = str(e)[:160]
        print(f"merge: VOID: {e}; not a merge and not a verdict", file=sys.stderr)
        code = COULD_NOT_RUN
    except OSError as e:
        state.stop = f"a filesystem read failed: {e}"
        print(f"merge: VOID: a filesystem read failed: {e}", file=sys.stderr)
        code = COULD_NOT_RUN
    finally:
        try:
            write_record(state, code)
        except OSError as e:
            wrote = False
            print(f"merge: VOID: the record could not be written to {state.record_path}: {e}",
                  file=sys.stderr)
        cleanup_scratch(state)
    if not wrote and code == DONE:
        return COULD_NOT_RUN
    return code


def main() -> int:
    global GIT
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="act", required=True)
    for name, help_text, doing in (
        ("evaluate", "all eight conjuncts and the record, no act", False),
        ("merge", "evaluate, then the declared terminal act", True),
    ):
        one = sub.add_parser(name, help=help_text)
        one.add_argument("--root", required=True, help="the repository declaring the posture")
        one.add_argument("--repo", required=True,
                         help="the dedicated clone holding the story's refs and main")
        one.add_argument("--story", required=True, help="the story id, one ref component")
        one.add_argument("--expected-phases", required=True,
                         help="the phase count the caller declares this story's chain to have")
        one.add_argument("--commit-check", required=True,
                         help="the repository's own commit-path check, tree-relative, under "
                              "trusted_base")
        one.add_argument("--plan", help="the declared path list; absent reads conjunct 3 "
                                        "could-not-run")
        one.add_argument("--record", help="where the record lands; the default is composed "
                                          "under the pinned root")
        one.add_argument("--git", default="git",
                         help="the git command seam; fixtures point it at stubs")
        one.add_argument("--timeout", type=int, default=600,
                         help="seconds the check or the receipt reader may take")
        if doing:
            one.add_argument("--remote", default="origin",
                             help="the remote open-pr pushes the story branch to")
            one.add_argument("--forge", default="gh",
                             help="the forge command seam; fixtures point it at stubs")
            one.add_argument("--briefing", help="the documenter's briefing file; required "
                                                "under open-pr")
        one.set_defaults(doing=doing)
    a = ap.parse_args()
    GIT = a.git
    try:
        return run_stage(a, a.doing)
    except CouldNotRun as e:
        print(f"merge: VOID: {e}; not a merge and not a verdict", file=sys.stderr)
        return COULD_NOT_RUN
    except OSError as e:
        print(f"merge: VOID: a filesystem read failed: {e}", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    raise SystemExit(main())

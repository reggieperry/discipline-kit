#!/usr/bin/env python3
"""The sequencer core: fail-closed start-up, position re-derived from refs, and the resume read.

Four decisions become mechanism here, over the pinned resolution `loader.py` provides and the
attempt-boundary acts `attempt.py` already carries.

ADR-0003/D5, the sequencer starts fail-closed. It refuses to run, naming the condition, when the
chain profile is absent or unparseable, when no terminal act is declared, when the declared push
scope does not pair with that act, when `trusted_base` is unset or omits the sequencer's own
sources, or when `pinned_root` names nothing usable. A sequencer that runs with no declared
posture guards nothing while reporting progress. The refusal path is STORY-0011's subject, which
extends the per-condition fixtures; the mechanism is here because start-up is where it runs.

ADR-0001/D1, chain position derives from refs the sequencer writes and from nothing else. Every
resume re-derives it from `refs/chain/<story-id>/attempt-<a>/phase-<n>`, never from the event log,
never from a story spec's frontmatter, never from the harness stream. The derivation is the
CONTIGUOUS run of phases from 1 inside the current attempt, and a phase ref standing above a
missing one is an integrity finding rather than a position: skipping over the hole would advance
past a phase whose postcondition never passed at the seam, which is the one thing position exists
to prevent. Re-running a phase that already has a ref costs a phase; skipping one signs work
nobody graded.

ADR-0001/D5, harness-written state is admitted for session ids and liveness and for nothing else.
`admitted_signals` is the one function in this runtime that reads a stream, and it reads through
a declared key set: every other field of every record is dropped at one comprehension, before
anything downstream can see it. The design measured `is_error` false, `subtype` "success" and an
empty `permission_denials` on a phase that did nothing, so a field that never reaches a caller is
a field that cannot decide anything. `scripts`-side, `harness/sequencer_source_check.py` is the
grep-shaped court that keeps this the only reader.

ADR-0004/D2, an attempt starts on a cleared worktree path. THE CLEARING-AUTHORITY QUESTION that
`attempt.py` records and leaves open is decided here, because it is a question about the
sequencer's authority to act unattended rather than about that file. `attempt.py` refuses to
delete a directory git does not know about, which is right for a path a caller named and wedges
every retry of a story whose phase crashed leaving one behind. The sequencer does not accept a
path: it COMPOSES one from the pinned worktree root, the story id and the attempt number, so
there is no mistyped argument to act on. At that composed path, and only there, it clears an
unregistered leftover under its own authority after recording an inventory of what it found.
Three conditions bound the act, checked before anything is removed:

    the path is the composed one          <root>/<story>/attempt-<n>, never a caller's string
    the path is not a symlink             what a link names is not the sequencer's to delete
    no working tree contains its parent   so graded or examiner material is out of reach

The residue is disclosed rather than closed: a directory a human created at exactly that path is
deleted. The path shape is not one anybody types by accident, and the alternative is the
availability failure ADR-0004/D2 named, where every retry of that story stops at the same place
until an operator intervenes.

THE EXIT CONTRACT holds two values, and the absence of a third is the point:

    0   done, with what was derived printed
    2   could-not-run, naming the condition or the integrity finding that stopped it

There is no exit 1, because nothing in this module is a story verdict. Verdicts are the pinned
advance script's exit code (ADR-0003/D2) and are evaluated once at the seam; this module derives
where a story is, refuses to start when the posture is undeclared, and refuses to resume when the
ref namespace disagrees with the rule that only the sequencer writes it.

Usage:
    python3 harness/chain/core.py startup --root <repo>
    python3 harness/chain/core.py position --repo <repo> --story <id>
    python3 harness/chain/core.py resume --repo <repo> --story <id> [--stream <path>]
    python3 harness/chain/core.py start-attempt --repo <repo> --story <id> \
        [--worktree-root <dir>]
    python3 harness/chain/core.py bounce --repo <repo> --story <id> --to-phase <n>

`--root` is the repository whose `.claude/chain/profile.toml` declares the posture: the party
that sequences declares its own, never the tree it is grading. `--repo` is the repository whose
ref namespace carries the story's position.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import attempt  # noqa: E402  (resolved from this file's own directory, beside it)
import loader  # noqa: E402

DONE = 0
COULD_NOT_RUN = 2

CouldNotRun = loader.CouldNotRun

PROFILE = loader.PROFILE
TERMINAL_KEY = "terminal"
PUSH_KEY = "push"
TRUSTED_KEY = "trusted_base"

# ADR-0002/D1's pairing, reimplemented rather than imported: `scripts/merge-posture-check.sh`
# is a shell court with the table inside a heredoc, so there is nothing to import, and a
# subprocess call to a build-time court would make start-up depend on the repository layout of
# whatever tree it was pointed at. The table is small and its record is cited at both sites; the
# court remains the authority on the commit path, and this is the same rule read at start-up.
REQUIRED_PAIR = {"open-pr": "branches-only", "merge-local": "never"}

# ADR-0003/D4's material, as in-repo paths: the sequencer's own definition and the advance
# scripts must sit inside the trusted base, or a chain story can edit its own driver and merge.
# The list is every module of harness/chain/, and `sequencer-sources-complete` in core_test.py
# holds it to that directory's live listing, because the hand-kept form drifts: two modules
# shipped without joining it. scripts/profile-check.sh requires the whole directory covered at
# the commit path; this gate keeps the per-module form so a refusal names exactly what the
# declared base misses.
SEQUENCER_SOURCES = (
    "harness/chain/core.py",
    "harness/chain/advance.py",
    "harness/chain/attempt.py",
    "harness/chain/invoke.py",
    "harness/chain/loader.py",
    "harness/chain/merge.py",
    "harness/chain/receipt.py",
    "harness/chain/sequencer.py",
)

PHASE_REF = re.compile(r"^refs/chain/[^/]+/attempt-(?P<attempt>[^/]+)/phase-(?P<phase>[^/]+)$")
ATTEMPT_REF = re.compile(r"^refs/chain/[^/]+/attempt-(?P<attempt>[^/]+)(/|$)")
INTEGER = re.compile(r"^[1-9][0-9]*$")

# The record kind whose presence is the completion signal. Its FIELDS are verdicts and are never
# read; `stream-json` is appended incrementally, so a killed phase leaves events and no record of
# this kind, which is ADR-0001/D5's liveness signal in its positive form.
RESULT_RECORD = "result"

# The compaction marker, matched as a prefix on a record's kind or on a key NAME. ADR-0004/D1
# reads a compaction event as mid-phase death — the one event that may have lost the composed
# prompt's constraints. The D5 limb probe (docs/probe/d5-limbs-probe-2026-08-15.md) could not
# force a compaction in a `-p` stream: two heavy phases past the interactive compaction point
# completed cleanly with no compaction record, so the `-p` record shape stays unmeasured. What
# the probe did settle is that every real compaction boundary in a session transcript (29 of 29)
# carries a `compactMetadata` top-level key, which this key-NAME scan matches — so the documented
# blind spot below is real in principle but unexercised by any observed compaction record. The
# scan reads the record's kind and its top-level key names, never the subtype value, because
# subtype is not in ADMITTED_KEYS; reading it would widen the trusted harness-state surface to
# catch a subtype-only shape that does not occur. The fail-closed backstop is the liveness arm: a
# phase that dies mid-stream from any cause, a silent compaction included, reads in-phase.
COMPACT_PREFIX = "compact"

# ADR-0001/D5's allowlist, declared as data so a court can read it: the session id, for
# resumption and diagnosis, and the record kind, for liveness. Nothing else from a
# harness-written stream reaches this runtime, and `harness/sequencer_source_check.py` fails the
# build on any addition to this set.
ADMITTED_KEYS = frozenset({"session_id", "type"})

INVENTORY_LIMIT = 12


def say(line: str) -> None:
    print(line, flush=True)


@dataclass(frozen=True)
class Posture:
    """The declared posture a run is allowed to start under."""

    terminal: str
    push: str
    trusted_base: tuple[str, ...]
    pinned_root: Path


@dataclass(frozen=True)
class Position:
    """Where a story is, derived from refs, with whatever the namespace could not explain."""

    story: str
    attempt: int
    phase: int
    phases: tuple[int, ...]
    other: tuple[str, ...]
    findings: tuple[str, ...]


@dataclass(frozen=True)
class Signals:
    """What a harness-written stream is allowed to contribute: an id, liveness, a denominator.

    `keys` is the set of field names that actually survived the allowlist, reported so the seam
    is observable rather than asserted. Names only, never values: a run that starts admitting
    more says so on its own output, where a filter silently removed would look identical.
    """

    session_id: str | None
    ids: int
    liveness: str
    records: int
    keys: tuple[str, ...]


def profile_table(root: Path) -> dict:
    """The parsed chain profile, or could-not-run naming which start-up condition was met."""
    path = root / PROFILE
    if not path.exists():
        raise CouldNotRun(f"profile-absent: no chain profile at {path}, so this run has no "
                          "declared posture and would guard nothing (ADR-0003/D5)")
    if not path.is_file():
        raise CouldNotRun(f"profile-unparseable: {path} exists and is not a regular file")
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise CouldNotRun(f"profile-unparseable: cannot parse {path}: {e}") from e


def declared_below(data: dict, key: str) -> bool:
    """Whether `key` appears in any table below the top level.

    The schema puts every key at the top level, so a declaration found deeper is a guess about
    which one governs. `loader.py` carries the same rule for its own key and hard-codes it there;
    generalizing that function would edit a shipped module for a reason this one can carry.
    """

    def below(node: object) -> bool:
        if isinstance(node, dict):
            return key in node or any(below(v) for v in node.values())
        if isinstance(node, list):
            return any(below(v) for v in node)
        return False

    return any(below(v) for v in data.values())


def declared_terminal(data: dict) -> str:
    value = data.get(TERMINAL_KEY)
    if value is None:
        where = " (one is declared in a nested table, and the schema puts every key at top " \
                "level)" if declared_below(data, TERMINAL_KEY) else ""
        raise CouldNotRun(f"terminal-undeclared: no top-level {TERMINAL_KEY}{where}, so the "
                          "chain has no declared stopping point (ADR-0003/D5)")
    if not isinstance(value, str) or value not in REQUIRED_PAIR:
        raise CouldNotRun(f"terminal-unknown: terminal act {value!r} is not one ADR-0002/D1 "
                          f"names ({', '.join(sorted(REQUIRED_PAIR))})")
    return value


def declared_push(data: dict, terminal: str) -> str:
    required = REQUIRED_PAIR[terminal]
    value = data.get(PUSH_KEY)
    if value != required:
        raise CouldNotRun(
            f"push-unpaired: terminal = {terminal!r} requires push = {required!r} at the top "
            f"level, and the profile declares {value!r} (ADR-0002/D1)"
        )
    return required


def declared_trusted_base(data: dict) -> tuple[str, ...]:
    value = data.get(TRUSTED_KEY)
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise CouldNotRun(
            f"trusted-base-unset: {TRUSTED_KEY} is not a non-empty list of path prefixes, so "
            "nothing states what a chain story may not touch (ADR-0003/D5)"
        )
    base = tuple(value)
    missing = [path for path in SEQUENCER_SOURCES
               if not any(path == prefix or path.startswith(prefix) for prefix in base)]
    if missing:
        raise CouldNotRun(
            f"trusted-base-incomplete: {TRUSTED_KEY} covers none of {', '.join(missing)}, so a "
            "story could edit the sequencer that grades it and merge (ADR-0003/D4, D5)"
        )
    return base


def startup(root: Path) -> Posture:
    """ADR-0003/D5's gate, in the order a refusal is most useful to whoever hits it."""
    data = profile_table(root)
    terminal = declared_terminal(data)
    push = declared_push(data, terminal)
    base = declared_trusted_base(data)
    try:
        pinned = loader.declared_pinned_root(root)
        loader.refuse_judged_root(pinned)
    except CouldNotRun as e:
        raise CouldNotRun(f"pinned-root: {e}") from e
    return Posture(terminal=terminal, push=push, trusted_base=base, pinned_root=pinned)


def story_refs(repo: Path, story: str) -> list[str]:
    """Every ref under one story's namespace, listed through git with the caller's own scrubbed.

    `attempt.git` is that spawn, shared with the re-walk so there is one definition of what a
    child inherits: git reads `GIT_DIR` in preference to `-C`, so a core invoked from a hook
    would otherwise derive position from the caller's repository.
    """
    prefix = f"refs/chain/{story}/"
    done = attempt.git(repo, "for-each-ref", "--format=%(refname)", prefix)
    if done.returncode != 0:
        raise CouldNotRun(f"the refs under {prefix} could not be listed: {done.stderr.strip()}")
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def contiguous(phases: set[int]) -> int:
    """The highest phase reachable from 1 without a hole. Zero when phase 1 is absent."""
    reached = 0
    while reached + 1 in phases:
        reached += 1
    return reached


def position(repo: Path, story: str) -> Position:
    """ADR-0001/D1's derivation, from the ref namespace and nothing else."""
    repo = attempt.working_tree(repo)
    story = attempt.component("story id", story)
    findings: list[str] = []
    other: list[str] = []
    started: set[int] = set()
    phases: dict[int, set[int]] = {}

    for name in story_refs(repo, story):
        shaped = PHASE_REF.match(name)
        if shaped:
            a, p = shaped.group("attempt"), shaped.group("phase")
            if INTEGER.match(a) and INTEGER.match(p):
                started.add(int(a))
                phases.setdefault(int(a), set()).add(int(p))
            else:
                which = "attempt" if not INTEGER.match(a) else "phase"
                findings.append(
                    f"unreadable-ref: {name} is phase-shaped and its {which} component is not a "
                    "positive integer, so the re-walk rule cannot order it (ADR-0001/D1)"
                )
            continue
        inside = ATTEMPT_REF.match(name)
        if inside and INTEGER.match(inside.group("attempt")):
            started.add(int(inside.group("attempt")))
        other.append(name)

    current = max(started, default=0)
    here = phases.get(current, set())
    reached = contiguous(here)
    above = sorted(p for p in here if p > reached)
    if above:
        findings.append(
            f"gap: attempt-{current} of {story} holds phase {', '.join(str(p) for p in above)} "
            f"while phase {reached + 1} is absent, so the position is {reached} and the higher "
            "ref is not counted (ADR-0001/D1)"
        )
    return Position(story=story, attempt=current, phase=reached, phases=tuple(sorted(here)),
                    other=tuple(sorted(other)), findings=tuple(findings))


def report(here: Position) -> None:
    say(f"core: position: {here.story} attempt {here.attempt} phase {here.phase} "
        f"({len(here.phases)} phase ref(s) in attempt-{here.attempt}, "
        f"{len(here.other)} other ref(s) in the namespace)")
    for name in here.other:
        say(f"core: not a phase ref, left alone: {name}")
    for finding in here.findings:
        say(f"core: FINDING: {finding}")


def consistent(here: Position) -> Position:
    """The position, or could-not-run when the namespace holds something it cannot explain.

    A finding means the ref namespace disagrees with the rule that only the sequencer writes it
    (ADR-0001/D1), which is the forged-ref residue that record discloses arriving in the one
    place it can be seen. Advancing over it would decide from a namespace nobody can account
    for, so the run stops and the operator gets the finding.
    """
    if here.findings:
        raise CouldNotRun(
            f"the ref namespace of {here.story} holds {len(here.findings)} unexplained "
            "finding(s), printed above, so no position is derived from it"
        )
    return here


def admitted_signals(path: Path | None) -> Signals:
    """THE ONE ADMITTED READER of harness-written state (ADR-0001/D5).

    Everything a stream contributes to this runtime passes through the comprehension below,
    which keeps `ADMITTED_KEYS` and drops every other field of every record before any caller
    can see it. The session id is admitted for resumption and diagnosis; the presence of a
    record of the result kind is admitted as liveness, in the positive form the design measured
    (events and no result record is in-phase death). The fields inside that record are the
    conjunction the denial probe returned on a phase that did nothing, and none of them survives
    this function.

    Two ids in one stream leave the id unread rather than picking one, because picking would be
    a guess about which session a resume names, and the count is reported instead.

    THE COMPACTION LIMB is a liveness read, not an admitted field. ADR-0004/D1 rules that a
    compaction event observed in a phase transcript is mid-phase death, so a stream carrying
    one reads `compacted` even when a result record is present — the fail-closed ordering,
    since the event may have lost the composed prompt's constraints before the phase went on to
    finish. Detection is value-free: a record whose admitted kind, or any of whose KEY NAMES,
    begins with the compaction prefix. Key names are scanned, never their values, so nothing
    beyond `ADMITTED_KEYS` reaches this runtime; what the limb contributes is one more liveness
    word, which is exactly what ADR-0001/D5 admits.

    THE READ ANNOUNCES ITSELF, so that reading harness state is visible in a transcript wherever
    it happens. A caller that admits a stream before establishing that the ref namespace is
    consistent has read from a run it must not start, and without the announcement that ordering
    is unobservable from outside: the value is dropped on the refusal path either way. Measured
    as a surviving mutation before the line existed.
    """
    if path is None or not path.is_file():
        return Signals(session_id=None, ids=0, liveness="absent", records=0, keys=())
    say(f"core: admitting from {path}: a session id and liveness, by ADR-0001/D5")
    ids: list[str] = []
    seen: set[str] = set()
    records = 0
    unreadable = 0
    terminal = False
    compacted = False
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            whole = json.loads(line)
        except ValueError:
            unreadable += 1
            continue
        if not isinstance(whole, dict):
            unreadable += 1
            continue
        records += 1
        admitted = {k: v for k, v in whole.items() if k in ADMITTED_KEYS}
        seen.update(admitted)
        value = admitted.get("session_id")
        if isinstance(value, str) and value and value not in ids:
            ids.append(value)
        kind = admitted.get("type")
        if kind == RESULT_RECORD:
            terminal = True
        if isinstance(kind, str) and kind.startswith(COMPACT_PREFIX):
            compacted = True
        if any(isinstance(k, str) and k.startswith(COMPACT_PREFIX) for k in whole):
            compacted = True
    if records == 0:
        liveness = "unreadable" if unreadable else "empty"
    elif compacted:
        liveness = "compacted"
    else:
        liveness = "complete" if terminal else "in-phase"
    return Signals(session_id=ids[0] if len(ids) == 1 else None, ids=len(ids),
                   liveness=liveness, records=records, keys=tuple(sorted(seen)))


def resume(repo: Path, story: str, stream: Path | None) -> tuple[Position, Signals]:
    """Re-derive position, then admit the stream's ids and liveness and nothing else.

    The order is the property, and it lives here rather than in the CLI arm so there is one
    statement of it: an inconsistent namespace stops the run BEFORE any harness state is read,
    so a run that must not start never admits a session id it might act on.
    """
    here = position(repo, story)
    report(here)
    consistent(here)
    return here, admitted_signals(stream)


def attempt_worktree(root: Path, story: str, number: int) -> Path:
    """The path the sequencer owns for one attempt, composed rather than accepted."""
    return root / story / f"attempt-{number}"


def inventory(path: Path) -> str:
    """What is at the path, recorded before anything is removed."""
    try:
        entries = sorted(p.name for p in path.iterdir())
    except OSError as e:
        return f"unreadable ({e})"
    listed = ", ".join(entries[:INVENTORY_LIMIT])
    more = "" if len(entries) <= INVENTORY_LIMIT else f" and {len(entries) - INVENTORY_LIMIT} more"
    return f"{len(entries)} entry(ies): {listed}{more}" if entries else "empty"


def owned(path: Path, root: Path, story: str, number: int) -> Path:
    """The three conditions that make the composed path the sequencer's to clear."""
    if path != attempt_worktree(root, story, number):
        raise CouldNotRun(f"{path} is not the path this attempt composes, and the sequencer "
                          "clears only paths it composed itself (ADR-0004/D2)")
    # TOCTOU bound, named rather than rested on silently: a link swapped in between this
    # check and the removal is not caught HERE — what actually protects the target is that
    # shutil.rmtree refuses a top-level symlink and lstats internally, so a swapped link
    # errors rather than deleting through. The check exists for the honest refusal message;
    # the mechanism is rmtree's.
    if path.is_symlink():
        raise CouldNotRun(f"{path} is a symlink, and what a link names is not the sequencer's "
                          "to remove")
    holder = loader.working_tree_above(path.parent)
    if holder is not None:
        raise CouldNotRun(
            f"{path} sits inside the git working tree at {holder}, so clearing it could remove "
            "graded or examiner material; a phase worktree lives outside every repository "
            "(ADR-0004/D2)"
        )
    return path


def clear_owned(repo: Path, root: Path, story: str, number: int) -> Path:
    """ADR-0004/D2's clearing, with the authority this module's docstring decides.

    `attempt.clear_worktree` runs first and does the whole job wherever git knows about the
    path. Its one refusal is the unregistered leftover, and that is re-established structurally
    here rather than by reading its message: the path is no longer registered and still exists.
    """
    path = owned(attempt_worktree(root, story, number), root, story, number)
    try:
        attempt.clear_worktree(argparse.Namespace(repo=str(repo), path=str(path)))
        return path
    except CouldNotRun as refused:
        registered = [w for w in attempt.registered_worktrees(repo)
                      if attempt.same_path(w, path)]
        if registered or not path.exists():
            raise
        say(f"core: clearing {path} under the sequencer's own authority, which held "
            f"{inventory(path)}")
        shutil.rmtree(path)
        if path.exists():
            raise CouldNotRun(f"{path} survived the clearing, so this attempt cannot start "
                              f"({refused})") from refused
        attempt.clear_worktree(argparse.Namespace(repo=str(repo), path=str(path)))
        return path


def start_attempt(repo: Path, story: str, root: Path | None) -> tuple[int, Path | None]:
    """The fresh-attempt entry: the next number, on a cleared path (ADR-0001/D1, ADR-0004/D2)."""
    here = consistent(position(repo, story))
    number = here.attempt + 1
    path = None if root is None else clear_owned(repo, root.resolve(), here.story, number)
    return number, path


def bounce(repo: Path, story: str, to_phase: int) -> Position:
    """ADR-0001/D1's re-walk, driven from the derived attempt: phase-{N..end} in one batch.

    This is the one act that runs with findings present. It only ever deletes downstream refs of
    the current attempt, so it cannot sign anything, and a namespace holding a stray ref is
    among the states an operator reaches for it in.
    """
    here = position(repo, story)
    report(here)
    if here.attempt == 0:
        raise CouldNotRun(f"no attempt of {here.story} has started, so there is nothing to "
                          "re-walk")
    attempt.rewalk(argparse.Namespace(repo=str(repo), story=here.story,
                                      attempt=str(here.attempt), from_phase=str(to_phase)))
    return position(repo, story)


def act_startup(a: argparse.Namespace) -> int:
    posture = startup(Path(a.root).resolve())
    say(f"core: posture: terminal {posture.terminal}, push {posture.push}, "
        f"{len(posture.trusted_base)} trusted-base prefix(es), pinned root {posture.pinned_root}")
    return DONE


def act_position(a: argparse.Namespace) -> int:
    here = position(Path(a.repo).resolve(), a.story)
    report(here)
    consistent(here)
    return DONE


def act_resume(a: argparse.Namespace) -> int:
    _, signals = resume(Path(a.repo).resolve(), a.story,
                        Path(a.stream) if a.stream else None)
    named = signals.session_id or (f"none ({signals.ids} seen)" if signals.ids else "none")
    say(f"core: signals: session id {named}, liveness {signals.liveness}, "
        f"{signals.records} record(s), admitting only {', '.join(signals.keys) or 'nothing'}")
    return DONE


def act_start_attempt(a: argparse.Namespace) -> int:
    repo = Path(a.repo).resolve()
    root = Path(a.worktree_root) if a.worktree_root else None
    number, path = start_attempt(repo, a.story, root)
    where = f", worktree path {path} clear" if path is not None else ""
    say(f"core: attempt: {attempt.component('story id', a.story)} next attempt {number}{where}")
    return DONE


def act_bounce(a: argparse.Namespace) -> int:
    to_phase = int(attempt.positive("to-phase", a.to_phase))
    here = bounce(Path(a.repo).resolve(), a.story, to_phase)
    report(here)
    consistent(here)
    return DONE


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="act", required=True)

    gate = sub.add_parser("startup", help="refuse to run unless the posture is declared")
    gate.add_argument("--root", required=True, help="the repository declaring the posture")
    gate.set_defaults(run=act_startup)

    for name, help_text, runner in (
        ("position", "derive the story's position from refs/chain", act_position),
        ("resume", "re-derive position and admit ids and liveness only", act_resume),
        ("start-attempt", "take the next attempt number on a cleared path", act_start_attempt),
        ("bounce", "delete phase-{N..end} of the current attempt", act_bounce),
    ):
        one = sub.add_parser(name, help=help_text)
        one.add_argument("--repo", required=True, help="the repository holding the namespace")
        one.add_argument("--story", required=True, help="the story id, one ref component")
        if name == "resume":
            one.add_argument("--stream", help="a harness stream file, read for ids and liveness")
        if name == "start-attempt":
            one.add_argument("--worktree-root", help="the pinned root phase worktrees live under")
        if name == "bounce":
            one.add_argument("--to-phase", required=True, help="the phase being returned to")
        one.set_defaults(run=runner)

    a = ap.parse_args()
    try:
        return a.run(a)
    except CouldNotRun as e:
        print(f"core: VOID: {e}; not a position and not a verdict", file=sys.stderr)
        return COULD_NOT_RUN
    except OSError as e:
        print(f"core: VOID: a filesystem read failed: {e}", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    raise SystemExit(main())

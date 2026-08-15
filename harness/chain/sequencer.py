#!/usr/bin/env python3
"""The sequencer: one pinned driver from start-attempt to the terminal act.

The first end-to-end walk (docs/probe/first-walk-2026-08-14.md) was driven by hand, with four
conventions carried in the operator's head. This module encodes the walk's order — ADR-0003's —
so the next run re-derives nothing: per phase, `invoke.py run`, `seam-check`, the harvest,
`seam-close`, the checkout, the advance seam; then the merge stage; then the post-batch
transcript audit. It composes and drives, and it decides no verdict anywhere: phase verdicts are
the pinned advance script's exit code (ADR-0003/D2, spawned as a subprocess so the verdict
channel stays the exit code), the merge verdict is merge.py's, and both are relayed verbatim,
re-printed line by line under a prefix.

THE PHASE TABLE is pinned material at `<pinned_root>/phases/<story>`: one line per phase,
`<phase-number> <brief-name> <postcondition-name>`, `#` comments and blank lines ignored,
following the contract-file precedent in advance.py. It is the one authority for the story's
shape — the row count is what `--expected-phases` receives, verbatim — because the
phase-to-postcondition mapping the walk carried in the driver's head is shared pinned material
(merge.py's conjunct 4 hardcodes the receipt reader) and must be declared somewhere a court can
read. Every named brief and every named postcondition `run` is checked PRESENT at walk entry,
before any spend; the demonstration stays the advance seam's court, never this module's.

RESUME IS DERIVED, NEVER INVENTED. Position comes from `core.position` over refs and nothing
else (ADR-0001/D1), and `run` walks phases position+1 to N inside the derived attempt: a phase
that passed and recorded stays recorded, and the dead or failed phase has no ref, so position+1
IS that phase, re-run as a fresh invocation (ADR-0004/D4). A concluded attempt — its composed
`merge-<attempt>.record` exists, checked by presence only, never content — refuses to resume:
the record is written exactly once, so resuming inside it is mechanically unavailable, and a
fresh attempt is taken only with the explicit `--fresh-attempt` flag. The flag over a
non-concluded attempt is refused: it would abandon graded phases a resume covers. Phase death
stops the run at once with invoke's own words; the retry is the operator re-invoking `run`,
because every phase is live spend and a silent retry loop is a silent cap.

THE HARVEST anchors what a phase committed before the worktree is cleared: after seam-check,
before seam-close (walk finding 3). The worktree HEAD must equal or descend from the base —
the story tip for a later phase, the main tip for phase 1 — or the refusal is `harvest-diverged`
and nothing is anchored. Phase 1 creates `refs/heads/story/<id>` with `git branch`; later
phases move it with `git merge --ff-only` executed in the clone, the one mechanism that moves a
checked-out branch, its index and its working tree together. `update-ref` is never applied to
the story branch or any checked-out branch anywhere in this module. A did-nothing phase
harvests as a no-op and walks on to the seam, which owns the verdict (ADR-0001/D2): refusing
earlier would decide from a signal that is not the pinned script's exit code.

THE WALK-ENTRY RECONCILE is what makes bounce-and-re-run and crash recovery real, bounded and
loud. With k phases recorded: a branch tip at the phase-k sha is checked out and left alone; a
tip STRICTLY DESCENDING from it is the bounce or park shape — harvested-but-ungraded commits
riding the branch — and is reset hard back to the phase-k sha with every discarded sha listed,
because position derives from refs and the branch is an anchor, not authority (ADR-0001/D1);
anything else is refused by name. At position 0 a leftover branch is deleted after the clone
detaches at the main tip — detached, so a crash here can never leave main checked out for the
merge-local act to refuse — and an unrelated branch is refused, not deleted.

THE ENVIRONMENT SCRUB (walk finding 6) drops every variable whose name starts with `CLAUDE`
from this process's own environment, in place, at act start — names printed, values never. The
measured set has three shapes and one (`CLAUDECODE`) carries no underscore, so the prefix is
`CLAUDE`, not `CLAUDE_`, and an enumeration would be blind to whatever the next harness version
adds. `ANTHROPIC_*` survives: it is the auth channel invoke.py names. A needed `CLAUDE*`
variable breaks a phase loudly and diagnosably; a kept one is silent session coupling.

STREAMS ARE COMPOSED, NOT ACCEPTED (walk finding 2): `composed_stream` is the ONE site in this
module that names the stream suffix, composing `<pinned_root>/streams/<story>/attempt-<a>/p<n>`
under the suffix the audit globs, so the audit's corpus exists by construction. A name already
present — a dead phase's re-run — is renamed aside with a `prior` mark, still inside the audit's
corpus: a dead phase's evidence is never overwritten. The repo-local identity gate (walk
finding 4) refuses a clone with no local user.name/user.email or with local signing on, before
any spend, because the phase's repointed HOME hides all global git config.

THE EXIT CONTRACT:

    0   the terminal outcome was reached AND the post-batch audit ran clean
    1   a story verdict, relayed verbatim — the advance seam's FAIL or the merge stage's park.
        This module never originates a 1.
    2   could-not-run anywhere, stopping at the first; OR the post-batch audit not clean after
        a completed terminal act — a widening the operator ratified, because exit 0 over a
        spawn finding would be a green light over an unexamined alarm. The output then states
        that the terminal outcome stands and refs already written stay written: the audit is
        audit, never control flow (ADR-0001/D5). The audit runs only on the terminal-outcome
        path; a parked story's streams are audited when it completes, or by hand — a named
        residue, not an oversight.

WHAT THIS DOES NOT CHECK, stated so it is not mistaken for checked: a phase table that
miscounts the story's real shape walks a shorter story, and `--expected-phases` inherits the
miscount — the table is the operator's declaration, the same trust class as the briefs, and its
court is review of pinned material. A Bash-holding phase can write into `streams/` from its own
worktree's path — it can manufacture alarm and truncate its own live stream; the audit's honest
bound already discloses the class, and closure is the containment posture's, not this module's.
The same reach extends to `records/`: the selected attempt's record is checked absent at walk
entry, so a PRE-planted record refuses with nothing spent, but one planted MID-run still wedges
the merge stage after the phases were spent (record-refused; the re-entry is the manual merge
with an explicit --record), and closure is the same hardening's.

Usage:
    python3 harness/chain/sequencer.py run --root <kit> --repo <clone> --story <id>
        --commit-check <path> [--plan <path>] [--harness <cmd>] [--timeout <seconds>]
        [--fresh-attempt] [--briefing <file>] [--remote <name>] [--forge <cmd>] [--git <cmd>]

`--root` is the repository whose profile declares the posture, the pin and the pinned root;
`--repo` is the dedicated clone holding the story's refs, its branch and `main`. `--harness` is
the injectable command seam; fixtures point it at stubs and never at the real binary.
`--commit-check`, `--plan`, `--remote`, `--forge`, `--briefing` and `--git` are relayed to the
merge stage verbatim; `--timeout` reaches the phase runs.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import attempt  # noqa: E402  (resolved from this file's own directory, beside it)
import core  # noqa: E402
import invoke  # noqa: E402
import loader  # noqa: E402
import merge  # noqa: E402

DONE = 0
FAIL = 1
COULD_NOT_RUN = 2

CouldNotRun = loader.CouldNotRun

PHASES = "phases"
STREAMS = "streams"
SESSION_PREFIX = "CLAUDE"
PHASE_NUMBER = re.compile(r"^[1-9][0-9]*$")

HERE = Path(__file__).resolve().parent
ADVANCE = HERE / "advance.py"
MERGE_STAGE = HERE / "merge.py"
AUDIT = HERE.parent / "transcript_audit.py"


def say(line: str) -> None:
    print(line, flush=True)


@dataclass(frozen=True)
class PhaseRow:
    """One declared phase: its number, its pinned brief, its pinned postcondition."""

    number: int
    brief: str
    postcondition: str


@dataclass(frozen=True)
class Walk:
    """Everything walk entry established: where the story is and what remains to run."""

    root: Path
    repo: Path
    pinned: Path
    story: str
    table: dict[int, PhaseRow]
    number: int
    start: int
    tip: str


def phase_table_path(pinned: Path, story: str) -> Path:
    """Where one story's phase table lives: a pinned-material kind by fixed name."""
    return pinned / PHASES / story


def read_phase_table(pinned: Path, story: str) -> dict[int, PhaseRow]:
    """The story's declared shape, parsed fail-closed with every refusal naming file and line.

    The format mirrors the advance script's contract file: one mapping per line, comments and
    blank lines ignored. After the parse the numbers must be exactly 1..N contiguous — a
    declared phase above a hole is not a walkable story, and refusing here is a zero-spend stop
    where walking would be a live phase followed by a refusal.
    """
    path = phase_table_path(pinned, story)
    loader.refuse_escaping_material(pinned, path)
    if not path.is_file():
        raise CouldNotRun(
            f"phase-table-absent: no phase table at {path}, so the story's shape is declared "
            "nowhere and there is nothing to walk; one line per phase, "
            "'<phase-number> <brief-name> <postcondition-name>'"
        )
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError as e:
        raise CouldNotRun(f"phase-table-absent: {path} could not be read: {e}") from e
    rows: dict[int, PhaseRow] = {}
    for number, raw in enumerate(lines, start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 3:
            raise CouldNotRun(
                f"phase-table-malformed: {path}:{number}: {raw.strip()!r} is not "
                "'<phase-number> <brief-name> <postcondition-name>'"
            )
        if not PHASE_NUMBER.fullmatch(fields[0]):
            raise CouldNotRun(f"phase-table-malformed: {path}:{number}: {fields[0]!r} is not a "
                              "positive phase number")
        phase = int(fields[0])
        try:
            attempt.component("brief name", fields[1])
            attempt.component("postcondition name", fields[2])
        except CouldNotRun as e:
            raise CouldNotRun(f"phase-table-malformed: {path}:{number}: {e}") from e
        if phase in rows:
            raise CouldNotRun(f"phase-table-malformed: {path}:{number}: phase {phase} is "
                              "mapped twice")
        rows[phase] = PhaseRow(number=phase, brief=fields[1], postcondition=fields[2])
    if not rows:
        raise CouldNotRun(f"phase-table-empty: {path} declares no phase, so there is no story "
                          "to walk")
    for expected in range(1, len(rows) + 1):
        if expected not in rows:
            raise CouldNotRun(
                f"phase-table-gap: {path} declares phase {max(rows)} while phase {expected} is "
                "absent, so the declared shape has a hole and no contiguous walk exists"
            )
    say(f"sequencer: phase table at {path}: {len(rows)} phase(s) declared")
    return rows


def preflight_material(pinned: Path, table: dict[int, PhaseRow]) -> None:
    """Every named brief and postcondition run present before any spend — presence only.

    The demonstration stays the advance seam's court (ADR-0001/D4). What this converts is the
    drift failure mode: a table naming a renamed brief becomes a zero-spend refusal here rather
    than a live phase 1 followed by a phase-2 stop.
    """
    for number in sorted(table):
        row = table[number]
        invoke.pinned_brief(pinned, row.brief)
        run = pinned / loader.POSTCONDITIONS / row.postcondition / loader.RUN
        loader.refuse_escaping_material(pinned, run)
        if not run.is_file():
            raise CouldNotRun(
                f"postcondition-absent: phase {row.number} names {row.postcondition!r} and no "
                f"{loader.RUN} exists at {run}; presence is checked before any spend, and the "
                "demonstration stays the advance seam's"
            )
    say(f"sequencer: pre-flight: every brief and postcondition run of {len(table)} phase(s) "
        "is present as pinned material")


def scrub_environment() -> None:
    """Walk finding 6: drop every `CLAUDE`-prefixed variable from this process, in place.

    In place at act start so one act covers everything: import-called invoke functions and
    every spawned child inherit the scrubbed environment. Names are printed and values never
    are, the emit_env precedent. The prefix is `CLAUDE` and not `CLAUDE_` because the measured
    set includes `CLAUDECODE`, which carries no underscore.
    """
    dropped = sorted(k for k in os.environ if k.startswith(SESSION_PREFIX))
    for name in dropped:
        del os.environ[name]
    if dropped:
        say(f"sequencer: scrubbed {len(dropped)} session variable(s) from the environment: "
            f"{', '.join(dropped)} (names only, never values)")
    else:
        say("sequencer: no session variable in the environment to scrub")


def identity_gate(repo: Path) -> None:
    """Walk finding 4: repo-local identity in the clone, before any spend.

    `--local` is the point: the phase's repointed HOME hides all global git config, so only
    local values exist inside a phase, and a machine relying on global identity or global
    signing config would die mid-phase after spend.
    """
    missing = []
    for key in ("user.name", "user.email"):
        done = attempt.git(repo, "config", "--local", "--get", key)
        if done.returncode != 0 or not done.stdout.strip():
            missing.append(key)
    if missing:
        wanted = " and ".join(f"'git config {key} <value>'" for key in missing)
        raise CouldNotRun(
            f"identity-unset: {repo} declares no repo-local {' or '.join(missing)}, and the "
            "phase's repointed HOME hides all global git config, so phase commits would die "
            f"mid-phase after spend; run {wanted} in the clone"
        )
    signed = attempt.git(repo, "config", "--local", "--get", "commit.gpgsign")
    if signed.returncode == 0 and signed.stdout.strip().lower() in {"true", "1", "yes", "on"}:
        raise CouldNotRun(
            f"identity-signing: {repo} sets repo-local commit.gpgsign, and the phase's empty "
            "repointed HOME has no keys, so the commit would die mid-phase after spend; unset "
            "it in the clone"
        )
    say(f"sequencer: repo-local identity present in {repo}, signing not configured")


def clone_clean(repo: Path) -> None:
    """The clone's porcelain read at walk entry, naming the dirt when there is any."""
    done = attempt.git(repo, "status", "--porcelain")
    if done.returncode != 0:
        raise CouldNotRun(f"the tree state of {repo} could not be read: {done.stderr.strip()}")
    dirt = [line for line in done.stdout.splitlines() if line.strip()]
    if dirt:
        listed = "; ".join(dirt[:20])
        more = "" if len(dirt) <= 20 else f" (and {len(dirt) - 20} more)"
        raise CouldNotRun(f"clone-dirty: {repo} is not clean at walk entry, so what the walk "
                          f"would build on is not what any sha records: {listed}{more}")
    say(f"sequencer: porcelain empty in {repo} at walk entry")


def resolve(repo: Path, name: str) -> str | None:
    """The commit `name` names right now, or None where the caller decides what absence means."""
    done = attempt.git(repo, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}")
    sha = done.stdout.strip()
    return sha if done.returncode == 0 and sha else None


def resolved(repo: Path, name: str) -> str:
    sha = resolve(repo, name)
    if sha is None:
        raise CouldNotRun(f"{name!r} does not resolve to a commit in {repo}")
    return sha


def is_ancestor(repo: Path, base: str, tip: str) -> bool:
    done = attempt.git(repo, "merge-base", "--is-ancestor", base, tip)
    if done.returncode == 0:
        return True
    if done.returncode == 1:
        return False
    raise CouldNotRun(f"the ancestry of {base} against {tip} could not be read: "
                      f"{done.stderr.strip()}")


def commits_between(repo: Path, keep: str, drop: str) -> list[str]:
    """Every commit on `drop` and not on `keep` — what a reconcile is about to discard."""
    done = attempt.git(repo, "rev-list", f"{keep}..{drop}")
    if done.returncode != 0:
        raise CouldNotRun(f"the commits between {keep} and {drop} could not be listed: "
                          f"{done.stderr.strip()}")
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def checked_out_story(repo: Path, story: str) -> None:
    """The clone on the story branch, which takes it off main and seats the graded tree."""
    want = f"refs/heads/story/{story}"
    head = attempt.git(repo, "symbolic-ref", "-q", "HEAD")
    if head.returncode == 0 and head.stdout.strip() == want:
        return
    done = attempt.git(repo, "checkout", "-q", f"story/{story}")
    if done.returncode != 0:
        raise CouldNotRun(f"checkout-failed: git checkout story/{story} in {repo} exited "
                          f"{done.returncode}: {done.stderr.strip()}")
    say(f"sequencer: {repo} checked out story/{story}")


def reconcile_story_branch(repo: Path, story: str, number: int, start: int) -> str:
    """The walk-entry reconcile: bounded, loud, descendant-only. Returns the walk's base sha.

    The authority for discarding is the ref namespace (ADR-0001/D1): the branch is an anchor,
    not authority, and harvested-but-ungraded commits are re-run fresh, never signed. Without
    the reset arm there is a reachable fail-open — a phase park leaves the branch at the
    harvested-but-failed commit, the next worktree detaches there, and the rejected work rides
    into the merge candidate with tip-equality passing.
    """
    branch = f"refs/heads/story/{story}"
    tip = resolve(repo, branch)
    main_tip = resolved(repo, "refs/heads/main")
    if start == 0:
        if tip is None:
            head = resolved(repo, "HEAD")
            if head != main_tip:
                raise CouldNotRun(
                    f"clone-not-at-main: {repo} HEAD is {head} and refs/heads/main is "
                    f"{main_tip}; phase 1 runs off the clone's HEAD, so they must agree"
                )
            say(f"sequencer: reconcile: no story branch, clone at main {main_tip}")
            return main_tip
        merged = is_ancestor(repo, tip, main_tip)
        beyond = is_ancestor(repo, main_tip, tip)
        if not merged and not beyond:
            raise CouldNotRun(
                f"story-branch-unrelated: {branch} stands at {tip}, neither an ancestor nor a "
                f"descendant of main {main_tip}, and a branch nobody can account for is not "
                "this module's to delete"
            )
        shape = "already merged into" if merged else "left beyond"
        say(f"sequencer: reconcile: {branch} at {tip} is {shape} main {main_tip}; detaching "
            "the clone at main and deleting the branch — position derives from refs, and the "
            "branch is an anchor, not authority (ADR-0001/D1)")
        for sha in commits_between(repo, main_tip, tip):
            say(f"sequencer: reconcile: discarded {sha}, re-run fresh and never signed")
        done = attempt.git(repo, "checkout", "-q", "--detach", main_tip)
        if done.returncode != 0:
            raise CouldNotRun(f"the clone could not detach at {main_tip}: "
                              f"{done.stderr.strip()}")
        done = attempt.git(repo, "branch", "-q", "-D", f"story/{story}")
        if done.returncode != 0:
            raise CouldNotRun(f"the branch story/{story} could not be deleted: "
                              f"{done.stderr.strip()}")
        return main_tip
    anchor = resolved(repo, f"refs/chain/{story}/attempt-{number}/phase-{start}")
    if tip is None:
        raise CouldNotRun(
            f"story-branch-absent: {branch} does not resolve while phase {start} of attempt "
            f"{number} is recorded, so the anchor the walk resumes from is gone"
        )
    if tip == anchor:
        checked_out_story(repo, story)
        say(f"sequencer: reconcile: {branch} stands at the phase-{start} sha {anchor}")
        return anchor
    if is_ancestor(repo, anchor, tip):
        say(f"sequencer: reconcile: {branch} at {tip} is past the phase-{start} sha {anchor} "
            "— harvested-but-ungraded work rides the branch, and it is discarded here because "
            "position derives from refs and nothing else (ADR-0001/D1)")
        checked_out_story(repo, story)
        for sha in commits_between(repo, anchor, tip):
            say(f"sequencer: reconcile: discarded {sha}, re-run fresh and never signed")
        done = attempt.git(repo, "reset", "-q", "--hard", anchor)
        if done.returncode != 0:
            raise CouldNotRun(f"the branch could not be reset to {anchor}: "
                              f"{done.stderr.strip()}")
        seen = resolved(repo, branch)
        if seen != anchor:
            raise CouldNotRun(f"{branch} reads {seen} after the reset, not {anchor}, so the "
                              "reconcile did not land")
        return anchor
    raise CouldNotRun(
        f"story-tip-diverged: {branch} stands at {tip}, which does not descend from the "
        f"phase-{start} ref's {anchor}, so the branch and the refs disagree in a shape no "
        "bounded reconcile covers"
    )


def harvest(repo: Path, worktree: Path, story: str, phase: int, base: str) -> str:
    """Anchor the phase's commit: lineage first, then create-or-fast-forward, then read back.

    The lineage check is what refuses a phase that rewrote history sideways — without it,
    phase 1's `git branch` would happily anchor an orphan commit and the wreck surfaces only
    at the trial merge, phases already spent. A worktree HEAD equal to the base is a
    did-nothing phase: the harvest is a no-op and the seam owns the verdict.
    """
    done = attempt.git(worktree, "rev-parse", "HEAD")
    head = done.stdout.strip()
    if done.returncode != 0 or not head:
        raise CouldNotRun(f"the worktree HEAD at {worktree} could not be read: "
                          f"{done.stderr.strip()}")
    if head != base and not is_ancestor(repo, base, head):
        raise CouldNotRun(
            f"harvest-diverged: the worktree HEAD {head} neither equals nor descends from the "
            f"base {base}, so the phase rewrote history sideways and nothing is anchored"
        )
    branch = f"story/{story}"
    if phase == 1:
        done = attempt.git(repo, "branch", branch, head)
        if done.returncode != 0:
            raise CouldNotRun(
                f"harvest-refused: git branch {branch} {head} exited {done.returncode}: "
                f"{done.stderr.strip()}; a branch that already exists here was minted by "
                "something other than this walk"
            )
    else:
        done = attempt.git(repo, "merge", "--ff-only", head)
        if done.returncode != 0:
            raise CouldNotRun(
                f"harvest-not-fast-forward: git merge --ff-only {head} onto the story tip "
                f"{base} exited {done.returncode}: {done.stderr.strip()}"
            )
    seen = resolved(repo, f"refs/heads/{branch}")
    if seen != head:
        raise CouldNotRun(f"refs/heads/{branch} reads {seen} after the harvest, not the "
                          f"worktree HEAD {head}, so nothing graded would be anchored")
    moved = "created at" if phase == 1 else "fast-forwarded to"
    say(f"sequencer: harvest: {branch} {moved} {head} (phase {phase})")
    return head


def stream_directory(pinned: Path, story: str, number: int) -> Path:
    """Where one attempt's phase streams land, and the corpus the post-batch audit reads."""
    return pinned / STREAMS / story / f"attempt-{number}"


def composed_stream(pinned: Path, story: str, number: int, phase: int) -> Path:
    """THE ONE SITE that names the stream suffix: walk finding 2 by construction.

    The suffix is composed here and nowhere else in this module, and the D5 source court
    exempts exactly this function for exactly the stream-file pattern: composing where a
    stream will LAND is the write side of the finding, not a read. A name already present is a
    dead phase's stream, renamed aside under a `prior` mark that keeps it inside the audit's
    corpus — a dead phase's evidence is never overwritten.
    """
    directory = stream_directory(pinned, story, number)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"p{phase}.jsonl"
    if path.exists():
        prior = 1
        while (directory / f"p{phase}.prior{prior}.jsonl").exists():
            prior += 1
        aside = directory / f"p{phase}.prior{prior}.jsonl"
        path.rename(aside)
        # The stderr sidecar the spawn writes beside the stream moves with it: the re-run's
        # spawn re-opens the sidecar name truncating, and a dead phase's stderr can carry the
        # death diagnosis. The aside name keeps the .stderr tail, so it stays outside the
        # audit's stream glob.
        sidecar = directory / (path.name + ".stderr")
        if sidecar.exists():
            sidecar.rename(directory / (aside.name + ".stderr"))
        say(f"sequencer: prior stream at {path} renamed aside to {aside}, its stderr sidecar "
            "with it; a dead phase's evidence stays in the audit corpus")
    return path


def merge_record(pinned: Path, story: str, number: int) -> Path:
    """The composed record path merge.py arms for one attempt; presence means concluded."""
    return pinned / merge.RECORDS / story / f"merge-{number}.record"


def refuse_preexisting_record(pinned: Path, story: str, number: int) -> None:
    """A record already standing at the SELECTED attempt's composed path stops the walk cold.

    The merge stage writes each record exactly once and refuses an existing file, so a walk
    into an attempt whose record pre-exists would spend every phase and then VOID at the merge
    — and the re-run would read attempt-concluded, wedging the attempt out of merge entirely.
    Refusing here costs nothing and names the remedy.
    """
    record = merge_record(pinned, story, number)
    if record.exists():
        raise CouldNotRun(
            f"record-preexists: {record} exists before attempt {number} has run, and the "
            "merge stage writes each record exactly once, so it would refuse after every "
            "phase was spent; delete the foreign file, or take the merge by hand with an "
            "explicit --record"
        )


def selected_attempt(a: argparse.Namespace, repo: Path, story: str, pinned: Path,
                     here: core.Position) -> tuple[int, int]:
    """The attempt this run walks and the position it resumes from. Never an invented number."""
    derived = here.attempt
    if a.fresh_attempt:
        if derived == 0:
            raise CouldNotRun(f"fresh-attempt-unearned: no attempt of {story} has started, so "
                              "there is nothing concluded to walk past; run without the flag")
        record = merge_record(pinned, story, derived)
        if not record.exists():
            raise CouldNotRun(
                f"fresh-attempt-unearned: {record} does not exist, so attempt {derived} is not "
                "concluded and re-invoking without the flag resumes it; a fresh attempt "
                "abandons graded phases only after the merge stage has spoken"
            )
        refuse_preexisting_record(pinned, story, derived + 1)
        number, _ = core.start_attempt(repo, story, invoke.worktree_root(pinned))
        say(f"sequencer: fresh attempt {number} of {story}; attempt {derived} concluded at "
            f"{record}")
        return number, 0
    if derived == 0:
        refuse_preexisting_record(pinned, story, derived + 1)
        number, _ = core.start_attempt(repo, story, invoke.worktree_root(pinned))
        say(f"sequencer: attempt {number} of {story} starts at phase 1")
        return number, 0
    record = merge_record(pinned, story, derived)
    if record.exists():
        raise CouldNotRun(
            f"attempt-concluded: {record} exists, so the merge stage has already spoken for "
            f"attempt {derived} and the record is written exactly once; a re-walk is a fresh "
            "attempt, taken explicitly with --fresh-attempt"
        )
    say(f"sequencer: resuming attempt {derived} of {story} at phase {here.phase + 1}; "
        f"{here.phase} recorded phase(s) stay recorded, nothing unrecorded is trusted")
    return derived, here.phase


def relay(tool: Path, *args: str, prefix: str) -> int:
    """Spawn one pinned script and re-print its output line by line, verbatim under a prefix.

    The verdict channel is the script's exit code (ADR-0003/D2); the re-print is so the
    deciding court's own words reach the operator through this transcript, never paraphrased.
    """
    argv = [sys.executable, str(tool), *args]
    say(f"sequencer: {prefix}: {tool.name} {' '.join(args)}")
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, errors="replace", env=loader.child_env(None))
    except OSError as e:
        raise CouldNotRun(f"{tool.name} could not be executed: {e}") from e
    out = child.stdout
    if out is not None:
        for line in out:
            say(f"sequencer: {prefix}| {line.rstrip()}")
    return child.wait()


def walk_entry(a: argparse.Namespace) -> Walk:
    """Every refusal that costs nothing, in the order a stop is most useful, then the state."""
    root = Path(a.root).resolve()
    repo = attempt.working_tree(Path(a.repo).resolve())
    story = attempt.component("story id", a.story)
    posture = core.startup(root)
    say(f"sequencer: posture: terminal {posture.terminal}, push {posture.push}, pinned root "
        f"{posture.pinned_root}")
    pinned = posture.pinned_root
    table = read_phase_table(pinned, story)
    preflight_material(pinned, table)
    identity_gate(repo)
    invoke.version_gate(root, a.harness)
    clone_clean(repo)
    here = core.position(repo, story)
    core.report(here)
    core.consistent(here)
    number, start = selected_attempt(a, repo, story, pinned, here)
    tip = reconcile_story_branch(repo, story, number, start)
    return Walk(root=root, repo=repo, pinned=pinned, story=story, table=table,
                number=number, start=start, tip=tip)


def run_story(a: argparse.Namespace, w: Walk) -> int:
    """The walk's order, encoded: phases from position+1, the merge stage, the audit."""
    total = len(w.table)
    worktree = core.attempt_worktree(invoke.worktree_root(w.pinned), w.story, w.number)
    tip = w.tip
    for phase in range(w.start + 1, total + 1):
        row = w.table[phase]
        say(f"sequencer: phase {phase} of {total}: brief {row.brief!r}, postcondition "
            f"{row.postcondition!r}")
        stream = composed_stream(w.pinned, w.story, w.number, phase)
        invoke.run_phase(w.root, w.repo, w.story, w.number, row.brief, stream, a.harness,
                         a.timeout or None)
        invoke.seam_check(w.root, w.repo, w.story, w.number)
        tip = harvest(w.repo, worktree, w.story, phase, tip)
        invoke.seam_close(w.root, w.repo, w.story, w.number)
        if phase == 1:
            checked_out_story(w.repo, w.story)
        code = relay(ADVANCE, "--repo", str(w.repo), "--story", w.story,
                     "--attempt", str(w.number), "--phase", str(phase),
                     "--postcondition", row.postcondition, "--profile-root", str(w.root),
                     "--tree-ref", tip, prefix="advance")
        if code == FAIL:
            print(f"sequencer: FAIL: phase {phase} of {w.story} did not pass at the seam; the "
                  "seam's words are relayed above, no later phase spawns, no merge is "
                  "attempted, and 1 is the seam's own exit relayed", file=sys.stderr)
            return FAIL
        if code != DONE:
            raise CouldNotRun(f"the advance seam exited {code} at phase {phase}, relayed above")
        say(f"sequencer: phase {phase} of {total} recorded at {tip}")

    merge_args = ["merge", "--root", str(w.root), "--repo", str(w.repo), "--story", w.story,
                  "--expected-phases", str(total), "--commit-check", a.commit_check]
    if a.plan:
        merge_args += ["--plan", a.plan]
    if a.git:
        merge_args += ["--git", a.git]
    if a.remote:
        merge_args += ["--remote", a.remote]
    if a.forge:
        merge_args += ["--forge", a.forge]
    if a.briefing:
        merge_args += ["--briefing", a.briefing]
    code = relay(MERGE_STAGE, *merge_args, prefix="merge")
    if code == FAIL:
        print(f"sequencer: FAIL: merge_ok is false for {w.story} — the story parks, with the "
              "stage's words and record above; 1 is the stage's own exit relayed",
              file=sys.stderr)
        return FAIL
    if code != DONE:
        raise CouldNotRun(f"the merge stage exited {code}, relayed above")
    say(f"sequencer: terminal outcome reached for {w.story} attempt {w.number}")

    code = relay(AUDIT, "--dir", str(stream_directory(w.pinned, w.story, w.number)),
                 prefix="audit")
    if code != DONE:
        print(f"sequencer: the post-batch transcript audit did not read clean (exit {code}); "
              "the terminal outcome stands and refs already written stay written — the audit "
              "is audit, never control flow (ADR-0001/D5) — and this exit says "
              "looked-at-and-not-clean rather than green over an unexamined alarm",
              file=sys.stderr)
        return COULD_NOT_RUN
    say("sequencer: post-batch transcript audit clean; the whole story ran from one invocation")
    return DONE


def act_run(a: argparse.Namespace) -> int:
    scrub_environment()
    return run_story(a, walk_entry(a))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="act", required=True)

    run = sub.add_parser("run", help="the whole story: phases from position, the merge stage, "
                                     "the post-batch audit")
    run.add_argument("--root", required=True, help="the repository declaring the posture and "
                                                   "the pin")
    run.add_argument("--repo", required=True,
                     help="the dedicated clone holding the story's refs and main")
    run.add_argument("--story", required=True, help="the story id, one ref component")
    run.add_argument("--commit-check", required=True,
                     help="the repository's own commit-path check, relayed to the merge stage")
    run.add_argument("--plan", help="the declared path list, relayed to the merge stage")
    run.add_argument("--harness", default="claude",
                     help="the harness command seam; fixtures point it at stubs")
    run.add_argument("--timeout", type=int, default=0,
                     help="seconds one phase may take before it reads dead")
    run.add_argument("--fresh-attempt", action="store_true",
                     help="walk a fresh attempt after a concluded one; never implied")
    run.add_argument("--briefing", help="the documenter's briefing, relayed to the merge stage")
    run.add_argument("--remote", help="the remote name, relayed to the merge stage")
    run.add_argument("--forge", help="the forge command seam, relayed to the merge stage")
    run.add_argument("--git", help="the merge stage's git seam, relayed verbatim")
    run.set_defaults(run=act_run)

    a = ap.parse_args()
    try:
        return a.run(a)
    except CouldNotRun as e:
        print(f"sequencer: VOID: {e}; not a phase and not a verdict", file=sys.stderr)
        return COULD_NOT_RUN
    except OSError as e:
        print(f"sequencer: VOID: a filesystem read failed: {e}", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    raise SystemExit(main())

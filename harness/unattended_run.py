#!/usr/bin/env python3
"""ADR-0005/D7's runtime enforcement: the unattended-run envelope runner.

STORY-0016 wraps `harness/chain/sequencer.py run` for a run no human is watching, and its spine is
that a built envelope on an unhardened host refuses rather than runs. Permissibility to run is the
unattended-start gate's clear (`harness/unattended_start_gate.py`, STORY-0015), reachable only on a
hardened host; a built, ready envelope is not a blessing to run.

THE GATE CALL COMES FIRST AND FAILS CLOSED, before anything that spends:

    integrity   The gate binary is checked OUT OF BAND before it is trusted: root-owned and not
                group- or other-writable, the gate file and the directory it lives under both. This
                is the non-circular guard ADR-0005/D7 condition 3 names — a stubbed gate does not
                run its own examiner-ownership check, so on the unhardened host where the pinned
                root is still owner-writable a phase stubs the gate to exit 0 and the runner would
                read the stub as clear. The read is by owner and mode rather than by an attempted
                write, because this check runs out of band as the runner rather than as the
                run-user, so `mode & 022 == 0` on a root-owned file is the ground truth here, where
                for the run-user it is not.
    gate        The gate is invoked as the declared run-user in Step 6's `sudo -u RUN_USER env -i`
                form, the same environment allowlist a phase is spawned under, so it measures the
                environment it certifies — a `gh` or credential reachable to a phase but absent to
                the gate would otherwise read clear while the phase can still push.
    clear       The run starts ONLY on an affirmative exit-0 clear. Every other outcome refuses,
                loudly, exit 2: a nonzero gate exit, an absent, non-executable, or unreadable gate,
                or a failed integrity check. Absence is a refuse condition, never a missing result
                read as clear.

THEN THE LOCK, THEN THE BUDGET, THEN THE RUN, no spend before the gate and the lock:

    lock        An exclusive `flock` on a lockfile named by the story id under a runner-owned
                directory, taken non-blocking. A second invocation on the same story finds the lock
                held and refuses rather than racing the refs and worktrees the sequencer moves.
    budget      A recorded spend ceiling, enforced at RUN granularity — the honest granularity for a
                runner that wraps one `sequencer.py run` driving every phase of a story in a single
                invocation, which it cannot interpose between without changing the sequencer. The
                runner reads the recorded spend, refuses to launch when the ceiling is already
                reached with the stop NAMED and RECORDED rather than a silent cap, and records the
                run's declared cost to the meter after. A present-but-unreadable meter refuses.
    run         Only on a clear integrity-verified gate AND an acquired lock AND budget remaining
                does `sequencer.py run` spawn, its exit relayed.

THE SEAM. The integrity check and the gate invocation are behind an in-process override, the only
path a stub reaches, exactly as the gate's own probe seam is. `real_seams` binds the real integrity
stat and the real gate subprocess and is the only `Seams` `main` builds, so on a real host the
runner runs the real checks and cannot be talked out of them: there is no command-line flag that
substitutes a clearing stub. The fixture drives clear, exit 2, and absent gate results and
root-owned-versus-writable integrity by IMPORTING this module and constructing its own `Seams`. The
lock, the meter, and the outcome record are not stubbed — they run for real against paths the
fixture points at throwaway directories, so the seam never becomes a way to pass a real runner on a
real host.

THE ACTIVATION BOUNDARY. This tool stays off the commit path. On an unhardened host the integrity
check or the gate refuses (exit 2), so wiring it into `scripts/check.sh` would block every commit
rather than report a defect, exactly as the start gate, `loader.py`, and `core.py` refuse until the
pinned root exists. Its fixture runs on the commit path; the tool does not.

THE EXIT CONTRACT mirrors the kit's three-valued convention:

    0   the sequencer ran and completed; its exit is relayed.
    1   the sequencer ran and relayed a story verdict (the advance seam's FAIL or the merge park).
    2   the runner refused before spending — a failed integrity check, a non-clear gate, a held
        lock, an exhausted budget, or any could-not-run — or the sequencer's own could-not-run.
        There is never a false clear: exit 0 means the sequencer ran on a clear gate.

Usage:
    python3 harness/unattended_run.py --run-user <user> --gate <path> \\
        --pinned-root <dir> --clone <dir> --expect-remotes <none|name[,name...]> \\
        --story <id> --runner-dir <dir> --budget <float> [--run-cost <float>] \\
        --root <kit> --commit-check <path> [--plan <path>] [--harness <cmd>] \\
        [--timeout <seconds>] [--fresh-attempt]
"""
from __future__ import annotations

import argparse
import fcntl
import os
import stat
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

REFUSED = 2

HERE = Path(__file__).resolve().parent
SEQUENCER = HERE / "chain" / "sequencer.py"

GATE_ENV_PATH = "/usr/bin:/bin"
GATE_TIMEOUT = 120
GATE_OUTPUT_TAIL = 400


def clean_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """The environment with git's own variables dropped, for every subprocess this runner spawns.

    git reads `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` and their siblings in preference to
    `-C`, so a runner invoked from a hook or a linked worktree would otherwise reach the caller's
    repository. That defect has a long tail in this repository, so the scrub is applied at every
    subprocess boundary here.
    """
    src = os.environ if base is None else base
    return {k: v for k, v in src.items() if not k.startswith("GIT_")}


@dataclass(frozen=True)
class Config:
    """What the runner was pointed at, as arguments so no real path is compiled into the tool."""

    run_user: str
    gate: Path
    pinned_root: Path
    clone: Path
    expect_remotes: str
    story: str
    runner_dir: Path
    budget: float
    run_cost: float
    root: Path
    commit_check: str
    plan: str | None
    harness: str | None
    timeout: int
    fresh_attempt: bool
    gate_env_path: str = GATE_ENV_PATH
    gate_timeout: int = GATE_TIMEOUT

    @property
    def lock_path(self) -> Path:
        return self.runner_dir / f"{self.story}.lock"

    @property
    def meter_path(self) -> Path:
        return self.runner_dir / f"{self.story}.meter"

    @property
    def outcomes_path(self) -> Path:
        return self.runner_dir / f"{self.story}.outcomes"


@dataclass(frozen=True)
class IntegrityResult:
    """The out-of-band read of the gate binary: whether it may be trusted, and why."""

    ok: bool
    detail: str


@dataclass(frozen=True)
class GateResult:
    """The gate invocation's reading: clear iff exit 0, the exit code, and the evidence.

    `exit_code` is None when the gate was never invoked — absent, non-executable, unreadable, or
    uninvokable — which is a refuse condition, never a missing result read as clear.
    """

    clear: bool
    exit_code: int | None
    detail: str


@dataclass(frozen=True)
class Seams:
    """The integrity check, the gate invocation, and the sequencer call, each a zero-arg act."""

    integrity: Callable[[], IntegrityResult]
    gate: Callable[[], GateResult]
    sequencer: Callable[[], int]


def gate_argv(cfg: Config, env: dict[str, str] | None = None) -> list[str]:
    """Step 6's `sudo -u RUN_USER env -i` form: the gate run as the run-user under a phase's allowlist.

    The environment is reset to the same allowlist a phase is spawned under so the gate resolves
    `gh`, `git`, and any forwarded credential exactly as a phase would, and measures the environment
    it certifies. `ANTHROPIC_API_KEY` rides through when present, matching the phase spawn; it is not
    a publish credential and so does not trip the gate's credential-reach condition.
    """
    world = os.environ if env is None else env
    argv = ["sudo", "-u", cfg.run_user, "env", "-i", f"PATH={cfg.gate_env_path}"]
    key = world.get("ANTHROPIC_API_KEY")
    if key:
        argv.append(f"ANTHROPIC_API_KEY={key}")
    argv += [str(cfg.gate), "--run-user", cfg.run_user, "--pinned-root", str(cfg.pinned_root),
             "--clone", str(cfg.clone), "--expect-remotes", cfg.expect_remotes]
    return argv


def sequencer_argv(cfg: Config) -> list[str]:
    """The `sequencer.py run` invocation the runner wraps, relaying the run's own arguments."""
    argv = [sys.executable, str(SEQUENCER), "run", "--root", str(cfg.root),
            "--repo", str(cfg.clone), "--story", cfg.story, "--commit-check", cfg.commit_check]
    if cfg.plan:
        argv += ["--plan", cfg.plan]
    if cfg.harness:
        argv += ["--harness", cfg.harness]
    if cfg.timeout:
        argv += ["--timeout", str(cfg.timeout)]
    if cfg.fresh_attempt:
        argv += ["--fresh-attempt"]
    return argv


def real_integrity(cfg: Config) -> IntegrityResult:
    """The gate binary and its directory root-owned and not group- or other-writable, by stat.

    `lstat`, not `stat`, so a symlink planted at the gate path by a phase reads with the link's own
    non-root owner rather than following to whatever it names. The parent directory is read too: a
    group- or other-writable directory lets a phase replace the gate wholesale, the rename defeat.
    """
    problems: list[str] = []
    for path in (cfg.gate, cfg.gate.parent):
        try:
            st = os.lstat(path)
        except OSError as e:
            return IntegrityResult(
                False, f"gate-integrity-unmeasurable: {path} could not be stat'd out of band: {e}")
        if st.st_uid != 0:
            problems.append(f"{path} is not root-owned (owner uid {st.st_uid})")
        if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            problems.append(f"{path} is group- or other-writable (mode {oct(st.st_mode & 0o777)})")
    if not cfg.gate.is_file():
        problems.append(f"{cfg.gate} is not a regular file")
    if problems:
        return IntegrityResult(False, "; ".join(problems))
    return IntegrityResult(
        True, f"{cfg.gate} and its directory are root-owned and not group- or other-writable")


def real_gate(cfg: Config) -> GateResult:
    """Invoke the gate as the run-user; clear iff it exits 0. Absence never reads as clear.

    The presence, executability, and readability of the gate are read before the invocation, so an
    absent or unusable gate refuses without a subprocess. A present, executable, readable gate is
    invoked in Step 6's form and its exit code is the reading.
    """
    if not cfg.gate.is_file():
        return GateResult(
            False, None,
            f"gate-absent: no gate at {cfg.gate}; an absent gate is a refuse condition, never a "
            "missing result read as clear")
    if not os.access(cfg.gate, os.X_OK):
        return GateResult(False, None, f"gate-non-executable: {cfg.gate} is not executable")
    if not os.access(cfg.gate, os.R_OK):
        return GateResult(False, None, f"gate-unreadable: {cfg.gate} is not readable")
    argv = gate_argv(cfg)
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=cfg.gate_timeout,
                              env=clean_env())
    except (OSError, subprocess.TimeoutExpired) as e:
        return GateResult(False, None, f"gate-uninvokable: the gate could not be invoked: {e}")
    tail = (done.stdout + done.stderr).strip()[:GATE_OUTPUT_TAIL]
    return GateResult(done.returncode == 0, done.returncode,
                      f"the gate exited {done.returncode}: {tail}")


def real_sequencer(cfg: Config) -> int:
    """Spawn `sequencer.py run`, re-print its output under a prefix, and return its exit verbatim."""
    argv = sequencer_argv(cfg)
    say(f"unattended-run: sequencer: {' '.join(argv[1:])}")
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 errors="replace", env=clean_env())
    except OSError as e:
        say(f"unattended-run: seq| the sequencer could not be executed: {e}", err=True)
        return REFUSED
    out = child.stdout
    if out is not None:
        for line in out:
            say(f"unattended-run: seq| {line.rstrip()}")
    return child.wait()


def real_seams(cfg: Config) -> Seams:
    """The real integrity stat and gate subprocess, the only Seams `main` ever builds.

    On a real host the runner runs these and nothing overrides them: no command-line flag
    substitutes a clearing stub. The fixture drives the orchestration by importing this module and
    constructing its own Seams, which is the only path an override reaches.
    """
    return Seams(
        integrity=lambda: real_integrity(cfg),
        gate=lambda: real_gate(cfg),
        sequencer=lambda: real_sequencer(cfg),
    )


def say(line: str, err: bool = False) -> None:
    print(line, file=sys.stderr if err else sys.stdout, flush=True)


@contextmanager
def story_lock(cfg: Config) -> Iterator[bool]:
    """An exclusive non-blocking `flock` on the per-story lockfile. Yields whether it was acquired.

    Non-blocking so a second invocation refuses at once rather than queueing behind the first. A
    lock held by another invocation yields False; any other lock error propagates and the caller
    fails closed to a refusal.
    """
    cfg.runner_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(cfg.lock_path, os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def read_meter(meter: Path) -> float | None:
    """The recorded spend: 0.0 when the meter is absent or empty, None when present but unreadable.

    An absent meter is a fresh runner with no spend recorded. A present meter that cannot be read as
    a number is a corruption the runner must not read as zero, because reading zero would step past
    the ceiling — so it returns None, which the caller reads fail-closed as a refusal.
    """
    if not meter.exists():
        return 0.0
    try:
        text = meter.read_text().strip()
    except OSError:
        return None
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return None


def record_spend(meter: Path, amount: float) -> None:
    """Write the cumulative recorded spend after a run, so the next launch reads it against the ceiling."""
    meter.parent.mkdir(parents=True, exist_ok=True)
    meter.write_text(f"{amount}\n")


def record_outcome(cfg: Config, outcome: str, detail: str) -> None:
    """Append every terminal decision to the story's outcome record, so no stop is silent."""
    cfg.runner_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    with open(cfg.outcomes_path, "a") as f:
        f.write(f"{stamp} {cfg.story} {outcome} {detail}\n")


def refuse(cfg: Config, marker: str, detail: str) -> int:
    """Record the named refusal and print it to stderr, exit 2. The one refusal path."""
    record_outcome(cfg, marker, detail)
    say(f"unattended-run: REFUSED: {marker}: {detail} (exit {REFUSED})", err=True)
    return REFUSED


def run(seams: Seams, cfg: Config) -> int:
    """The gate first and fail-closed, then the lock, then the budget, then the run.

    Nothing that spends runs before the integrity-verified gate clears and the lock is held; the
    budget is read under the lock and refuses to launch when the ceiling is already reached, so the
    sequencer is never invoked past the ceiling.
    """
    integrity = seams.integrity()
    if not integrity.ok:
        return refuse(cfg, "gate-integrity", integrity.detail)
    say(f"unattended-run: gate integrity verified: {integrity.detail}")

    gate = seams.gate()
    if not gate.clear:
        return refuse(cfg, "gate-not-clear", gate.detail)
    say(f"unattended-run: gate clear (exit {gate.exit_code}): {gate.detail}")

    with story_lock(cfg) as held:
        if not held:
            return refuse(cfg, "lock-held",
                          f"another invocation holds {cfg.lock_path}, so this one does not race it")
        say(f"unattended-run: acquired the per-story lock {cfg.lock_path}")

        spent = read_meter(cfg.meter_path)
        if spent is None:
            return refuse(cfg, "meter-unreadable",
                          f"{cfg.meter_path} could not be read as a recorded spend")
        if spent >= cfg.budget:
            return refuse(cfg, "budget-exhausted",
                          f"recorded spend {spent} has reached the ceiling {cfg.budget}, so no run "
                          "is launched and the sequencer is not invoked")
        say(f"unattended-run: budget ok: recorded spend {spent} below the ceiling {cfg.budget}")

        code = seams.sequencer()
        record_spend(cfg.meter_path, spent + cfg.run_cost)
        record_outcome(cfg, "ran",
                       f"sequencer exit {code}; recorded spend {spent} to {spent + cfg.run_cost}")
        say(f"unattended-run: sequencer returned {code}; recorded spend {spent} to "
            f"{spent + cfg.run_cost}; relaying the exit")
        return code


def build_config(a: argparse.Namespace) -> Config:
    return Config(
        run_user=a.run_user, gate=Path(a.gate), pinned_root=Path(a.pinned_root),
        clone=Path(a.clone), expect_remotes=a.expect_remotes, story=a.story,
        runner_dir=Path(a.runner_dir), budget=a.budget, run_cost=a.run_cost,
        root=Path(a.root), commit_check=a.commit_check, plan=a.plan, harness=a.harness,
        timeout=a.timeout, fresh_attempt=a.fresh_attempt,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ADR-0005/D7's unattended-run envelope, gate-first.")
    ap.add_argument("--run-user", required=True,
                    help="the declared unprivileged run-user the gate is invoked as")
    ap.add_argument("--gate", required=True,
                    help="the unattended-start gate binary, integrity-checked then invoked")
    ap.add_argument("--pinned-root", required=True, help="the pinned root, relayed to the gate")
    ap.add_argument("--clone", required=True,
                    help="the dedicated clone: the gate's --clone and the sequencer's --repo")
    ap.add_argument("--expect-remotes", required=True,
                    help="the declared remotes, relayed to the gate: 'none' or a name list")
    ap.add_argument("--story", required=True, help="the story id, the lock and run key")
    ap.add_argument("--runner-dir", required=True,
                    help="the runner-owned directory holding the lockfile, meter, and outcomes")
    ap.add_argument("--budget", required=True, type=float,
                    help="the recorded spend ceiling; a run does not launch at or above it")
    ap.add_argument("--run-cost", type=float, default=1.0,
                    help="the cost recorded to the meter after a run completes")
    ap.add_argument("--root", required=True,
                    help="the repository declaring the posture, relayed to the sequencer")
    ap.add_argument("--commit-check", required=True,
                    help="the repository's commit-path check, relayed to the sequencer")
    ap.add_argument("--plan", help="the declared path list, relayed to the sequencer")
    ap.add_argument("--harness", help="the harness command seam, relayed to the sequencer")
    ap.add_argument("--timeout", type=int, default=0,
                    help="seconds one phase may take, relayed to the sequencer")
    ap.add_argument("--fresh-attempt", action="store_true",
                    help="walk a fresh attempt, relayed to the sequencer")
    a = ap.parse_args(argv)
    cfg = build_config(a)
    try:
        return run(real_seams(cfg), cfg)
    except OSError as e:
        say(f"unattended-run: REFUSED: a filesystem or process error stopped the runner: {e} "
            f"(exit {REFUSED})", err=True)
        return REFUSED


if __name__ == "__main__":
    raise SystemExit(main())

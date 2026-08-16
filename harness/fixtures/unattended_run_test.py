#!/usr/bin/env python3
"""Red-first fixture for `harness/unattended_run.py`, the unattended-run envelope runner.

The runner is ADR-0005/D7's runtime enforcement: integrity-check the gate out of band, invoke it as
the run-user, start the sequencer ONLY on an exit-0 clear, hold a per-story lock, and refuse past a
recorded budget ceiling. This is a detector story, so each guard was watched failing before it
existed: a runner without the gate call runs the sequencer stub on a stubbed-clear gate, and one
without the integrity precheck runs it on a writable stub-clear gate, which these cases catch.

The host is not hardened, so the integrity OK branch and the gate invocation cannot be exercised for
real by a non-root fixture. They sit behind the runner's in-process seam, and the orchestration is
driven with injected results; the seam logic that can be tested without root is tested directly.

  THE ORCHESTRATION, injected seam results
  clear-runs-0               integrity ok, gate clear             -> 0, sequencer invoked, relayed,
                                                                     order integrity<gate<sequencer
  gate-exit2-refuses-2       integrity ok, gate exit 2            -> 2, gate-not-clear, no sequencer
  gate-absent-refuses-2      integrity ok, gate absent            -> 2, gate-absent, no sequencer
  writable-gate-refused-2    integrity BAD, gate would clear      -> 2, gate-integrity, no sequencer
  budget-ceiling-refuses-2   the meter already at the ceiling     -> 2, budget-exhausted NAMED and
                                                                     RECORDED, no sequencer
  budget-records-spend-0     a run under the ceiling              -> 0, the run's cost recorded
  meter-unreadable-refuses-2 a present unparseable meter          -> 2, meter-unreadable, fail closed
  concurrent-invocation      one holds via a slow sequencer, a    -> the second refuses lock-held,
                             second hits the lock                   exactly one sequencer run

  THE SEAM LOGIC, tested directly without root
  integrity-not-root-mech    a fixture-owned gate file            -> BAD, not root-owned
  integrity-writable-mech    a group/other-writable gate file     -> BAD, writable named
  integrity-absent-mech      a gate path that does not exist      -> BAD, unmeasurable, never ok
  gate-absent-real-mech      real gate seam on an absent path     -> not clear, absent, no subprocess
  gate-nonexec-real-mech     real gate seam on a non-exec file    -> not clear, non-executable
  gate-argv-shape            the Step 6 sudo -u env -i form        -> run-user, allowlist, key, gate
  sequencer-argv-shape       the sequencer.py run relay            -> root, repo, story, commit-check
  read-meter-mech            absent, a number, empty, garbage      -> 0.0, value, 0.0, None
  story-lock-mech            a held lock, then a nested attempt    -> acquired, then refused

  THE REAL CLI, end to end through main
  cli-refuses-on-this-host-2 main against a non-root gate file     -> 2, gate-integrity, no run:
                                                                     the real runner cannot be
                                                                     talked into a clear

The writable-gate and absent-gate cases carry the mechanism the mutation table names: a stub gate
returning clear is still refused when the out-of-band integrity read fails, and an absent gate is a
refuse condition rather than a missing result read as clear.

Run: python3 harness/fixtures/unattended_run_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import io
import os
import stat
import sys
import tempfile
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HARNESS))

import unattended_run as ur  # noqa: E402

RUNNER = HARNESS / "unattended_run.py"
STORY = "STORY-0042"
REFUSED = ur.REFUSED


def clean_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """The environment with git's own variables dropped, so a fixture subprocess stays in its tree.

    A pre-commit hook exports `GIT_DIR` and a subprocess inheriting it operates on the real
    repository, a defect this repository has paid for repeatedly.
    """
    src = os.environ if base is None else base
    return {k: v for k, v in src.items() if not k.startswith("GIT_")}


def show(name: str, ok: bool, extra: str = "") -> bool:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{extra}")
    return ok


def make_cfg(td: str, *, budget: float = 100.0, run_cost: float = 1.0,
             gate: Path | None = None, story: str = STORY) -> "ur.Config":
    root = Path(td)
    gate_path = gate if gate is not None else root / "sequencer" / "unattended-start-gate.sh"
    return ur.Config(
        run_user="someuser", gate=Path(gate_path), pinned_root=root / "pinned",
        clone=root / "clone", expect_remotes="none", story=story,
        runner_dir=root / "runner", budget=budget, run_cost=run_cost,
        root=root / "kit", commit_check="scripts/check.sh", plan=None, harness=None,
        timeout=0, fresh_attempt=False,
    )


class SeqSpy:
    """A sequencer stub that records whether and how often it was called, so no-run is observable."""

    def __init__(self, code: int = 0, order: list[str] | None = None) -> None:
        self.code = code
        self.calls = 0
        self.order = order

    def __call__(self) -> int:
        self.calls += 1
        if self.order is not None:
            self.order.append("sequencer")
        return self.code


def ok_integrity(order: list[str] | None = None):
    def probe() -> "ur.IntegrityResult":
        if order is not None:
            order.append("integrity")
        return ur.IntegrityResult(True, "root-owned and not writable (stub)")
    return probe


def bad_integrity(detail: str):
    def probe() -> "ur.IntegrityResult":
        return ur.IntegrityResult(False, detail)
    return probe


def gate_result(clear: bool, code: int | None, detail: str, order: list[str] | None = None):
    def probe() -> "ur.GateResult":
        if order is not None:
            order.append("gate")
        return ur.GateResult(clear, code, detail)
    return probe


def run_capturing(seams: "ur.Seams", cfg: "ur.Config") -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = ur.run(seams, cfg)
    return code, out.getvalue() + err.getvalue()


def clear_runs_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td)
        order: list[str] = []
        seq = SeqSpy(0, order=order)
        seams = ur.Seams(ok_integrity(order),
                         gate_result(True, 0, "the gate exited 0 (stub)", order), seq)
        code, said = run_capturing(seams, cfg)
        outcomes = cfg.outcomes_path.read_text() if cfg.outcomes_path.is_file() else ""
        ok = (code == 0 and seq.calls == 1 and order == ["integrity", "gate", "sequencer"]
              and "sequencer returned 0" in said and "ran" in outcomes)
    return show("clear-runs-0", ok, f": exit {code}, order={order}")


def gate_exit2_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td)
        seq = SeqSpy(0)
        seams = ur.Seams(ok_integrity(), gate_result(False, 2, "the gate exited 2 (stub)"), seq)
        code, said = run_capturing(seams, cfg)
        ok = code == REFUSED and seq.calls == 0 and "gate-not-clear" in said
    return show("gate-exit2-refuses-2", ok, f": exit {code}, sequencer-calls={seq.calls}")


def gate_absent_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td)
        seq = SeqSpy(0)
        seams = ur.Seams(ok_integrity(),
                         gate_result(False, None, "gate-absent: no gate (stub)"), seq)
        code, said = run_capturing(seams, cfg)
        ok = code == REFUSED and seq.calls == 0 and "gate-absent" in said
    return show("gate-absent-refuses-2", ok, f": exit {code}, sequencer-calls={seq.calls}")


def writable_gate_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td)
        seq = SeqSpy(0)
        seams = ur.Seams(bad_integrity("the gate is group- or other-writable (mode 0o777)"),
                         gate_result(True, 0, "the gate exited 0 (stub)"), seq)
        code, said = run_capturing(seams, cfg)
        ok = code == REFUSED and seq.calls == 0 and "gate-integrity" in said
    return show("writable-gate-refused-2", ok, f": exit {code}, sequencer-calls={seq.calls}")


def budget_ceiling_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td, budget=5.0)
        cfg.runner_dir.mkdir(parents=True, exist_ok=True)
        cfg.meter_path.write_text("5.0\n")
        seq = SeqSpy(0)
        seams = ur.Seams(ok_integrity(), gate_result(True, 0, "clear (stub)"), seq)
        code, said = run_capturing(seams, cfg)
        recorded = cfg.outcomes_path.read_text() if cfg.outcomes_path.is_file() else ""
        ok = (code == REFUSED and seq.calls == 0 and "budget-exhausted" in said
              and "budget-exhausted" in recorded)
    return show("budget-ceiling-refuses-2", ok,
                f": exit {code}, sequencer-calls={seq.calls}, recorded={'budget-exhausted' in recorded}")


def budget_records_spend_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td, budget=10.0, run_cost=3.0)
        seq = SeqSpy(0)
        seams = ur.Seams(ok_integrity(), gate_result(True, 0, "clear (stub)"), seq)
        code, _ = run_capturing(seams, cfg)
        meter = cfg.meter_path.read_text().strip() if cfg.meter_path.is_file() else "<absent>"
        ok = code == 0 and seq.calls == 1 and meter == "3.0"
    return show("budget-records-spend-0", ok, f": exit {code}, meter={meter}")


def meter_unreadable_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td, budget=10.0)
        cfg.runner_dir.mkdir(parents=True, exist_ok=True)
        cfg.meter_path.write_text("not-a-number\n")
        seq = SeqSpy(0)
        seams = ur.Seams(ok_integrity(), gate_result(True, 0, "clear (stub)"), seq)
        code, said = run_capturing(seams, cfg)
        ok = code == REFUSED and seq.calls == 0 and "meter-unreadable" in said
    return show("meter-unreadable-refuses-2", ok, f": exit {code}, sequencer-calls={seq.calls}")


def concurrent_case() -> bool:
    """One invocation holds the lock inside a slow sequencer while a second hits the lock.

    The handshake is deterministic: the holder signals it has entered the sequencer with the lock
    held, the second invocation runs only then, and the holder is released only after. The second
    must refuse lock-held, and exactly one sequencer runs.
    """
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td)
        entered = threading.Event()
        release = threading.Event()
        ran: list[str] = []
        ran_lock = threading.Lock()

        def slow_sequencer() -> int:
            with ran_lock:
                ran.append("holder")
            entered.set()
            release.wait(timeout=5)
            return 0

        def second_sequencer() -> int:
            with ran_lock:
                ran.append("second")
            return 0

        holder_seams = ur.Seams(ok_integrity(), gate_result(True, 0, "clear"), slow_sequencer)
        second_seams = ur.Seams(ok_integrity(), gate_result(True, 0, "clear"), second_sequencer)
        holder_result: list[int] = []

        def hold() -> None:
            holder_result.append(ur.run(holder_seams, cfg))

        sink = io.StringIO()
        with redirect_stdout(sink), redirect_stderr(sink):
            t = threading.Thread(target=hold)
            t.start()
            got_in = entered.wait(timeout=5)
            second_code = ur.run(second_seams, cfg)
            release.set()
            t.join(timeout=5)

        recorded = cfg.outcomes_path.read_text() if cfg.outcomes_path.is_file() else ""
        ok = (got_in and second_code == REFUSED and "lock-held" in recorded
              and ran == ["holder"] and holder_result == [0])
    return show("concurrent-invocation", ok,
                f": second-exit={second_code}, sequencer-runs={ran}, holder={holder_result}")


def integrity_not_root_case() -> bool:
    if os.geteuid() == 0:
        return show("integrity-not-root-mech", False, ": fixture is running as root")
    with tempfile.TemporaryDirectory() as td:
        gate = Path(td) / "sequencer" / "gate.sh"
        gate.parent.mkdir(parents=True)
        gate.write_text("#!/usr/bin/env bash\nexit 0\n")
        gate.chmod(0o755)
        cfg = make_cfg(td, gate=gate)
        res = ur.real_integrity(cfg)
        ok = not res.ok and "not root-owned" in res.detail
    return show("integrity-not-root-mech", ok, f": ok={res.ok}")


def integrity_writable_case() -> bool:
    if os.geteuid() == 0:
        return show("integrity-writable-mech", False, ": fixture is running as root")
    with tempfile.TemporaryDirectory() as td:
        gate = Path(td) / "sequencer" / "gate.sh"
        gate.parent.mkdir(parents=True)
        gate.write_text("#!/usr/bin/env bash\nexit 0\n")
        gate.chmod(0o777)
        cfg = make_cfg(td, gate=gate)
        res = ur.real_integrity(cfg)
        ok = not res.ok and "writable" in res.detail
    return show("integrity-writable-mech", ok, f": ok={res.ok}")


def integrity_absent_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        gate = Path(td) / "sequencer" / "gate.sh"
        cfg = make_cfg(td, gate=gate)
        res = ur.real_integrity(cfg)
        ok = not res.ok and "unmeasurable" in res.detail
    return show("integrity-absent-mech", ok, f": ok={res.ok}")


def gate_absent_real_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        gate = Path(td) / "sequencer" / "gate.sh"
        cfg = make_cfg(td, gate=gate)
        res = ur.real_gate(cfg)
        ok = not res.clear and res.exit_code is None and "gate-absent" in res.detail
    return show("gate-absent-real-mech", ok, f": clear={res.clear}, exit={res.exit_code}")


def gate_nonexec_real_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        gate = Path(td) / "sequencer" / "gate.sh"
        gate.parent.mkdir(parents=True)
        gate.write_text("#!/usr/bin/env bash\nexit 0\n")
        gate.chmod(0o644)
        cfg = make_cfg(td, gate=gate)
        res = ur.real_gate(cfg)
        ok = not res.clear and res.exit_code is None and "non-executable" in res.detail
    return show("gate-nonexec-real-mech", ok, f": clear={res.clear}, detail={res.detail[:40]!r}")


def gate_argv_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td)
        with_key = ur.gate_argv(cfg, env={"PATH": "x", "ANTHROPIC_API_KEY": "KV-SECRET"})
        without_key = ur.gate_argv(cfg, env={"PATH": "x"})
        head_ok = with_key[:6] == ["sudo", "-u", "someuser", "env", "-i",
                                   f"PATH={cfg.gate_env_path}"]
        key_ok = "ANTHROPIC_API_KEY=KV-SECRET" in with_key
        no_key_ok = not any(tok.startswith("ANTHROPIC_API_KEY=") for tok in without_key)
        relay_ok = (str(cfg.gate) in with_key and "--run-user" in with_key
                    and "someuser" in with_key and "--pinned-root" in with_key
                    and "--clone" in with_key and "--expect-remotes" in with_key
                    and "none" in with_key)
        ok = head_ok and key_ok and no_key_ok and relay_ok
    return show("gate-argv-shape", ok,
                f": head={head_ok}, key={key_ok}, key-absent-clean={no_key_ok}, relay={relay_ok}")


def sequencer_argv_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = ur.Config(
            run_user="someuser", gate=Path(td) / "g", pinned_root=Path(td) / "p",
            clone=Path(td) / "clone", expect_remotes="none", story=STORY,
            runner_dir=Path(td) / "runner", budget=1.0, run_cost=1.0,
            root=Path(td) / "kit", commit_check="scripts/check.sh", plan="plan.txt",
            harness="stub", timeout=90, fresh_attempt=True,
        )
        argv = ur.sequencer_argv(cfg)
        ok = (str(ur.SEQUENCER) in argv and "run" in argv and "--root" in argv
              and "--repo" in argv and str(cfg.clone) in argv and "--story" in argv
              and STORY in argv and "--commit-check" in argv and "--plan" in argv
              and "--harness" in argv and "--timeout" in argv and "90" in argv
              and "--fresh-attempt" in argv)
    return show("sequencer-argv-shape", ok, f": tokens={len(argv)}")


def read_meter_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        absent = ur.read_meter(base / "nope.meter")
        five = base / "five.meter"
        five.write_text("5.0\n")
        five_val = ur.read_meter(five)
        empty = base / "empty.meter"
        empty.write_text("")
        empty_val = ur.read_meter(empty)
        garbage = base / "garbage.meter"
        garbage.write_text("not-a-number\n")
        garbage_val = ur.read_meter(garbage)
        ok = absent == 0.0 and five_val == 5.0 and empty_val == 0.0 and garbage_val is None
    return show("read-meter-mech", ok,
                f": absent={absent}, five={five_val}, empty={empty_val}, garbage={garbage_val}")


def story_lock_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(td)
        with ur.story_lock(cfg) as first:
            with ur.story_lock(cfg) as second:
                held_out = first and not second
        with ur.story_lock(cfg) as again:
            reacquired = again
        ok = held_out and reacquired
    return show("story-lock-mech", ok, f": held-then-refused={held_out}, reacquired={reacquired}")


def cli_refuses_case() -> bool:
    """The real main against a non-root gate file: the runner refuses and cannot be talked to clear."""
    if os.geteuid() == 0:
        return show("cli-refuses-on-this-host-2", False, ": fixture is running as root")
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        gate = base / "sequencer" / "gate.sh"
        gate.parent.mkdir(parents=True)
        gate.write_text("#!/usr/bin/env bash\nexit 0\n")
        # Deliberately not executable: this is a fixture-owned (non-root) gate, so integrity refuses
        # it first. Keeping it non-executable means even a runner with the integrity guard removed
        # refuses at the gate seam's exec check rather than reaching the real sudo invocation, so no
        # mutation of this fixture can spawn sudo on the test host.
        gate.chmod(0o644)
        got = subprocess.run(
            [sys.executable, str(RUNNER),
             "--run-user", "someuser", "--gate", str(gate),
             "--pinned-root", str(base / "pinned"), "--clone", str(base / "clone"),
             "--expect-remotes", "none", "--story", STORY,
             "--runner-dir", str(base / "runner"), "--budget", "100",
             "--root", str(base / "kit"), "--commit-check", "scripts/check.sh"],
            capture_output=True, text=True, env=clean_env())
        said = got.stdout + got.stderr
        ok = (got.returncode == REFUSED and "gate-integrity" in said
              and "not root-owned" in said and "seq|" not in said)
    return show("cli-refuses-on-this-host-2", ok, f": exit {got.returncode}")


def main() -> int:
    if not RUNNER.is_file():
        print(f"unattended_run_test: runner not found at {RUNNER}", file=sys.stderr)
        return 2
    results = [
        clear_runs_case(),
        gate_exit2_case(),
        gate_absent_case(),
        writable_gate_case(),
        budget_ceiling_case(),
        budget_records_spend_case(),
        meter_unreadable_case(),
        concurrent_case(),

        integrity_not_root_case(),
        integrity_writable_case(),
        integrity_absent_case(),
        gate_absent_real_case(),
        gate_nonexec_real_case(),
        gate_argv_case(),
        sequencer_argv_case(),
        read_meter_case(),
        story_lock_case(),

        cli_refuses_case(),
    ]
    failed = results.count(False)
    print(f"unattended_run_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

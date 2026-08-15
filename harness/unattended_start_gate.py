#!/usr/bin/env python3
"""ADR-0005/D2's fail-closed court: the unattended-start gate.

INSTALL-HARDENING.md Step 6 specifies it and ADR-0005/D2 gates unattended operation behind it: a
check the unattended-run envelope (STORY-0016, ADR-0005/D7) runs before starting a run no human is
watching, that refuses to start unless every hardening condition holds. Its absence is why
unattended operation is refused today; its presence lets "verified" carry one mechanical meaning.

THE IDENTITY SELF-GUARD RUNS FIRST. The gate is meant to run as the declared run-user, and a gate
run as root or as the operator makes `sudo -n true`, every ownership write attempt, and the
credential resolution a catastrophic false pass: root passes them all trivially and answers for
none of them. So the first act asserts that this process's own effective uid (`id -u`) resolves to
the declared run-user, and a mismatch refuses before any host condition is measured.

THE SIX CONDITIONS, each with the real measurement INSTALL-HARDENING Steps 1 to 5 name and the
false-confidence trap each carries:

    run-identity-sudo   Step 1. `sudo -n true` fails for the run-user AND `sudo -l -U` reports no
                        sudo. Both polarities: `sudo -n true` failing proves only NO PASSWORDLESS
                        sudo, since a user with a password in sudoers prints the same and exits
                        nonzero, so the definitive read is the `sudo -l` message.
    examiner-ownership  Step 3. Every pinned examiner path is root-owned and not run-user-writable,
                        the write bound proven by an ATTEMPTED write rather than an octal-mode
                        read, because an ACL an octal read misses is exactly the hole, and because
                        a run-user-owned 0644 file reads clean to `mode & 022` while its owner can
                        write it.
    credential-reach    Step 2. The run-user resolves no publish credential: `gh auth token` is
                        empty, `git credential fill` returns no secret, and no token stands in the
                        environment. The credential PATH is exercised, never a file stat, because
                        the reference host's token lives in the secret-service keyring while its gh
                        config file carries none, so a stat reads clean vacuously.
    per-run-ownership   Step 3. The per-run writable directories are owned by the run-user, so one
                        run cannot corrupt another's evidence.
    sandbox             Step 5. A `bwrap --unshare-user` probe succeeds AND the pinned or managed
                        settings carry `sandbox.enabled` and `sandbox.failIfUnavailable`. The bwrap
                        probe alone is insufficient and reproduces Step 5's own trap: Claude Code
                        fails open, so a host where bwrap can start but the sandbox is not enabled
                        runs the phase unsandboxed while a probe-only gate reports the tier present.
    clone-remotes       Step 6. The clone's remotes match the declared `--expect-remotes`.

These six omit Step 4's managed-settings tier deliberately, matching ADR-0005/D2's falsifier: a
clear gate means unattended operation MAY begin, not that every step in the checklist is applied.

EVERY CONDITION IS CHECKED EVERY RUN. The gate never short-circuits among the six, because a
partial gate is worse than none: a gate that stops at the first hole leaves the rest unread and
blesses a host that fails them. A FAILED condition and an UNMEASURABLE one alike refuse, the latter
naming what could not be measured (a missing tool, an unreadable path, a git error) rather than
skipping to clear, because the instrument reading clean because nothing looked is the failure this
court exists against.

THE EXIT CONTRACT holds two values, and the absence of a third is the point:

    0   clear: the identity guard held and all six conditions hold, so unattended operation is
        permissible under ADR-0005/D2 on this host.
    2   refused: the identity guard did not hold, or a condition FAILED or could not be measured.
        Named on stderr. There is no exit 1, because the gate makes no story-shaped verdict: it
        either clears the host or refuses to start on it, and a refusal is could-not-start rather
        than a finding about a story.

THE PROBE SEAM. Each condition's measurement is a probe. `real_probes` binds the real measurements
and is the only `Probes` `main` ever builds, so on a real host with no override the gate runs the
real probes and cannot be talked out of them. The `Probes` indirection exists for the fixture,
which drives the orchestration against planted holes by IMPORTING this module and passing stub
probe results; it is reachable only from Python, never from a command-line flag, so the default is
real and the override is fixtures-only. A few real probe functions take the world they measure as a
defaulted parameter (the environment, the bwrap binary) for the same fixture reason and with the
same discipline: the default is the real world, and no CLI argument reaches the override.

THE ACTIVATION BOUNDARY. This tool stays off the commit path. On an unhardened host it refuses
(exit 2), so wiring it into `scripts/check.sh` would block every commit rather than report a
defect, exactly as `harness/chain/loader.py` and `core.py` VOID until the pinned root exists. Its
fixture runs on the commit path; the tool does not. The unattended-run envelope (STORY-0016)
invokes it at runtime, having integrity-checked it out of band (ADR-0005/D7).

Usage:
    python3 harness/unattended_start_gate.py --run-user <user> --pinned-root <dir> \\
        --clone <dir> --expect-remotes <none|name[,name...]>
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

CLEAR = 0
REFUSED = 2

IDENTITY = "identity-self-guard"
CONDITIONS = (
    "run-identity-sudo",
    "examiner-ownership",
    "credential-reach",
    "per-run-ownership",
    "sandbox",
    "clone-remotes",
)

# The pinned examiner material root-owned and read-only to the run-user (Step 3), and the per-run
# writable directories owned by the run-user (Step 3). The pinned root itself is walked with the
# examiner set because the parent-dir rename defeat needs write on the parent.
EXAMINER_SUBDIRS = ("settings", "briefs", "postconditions", "phases", "rules", "sequencer")
PER_RUN_SUBDIRS = ("worktrees", "streams", "records")

MANAGED_SETTINGS = Path("/etc/claude-code/managed-settings.json")
CREDENTIAL_ENV_KEYS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN",
                       "GITHUB_ENTERPRISE_TOKEN", "SSH_AUTH_SOCK")
PROBE_TIMEOUT = 30
LISTED = 20


class Status(Enum):
    HOLDS = "HOLDS"
    FAILED = "FAILED"
    UNMEASURABLE = "UNMEASURABLE"


@dataclass(frozen=True)
class ProbeResult:
    """One condition's reading: its stable id, whether it holds, and the evidence."""

    condition: str
    status: Status
    detail: str


def holds(condition: str, detail: str) -> ProbeResult:
    return ProbeResult(condition, Status.HOLDS, detail)


def failed(condition: str, detail: str) -> ProbeResult:
    return ProbeResult(condition, Status.FAILED, detail)


def unmeasurable(condition: str, detail: str) -> ProbeResult:
    return ProbeResult(condition, Status.UNMEASURABLE, detail)


def clean_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """The environment with git's own variables dropped, for every git spawn this gate makes.

    git reads `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` and their siblings in preference to
    `-C`, so a gate invoked from a hook or a linked worktree would otherwise read the caller's
    repository rather than the clone it was pointed at. That defect has a long tail in this
    repository, so the scrub is applied at every git boundary here.
    """
    src = os.environ if base is None else base
    return {k: v for k, v in src.items() if not k.startswith("GIT_")}


def capped(items: list[str]) -> str:
    """The first LISTED entries, with the remainder counted rather than dropped."""
    listed = "; ".join(items[:LISTED])
    more = "" if len(items) <= LISTED else f" (and {len(items) - LISTED} more)"
    return f"{listed}{more}"


def writable_by_write_attempt(path: Path) -> bool | None:
    """Whether the current process can write `path`, by attempting the write, not reading its mode.

    An octal read of the mode is the instrument this measurement exists to replace: `mode & 022`
    reports a run-user-owned 0644 file NOT writable while its owner can write it, and misses an ACL
    entirely. The attempt is the ground truth. It is non-destructive: a directory gets a uniquely
    named probe entry created and immediately unlinked, and a file is opened for append and closed
    without a byte written, so opening it acquires and releases write access without changing it.

    Returns True writable, False not writable, and None when the attempt could not decide (an odd
    node, a name collision), which the caller reads fail-closed as unmeasurable.
    """
    try:
        if path.is_dir() and not path.is_symlink():
            probe = path / f".unattended-start-gate-probe-{os.getpid()}"
            try:
                fd = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                return None
            os.close(fd)
            probe.unlink()
            return True
        fd = os.open(path, os.O_WRONLY | os.O_APPEND)
        os.close(fd)
        return True
    except PermissionError:
        return False
    except OSError:
        return None


def identity_probe(run_user: str) -> ProbeResult:
    """The self-guard: this process's effective uid (`id -u`) resolves to the declared run-user."""
    try:
        pw = pwd.getpwnam(run_user)
    except KeyError:
        return unmeasurable(
            IDENTITY,
            f"the declared run-user {run_user!r} does not resolve to an account, so this "
            "process's identity cannot be established against it",
        )
    current = os.geteuid()
    if pw.pw_uid == 0:
        return failed(
            IDENTITY,
            f"the declared run-user {run_user!r} is uid 0 (root); the run-identity must be "
            "unprivileged, or every sudo, ownership and credential probe is a false pass",
        )
    if current != pw.pw_uid:
        return failed(
            IDENTITY,
            f"this process runs as uid {current}, not {run_user!r} (uid {pw.pw_uid}); a gate run "
            "as root or the operator makes every sudo and ownership probe a false pass",
        )
    return holds(IDENTITY, f"this process runs as {run_user!r} (uid {current})")


def sudo_probe(run_user: str, env: dict[str, str] | None = None) -> ProbeResult:
    """Step 1: no passwordless sudo, and no sudo at all, read at both polarities.

    `env` defaults to the process environment, which is the real measurement; the fixture passes a
    shimmed environment to drive the definitive-no-sudo HOLDS branch and the password-required
    UNMEASURABLE branch, neither of which a non-root host can otherwise produce.
    """
    world = os.environ if env is None else env
    try:
        passwordless = subprocess.run(
            ["sudo", "-n", "true"], capture_output=True, text=True, timeout=PROBE_TIMEOUT,
            env=dict(world),
        )
    except FileNotFoundError:
        return unmeasurable("run-identity-sudo", "sudo is not installed, so the no-sudo condition "
                            "could not be measured")
    except (OSError, subprocess.TimeoutExpired) as e:
        return unmeasurable("run-identity-sudo", f"sudo -n true could not be measured: {e}")
    if passwordless.returncode == 0:
        return failed("run-identity-sudo", "sudo -n true succeeded, so the run-user holds "
                      "passwordless sudo (NOPASSWD)")
    try:
        listing = subprocess.run(
            ["sudo", "-n", "-l", "-U", run_user], capture_output=True, text=True,
            timeout=PROBE_TIMEOUT, env=dict(world),
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return unmeasurable("run-identity-sudo", f"sudo -l -U {run_user} could not be "
                            f"measured: {e}")
    text = listing.stdout + listing.stderr
    if "is not allowed to run sudo" in text:
        return holds("run-identity-sudo", f"sudo -n true fails and sudo -l reports {run_user} may "
                     "not run sudo")
    if listing.returncode != 0 and "password is required" in text:
        return unmeasurable("run-identity-sudo", f"sudo -l -U {run_user} needs a password to "
                            "query, so no-sudo could not be confirmed at the definitive polarity")
    return failed("run-identity-sudo", f"sudo -l -U {run_user} does not report the run-user may "
                  f"not run sudo, so sudo is reachable: {text.strip()[:160]}")


def walk(base: Path) -> tuple[list[Path], bool]:
    """Every path at or under `base`, and whether any directory could not be read (fail-closed)."""
    errors: list[OSError] = []
    found = [base]
    for root, dirs, files in os.walk(base, onerror=errors.append):
        for name in sorted(dirs) + sorted(files):
            found.append(Path(root) / name)
    return found, bool(errors)


def examiner_ownership_probe(pinned_root: Path, run_user: str) -> ProbeResult:
    """Step 3: the pinned root and every examiner path root-owned and not run-user-writable.

    The pinned root is checked as a single directory and never walked, because its per-run children
    (worktrees, streams, records) are run-user-owned by design and are the per-run condition's to
    read; walking the root would report them as examiner holes on a correctly hardened host. Only
    the examiner subtrees are walked. The root's own ownership is the parent-rename defeat: a
    run-user-writable root lets a phase replace a whole examiner directory with a writable one.
    """
    cond = "examiner-ownership"
    if not pinned_root.is_dir():
        return unmeasurable(cond, f"the pinned root {pinned_root} is not a directory, so the "
                            "examiner ownership could not be measured")
    to_check: list[Path] = [pinned_root]
    for name in EXAMINER_SUBDIRS:
        base = pinned_root / name
        if not base.exists():
            return unmeasurable(cond, f"the examiner path {base} is absent, so it could not be "
                                "measured, and a skip-to-clear here is the hole this gate refuses")
        paths, unreadable = walk(base)
        if unreadable:
            return unmeasurable(cond, f"a directory under {base} could not be listed, so its "
                                "ownership could not be read")
        to_check.extend(paths)
    not_root: list[str] = []
    writable: list[str] = []
    for path in to_check:
        try:
            owner = os.stat(path, follow_symlinks=False).st_uid
        except OSError as e:
            return unmeasurable(cond, f"{path} could not be stat'd: {e}")
        if owner != 0:
            not_root.append(str(path))
        attempt = writable_by_write_attempt(path)
        if attempt is True:
            writable.append(str(path))
        elif attempt is None:
            return unmeasurable(cond, f"the writability of {path} could not be decided by an "
                                "attempted write, so it is not proven not-writable")
    problems: list[str] = []
    if not_root:
        problems.append(f"not root-owned: {capped(not_root)}")
    if writable:
        problems.append(f"run-user-writable, proven by an attempted write: {capped(writable)}")
    if problems:
        return failed(cond, "; ".join(problems))
    return holds(cond, f"the pinned root and {len(EXAMINER_SUBDIRS)} examiner subtree(s) are "
                 "root-owned and not run-user-writable")


def credential_probe(run_user: str, env: dict[str, str] | None = None) -> ProbeResult:
    """Step 2: the run-user resolves no publish credential, by exercising the resolution path.

    `env` defaults to the process environment, which is the real measurement; the fixture passes a
    shimmed environment to prove the probe consults `gh` and `git` rather than statting a file, the
    reversion Step 2 names as vacuous here. A forwarded ssh-agent socket (`SSH_AUTH_SOCK`) is a
    reachable push credential too, so it is among the environment keys that fail this condition:
    with `--expect-remotes none` an explicit `ssh://` or `git@` push URL plus a forwarded agent
    reaches the trunk while the remote list reads clean.
    """
    cond = "credential-reach"
    world = dict(os.environ) if env is None else dict(env)
    reaches: list[str] = []
    gh_present = True
    try:
        gh = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, env=world,
                            timeout=PROBE_TIMEOUT)
        if gh.returncode == 0 and gh.stdout.strip():
            reaches.append("gh auth token resolves a token")
    except FileNotFoundError:
        gh_present = False
    except (OSError, subprocess.TimeoutExpired) as e:
        return unmeasurable(cond, f"gh auth token could not be measured: {e}")
    try:
        git = subprocess.run(
            ["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, env=clean_env(world), timeout=PROBE_TIMEOUT,
        )
        if any(line.startswith("password=") and line.strip() != "password="
               for line in git.stdout.splitlines()):
            reaches.append("git credential fill returns a secret")
    except FileNotFoundError:
        return unmeasurable(cond, "git is not installed, so the credential path could not be "
                            "measured")
    except (OSError, subprocess.TimeoutExpired) as e:
        return unmeasurable(cond, f"git credential fill could not be measured: {e}")
    present = [k for k in CREDENTIAL_ENV_KEYS if world.get(k)]
    if present:
        reaches.append(f"a publish credential stands in the environment ({', '.join(present)})")
    if reaches:
        return failed(cond, "the run-user reaches a publish credential: " + "; ".join(reaches))
    gh_note = "gh auth token empty" if gh_present else "gh absent"
    return holds(cond, f"no publish credential resolves: {gh_note}, git credential fill returns "
                 "no secret, no publish credential in the environment")


def per_run_ownership_probe(pinned_root: Path, run_user: str) -> ProbeResult:
    """Step 3: the per-run writable directories are owned by the run-user."""
    cond = "per-run-ownership"
    try:
        target = pwd.getpwnam(run_user).pw_uid
    except KeyError:
        return unmeasurable(cond, f"the run-user {run_user!r} does not resolve to an account, so "
                            "the per-run ownership could not be measured")
    wrong: list[str] = []
    for name in PER_RUN_SUBDIRS:
        directory = pinned_root / name
        if not directory.exists():
            return unmeasurable(cond, f"the per-run directory {directory} is absent, so its "
                                "ownership could not be measured")
        try:
            owner = os.stat(directory, follow_symlinks=False).st_uid
        except OSError as e:
            return unmeasurable(cond, f"{directory} could not be stat'd: {e}")
        if owner != target:
            wrong.append(f"{name} owned by uid {owner}")
    if wrong:
        return failed(cond, f"a per-run directory is not owned by {run_user}: {', '.join(wrong)}")
    return holds(cond, f"{', '.join(PER_RUN_SUBDIRS)} owned by {run_user}")


def settings_carry_sandbox(paths: list[Path]) -> tuple[bool | None, str]:
    """Whether any settings file carries sandbox.enabled and sandbox.failIfUnavailable.

    Returns True when one does, False when none of the present files does, and None when a present
    file could not be parsed, which the caller reads fail-closed as unmeasurable.
    """
    checked: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        checked.append(str(path))
        try:
            with open(path, "rb") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            return None, f"{path} could not be parsed as settings JSON: {e}"
        box = data.get("sandbox") if isinstance(data, dict) else None
        if isinstance(box, dict) and box.get("enabled") is True \
                and box.get("failIfUnavailable") is True:
            return True, f"{path} carries sandbox.enabled and sandbox.failIfUnavailable"
    if not checked:
        return False, "no pinned or managed settings file was present to read"
    return False, (f"no settings file among {', '.join(checked)} carries sandbox.enabled and "
                   "sandbox.failIfUnavailable")


def sandbox_probe(settings_paths: list[Path], bwrap: str = "bwrap") -> ProbeResult:
    """Step 5: a bwrap user-namespace probe succeeds AND the settings enable the sandbox.

    `bwrap` defaults to the real binary; the fixture substitutes a succeeding or failing stand-in
    to exercise the composition, and the settings half is exercised directly through
    `settings_carry_sandbox`.
    """
    cond = "sandbox"
    try:
        done = subprocess.run(
            [bwrap, "--unshare-user", "--ro-bind", "/", "/", "/bin/true"],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT,
        )
        bwrap_ok = done.returncode == 0
        bwrap_note = ("bwrap --unshare-user succeeds" if bwrap_ok
                      else f"bwrap --unshare-user failed (exit {done.returncode}: "
                           f"{done.stderr.strip()[:120]})")
    except FileNotFoundError:
        bwrap_ok = False
        bwrap_note = "bwrap is not installed, so no sandbox tier is present"
    except (OSError, subprocess.TimeoutExpired) as e:
        return unmeasurable(cond, f"the bwrap probe could not be measured: {e}")
    carried, settings_note = settings_carry_sandbox(settings_paths)
    if carried is None:
        return unmeasurable(cond, settings_note)
    if bwrap_ok and carried:
        return holds(cond, f"{bwrap_note}; {settings_note}")
    problems: list[str] = []
    if not bwrap_ok:
        problems.append(bwrap_note)
    if not carried:
        problems.append(settings_note + "; the bwrap probe alone is insufficient because Claude "
                        "Code fails open")
    return failed(cond, "; ".join(problems))


def parse_expected_remotes(expect: str) -> list[str]:
    """The declared expectation: `none` for zero remotes, else a comma or space separated list."""
    if expect.strip().lower() == "none":
        return []
    return sorted({token for token in re.split(r"[,\s]+", expect.strip()) if token})


def clone_remotes_probe(clone: Path, expect: str) -> ProbeResult:
    """Step 6: the clone's remotes match the declared expectation."""
    cond = "clone-remotes"
    expected = parse_expected_remotes(expect)
    if not clone.is_dir():
        return unmeasurable(cond, f"the clone {clone} is not a directory, so its remotes could "
                            "not be read")
    try:
        done = subprocess.run(
            ["git", "-C", str(clone), "remote"], capture_output=True, text=True,
            env=clean_env(), timeout=PROBE_TIMEOUT,
        )
    except FileNotFoundError:
        return unmeasurable(cond, "git is not installed, so the clone's remotes could not be read")
    except (OSError, subprocess.TimeoutExpired) as e:
        return unmeasurable(cond, f"git remote could not be measured: {e}")
    if done.returncode != 0:
        return unmeasurable(cond, f"git remote failed in {clone}: {done.stderr.strip()[:160]}")
    actual = sorted({line.strip() for line in done.stdout.splitlines() if line.strip()})
    if actual == expected:
        return holds(cond, f"the clone's remotes {actual or 'none'} match the declared expectation")
    return failed(cond, f"the clone's remotes {actual or 'none'} do not match the declared "
                  f"{expected or 'none'}")


@dataclass(frozen=True)
class Config:
    """What the gate was pointed at, as arguments so no real path is compiled into the tool."""

    run_user: str
    pinned_root: Path
    clone: Path
    expect_remotes: str

    def settings_paths(self) -> list[Path]:
        return [self.pinned_root / "settings" / "settings.json", MANAGED_SETTINGS]


@dataclass(frozen=True)
class Probes:
    """The identity guard and the six condition probes, each a zero-argument reading."""

    identity: Callable[[], ProbeResult]
    run_identity_sudo: Callable[[], ProbeResult]
    examiner_ownership: Callable[[], ProbeResult]
    credential_reach: Callable[[], ProbeResult]
    per_run_ownership: Callable[[], ProbeResult]
    sandbox: Callable[[], ProbeResult]
    clone_remotes: Callable[[], ProbeResult]

    def conditions(self) -> tuple[Callable[[], ProbeResult], ...]:
        return (self.run_identity_sudo, self.examiner_ownership, self.credential_reach,
                self.per_run_ownership, self.sandbox, self.clone_remotes)


def real_probes(cfg: Config) -> Probes:
    """The real measurements, bound to the config. The only Probes `main` ever builds.

    On a real host the gate runs these and nothing overrides them: there is no command-line flag
    that substitutes a probe. The fixture drives the orchestration with stub probes by importing
    this module and constructing its own Probes, which is the only path an override reaches.
    """
    return Probes(
        identity=lambda: identity_probe(cfg.run_user),
        run_identity_sudo=lambda: sudo_probe(cfg.run_user),
        examiner_ownership=lambda: examiner_ownership_probe(cfg.pinned_root, cfg.run_user),
        credential_reach=lambda: credential_probe(cfg.run_user),
        per_run_ownership=lambda: per_run_ownership_probe(cfg.pinned_root, cfg.run_user),
        sandbox=lambda: sandbox_probe(cfg.settings_paths()),
        clone_remotes=lambda: clone_remotes_probe(cfg.clone, cfg.expect_remotes),
    )


@dataclass(frozen=True)
class Outcome:
    """The identity guard's reading and the six condition readings the run produced."""

    guard: ProbeResult
    conditions: tuple[ProbeResult, ...]

    @property
    def clear(self) -> bool:
        return (self.guard.status is Status.HOLDS and len(self.conditions) == len(CONDITIONS)
                and all(c.status is Status.HOLDS for c in self.conditions))


def evaluate(probes: Probes) -> Outcome:
    """The identity guard, then every condition, never short-circuited among the six.

    The guard short-circuits the conditions, and only the guard: a gate run as the wrong identity
    must not go on to run measurements that read a false pass. Once the guard holds, all six run
    regardless of what any one reads, because a partial gate is worse than none.
    """
    guard = probes.identity()
    if guard.status is not Status.HOLDS:
        return Outcome(guard=guard, conditions=())
    return Outcome(guard=guard, conditions=tuple(probe() for probe in probes.conditions()))


def report(outcome: Outcome, out=sys.stdout, err=sys.stderr) -> None:
    """Every reading printed, holds to stdout and refusals to stderr, then the verdict line."""
    guard = outcome.guard
    print(f"unattended-start: {guard.condition}: {guard.status.value}: {guard.detail}",
          file=out if guard.status is Status.HOLDS else err)
    if guard.status is not Status.HOLDS:
        print("unattended-start: REFUSED: the identity self-guard did not hold, so no host "
              f"condition was measured (exit {REFUSED})", file=err)
        return
    for c in outcome.conditions:
        print(f"unattended-start: {c.condition}: {c.status.value}: {c.detail}",
              file=out if c.status is Status.HOLDS else err)
    if outcome.clear:
        held = len(outcome.conditions)
        print(f"unattended-start: clear: {held}/{held} conditions hold (exit {CLEAR})", file=out)
        return
    bad = [f"{c.condition} ({c.status.value})" for c in outcome.conditions
           if c.status is not Status.HOLDS]
    print(f"unattended-start: REFUSED: {len(bad)} condition(s) did not hold: {', '.join(bad)} "
          f"(exit {REFUSED})", file=err)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ADR-0005/D2's fail-closed unattended-start gate.")
    ap.add_argument("--run-user", required=True,
                    help="the declared unprivileged run-user the gate must run as")
    ap.add_argument("--pinned-root", required=True,
                    help="the pinned root holding the examiner and per-run material")
    ap.add_argument("--clone", required=True, help="the dedicated clone whose remotes are checked")
    ap.add_argument("--expect-remotes", required=True,
                    help="the declared remotes: 'none', or a comma or space separated name list")
    a = ap.parse_args(argv)
    cfg = Config(run_user=a.run_user, pinned_root=Path(a.pinned_root), clone=Path(a.clone),
                 expect_remotes=a.expect_remotes)
    outcome = evaluate(real_probes(cfg))
    report(outcome)
    return CLEAR if outcome.clear else REFUSED


if __name__ == "__main__":
    raise SystemExit(main())

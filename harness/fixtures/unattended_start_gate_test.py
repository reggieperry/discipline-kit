#!/usr/bin/env python3
"""Red-first fixture for `harness/unattended_start_gate.py`.

The gate is ADR-0005/D2's fail-closed court (INSTALL-HARDENING Step 6): run as the declared
run-user, assert `id -u` first, then check all six hardening conditions every run, refuse (exit 2)
naming any hole, and read an unmeasurable condition as refuse rather than skip. This is a detector
story, so each planted-hole case was watched failing against a gate that did not yet check that
condition before the check existed.

The host is not hardened, so the host-level probes (sudo, ownership as root, the credential
keyring, bwrap) cannot be exercised for real by a non-root fixture. They sit behind the gate's
probe seam, and the orchestration is driven with injected probe results; the probe logic that can
be tested without root is tested directly.

  THE ORCHESTRATION, injected probe results
  all-clear-0                every probe HOLDS                     -> 0, clear, all six called
  hole-run-identity-sudo-2   one condition FAILED                  -> 2, that condition named
  hole-examiner-ownership-2  one condition FAILED                  -> 2, that condition named
  hole-credential-reach-2    one condition FAILED                  -> 2, that condition named
  hole-per-run-ownership-2   one condition FAILED                  -> 2, that condition named
  hole-sandbox-2             one condition FAILED                  -> 2, that condition named
  hole-clone-remotes-2       the LAST condition FAILED             -> 2, named, all six checked
  wrong-identity-2           the identity guard FAILED             -> 2, no condition measured
  unmeasurable-condition-2   one condition UNMEASURABLE            -> 2, never a skip-to-clear

  THE PROBE LOGIC, tested directly without root
  write-attempt-mechanism    a 0644 owned file, a 0444 file, a dir -> written, refused, written
  remotes-mechanism          a clone with and without a remote     -> match holds, mismatch fails
  credential-gh-token-fails  a shim gh that resolves a token       -> FAILED, the token unprinted
  credential-clean-holds     shims that resolve nothing            -> HOLDS
  credential-env-token-fails a token in the environment            -> FAILED, the value unprinted
  identity-current-holds     the current euid's own account        -> HOLDS
  identity-root-fails        a run-user of root                    -> FAILED, uid 0 named
  identity-mismatch-fails    a real account that is not this one   -> FAILED
  identity-unresolved-2      an account that does not resolve      -> UNMEASURABLE
  per-run-owned-holds        per-run dirs owned by the run-user    -> HOLDS
  per-run-missing-2          a per-run dir absent                  -> UNMEASURABLE
  examiner-scope-excludes-per-run  a sentinel under worktrees      -> never read, examiner is
  settings-carry-sandbox     enabled+failIfUnavailable, or not     -> True, False, None
  sandbox-holds              a succeeding bwrap and enabled settings-> HOLDS
  sandbox-bwrap-fails        a failing bwrap                       -> FAILED, bwrap named
  sandbox-settings-fails     a succeeding bwrap, settings absent   -> FAILED, fails-open named
  sandbox-unparseable-2      a succeeding bwrap, settings unreadable-> UNMEASURABLE

  THE REAL CLI, end to end through main
  cli-wrong-identity-root-2  --run-user root against this process  -> 2, identity named
  cli-unresolved-user-2      --run-user names no account           -> 2, UNMEASURABLE

The credential and write-attempt cases carry the mechanism the mutation table names: the shim gh
resolves a token a file stat would never consult, and the 0644 owned file reads clean to `mode &
022` while its owner can write it, so a probe that stats instead of attempting reads it clean.

Run: python3 harness/fixtures/unattended_start_gate_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import io
import json
import os
import pwd
import subprocess
import sys
import tempfile
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HARNESS))

import unattended_start_gate as gate  # noqa: E402

GATE = HARNESS / "unattended_start_gate.py"
HOLDS = gate.Status.HOLDS
FAILED = gate.Status.FAILED
UNMEAS = gate.Status.UNMEASURABLE

FIELD_COND = {
    "identity": gate.IDENTITY,
    "run_identity_sudo": "run-identity-sudo",
    "examiner_ownership": "examiner-ownership",
    "credential_reach": "credential-reach",
    "per_run_ownership": "per-run-ownership",
    "sandbox": "sandbox",
    "clone_remotes": "clone-remotes",
}
SIX = tuple(f for f in FIELD_COND if f != "identity")


def clean_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """The environment with git's own variables dropped, so a fixture git spawn stays in its tree.

    A pre-commit hook exports GIT_DIR and GIT_INDEX_FILE and a subprocess inherits them, so a
    throwaway repository built here would otherwise be written into the real one.
    """
    src = os.environ if base is None else base
    return {k: v for k, v in src.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
                   env=clean_env())


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main", ".")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "fixture")
    git(path, "commit", "-qm", "baseline", "--allow-empty")
    return path


def shim(bindir: Path, name: str, body: str) -> None:
    path = bindir / name
    path.write_text(body)
    path.chmod(0o755)


def show(name: str, ok: bool, extra: str = "") -> bool:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{extra}")
    return ok


class Spy:
    """A probe that records whether it was called, so all-checked and short-circuit are observable."""

    def __init__(self, result: "gate.ProbeResult") -> None:
        self.result = result
        self.called = False

    def __call__(self) -> "gate.ProbeResult":
        self.called = True
        return self.result


def build_probes(holes: dict[str, tuple] | None = None) -> tuple["gate.Probes", dict[str, Spy]]:
    holes = holes or {}
    spies: dict[str, Spy] = {}
    for field, cond in FIELD_COND.items():
        status, detail = holes.get(field, (HOLDS, f"{cond} holds (stub)"))
        spies[field] = Spy(gate.ProbeResult(cond, status, detail))
    return gate.Probes(**spies), spies


def run_orchestration(probes: "gate.Probes") -> tuple[int, str, "gate.Outcome"]:
    outcome = gate.evaluate(probes)
    out, err = io.StringIO(), io.StringIO()
    gate.report(outcome, out=out, err=err)
    code = gate.CLEAR if outcome.clear else gate.REFUSED
    return code, out.getvalue() + err.getvalue(), outcome


def all_clear_case() -> bool:
    probes, spies = build_probes()
    code, said, outcome = run_orchestration(probes)
    ok = (code == gate.CLEAR and outcome.clear and "clear: 6/6" in said
          and all(spies[f].called for f in FIELD_COND))
    return show("all-clear-0", ok, f": exit {code}")


def hole_case(field: str) -> bool:
    cond = FIELD_COND[field]
    probes, spies = build_probes({field: (FAILED, "planted hole")})
    code, said, outcome = run_orchestration(probes)
    all_checked = all(spies[f].called for f in FIELD_COND)
    ok = (code == gate.REFUSED and not outcome.clear and cond in said and "FAILED" in said
          and all_checked)
    return show(f"hole-{cond}-2", ok, f": exit {code}, every-condition-checked={all_checked}")


def wrong_identity_case() -> bool:
    probes, spies = build_probes({"identity": (FAILED, "running as the operator, not the run-user")})
    code, said, outcome = run_orchestration(probes)
    six_skipped = not any(spies[f].called for f in SIX)
    ok = (code == gate.REFUSED and not outcome.clear and gate.IDENTITY in said
          and spies["identity"].called and six_skipped)
    return show("wrong-identity-2", ok, f": exit {code}, six-skipped={six_skipped}")


def unmeasurable_case() -> bool:
    probes, _ = build_probes({"sandbox": (UNMEAS, "bwrap not installed")})
    code, said, outcome = run_orchestration(probes)
    ok = (code == gate.REFUSED and not outcome.clear and "sandbox" in said
          and "UNMEASURABLE" in said)
    return show("unmeasurable-condition-2", ok, f": exit {code}")


def write_attempt_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        readwrite = tmp / "data0644"
        readwrite.write_text("x\n")
        os.chmod(readwrite, 0o644)
        readonly = tmp / "data0444"
        readonly.write_text("x\n")
        os.chmod(readonly, 0o444)
        directory = tmp / "dir"
        directory.mkdir()
        w644 = gate.writable_by_write_attempt(readwrite)
        w444 = gate.writable_by_write_attempt(readonly)
        wdir = gate.writable_by_write_attempt(directory)
        octal_reads_clean = (os.stat(readwrite).st_mode & 0o022) == 0
        os.chmod(readonly, 0o644)
        ok = w644 is True and w444 is False and wdir is True and octal_reads_clean
    return show("write-attempt-mechanism", ok,
                f": 0644->{w644}, 0444->{w444}, dir->{wdir}, octal-clean-on-0644={octal_reads_clean}")


def remotes_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        clone = init_repo(Path(td) / "clone")
        none_holds = gate.clone_remotes_probe(clone, "none").status is HOLDS
        git(clone, "remote", "add", "origin", "https://example.invalid/x.git")
        mismatch = gate.clone_remotes_probe(clone, "none")
        match = gate.clone_remotes_probe(clone, "origin")
        ok = (none_holds and mismatch.status is FAILED and "origin" in mismatch.detail
              and match.status is HOLDS)
    return show("remotes-mechanism", ok,
                f": none-on-empty={none_holds}, origin-vs-none={mismatch.status.value}, "
                f"origin-vs-origin={match.status.value}")


def credential_gh_token_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        bindir = Path(td) / "bin"
        bindir.mkdir()
        shim(bindir, "gh", "#!/usr/bin/env bash\necho FAKE-TOKEN-VALUE\n")
        shim(bindir, "git", "#!/usr/bin/env bash\ncat >/dev/null 2>&1\nexit 0\n")
        env = clean_env()
        env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
        res = gate.credential_probe("someuser", env=env)
        ok = (res.status is FAILED and "gh auth token resolves a token" in res.detail
              and "FAKE-TOKEN-VALUE" not in res.detail)
    return show("credential-gh-token-fails", ok, f": {res.status.value}, token-unprinted="
                f"{'FAKE-TOKEN-VALUE' not in res.detail}")


def credential_clean_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        bindir = Path(td) / "bin"
        bindir.mkdir()
        shim(bindir, "gh", "#!/usr/bin/env bash\nexit 1\n")
        shim(bindir, "git", "#!/usr/bin/env bash\ncat >/dev/null 2>&1\nexit 0\n")
        env = clean_env()
        for key in gate.CREDENTIAL_ENV_KEYS:
            env.pop(key, None)
        env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
        res = gate.credential_probe("someuser", env=env)
        ok = res.status is HOLDS
    return show("credential-clean-holds", ok, f": {res.status.value}")


def credential_env_token_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        bindir = Path(td) / "bin"
        bindir.mkdir()
        shim(bindir, "gh", "#!/usr/bin/env bash\nexit 1\n")
        shim(bindir, "git", "#!/usr/bin/env bash\ncat >/dev/null 2>&1\nexit 0\n")
        env = clean_env()
        env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
        env["GH_TOKEN"] = "FAKE-ENV-TOKEN"
        res = gate.credential_probe("someuser", env=env)
        ok = (res.status is FAILED and "environment" in res.detail
              and "FAKE-ENV-TOKEN" not in res.detail)
    return show("credential-env-token-fails", ok, f": {res.status.value}, value-unprinted="
                f"{'FAKE-ENV-TOKEN' not in res.detail}")


def identity_current_case() -> bool:
    me = pwd.getpwuid(os.geteuid()).pw_name
    res = gate.identity_probe(me)
    return show("identity-current-holds", res.status is HOLDS, f": {res.status.value}")


def identity_root_case() -> bool:
    res = gate.identity_probe("root")
    ok = res.status is FAILED and "uid 0" in res.detail
    return show("identity-root-fails", ok, f": {res.status.value}")


def identity_mismatch_case() -> bool:
    me = os.geteuid()
    other = next((u.pw_name for u in pwd.getpwall() if u.pw_uid not in (0, me)), None)
    if other is None:
        return show("identity-mismatch-fails", False, ": no distinct account to test against")
    res = gate.identity_probe(other)
    ok = res.status is FAILED and "not" in res.detail
    return show("identity-mismatch-fails", ok, f": {res.status.value}")


def identity_unresolved_case() -> bool:
    res = gate.identity_probe("no-such-account-xyzzy")
    return show("identity-unresolved-2", res.status is UNMEAS, f": {res.status.value}")


def per_run_holds_case() -> bool:
    me = pwd.getpwuid(os.geteuid()).pw_name
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "pinned"
        root.mkdir()
        for name in gate.PER_RUN_SUBDIRS:
            (root / name).mkdir()
        res = gate.per_run_ownership_probe(root, me)
    return show("per-run-owned-holds", res.status is HOLDS, f": {res.status.value}")


def per_run_missing_case() -> bool:
    me = pwd.getpwuid(os.geteuid()).pw_name
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "pinned"
        root.mkdir()
        (root / "worktrees").mkdir()
        res = gate.per_run_ownership_probe(root, me)
        ok = res.status is UNMEAS and "absent" in res.detail
    return show("per-run-missing-2", ok, f": {res.status.value}")


def examiner_scope_case() -> bool:
    """examiner-ownership walks the examiner subtrees, never the run-user-owned per-run dirs.

    The pinned root's per-run children are run-user-owned by design, so a probe that walked the
    whole root would read them as examiner holes on a hardened host. This pins the scope: a
    sentinel under worktrees never enters the reading, and the examiner material does.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "pinned"
        root.mkdir()
        for name in gate.EXAMINER_SUBDIRS:
            (root / name).mkdir()
        for name in gate.PER_RUN_SUBDIRS:
            (root / name).mkdir()
        (root / "worktrees" / "SENTINEL-PER-RUN").write_text("run-user material\n")
        (root / "settings" / "grader.json").write_text("{}\n")
        res = gate.examiner_ownership_probe(root, "someuser")
        ok = (res.status is FAILED and "SENTINEL-PER-RUN" not in res.detail
              and "grader.json" in res.detail)
    return show("examiner-scope-excludes-per-run", ok,
                f": {res.status.value}, per-run-untouched={'SENTINEL-PER-RUN' not in res.detail}")


def settings_carry_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        good = tmp / "good.json"
        good.write_text(json.dumps({"sandbox": {"enabled": True, "failIfUnavailable": True}}))
        missing = tmp / "missing.json"
        missing.write_text(json.dumps({"sandbox": {"enabled": True}}))
        broken = tmp / "broken.json"
        broken.write_text("{ not json")
        carried, _ = gate.settings_carry_sandbox([good])
        absent, _ = gate.settings_carry_sandbox([missing])
        unparseable, _ = gate.settings_carry_sandbox([broken])
        ok = carried is True and absent is False and unparseable is None
    return show("settings-carry-sandbox", ok,
                f": enabled+fail={carried}, missing-key={absent}, unparseable={unparseable}")


def sandbox_cases() -> list[bool]:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        good = tmp / "good.json"
        good.write_text(json.dumps({"sandbox": {"enabled": True, "failIfUnavailable": True}}))
        missing = tmp / "missing.json"
        missing.write_text(json.dumps({"sandbox": {"enabled": True}}))
        broken = tmp / "broken.json"
        broken.write_text("{ not json")
        holds = gate.sandbox_probe([good], bwrap="/bin/true")
        bwrap_fail = gate.sandbox_probe([good], bwrap="/bin/false")
        settings_fail = gate.sandbox_probe([missing], bwrap="/bin/true")
        unparseable = gate.sandbox_probe([broken], bwrap="/bin/true")
    return [
        show("sandbox-holds", holds.status is HOLDS, f": {holds.status.value}"),
        show("sandbox-bwrap-fails", bwrap_fail.status is FAILED and "bwrap" in bwrap_fail.detail,
             f": {bwrap_fail.status.value}"),
        show("sandbox-settings-fails",
             settings_fail.status is FAILED and "fails open" in settings_fail.detail,
             f": {settings_fail.status.value}"),
        show("sandbox-unparseable-2", unparseable.status is UNMEAS, f": {unparseable.status.value}"),
    ]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(GATE), *args], capture_output=True, text=True,
                          env=clean_env())


def cli_wrong_identity_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        got = run_cli("--run-user", "root", "--pinned-root", td, "--clone", td,
                      "--expect-remotes", "none")
    said = got.stdout + got.stderr
    ok = got.returncode == gate.REFUSED and gate.IDENTITY in said and "REFUSED" in said
    return show("cli-wrong-identity-root-2", ok, f": exit {got.returncode}")


def cli_unresolved_user_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        got = run_cli("--run-user", "no-such-account-xyzzy", "--pinned-root", td, "--clone", td,
                      "--expect-remotes", "none")
    said = got.stdout + got.stderr
    ok = got.returncode == gate.REFUSED and gate.IDENTITY in said and "UNMEASURABLE" in said
    return show("cli-unresolved-user-2", ok, f": exit {got.returncode}")


def main() -> int:
    if not GATE.is_file():
        print(f"unattended_start_gate_test: gate not found at {GATE}", file=sys.stderr)
        return 2
    results = [
        all_clear_case(),
        *[hole_case(field) for field in SIX],
        wrong_identity_case(),
        unmeasurable_case(),

        write_attempt_case(),
        remotes_case(),
        credential_gh_token_case(),
        credential_clean_case(),
        credential_env_token_case(),
        identity_current_case(),
        identity_root_case(),
        identity_mismatch_case(),
        identity_unresolved_case(),
        per_run_holds_case(),
        per_run_missing_case(),
        examiner_scope_case(),
        settings_carry_case(),
        *sandbox_cases(),

        cli_wrong_identity_case(),
        cli_unresolved_user_case(),
    ]
    failed = results.count(False)
    print(f"unattended_start_gate_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Red-first fixture for `install-chain.sh`.

install-chain.sh upgrades another repository ON THIS MACHINE to the SDLC chain capability, sourced
from a branch of the kit, in three moves and zero chain-code changes: a SHARED, SHA-named, immutable
TOOL SNAPSHOT archived out of the branch into a cache outside every target; the kit's rules VENDORED
into the target's `.claude/rules/`; and a per-target chain PROFILE written into the target. The tools
resolve their own siblings by layout and read the target's posture from ITS profile, so a per-target
`pinned_root` dissolves the cross-target story-id collision with no runtime edit.

The fixture is hermetic: it builds a scratch KIT repository once (the real chain runtime and rules
copied in, committed on a branch), and per case a scratch TARGET, a throwaway tools cache, and a
throwaway pinned root, all under temp directories. It never touches a real repository and never runs
a chain. Every git spawn drops `GIT_*` from its environment, because a pre-commit hook exports
`GIT_DIR`/`GIT_INDEX_FILE` and a subprocess that inherits them operates on the real repository -- the
defect this repository has paid for four times.

  materialization     the 12 runtime files land at <tools>/<sha>/, PROVENANCE      -> present
                      carries the branch's sha, and NO __pycache__ or .git leaked     no leak
  vendoring           the kit's rules reach the target's .claude/rules/            -> present
  profile             terminal/push paired, harness_version copied from the        -> correct
                      branch, pinned_root the per-target one, trusted_base covers
                      harness/chain/, and pinned_root is NOT the kit's own default
  wiring              the SHARED tools resolve the TARGET's profile: core.py        -> 2 then 0
                      startup exits 2 before the pinned root exists (fail closed,
                      naming it) and 0 after mkdir, printing the per-target root
  terminal-open-pr    the other terminal posture pairs the other way               -> correct
  collision           two targets take DISTINCT default pinned roots               -> distinct
  idempotency         a second identical run leaves the profile byte-identical,    -> untouched
                      backs it up, and re-uses the snapshot
  existing-profile    a pre-existing target profile is never clobbered: it is      -> preserved
                      backed up, a merge note printed, the sentinel survives

THE WIRING CASE IS THE END-TO-END PROOF and needs no live chain spawn: core.py startup does no
`claude` spawn, it only reads the target's profile and resolves the declared pinned root. Exit 2
before the root exists is the fail-closed gate (the root is created by the machine-hardening
checklist, which the method deliberately does not run); exit 0 after `mkdir` proves the shared tools,
run from the snapshot OUTSIDE the target, read the target's OWN posture. The mutations this catches:
a working-tree `cp` for the archive (materialization sees __pycache__); the kit's own pinned_root
copied instead of a per-target one (collision, profile); the terminal/push pairing inverted (profile,
and startup would VOID on push-unpaired); an existing profile clobbered (existing-profile).

Run: python3 harness/fixtures/install_chain_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "install-chain.sh"
RULES_SRC = REPO / "claude-project" / "rules"

BRANCH = "docs/sdlc-chain-design"

# The runtime the snapshot must carry, as archive-relative paths. The eight sequencer sources plus
# the two files the sequencer and the receipt reach by layout, plus the two unattended-run modules.
EXPECTED_TOOLS = (
    "harness/chain/core.py",
    "harness/chain/advance.py",
    "harness/chain/attempt.py",
    "harness/chain/invoke.py",
    "harness/chain/loader.py",
    "harness/chain/merge.py",
    "harness/chain/receipt.py",
    "harness/chain/sequencer.py",
    "harness/transcript_audit.py",
    "harness/rule_grades.py",
    "harness/unattended_run.py",
    "harness/unattended_start_gate.py",
)

# A distinctive version written into the scratch kit's profile, so a target that carries it proves
# install-chain COPIED it from the branch rather than hard-coding a value.
SENTINEL_VERSION = "9.9.999-installchain-test"

# The kit's own default root shape, which a per-target profile must NOT be. If install-chain copied
# the kit's profile.toml this bare form would appear; a per-target run appends a slug.
KIT_DEFAULT_ROOT = "/var/lib/discipline-chain/"


def clean_env() -> dict[str, str]:
    """The caller's environment with git's own variables dropped (the inherited-GIT_DIR scar)."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> str:
    """Git confined to a scratch repository, signing pinned off so no operator config prompts."""
    done = subprocess.run(
        ["git", "-c", "tag.gpgsign=false", "-c", "commit.gpgsign=false", "-C", str(repo), *args],
        capture_output=True, text=True, check=True, env=clean_env(),
    )
    return done.stdout.strip()


def build_kit() -> Path:
    """A scratch kit: install-chain.sh, the real runtime, the rules, and a profile, on BRANCH.

    Built once and reused read-only across cases (install-chain only reads the kit). The runtime
    files are the REAL ones, so the wiring case genuinely runs core.py startup out of the snapshot.
    """
    root = Path(tempfile.mkdtemp(prefix="installchain-kit-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    shutil.copy(INSTALLER, root / "install-chain.sh")
    for rel in EXPECTED_TOOLS:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, dst)
    rules = root / "claude-project" / "rules"
    rules.mkdir(parents=True)
    for md in sorted(RULES_SRC.glob("*.md")):
        shutil.copy(md, rules / md.name)
    chain = root / ".claude" / "chain"
    chain.mkdir(parents=True)
    (chain / "profile.toml").write_text(
        "# scratch kit profile\n"
        'terminal = "open-pr"\n'
        'push = "branches-only"\n'
        f'harness_version = "{SENTINEL_VERSION}"\n'
        'settings_sources = "pinned"\n'
        'pinned_root = "/var/lib/discipline-chain/"\n'
        'trusted_base = [".claude/", "harness/chain/"]\n'
    )
    git(root, "init", "-q", "-b", BRANCH, ".")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "fixture")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "scratch kit")
    # An UNTRACKED __pycache__, planted after the commit, as any run Python project accumulates.
    # git archive (the committed tree at a sha) excludes it; a working-tree cp of the directory
    # would drag it into the snapshot, which is what the materialization case's no-leak assertion
    # is watching for -- the difference between archiving a sha and copying the working tree.
    cache = root / "harness" / "chain" / "__pycache__"
    cache.mkdir()
    (cache / "loader.cpython-311.pyc").write_bytes(b"\x00leaked bytecode\x00")
    return root


KIT = build_kit()
KIT_SHA = git(KIT, "rev-parse", BRANCH)
RULE_NAMES = {p.name for p in RULES_SRC.glob("*.md")}


def scratch_target(td: Path, name: str = "widget") -> Path:
    """A committed scratch target repository holding an empty `.claude/`."""
    target = td / name
    (target / ".claude").mkdir(parents=True)
    git(target, "init", "-q", "-b", "main", ".")
    git(target, "config", "user.email", "fixture@example.invalid")
    git(target, "config", "user.name", "fixture")
    (target / ".claude" / ".keep").write_text("")
    git(target, "add", "-A")
    git(target, "commit", "-qm", "empty .claude")
    return target


def install_chain(target: Path, td: Path, *extra: str,
                  terminal: str = "merge-local",
                  pinned_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Drive the real install-chain.sh (copied into the scratch kit) against a scratch target."""
    args = ["bash", str(KIT / "install-chain.sh"),
            "--dir", str(target), "--terminal", terminal,
            "--branch", BRANCH, "--tools-dir", str(td / "tools")]
    if pinned_root is not None:
        args += ["--pinned-root", str(pinned_root)]
    args += list(extra)
    return subprocess.run(args, capture_output=True, text=True, env=clean_env())


def startup(target: Path) -> subprocess.CompletedProcess[str]:
    """Run the SHARED snapshot's core.py startup against the target, from outside the target tree."""
    core = KIT_SHA_SNAPSHOT_HOLDER["snap"] / "harness" / "chain" / "core.py"
    return subprocess.run(
        ["python3", str(core), "startup", "--root", str(target)],
        capture_output=True, text=True, env=clean_env(),
    )


# The tools cache is per case, so the snapshot path is discovered per case and stashed here for
# `startup` to read. Keeping it in one place avoids threading the path through every helper.
KIT_SHA_SNAPSHOT_HOLDER: dict[str, Path] = {}


class Failure(Exception):
    pass


def expect(cond: bool, why: str) -> None:
    if not cond:
        raise Failure(why)


def snapshot_dir(td: Path) -> Path:
    return td / "tools" / KIT_SHA


def profile_of(target: Path) -> dict:
    with open(target / ".claude" / "chain" / "profile.toml", "rb") as f:
        return tomllib.load(f)


def case(name: str, body) -> bool:
    try:
        with tempfile.TemporaryDirectory() as td:
            body(Path(td))
        print(f"  ok   {name}")
        return True
    except Failure as e:
        print(f"  FAIL {name}: {e}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  FAIL {name}: fixture git call failed: {e.stderr.strip()[:300]}")
        return False


def materialization(td: Path) -> None:
    target = scratch_target(td)
    got = install_chain(target, td, pinned_root=td / "root")
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    snap = snapshot_dir(td)
    for rel in EXPECTED_TOOLS:
        expect((snap / rel).is_file(), f"missing tool {rel} under {snap}")
    leaked = [str(p) for p in snap.rglob("*") if p.name in ("__pycache__", ".git")]
    expect(not leaked, f"the working-tree drag-ins leaked into the snapshot: {leaked}")
    prov = (snap / "PROVENANCE").read_text()
    expect(KIT_SHA in prov, f"PROVENANCE must carry the branch sha {KIT_SHA}, got: {prov[:200]}")


def vendoring(td: Path) -> None:
    target = scratch_target(td)
    got = install_chain(target, td, pinned_root=td / "root")
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {(got.stdout + got.stderr)[:400]}")
    dst = target / ".claude" / "rules"
    landed = {p.name for p in dst.glob("*.md")}
    expect(landed, "no rules were vendored into the target")
    expect(landed <= RULE_NAMES, f"a vendored rule is not a kit rule: {landed - RULE_NAMES}")
    expect("python-style.md" in landed, f"expected a known kit rule to land, got: {sorted(landed)[:5]}")


def profile(td: Path) -> None:
    target = scratch_target(td)
    root = td / "root"
    got = install_chain(target, td, terminal="merge-local", pinned_root=root)
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {(got.stdout + got.stderr)[:400]}")
    p = profile_of(target)
    expect(p["terminal"] == "merge-local", f"terminal wrong: {p.get('terminal')!r}")
    expect(p["push"] == "never", f"push must pair with merge-local as 'never', got {p.get('push')!r}")
    expect(p["harness_version"] == SENTINEL_VERSION,
           f"harness_version must be copied from the branch profile, got {p.get('harness_version')!r}")
    expect(p["pinned_root"] == str(root),
           f"pinned_root must be the per-target one {root}, got {p.get('pinned_root')!r}")
    expect(p["pinned_root"] != KIT_DEFAULT_ROOT,
           "pinned_root is the kit's own bare default -- the kit's profile was copied")
    expect("harness/chain/" in p["trusted_base"],
           f"trusted_base must cover harness/chain/, got {p.get('trusted_base')!r}")


def wiring(td: Path) -> None:
    target = scratch_target(td)
    root = td / "root"
    got = install_chain(target, td, terminal="merge-local", pinned_root=root)
    expect(got.returncode == 0, f"install failed: {(got.stdout + got.stderr)[:400]}")
    KIT_SHA_SNAPSHOT_HOLDER["snap"] = snapshot_dir(td)

    before = startup(target)
    said = before.stdout + before.stderr
    expect(before.returncode == 2, f"before mkdir root, want exit 2, got {before.returncode}: {said[:400]}")
    expect(str(root) in said, f"the fail-closed refusal must name the missing root, got: {said[:400]}")

    root.mkdir(parents=True)
    after = startup(target)
    said = after.stdout + after.stderr
    expect(after.returncode == 0, f"after mkdir root, want exit 0, got {after.returncode}: {said[:400]}")
    expect(str(root.resolve()) in said,
           f"startup must print the per-target pinned root, got: {said[:400]}")


def terminal_open_pr(td: Path) -> None:
    target = scratch_target(td)
    got = install_chain(target, td, terminal="open-pr", pinned_root=td / "root")
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {(got.stdout + got.stderr)[:400]}")
    p = profile_of(target)
    expect(p["terminal"] == "open-pr", f"terminal wrong: {p.get('terminal')!r}")
    expect(p["push"] == "branches-only",
           f"push must pair with open-pr as 'branches-only', got {p.get('push')!r}")


def collision(td: Path) -> None:
    alpha = scratch_target(td, "alpha")
    beta = scratch_target(td, "beta")
    # No --pinned-root: each takes its per-target DEFAULT, derived from the target basename.
    a = install_chain(alpha, td)
    b = install_chain(beta, td)
    expect(a.returncode == 0 and b.returncode == 0,
           f"install failed: a={a.returncode} b={b.returncode}")
    pa = profile_of(alpha)["pinned_root"]
    pb = profile_of(beta)["pinned_root"]
    expect(pa != pb, f"two targets collided on one pinned root: {pa!r}")
    expect("alpha" in pa and "beta" in pb, f"the default roots must carry the slug: {pa!r}, {pb!r}")
    expect(pa != KIT_DEFAULT_ROOT and pb != KIT_DEFAULT_ROOT,
           "a default root is the kit's own bare default -- the collision is not dissolved")


def idempotency(td: Path) -> None:
    target = scratch_target(td)
    root = td / "root"
    first = install_chain(target, td, pinned_root=root)
    expect(first.returncode == 0, f"first run failed: {(first.stdout + first.stderr)[:400]}")
    prof = target / ".claude" / "chain" / "profile.toml"
    bytes_after_first = prof.read_bytes()

    second = install_chain(target, td, pinned_root=root)
    said = second.stdout + second.stderr
    expect(second.returncode == 0, f"second run failed: {said[:400]}")
    expect(prof.read_bytes() == bytes_after_first,
           "a second identical run changed the profile -- it must be left untouched")
    expect("NOT overwritten" in said, f"the second run must report the profile untouched, got: {said[:400]}")
    baks = list((target / ".claude" / "chain").glob("profile.toml.bak-*"))
    expect(baks, "the second run must back the existing profile up before leaving it")
    snap = snapshot_dir(td)
    present = [rel for rel in EXPECTED_TOOLS if (snap / rel).is_file()]
    expect(len(present) == len(EXPECTED_TOOLS), f"the snapshot lost files on re-run: {present}")


def existing_profile_preserved(td: Path) -> None:
    target = scratch_target(td)
    chain = target / ".claude" / "chain"
    chain.mkdir(parents=True)
    prof = chain / "profile.toml"
    prof.write_text('# operator-authored\nsentinel = "operator-authored-do-not-clobber"\n')

    got = install_chain(target, td, pinned_root=td / "root")
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said[:400]}")
    expect("operator-authored-do-not-clobber" in prof.read_text(),
           "an existing target profile was CLOBBERED -- it must never be overwritten")
    expect("NOT overwritten" in said, f"the guard must print a merge note, got: {said[:400]}")
    baks = list(chain.glob("profile.toml.bak-*"))
    expect(baks, "the existing profile must be backed up before the guard leaves it in place")


def main() -> int:
    if not INSTALLER.is_file():
        print(f"install_chain_test: install-chain.sh not found at {INSTALLER}", file=sys.stderr)
        return 2
    if not RULES_SRC.is_dir():
        print(f"install_chain_test: rules source not found at {RULES_SRC}", file=sys.stderr)
        return 2
    results = [
        case("materialization", materialization),
        case("vendoring", vendoring),
        case("profile", profile),
        case("wiring", wiring),
        case("terminal-open-pr", terminal_open_pr),
        case("collision", collision),
        case("idempotency", idempotency),
        case("existing-profile-preserved", existing_profile_preserved),
    ]
    failed = results.count(False)
    print(f"install_chain_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

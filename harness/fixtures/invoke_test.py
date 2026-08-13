#!/usr/bin/env python3
"""Red-first fixture for `harness/chain/invoke.py` and `harness/transcript_audit.py`.

The invocation layer is where ADR-0004's decisions become a composed command line, and every
case here asserts the strongest fact that composition can carry without running the real
harness: what settings file was materialized where and with what bytes, what the argv and
environment were composed to, what the prompt is byte-for-byte, and what the filesystem holds
after each act. The harness binary sits behind an injectable command seam, so every case that
spawns one spawns a stub written here; no case invokes the real `claude`, and the residue that
only a live phase can discharge (hook output absent from a real transcript) is recorded in
STORY-0012's notes rather than claimed by a stub.

Decisions under test: ADR-0004/D1 (the prompt is the one instruction channel, composed from the
pinned brief and nothing else; a dead phase is a fresh invocation, never resumed), D2 (worktrees
are sequencer-owned, outside the parent, cleared before every attempt and removed after the
seam), D3 (pinned settings materialized per invocation, user scope excluded, no
`.claude/agents/` in the judged tree), D4 (a compaction-marked or dead phase re-runs fresh),
D5 (the harness version is gated against the profile's pin before any phase), and
ADR-0003/D6 read at both trees (porcelain empty in the parent AND the phase worktree).

  THE VERSION GATE (ADR-0004/D5)
  version-match-0           the stub reports the pinned version     -> 0, matches the pin
  version-mismatch-2        the stub reports a newer version        -> 2, harness-version-mismatch
  version-unpinned-2        a profile with no harness_version       -> 2, harness-version-unpinned
  version-unreadable-2      a --version with no number in it        -> 2, harness-version-unread
  version-invalid-utf8-2    a --version that is not UTF-8           -> 2, harness-version-unread,
                                                                       never the verdict-shaped 1

  THE COMPOSED PROMPT (ADR-0004/D1, D3)
  prompt-byte-identical     the composed prompt vs the pinned brief -> 0, byte-for-byte equal
  brief-absent-2            no pinned brief of that name            -> 2, brief-absent
  brief-symlink-out-2       a brief symlinked out of the root       -> 2, outside the pinned root
  agents-dir-known-bad-2    .claude/agents/ in the judged tree      -> 2, agents-directory,
                                                                       the judged tree's path named
  agents-dir-empty-known-bad-2
                            an EMPTY .claude/agents/ in the judged  -> 2, agents-directory:
                            tree                                       presence, never content
  settings-local-known-bad-2 a COMMITTED settings.local.json        -> 2, settings-local

  THE SETTINGS PINNING (ADR-0004/D3): the per-invocation twin of core_test's decoy-user-hook
  settings-pinning-decoy    a decoy user-scope SessionStart hook    -> 0, materialized = pinned
                            and a decoy CLAUDE_CONFIG_DIR exported     bytes, env repointed at the
                                                                       owned home, decoy absent
  settings-collision-2      the workspace already carries settings  -> 2, settings-collision
  settings-unpinned-2       no pinned settings file                 -> 2, settings-unpinned
  home-not-empty-2          an isolated home carrying a file        -> 2, home-not-empty

  THE WORKTREE CUSTODY (ADR-0004/D2, ADR-0003/D6 at both trees)
  worktree-outside-parent-0 phase-worktree at the composed path     -> 0, outside the parent,
                                                                       registered, materialized
  worktree-live-porcelain-0 seam-check with the worktree live       -> 0, porcelain empty twice
  seam-dirt-in-worktree-2   untracked dirt in the phase worktree    -> 2, the dirt named
  seam-dirt-in-parent-2     untracked dirt in the parent            -> 2, the dirt named
  settings-tampered-2       the fence edited during the phase       -> 2, settings-tampered
  settings-missing-2        the fence deleted during the phase      -> 2, settings-missing
  seam-close-removes-0      seam-close after a clean seam           -> 0, path gone, unregistered
  seam-close-unchecked-2    seam-close with the fence still live    -> 2, seam-not-checked, the
                                                                       evidence preserved

  THE FRESH ATTEMPT (ADR-0004/D1, D4)
  phase-death-fresh-attempt a stub that dies mid-phase, then one    -> 2 phase-death, corpse left;
                            that completes, same composed path         then 0, corpse cleared,
                                                                       same pinned path, no
                                                                       resume-shaped flag logged
  phase-compaction-death    a result record AND a compaction record -> 2, phase-death, compacted
  resume-liveness-compacted core.py resume over a compacted stream  -> 0, liveness compacted

  THE TRANSCRIPT AUDIT (ADR-0004/D1: audit, not control flow)
  audit-flags-task-start-1  a stream carrying task_started          -> 1, spawn-event named
  audit-flags-notification-1 task_notification without its start    -> 1, spawn-event named
  audit-clean-0             a spawn-free phase stream               -> 0, denominators printed
  audit-empty-2             nothing to examine                      -> 2, VOID

The task_started record planted here carries the fields the D7 probe measured at 2.1.224
(`docs/probe/probe-stream.jsonl` line 45): type system, subtype task_started, a task_id and a
subagent_type. The audit's parser was grounded in that retained record before it was written.

Run: python3 harness/fixtures/invoke_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
INVOKE = HARNESS / "chain" / "invoke.py"
CORE = HARNESS / "chain" / "core.py"
AUDIT = HARNESS / "transcript_audit.py"

VOID = "invoke: VOID"
STORY = "STORY-0042"
SESSION = "6f1c9a2e-0b3d-4e77-9f21-8c5a4d6b1e30"
PIN = "2.1.224"
DECOY_MARKER = "USER-SCOPE-HOOK-FIRED"

# The default pinned brief carries the shapes that break naive composition: an em dash, quotes,
# a shell-metacharacter, a blank line, and NO trailing newline, so byte-for-byte is the only
# comparison that passes.
BRIEF = ('Phase 2: attest the tree — cite or stay silent.\n\n'
         'Say "blocked" on any $DOUBT.').encode()

SETTINGS = b'{"permissions": {"deny": ["Bash(rm:*)"]}}\n'

PROFILE = """terminal = "open-pr"
push = "branches-only"
harness_version = "{version}"
settings_sources = "pinned"
pinned_root = "{pinned}"
trusted_base = [".claude/", "harness/", "scripts/"]
"""

# The injectable harness: answers --version with the pinned string shape the probe recorded
# ("2.1.224 (Claude Code)"), logs its argv, HOME, CLAUDE_CONFIG_DIR and cwd so the composed
# environment reaching the child is an observation, then behaves as the case demands. Templated
# by .replace() because the JSON bodies carry braces that str.format would eat.
STUB = """#!/usr/bin/env bash
if [ "${1:-}" = "--version" ]; then
  printf '%s\\n' "__VERSION__ (Claude Code)"
  exit 0
fi
printf 'argv %s\\n' "$*" >> "__LOG__"
printf 'HOME %s\\n' "$HOME" >> "__LOG__"
printf 'CONFIG %s\\n' "${CLAUDE_CONFIG_DIR:-unset}" >> "__LOG__"
printf 'CWD %s\\n' "$PWD" >> "__LOG__"
__BEHAVIOR__
"""

COMPLETES = """printf '%s\\n' '{"type":"system","session_id":"__SESSION__"}'
printf '%s\\n' '{"type":"result","session_id":"__SESSION__"}'
exit 0"""

# A death: events and no result record, ADR-0001/D5's liveness signal in its negative form,
# plus a half-done file in the workspace so the corpse is observably dirty.
DIES = """printf '%s\\n' '{"type":"system","session_id":"__SESSION__"}'
printf 'half-done\\n' > "$PWD/half-done-work.txt"
exit 1"""

COMPACTS = """printf '%s\\n' '{"type":"system","session_id":"__SESSION__"}'
printf '%s\\n' '{"type":"system","compact_metadata":{"trigger":"auto"}}'
printf '%s\\n' '{"type":"result","session_id":"__SESSION__"}'
exit 0"""


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


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("the judged tree\n")
    git(path, "init", "-q", "-b", "main", ".")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "fixture")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "baseline", "--allow-empty")
    return path


def pinned_tree(td: Path, *, brief: bytes = BRIEF, settings: bytes | None = SETTINGS,
                brief_name: str = "phase-2-tester") -> Path:
    root = td / "pinned"
    (root / "briefs").mkdir(parents=True)
    (root / "briefs" / brief_name).write_bytes(brief)
    if settings is not None:
        (root / "settings").mkdir()
        (root / "settings" / "settings.json").write_bytes(settings)
    return root


def kit_tree(td: Path, pinned: Path, *, version: str = PIN, profile: str | None = None) -> Path:
    """The sequencer's own repository-shaped tree: the profile is the grader's, never the graded."""
    kit = td / "kit"
    chain = kit / ".claude" / "chain"
    chain.mkdir(parents=True)
    body = PROFILE.format(version=version, pinned=pinned) if profile is None else profile
    (chain / "profile.toml").write_text(body)
    return kit


def stub_harness(td: Path, *, version: str = PIN, behavior: str = COMPLETES,
                 name: str = "claude-stub") -> tuple[Path, Path]:
    log = td / "harness.log"
    path = td / name
    body = (STUB.replace("__VERSION__", version).replace("__LOG__", str(log))
                .replace("__BEHAVIOR__", behavior).replace("__SESSION__", SESSION))
    path.write_text(body)
    path.chmod(0o755)
    return path, log


def run_tool(tool: Path, *args: str, env: dict[str, str] | None = None
             ) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(tool), *args],
        capture_output=True, text=True, env=clean_env() if env is None else env,
    )


def judge(name: str, got: subprocess.CompletedProcess[str], *, want: int, marker: str,
          absent: str | tuple[str, ...] = (), present: tuple[str, ...] = (),
          faults: tuple[str, ...] = ()) -> bool:
    """Compare exit code, required markers, forbidden markers, and caller-established state.

    `faults` arrives already worded: whatever the caller measured on the filesystem before
    judging. It lands here so the verdict line is the verdict rather than a first word a later
    complaint contradicts.
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


class Bench:
    """One throwaway world: a judged repository, a pinned root, a kit profile, a stub harness."""

    def __init__(self, td: Path, *, version: str = PIN, behavior: str = COMPLETES,
                 settings: bytes | None = SETTINGS, profile_template: str | None = None):
        self.td = td
        self.repo = init_repo(td / "judged")
        self.pinned = pinned_tree(td, settings=settings)
        profile = None if profile_template is None else \
            profile_template.format(pinned=self.pinned)
        self.kit = kit_tree(td, self.pinned, profile=profile)
        self.harness, self.log = stub_harness(td, version=version, behavior=behavior)
        self.workspace = td / "workspace"
        self.workspace.mkdir()
        self.home = td / "owned-home"

    def compose(self, *extra: str, env: dict[str, str] | None = None,
                brief: str = "phase-2-tester") -> subprocess.CompletedProcess[str]:
        return run_tool(INVOKE, "compose", "--root", str(self.kit), "--repo", str(self.repo),
                        "--workspace", str(self.workspace), "--brief", brief,
                        "--home", str(self.home), "--harness", str(self.harness), *extra,
                        env=env)

    def worktree_path(self, attempt: str = "1") -> Path:
        return self.pinned / "worktrees" / STORY / f"attempt-{attempt}"

    def phase_worktree(self, attempt: str = "1") -> subprocess.CompletedProcess[str]:
        return run_tool(INVOKE, "phase-worktree", "--root", str(self.kit),
                        "--repo", str(self.repo), "--story", STORY, "--attempt", attempt)

    def seam(self, act: str, attempt: str = "1") -> subprocess.CompletedProcess[str]:
        return run_tool(INVOKE, act, "--root", str(self.kit), "--repo", str(self.repo),
                        "--story", STORY, "--attempt", attempt)

    def run_phase(self, attempt: str = "1") -> subprocess.CompletedProcess[str]:
        return run_tool(INVOKE, "run", "--root", str(self.kit), "--repo", str(self.repo),
                        "--story", STORY, "--attempt", attempt, "--brief", "phase-2-tester",
                        "--stream", str(self.td / "runs" / "phase-2.stream"),
                        "--harness", str(self.harness))

    def materialize_into_worktree(self, attempt: str = "1") -> subprocess.CompletedProcess[str]:
        """Compose against the live worktree, which is how the seam cases arm the fence."""
        return run_tool(INVOKE, "compose", "--root", str(self.kit), "--repo", str(self.repo),
                        "--workspace", str(self.worktree_path(attempt)), "--brief",
                        "phase-2-tester", "--home", str(self.home),
                        "--harness", str(self.harness))


def version_match_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        got = run_tool(INVOKE, "gate", "--root", str(b.kit), "--harness", str(b.harness))
        return judge("version-match-0", got, want=0, marker="matches the pin", present=(PIN,))


def version_mismatch_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), version="2.1.300")
        got = run_tool(INVOKE, "gate", "--root", str(b.kit), "--harness", str(b.harness))
        return judge("version-mismatch-2", got, want=2, marker="harness-version-mismatch",
                     present=("2.1.300", PIN, "probe"))


def version_unpinned_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), profile_template='terminal = "open-pr"\npush = "branches-only"\n'
                                             'pinned_root = "{pinned}"\n')
        got = run_tool(INVOKE, "gate", "--root", str(b.kit), "--harness", str(b.harness))
        return judge("version-unpinned-2", got, want=2, marker="harness-version-unpinned")


def version_unreadable_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        b = Bench(tmp)
        bare = tmp / "versionless"
        bare.write_text('#!/usr/bin/env bash\nprintf "Claude Code\\n"\nexit 0\n')
        bare.chmod(0o755)
        got = run_tool(INVOKE, "gate", "--root", str(b.kit), "--harness", str(bare))
        return judge("version-unreadable-2", got, want=2, marker="harness-version-unread")


def version_invalid_utf8_case() -> bool:
    """A --version that is not UTF-8 is a broken instrument, and the contract has no exit 1."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        b = Bench(tmp)
        bad = tmp / "mojibake"
        bad.write_bytes(b'#!/usr/bin/env bash\nprintf \'\\xff\\xfe garbled\\n\'\nexit 0\n')
        bad.chmod(0o755)
        got = run_tool(INVOKE, "gate", "--root", str(b.kit), "--harness", str(bad))
        faults = ("exit 1 is a verdict-shaped code and this module has none",) \
            if got.returncode == 1 else ()
        return judge("version-invalid-utf8-2", got, want=2, marker="harness-version-unread",
                     faults=faults)


def prompt_byte_identical_case() -> bool:
    """Criterion 1: the composed prompt is the pinned brief, byte for byte, and nothing else."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        b = Bench(tmp)
        emitted = tmp / "prompt.bin"
        got = b.compose("--emit-prompt", str(emitted))
        faults = []
        if not emitted.is_file():
            faults.append("no composed prompt was emitted")
        elif emitted.read_bytes() != BRIEF:
            faults.append("the composed prompt is not byte-identical to the pinned brief")
        return judge("prompt-byte-identical", got, want=0, marker="invoke: argv:",
                     present=("--output-format stream-json",), faults=tuple(faults))


def brief_absent_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        got = b.compose(brief="phase-9-nothing")
        return judge("brief-absent-2", got, want=2, marker="brief-absent")


def brief_symlink_out_case() -> bool:
    """A brief reached through a symlink out of the pinned root is not pinned material."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        b = Bench(tmp)
        elsewhere = tmp / "elsewhere.md"
        elsewhere.write_text("an unpinned brief\n")
        (b.pinned / "briefs" / "escaping").symlink_to(elsewhere)
        got = b.compose(brief="escaping")
        return judge("brief-symlink-out-2", got, want=2, marker="outside the pinned root")


def agents_dir_case() -> bool:
    """Criterion 3's known-bad: .claude/agents/ in the judged tree is a named finding."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        (b.repo / ".claude" / "agents").mkdir(parents=True)
        (b.repo / ".claude" / "agents" / "phase-worker.md").write_text("a competing source\n")
        got = b.compose()
        return judge("agents-dir-known-bad-2", got, want=2, marker="agents-directory",
                     present=(str(b.repo / ".claude" / "agents"),))


def agents_dir_empty_case() -> bool:
    """STORY-0009's empty arm: an EMPTY .claude/agents/ is the same finding as a populated one.

    The one-source rule (the D7 probe read at its correction) is directory ABSENCE asserted from
    the filesystem: content is never read, so an empty directory and a populated one are one
    finding, and name-sharing with a pinned definition is irrelevant. A refusal keyed on
    contents — `any(iterdir())` instead of `exists()` — admits exactly this tree, and nothing
    else in the fixture would catch it: the populated known-bad still fires and every clean
    compose case still passes, which is why this arm needs its own case.
    """
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        (b.repo / ".claude" / "agents").mkdir(parents=True)
        got = b.compose()
        return judge("agents-dir-empty-known-bad-2", got, want=2, marker="agents-directory",
                     present=(str(b.repo / ".claude" / "agents"),))


def settings_local_case() -> bool:
    """F1's known-bad: a COMMITTED settings.local.json is a tree-supplied settings source.

    Committed matters: the file rides the judged tree into the phase's cwd, and porcelain never
    names a tracked file, so the seam sees nothing — presence must be refused from the
    filesystem before the phase, exactly like the agents directory.
    """
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        (b.repo / ".claude").mkdir()
        (b.repo / ".claude" / "settings.local.json").write_text(json.dumps({
            "hooks": {"SessionStart": [{"hooks": [
                {"type": "command", "command": f"echo {DECOY_MARKER}"}]}]}
        }))
        git(b.repo, "add", "-A")
        git(b.repo, "commit", "-qm", "plant a tree-supplied settings source")
        got = b.compose()
        return judge("settings-local-known-bad-2", got, want=2, marker="settings-local")


def settings_pinning_decoy_case() -> bool:
    """Criterion 2: the per-invocation twin of core_test's decoy-user-hook case.

    A decoy user scope exists twice over: a SessionStart hook in the calling HOME's settings,
    and a CLAUDE_CONFIG_DIR exported at the decoy, which would survive a HOME swap alone. The
    composed invocation must exclude both: the materialized project settings are byte-identical
    to the pinned settings (no decoy content), the emitted environment points HOME and
    CLAUDE_CONFIG_DIR into the sequencer-owned home, the decoy path appears nowhere in the
    decided values, and the argv carries no settings flag, because the flag-supplied path is
    unmeasured (ADR-0004/D3). What a stub cannot show is a real transcript free of injected
    content; that residue is recorded in the story's notes, not claimed here.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        b = Bench(tmp)
        decoy_home = tmp / "decoy-home"
        (decoy_home / ".claude").mkdir(parents=True)
        (decoy_home / ".claude" / "settings.json").write_text(json.dumps({
            "hooks": {"SessionStart": [{"hooks": [
                {"type": "command", "command": f"echo {DECOY_MARKER}"}]}]}
        }))
        env = clean_env()
        env["HOME"] = str(decoy_home)
        env["CLAUDE_CONFIG_DIR"] = str(decoy_home / ".claude")
        emitted_env = tmp / "env.txt"
        emitted_prompt = tmp / "prompt.bin"
        got = b.compose("--emit-env", str(emitted_env), "--emit-prompt", str(emitted_prompt),
                        env=env)

        faults = []
        materialized = b.workspace / ".claude" / "settings.json"
        if not materialized.is_file():
            faults.append("no settings were materialized into the workspace")
        else:
            body = materialized.read_bytes()
            if body != SETTINGS:
                faults.append("the materialized settings are not the pinned bytes")
            if DECOY_MARKER.encode() in body:
                faults.append("the decoy hook reached the materialized settings")
        if not emitted_env.is_file():
            faults.append("no composed environment was emitted")
        else:
            lines = emitted_env.read_text().splitlines()
            if f"HOME={b.home}" not in lines:
                faults.append("HOME is not the sequencer-owned home")
            if f"CLAUDE_CONFIG_DIR={b.home / '.claude'}" not in lines:
                faults.append("CLAUDE_CONFIG_DIR is not inside the sequencer-owned home")
            if any(str(decoy_home) in line for line in lines):
                faults.append("the decoy home survives in a decided environment value")
        if emitted_prompt.is_file() and emitted_prompt.read_bytes() != BRIEF:
            faults.append("the composed prompt drifted from the pinned brief")
        return judge("settings-pinning-decoy", got, want=0, marker="settings materialized",
                     absent=(DECOY_MARKER, "--settings"), faults=tuple(faults))


def settings_collision_case() -> bool:
    """A settings file the workspace already carries is the fence the phase can edit."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        (b.workspace / ".claude").mkdir(parents=True)
        (b.workspace / ".claude" / "settings.json").write_text("{}\n")
        got = b.compose()
        return judge("settings-collision-2", got, want=2, marker="settings-collision")


def settings_unpinned_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), settings=None)
        got = b.compose()
        return judge("settings-unpinned-2", got, want=2, marker="settings-unpinned")


def home_not_empty_case() -> bool:
    """An isolated home carrying anything is a user scope by another name."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        (b.home / ".claude").mkdir(parents=True)
        (b.home / ".claude" / "settings.json").write_text(json.dumps(
            {"hooks": {"SessionStart": []}}))
        got = b.compose()
        return judge("home-not-empty-2", got, want=2, marker="home-not-empty")


def worktree_outside_case() -> bool:
    """Criterion 4's first half: the worktree lands at the composed path, outside the parent."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        got = b.phase_worktree()
        path = b.worktree_path()
        faults = []
        if not path.is_dir() or not (path / ".git").exists():
            faults.append("no worktree was materialized at the composed path")
        else:
            if path.resolve().is_relative_to(b.repo.resolve()):
                faults.append("the worktree sits inside the parent repository")
            if str(path) not in git(b.repo, "worktree", "list", "--porcelain"):
                faults.append("the worktree is not registered with the parent")
        return judge("worktree-outside-parent-0", got, want=0, marker="invoke: worktree at",
                     faults=tuple(faults))


def live_porcelain_case() -> bool:
    """Criterion 4's seam half: porcelain empty in BOTH trees while the worktree is live.

    This is the case STORY-0005 could not see: its seam reads the one repository it is pointed
    at, and this story decides that the seam reads both. The fence is armed first (settings
    materialized into the worktree), so a passing read also pins that seam-check closes the
    settings custody before reading porcelain.
    """
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        made = b.phase_worktree()
        armed = b.materialize_into_worktree()
        got = b.seam("seam-check")
        said = got.stdout + got.stderr
        faults = []
        if made.returncode != 0:
            faults.append("the worktree act failed, so the case was not constructed")
        if armed.returncode != 0:
            faults.append("the fence was not armed, so the case was not constructed")
        if said.count("advance: porcelain empty") < 2:
            faults.append("fewer than two porcelain reads were reported")
        if (b.worktree_path() / ".claude" / "settings.json").exists():
            faults.append("the materialized settings survived the seam")
        return judge("worktree-live-porcelain-0", got, want=0, marker="both trees",
                     faults=tuple(faults))


def armed_bench(td: Path) -> tuple[Bench, tuple[str, ...]]:
    """A bench with the worktree made and the fence armed, or the construction fault naming why."""
    b = Bench(td)
    made = b.phase_worktree()
    armed = b.materialize_into_worktree()
    faults = []
    if made.returncode != 0 or not b.worktree_path().is_dir():
        faults.append("the worktree was not materialized, so the case was not constructed")
    elif armed.returncode != 0:
        faults.append("the fence was not armed, so the case was not constructed")
    return b, tuple(faults)


def seam_dirt_worktree_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b, faults = armed_bench(Path(td))
        if not faults:
            (b.worktree_path() / "half-done-work.txt").write_text("dirt in the worktree\n")
        got = b.seam("seam-check")
        return judge("seam-dirt-in-worktree-2", got, want=2, marker="half-done-work.txt",
                     faults=faults)


def seam_dirt_parent_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b, faults = armed_bench(Path(td))
        (b.repo / "uncommitted.txt").write_text("dirt in the parent\n")
        got = b.seam("seam-check")
        return judge("seam-dirt-in-parent-2", got, want=2, marker="uncommitted.txt",
                     faults=faults)


def settings_tampered_case() -> bool:
    """A fence the phase edited is a fence nobody pinned, and the seam refuses over it."""
    with tempfile.TemporaryDirectory() as td:
        b, faults = armed_bench(Path(td))
        target = b.worktree_path() / ".claude" / "settings.json"
        if target.is_file():
            target.write_text("{}\n")
        else:
            faults += ("no fence was materialized to tamper with",)
        got = b.seam("seam-check")
        return judge("settings-tampered-2", got, want=2, marker="settings-tampered",
                     faults=faults)


def settings_missing_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b, faults = armed_bench(Path(td))
        target = b.worktree_path() / ".claude" / "settings.json"
        if target.is_file():
            target.unlink()
        got = b.seam("seam-check")
        return judge("settings-missing-2", got, want=2, marker="settings-missing", faults=faults)


def seam_close_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b, faults = armed_bench(Path(td))
        checked = b.seam("seam-check")
        got = b.seam("seam-close")
        path = b.worktree_path()
        more = list(faults)
        if checked.returncode != 0:
            more.append("the seam check failed, so the case was not constructed")
        if path.exists():
            more.append("the worktree survived seam-close")
        if str(path) in git(b.repo, "worktree", "list", "--porcelain"):
            more.append("the worktree is still registered after seam-close")
        return judge("seam-close-removes-0", got, want=0, marker="removed after the seam",
                     faults=tuple(more))


def seam_close_unchecked_case() -> bool:
    """F3's known-bad: closing over a live fence would destroy the tamper evidence.

    seam-check consumes the fence; a seam-close that finds one still present means the seam was
    never checked here, and removing the worktree would take the evidence with it.
    """
    with tempfile.TemporaryDirectory() as td:
        b, faults = armed_bench(Path(td))
        got = b.seam("seam-close")
        more = list(faults)
        if not b.worktree_path().is_dir():
            more.append("the worktree was destroyed with its evidence")
        elif not (b.worktree_path() / ".claude" / "settings.json").is_file():
            more.append("the fence evidence did not survive the refusal")
        return judge("seam-close-unchecked-2", got, want=2, marker="seam-not-checked",
                     faults=tuple(more))


def fresh_attempt_case() -> bool:
    """Criterion 5: a dead phase re-runs as a fresh invocation at the same pinned path.

    The first stub dies mid-phase, leaving a stream with no result record and a dirty corpse
    at the pinned path. The retry is the same command again: the pinned path is cleared first
    under the shared authority, the worktree is fresh, and the second stub completes. The log
    carries both invocations' argv, so the retry observably carries no resume-shaped flag.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        b = Bench(tmp, behavior=DIES)
        first = b.run_phase()
        corpse = b.worktree_path() / "half-done-work.txt"
        died = judge("phase-death-fresh-attempt (death)", first, want=2, marker="phase-death",
                     faults=() if corpse.is_file() else
                     ("the dead phase left no corpse, so the retry proves nothing",))

        stub_harness(tmp, behavior=COMPLETES)
        second = b.run_phase()
        faults = []
        if corpse.exists():
            faults.append("the corpse survived the retry, so the pinned path was not cleared")
        if not (b.worktree_path() / ".git").exists():
            faults.append("the retry did not materialize a worktree at the same pinned path")
        logged = b.log.read_text() if b.log.is_file() else ""
        if logged.count("argv ") != 2:
            faults.append(f"expected two logged invocations, saw {logged.count('argv ')}")
        if "--resume" in logged or "--continue" in logged:
            faults.append("a resume-shaped flag reached the harness")
        retried = judge("phase-death-fresh-attempt (retry)", second, want=0,
                        marker="phase complete", faults=tuple(faults))
        return died and retried


def compaction_death_case() -> bool:
    """A compaction event reads as mid-phase death even when a result record is present."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), behavior=COMPACTS)
        got = b.run_phase()
        return judge("phase-compaction-death", got, want=2, marker="phase-death",
                     present=("compacted",))


def resume_compacted_case() -> bool:
    """The liveness read itself: core's one admitted reader reports a compacted stream."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        sha = git(repo, "rev-parse", "HEAD")
        git(repo, "update-ref", f"refs/chain/{STORY}/attempt-1/phase-1", sha)
        stream = tmp / "phase.stream"
        stream.write_text(
            json.dumps({"type": "system", "session_id": SESSION}) + "\n"
            + json.dumps({"type": "system", "compact_metadata": {"trigger": "auto"}}) + "\n"
            + json.dumps({"type": "result", "session_id": SESSION}) + "\n")
        got = run_tool(CORE, "resume", "--repo", str(repo), "--story", STORY,
                       "--stream", str(stream))
        return judge("resume-liveness-compacted", got, want=0, marker="liveness compacted")


def stream_records(*records: dict) -> str:
    return "".join(json.dumps(r) + "\n" for r in records)


def audit_case(name: str, streams: dict[str, str], *, want: int, marker: str,
               present: tuple[str, ...] = ()) -> bool:
    with tempfile.TemporaryDirectory() as td:
        directory = Path(td) / "transcripts"
        directory.mkdir()
        for filename, body in streams.items():
            (directory / filename).write_text(body)
        got = run_tool(AUDIT, "--dir", str(directory))
        return judge(name, got, want=want, marker=marker, present=present)


def audit_task_start_case() -> bool:
    """The record planted is the probe's own measured task_started shape at 2.1.224."""
    return audit_case(
        "audit-flags-task-start-1",
        {"phase-2.jsonl": stream_records(
            {"type": "system", "session_id": SESSION},
            {"type": "system", "subtype": "task_started", "task_id": "a9d2a96d253f531b5",
             "tool_use_id": "toolu_01XXXXXXXXXXXXXXXXXXXXXX",
             "description": "Run probe-worker job", "subagent_type": "general-purpose",
             "task_type": "local_agent", "prompt": "do the phase's work for it"},
            {"type": "result", "session_id": SESSION})},
        want=1, marker="spawn-event", present=("task_started", "phase-2.jsonl"))


def audit_notification_case() -> bool:
    """A notification without its start is still spawn evidence; a truncated stream hides nothing."""
    return audit_case(
        "audit-flags-notification-1",
        {"phase-3.jsonl": stream_records(
            {"type": "system", "session_id": SESSION},
            {"type": "system", "subtype": "task_notification", "task_id": "a9d2a96d253f531b5",
             "status": "completed", "summary": "done"})},
        want=1, marker="spawn-event", present=("task_notification",))


def audit_clean_case() -> bool:
    return audit_case(
        "audit-clean-0",
        {"phase-2.jsonl": stream_records(
            {"type": "system", "session_id": SESSION},
            {"type": "assistant", "session_id": SESSION},
            {"type": "result", "session_id": SESSION})},
        want=0, marker="transcript(s) examined", present=("transcript-audit: clean",))


def audit_empty_case() -> bool:
    return audit_case("audit-empty-2", {}, want=2, marker="transcript-audit: VOID")


def main() -> int:
    for tool in (INVOKE, CORE, AUDIT):
        if not tool.is_file():
            print(f"invoke_test: tool not found at {tool}", file=sys.stderr)
            return 2
    results = [
        version_match_case(),
        version_mismatch_case(),
        version_unpinned_case(),
        version_unreadable_case(),
        version_invalid_utf8_case(),

        prompt_byte_identical_case(),
        brief_absent_case(),
        brief_symlink_out_case(),
        agents_dir_case(),
        agents_dir_empty_case(),
        settings_local_case(),

        settings_pinning_decoy_case(),
        settings_collision_case(),
        settings_unpinned_case(),
        home_not_empty_case(),

        worktree_outside_case(),
        live_porcelain_case(),
        seam_dirt_worktree_case(),
        seam_dirt_parent_case(),
        settings_tampered_case(),
        settings_missing_case(),
        seam_close_case(),
        seam_close_unchecked_case(),

        fresh_attempt_case(),
        compaction_death_case(),
        resume_compacted_case(),

        audit_task_start_case(),
        audit_notification_case(),
        audit_clean_case(),
        audit_empty_case(),
    ]
    failed = results.count(False)
    print(f"invoke_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

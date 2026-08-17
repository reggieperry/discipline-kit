#!/usr/bin/env python3
"""The phase invocation builder: pinned prompt, pinned settings, owned worktrees, gated version.

ADR-0004 chose the substrate — each phase is its own bare headless invocation, driven by the
pinned sequencer — and this module is where its decisions become a composed command line. It
builds on what already exists rather than re-deciding it: pinned-material resolution and the
judged-tree refusals are `loader.py`'s, the composed-path clearing authority is `core.py`'s, the
porcelain read is `advance.py`'s, and the one admitted reader of harness-written state stays
`core.admitted_signals`. Nothing here reads a stream field, and nothing here is a story verdict.

ADR-0004/D1, the prompt is the one instruction channel. The probe's correction measured the
invoking prompt overriding a pinned `--agents` definition, so under the bare substrate the
sequencer composes the prompt FROM the pinned brief file, byte for byte, and adds nothing — a
composition that decorated the brief would be a relay, and the relay is the measured override
channel. The composed argv is the probe's own measured invocation shape at 2.1.224 (`-p`,
stream output, verbose, bypass permissions) and nothing else.

ADR-0004/D3, every invocation pins its settings sources. The pinned project settings are
materialized into the workspace the sequencer owns — the worktree it created — byte-identical
to the pinned file, unconditionally per invocation, never keyed on any agent-type field. User
scope is excluded at the environment: HOME and CLAUDE_CONFIG_DIR point into a sequencer-owned
home that is required empty, so no user-scope settings file exists for the harness to resolve.
The flag-supplied settings path is deliberately NOT used: it is unmeasured, and ADR-0004/D3
says that if it is ever relied on, D5's re-probe gains that limb first. The environment lever is
itself version-scoped material — "settings-source pinning taking effect" is a named limb of the
extended probe, which is what the version gate below forces on any harness change. The judged
tree must carry no `.claude/agents/` directory at phase start, asserted from the filesystem in
both the parent and the workspace, because leg 1 measured a headless main agent improvising a
brief from the judged tree when its named source was missing.

ADR-0004/D2, worktree custody. An attest-only phase runs in a worktree the sequencer creates at
the composed path `<pinned_root>/worktrees/<story>/attempt-<n>` — composed, never accepted, so
the clearing authority `core.clear_owned` decides applies unchanged, and `owned`'s working-tree
condition makes a path inside the parent unreachable rather than merely wrong. The seam reads
`git status --porcelain` in BOTH trees (ADR-0003/D6's every-seam rule, both halves: the parent
AND the phase worktree), after closing the settings custody — the materialized fence is checked
byte-identical to the pinned file and removed, so an edited fence is a named finding and a
clean seam grades exactly what a sha records. The worktree is removed after the seam. The
isolated home lives beside the worktree at `attempt-<n>.home`, under the same composed-path
conditions. One residue is disclosed rather than closed: the hardening checklist that will one
day root-own the pinned root must leave `worktrees/` writable by the sequencer, or relocate it;
no machine has run that checklist, so nothing breaks today and the note travels with the code.

ADR-0004/D1 and D4, a dead phase is a fresh invocation. Completion is read from the stream
through `core.admitted_signals` — the one admitted reader — and ONLY liveness decides: a stream
whose liveness is not `complete` is a mid-phase death, including `compacted`, the fail-closed
reading of the one event that may have lost the composed prompt's constraints. The harness's
own exit code is reported for diagnosis and decides nothing. A dead phase re-runs as a fresh
invocation at the same composed path, cleared first; nothing here resumes a session, and the
D5 source court holds that at the source level. Whether the operator also takes a story-level
fresh attempt number is the driver's decision, not this module's; both routes clear before
they create.

ADR-0004/D5, the version gate. The harness version is read through the same injectable command
seam the spawn uses, and compared against the profile's `harness_version` pin before any phase:
a mismatch is a named refusal demanding the extended D7 probe, because every enabling fact
above is scoped to the measured 2.1.224.

WHAT THIS DOES NOT CHECK, stated so it is not mistaken for checked. The pinned settings CONTENT
is operator material: nothing here parses it or verifies it denies the spawn tool, both because
the operator pins it and because the sequencer runtime deliberately parses no JSON outside the
admitted reader. And no fixture can show a real transcript free of injected hook content
without running the real harness; the composition facts here are the mechanical half, and the
live half is a separately gated smoke.

THE EXIT CONTRACT holds two values, like the core's:

    0   done — gate passed, invocation composed, phase complete, or custody closed
    2   could-not-run, naming the refusal, the finding, or the death. Never a story verdict.

Usage:
    python3 harness/chain/invoke.py gate --root <kit> --harness <cmd>
    python3 harness/chain/invoke.py compose --root <kit> --repo <judged> --workspace <dir>
        --brief <name> --home <dir> [--harness <cmd>] [--emit-prompt <p>] [--emit-env <p>]
    python3 harness/chain/invoke.py phase-worktree --root <kit> --repo <judged>
        --story <id> --attempt <n>
    python3 harness/chain/invoke.py run --root <kit> --repo <judged> --story <id>
        --attempt <n> --brief <name> --stream <path> [--harness <cmd>] [--timeout <seconds>]
    python3 harness/chain/invoke.py seam-check --root <kit> --repo <judged> --story <id>
        --attempt <n>
    python3 harness/chain/invoke.py seam-close --root <kit> --repo <judged> --story <id>
        --attempt <n>

`--root` is the repository whose `.claude/chain/profile.toml` declares the pin and the pinned
root: the party that sequences, never the tree being graded. `--harness` is the injectable
command seam; fixtures point it at stubs and never at the real binary. `--stream` is where the
phase's stream output lands, named by the caller and kept outside every tree.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import advance  # noqa: E402  (resolved from this file's own directory, beside it)
import attempt  # noqa: E402
import core  # noqa: E402
import loader  # noqa: E402

DONE = 0
COULD_NOT_RUN = 2

CouldNotRun = loader.CouldNotRun

BRIEFS = "briefs"
SETTINGS_DIR = "settings"
SETTINGS_FILE = "settings.json"
SETTINGS_LOCAL = "settings.local.json"
PROJECT_DIR = ".claude"
AGENTS_DIR = "agents"
WORKTREES = "worktrees"
VERSION_KEY = "harness_version"
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
VERSION_TIMEOUT = 30
HOME_VAR = "HOME"
CONFIG_VAR = "CLAUDE_CONFIG_DIR"
COMPLETE = "complete"


def say(line: str) -> None:
    print(line, flush=True)


@dataclass(frozen=True)
class Invocation:
    """One composed phase invocation: everything the spawn needs, and the record of it."""

    argv: tuple[str, ...]
    env: dict[str, str]
    cwd: Path
    prompt: bytes
    settings: Path
    home: Path


def declared_version(root: Path) -> str:
    """The profile's harness_version pin, or could-not-run: an unpinned harness gates nothing."""
    value = core.profile_table(root).get(VERSION_KEY)
    if value is None:
        raise CouldNotRun(
            f"harness-version-unpinned: {root / core.PROFILE} declares no {VERSION_KEY}, and "
            "ADR-0004/D5 scopes every enabling fact to a measured version, so no phase can run "
            "against a harness nothing vouches for"
        )
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise CouldNotRun(f"harness-version-unpinned: {VERSION_KEY} {value!r} is not a plain "
                          "version number")
    return value


def observed_version(harness: str) -> str:
    """What the harness itself reports, read through the injectable command seam.

    The probe recorded the shape: `claude --version` prints "2.1.224 (Claude Code)", so the
    version is the first dotted-number token. Anything else — a command that cannot run, hangs,
    fails, or prints no number — is could-not-run, never a match.
    """
    try:
        # errors="replace" because a --version that is not UTF-8 must read could-not-run, not
        # crash: an escaped UnicodeDecodeError exits 1, the one code this module must not
        # produce. The read only regex-searches for digits, so replacement characters cost
        # nothing.
        done = subprocess.run([harness, "--version"], capture_output=True, text=True,
                              errors="replace", env=loader.child_env(None),
                              timeout=VERSION_TIMEOUT)
    except subprocess.TimeoutExpired as e:
        raise CouldNotRun(f"harness-version-unread: {harness} --version did not return within "
                          f"{VERSION_TIMEOUT}s") from e
    except OSError as e:
        raise CouldNotRun(f"harness-version-unread: {harness} could not be executed: {e}") from e
    if done.returncode != 0:
        raise CouldNotRun(f"harness-version-unread: {harness} --version exited "
                          f"{done.returncode}: {done.stderr.strip()[:120]}")
    found = VERSION.search(done.stdout)
    if not found:
        raise CouldNotRun(f"harness-version-unread: {harness} --version printed "
                          f"{done.stdout.strip()[:80]!r}, which carries no version number")
    return found.group(0)


def version_gate(root: Path, harness: str) -> str:
    """ADR-0004/D5's gate, before any phase: the observed version must equal the pin."""
    pinned = declared_version(root)
    seen = observed_version(harness)
    if seen != pinned:
        raise CouldNotRun(
            f"harness-version-mismatch: the harness reports {seen} and the profile pins "
            f"{pinned}; every enabling fact of ADR-0004 is scoped to the pinned version, so no "
            f"phase runs until the extended D7 probe re-runs against {seen} and the pin moves"
        )
    say(f"invoke: harness version {seen} matches the pin")
    return seen


def refuse_agents_directory(tree: Path) -> None:
    """ADR-0004/D3's filesystem assertion: no competing definition source in the judged tree.

    Leg 1 of the probe measured a headless main agent, told its named type was missing,
    improvising a substitute brief from the judged tree. The assertion is on presence, not
    content: a directory that exists is a source that can be found. An EMPTY directory is the
    same finding — content is never read, so what it holds today decides nothing and a phase can
    populate it — and name-sharing with any pinned definition is irrelevant for the same reason.
    """
    found = tree / PROJECT_DIR / AGENTS_DIR
    if found.exists():
        raise CouldNotRun(
            f"agents-directory: {found} exists at phase start, and ADR-0004/D3 requires the "
            "judged tree to carry no competing definition source at all"
        )
    say(f"invoke: no {PROJECT_DIR}/{AGENTS_DIR}/ in {tree}")


def refuse_settings_local(tree: Path) -> None:
    """ADR-0004/D3's assertion at a second file: no tree-supplied project settings source.

    `materialize_settings` refuses a workspace-supplied `settings.json`; this is the same
    rationale at the sibling name the harness also reads as project scope. A COMMITTED
    settings.local.json rides the judged tree into the phase's cwd and porcelain never names a
    tracked file, so the seam sees nothing — presence is refused from the filesystem before
    each phase instead. The real harness's precedence for this file is argued from harness
    knowledge, not measured: the settings-source limb of D5's extended probe covers it.
    System-scope managed settings are operator-machine material outside any environment
    repoint — a disclosure rather than a mechanism; the operator checklist owns that surface.
    """
    found = tree / PROJECT_DIR / SETTINGS_LOCAL
    if found.exists():
        raise CouldNotRun(
            f"settings-local: {found} exists at phase start, a project-scope settings source "
            "the tree supplies and the phase can edit; the fence is the pinned settings and "
            "nothing else (ADR-0004/D3)"
        )
    say(f"invoke: no {PROJECT_DIR}/{SETTINGS_LOCAL} in {tree}")


def pinned_material(root: Path) -> Path:
    """The pinned root, through the loader's own refusals: one definition of a usable root."""
    pinned = loader.declared_pinned_root(root)
    loader.refuse_judged_root(pinned)
    return pinned


def pinned_brief(pinned: Path, name: str) -> Path:
    """The brief file for one phase, resolved from pinned material (ADR-0003/D4)."""
    attempt.component("brief name", name)
    path = pinned / BRIEFS / name
    loader.refuse_escaping_material(pinned, path)
    if not path.is_file():
        raise CouldNotRun(f"brief-absent: no pinned brief {name!r} at {path} (ADR-0003/D4), and "
                          "a phase with no pinned brief has no instruction channel to compose")
    return path


def pinned_settings(pinned: Path) -> Path:
    """The pinned project settings every invocation materializes (ADR-0004/D3)."""
    path = pinned / SETTINGS_DIR / SETTINGS_FILE
    loader.refuse_escaping_material(pinned, path)
    if not path.is_file():
        raise CouldNotRun(
            f"settings-unpinned: no pinned project settings at {path}, and ADR-0004/D3 "
            "materializes the fence unconditionally per invocation, so no phase runs without one"
        )
    return path


def materialize_settings(workspace: Path, source: Path) -> Path:
    """Write the pinned settings into the workspace the sequencer owns, byte-identical.

    Bytes are copied and read back, never parsed: the sequencer runtime parses no JSON outside
    the admitted reader, and a reserialization could drift from what the operator pinned. A
    settings file the workspace ALREADY carries is refused: it is material the judged tree
    supplies and the phase can edit, and materializing over it would leave the fence's origin
    undecidable at the seam.
    """
    target = workspace / PROJECT_DIR / SETTINGS_FILE
    if target.exists():
        raise CouldNotRun(
            f"settings-collision: {target} already exists, so the workspace supplies its own "
            "settings file, which is the fence the phased agent's tree can edit (ADR-0004/D3)"
        )
    body = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    if target.read_bytes() != body:
        raise CouldNotRun(f"the settings at {target} do not read back as the pinned bytes, so "
                          "the fence was not materialized")
    say(f"invoke: settings materialized at {target}, {len(body)} byte(s), byte-identical "
        f"to {source}")
    return target


def owned_home(home: Path) -> Path:
    """The isolated home the invocation's environment points user scope at.

    It must be empty, because an isolated home carrying anything is a user scope by another
    name: a settings file planted here would be resolved exactly as the operator's own would
    have been. An empty `.claude` left by a previous invocation is tolerated — this module
    creates it — and anything else is a named refusal.
    """
    if home.is_symlink():
        raise CouldNotRun(f"home-symlink: {home} is a symlink, and what a link names is not "
                          "the sequencer's to use as an isolated home")
    config = home / PROJECT_DIR
    if home.exists():
        stray = sorted(p.name for p in home.iterdir() if p.name != PROJECT_DIR)
        inside = sorted(p.name for p in config.iterdir()) if config.is_dir() else []
        if config.exists() and not config.is_dir():
            stray.append(PROJECT_DIR)
        if stray or inside:
            held = ", ".join(stray + inside)
            raise CouldNotRun(f"home-not-empty: {home} carries {held}, and an isolated home "
                              "carrying anything is a user scope by another name (ADR-0004/D3)")
    config.mkdir(parents=True, exist_ok=True)
    return home


def invocation_env(home: Path) -> dict[str, str]:
    """The phase environment: the caller's, with git scrubbed and user scope excluded.

    `loader.child_env` is the shared scrub — one definition of what a child inherits. On top of
    it, HOME and CLAUDE_CONFIG_DIR both point into the owned home: HOME because user-scope
    settings resolve under it, and the config-dir override as well because an operator
    environment that already exports it would otherwise survive the HOME swap and re-point the
    harness at the real user scope. API-key auth rides the surviving environment, which is the
    precedence the probe's stderr recorded.

    This is an inherited-and-patched environment, not a fresh one: whatever else the operator's
    environment carries — ANTHROPIC_* keys, NODE_OPTIONS, CLAUDE_CODE_* toggles, PATH —
    survives into the phase. That is operator-hygiene surface, not a judged-party channel: the
    judged tree cannot write the sequencer's environment, and pinning the operator's own is
    the machine checklist's ground.
    """
    env = loader.child_env(None)
    env[HOME_VAR] = str(home)
    env[CONFIG_VAR] = str(home / PROJECT_DIR)
    return env


def composed_argv(harness: str, prompt: str) -> tuple[str, ...]:
    """The probe's measured invocation shape at 2.1.224, and nothing else.

    No settings flag: the flag-supplied settings path is unmeasured, ADR-0004/D3 forbids
    relying on it without D5's re-probe gaining that limb first, and the measured mechanism is
    the materialized project-scope file. No agents payload: the phase IS the session's main
    agent under ADR-0004/D1, and the spawn denial lives in the pinned settings, not here.
    """
    return (harness, "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions")


def materialized(pinned: Path, workspace: Path, brief_name: str, home: Path,
                 harness: str) -> Invocation:
    """The composition tail both entries share: brief, settings, environment, argv.

    `home` arrives already owned; the callers decide where it lives. The prompt is the brief's
    bytes and nothing else, so the argv line reported here shows a placeholder naming its size
    rather than spilling the brief into every transcript.
    """
    brief = pinned_brief(pinned, brief_name)
    prompt = brief.read_bytes()
    try:
        text = prompt.decode()
    except UnicodeDecodeError as e:
        raise CouldNotRun(f"brief-undecodable: {brief} is not UTF-8 ({e}), so it cannot ride "
                          "the command line") from e
    settings = materialize_settings(workspace, pinned_settings(pinned))
    argv = composed_argv(harness, text)
    say(f"invoke: brief {brief_name!r} at {brief}, {len(prompt)} byte(s), the whole prompt "
        "and nothing else")
    shown = list(argv)
    shown[2] = f"<the pinned brief, {len(prompt)} byte(s)>"
    say(f"invoke: argv: {' '.join(shown)}")
    say(f"invoke: cwd {workspace}")
    say(f"invoke: home {home} ({HOME_VAR} and {CONFIG_VAR} point into it; user scope excluded)")
    return Invocation(argv=argv, env=invocation_env(home), cwd=workspace, prompt=prompt,
                      settings=settings, home=home)


def build(root: Path, repo: Path, workspace: Path, brief_name: str, home: Path,
          harness: str) -> Invocation:
    """The whole pre-phase, in the order each step makes the next one meaningful.

        the version gate            ADR-0004/D5, before any phase
        no agents directory         ADR-0004/D3, judged tree and workspace both
        the brief resolved          pinned material, ADR-0003/D4
        the settings materialized   the fence, into the workspace the sequencer owns
        the home isolated           user scope excluded at the environment
        the argv composed           the prompt is the brief, byte for byte
    """
    version_gate(root, harness)
    repo = attempt.working_tree(repo)
    refuse_agents_directory(repo)
    refuse_settings_local(repo)
    if not workspace.is_dir():
        raise CouldNotRun(f"the workspace {workspace} is not a directory, so there is nowhere "
                          "to materialize the fence")
    if workspace.resolve() != repo.resolve():
        refuse_agents_directory(workspace)
        refuse_settings_local(workspace)
    pinned = pinned_material(root)
    return materialized(pinned, workspace, brief_name, owned_home(home), harness)


def emit_prompt(path: Path, inv: Invocation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(inv.prompt)
    say(f"invoke: composed prompt emitted to {path}")


def emit_env(path: Path, inv: Invocation) -> None:
    """The decided environment facts, for a fixture or an operator to hold against the decoy.

    Only what this module decided is emitted — the two re-pointed variables and the names of
    what the scrub dropped — never the whole environment, which carries the operator's secrets.
    """
    decided = [f"{HOME_VAR}={inv.env[HOME_VAR]}", f"{CONFIG_VAR}={inv.env[CONFIG_VAR]}"]
    dropped = sorted(k for k in os.environ if k not in inv.env)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(decided + [f"dropped {k}" for k in dropped]) + "\n")
    say(f"invoke: composed environment facts emitted to {path}")


def worktree_root(pinned: Path) -> Path:
    """Where phase worktrees live: composed from the pinned root, outside every working tree.

    The pinned root arrives resolved and refused-if-judged, so this path inherits both facts.
    """
    return pinned / WORKTREES


def attempt_home(root: Path, story: str, number: int) -> Path:
    """The isolated home beside one attempt's worktree, composed rather than accepted."""
    return root / story / f"attempt-{number}.home"


def cleared_home(root: Path, story: str, number: int) -> Path:
    """The composed home path, cleared under the same authority `core.clear_owned` decides.

    The conditions are core's, read at a second composed path: this path was composed here and
    never accepted from a caller, a symlink is not the sequencer's to clear through, and a path
    inside a working tree could hold graded material. `core.owned` itself is worktree-shaped,
    which is why the conditions are re-stated rather than the function called.
    """
    path = attempt_home(root, story, number)
    if path.is_symlink():
        raise CouldNotRun(f"{path} is a symlink, and what a link names is not the sequencer's "
                          "to clear")
    holder = loader.working_tree_above(path.parent)
    if holder is not None:
        raise CouldNotRun(f"{path} sits inside the git working tree at {holder}, so clearing "
                          "it could remove graded or examiner material (ADR-0004/D2)")
    if path.exists():
        say(f"invoke: clearing the previous attempt's home at {path}, which held "
            f"{core.inventory(path)}")
        shutil.rmtree(path)
    return path


def fresh_worktree(repo: Path, root: Path, story: str, number: int) -> Path:
    """ADR-0004/D2: the composed path cleared under the shared authority, then a fresh worktree.

    `core.clear_owned` is the clearing decision and is called, not reimplemented: it removes a
    registered worktree, prunes a stale registration, and force-clears an unregistered leftover
    at the path it composes itself — which is what makes a retry after a mid-phase death succeed
    at the same pinned path. The worktree is detached at the judged tree's HEAD: an attest-only
    phase grades, it does not branch.
    """
    path = core.clear_owned(repo, root, story, number)
    path.parent.mkdir(parents=True, exist_ok=True)
    done = attempt.git(repo, "worktree", "add", "--detach", "-q", str(path))
    if done.returncode != 0:
        raise CouldNotRun(f"worktree-uncreated: git worktree add at {path} exited "
                          f"{done.returncode}: {done.stderr.strip()}")
    say(f"invoke: worktree at {path}, outside {repo}, detached at its HEAD")
    return path


def worktree_for(root: Path, repo: Path, story: str, number: int) -> tuple[Path, Path]:
    """The composed worktree path and its root, for the acts that address an existing one."""
    pinned = pinned_material(root)
    wroot = worktree_root(pinned)
    return core.attempt_worktree(wroot, story, number), wroot


def seam_check(root: Path, repo: Path, story: str, number: int) -> None:
    """The seam's custody read: settings closed first, then porcelain in BOTH trees.

    The order is the design: the materialized fence is an untracked file this module put in the
    worktree, so it is verified byte-identical to the pinned settings and removed BEFORE the
    porcelain read — an edited fence is a named finding, never silently swept — and only then
    does ADR-0003/D6's precondition run, in the parent AND the phase worktree, because
    STORY-0005's seam reads the one repository it is pointed at and cannot know a worktree
    exists that it was not told about. Which trees the seam reads is decided here.

    A consequence worth naming: a refusal AFTER the fence is consumed (parent or worktree
    dirt) leaves the fence gone, so re-running seam-check reads settings-missing. The recovery
    route is to re-arm the fence with `compose` against the same worktree once the dirt is
    resolved, or to take a fresh attempt, which clears and re-materializes everything.
    """
    path, _ = worktree_for(root, repo, story, number)
    if not path.is_dir():
        raise CouldNotRun(f"seam-unworktreed: no phase worktree at {path}, so there is no seam "
                          "to close")
    pinned_body = pinned_settings(pinned_material(root)).read_bytes()
    target = path / PROJECT_DIR / SETTINGS_FILE
    if not target.is_file():
        raise CouldNotRun(
            f"settings-missing: {target} is absent at the seam, so the fence this invocation "
            "materialized did not survive the phase, and what the phase ran under is not what "
            "was pinned (ADR-0004/D3)"
        )
    if target.read_bytes() != pinned_body:
        raise CouldNotRun(
            f"settings-tampered: {target} no longer matches the pinned settings, so the phase "
            "ran under a fence nobody pinned (ADR-0004/D3)"
        )
    target.unlink()
    with contextlib.suppress(OSError):
        (path / PROJECT_DIR).rmdir()
    say(f"invoke: settings custody closed at {target}")
    advance.porcelain_empty(attempt.working_tree(repo))
    advance.porcelain_empty(attempt.working_tree(path))
    say("invoke: porcelain empty in both trees at the seam (ADR-0003/D6, both halves)")


def seam_close(root: Path, repo: Path, story: str, number: int) -> Path:
    """ADR-0004/D2's last act: the worktree is removed after the seam, by the shared authority.

    The driver's ordering obligation is bound here rather than trusted: seam-check consumes the
    fence, so a close that finds the materialized fence still present means the seam was never
    checked at this worktree — and removing it would destroy the very tamper evidence
    seam-check exists to name. That reads seam-not-checked, and the worktree stays.
    """
    path, wroot = worktree_for(root, repo, story, number)
    fence = path / PROJECT_DIR / SETTINGS_FILE
    if fence.exists():
        raise CouldNotRun(
            f"seam-not-checked: {fence} still exists, so the seam was never checked at this "
            "worktree; seam-check consumes the fence and names a tampered one, and closing "
            "over it would destroy that evidence (ADR-0004/D2, D3)"
        )
    path = core.clear_owned(repo, wroot, story, number)
    say(f"invoke: worktree at {path} removed after the seam (ADR-0004/D2)")
    return path


def spawn(inv: Invocation, stream: Path, timeout: int | None) -> int:
    """The phase spawn: stdout to the caller's stream path, stderr beside it.

    The stream lands where the caller named, outside every tree; this module never names its
    format and never parses it — the liveness read is `core.admitted_signals`, the one admitted
    reader.
    """
    stream.parent.mkdir(parents=True, exist_ok=True)
    say(f"invoke: phase spawn, stream to {stream}")
    with open(stream, "wb") as out, open(str(stream) + ".stderr", "wb") as err:
        try:
            done = subprocess.run(list(inv.argv), cwd=str(inv.cwd), env=inv.env,
                                  stdout=out, stderr=err, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise CouldNotRun(
                f"phase-death: the phase did not return within {timeout}s and was killed; a "
                "dead phase re-runs as a fresh invocation at the cleared pinned path, and is "
                "never resumed (ADR-0004/D4)"
            ) from e
        except OSError as e:
            raise CouldNotRun(f"the harness {inv.argv[0]} could not be executed: {e}") from e
    return done.returncode


def run_phase(root: Path, repo: Path, story: str, number: int, brief_name: str,
              stream: Path, harness: str, timeout: int | None) -> None:
    """One attest-only phase, end to end: build, spawn, and the liveness read.

    Only liveness decides completion. The harness exit code is reported for diagnosis and
    decides nothing, because ADR-0001/D5 admits ids and liveness from harness-written state and
    the positive completion signal is the result record's presence — a nonzero exit after a
    complete stream is a fact for an operator, and a zero exit over an incomplete stream is
    still a death.
    """
    version_gate(root, harness)
    repo = attempt.working_tree(repo)
    refuse_agents_directory(repo)
    refuse_settings_local(repo)
    pinned = pinned_material(root)
    wroot = worktree_root(pinned)
    workspace = fresh_worktree(repo, wroot, story, number)
    refuse_agents_directory(workspace)
    refuse_settings_local(workspace)
    home = owned_home(cleared_home(wroot, story, number))
    inv = materialized(pinned, workspace, brief_name, home, harness)

    code = spawn(inv, stream, timeout)
    signals = core.admitted_signals(stream)
    say(f"invoke: harness exited {code} (reported, not decided from); liveness "
        f"{signals.liveness}, {signals.records} record(s)")
    if signals.liveness != COMPLETE:
        raise CouldNotRun(
            f"phase-death: the stream at {stream} reads {signals.liveness}, not {COMPLETE}, so "
            "the phase died mid-run — a compaction event reads as death, the fail-closed "
            "reading of ADR-0004/D1 — and it re-runs as a fresh invocation at the cleared "
            "pinned path, never resumed (ADR-0004/D4)"
        )
    say(f"invoke: phase complete at {workspace}; the verdict is the advance script's, not "
        "this module's")


def act_gate(a: argparse.Namespace) -> int:
    version_gate(Path(a.root).resolve(), a.harness)
    return DONE


def act_compose(a: argparse.Namespace) -> int:
    inv = build(Path(a.root).resolve(), Path(a.repo).resolve(),
                Path(a.workspace).resolve(), a.brief, Path(a.home).resolve(), a.harness)
    if a.emit_prompt:
        emit_prompt(Path(a.emit_prompt), inv)
    if a.emit_env:
        emit_env(Path(a.emit_env), inv)
    return DONE


def act_phase_worktree(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve()
    repo = attempt.working_tree(Path(a.repo).resolve())
    story = attempt.component("story id", a.story)
    number = int(attempt.positive("attempt", a.attempt))
    pinned = pinned_material(root)
    fresh_worktree(repo, worktree_root(pinned), story, number)
    return DONE


def act_run(a: argparse.Namespace) -> int:
    run_phase(Path(a.root).resolve(), Path(a.repo).resolve(),
              attempt.component("story id", a.story),
              int(attempt.positive("attempt", a.attempt)),
              a.brief, Path(a.stream), a.harness, a.timeout or None)
    return DONE


def act_seam_check(a: argparse.Namespace) -> int:
    seam_check(Path(a.root).resolve(), Path(a.repo).resolve(),
               attempt.component("story id", a.story),
               int(attempt.positive("attempt", a.attempt)))
    return DONE


def act_seam_close(a: argparse.Namespace) -> int:
    seam_close(Path(a.root).resolve(), Path(a.repo).resolve(),
               attempt.component("story id", a.story),
               int(attempt.positive("attempt", a.attempt)))
    return DONE


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="act", required=True)

    gate = sub.add_parser("gate", help="compare the harness version against the profile's pin")
    gate.add_argument("--root", required=True, help="the repository declaring the pin")
    gate.add_argument("--harness", default="claude", help="the harness command seam")
    gate.set_defaults(run=act_gate)

    compose = sub.add_parser("compose", help="compose one invocation without running it")
    compose.add_argument("--root", required=True)
    compose.add_argument("--repo", required=True, help="the judged tree")
    compose.add_argument("--workspace", required=True, help="the workspace the sequencer owns")
    compose.add_argument("--brief", required=True, help="the pinned brief's name")
    compose.add_argument("--home", required=True, help="the isolated home, empty or absent")
    compose.add_argument("--harness", default="claude")
    compose.add_argument("--emit-prompt", help="write the composed prompt bytes here")
    compose.add_argument("--emit-env", help="write the decided environment facts here")
    compose.set_defaults(run=act_compose)

    tree = sub.add_parser("phase-worktree", help="clear the composed path and create a worktree")
    run = sub.add_parser("run", help="one attest-only phase: build, spawn, liveness")
    check = sub.add_parser("seam-check", help="settings custody, then porcelain in both trees")
    close = sub.add_parser("seam-close", help="remove the phase worktree after the seam")
    for one in (tree, run, check, close):
        one.add_argument("--root", required=True)
        one.add_argument("--repo", required=True)
        one.add_argument("--story", required=True)
        one.add_argument("--attempt", required=True)
    run.add_argument("--brief", required=True)
    run.add_argument("--stream", required=True, help="where the phase's stream output lands")
    run.add_argument("--harness", default="claude")
    run.add_argument("--timeout", type=int, default=0, help="seconds before the phase reads dead")
    tree.set_defaults(run=act_phase_worktree)
    run.set_defaults(run=act_run)
    check.set_defaults(run=act_seam_check)
    close.set_defaults(run=act_seam_close)

    a = ap.parse_args()
    try:
        return a.run(a)
    except CouldNotRun as e:
        print(f"invoke: VOID: {e}; not a phase and not a verdict", file=sys.stderr)
        return COULD_NOT_RUN
    except OSError as e:
        print(f"invoke: VOID: a filesystem read failed: {e}", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    raise SystemExit(main())

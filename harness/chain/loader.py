#!/usr/bin/env python3
"""The postcondition loader: examiner material resolved from a pinned root, demonstrated before use.

Two decisions of `docs/adrs/ADR-0001-advancement-re-derived.md` become mechanism here.

D3, the examiner never comes from the judged tree: a postcondition script, the checks it calls,
the configuration it reads and the fixtures that demonstrate it are resolved from a pinned copy
outside every working tree. Both reachable violations were measured before the record was written
(design §4.8: a check script that changes directory into its own tree; a verdict surface read from
a gitignored `.envrc`), so resolution is refused outright from any path inside a git working tree
rather than trusted to a path convention.

D4, no postcondition's verdict counts before it has demonstrated red and green: every
postcondition ships a known-bad fixture it fails and a known-good fixture it passes, and the
demonstration runs on load. A predicate that always fails and a working fence are
indistinguishable from outside, which is what the archived `postcondition.py` was for a month.

THE PINNED LAYOUT, rooted at the profile's `pinned_root`:

    <pinned_root>/
      postconditions/
        <name>/
          run                 the postcondition, executable
          config/             optional; the configuration it reads, pinned with it
          fixtures/
            red/              a tree `run` must FAIL against, exit 1
            green/            a tree `run` must PASS against, exit 0

`run` is invoked as `run <tree>`, with the tree to judge as its one argument and an absolute
path. Its working directory is its own pinned directory and never the judged tree, so relative
resolution inside a postcondition reaches pinned material rather than the material it is judging;
`CHAIN_POSTCONDITION_CONFIG` names the pinned `config/` when one exists, for the same reason. The
child's environment has every `GIT_*` variable dropped: a hook or a phase seam exports `GIT_DIR`
and `GIT_INDEX_FILE`, and a subprocess that inherits them operates on the caller's repository
rather than on the tree it was pointed at. That defect has landed four times in this repository.

`run` honours the canonical contract of ADR-0003/D2 at its own boundary: 0 pass, 1 fail, and any
other code a broken instrument. So a red limb exiting 1 and a green limb exiting 0 are the
demonstration; a red limb exiting 0 or a green limb exiting 1 is a demonstration FAILURE, which is
a fact about the postcondition; and anything else is could-not-run, which is not.

A PREDICATE WHOSE NATIVE CONTRACT DIFFERS is adapted through the optional `adapt` argument: a map
from the code the postcondition returns to the canonical one, supplied by `harness/chain/advance.py`
out of pinned material, since ADR-0003/D2 puts that adaptation inside the advance script and
forbids the sequencer from interpreting a native code anywhere else. It applies to the
demonstration for the reason the demonstration exists: red-proof's own known-bad tree makes it
exit 2, so a demonstration read in native codes would call that predicate broken, and one read in
codes the seam will never use is not evidence about the seam. The default is identity, which is
every postcondition written to the canonical contract.

THE LOADER'S OWN EXIT CONTRACT is the same three values read for the loader's act:

    0   loadable, and the demonstration ran
    1   the demonstration failed, naming which limb and how
    2   could-not-run, naming what was missing or what code was observed

Could-not-run dominates a failed demonstration when both are met in one load, because a limb that
could not run leaves the demonstration incomplete and an incomplete demonstration is not evidence
either way. Nothing about that ordering admits a postcondition: only exit 0 does.

WHAT THIS DOES NOT CHECK, stated so it is not mistaken for checked: ownership and mode of the
pinned root. Design §4.3 puts predicate scripts at absolute paths outside any working tree,
root-owned 0755, and that hardening is an operator checklist item that has not landed on any
machine here. A root-ownership assertion in this loader would fail every machine today and would
be edited out; the property it would carry is that a phase agent cannot write the examiner, and
until the checklist runs, that property rests on the path being outside the agent's tree and on
nothing else. The absence is the honest state. Two shapes live inside that same gap, confirmed
by the merge review: a HARD LINK whose inode is judged-tree material is invisible to resolve()
and to any walk (no design catches it; it needs same-filesystem write access to the pinned
root, which the ownership property is what would deny), and the fixture copy follows symlinks
inside a fixture tree, so a link planted there would be copied through (the fixture is the
postcondition's subject; robustness for the seam build to weigh, not a pinning hole).

Usage:
    python3 harness/chain/loader.py <postcondition-name> [--root <repo>] [--timeout <seconds>]

`--root` is the repository whose `.claude/chain/profile.toml` declares the pinned root; it
defaults to the repository holding this file. It is what lets `harness/fixtures/loader_test.py`
point the loader at throwaway trees, which is the only way to observe it refusing.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

LOADABLE = 0
DEMONSTRATION_FAILED = 1
COULD_NOT_RUN = 2

PROFILE = ".claude/chain/profile.toml"
PINNED_KEY = "pinned_root"
POSTCONDITIONS = "postconditions"
RUN = "run"
CONFIG = "config"
FIXTURES = "fixtures"
CONFIG_ENV = "CHAIN_POSTCONDITION_CONFIG"
DEFAULT_TIMEOUT = 120

# The verdict each fixture limb must produce, under `run`'s own 0/1/2 contract.
REQUIRED = {"red": 1, "green": 0}


class CouldNotRun(Exception):
    """Nothing was demonstrated, and the reason is named. Never a pass (ADR-0001/D2)."""


class DemonstrationFailed(Exception):
    """A limb ran and produced the wrong verdict, which is a fact about the postcondition."""


@dataclass(frozen=True)
class Postcondition:
    """A demonstrated postcondition: the only thing this module hands back as loadable."""

    name: str
    home: Path
    run: Path
    config: Path | None
    codes: dict[str, int]


def working_tree_above(path: Path) -> Path | None:
    """The nearest directory at or above `path` that carries a `.git` entry, if any.

    `.git` is a directory in an ordinary checkout and a file in a linked worktree, so presence
    rather than kind is the test. This is a filesystem walk and spawns no git: a loader that
    asked git would be asking a tool the caller's environment can redirect, and the redirection
    is exactly what the pinning rule is defending against.
    """
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def nested_declaration(data: dict) -> bool:
    """Whether `pinned_root` appears in any table below the top level.

    Reading it there would be a guess about which declaration governs; refusing it is the
    fail-closed answer, and naming it is what keeps the remedy findable.
    """

    def below(node: object) -> bool:
        if isinstance(node, dict):
            return PINNED_KEY in node or any(below(v) for v in node.values())
        if isinstance(node, list):
            return any(below(v) for v in node)
        return False

    return any(below(v) for v in data.values())


def declared_pinned_root(root: Path) -> Path:
    """The `pinned_root` the repository's chain profile declares, or could-not-run saying why."""
    profile = root / PROFILE
    if not profile.is_file():
        raise CouldNotRun(f"no chain profile at {root / PROFILE}, so no pinned root is declared")
    try:
        with open(profile, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise CouldNotRun(f"cannot parse {profile}: {e}") from e

    value = data.get(PINNED_KEY)
    if value is None:
        where = "" if not nested_declaration(data) else (
            " (one is declared in a nested table, and the schema puts every key at top level)"
        )
        raise CouldNotRun(f"{profile} declares no top-level {PINNED_KEY}{where}")
    if not isinstance(value, str):
        raise CouldNotRun(f"{PINNED_KEY} is {type(value).__name__}, not a path")
    candidate = Path(value)
    if not candidate.is_absolute():
        raise CouldNotRun(f"{PINNED_KEY} {value!r} is not absolute, so it names a path relative "
                          "to whatever tree the caller happens to be standing in")
    if ".." in candidate.parts:
        raise CouldNotRun(f"{PINNED_KEY} {value!r} walks out through a parent, so what it names "
                          "depends on a link it does not control")
    if not candidate.is_dir():
        raise CouldNotRun(f"{PINNED_KEY} {value} does not exist, or is not a directory")
    # Resolved here and nowhere else, so every later decision is about the directory the root
    # reaches rather than about the string that names it.
    return candidate.resolve()


def refuse_judged_root(pinned: Path) -> None:
    """ADR-0001/D3, mechanically: a root inside a working tree does not pin anything.

    `pinned` arrives resolved, and that is the whole of the fix for the escape measured here: a
    lexical walk reads the names in the declared string rather than the directories they reach,
    so a root symlinked into a subdirectory of a judged repository never brings that repository
    into the walk. A symlink naming the repository's own root happened to be caught, because the
    first probe resolves through the link and meets `.git` immediately, and one shape being
    caught by accident is what let the other shape read loadable.
    """
    tree = working_tree_above(pinned)
    if tree is not None:
        raise CouldNotRun(
            f"the pinned root {pinned} is inside the git working tree at {tree}, so it is "
            "material the judged party can write (ADR-0001/D3)"
        )


def refuse_escaping_material(pinned: Path, *paths: Path | None) -> None:
    """Every resolved material path must sit under the resolved pinned root.

    The escape this closes is a clean root whose `postconditions/` (or anything under it) is a
    symlink into a judged repository: nothing about the root is wrong, so a root-only check
    reports nothing while every path below it reaches the judged tree.

    CONTAINMENT RATHER THAN A WALK FROM EACH PATH, and the difference is a case rather than a
    preference. A fixture tree is the SUBJECT of a postcondition, not part of the examiner's
    apparatus, and a postcondition over a tree's porcelain needs a fixture tree that is itself a
    git repository—so a rule refusing any material with a working tree at or under it refuses
    exactly the shape D4 most needs. `fixture-is-a-repo` in the fixture pins that; the two
    symlink cases pin that containment still closes the escape.
    """
    for path in paths:
        if path is None:
            continue
        real = path.resolve()
        if real != pinned and pinned not in real.parents:
            raise CouldNotRun(
                f"{path} resolves to {real}, outside the pinned root {pinned}, so what would run "
                "is not the material the root pins (ADR-0001/D3)"
            )


def resolve(pinned: Path, name: str) -> tuple[Path, Path, Path | None, dict[str, Path]]:
    """The postcondition's pinned material, or could-not-run naming the first thing absent."""
    home = pinned / POSTCONDITIONS / name
    if not home.is_dir():
        raise CouldNotRun(f"no postcondition {name!r} under {pinned / POSTCONDITIONS}")
    run = home / RUN
    if not run.is_file():
        raise CouldNotRun(f"postcondition {name!r} has no {RUN} at {run}")
    if not os.access(run, os.X_OK):
        raise CouldNotRun(f"postcondition {name!r} has a {RUN} that is not executable ({run})")
    fixtures: dict[str, Path] = {}
    for limb in REQUIRED:
        tree_path = home / FIXTURES / limb
        if not tree_path.is_dir():
            raise CouldNotRun(
                f"postcondition {name!r} has no {limb} fixture at {tree_path}, so its verdict "
                "cannot count (ADR-0001/D4)"
            )
        fixtures[limb] = tree_path
    config = home / CONFIG
    return home, run, (config if config.is_dir() else None), fixtures


def child_env(config: Path | None) -> dict[str, str]:
    """The environment a postcondition runs in: the caller's, with git's own variables dropped."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop(CONFIG_ENV, None)
    if config is not None:
        env[CONFIG_ENV] = str(config)
    return env


def demonstrate(run: Path, home: Path, tree: Path, config: Path | None,
                timeout: int) -> tuple[int, str]:
    """Run the postcondition against a COPY of one fixture tree; return its code and its output.

    A copy because the fixtures are examiner material and the postcondition is the thing being
    examined. Demonstrating in place lets any postcondition write into the evidence that every
    later demonstration is judged by, which is the judged party editing the examiner one level
    down from where D3 blocked it. Symlinks inside a fixture are copied as symlinks rather than
    followed, so copying cannot pull in whatever they point at.
    """
    with tempfile.TemporaryDirectory() as scratch:
        judged = Path(scratch) / tree.name
        shutil.copytree(tree, judged, symlinks=True)
        try:
            done = subprocess.run(
                [str(run), str(judged)],
                cwd=str(home),
                env=child_env(config),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise CouldNotRun(f"{run} did not return within {timeout}s against {tree}") from e
        except OSError as e:
            raise CouldNotRun(f"{run} could not be executed against {tree}: {e}") from e
        return done.returncode, done.stdout + done.stderr


def native(code: int) -> int | None:
    """The identity adaptation: a postcondition written to the canonical contract of ADR-0003/D2."""
    return code


def load(root: Path, name: str, *, timeout: int = DEFAULT_TIMEOUT,
         say: Callable[[str], None] = print,
         adapt: Callable[[int], int | None] = native) -> Postcondition:
    """Resolve `name` from the pinned root and demonstrate it, or raise saying why not.

    Every `OSError` on the resolution path becomes could-not-run. A filesystem the loader cannot
    read is a broken instrument, and ADR-0003/D2 forbids reading one as a verdict; measured
    before this net existed, a `PermissionError` from an unreadable ancestor escaped as a
    traceback, and an uncaught exception exits 1, which is the code for a failed demonstration.
    The net is here rather than around the path walk because that is not where it fired: the
    probe that raised was the `is_dir()` on the declared root, one step earlier, and a guard
    placed at the reported site would have left the measured shape open.
    """
    try:
        return demonstrated(root, name, timeout=timeout, say=say, adapt=adapt)
    except OSError as e:
        raise CouldNotRun(f"a filesystem read failed while loading {name!r}: {e}") from e


def demonstrated(root: Path, name: str, *, timeout: int,
                 say: Callable[[str], None],
                 adapt: Callable[[int], int | None] = native) -> Postcondition:
    """The resolution and demonstration themselves, guarded by `load`.

    The denominators go to `say` as they are established, so a refusal reports what it did reach
    rather than only what stopped it.
    """
    pinned = declared_pinned_root(root)
    refuse_judged_root(pinned)
    say(f"postcondition-loader: pinned root {pinned}, declared by {root / PROFILE}")
    home, run, config, fixtures = resolve(pinned, name)
    refuse_escaping_material(pinned, home, run, config, *fixtures.values())
    say(f"postcondition-loader: resolved {name!r} at {home} "
        f"({RUN} present, {CONFIG}/ {'present' if config else 'absent'}, "
        f"{len(fixtures)} fixture tree(s) demonstrated against copies: "
        f"{', '.join(sorted(fixtures))})")

    codes: dict[str, int] = {}
    broken: list[str] = []
    wrong: list[str] = []
    for limb in sorted(REQUIRED):
        code, transcript = demonstrate(run, home, fixtures[limb], config, timeout)
        codes[limb] = code
        want = REQUIRED[limb]
        read = adapt(code)
        as_read = "" if read == code else f", read as {read}"
        say(f"postcondition-loader: demonstration {limb}: exit {code}{as_read} (required {want})")
        # In full rather than summarized. The transcript is how an operator sees WHICH examiner
        # spoke and why it decided as it did, and a truncated one is a filtered failure signal.
        for line in transcript.splitlines():
            say(f"postcondition-loader: {limb}| {line}")
        if read is None:
            broken.append(f"{limb} exited {code}, which the declared contract does not map")
        elif read not in (0, 1):
            broken.append(f"{limb} exited {code}{as_read}, outside the 0/1 contract")
        elif read != want:
            wrong.append(f"the {limb} fixture returned {code}{as_read} where {want} was required")

    if broken:
        raise CouldNotRun(
            f"postcondition {name!r} did not complete its demonstration: {'; '.join(broken)}"
        )
    if wrong:
        raise DemonstrationFailed(
            f"postcondition {name!r} did not demonstrate red and green: {'; '.join(wrong)}"
        )
    return Postcondition(name=name, home=home, run=run, config=config, codes=codes)


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve and demonstrate one pinned postcondition.")
    ap.add_argument("name", help="the postcondition to load")
    ap.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[2]),
        help="the repository whose chain profile declares the pinned root",
    )
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="seconds one demonstration limb may take before it reads could-not-run")
    a = ap.parse_args()

    try:
        found = load(Path(a.root), a.name, timeout=a.timeout)
    except CouldNotRun as e:
        print(f"postcondition-loader: VOID: {e}; not a pass", file=sys.stderr)
        return COULD_NOT_RUN
    except DemonstrationFailed as e:
        print(f"postcondition-loader: FAIL: {e}", file=sys.stderr)
        return DEMONSTRATION_FAILED
    codes = ", ".join(f"{limb} {code}" for limb, code in sorted(found.codes.items()))
    print(f"postcondition-loader: loadable '{found.name}' from {found.home} "
          f"(demonstrated: {codes})")
    return LOADABLE


if __name__ == "__main__":
    raise SystemExit(main())

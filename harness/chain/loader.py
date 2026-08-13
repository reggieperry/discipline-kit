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
nothing else. The absence is the honest state.

Usage:
    python3 harness/chain/loader.py <postcondition-name> [--root <repo>] [--timeout <seconds>]

`--root` is the repository whose `.claude/chain/profile.toml` declares the pinned root; it
defaults to the repository holding this file. It is what lets `harness/fixtures/loader_test.py`
point the loader at throwaway trees, which is the only way to observe it refusing.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
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
    return candidate


def refuse_judged_material(pinned: Path) -> None:
    """ADR-0001/D3, mechanically: material inside a working tree is not pinned material."""
    tree = working_tree_above(pinned)
    if tree is not None:
        raise CouldNotRun(
            f"the pinned root {pinned} is inside the git working tree at {tree}, so it is "
            "material the judged party can write (ADR-0001/D3)"
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
    """Run the postcondition against one fixture tree; return its exit code and what it said."""
    try:
        done = subprocess.run(
            [str(run), str(tree)],
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


def load(root: Path, name: str, *, timeout: int = DEFAULT_TIMEOUT,
         say: Callable[[str], None] = print) -> Postcondition:
    """Resolve `name` from the pinned root and demonstrate it, or raise saying why not.

    The denominators go to `say` as they are established, so a refusal reports what it did reach
    rather than only what stopped it.
    """
    pinned = declared_pinned_root(root)
    refuse_judged_material(pinned)
    say(f"postcondition-loader: pinned root {pinned}, declared by {root / PROFILE}")
    home, run, config, fixtures = resolve(pinned, name)
    say(f"postcondition-loader: resolved {name!r} at {home} "
        f"({RUN} present, {CONFIG}/ {'present' if config else 'absent'}, "
        f"{len(fixtures)} fixture tree(s): {', '.join(sorted(fixtures))})")

    codes: dict[str, int] = {}
    broken: list[str] = []
    wrong: list[str] = []
    for limb in sorted(REQUIRED):
        code, transcript = demonstrate(run, home, fixtures[limb], config, timeout)
        codes[limb] = code
        want = REQUIRED[limb]
        say(f"postcondition-loader: demonstration {limb}: exit {code} (required {want})")
        # In full rather than summarized. The transcript is how an operator sees WHICH examiner
        # spoke and why it decided as it did, and a truncated one is a filtered failure signal.
        for line in transcript.splitlines():
            say(f"postcondition-loader: {limb}| {line}")
        if code not in (0, 1):
            broken.append(f"{limb} exited {code}, outside the 0/1 contract")
        elif code != want:
            wrong.append(f"the {limb} fixture returned {code} where {want} was required")

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

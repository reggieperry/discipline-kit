#!/usr/bin/env python3
"""Red-first fixture for `harness/chain/core.py` and `harness/sequencer_source_check.py`.

The core is the sequencer's start-up, its position derivation, and its resume read. Four
decisions become mechanism there and each one has cases here.

ADR-0003/D5, the sequencer starts fail-closed: an absent or unparseable profile, no declared
terminal act, a push scope that does not pair with it, an unset `trusted_base`, one that omits
the sequencer's own sources, and an unusable `pinned_root` each read could-not-run with the
condition named. Exit 2 alone cannot tell those apart, so every refusal case asserts the
condition's own marker as well as the code.

ADR-0001/D1, position is re-derived from refs and never reported: this is the position court that
record's Falsification section names. A fixture repository carries planted refs and the derived
position must equal them, across contiguous, gapped, multi-attempt, empty, foreign and
unreadable permutations.

ADR-0001/D5, harness-written state is admitted for session ids and liveness only: the allowlist
function is the one admitted reader, and the case that discriminates plants a stream carrying
BOTH a session id and every verdict field the design measured non-discriminating, then requires
the verdicts to be absent from what the core prints.

ADR-0004/D2 and D3, the attempt boundary and the settings sources: a fresh attempt takes the next
number and clears the pinned worktree path it owns, and the core's own run cannot be injected
into by a user-scope hook, which at this story's depth means it spawns no harness invocation at
all. The full invocation audit is STORY-0012's.

  THE START-UP GATE
  startup-clean-0            a well-formed profile               -> 0, the posture printed
  profile-absent-2           no profile at all                   -> 2, profile-absent
  profile-unparseable-2      a profile that is not TOML          -> 2, profile-unparseable
  profile-not-a-file-2       a directory at the profile path     -> 2, profile-unparseable
  terminal-undeclared-2      no terminal act                     -> 2, terminal-undeclared
  terminal-nested-2          a terminal act in a nested table    -> 2, terminal-undeclared
  terminal-unknown-2         a terminal act the record omits     -> 2, terminal-unknown
  push-missing-2             a terminal act with no push scope   -> 2, push-unpaired
  push-unpaired-2            open-pr with push = never           -> 2, push-unpaired
  trusted-base-unset-2       no trusted_base                     -> 2, trusted-base-unset
  trusted-base-empty-2       an empty trusted_base               -> 2, trusted-base-unset
  trusted-base-incomplete-2  a base omitting the sequencer       -> 2, trusted-base-incomplete
  trusted-base-omits-invocation-sources-2
                             a base naming five modules by file  -> 2, trusted-base-incomplete,
                             and omitting invoke.py + receipt.py    both omissions named
  sequencer-sources-complete SEQUENCER_SOURCES vs harness/chain/ -> every live module listed
  pinned-root-unset-2        no pinned_root                      -> 2, pinned-root
  pinned-root-in-worktree-2  a pinned root inside a working tree -> 2, pinned-root

  THE POSITION COURT
  position-contiguous        phases 1,2,3 of attempt 1           -> attempt 1, phase 3
  position-gapped            phases 1,2,4                        -> phase 2, gap named
  position-missing-first     phases 2,3                          -> phase 0, gap named
  position-multi-attempt     attempt 1 full, attempt 2 at 1      -> attempt 2, phase 1
  position-empty             no refs at all                      -> attempt 0, phase 0
  position-foreign-ref       a park ref and an attempt note      -> counted as other, not a phase
  position-attempt-only-ref  attempts carrying no phase ref      -> that attempt, phase 0
  position-non-integer-phase phase-x under a good attempt        -> 2, unreadable-ref
  position-phase-zero        phase-0, which orders nothing       -> 2, unreadable-ref
  position-non-integer-att   attempt-one/phase-1                 -> 2, unreadable-ref
  position-other-story       another story's refs alongside      -> not counted
  position-hostile-git-env   GIT_DIR naming a decoy repository   -> derived from --repo
  position-not-a-repo-2      --repo names no working tree        -> 2

  THE RESUME PATH
  resume-clean-0             contiguous refs and a live stream   -> 0, id and liveness printed
  resume-refuses-on-gap-2    a gap in the namespace              -> 2, nothing resumed
  resume-allowlist-drops     a stream carrying verdict fields    -> the verdicts never printed
  resume-liveness-in-phase   events with no result record        -> in-phase
  resume-liveness-complete   a result record present             -> complete
  resume-stream-absent       no stream file                      -> 0, absent, no session id
  resume-two-session-ids     two ids in one stream               -> neither picked

  THE ATTEMPT BOUNDARY
  next-attempt-after-two     attempts 1 and 2 present            -> next attempt 3
  start-attempt-registered   a registered worktree at the path   -> cleared, re-creatable
  start-attempt-unregistered a leftover directory, unregistered  -> force-cleared, inventoried
  start-attempt-in-worktree  a path inside a git working tree    -> 2, that condition named
  start-attempt-symlink      a symlinked path                    -> 2, that condition named
  bounce-rewalk              phases 1..5 bounced to 3            -> 1,2 survive, position 2

  THE SETTINGS-SOURCE SLICE
  decoy-user-hook            a user-scope SessionStart decoy     -> no invocation, no marker

  THE D5 SOURCE CHECK
  source-live-corpus-0       the real harness/chain              -> 0, denominators printed
  source-clean-tree-0        a planted tree with no violation    -> 0
  source-comments-only-0     the patterns in prose alone         -> 0
  source-allowlist-exempt-0  the admitted reader parsing a stream-> 0
  source-status-frontmatter  a story spec's status field read    -> 1
  source-event-log           an event-log path opened            -> 1
  source-stream-verdict      is_error read in control flow       -> 1
  source-result-string       a wrapper return string consumed    -> 1
  source-harness-json        a stream parsed outside the reader  -> 1
  source-subagent-spawn      a subagent spawned                  -> 1
  source-session-resume      --resume on an advancement path     -> 1
  source-session-continue    --continue, resumption by another
                             flag, on an advancement path        -> 1
  source-session-short-flag  a quoted "-r" argv element, the
                             short resume flag                   -> 1
  source-verdict-in-reader   the reader itself reading is_error  -> 1
  source-widened-allowlist   ADMITTED_KEYS carrying a new key    -> 1
  source-no-allowlist-2      no admitted reader to exempt        -> 2
  source-empty-dir-2         nothing to examine                  -> 2

THE REFUSAL CASES ASSERT AN ABSENCE where the ordering is the property. `resume-refuses-on-gap-2`
requires the session-id line to be ABSENT: a resume that reads the stream and then notices the
namespace is inconsistent has already admitted harness state into a run it must not start.

Run: python3 harness/fixtures/core_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
CORE = HARNESS / "chain" / "core.py"
SOURCE_CHECK = HARNESS / "sequencer_source_check.py"

VOID = "core: VOID"
STORY = "STORY-0042"
OTHER_STORY = "STORY-0099"
SESSION = "6f1c9a2e-0b3d-4e77-9f21-8c5a4d6b1e30"
SECOND_SESSION = "1a2b3c4d-5e6f-4708-8192-a3b4c5d6e7f8"
DECOY_MARKER = "USER-SCOPE-HOOK-FIRED"

GOOD_PROFILE = """terminal = "open-pr"
push = "branches-only"
pinned_root = "{pinned}"
trusted_base = [".claude/", "harness/", "scripts/"]
"""

# A `claude` that behaves as the probe measured a user-scope SessionStart hook behaving: it
# writes the decoy marker before doing anything else. If the core ever invokes it, the marker
# lands and `decoy-user-hook` fails on the observable the story names.
CLAUDE_DECOY = """#!/usr/bin/env bash
printf 'claude %s\\n' "$*" >> {log}
printf '%s\\n' "{marker}" > {sentinel}
exit 0
"""

GIT_SPY = """#!/usr/bin/env bash
printf 'git %s\\n' "$*" >> {log}
exec {real} "$@"
"""


def clean_env() -> dict[str, str]:
    """The environment with git's own variables dropped.

    A `pre-commit` hook exports `GIT_DIR` and `GIT_INDEX_FILE`, and a subprocess inherits them,
    so a fixture that builds a throwaway repository writes into the REAL one instead. The tool
    under test scrubs the same variables for its own children, which is what
    `position-hostile-git-env` observes; that case deliberately does not use this helper.
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
    (path / "README.md").write_text("the graded tree\n")
    git(path, "init", "-q", "-b", "main", ".")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "fixture")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "baseline", "--allow-empty")
    return path


def phase_ref(story: str = STORY, attempt: int | str = 1, phase: int | str = 1) -> str:
    return f"refs/chain/{story}/attempt-{attempt}/phase-{phase}"


def plant(repo: Path, *refs: str) -> str:
    """Plant refs at HEAD and return the sha they all name."""
    sha = git(repo, "rev-parse", "HEAD")
    for ref in refs:
        git(repo, "update-ref", ref, sha)
    return sha


def ref_value(repo: Path, ref: str) -> str | None:
    done = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True, text=True, env=clean_env(),
    )
    return done.stdout.strip() or None


def kit_tree(td: Path, pinned: Path | None, *, profile: str | None = None,
             name: str = "kit") -> Path:
    """A repository-shaped tree carrying the chain profile the core reads at start-up.

    This is the SEQUENCER's own profile, never the graded repository's: the party that grades
    declares its own posture and its own examiner root (ADR-0001/D3, ADR-0003/D4).
    """
    kit = td / name
    chain = kit / ".claude" / "chain"
    chain.mkdir(parents=True)
    body = GOOD_PROFILE.format(pinned=pinned) if profile is None else profile
    (chain / "profile.toml").write_text(body)
    return kit


def pinned_root(td: Path, name: str = "pinned") -> Path:
    root = td / name
    root.mkdir(parents=True)
    return root


def run_core(act: str, *args: str, env: dict[str, str] | None = None
             ) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CORE), act, *args],
        capture_output=True, text=True, env=clean_env() if env is None else env,
    )


def run_source_check(directory: Path, env: dict[str, str] | None = None
                     ) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SOURCE_CHECK), "--dir", str(directory)],
        capture_output=True, text=True, env=clean_env() if env is None else env,
    )


def judge(name: str, got: subprocess.CompletedProcess[str], *, want: int, marker: str,
          absent: str | tuple[str, ...] = (), present: tuple[str, ...] = (),
          faults: tuple[str, ...] = ()) -> bool:
    """Compare the exit code, required markers, any marker that must NOT appear, and the state.

    `faults` carries whatever the caller established about the filesystem or the refs before
    judging, already worded as a complaint. It arrives here rather than being printed after the
    verdict line so that the verdict line is the verdict: a case printing `ok` and then a
    complaint under it is the shape where a reader stops at the first word.
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
            detail += f" (found '{forbidden}', which must not have been read)"
    for fault in faults:
        ok = False
        detail += f" ({fault})"
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: want exit {want} naming '{marker}', "
          f"got exit {got.returncode}{detail}")
    if not ok:
        print(f"       stdout: {got.stdout.strip()[:600]}")
        print(f"       stderr: {got.stderr.strip()[:600]}")
    return ok


def startup_case(name: str, *, want: int, marker: str, profile: str | None,
                 pinned: str = "make", present: tuple[str, ...] = ()) -> bool:
    """One start-up condition, planted in a throwaway kit tree."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        root = pinned_root(tmp) if pinned == "make" else None
        body = None if profile is None else profile.format(pinned=root)
        kit = kit_tree(tmp, root, profile=body)
        if profile is not None and "PROFILE-IS-A-DIRECTORY" in profile:
            path = kit / ".claude" / "chain" / "profile.toml"
            path.unlink()
            path.mkdir()
        return judge(name, run_core("startup", "--root", str(kit)), want=want, marker=marker,
                     present=present)


def startup_clean_case() -> bool:
    return startup_case("startup-clean-0", want=0, marker="core: posture:", profile=None)


def profile_absent_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        bare = Path(td) / "bare"
        bare.mkdir()
        return judge("profile-absent-2", run_core("startup", "--root", str(bare)),
                     want=2, marker="profile-absent")


def profile_unparseable_case() -> bool:
    return startup_case("profile-unparseable-2", want=2, marker="profile-unparseable",
                        profile='terminal = "open-pr\nthis is not toml [[[\n')


def profile_not_a_file_case() -> bool:
    return startup_case("profile-not-a-file-2", want=2, marker="profile-unparseable",
                        profile='# PROFILE-IS-A-DIRECTORY\n')


def terminal_undeclared_case() -> bool:
    return startup_case(
        "terminal-undeclared-2", want=2, marker="terminal-undeclared",
        profile='push = "branches-only"\npinned_root = "{pinned}"\ntrusted_base = ["harness/"]\n')


def terminal_nested_case() -> bool:
    """A declaration below the top level is a guess about which one governs, so it is refused."""
    return startup_case(
        "terminal-nested-2", want=2, marker="terminal-undeclared",
        profile='pinned_root = "{pinned}"\ntrusted_base = ["harness/"]\n'
                '[chain]\nterminal = "open-pr"\npush = "branches-only"\n')


def terminal_unknown_case() -> bool:
    return startup_case(
        "terminal-unknown-2", want=2, marker="terminal-unknown",
        profile='terminal = "push-to-main"\npush = "branches-only"\n'
                'pinned_root = "{pinned}"\ntrusted_base = ["harness/"]\n')


def push_missing_case() -> bool:
    return startup_case(
        "push-missing-2", want=2, marker="push-unpaired",
        profile='terminal = "open-pr"\npinned_root = "{pinned}"\ntrusted_base = ["harness/"]\n')


def push_unpaired_case() -> bool:
    return startup_case(
        "push-unpaired-2", want=2, marker="push-unpaired",
        profile='terminal = "open-pr"\npush = "never"\n'
                'pinned_root = "{pinned}"\ntrusted_base = ["harness/"]\n')


def trusted_base_unset_case() -> bool:
    return startup_case(
        "trusted-base-unset-2", want=2, marker="trusted-base-unset",
        profile='terminal = "open-pr"\npush = "branches-only"\npinned_root = "{pinned}"\n')


def trusted_base_empty_case() -> bool:
    return startup_case(
        "trusted-base-empty-2", want=2, marker="trusted-base-unset",
        profile='terminal = "open-pr"\npush = "branches-only"\n'
                'pinned_root = "{pinned}"\ntrusted_base = []\n')


def trusted_base_incomplete_case() -> bool:
    """ADR-0003/D5's second half: a base omitting the sequencer's own sources guards nothing."""
    return startup_case(
        "trusted-base-incomplete-2", want=2, marker="trusted-base-incomplete",
        profile='terminal = "open-pr"\npush = "branches-only"\n'
                'pinned_root = "{pinned}"\ntrusted_base = [".claude/", "scripts/"]\n')


def trusted_base_omits_invocation_sources_case() -> bool:
    """The two modules STORY-0009's audit found outside the D4 list, each required by name.

    The base below names five sequencer modules file by file and omits invoke.py and receipt.py,
    the two that shipped without joining SEQUENCER_SOURCES. Both must be in the refusal's own
    message: a case asserting only the marker would stay green while either one drifted back out
    of the list, because the other's absence raises the identical refusal.
    """
    return startup_case(
        "trusted-base-omits-invocation-sources-2", want=2, marker="trusted-base-incomplete",
        present=("harness/chain/invoke.py", "harness/chain/receipt.py"),
        profile='terminal = "open-pr"\npush = "branches-only"\n'
                'pinned_root = "{pinned}"\n'
                'trusted_base = [".claude/", "scripts/", "harness/chain/core.py",\n'
                '  "harness/chain/advance.py", "harness/chain/attempt.py",\n'
                '  "harness/chain/loader.py", "harness/chain/merge.py"]\n')


def sequencer_sources_complete_case() -> bool:
    """The hand-kept D4 list held to the directory it stands for, so it cannot drift silently.

    STORY-0009's audit measured the drift live: SEQUENCER_SOURCES read five modules while
    harness/chain/ held seven, so a trusted_base omitting invoke.py or receipt.py started
    cleanly. The commit-path court now requires the whole directory covered
    (scripts/profile-check.sh); this case holds the run-time gate's list to the same
    denominator, and a module added to harness/chain/ without joining the list fails here.
    """
    sys.path.insert(0, str(CORE.parent))
    import core
    listed = frozenset(core.SEQUENCER_SOURCES)
    on_disk = frozenset(f"harness/chain/{p.name}" for p in CORE.parent.glob("*.py"))
    missing = sorted(on_disk - listed)
    stale = sorted(listed - on_disk)
    ok = not missing and not stale
    detail = ""
    if missing:
        detail += f" (on disk and not in SEQUENCER_SOURCES: {', '.join(missing)})"
    if stale:
        detail += f" (in SEQUENCER_SOURCES and not on disk: {', '.join(stale)})"
    print(f"  {'ok  ' if ok else 'FAIL'} sequencer-sources-complete: {len(listed)} listed, "
          f"{len(on_disk)} module(s) in harness/chain/{detail}")
    return ok


def pinned_root_unset_case() -> bool:
    return startup_case(
        "pinned-root-unset-2", want=2, marker="pinned-root",
        profile='terminal = "open-pr"\npush = "branches-only"\ntrusted_base = ["harness/"]\n',
        pinned="none")


def pinned_root_in_worktree_case() -> bool:
    """The loader's own refusal, reached through the core: one definition of a usable root."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        inside = init_repo(tmp / "judged") / "pinned"
        inside.mkdir()
        kit = kit_tree(tmp, inside)
        return judge("pinned-root-in-worktree-2", run_core("startup", "--root", str(kit)),
                     want=2, marker="is inside the git working tree")


def position_case(name: str, refs: tuple[str, ...], *, want: int = 0,
                  marker: str = "core: position:", also: tuple[str, ...] = (),
                  absent: tuple[str, ...] = ()) -> bool:
    with tempfile.TemporaryDirectory() as td:
        repo = init_repo(Path(td) / "graded")
        if refs:
            plant(repo, *refs)
        got = run_core("position", "--repo", str(repo), "--story", STORY)
        return judge(name, got, want=want, marker=marker, absent=absent, present=also)


def position_contiguous_case() -> bool:
    return position_case(
        "position-contiguous",
        tuple(phase_ref(phase=n) for n in (1, 2, 3)),
        also=("attempt 1 phase 3",))


def position_gapped_case() -> bool:
    """A gap is a named integrity finding and the higher ref is never skipped over."""
    return position_case(
        "position-gapped",
        tuple(phase_ref(phase=n) for n in (1, 2, 4)),
        want=2, marker="gap:", also=("attempt 1 phase 2",))


def position_missing_first_case() -> bool:
    return position_case(
        "position-missing-first",
        tuple(phase_ref(phase=n) for n in (2, 3)),
        want=2, marker="gap:", also=("attempt 1 phase 0",))


def position_multi_attempt_case() -> bool:
    return position_case(
        "position-multi-attempt",
        tuple(phase_ref(phase=n) for n in (1, 2, 3)) + (phase_ref(attempt=2, phase=1),),
        also=("attempt 2 phase 1",))


def position_empty_case() -> bool:
    return position_case("position-empty", (), also=("attempt 0 phase 0",))


def position_foreign_ref_case() -> bool:
    """A park ref and a note under an attempt are neither phases nor findings."""
    return position_case(
        "position-foreign-ref",
        (phase_ref(phase=1), phase_ref(phase=2),
         f"refs/chain/{STORY}/park", f"refs/chain/{STORY}/attempt-1/notes"),
        also=("attempt 1 phase 2", "2 other ref(s)"))


def position_attempt_only_ref_case() -> bool:
    """An attempt carrying no phase ref still counts as started, so its number is not reused.

    Both shapes are planted: a ref under an attempt, and a ref AT one. The second is why the
    attempt match does not require a trailing separator, since a bare `attempt-3` that did not
    register would let the next attempt reuse a number the namespace already mentions.
    """
    return position_case(
        "position-attempt-only-ref",
        (phase_ref(phase=1), f"refs/chain/{STORY}/attempt-2/notes",
         f"refs/chain/{STORY}/attempt-3"),
        also=("attempt 3 phase 0",))


def position_non_integer_phase_case() -> bool:
    return position_case(
        "position-non-integer-phase",
        (phase_ref(phase=1), phase_ref(phase="x")),
        want=2, marker="unreadable-ref:")


def position_phase_zero_case() -> bool:
    return position_case(
        "position-phase-zero",
        (phase_ref(phase=1), phase_ref(phase=0)),
        want=2, marker="unreadable-ref:")


def position_non_integer_attempt_case() -> bool:
    return position_case(
        "position-non-integer-att",
        (phase_ref(phase=1), phase_ref(attempt="one", phase=1)),
        want=2, marker="unreadable-ref:")


def position_other_story_case() -> bool:
    return position_case(
        "position-other-story",
        (phase_ref(phase=1),
         phase_ref(story=OTHER_STORY, phase=4), phase_ref(story=OTHER_STORY, attempt=3, phase=1)),
        also=("attempt 1 phase 1",))


def position_hostile_env_case() -> bool:
    """`GIT_DIR` names a decoy: the derivation must read the repository it was pointed at."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        decoy = init_repo(tmp / "decoy")
        plant(repo, phase_ref(phase=1), phase_ref(phase=2))
        plant(decoy, *[phase_ref(phase=n) for n in (1, 2, 3, 4, 5)])
        env = clean_env()
        env["GIT_DIR"] = str(decoy / ".git")
        env["GIT_INDEX_FILE"] = str(decoy / ".git" / "index")
        got = run_core("position", "--repo", str(repo), "--story", STORY, env=env)
        return judge("position-hostile-git-env", got, want=0, marker="attempt 1 phase 2")


def position_not_a_repo_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        bare = Path(td) / "not-a-repo"
        bare.mkdir()
        return judge("position-not-a-repo-2",
                     run_core("position", "--repo", str(bare), "--story", STORY),
                     want=2, marker=VOID)


def stream_file(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    return path


def verdict_stream(path: Path, *, result: bool = True, session: str = SESSION,
                   second: str | None = None) -> Path:
    """A stream carrying a session id AND every verdict field the design measured.

    The denial probe returned `is_error` false, `subtype` success and an empty
    `permission_denials` on a phase that did nothing, which is why none of them may reach a
    decision. They are planted here so their ABSENCE from what the core prints is an
    observation rather than an assumption.
    """
    records: list[dict] = [
        {"type": "system", "subtype": "init", "session_id": session},
        {"type": "assistant", "session_id": session, "message": {"role": "assistant"}},
    ]
    if second is not None:
        records.append({"type": "assistant", "session_id": second})
    if result:
        records.append({
            "type": "result", "subtype": "success", "is_error": False,
            "permission_denials": [], "session_id": session,
            "result": "WRAPPER-RETURN-STRING", "total_cost_usd": 0.034,
        })
    return stream_file(path, records)


def resume_clean_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        plant(repo, phase_ref(phase=1), phase_ref(phase=2))
        stream = verdict_stream(tmp / "runs" / STORY / "2.jsonl")
        got = run_core("resume", "--repo", str(repo), "--story", STORY, "--stream", str(stream))
        return judge("resume-clean-0", got, want=0, marker="attempt 1 phase 2", present=(SESSION,),
                     absent=("is_error", "permission_denials", "WRAPPER-RETURN-STRING"))


def resume_gap_case() -> bool:
    """A resume over an inconsistent namespace does not start, and reads no harness state."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        plant(repo, phase_ref(phase=1), phase_ref(phase=4))
        stream = verdict_stream(tmp / "runs" / STORY / "4.jsonl")
        got = run_core("resume", "--repo", str(repo), "--story", STORY, "--stream", str(stream))
        return judge("resume-refuses-on-gap-2", got, want=2, marker="gap:",
                     absent=(SESSION, "core: admitting from"))


def resume_allowlist_case() -> bool:
    """The one admitted reader returns ids and liveness, and provably not the verdicts."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        plant(repo, phase_ref(phase=1))
        stream = verdict_stream(tmp / "runs" / STORY / "1.jsonl")
        got = run_core("resume", "--repo", str(repo), "--story", STORY, "--stream", str(stream))
        return judge("resume-allowlist-drops", got, want=0, marker="liveness complete",
                     absent=("is_error", "subtype", "permission_denials",
                             "WRAPPER-RETURN-STRING", "total_cost_usd", "success"))


def resume_in_phase_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        plant(repo, phase_ref(phase=1))
        stream = verdict_stream(tmp / "runs" / STORY / "2.jsonl", result=False)
        got = run_core("resume", "--repo", str(repo), "--story", STORY, "--stream", str(stream))
        return judge("resume-liveness-in-phase", got, want=0, marker="liveness in-phase")


def resume_complete_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        plant(repo, phase_ref(phase=1))
        stream = verdict_stream(tmp / "runs" / STORY / "1.jsonl")
        got = run_core("resume", "--repo", str(repo), "--story", STORY, "--stream", str(stream))
        return judge("resume-liveness-complete", got, want=0, marker="liveness complete")


def resume_stream_absent_case() -> bool:
    """A stream is diagnosis, so its absence is reported and never blocks the derivation."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        plant(repo, phase_ref(phase=1))
        got = run_core("resume", "--repo", str(repo), "--story", STORY,
                       "--stream", str(tmp / "runs" / STORY / "nothing.jsonl"))
        return judge("resume-stream-absent", got, want=0, marker="liveness absent")


def resume_two_ids_case() -> bool:
    """Two ids in one stream: neither is picked, because picking one would be a guess."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        plant(repo, phase_ref(phase=1))
        stream = verdict_stream(tmp / "runs" / STORY / "1.jsonl", second=SECOND_SESSION)
        got = run_core("resume", "--repo", str(repo), "--story", STORY, "--stream", str(stream))
        return judge("resume-two-session-ids", got, want=0, marker="session id none (2 seen)",
                     absent=(SESSION, SECOND_SESSION))


def next_attempt_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        plant(repo, phase_ref(phase=1), phase_ref(phase=2), phase_ref(attempt=2, phase=1))
        root = tmp / "worktrees"
        got = run_core("start-attempt", "--repo", str(repo), "--story", STORY,
                       "--worktree-root", str(root))
        return judge("next-attempt-after-two", got, want=0, marker="next attempt 3")


def start_attempt_registered_case() -> bool:
    """A registered worktree at the pinned path is removed, so the attempt can create its own."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        root = tmp / "worktrees"
        path = root / STORY / "attempt-1"
        git(repo, "worktree", "add", "-q", "-b", "phase-tester", str(path))
        got = run_core("start-attempt", "--repo", str(repo), "--story", STORY,
                       "--worktree-root", str(root))
        faults = () if not path.exists() else (
            "the pinned path still exists, so an attempt cannot create a worktree there",)
        return judge("start-attempt-registered", got, want=0, marker="next attempt 1",
                     faults=faults)


def start_attempt_unregistered_case() -> bool:
    """The clearing-authority decision: a leftover the registration no longer covers is cleared.

    `attempt.py` refuses to delete a directory git does not know about, which is right for a
    caller-named path and wedges every retry of a story whose phase crashed. The sequencer owns
    this path by construction, so it clears it under its own authority after recording what it
    found. The case is only constructed if the leftover really is unregistered.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        root = tmp / "worktrees"
        path = root / STORY / "attempt-1"
        git(repo, "worktree", "add", "-q", "-b", "phase-tester", str(path))
        git(repo, "worktree", "remove", "--force", str(path))
        path.mkdir(parents=True)
        (path / "leftover.txt").write_text("a crashed phase left this\n")
        registered = str(path) in git(repo, "worktree", "list", "--porcelain")
        got = run_core("start-attempt", "--repo", str(repo), "--story", STORY,
                       "--worktree-root", str(root))
        faults = []
        if registered:
            faults.append("the leftover was still registered, so the case was not constructed")
        if path.exists():
            faults.append("the leftover survived, so a retry still cannot start")
        return judge("start-attempt-unregistered", got, want=0, marker="leftover.txt",
                     faults=tuple(faults))


def start_attempt_in_worktree_case() -> bool:
    """The ownership condition: a path inside a working tree is never the core's to clear."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        root = repo / "inside"
        (root / STORY / "attempt-1").mkdir(parents=True)
        got = run_core("start-attempt", "--repo", str(repo), "--story", STORY,
                       "--worktree-root", str(root))
        faults = () if (root / STORY / "attempt-1").exists() else (
            "the refused path was deleted anyway",)
        return judge("start-attempt-in-worktree", got, want=2,
                     marker="sits inside the git working tree", faults=faults)


def start_attempt_symlink_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        root = tmp / "worktrees"
        elsewhere = tmp / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "keep.txt").write_text("not the sequencer's\n")
        (root / STORY).mkdir(parents=True)
        (root / STORY / "attempt-1").symlink_to(elsewhere)
        got = run_core("start-attempt", "--repo", str(repo), "--story", STORY,
                       "--worktree-root", str(root))
        faults = () if (elsewhere / "keep.txt").exists() else (
            "the symlink's target was deleted, which the core never owns",)
        return judge("start-attempt-symlink", got, want=2, marker="is a symlink",
                     faults=faults)


def bounce_case() -> bool:
    """ADR-0001/D1's re-walk, driven by the core: phases 3 and above of the current attempt go."""
    with tempfile.TemporaryDirectory() as td:
        repo = init_repo(Path(td) / "graded")
        plant(repo, *[phase_ref(phase=n) for n in (1, 2, 3, 4, 5)])
        got = run_core("bounce", "--repo", str(repo), "--story", STORY, "--to-phase", "3")
        survived = [n for n in (1, 2, 3, 4, 5) if ref_value(repo, phase_ref(phase=n))]
        faults = () if survived == [1, 2] else (f"survivors {survived}, wanted [1, 2]",)
        return judge("bounce-rewalk", got, want=0, marker="attempt 1 phase 2", faults=faults)


def decoy_hook_case() -> bool:
    """The honest slice of criterion 3, at the depth the core can pin today.

    ADR-0004/D3 pins the settings sources of a PHASE invocation, and the probe measured a
    user-scope SessionStart hook injecting into phase transcripts. The core is a script under
    ADR-0004/D1 and has no transcript of its own, so what is observable here is that it produces
    no phase transcript at all: a `claude` on PATH that would inject the decoy marker is never
    invoked, while the git spy beside it logs invocations, which is what proves the shimmed PATH
    was live rather than ignored. The per-invocation audit is STORY-0012's.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = init_repo(tmp / "graded")
        plant(repo, phase_ref(phase=1), phase_ref(phase=2))
        stream = verdict_stream(tmp / "runs" / STORY / "2.jsonl")

        home = tmp / "home"
        (home / ".claude").mkdir(parents=True)
        sentinel = tmp / "decoy-marker.txt"
        log = tmp / "invocations.log"
        (home / ".claude" / "settings.json").write_text(json.dumps({
            "hooks": {"SessionStart": [{"hooks": [
                {"type": "command", "command": f"echo {DECOY_MARKER} > {sentinel}"}]}]}
        }))

        bindir = tmp / "shim-bin"
        bindir.mkdir()
        real = subprocess.run(["bash", "-c", "command -v git"], capture_output=True, text=True,
                              env=clean_env()).stdout.strip()
        (bindir / "git").write_text(GIT_SPY.format(log=log, real=real))
        (bindir / "git").chmod(0o755)
        (bindir / "claude").write_text(
            CLAUDE_DECOY.format(log=log, marker=DECOY_MARKER, sentinel=sentinel))
        (bindir / "claude").chmod(0o755)

        env = clean_env()
        env["HOME"] = str(home)
        env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
        got = run_core("resume", "--repo", str(repo), "--story", STORY, "--stream", str(stream),
                       env=env)

        logged = log.read_text().splitlines() if log.is_file() else []
        spawned = [line for line in logged if line.startswith("claude ")]
        faults = []
        if sentinel.exists():
            faults.append("the decoy marker was written, so something invoked the harness")
        if spawned:
            faults.append(f"{len(spawned)} harness invocation(s) on a path that composes none")
        if not logged:
            faults.append("the shim logged nothing, so PATH was not in effect and this is void")
        return judge("decoy-user-hook", got, want=0, marker="attempt 1 phase 2",
                     absent=DECOY_MARKER, faults=tuple(faults))


# The planted sequencer sources. Each names one pattern the D5 source check must find, and the
# clean pair is what keeps a check that fires on everything from passing this suite.
CLEAN_CORE = '''#!/usr/bin/env python3
"""A core whose docstring mentions nothing forbidden."""
ADMITTED_KEYS = frozenset({"session_id", "type"})


def admitted_signals(path):
    """The one admitted reader."""
    import json
    signals = []
    for line in path.read_text().splitlines():
        record = json.loads(line)
        signals.append({k: v for k, v in record.items() if k in ADMITTED_KEYS})
    return signals


def position(repo):
    return len(repo)
'''

COMMENTS_ONLY = '''#!/usr/bin/env python3
"""A module naming is_error, subtype, permission_denials and --resume in PROSE.

The design measured every one of those fields reporting success on a phase that did nothing, and
a record that may not name them cannot state its own reason. Reading `runs/x/1.jsonl` is what
this module does not do.
"""


def decide(verdict):
    # status: done in a story spec is not authority, and --resume is not depended on here.
    return verdict
'''

PLANTED = {
    "source-status-frontmatter": 'import re\n\n\ndef read(text):\n'
                                 '    return re.search(r"^status: done", text)\n',
    "source-event-log": 'def read(path):\n'
                        '    return open("/var/log/discipline-chain/events.jsonl").read()\n',
    "source-stream-verdict": 'def decide(record):\n'
                             '    if record["is_error"]:\n        return 1\n    return 0\n',
    "source-result-string": 'def decide(record):\n'
                            '    return record["result"].strip() == "done"\n',
    "source-harness-json": 'import json\n\n\ndef read(line):\n    return json.loads(line)\n',
    "source-subagent-spawn": 'def run(brief):\n'
                             '    return Task(subagent_type="worker", prompt=brief)\n',
    "source-session-resume": 'def invoke(sid):\n'
                             '    return ["claude", "-p", "go", "--resume", sid]\n',
    "source-session-continue": 'def invoke():\n'
                               '    return ["claude", "-p", "go", "--continue"]\n',
    "source-session-short-flag": 'def invoke(sid):\n'
                                 '    return ["claude", "-p", "go", "-r", sid]\n',
}


def source_tree(td: Path, files: dict[str, str]) -> Path:
    directory = td / "chain"
    directory.mkdir(parents=True)
    for name, body in files.items():
        (directory / name).write_text(body)
    return directory


def source_case(name: str, files: dict[str, str], *, want: int, marker: str) -> bool:
    with tempfile.TemporaryDirectory() as td:
        directory = source_tree(Path(td), files)
        return judge(name, run_source_check(directory), want=want, marker=marker)


def source_live_corpus_case() -> bool:
    """The live corpus, which is what makes the check non-vacuous rather than merely present.

    A clean report over an empty corpus is the shape this whole kit exists against, so the
    denominator is asserted rather than printed: `0 file(s) examined` must not appear.
    """
    return judge("source-live-corpus-0", run_source_check(HARNESS / "chain"), want=0,
                 marker="file(s) examined", absent="0 file(s) examined")


def source_planted_case(name: str) -> bool:
    return source_case(name, {"core.py": CLEAN_CORE, "phase.py": PLANTED[name]},
                       want=1, marker="source-check: FINDING")


def source_verdict_in_reader_case() -> bool:
    """The stream patterns are exempt inside the admitted reader; the verdict patterns are not.

    The exemption exists so ONE function may touch a stream, never so that function may decide
    from it. A reader that reaches into `is_error` is the same defect one level in, so the case
    plants exactly that and requires a finding.
    """
    reader = CLEAN_CORE.replace(
        "        signals.append({k: v for k, v in record.items() if k in ADMITTED_KEYS})",
        "        if record[\"is_error\"]:\n            signals.append(record)")
    return source_case("source-verdict-in-reader", {"core.py": reader},
                       want=1, marker="source-check: FINDING")


def source_widened_allowlist_case() -> bool:
    """The allowlist is a declared set, and widening it to a verdict field is a finding."""
    widened = CLEAN_CORE.replace(
        'frozenset({"session_id", "type"})',
        'frozenset({"session_id", "type", "result"})')
    return source_case("source-widened-allowlist", {"core.py": widened},
                       want=1, marker="source-check: FINDING")


def source_no_allowlist_case() -> bool:
    """With no admitted reader to exempt, the check proved nothing and says so."""
    return source_case("source-no-allowlist-2", {"core.py": "def position(repo):\n    return 0\n"},
                       want=2, marker="source-check: VOID")


def source_empty_dir_case() -> bool:
    return source_case("source-empty-dir-2", {}, want=2, marker="source-check: VOID")


def main() -> int:
    for tool in (CORE, SOURCE_CHECK):
        if not tool.is_file():
            print(f"core_test: tool not found at {tool}", file=sys.stderr)
            return 2
    results = [
        startup_clean_case(),
        profile_absent_case(),
        profile_unparseable_case(),
        profile_not_a_file_case(),
        terminal_undeclared_case(),
        terminal_nested_case(),
        terminal_unknown_case(),
        push_missing_case(),
        push_unpaired_case(),
        trusted_base_unset_case(),
        trusted_base_empty_case(),
        trusted_base_incomplete_case(),
        trusted_base_omits_invocation_sources_case(),
        sequencer_sources_complete_case(),
        pinned_root_unset_case(),
        pinned_root_in_worktree_case(),

        position_contiguous_case(),
        position_gapped_case(),
        position_missing_first_case(),
        position_multi_attempt_case(),
        position_empty_case(),
        position_foreign_ref_case(),
        position_attempt_only_ref_case(),
        position_non_integer_phase_case(),
        position_phase_zero_case(),
        position_non_integer_attempt_case(),
        position_other_story_case(),
        position_hostile_env_case(),
        position_not_a_repo_case(),

        resume_clean_case(),
        resume_gap_case(),
        resume_allowlist_case(),
        resume_in_phase_case(),
        resume_complete_case(),
        resume_stream_absent_case(),
        resume_two_ids_case(),

        next_attempt_case(),
        start_attempt_registered_case(),
        start_attempt_unregistered_case(),
        start_attempt_in_worktree_case(),
        start_attempt_symlink_case(),
        bounce_case(),

        decoy_hook_case(),

        source_live_corpus_case(),
        source_case("source-clean-tree-0", {"core.py": CLEAN_CORE}, want=0,
                    marker="file(s) examined"),
        source_case("source-comments-only-0", {"core.py": CLEAN_CORE, "prose.py": COMMENTS_ONLY},
                    want=0, marker="file(s) examined"),
        source_case("source-allowlist-exempt-0", {"core.py": CLEAN_CORE}, want=0,
                    marker="1 admitted reader"),
        *[source_planted_case(name) for name in sorted(PLANTED)],
        source_verdict_in_reader_case(),
        source_widened_allowlist_case(),
        source_no_allowlist_case(),
        source_empty_dir_case(),
    ]
    failed = results.count(False)
    print(f"core_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

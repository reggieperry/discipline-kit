#!/usr/bin/env python3
"""Red-first fixture for `harness/chain/sequencer.py`, the pinned driver.

The sequencer composes the whole walk — phases, seams, harvest, merge stage, post-batch audit —
and decides no verdict anywhere, so every case here asserts exit code AND marker AND state:
refs, branches and trees read back from throwaway clones, records and streams read back from
throwaway pinned roots. The harness is the injectable `--harness` seam pointed at a stub that
dispatches on the composed prompt itself (the brief bytes are the argv, so per-phase behavior is
selected by the one instruction channel); no case invokes the real `claude`. Every git spawn
scrubs the caller's own `GIT_*` environment first, and the bench also strips the driving
session's own `CLAUDE*` variables so the scrub-count assertions are hermetic under any caller.

  THE WHOLE WALK (criterion 1)
  walk-replay-0              two phases, merge-local, audit         -> 0; phase refs chained,
                                                                       story branch at the final
                                                                       ref, main advanced with
                                                                       the trailer and both
                                                                       artifacts, merge_ok: true,
                                                                       clone left on the branch
  streams-composed-0         finding 2: streams by construction     -> 0; p1/p2 under
                                                                       streams/<story>/attempt-1,
                                                                       audit denominator >= 2

  THE ENVIRONMENT AND IDENTITY GATES (criterion 2)
  decoy-env-0                CLAUDECODE + CLAUDE_CODE_SESSION_ID    -> 0; stub sees both unset,
                             + ANTHROPIC_PROBE planted                 probe SURVIVES (the
                                                                       false-drop guard)
  identity-unset-2           clone without repo-local identity      -> 2, identity-unset, zero
                                                                       spend (no stub log)
  gpgsign-local-2            repo-local commit.gpgsign true         -> 2, identity-signing, zero
                                                                       spend

  THE VERDICT RELAYS (criteria 3 and 4)
  park-relay-1               phase-1 commits the wrong file         -> 1, the seam's own words,
                                                                       one spawn only, no ref,
                                                                       no record, no merge
  audit-report-2             a task_started record in phase 2's     -> 2, FINDING relayed, main
                             stream                                    STILL advanced, refs stay,
                                                                       the outcome-stands line
  did-nothing-phase-1        phase 1 emits records, commits nothing -> 1; harvest no-ops at the
                                                                       base and the seam owns the
                                                                       verdict

  RESUME AND RE-WALK
  phase-death-resume         phase 2 dies, then a re-run completes  -> 2 then 0; phase 1 never
                                                                       re-spawned, dead stream
                                                                       kept as p2.prior1, fresh
                                                                       p2, merge done
  fresh-attempt-unearned-2   --fresh-attempt before anything ran    -> 2, refused
  rerun-concluded-2          re-run after a merged walk             -> 2, attempt-concluded names
                                                                       the record and the flag,
                                                                       nothing spawned
  fresh-attempt-0            --fresh-attempt after the merge        -> 0; attempt 2 walked from
                                                                       phase 1, the branch
                                                                       reconcile named
  park-then-rerun-reconcile-0 phase-2 park, then a corrected re-run -> 0; the failed commit is
                                                                       listed discarded and is
                                                                       NOT an ancestor of the
                                                                       merged candidate

  THE PHASE TABLE (zero-spend refusals)
  table-absent-2             no phases/<story> file                 -> 2, the composed path named
  table-malformed-2          a two-field line                       -> 2, file:line named
  table-gap-2                phases 1 and 3 declared                -> 2, the hole named
  table-brief-missing-2      a brief the table names is absent      -> 2, brief-absent

  THE HOSTILE SHAPES
  hostile-branch-moved-2     phase 1 mints the story branch itself  -> 2, the create refused
  story-branch-unrelated-2   a pre-planted unrelated branch         -> 2, refused before any
                                                                       spawn, branch not deleted
  hostile-history-rewrite-2  phase 1 moves to an orphan commit      -> 2, harvest-diverged,
                                                                       nothing anchored

Run: python3 harness/fixtures/sequencer_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
SEQUENCER = HARNESS / "chain" / "sequencer.py"

STORY = "STORY-0042"
SESSION = "6f1c9a2e-0b3d-4e77-9f21-8c5a4d6b1e30"
PIN = "2.1.224"

PROFILE = """terminal = "merge-local"
push = "never"
harness_version = "__PIN__"
pinned_root = "__PINNED__"
trusted_base = [".claude/", "harness/", "scripts/"]
"""

# The two pinned briefs. The dispatch markers ride the first line; the shapes that break naive
# composition ride along (an em dash, quotes, a shell metacharacter, and no trailing newline on
# the second), so byte-for-byte relay is the only composition that reaches the stub's case arms.
BRIEF1 = ('Phase 1 phase-1-marker — build the walk artifact.\n\n'
          'Commit one file and say "blocked" on any $DOUBT.').encode()
BRIEF2 = ('Phase 2 phase-2-marker — commit the receipt.').encode()

SETTINGS = b'{"permissions": {"deny": ["Bash(rm:*)"]}}\n'

MANIFEST = """# STORY-0042: the two-phase walk
1 phase-1-build phase-1-artifact
2 phase-2-review receipt-complete
"""

PC_ARTIFACT = '#!/usr/bin/env bash\ntest -f "$1/artifact-1.txt"\n'
PC_RECEIPT = '#!/usr/bin/env bash\ntest -f "$1/chain/receipt.txt"\n'

# The injectable harness. It answers --version with the pinned shape, logs the composed
# environment facts the cases assert, then dispatches on the PROMPT ($2 of the composed argv):
# the brief bytes are the argv, so per-phase behavior is selected by the one instruction channel
# itself. Phase work runs in $PWD, the sequencer-owned worktree, whose shared clone config
# supplies the commit identity. Templated by .replace() because the JSON bodies carry braces.
STUB = """#!/usr/bin/env bash
if [ "${1:-}" = "--version" ]; then
  printf '%s\\n' "__VERSION__ (Claude Code)"
  exit 0
fi
printf 'argv %s\\n' "$*" >> "__LOG__"
printf 'HOME %s\\n' "$HOME" >> "__LOG__"
printf 'CWD %s\\n' "$PWD" >> "__LOG__"
printf 'CLAUDECODE %s\\n' "${CLAUDECODE:-unset}" >> "__LOG__"
printf 'SESSIONVAR %s\\n' "${CLAUDE_CODE_SESSION_ID:-unset}" >> "__LOG__"
printf 'PROBE %s\\n' "${ANTHROPIC_PROBE:-unset}" >> "__LOG__"
case "$2" in
  *phase-1-marker*)
    printf 'ran phase-1\\n' >> "__LOG__"
__P1__
    ;;
  *phase-2-marker*)
    printf 'ran phase-2\\n' >> "__LOG__"
__P2__
    ;;
  *)
    printf 'no phase marker in the prompt\\n' >&2
    exit 90
    ;;
esac
"""

RECORDS_OK = """printf '%s\\n' '{"type":"system","session_id":"__SESSION__"}'
printf '%s\\n' '{"type":"result","session_id":"__SESSION__"}'
exit 0"""

# Phase work writes content keyed on the invocation's own PID so a fresh attempt over an
# already-merged tree still has a change to commit.
P1_GOOD = """printf 'work %s\\n' "$$" > artifact-1.txt
git add artifact-1.txt
git commit -qm 'phase 1: the artifact'
""" + RECORDS_OK

P2_GOOD = """mkdir -p chain
printf 'receipt %s\\n' "$$" > chain/receipt.txt
git add chain/receipt.txt
git commit -qm 'phase 2: the receipt'
""" + RECORDS_OK

P1_WRONG = """printf 'work %s\\n' "$$" > wrong-artifact.txt
git add wrong-artifact.txt
git commit -qm 'phase 1: the wrong file'
""" + RECORDS_OK

P2_WRONG = """mkdir -p chain
printf 'wrong %s\\n' "$$" > chain/wrong.txt
git add chain/wrong.txt
git commit -qm 'phase 2: the wrong file'
""" + RECORDS_OK

# A death: an event and no record of the terminal kind, ADR-0001/D5's liveness in its negative
# form.
P2_DIES = """printf '%s\\n' '{"type":"system","session_id":"__SESSION__"}'
exit 1"""

# The probe-grounded spawn record (docs/probe/probe-stream.jsonl line 45) planted in an
# otherwise complete, honestly committed phase: the audit must flag it while the outcome stands.
P2_SPAWN = """mkdir -p chain
printf 'receipt %s\\n' "$$" > chain/receipt.txt
git add chain/receipt.txt
git commit -qm 'phase 2: the receipt'
printf '%s\\n' '{"type":"system","session_id":"__SESSION__"}'
printf '%s\\n' '{"type":"system","subtype":"task_started","task_id":"a9d2a96d253f531b5","subagent_type":"general-purpose"}'
printf '%s\\n' '{"type":"result","session_id":"__SESSION__"}'
exit 0"""

P1_NOOP = RECORDS_OK

# History rewritten sideways: the same tree wrapped in a parentless commit, checked out
# detached, so the seam reads clean and only the harvest's lineage check can refuse it.
P1_ORPHAN = """printf 'work %s\\n' "$$" > artifact-1.txt
git add artifact-1.txt
git commit -qm 'phase 1: the artifact'
oid=$(git commit-tree "$(git rev-parse 'HEAD^{tree}')" -m 'history rewritten sideways')
git checkout -q "$oid"
""" + RECORDS_OK

# A hostile phase minting the story branch mid-run: refs are shared across worktrees.
P1_MINTS = """junk=$(git commit-tree "$(git rev-parse 'HEAD^{tree}')" -m 'minted mid-run')
git update-ref refs/heads/story/__STORY__ "$junk"
printf 'work %s\\n' "$$" > artifact-1.txt
git add artifact-1.txt
git commit -qm 'phase 1: the artifact'
""" + RECORDS_OK


def clean_env() -> dict[str, str]:
    """The environment with git's own variables AND the driving session's `CLAUDE*` dropped.

    `GIT_*` because a pre-commit hook exports `GIT_DIR` and a subprocess inheriting it operates
    on the REAL repository. `CLAUDE*` because the decoy case asserts the sequencer's own scrub
    count, and a bench inheriting the driving session's variables would make that count depend
    on who runs the fixture.
    """
    return {k: v for k, v in os.environ.items()
            if not k.startswith("GIT_") and not k.startswith("CLAUDE")}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True, env=clean_env(),
    )
    return done.stdout.strip()


def ref_value(repo: Path, ref: str) -> str | None:
    done = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True, text=True, env=clean_env(),
    )
    return done.stdout.strip() or None


def is_ancestor(repo: Path, base: str, tip: str) -> bool:
    done = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", base, tip],
        capture_output=True, text=True, env=clean_env(),
    )
    return done.returncode == 0


def tree_has(repo: Path, ref: str, path: str) -> bool:
    done = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{ref}:{path}"],
        capture_output=True, text=True, env=clean_env(),
    )
    return done.returncode == 0


def symbolic_head(repo: Path) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "-q", "HEAD"],
        capture_output=True, text=True, env=clean_env(),
    )
    return done.stdout.strip()


def executable(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


def init_clone(path: Path, *, identity: bool = True, gpgsign: bool = False) -> Path:
    path.mkdir(parents=True)
    (path / "README.md").write_text("the judged tree\n")
    executable(path / "scripts" / "check.sh", "#!/usr/bin/env bash\nexit 0\n")
    git(path, "init", "-q", "-b", "main", ".")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "fixture")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "baseline")
    if gpgsign:
        git(path, "config", "commit.gpgsign", "true")
    if not identity:
        git(path, "config", "--unset", "user.name")
        git(path, "config", "--unset", "user.email")
    return path


def postcondition(root: Path, name: str, green_file: str, run_body: str) -> None:
    home = root / "postconditions" / name
    executable(home / "run", run_body)
    (home / "fixtures" / "red").mkdir(parents=True)
    (home / "fixtures" / "red" / "placeholder.txt").write_text("nothing demonstrable here\n")
    green = home / "fixtures" / "green" / green_file
    green.parent.mkdir(parents=True)
    green.write_text("present\n")


class Bench:
    """One throwaway world: a dedicated clone, a pinned root, a kit profile, a stub harness."""

    def __init__(self, td: Path, *, identity: bool = True, gpgsign: bool = False,
                 p1: str = P1_GOOD, p2: str = P2_GOOD,
                 manifest: str | None = MANIFEST):
        self.td = td
        self.clone = init_clone(td / "clone", identity=identity, gpgsign=gpgsign)
        self.base = ref_value(self.clone, "HEAD") or ""
        self.pinned = td / "pinned"
        (self.pinned / "briefs").mkdir(parents=True)
        (self.pinned / "briefs" / "phase-1-build").write_bytes(BRIEF1)
        (self.pinned / "briefs" / "phase-2-review").write_bytes(BRIEF2)
        (self.pinned / "settings").mkdir()
        (self.pinned / "settings" / "settings.json").write_bytes(SETTINGS)
        if manifest is not None:
            (self.pinned / "phases").mkdir()
            (self.pinned / "phases" / STORY).write_text(manifest)
        postcondition(self.pinned, "phase-1-artifact", "artifact-1.txt", PC_ARTIFACT)
        postcondition(self.pinned, "receipt-complete", "chain/receipt.txt", PC_RECEIPT)
        self.kit = td / "kit"
        chain = self.kit / ".claude" / "chain"
        chain.mkdir(parents=True)
        (chain / "profile.toml").write_text(
            PROFILE.replace("__PIN__", PIN).replace("__PINNED__", str(self.pinned)))
        self.log = td / "harness.log"
        self.harness = td / "claude-stub"
        self.stub(p1=p1, p2=p2)
        self.plan = td / "plan.txt"
        self.plan.write_text("artifact-1.txt\nchain/receipt.txt\n")

    def stub(self, *, p1: str, p2: str) -> None:
        """Write or rewrite the stub in place, which is how a re-run changes phase behavior."""
        body = (STUB.replace("__VERSION__", PIN).replace("__LOG__", str(self.log))
                    .replace("__P1__", p1).replace("__P2__", p2)
                    .replace("__SESSION__", SESSION).replace("__STORY__", STORY))
        executable(self.harness, body)

    def run(self, *extra: str, env: dict[str, str] | None = None
            ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SEQUENCER), "run", "--root", str(self.kit),
             "--repo", str(self.clone), "--story", STORY,
             "--commit-check", "scripts/check.sh", "--plan", str(self.plan),
             "--harness", str(self.harness), *extra],
            capture_output=True, text=True, env=clean_env() if env is None else env)

    def logged(self, marker: str) -> int:
        text = self.log.read_text() if self.log.is_file() else ""
        return text.count(marker)

    def phase_ref(self, attempt: int, phase: int) -> str | None:
        return ref_value(self.clone, f"refs/chain/{STORY}/attempt-{attempt}/phase-{phase}")

    def record(self, attempt: int) -> Path:
        return self.pinned / "records" / STORY / f"merge-{attempt}.record"

    def stream_dir(self, attempt: int) -> Path:
        return self.pinned / "streams" / STORY / f"attempt-{attempt}"


def judge(name: str, got: subprocess.CompletedProcess[str], *, want: int, marker: str,
          absent: str | tuple[str, ...] = (), present: tuple[str, ...] = (),
          faults: tuple[str, ...] = ()) -> bool:
    """Compare exit code, required markers, forbidden markers, and caller-established state.

    `faults` arrives already worded: whatever the caller measured on the filesystem, the refs
    or the record before judging. It lands here so the verdict line is the verdict rather than
    a first word a later complaint contradicts.
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
        print(f"       stdout: {got.stdout.strip()[:900]}")
        print(f"       stderr: {got.stderr.strip()[:600]}")
    return ok


def merged_faults(b: Bench, attempt: int) -> list[str]:
    """What a completed merge-local walk must have left behind, whatever else a case asserts."""
    faults = []
    candidate = b.phase_ref(attempt, 2)
    if b.phase_ref(attempt, 1) is None or candidate is None:
        faults.append(f"attempt-{attempt} phase refs were not recorded")
    main_now = ref_value(b.clone, "refs/heads/main")
    if main_now is None or main_now == b.base:
        faults.append("main did not advance")
    if candidate is not None and ref_value(b.clone, "refs/heads/main^2") != candidate:
        faults.append("the merge commit's second parent is not the candidate")
    record = b.record(attempt)
    if not record.is_file() or "merge_ok: true" not in record.read_text():
        faults.append(f"no composed record carrying merge_ok: true at {record}")
    return faults


def walk_replay_case() -> bool:
    """Criterion 1: one invocation, a two-phase story, everything real down to the record."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        got = b.run()
        faults = merged_faults(b, 1)
        p1 = b.phase_ref(1, 1)
        p2 = b.phase_ref(1, 2)
        if p1 is not None and p2 is not None:
            if ref_value(b.clone, f"{p2}^") != p1:
                faults.append("phase-2's parent is not the phase-1 sha")
            if ref_value(b.clone, f"refs/heads/story/{STORY}") != p2:
                faults.append("the story branch does not stand at the final phase ref")
        message = git(b.clone, "log", "-1", "--format=%B", "refs/heads/main")
        if f"Merged-Story: {STORY}" not in message:
            faults.append("the merge commit carries no Merged-Story trailer")
        for path in ("artifact-1.txt", "chain/receipt.txt"):
            if not tree_has(b.clone, "refs/heads/main", path):
                faults.append(f"the merged tree lacks {path}")
        if symbolic_head(b.clone) != f"refs/heads/story/{STORY}":
            faults.append("the clone is not left on the story branch")
        return judge("walk-replay-0", got, want=0,
                     marker="the whole story ran from one invocation",
                     present=("sequencer: harvest:", "act: merge-local"),
                     faults=tuple(faults))


def streams_composed_case() -> bool:
    """Finding 2 encoded: the audit's corpus exists by construction, under the pinned root."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        got = b.run()
        faults = []
        for n in (1, 2):
            if not (b.stream_dir(1) / f"p{n}.jsonl").is_file():
                faults.append(f"no composed stream p{n} under {b.stream_dir(1)}")
        return judge("streams-composed-0", got, want=0, marker="2 transcript(s) examined",
                     present=("transcript-audit: clean",), faults=tuple(faults))


def decoy_env_case() -> bool:
    """Finding 6: the CLAUDE-prefix scrub, with the false-drop guard on ANTHROPIC_*.

    CLAUDECODE carries no underscore, so a scrub keyed on CLAUDE_ misses it; ANTHROPIC_PROBE
    must SURVIVE, because that prefix is the auth channel and a scrub that eats it would break
    every live phase silently.
    """
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        env = clean_env()
        env["CLAUDECODE"] = "1"
        env["CLAUDE_CODE_SESSION_ID"] = "decoy-session"
        env["ANTHROPIC_PROBE"] = "1"
        got = b.run(env=env)
        faults = []
        if b.logged("CLAUDECODE unset") < 2:
            faults.append("the stub saw CLAUDECODE in some phase")
        if b.logged("CLAUDECODE 1") > 0:
            faults.append("CLAUDECODE reached a phase spawn")
        if b.logged("SESSIONVAR decoy-session") > 0:
            faults.append("CLAUDE_CODE_SESSION_ID reached a phase spawn")
        if b.logged("PROBE 1") < 2:
            faults.append("ANTHROPIC_PROBE was dropped: the scrub is too wide")
        return judge("decoy-env-0", got, want=0,
                     marker="scrubbed 2 session variable(s)",
                     present=("CLAUDECODE, CLAUDE_CODE_SESSION_ID",),
                     faults=tuple(faults))


def identity_unset_case() -> bool:
    """Finding 4: a clone without repo-local identity is refused before any spend."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), identity=False)
        got = b.run()
        faults = ("a phase was spawned before the identity gate",) if b.log.is_file() else ()
        return judge("identity-unset-2", got, want=2, marker="identity-unset",
                     present=("git config user.name", "git config user.email"),
                     faults=faults)


def gpgsign_local_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), gpgsign=True)
        got = b.run()
        faults = ("a phase was spawned before the identity gate",) if b.log.is_file() else ()
        return judge("gpgsign-local-2", got, want=2, marker="identity-signing", faults=faults)


def park_relay_case() -> bool:
    """Criterion 3: advance exit 1 parks the run — relayed, nothing later spawns or merges."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), p1=P1_WRONG)
        got = b.run()
        faults = []
        if b.logged("ran phase-1") != 1:
            faults.append(f"expected exactly one phase-1 spawn, saw {b.logged('ran phase-1')}")
        if b.logged("ran phase-2") != 0:
            faults.append("phase 2 was spawned after the park")
        if b.phase_ref(1, 1) is not None:
            faults.append("a phase-1 ref was written for a failed phase")
        if b.record(1).exists():
            faults.append("a merge record exists although no merge may be attempted")
        if ref_value(b.clone, "refs/heads/main") != b.base:
            faults.append("main moved on a parked story")
        return judge("park-relay-1", got, want=1, marker="the postcondition did not pass",
                     present=("sequencer: FAIL",), absent=("sequencer: merge|",),
                     faults=tuple(faults))


def audit_report_case() -> bool:
    """Criterion 4: the audit reports and never decides — the outcome stands, exit says looked."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), p2=P2_SPAWN)
        got = b.run()
        faults = merged_faults(b, 1)
        return judge("audit-report-2", got, want=2, marker="the terminal outcome stands",
                     present=("spawn-event", "task_started", "act: merge-local"),
                     faults=tuple(faults))


def did_nothing_case() -> bool:
    """The seam owns the verdict: a did-nothing phase harvests as a no-op and FAILs at advance."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), p1=P1_NOOP)
        got = b.run()
        faults = []
        if ref_value(b.clone, f"refs/heads/story/{STORY}") != b.base:
            faults.append("the no-op harvest did not anchor the branch at the base")
        if b.phase_ref(1, 1) is not None:
            faults.append("a phase-1 ref was written for a failed phase")
        return judge("did-nothing-phase-1", got, want=1,
                     marker="the postcondition did not pass",
                     present=("sequencer: harvest:",), faults=tuple(faults))


def phase_death_resume_case() -> bool:
    """Resume from position+1 within the derived attempt, with the dead stream renamed aside."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), p2=P2_DIES)
        first = b.run()
        p1sha = b.phase_ref(1, 1)
        faults = []
        if p1sha is None:
            faults.append("phase 1 did not record before the death")
        elif ref_value(b.clone, f"refs/heads/story/{STORY}") != p1sha:
            faults.append("the story branch is not at the phase-1 sha after the death")
        if not (b.stream_dir(1) / "p2.jsonl").is_file():
            faults.append("the dead phase left no composed stream")
        died = judge("phase-death-resume (death)", first, want=2, marker="phase-death",
                     faults=tuple(faults))

        b.stub(p1=P1_GOOD, p2=P2_GOOD)
        second = b.run()
        faults = merged_faults(b, 1)
        if b.logged("ran phase-1") != 1:
            faults.append("phase 1 was re-spawned on resume")
        if b.logged("ran phase-2") != 2:
            faults.append(f"expected two phase-2 spawns in all, saw {b.logged('ran phase-2')}")
        if not (b.stream_dir(1) / "p2.prior1.jsonl").is_file():
            faults.append("the dead phase's stream was not preserved aside")
        if not (b.stream_dir(1) / "p2.jsonl").is_file():
            faults.append("the re-run phase left no fresh stream")
        resumed = judge("phase-death-resume (resume)", second, want=0,
                        marker="resuming attempt 1", present=("renamed aside",),
                        faults=tuple(faults))
        return died and resumed


def rewalk_trio_case() -> bool:
    """Concluded attempts refuse to resume; a fresh attempt is explicit and reconciled."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        unearned = b.run("--fresh-attempt")
        r0 = judge("fresh-attempt-unearned-2", unearned, want=2,
                   marker="fresh-attempt-unearned",
                   faults=("a phase was spawned",) if b.log.is_file() else ())

        first = b.run()
        spawned = b.logged("ran phase-1")
        again = b.run()
        faults = []
        if first.returncode != 0:
            faults.append(f"the constructing walk exited {first.returncode}, not 0")
        if b.logged("ran phase-1") != spawned or b.logged("ran phase-2") != spawned:
            faults.append("a concluded attempt spawned a phase")
        r1 = judge("rerun-concluded-2", again, want=2, marker="attempt-concluded",
                   present=("merge-1.record", "--fresh-attempt"), faults=tuple(faults))

        third = b.run("--fresh-attempt")
        faults = merged_faults(b, 2)
        if not (b.stream_dir(2) / "p1.jsonl").is_file():
            faults.append("attempt 2 composed no streams of its own")
        r2 = judge("fresh-attempt-0", third, want=0, marker="deleting the branch",
                   present=("fresh attempt 2 of",), faults=tuple(faults))
        return r0 and r1 and r2


def park_rerun_reconcile_case() -> bool:
    """The fail-open closure: a parked phase's harvested commit never rides into the candidate."""
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), p2=P2_WRONG)
        first = b.run()
        p1sha = b.phase_ref(1, 1)
        failed = ref_value(b.clone, f"refs/heads/story/{STORY}")
        faults = []
        if failed is None or failed == p1sha:
            faults.append("the park did not leave a harvested-but-failed commit on the branch")
        parked = judge("park-then-rerun (park)", first, want=1,
                       marker="the postcondition did not pass", faults=tuple(faults))

        b.stub(p1=P1_GOOD, p2=P2_GOOD)
        second = b.run()
        faults = merged_faults(b, 1)
        candidate = b.phase_ref(1, 2)
        if failed is not None and f"discarded {failed}" not in second.stdout:
            faults.append("the reconcile did not list the discarded sha")
        if failed is not None and candidate is not None \
                and is_ancestor(b.clone, failed, candidate):
            faults.append("the rejected work rides inside the merged candidate")
        main_now = ref_value(b.clone, "refs/heads/main")
        if failed is not None and main_now is not None \
                and is_ancestor(b.clone, failed, main_now):
            faults.append("the rejected work reached main")
        healed = judge("park-then-rerun-reconcile-0", second, want=0,
                       marker="re-run fresh and never signed", faults=tuple(faults))
        return parked and healed


def table_case(name: str, manifest: str | None, *, marker: str,
               line: int | None = None) -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), manifest=manifest)
        got = b.run()
        faults = ("a phase was spawned on a zero-spend refusal",) if b.log.is_file() else ()
        present: tuple[str, ...] = ()
        if line is not None:
            present = (f"{b.pinned / 'phases' / STORY}:{line}",)
        elif manifest is None:
            present = (str(b.pinned / "phases" / STORY),)
        return judge(name, got, want=2, marker=marker, present=present, faults=faults)


def hostile_branch_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), p1=P1_MINTS)
        got = b.run()
        faults = []
        if b.phase_ref(1, 1) is not None:
            faults.append("a phase ref was recorded over a refused harvest")
        return judge("hostile-branch-moved-2", got, want=2, marker="harvest-refused",
                     present=("already exists",), faults=tuple(faults))


def story_branch_unrelated_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td))
        orphan = git(b.clone, "commit-tree", git(b.clone, "rev-parse", "HEAD^{tree}"),
                     "-m", "unrelated root")
        git(b.clone, "update-ref", f"refs/heads/story/{STORY}", orphan)
        got = b.run()
        faults = []
        if b.log.is_file():
            faults.append("a phase was spawned over an unaccountable branch")
        if ref_value(b.clone, f"refs/heads/story/{STORY}") != orphan:
            faults.append("the unrelated branch was deleted rather than refused")
        return judge("story-branch-unrelated-2", got, want=2,
                     marker="story-branch-unrelated", faults=tuple(faults))


def history_rewrite_case() -> bool:
    with tempfile.TemporaryDirectory() as td:
        b = Bench(Path(td), p1=P1_ORPHAN)
        got = b.run()
        faults = []
        if ref_value(b.clone, f"refs/heads/story/{STORY}") is not None:
            faults.append("something was anchored from a sideways history")
        return judge("hostile-history-rewrite-2", got, want=2, marker="harvest-diverged",
                     faults=tuple(faults))


def main() -> int:
    if not SEQUENCER.is_file():
        print(f"sequencer_test: tool not found at {SEQUENCER}", file=sys.stderr)
        return 2
    results = [
        walk_replay_case(),
        streams_composed_case(),

        decoy_env_case(),
        identity_unset_case(),
        gpgsign_local_case(),

        park_relay_case(),
        audit_report_case(),
        did_nothing_case(),

        phase_death_resume_case(),
        rewalk_trio_case(),
        park_rerun_reconcile_case(),

        table_case("table-absent-2", None, marker="phase-table-absent"),
        table_case("table-malformed-2", "1 phase-1-build\n",
                   marker="phase-table-malformed", line=1),
        table_case("table-gap-2",
                   "1 phase-1-build phase-1-artifact\n3 phase-2-review receipt-complete\n",
                   marker="phase-table-gap"),
        table_case("table-brief-missing-2",
                   "1 phase-9-nothing phase-1-artifact\n2 phase-2-review receipt-complete\n",
                   marker="brief-absent"),

        hostile_branch_case(),
        story_branch_unrelated_case(),
        history_rewrite_case(),
    ]
    failed = results.count(False)
    print(f"sequencer_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

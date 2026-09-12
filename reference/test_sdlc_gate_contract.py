#!/usr/bin/env python3
"""Tests for Checks E-H's CONTRACT in sdlc-gate.py — stdlib unittest, run: python3 <this file>.

These pin the engine half of the agent-smell checks, independently of any toolchain:
the NotWired coverage receipt, the did-not-run refusals, the four differentials, the
serializers, the -U0 diff parser, and the run_ruff fail-open that was fixed alongside.
Per-language runners have their own test file each (test_sdlc_gate_<lang>.py), so four
authors never edit one file.

Every guard here has a test that makes it FIRE, and a negative control beside it — a
guard that has never been seen to trip is decoration.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock as mock
from collections import Counter
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "sdlc_gate", str(Path(__file__).resolve().parent / "sdlc-gate.py")
)
assert _spec and _spec.loader
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


# --- A toolchain that implements E-H with canned results, for engine tests ------------------

class _Canned(gate.Toolchain):
    """Every check returns what the test told it to; `files` defaults to 1 so the engine's
    zero-files refusal stays out of the way unless a test wants it. Every call to a scanner that
    runs a tool (Check A, the compile precondition, E-H) is recorded in `calls` before it returns
    or raises, so a test that forbids a scan asserts `calls` is empty, and an engine that swallowed
    the scanner's exception still cannot hide the call."""
    name = "canned"

    def __init__(self, **scans):
        self._scans = scans
        self.calls: list[str] = []

    def detect(self, root):  # pragma: no cover - never auto-selected
        return False

    def static_analysis(self, root):
        self.calls.append("static_analysis")
        return {}

    def compile_check(self, root):
        self.calls.append("compile_check")
        return "skip"

    def _get(self, which):
        self.calls.append(which)
        v = self._scans.get(which)
        if v is None:
            raise gate.NotWired(f"{which}: not wired for canned")
        if isinstance(v, Exception):
            raise v
        return v

    def unreferenced(self, root):
        return self._get("unreferenced")

    def duplication(self, root):
        return self._get("duplication")

    def complexity(self, root):
        return self._get("complexity")

    def abstractions(self, root):
        return self._get("abstractions")


def _scan(findings: dict, files: int = 1, tool: str = "canned") -> "gate.Scan":
    return gate.Scan(tool=tool, files=files, findings=findings)


# --- The coverage receipt ------------------------------------------------------------------

class NotWiredIsReportedNotSkippedTests(unittest.TestCase):
    def test_base_toolchain_raises_notwired_for_all_four(self):
        tc = gate.Toolchain()
        for m in ("unreferenced", "duplication", "complexity", "abstractions"):
            with self.assertRaises(gate.NotWired, msg=m):
                getattr(tc, m)(Path("."))

    def test_capture_records_not_wired_rather_than_omitting_the_check(self):
        out = gate._capture_agent_scans(gate.Toolchain(), Path("."))
        self.assertEqual(set(out), {"E", "F", "G", "H"}, "every check appears, wired or not")
        for check in "EFGH":
            self.assertIn("not_wired", out[check])

    def test_capture_records_the_denominator_of_a_wired_check(self):
        tc = _Canned(complexity=_scan({("a.py", "f"): 3}, files=7))
        out = gate._capture_agent_scans(tc, Path("."))
        self.assertEqual(out["G"]["files"], 7)
        self.assertEqual(out["G"]["tool"], "canned")
        self.assertIn("not_wired", out["E"], "the unwired siblings are still listed")

    def test_diff_lists_not_wired_checks_in_the_report(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "agent-scans.json").write_text(json.dumps(
                {"E": {"not_wired": "unreferenced: not wired for canned"},
                 "G": {"tool": "canned", "files": 1, "findings": []}}))
            with mock.patch.object(gate, "_diff_added_lines", return_value={}):
                blocks, not_wired, scans = gate._run_agent_checks(
                    _Canned(complexity=_scan({})), Path("."), base, "deadbeef", {}, set())
        self.assertEqual(blocks, [])
        self.assertTrue(any(s.startswith("E:") for s in not_wired), not_wired)
        self.assertTrue(any(s.startswith("F:") for s in not_wired), "no baseline scan for F is reported")
        self.assertIn("G", scans)


# --- Did-not-run is never clean --------------------------------------------------------------

class DidNotRunRefusalsTests(unittest.TestCase):
    def _base_with(self, td: Path, check: str, findings=()):
        (td / "agent-scans.json").write_text(json.dumps(
            {check: {"tool": "canned", "files": 1, "findings": list(findings)}}))

    def test_zero_files_on_the_branch_exits_2(self):
        with tempfile.TemporaryDirectory() as td:
            self._base_with(Path(td), "G")
            tc = _Canned(complexity=_scan({}, files=0))
            with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
                gate._run_agent_checks(tc, Path("."), Path(td), "deadbeef", {}, set())
            self.assertEqual(cm.exception.code, 2)

    def test_scan_operational_error_exits_2(self):
        with tempfile.TemporaryDirectory() as td:
            self._base_with(Path(td), "G")
            tc = _Canned(complexity=gate.ScanOperationalError("tool exploded"))
            with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
                gate._run_agent_checks(tc, Path("."), Path(td), "deadbeef", {}, set())
            self.assertEqual(cm.exception.code, 2)

    def test_operational_error_at_capture_exits_2(self):
        tc = _Canned(unreferenced=gate.ScanOperationalError("no such tool"))
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            gate._capture_agent_scans(tc, Path("."))
        self.assertEqual(cm.exception.code, 2)

    def test_negative_control_a_clean_wired_check_passes(self):
        with tempfile.TemporaryDirectory() as td:
            self._base_with(Path(td), "G")
            tc = _Canned(complexity=_scan({}, files=3))
            with mock.patch.object(gate, "_diff_added_lines", return_value={}):
                blocks, not_wired, scans = gate._run_agent_checks(
                    tc, Path("."), Path(td), "deadbeef", {}, set())
        self.assertEqual(blocks, [])
        self.assertEqual(scans["G"]["files_branch"], 3)


# --- --no-static skips every tool-running scanner, E-H included, and says so ---------------------
# Until 2026-09-10 baseline and diff ran E-H under --no-static: a Python baseline with uvx off
# PATH exited 2 (measured), and a Scala one ran `sbt clean Test/compile`, the cost the flag exists
# to avoid.

def _all_four_clean() -> "_Canned":
    return _Canned(unreferenced=_scan({}), duplication=_scan({}), complexity=_scan({}),
                   abstractions=_scan({}))


def _run_baseline(tc: "_Canned", *, no_static: bool) -> tuple[int, dict, dict[str, str]]:
    """cmd_baseline against `tc`; returns (exit code, stdout JSON, {file name: text} written).
    The root is a plain temporary directory, so the check that it is a clean checkout of --sha is
    patched to accept it; BaselineShaTests runs that check on real repositories."""
    with tempfile.TemporaryDirectory() as td, mock.patch.dict(gate._TOOLCHAINS, {"canned": tc}), \
            mock.patch.object(gate, "_resolve_baseline_sha", side_effect=lambda root, sha: sha):
        out = Path(td) / "out"
        args = types.SimpleNamespace(sha="deadbeef", out=str(out), root=td, toolchain="canned",
                                     no_static=no_static, coverage=False)
        stdout = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            try:
                gate.cmd_baseline(args)
            except SystemExit as e:
                code = e.code or 0
        written = {p.name: p.read_text() for p in out.iterdir()} if out.exists() else {}
    body = stdout.getvalue().strip()
    return code, (json.loads(body) if body else {}), written


class NoStaticBaselineTests(unittest.TestCase):
    def test_no_static_baseline_calls_no_agent_scanner_and_records_the_skip(self):
        tc = _all_four_clean()
        code, report, written = _run_baseline(tc, no_static=True)
        self.assertEqual(code, 0)
        self.assertEqual(tc.calls, [], "no tool-running scanner may run under --no-static")
        self.assertEqual(json.loads(written["agent-scans.json"]),
                         {c: {"skipped": "--no-static"} for c in "EFGH"})
        self.assertEqual(written.get("no-static.txt"), "true\n")
        self.assertIs(report.get("no_static"), True)

    def test_no_static_baseline_exits_0_when_every_agent_tool_is_missing(self):
        """The measured repro: `baseline --no-static --toolchain python`, uvx off PATH, exited 2."""
        boom = gate.ScanOperationalError("uvx: command not found")
        tc = _Canned(unreferenced=boom, duplication=boom, complexity=boom, abstractions=boom)
        code, _, written = _run_baseline(tc, no_static=True)
        self.assertEqual(code, 0, "a tool --no-static does not run cannot fail the capture")
        self.assertEqual(tc.calls, [])
        self.assertIn("agent-scans.json", written)

    def test_negative_control_full_baseline_calls_every_agent_scanner(self):
        tc = _all_four_clean()
        code, report, written = _run_baseline(tc, no_static=False)
        self.assertEqual(code, 0)
        self.assertEqual(tc.calls, ["compile_check", "static_analysis",
                                    "unreferenced", "duplication", "complexity", "abstractions"])
        self.assertEqual(json.loads(written["agent-scans.json"])["G"]["files"], 1)
        self.assertEqual(written.get("no-static.txt"), "false\n",
                         "every baseline records its mode, so diff can refuse a mismatch")
        self.assertIs(report.get("no_static"), False)


class BaselineCapturedWithNoStaticTests(unittest.TestCase):
    """A skipped entry reaching a full diff. The mode check in cmd_diff refuses this whenever
    no-static.txt is present; this is the path for a baseline dir that lost it."""

    def test_skipped_entry_is_reported_and_its_scanner_not_called(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "agent-scans.json").write_text(json.dumps(
                {"E": {"skipped": "--no-static"}, "F": {"skipped": "--no-static"},
                 "G": {"tool": "canned", "files": 1, "findings": []},
                 "H": {"skipped": "--no-static"}}))
            tc = _all_four_clean()
            with mock.patch.object(gate, "_diff_added_lines", return_value={}):
                blocks, not_wired, scans = gate._run_agent_checks(
                    tc, Path("."), base, "deadbeef", {}, set())
        self.assertEqual(tc.calls, ["complexity"], "only the check the baseline scanned runs")
        self.assertEqual(not_wired, [f"{c}: baseline captured with --no-static; not compared"
                                     for c in "EFH"])
        self.assertEqual(list(scans), ["G"])
        self.assertEqual(blocks, [])


# --- Check G: complexity, delta-checked --------------------------------------------------------

class DiffComplexityTests(unittest.TestCase):
    def setUp(self):
        self._thr = gate.COMPLEXITY_THRESHOLD
        gate.COMPLEXITY_THRESHOLD = 15

    def tearDown(self):
        gate.COMPLEXITY_THRESHOLD = self._thr

    def test_new_function_over_threshold_blocks(self):
        b = gate._diff_complexity({("a.py", "f"): 20}, {}, {}, set(), {})
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0]["items"][0]["baseline"], None)

    def test_function_pushed_higher_blocks(self):
        b = gate._diff_complexity({("a.py", "f"): 21}, {("a.py", "f"): 20}, {}, set(), {})
        self.assertEqual(b[0]["items"][0]["branch"], 21)

    def test_complex_but_unchanged_does_not_block(self):
        """The Ousterhout constraint: a function that merely IS complex is not a finding."""
        b = gate._diff_complexity({("a.py", "f"): 40}, {("a.py", "f"): 40}, {}, set(), {})
        self.assertEqual(b, [])

    def test_complex_but_reduced_does_not_block(self):
        b = gate._diff_complexity({("a.py", "f"): 30}, {("a.py", "f"): 40}, {}, set(), {})
        self.assertEqual(b, [])

    def test_under_threshold_never_blocks_even_when_rising(self):
        b = gate._diff_complexity({("a.py", "f"): 14}, {("a.py", "f"): 3}, {}, set(), {})
        self.assertEqual(b, [])

    def test_rename_is_followed(self):
        """b.py was a.py at the baseline; the function's baseline value must be found there."""
        b = gate._diff_complexity({("b.py", "f"): 20}, {("a.py", "f"): 20}, {"a.py": "b.py"}, set(), {})
        self.assertEqual(b, [], "same value under a rename is not a rise")


# --- Check F: whole-tree duplication, attributed to added lines ----------------------------------

class DiffDuplicationTests(unittest.TestCase):
    def test_fingerprint_present_at_baseline_does_not_block(self):
        b = gate._diff_duplication({"fp1": [["a.py", 1, 5], ["b.py", 1, 5]]},
                                   {"fp1": [["a.py", 1, 5], ["b.py", 1, 5]]},
                                   {}, set(), {"a.py": {3}})
        self.assertEqual(b, [])

    def test_new_fingerprint_on_an_added_line_blocks(self):
        b = gate._diff_duplication({"fp2": [["a.py", 1, 5], ["c.py", 10, 14]]}, {},
                                   {}, set(), {"c.py": {12}})
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0]["items"][0]["fingerprint"], "fp2")

    def test_new_fingerprint_nowhere_near_the_diff_does_not_block(self):
        """A clone the branch did not write is not the branch's doing (e.g. a moved file)."""
        b = gate._diff_duplication({"fp2": [["a.py", 1, 5], ["c.py", 10, 14]]}, {},
                                   {}, set(), {"z.py": {1}})
        self.assertEqual(b, [])


# --- Check H: the inheritance-dedup refusal ----------------------------------------------------

class DiffAbstractionsTests(unittest.TestCase):
    def test_new_abstraction_with_one_implementor_blocks(self):
        b = gate._diff_abstractions({("a.py", "Base"): 1}, {}, {}, set(), {})
        self.assertEqual(b[0]["items"][0]["name"], "Base")

    def test_new_abstraction_with_zero_implementors_blocks(self):
        b = gate._diff_abstractions({("a.py", "Base"): 0}, {}, {}, set(), {})
        self.assertEqual(len(b), 1)

    def test_new_abstraction_with_two_implementors_passes(self):
        b = gate._diff_abstractions({("a.py", "Base"): 2}, {}, {}, set(), {})
        self.assertEqual(b, [])

    def test_pre_existing_single_implementor_abstraction_passes(self):
        """The gate judges what this change introduced, not what the tree already had."""
        b = gate._diff_abstractions({("a.py", "Base"): 1}, {("a.py", "Base"): 1}, {}, set(), {})
        self.assertEqual(b, [])


# --- Check E: unreferenced code, Check-A shaped ------------------------------------------------

class DiffUnreferencedTests(unittest.TestCase):
    def test_count_increase_blocks(self):
        b = gate._diff_unreferenced({("a.py", "ARG001"): 2}, {("a.py", "ARG001"): 1}, {}, set(), {})
        self.assertEqual(b[0]["items"][0]["new"], 1)

    def test_same_count_passes(self):
        b = gate._diff_unreferenced({("a.py", "ARG001"): 2}, {("a.py", "ARG001"): 2}, {}, set(), {})
        self.assertEqual(b, [])

    def test_decrease_passes(self):
        b = gate._diff_unreferenced({("a.py", "ARG001"): 1}, {("a.py", "ARG001"): 3}, {}, set(), {})
        self.assertEqual(b, [])


# --- Plumbing ----------------------------------------------------------------------------------

class SerializeRoundTripTests(unittest.TestCase):
    def test_tuple_and_string_keys_survive_json(self):
        findings = {("a.py", "f"): 3, "fp1": [["a.py", 1, 5]]}
        back = gate._deserialize_scan(json.loads(json.dumps(gate._serialize_scan(findings))))
        self.assertEqual(back[("a.py", "f")], 3)
        self.assertEqual(back["fp1"], [["a.py", 1, 5]])


class DiffAddedLinesTests(unittest.TestCase):
    def test_parses_u0_hunks_into_added_line_sets(self):
        fake = types.SimpleNamespace(returncode=0, stderr="", stdout=(
            "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
            "@@ -1,0 +2,3 @@\n+a\n+b\n+c\n"
            "@@ -10 +12 @@\n+d\n"
            "diff --git a/gone.py b/gone.py\n--- a/gone.py\n+++ /dev/null\n@@ -1,4 +0,0 @@\n"))
        # A stand-in index: every git call returns this patch, so a real one would read it as the
        # index path, find no file there, and refuse a missing index under a HEAD that names a commit.
        with mock.patch.object(gate.subprocess, "run", return_value=fake):
            added = gate._diff_added_lines("deadbeef", types.SimpleNamespace(env=dict))
        self.assertEqual(added["x.py"], {2, 3, 4, 12})
        self.assertNotIn("gone.py", added, "a deleted file adds no lines")

    def test_git_failure_is_operational_not_empty(self):
        fake = types.SimpleNamespace(returncode=128, stderr="fatal: bad object", stdout="")
        with mock.patch.object(gate.subprocess, "run", return_value=fake):
            with self.assertRaises(gate.ScanOperationalError):
                gate._diff_added_lines("nope")


# --- diff's two git reads: the root's path space, the working tree, untracked files ------------
# Measured 2026-09-10 on all four toolchains: a project in a subdirectory of its repository never
# blocked Check F, because git printed svc/src/x.py where every scanner keys src/x.py; the rename
# map read <sha>..HEAD, so a staged git mv made Check G block two unchanged functions; and a clone
# in a never-added file passed while `git add -N` on the same bytes blocked.

_GATE_PATH = Path(__file__).resolve().parent / "sdlc-gate.py"
_SEVEN = "".join(f"line {i} of a file long enough for git to pair its rename\n" for i in range(7))


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "commit.gpgsign=false", *args],
                          cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise AssertionError(f"setup: git {' '.join(args)} exited {proc.returncode}: {proc.stderr}")
    return proc.stdout


def _baseline_dir(d: Path, *, sha: str, toolchain: str, agent_scans: dict | None = None,
                  no_static: bool = False) -> Path:
    d.mkdir()
    (d / "sha.txt").write_text(sha + "\n")
    (d / "toolchain.txt").write_text(toolchain + "\n")
    (d / "suppressions.json").write_text("[]")
    (d / "test-weakening.json").write_text(json.dumps({"skips": {}, "asserts": {}, "params": {}}))
    (d / "build.txt").write_text("skip\n")
    (d / "no-static.txt").write_text(("true" if no_static else "false") + "\n")
    if agent_scans is not None:
        (d / "agent-scans.json").write_text(json.dumps(agent_scans))
    return d


class _RealRepoCase(unittest.TestCase):
    """A scratch directory for a real repository, the cwd restored after each test, and git's
    per-repository environment removed: scripts/check.sh runs from the pre-commit hook, where
    GIT_INDEX_FILE names this kit's own index."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.git_env_vars = subprocess.run(["git", "rev-parse", "--local-env-vars"], capture_output=True,
                                          text=True, check=True).stdout.split()

    def setUp(self) -> None:
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for name in self.git_env_vars:
            os.environ.pop(name, None)
        os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.scratch = Path(td.name).resolve()
        self.addCleanup(os.chdir, os.getcwd())

    def repo(self, files: dict[str, str]) -> tuple[Path, str]:
        """`files` committed in a new repository at scratch/repo; returns (top, that commit)."""
        return self.repo_at("repo", files)

    def repo_at(self, name: str, files: dict[str, str]) -> tuple[Path, str]:
        """`files` committed in a new repository at scratch/<name>; returns (top, that commit)."""
        top = self.scratch / name
        top.mkdir()
        _git(top, "init", "-q")
        for rel, text in files.items():
            (top / rel).parent.mkdir(parents=True, exist_ok=True)
            (top / rel).write_text(text)
        _git(top, "add", "-A")
        _git(top, "commit", "-qm", "baseline")
        return top, _git(top, "rev-parse", "HEAD").strip()


class DiffGitReadsTests(_RealRepoCase):
    def test_subdirectory_project_keys_from_its_root_and_excludes_changes_outside(self):
        top, sha = self.repo({"sub/x.py": "a\n", "sub/old.py": _SEVEN, "other/y.py": "o\n",
                              "other/z.py": _SEVEN, "other/gone.py": "g\n"})
        (top / "sub/x.py").write_text("a\nb\nc\n")
        (top / "other/y.py").write_text("o\np\n")
        _git(top, "mv", "sub/old.py", "sub/new.py")
        _git(top, "mv", "other/z.py", "other/z2.py")
        _git(top, "rm", "-q", "other/gone.py")
        _git(top, "commit", "-qam", "branch")
        os.chdir(top / "sub")
        self.assertEqual(gate._diff_added_lines(sha), {"x.py": {2, 3}})
        self.assertEqual(gate._git_rename_map(sha), ({"old.py": "new.py"}, set()))

    def test_staged_rename_is_in_the_rename_map(self):
        top, sha = self.repo({"pkg/tangle.py": _SEVEN, "pkg/drop.py": "d\n"})
        _git(top, "mv", "pkg/tangle.py", "pkg/knot.py")
        _git(top, "rm", "-q", "pkg/drop.py")
        os.chdir(top)
        self.assertEqual(gate._git_rename_map(sha), ({"pkg/tangle.py": "pkg/knot.py"}, {"pkg/drop.py"}))
        self.assertEqual(gate._diff_added_lines(sha), {}, "a pure rename adds no lines")

    def test_unstaged_plain_move_reads_as_a_rename(self):
        # Measured 2026-09-10: with the new path marked intent-to-add, git pairs it with the
        # deleted old path, so a plain `mv` translates the baseline like a `git mv` does.
        top, sha = self.repo({"pkg/tangle.py": _SEVEN})
        (top / "pkg/tangle.py").rename(top / "pkg/knot.py")
        os.chdir(top)
        self.assertEqual(gate._git_rename_map(sha), ({"pkg/tangle.py": "pkg/knot.py"}, set()))
        self.assertEqual(gate._diff_added_lines(sha), {})

    def test_untracked_file_counts_as_added_and_an_ignored_one_does_not(self):
        top, sha = self.repo({".gitignore": "ignored.py\n", "pkg/a.py": "a\n"})
        (top / "pkg/new.py").write_text("n1\nn2\nn3\n")
        (top / "ignored.py").write_text("i1\ni2\n")
        os.chdir(top)
        self.assertEqual(gate._diff_added_lines(sha), {"pkg/new.py": {1, 2, 3}})
        self.assertEqual(gate._git_rename_map(sha), ({}, set()))

    def test_untracked_names_git_would_refuse_still_read(self):
        top, sha = self.repo({"pkg/a.py": "a\n"})
        (top / ":odd.py").write_text("o\n")  # magic to git add unless literal; only at a path's start
        (top / "pkg/latin1.py").write_bytes(b"caf\xe9\nb\n")  # a strict UTF-8 decode raised on it
        nested = top / "vendor"
        nested.mkdir()
        _git(nested, "init", "-q")  # listed as vendor/, and git add refuses a repository with no commit
        (nested / "v.py").write_text("v\n")
        os.chdir(top)
        self.assertEqual(gate._diff_added_lines(sha), {":odd.py": {1}, "pkg/latin1.py": {1, 2}})
        self.assertEqual(gate._git_rename_map(sha), ({}, set()))

    def test_bogus_sha_raises_from_the_rename_map(self):
        top, _ = self.repo({"a.py": "a\n"})
        os.chdir(top)
        with self.assertRaises(gate.ScanOperationalError) as cm:
            gate._git_rename_map("deadbeef")
        self.assertIn("deadbeef", str(cm.exception), "git's own stderr says what it could not read")
        self.assertNotIn("\n", str(cm.exception))

    def test_git_missing_from_path_is_operational(self):
        top, sha = self.repo({"a.py": "a\n"})
        os.chdir(top)
        empty = self.scratch / "empty-path"
        empty.mkdir()
        os.environ["PATH"] = str(empty)
        for read in (gate._git_rename_map, gate._diff_added_lines):
            with self.subTest(read=read.__name__), self.assertRaises(gate.ScanOperationalError):
                read(sha)

    def test_bogus_sha_raises_from_added_lines(self):
        top, _ = self.repo({"a.py": "a\n"})
        os.chdir(top)
        with self.assertRaises(gate.ScanOperationalError) as cm:
            gate._diff_added_lines("deadbeef")
        self.assertIn("deadbeef", str(cm.exception))
        self.assertNotIn("\n", str(cm.exception))

    def test_the_real_index_is_never_written_and_the_copy_is_removed(self):
        top, sha = self.repo({"pkg/a.py": "a\n", "pkg/b.py": "b\n", "pkg/c.py": _SEVEN})
        (top / "pkg/a.py").write_text("a\nstaged\n")
        _git(top, "add", "pkg/a.py")
        (top / "pkg/b.py").write_text("b\nunstaged\n")
        _git(top, "mv", "pkg/c.py", "pkg/c2.py")
        (top / "pkg/new.py").write_text("n\n")
        os.chdir(top / "pkg")
        status, cached = _git(top, "status", "--porcelain"), _git(top, "diff", "--cached")
        index = (top / ".git" / "index").read_bytes()
        tmp = self.scratch / "tmp"
        tmp.mkdir()
        with mock.patch.object(tempfile, "tempdir", str(tmp)):
            renames = gate._git_rename_map(sha)
            added = gate._diff_added_lines(sha)
        self.assertEqual((top / ".git" / "index").read_bytes(), index)
        self.assertEqual(_git(top, "status", "--porcelain"), status)
        self.assertEqual(_git(top, "diff", "--cached"), cached)
        self.assertIn("?? pkg/new.py", status.splitlines())
        self.assertEqual(list(tmp.iterdir()), [], "the temporary index is deleted")
        self.assertEqual(renames, ({"c.py": "c2.py"}, set()))
        self.assertEqual(added, {"a.py": {2}, "b.py": {2}, "new.py": {1}})
        # Held open, as cmd_diff holds it: CPython's finalizer deletes an unreferenced temporary
        # directory anyway, so only a live object shows the deletion is the gate's own.
        index = (top / ".git" / "index").read_bytes()  # again: git status above may rewrite it
        with mock.patch.object(tempfile, "tempdir", str(tmp)):
            with gate._TreeIndex() as shared:
                self.assertEqual(gate._git_rename_map(sha, shared), renames)
                self.assertEqual(len(list(tmp.iterdir())), 1, "one temporary index while the diff runs")
            self.assertEqual(list(tmp.iterdir()), [], "deleted on exit while the object is still referenced")
        self.assertEqual((top / ".git" / "index").read_bytes(), index)

    def test_a_racily_clean_edit_counts_as_it_does_in_the_real_index(self):
        # git content-checks an entry whose mtime is not older than the index file's. Measured
        # 2026-09-10: a copy with a fresh mtime reads this same-size, same-mtime edit as clean,
        # where the real index and an mtime-preserving copy both report it.
        top, sha = self.repo({"f.py": "aaaa\n"})
        _git(top, "config", "core.checkStat", "minimal")
        _git(top, "config", "core.trustCtime", "false")
        stamp = 1577836800
        os.utime(top / "f.py", (stamp, stamp))
        _git(top, "add", "f.py")  # the index entry now records the stamp
        (top / "f.py").write_text("bbbb\n")
        os.utime(top / "f.py", (stamp, stamp))
        os.utime(top / ".git" / "index", (stamp, stamp))
        self.assertEqual(_git(top, "diff", "--name-status", sha), "M\tf.py\n", "setup: git sees the edit")
        os.chdir(top)
        self.assertEqual(gate._diff_added_lines(sha), {"f.py": {1}})

    def test_a_missing_index_with_no_commit_on_head_reads_the_working_tree(self):
        # An unborn branch whose index was never written: every file is untracked, and with each
        # marked intent-to-add in an empty copy the reads see the tree the scanners walk.
        top, sha = self.repo({"pkg/a.py": "a\n", "pkg/b.py": _SEVEN})
        _git(top, "checkout", "-q", "--orphan", "fresh")
        (top / ".git" / "index").unlink()
        (top / "pkg/a.py").write_text("a\nmore\n")
        (top / "pkg/c.py").write_text("new\n")
        os.chdir(top)
        self.assertEqual(gate._git_rename_map(sha), ({}, set()))
        self.assertEqual(gate._diff_added_lines(sha), {"pkg/a.py": {2}, "pkg/c.py": {1}})
        self.assertFalse((top / ".git" / "index").exists(), "no real index is created either")

    def test_a_missing_index_is_operational_when_head_names_a_commit(self):
        # git reads a missing index as an empty one and reports every tracked file deleted. With a
        # commit on HEAD that is not a repository that never added anything, and a copy that
        # started empty lost every sparse-checkout and submodule entry without a word.
        top, sha = self.repo({"pkg/a.py": "a\n"})
        (top / ".git" / "index").unlink()
        os.chdir(top)
        for read in (gate._git_rename_map, gate._diff_added_lines):
            with self.subTest(read=read.__name__):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    read(sha)
                self.assertIn("index", str(cm.exception))
                self.assertNotIn("\n", str(cm.exception))
        self.assertFalse((top / ".git" / "index").exists(), "no real index is created either")

    def test_a_sparse_checkout_reads_untracked_files_outside_the_cone(self):
        # Measured 2026-09-11 with git 2.43: git add --intent-to-add exits 1 on an untracked file
        # outside the sparse-checkout cone, so diff exited 2. A tracked file outside the cone is
        # skip-worktree and absent from the tree, and a copy that started empty read it as deleted.
        top, sha = self.repo({"in/a.py": "a\n", "out/o.py": "o\n"})
        _git(top, "sparse-checkout", "set", "in")
        self.assertFalse((top / "out/o.py").exists(), "setup: out/ is outside the cone")
        (top / "in/a.py").write_text("a\nb\n")
        (top / "out").mkdir(exist_ok=True)
        (top / "out/new.py").write_text("n\n")
        os.chdir(top)
        self.assertEqual(gate._git_rename_map(sha), ({}, set()))
        self.assertEqual(gate._diff_added_lines(sha), {"in/a.py": {2}, "out/new.py": {1}})

    def test_a_submodule_is_not_read_as_deleted(self):
        # A copy that started empty had no gitlink for lib, and ls-files lists a nested repository
        # as `lib/`, which is never marked, so the submodule read as deleted (measured 2026-09-11).
        top, _ = self.repo({"a.py": "a\n"})
        lib = top / "lib"
        lib.mkdir()
        _git(lib, "init", "-q")
        (lib / "l.py").write_text("l\n")
        _git(lib, "add", "-A")
        _git(lib, "commit", "-qm", "lib")
        _git(top, "-c", "advice.addEmbeddedRepo=false", "add", "lib")
        _git(top, "commit", "-qm", "a submodule")
        sha = _git(top, "rev-parse", "HEAD").strip()
        (top / "a.py").write_text("a\nb\n")
        (top / "new.py").write_text("n\n")
        os.chdir(top)
        self.assertEqual(gate._git_rename_map(sha), ({}, set()))
        self.assertEqual(gate._diff_added_lines(sha), {"a.py": {2}, "new.py": {1}})

    def test_a_split_index_leaves_the_git_directory_as_it_was(self):
        # Measured 2026-09-11 with git 2.43: under core.splitIndex=true the intent-to-add on the
        # temporary index wrote a new sharedindex file into the repository's .git and left it there.
        top, sha = self.repo({"pkg/a.py": "a\n", "pkg/b.py": "b\n"})
        _git(top, "config", "core.splitIndex", "true")
        _git(top, "update-index", "--split-index")
        (top / "pkg/a.py").write_text("a\nmore\n")
        (top / "pkg/new.py").write_text("n\n")
        before = sorted(p.name for p in (top / ".git").iterdir())
        self.assertTrue(any(n.startswith("sharedindex.") for n in before), "setup: a split index")
        os.chdir(top)
        self.assertEqual(gate._diff_added_lines(sha), {"pkg/a.py": {2}, "pkg/new.py": {1}})
        self.assertEqual(gate._git_rename_map(sha), ({}, set()))
        self.assertEqual(sorted(p.name for p in (top / ".git").iterdir()), before)

    def test_a_split_index_is_not_written_when_a_tracked_file_is_only_touched(self):
        # Measured 2026-09-11 with git 2.43: a tracked file with new stat data and the same content
        # (a touch, an editor save, a formatter), beside an edited file and an untracked one, made
        # the git diff over the temporary index refresh it and write it split, leaving a new
        # sharedindex file in the repository's .git. Only the intent-to-add carried
        # core.splitIndex=false, so the add was clean and the diff was not.
        top, sha = self.repo({"pkg/a.py": "a\n", "pkg/b.py": "b\n"})
        _git(top, "config", "core.splitIndex", "true")
        _git(top, "update-index", "--split-index")
        (top / "pkg/a.py").write_text("a\nmore\n")
        (top / "pkg/new.py").write_text("n\n")
        stat = (top / "pkg/b.py").stat()
        os.utime(top / "pkg/b.py", (stat.st_atime + 30, stat.st_mtime + 30))
        before = sorted(p.name for p in (top / ".git").iterdir())
        self.assertTrue(any(n.startswith("sharedindex.") for n in before), "setup: a split index")
        os.chdir(top)
        self.assertEqual(gate._diff_added_lines(sha), {"pkg/a.py": {2}, "pkg/new.py": {1}})
        self.assertEqual(gate._git_rename_map(sha), ({}, set()))
        self.assertEqual(sorted(p.name for p in (top / ".git").iterdir()), before)

    def test_the_waiver_read_ignores_user_diff_config_and_hook_variables(self):
        # _removed_assert_predicates ran a plain git diff: color.ui=always wrapped each removed line
        # in escape codes, so a correct migration waiver found no removed assertion and the
        # D.asserts loss stayed a block (measured 2026-09-11). It now reads like diff's other reads.
        top, sha = self.repo({"tests/test_x.py": "def test_f():\n    assert f(1) == 2\n    assert g()\n"})
        (top / "tests/test_x.py").write_text("def test_f():\n    assert g()\n")
        config = self.scratch / "gitconfig"
        config.write_text("[color]\n\tui = always\n[diff]\n\tnoprefix = true\n\tmnemonicPrefix = true\n")
        os.environ["GIT_CONFIG_GLOBAL"] = str(config)
        os.environ["GIT_INDEX_FILE"] = str(self.scratch / "no-such-index")
        self.assertIn("\x1b[", _git(top, "diff", sha), "setup: git reads the color config")
        os.chdir(top)
        self.assertEqual(gate._removed_assert_predicates(sha, "tests/test_x.py"), ["f(1) == 2"])

    def test_a_hook_environment_reads_as_a_plain_shell_does(self):
        # Measured 2026-09-11 with git 2.43: a pre-commit hook exports GIT_INDEX_FILE, `.git/index`
        # for a plain commit and an absolute index.lock for `commit -a`, and in a linked worktree
        # GIT_DIR as well. With GIT_DIR set and no GIT_WORK_TREE, git takes the cwd as the top of
        # the work tree: run from the project directory, the rename map paired every file with
        # itself under another prefix, so G and H blocked unchanged code. gen.py is tracked and
        # ignored, so only the checkout's own index says it is tracked.
        top, _ = self.repo({".gitignore": "gen.py\n", "README.md": "r\n", "sub/keep.py": "k\n",
                            "sub/old.py": _SEVEN})
        (top / "sub/gen.py").write_text("g\n")
        _git(top, "add", "-f", "sub/gen.py")
        _git(top, "commit", "-qm", "a tracked, ignored file")
        sha = _git(top, "rev-parse", "HEAD").strip()
        wt = self.scratch / "wt"
        _git(top, "worktree", "add", "-q", "--detach", str(wt), sha)
        for checkout in (top, wt):
            _git(checkout, "mv", "sub/old.py", "sub/new.py")
            (checkout / "sub/clone.py").write_text("c1\nc2\n")
            (checkout / "sub/gen.py").write_text("g\nh\n")
        other, _ = self.repo_at("other", {"x.py": "x\n"})
        wt_git_dir = _git(wt, "rev-parse", "--absolute-git-dir").strip()
        expected = (({"old.py": "new.py"}, set()), {"clone.py": {1, 2}, "gen.py": {2}})
        hooks = {
            "linked worktree, plain commit": (wt, {"GIT_DIR": wt_git_dir,
                                                   "GIT_INDEX_FILE": f"{wt_git_dir}/index"}),
            "linked worktree, commit -a": (wt, {"GIT_DIR": wt_git_dir,
                                                "GIT_INDEX_FILE": f"{wt_git_dir}/index.lock"}),
            "main worktree, plain commit": (top, {"GIT_INDEX_FILE": ".git/index"}),
            "main worktree, commit -a": (top, {"GIT_INDEX_FILE": str(top / ".git" / "index.lock")}),
            # As this kit's own pre-commit hook runs the suite: the index of another repository.
            "another repository's index": (wt, {"GIT_INDEX_FILE": str(other / ".git" / "index")}),
        }
        for label, (checkout, hook_env) in hooks.items():
            with self.subTest(label):
                os.chdir(checkout / "sub")
                self.assertEqual((gate._git_rename_map(sha), gate._diff_added_lines(sha)), expected,
                                 "setup: a plain shell")
                lock = hook_env["GIT_INDEX_FILE"]
                if lock.endswith(".lock"):  # git builds the index it commits there
                    shutil.copy2(Path(lock).with_suffix(""), lock)
                try:
                    with mock.patch.dict(os.environ, {**hook_env, "GIT_PREFIX": "sub/"}):
                        got = (gate._git_rename_map(sha), gate._diff_added_lines(sha))
                finally:
                    if lock.endswith(".lock"):
                        Path(lock).unlink()
                self.assertEqual(got, expected)

    def test_names_git_would_pad_or_quote_key_as_the_scanners_do(self):
        # Measured 2026-09-11 with git 2.43: a `+++ b/<name>` header ends in a TAB when the name
        # holds a space, and git C-quotes a name holding a double quote, a control character (\a,
        # \001) or a non-ASCII byte. Each came back as a key no scanner uses, so Check F never
        # attributed a clone in such a file.
        edited = ("my file.py", "café.py", 'say "hi".py', "tab\there.py", "bell\x07.py",
                  "ctl\x01.py", "nel\x85.py")
        top, sha = self.repo({**{name: "a\n" for name in edited}, "old name.py": _SEVEN,
                              "gone file.py": "g\n"})
        for name in edited:
            (top / name).write_text("a\nb\n")
        _git(top, "mv", "old name.py", "nëw name.py")
        _git(top, "rm", "-q", "gone file.py")
        os.chdir(top)
        self.assertEqual(gate._diff_added_lines(sha), {name: {2} for name in edited})
        self.assertEqual(gate._git_rename_map(sha),
                         ({"old name.py": "nëw name.py"}, {"gone file.py"}))

    def test_added_text_cannot_forge_a_file_header(self):
        # An added line whose text starts `++ ` prints as `+++ `, and str.splitlines broke a line at
        # U+2028, so text could also start a `diff --git` line. Either forged a header that hid the
        # file's later hunks from Check F, so a clone placed after one passed (measured 2026-09-11).
        base = [f"line {i}\n" for i in range(20)]
        top, sha = self.repo({"plus.py": "".join(base), "separator.py": "".join(base)})
        separator = chr(0x2028)
        forged = {"plus.py": "++ /dev/null\n", "separator.py": (
            f's = "{separator}diff --git a/s b/s{separator}+++ /dev/null{separator}"\n')}
        for name, first in forged.items():
            lines = [*base[:2], first, *base[2:14], "clone 1\n", "clone 2\n", *base[14:]]
            (top / name).write_text("".join(lines))
        os.chdir(top)
        self.assertEqual(gate._diff_added_lines(sha),
                         {"plus.py": {3, 16, 17}, "separator.py": {3, 16, 17}})

    def test_user_git_config_does_not_change_what_the_reads_see(self):
        # This suite runs with GIT_CONFIG_GLOBAL=/dev/null, so no test saw a user's config. Measured
        # 2026-09-11 with git 2.43: diff.noprefix drops the `b/` prefix (so b/x.py read as x.py),
        # diff.external replaces the patch, color.ui=always wraps each header in escape codes, and a
        # textconv driver shifts every line number.
        top, sha = self.repo({"b/x.py": "x\n", "pkg/a.py": "a\n", "pkg/old.py": _SEVEN})
        (top / "b/x.py").write_text("x\ny\n")
        (top / "pkg/a.py").write_text("a\nb\nc\n")
        _git(top, "mv", "pkg/old.py", "pkg/new.py")
        (top / "pkg/untracked.py").write_text("u\n")
        external = self.scratch / "external-diff"
        external.write_text("#!/bin/sh\necho an external diff ran\n")
        external.chmod(0o755)
        attributes = self.scratch / "attributes"
        attributes.write_text("*.py diff=dropfirst\n")
        config = self.scratch / "gitconfig"
        config.write_text("[diff]\n\tmnemonicPrefix = true\n\tnoprefix = true\n"
                          f"\texternal = {external}\n[color]\n\tui = always\n"
                          f"[core]\n\tattributesFile = {attributes}\n"
                          '[diff "dropfirst"]\n\ttextconv = sed 1d\n')
        os.environ["GIT_CONFIG_GLOBAL"] = str(config)
        self.assertIn("an external diff ran", _git(top, "diff", sha), "setup: git reads the config")
        os.chdir(top)
        self.assertEqual(gate._diff_added_lines(sha),
                         {"b/x.py": {2}, "pkg/a.py": {2, 3}, "pkg/untracked.py": {1}})
        self.assertEqual(gate._git_rename_map(sha), ({"pkg/old.py": "pkg/new.py"}, set()))

    def test_negative_control_committed_changes_at_the_top_read_as_before(self):
        top, sha = self.repo({"pkg/tangle.py": _SEVEN, "pkg/x.py": "a\n", "pkg/gone.py": "g\n"})
        (top / "pkg/x.py").write_text("a\nb\n")
        _git(top, "mv", "pkg/tangle.py", "pkg/knot.py")
        _git(top, "rm", "-q", "pkg/gone.py")
        _git(top, "commit", "-qam", "branch")
        os.chdir(top)
        self.assertEqual(gate._diff_added_lines(sha), {"pkg/x.py": {2}})
        self.assertEqual(gate._git_rename_map(sha), ({"pkg/tangle.py": "pkg/knot.py"}, {"pkg/gone.py"}))


class CmdDiffGitReadsTests(_RealRepoCase):
    """cmd_diff over a real repository with the canned toolchain, so no tool runs."""

    def _cmd_diff(self, base: Path, tc: "_Canned") -> tuple[int, str, str]:
        args = types.SimpleNamespace(baseline_dir=str(base), no_static=False, coverage=False,
                                     assertion_loss_waiver=None)
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.dict(gate._TOOLCHAINS, {"canned": tc}), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            try:
                gate.cmd_diff(args)
            except SystemExit as e:
                code = e.code or 0
        return code, out.getvalue(), err.getvalue()

    def test_subdirectory_clone_in_a_never_added_file_blocks_check_f(self):
        top, sha = self.repo({"README.md": "top\n", "sub/ledger.py": "l1\nl2\nl3\n"})
        (top / "sub/audit.py").write_text("l1\nl2\nl3\n")
        base = _baseline_dir(self.scratch / "base", sha=sha, toolchain="canned",
                             agent_scans={"F": {"tool": "canned", "files": 1, "findings": []}})
        os.chdir(top / "sub")
        clone = {"fp": [["audit.py", 1, 3], ["ledger.py", 1, 3]]}
        code, out, err = self._cmd_diff(base, _Canned(duplication=_scan(clone)))
        self.assertEqual(code, 1, err)
        self.assertEqual([b["check"] for b in json.loads(out)["blocks"]], ["F"])

    def test_one_temporary_index_serves_both_reads(self):
        top, sha = self.repo({"sub/ledger.py": "l1\n"})
        (top / "sub/audit.py").write_text("a1\n")
        base = _baseline_dir(self.scratch / "base", sha=sha, toolchain="canned",
                             agent_scans={"F": {"tool": "canned", "files": 1, "findings": []}})
        os.chdir(top / "sub")
        real_run, commands = subprocess.run, []

        def recording_run(cmd, *a, **kw):
            commands.append(list(cmd))
            return real_run(cmd, *a, **kw)

        with mock.patch.object(gate.subprocess, "run", side_effect=recording_run):
            code, _, err = self._cmd_diff(base, _Canned(duplication=_scan({})))
        self.assertEqual(code, 0, err)
        self.assertEqual(sum("ls-files" in c for c in commands), 1, commands)
        self.assertEqual(sum("diff" in c for c in commands), 2, commands)

    def test_the_temporary_index_is_built_on_first_use_only(self):
        # cmd_diff opens one for every diff; a test that stubs both reads must not run git in
        # whatever directory the suite happens to run from.
        with mock.patch.object(gate.subprocess, "run", side_effect=AssertionError("git ran")):
            with gate._TreeIndex():
                pass

    def test_bogus_sha_at_the_rename_map_exits_2_on_one_line(self):
        top, _ = self.repo({"a.py": "a\n"})
        base = _baseline_dir(self.scratch / "base", sha="deadbeef", toolchain="canned")
        os.chdir(top)
        tc = _all_four_clean()
        code, out, err = self._cmd_diff(base, tc)
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertIn("deadbeef", err)
        self.assertEqual(tc.calls, [], "no scanner runs on a tree whose renames could not be read")

    def test_bogus_sha_at_the_agent_checks_exits_2_on_one_line(self):
        # The rename map is stubbed, so the first git read to fail is Check E's added-lines read.
        top, _ = self.repo({"a.py": "a\n"})
        base = _baseline_dir(self.scratch / "base", sha="deadbeef", toolchain="canned",
                             agent_scans={c: {"tool": "canned", "files": 1, "findings": []} for c in "EFGH"})
        os.chdir(top)
        tc = _all_four_clean()
        with mock.patch.object(gate, "_git_rename_map", return_value=({}, set())):
            code, out, err = self._cmd_diff(base, tc)
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertIn("deadbeef", err)
        self.assertEqual(tc.calls[-1], "unreferenced", "E ran, then the read failed before F")

    def test_cli_exits_2_on_a_bogus_sha_without_a_traceback(self):
        top, _ = self.repo({"a.py": "a\n"})
        base = _baseline_dir(self.scratch / "base", sha="deadbeef", toolchain="python", no_static=True)
        proc = subprocess.run([sys.executable, str(_GATE_PATH), "diff", "--baseline-dir", str(base),
                               "--no-static"], cwd=top, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(len(proc.stderr.splitlines()), 1, proc.stderr)
        self.assertEqual(proc.stdout, "")


# --- baseline scans the tree at --root, so --root must be a clean checkout of --sha ----------------
# Measured 2026-09-10: the documented flow ran baseline in the branch checkout with --sha at the
# merge-base, so diff compared the branch with itself and passed A, E, F, G and H plants on
# TypeScript, Scala and Python, and `baseline --sha not-a-commit` exited 0 and recorded the string.

class BaselineShaTests(_RealRepoCase):
    """cmd_baseline over real repositories with the canned toolchain, so no tool runs."""

    def two_commits(self) -> tuple[Path, str, str]:
        """A repository at the second of two commits; returns (top, first commit, second commit)."""
        top, base = self.repo({"pkg/a.py": "a\n", "pkg/b.py": "b\n"})
        (top / "pkg/a.py").write_text("a\nbranch\n")
        _git(top, "commit", "-qam", "branch")
        return top, base, _git(top, "rev-parse", "HEAD").strip()

    def baseline(self, root: Path, sha: str, *, no_static: bool = False
                 ) -> tuple[int, dict, str, dict[str, str], "_Canned"]:
        """cmd_baseline at `root`, into a fresh --out; returns (exit code, stdout JSON, stderr,
        {file name: text} written or None when no --out directory exists, the toolchain whose calls
        show what was scanned)."""
        tc = _all_four_clean()
        out = Path(tempfile.mkdtemp(dir=self.scratch)) / "out"
        args = types.SimpleNamespace(sha=sha, out=str(out), root=str(root), toolchain="canned",
                                     no_static=no_static, coverage=False)
        stdout, stderr = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.dict(gate._TOOLCHAINS, {"canned": tc}), contextlib.redirect_stdout(stdout), \
                contextlib.redirect_stderr(stderr):
            try:
                gate.cmd_baseline(args)
            except SystemExit as e:
                code = e.code or 0
        written = {p.name: p.read_text() for p in out.iterdir()} if out.exists() else None
        body = stdout.getvalue().strip()
        return code, (json.loads(body) if body else {}), stderr.getvalue(), written, tc

    def assert_refused(self, result: tuple, *tokens: str) -> None:
        code, report, err, written, tc = result
        self.assertEqual(code, 2, err)
        self.assertEqual(report, {})
        self.assertIsNone(written, "no --out directory, so no file is written, sha.txt least of all")
        self.assertEqual(tc.calls, [], "no scanner runs")
        self.assert_one_line_then_shell(err)
        for token in tokens:
            self.assertIn(token, err)

    def assert_one_line_then_shell(self, err: str) -> None:
        """The prose is ONE line. Anything below it is the flow, between its two markers, and
        nothing else: a sentence loose under the first line is a sentence in a block a reader
        pastes into a shell, which is how the previous revision shipped a line that did not
        parse."""
        head, *rest = err.splitlines()
        self.assertTrue(head.startswith("sdlc-gate: baseline refused: "), err)
        if rest:
            self.assertEqual(rest[0], gate._RECIPE_START, err)
            self.assertEqual(rest[-1], gate._RECIPE_END, err)

    def test_head_other_than_sha_exits_2(self):
        # The old documented flow: in the branch checkout, --sha at the merge-base.
        top, base, tip = self.two_commits()
        for no_static in (False, True):
            with self.subTest(no_static=no_static):
                self.assert_refused(self.baseline(top, base, no_static=no_static),
                                    base, tip, "worktree")

    def test_sha_that_names_no_commit_exits_2(self):
        top, _ = self.repo({"pkg/a.py": "a\n"})
        blob = _git(top, "rev-parse", "HEAD:pkg/a.py").strip()
        for sha in ("not-a-commit", blob, "", "-q"):
            for no_static in (False, True):
                with self.subTest(sha=sha, no_static=no_static):
                    self.assert_refused(self.baseline(top, sha, no_static=no_static),
                                        "does not name a commit", sha)

    def test_root_outside_a_work_tree_exits_2(self):
        top, sha = self.repo({"pkg/a.py": "a\n"})
        plain = self.scratch / "plain"
        plain.mkdir()
        os.environ["GIT_CEILING_DIRECTORIES"] = str(self.scratch)  # no repository above the scratch
        for root in (plain, top / ".git", self.scratch / "missing"):
            with self.subTest(root=root.name):
                self.assert_refused(self.baseline(root, sha), "not inside a git work tree", str(root))

    def test_git_missing_from_path_exits_2(self):
        top, sha = self.repo({"pkg/a.py": "a\n"})
        empty = self.scratch / "empty-path"
        empty.mkdir()
        os.environ["PATH"] = str(empty)
        self.assert_refused(self.baseline(top, sha), "cannot run git")

    def test_tracked_change_under_root_exits_2(self):
        top, sha = self.repo({"pkg/a.py": "a\n", "pkg/b.py": "b\n"})
        changes = {
            "unstaged edit": lambda: (top / "pkg/a.py").write_text("a\nedited\n"),
            "staged edit": lambda: ((top / "pkg/a.py").write_text("a\nedited\n"), _git(top, "add", "-A")),
            "deleted file": lambda: (top / "pkg/b.py").unlink(),
        }
        for label, change in changes.items():
            for no_static in (False, True):
                with self.subTest(change=label, no_static=no_static):
                    change()
                    result = self.baseline(top, sha, no_static=no_static)
                    _git(top, "reset", "-q", "--hard")
                    self.assert_refused(result, "tracked change", "pkg/")

    def test_status_that_cannot_run_exits_2(self):
        # A corrupt index: rev-parse still reads HEAD, but status exits 128 and prints nothing,
        # which would read as no tracked changes.
        top, sha = self.repo({"pkg/a.py": "a\n"})
        (top / ".git" / "index").write_bytes(b"not an index")
        self.assert_refused(self.baseline(top, sha), "git status", "exited")

    def test_skip_worktree_or_assume_unchanged_under_root_exits_2(self):
        # git status does not look at a file marked skip-worktree or assume-unchanged, so an edit to
        # one was scanned and filed under --sha (measured 2026-09-11). ls-files -v tags the first S
        # and the second in lowercase.
        top, sha = self.repo({"svc/a.py": "a\n", "svc/b.py": "b\n", "docs/x.md": "x\n"})
        for flag in ("skip-worktree", "assume-unchanged"):
            for no_static in (False, True):
                with self.subTest(flag=flag, no_static=no_static):
                    _git(top, "update-index", f"--{flag}", "svc/a.py")
                    (top / "svc/a.py").write_text("a\nhidden edit\n")
                    self.assertEqual(_git(top, "status", "--porcelain"), "", "setup: status is blind")
                    at_top = self.baseline(top, sha, no_static=no_static)
                    at_svc = self.baseline(top / "svc", sha, no_static=no_static)
                    _git(top, "update-index", f"--no-{flag}", "svc/a.py")
                    _git(top, "checkout", "-q", "--", ".")
                    self.assert_refused(at_top, "svc/a.py", flag)
                    self.assert_refused(at_svc, "a.py", flag)
        with self.subTest("a flagged file outside a subdirectory root is not its tree"):
            _git(top, "update-index", "--skip-worktree", "docs/x.md")
            code, _, err, written, _ = self.baseline(top / "svc", sha)
            self.assertEqual(code, 0, err)
            self.assertEqual(written["sha.txt"], sha + "\n")

    def test_ls_files_that_cannot_run_exits_2(self):
        # A failed ls-files prints nothing, which would read as no flagged file. No real tree was
        # found where status passes and ls-files fails, so git's answer is stood in for.
        top, sha = self.repo({"pkg/a.py": "a\n"})
        real_run = subprocess.run

        def failing_ls_files(cmd, *args, **kwargs):
            if "ls-files" in cmd:
                return subprocess.CompletedProcess(cmd, 128, "", "fatal: index file corrupt\n")
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(gate.subprocess, "run", side_effect=failing_ls_files):
            result = self.baseline(top, sha)
        self.assert_refused(result, "git ls-files", "exited 128", "index file corrupt")

    # THE REFUSAL HAS TO CARRY THE FIX, not only the fault. These messages are read in a CI log
    # where the README is not at hand, and the corrected flow is not derivable from the rule they
    # state: a reader told "run it in a checkout of --sha with no tracked changes" still has to
    # invent the worktree recipe. Measured 2026-09-11: a consumer upgrading from v1.5.1, whose
    # documented flow ran baseline in the branch checkout, met these four refusals with no
    # instruction in them. Each case pins the actionable token rather than the sentence, so
    # rewording is free and deleting the fix is not.
    RECIPE = "git worktree add"
    # The pointer to the section carrying the full block. Mutating it to "" left the suite green
    # until this token was named here, so half of what the refusals gained was undefended.
    POINTER = ('"Using it"', "README")

    def test_head_other_than_sha_refusal_carries_the_worktree_recipe(self):
        top, base, _ = self.two_commits()
        self.assert_refused(self.baseline(top, base), self.RECIPE, "baseline --sha", *self.POINTER)

    def test_tracked_change_refusal_carries_the_worktree_recipe(self):
        top, sha = self.repo({"pkg/a.py": "a\n"})
        (top / "pkg/a.py").write_text("a\nedited\n")
        self.assert_refused(self.baseline(top, sha), self.RECIPE, "baseline --sha", *self.POINTER)

    def test_flagged_file_refusal_carries_the_flag_fix_and_the_worktree_recipe(self):
        # Clearing the flag is one fix and a fresh worktree is the other, since a new worktree has
        # its own index and inherits neither flag.
        top, sha = self.repo({"pkg/a.py": "a\n"})
        _git(top, "update-index", "--skip-worktree", "pkg/a.py")
        (top / "pkg/a.py").write_text("a\nhidden edit\n")
        result = self.baseline(top, sha)
        _git(top, "update-index", "--no-skip-worktree", "pkg/a.py")
        _git(top, "checkout", "-q", "--", ".")
        self.assert_refused(result, "--no-skip-worktree", "--no-assume-unchanged", self.RECIPE,
                            *self.POINTER)

    def test_root_outside_a_work_tree_names_the_fix_and_prints_no_flow(self):
        # THE ONE REFUSAL THAT PRINTS NO FLOW, and the only one where that is right: every command
        # in the flow is a git read of the repository at --root, and the fault is that there is no
        # repository at --root, so printing them would be printing commands that cannot run where
        # the reader is. It still has to name the fix in words and say where the block is.
        _, sha = self.repo({"pkg/a.py": "a\n"})
        plain = self.scratch / "plain"
        plain.mkdir()
        os.environ["GIT_CEILING_DIRECTORIES"] = str(self.scratch)  # no repository above the scratch
        result = self.baseline(plain, sha)
        self.assert_refused(result, "worktree at the merge-base", *self.POINTER)
        err = result[2]
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertNotIn(gate._RECIPE_START, err)

    def test_sha_that_names_no_commit_refusal_says_how_to_name_the_merge_base(self):
        # The one refusal whose --sha cannot be resolved, so the flow it prints computes the
        # merge-base rather than naming a commit.
        top, _ = self.repo({"pkg/a.py": "a\n"})
        self.assert_refused(self.baseline(top, "not-a-commit"), "git merge-base", self.RECIPE,
                            *self.POINTER)

    def test_untracked_and_ignored_files_are_allowed(self):
        # The documented flow links node_modules into the worktree, and uv creates .venv there.
        top, sha = self.repo({".gitignore": "node_modules\n", "pkg/a.py": "a\n"})
        (top / "pkg/new.py").write_text("n\n")
        deps = self.scratch / "deps"
        deps.mkdir()
        (top / "node_modules").symlink_to(deps)
        code, report, err, written, _ = self.baseline(top, sha)
        self.assertEqual(code, 0, err)
        self.assertEqual(written["sha.txt"], sha + "\n")

    def test_changes_outside_a_subdirectory_root_are_not_its_tree(self):
        top, sha = self.repo({"svc/a.py": "a\n", "docs/x.md": "x\n"})
        (top / "docs/x.md").write_text("edited\n")
        code, _, err, written, _ = self.baseline(top / "svc", sha)
        self.assertEqual(code, 0, err)
        self.assertEqual(written["sha.txt"], sha + "\n")
        (top / "svc/a.py").write_text("edited\n")
        self.assert_refused(self.baseline(top / "svc", sha), "svc/a.py")

    def test_records_the_full_commit_id_never_the_argument_as_typed(self):
        # HEAD or a short id read back later in the branch checkout would name another commit.
        top, _, tip = self.two_commits()
        _git(top, "tag", "-a", "-m", "annotated", "tip-tag")  # names a tag object, not the commit
        for typed in ("HEAD", tip[:7], "tip-tag", tip):
            with self.subTest(sha=typed):
                code, report, err, written, _ = self.baseline(top, typed)
                self.assertEqual(code, 0, err)
                self.assertEqual(written["sha.txt"], tip + "\n")
                self.assertEqual(report["sha"], tip)
                self.assertIn(f"sha={tip}", err)

    def test_negative_control_a_clean_worktree_at_sha_proceeds_from_any_cwd(self):
        top, base, _ = self.two_commits()
        wt = self.scratch / "wt"
        _git(top, "worktree", "add", "-q", "--detach", str(wt), base)
        os.chdir(top)  # the branch checkout, at the other commit: --root is what is checked
        full = ["compile_check", "static_analysis", "unreferenced", "duplication", "complexity",
                "abstractions"]
        for no_static in (False, True):
            with self.subTest(no_static=no_static):
                code, report, err, written, tc = self.baseline(wt, base, no_static=no_static)
                self.assertEqual(code, 0, err)
                self.assertEqual(written["sha.txt"], base + "\n")
                self.assertEqual(report["sha"], base)
                self.assertEqual(tc.calls, [] if no_static else full)

    def test_git_environment_naming_another_checkout_does_not_redirect_the_check(self):
        # Measured 2026-09-10: GIT_DIR and GIT_WORK_TREE, as a hook can set them, outrank -C, so
        # rev-parse read the other checkout's HEAD and status its tree; and a GIT_INDEX_FILE from
        # another checkout made a clean one read as changed.
        top, base, tip = self.two_commits()
        wt = self.scratch / "wt"
        _git(top, "worktree", "add", "-q", "--detach", str(wt), base)
        wt_git_dir = _git(wt, "rev-parse", "--absolute-git-dir").strip()
        with self.subTest("the branch checkout, with the environment of a worktree at --sha"):
            os.environ.update(GIT_DIR=wt_git_dir, GIT_WORK_TREE=str(wt))
            self.assert_refused(self.baseline(top, base), base, tip)
        for name in ("GIT_DIR", "GIT_WORK_TREE"):
            os.environ.pop(name, None)
        with self.subTest("a clean worktree at --sha, with the branch checkout's index"):
            os.environ["GIT_INDEX_FILE"] = str(top / ".git" / "index")
            code, _, err, written, _ = self.baseline(wt, base)
            self.assertEqual(code, 0, err)
            self.assertEqual(written["sha.txt"], base + "\n")


# The eight files a baseline writes. An --out that resolved to "." put them in the tree being
# scanned, so their absence from a project directory is what says the recipe passed a real one.
_BASELINE_FILES = frozenset({"agent-scans.json", "build.txt", "no-static.txt", "sha.txt",
                             "static-not-wired.json", "suppressions.json", "test-weakening.json",
                             "toolchain.txt"})

# The lines the printed flow and the README's block under "Using it" have in common. The README's
# is the full form (the golangci-lint caches, the node_modules link, the sparse-checkout case), so
# the two are not the same text and cannot be compared as one; these are the shell they share, and
# an edit to either that does not reach the other fails the case that reads them.
_SHARED_WITH_THE_README = (
    "unset $(git rev-parse --local-env-vars)",
    "P=$(git rev-parse --show-prefix)",
    "WT=$(mktemp -d); OUT=$(mktemp -d)",
    'git worktree add --quiet --detach "$WT" "$BASE"',
    '(cd "$WT/$P" || exit 2;',
    'baseline --sha "$BASE" --out "$OUT"',
    'diff --baseline-dir "$OUT"',
    "rc=$?",
    'git worktree remove --force "$WT"; rm -rf "$OUT"',
    '(exit "$rc")',
)


class BaselineRecipeRunsTests(_RealRepoCase):
    """THE FLOW A REFUSAL PRINTS IS EXTRACTED FROM THE GATE'S OWN STDERR AND EXECUTED HERE, the way
    a reader extracts it: the lines from one marker to the other.

    Token assertions are what let the previous revision ship a flow that does not run. Measured
    2026-09-11, pasting what it printed: `sdlc-gate.py` is on no PATH, so exit 127; `$OUT` was
    never set, so baseline resolved its output directory to "." and scattered the eight files into
    the tree it was scanning, reporting ok, and the failure surfaced only at the next command; the
    `$P` that carries a subdirectory project into the worktree was dropped, so baseline ran at the
    worktree top; the `unset` that makes the block work inside a pre-commit hook was dropped, so a
    hook died on `fatal: .git/index`; no `git worktree remove`, so a worktree stayed registered;
    and pasted whole it did not parse at all. A case that runs it catches every one of those. That
    the previous round pinned `git worktree add` and shipped exit 127 is the reason this file now
    executes rather than greps.

    The cases pass --no-static, so the flow needs python3 and git and no other tool; the printed
    flow carries the flag because _same_mode_flags reads it off the invocation's own argv, and a
    flow that dropped it would hand a caller in that mode a recipe that exits 2 on a missing uv."""

    def python_repo(self, prefix: str = "") -> tuple[Path, Path, str]:
        """A python project at `prefix` in a repository whose branch tip is one commit past its
        merge-base; returns (repository top, project directory, the merge-base commit). With a
        prefix, the marker file is only in the project directory, so a flow that lost $P and ran at
        the worktree top detects no toolchain and exits 2 rather than passing quietly."""
        files = {f"{prefix}pyproject.toml": "[project]\nname = 'x'\nversion = '0.1'\n",
                 f"{prefix}pkg/a.py": "def a(x):\n    return x\n"}
        if prefix:
            files["docs/notes.md"] = "outside the project\n"
        top, base = self.repo(files)
        (top / f"{prefix}pkg/b.py").write_text("def b(y):\n    return y\n")
        _git(top, "add", "-A")
        _git(top, "commit", "-qm", "branch")
        return top, (top / prefix) if prefix else top, base

    def refusal(self, project: Path, sha: str) -> str:
        """The gate's stderr from a real refusal, run as a caller runs it."""
        out = self.scratch / "never-written"
        proc = subprocess.run([sys.executable, str(_GATE_PATH), "baseline", "--no-static",
                               "--sha", sha, "--out", str(out)],
                              cwd=project, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertFalse(out.exists(), "refused before --out is made")
        return proc.stderr

    def recipe_from(self, err: str) -> str:
        """What a reader copies: the lines from one marker to the other, inclusive. It has to parse
        as it stands, markers included, since a reader who copies them too is the common case."""
        lines = err.splitlines()
        self.assertIn(gate._RECIPE_START, lines, err)
        self.assertIn(gate._RECIPE_END, lines, err)
        block = "\n".join(lines[lines.index(gate._RECIPE_START):
                                 lines.index(gate._RECIPE_END) + 1]) + "\n"
        script = self.scratch / "recipe.sh"
        script.write_text(block)
        parsed = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True,
                                check=False)
        self.assertEqual(parsed.returncode, 0, f"{parsed.stderr}\n{block}")
        return block

    def run_recipe(self, cwd: Path, block: str) -> subprocess.CompletedProcess:
        script = self.scratch / "run-recipe.sh"
        script.write_text(block)
        return subprocess.run(["bash", str(script)], cwd=cwd, capture_output=True, text=True,
                              check=False)

    def test_the_printed_flow_runs_verbatim_and_files_the_merge_base(self):
        top, project, base = self.python_repo()
        tip = _git(top, "rev-parse", "HEAD").strip()
        proc = self.run_recipe(project, self.recipe_from(self.refusal(project, base)))
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")
        report = json.loads(proc.stdout)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["baseline_sha"], base)  # the merge-base, never the branch's own tree
        self.assertIn(f"(sha={base})", proc.stderr)
        self.assertNotIn(tip, proc.stderr)
        self.assertEqual(sorted(p.name for p in project.iterdir() if p.name in _BASELINE_FILES), [])
        self.assertEqual(len(_git(top, "worktree", "list").splitlines()), 1,
                         "the flow leaves no worktree registered")

    def test_the_printed_flow_runs_verbatim_for_a_project_in_a_subdirectory(self):
        top, project, base = self.python_repo("proj/")
        proc = self.run_recipe(project, self.recipe_from(self.refusal(project, base)))
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")
        report = json.loads(proc.stdout)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["baseline_sha"], base)
        self.assertEqual(sorted(p.name for p in project.iterdir() if p.name in _BASELINE_FILES), [])
        self.assertEqual(len(_git(top, "worktree", "list").splitlines()), 1)

    def test_the_printed_flow_runs_verbatim_as_a_pre_commit_hook(self):
        # git exports GIT_INDEX_FILE to a pre-commit hook, and the first line of the flow is what
        # clears it. Without that line the hook's own `git worktree add` writes the merge-base tree
        # into the index the commit is about to write: fatal: .git/index (measured).
        top, project, base = self.python_repo()
        block = self.recipe_from(self.refusal(project, base))
        hook = Path(_git(top, "rev-parse", "--absolute-git-dir").strip()) / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/usr/bin/env bash\n" + block)
        hook.chmod(0o755)
        (top / "pkg/c.py").write_text("def c(z):\n    return z\n")
        _git(top, "add", "-A")
        proc = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                               "-c", "commit.gpgsign=false", "commit", "-m", "hooked"],
                              cwd=top, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")
        self.assertNotIn("fatal:", proc.stderr)
        self.assertEqual(_git(top, "log", "--format=%s", "-1").strip(), "hooked")
        self.assertEqual(_git(top, "status", "--porcelain").strip(), "")
        self.assertEqual(len(_git(top, "worktree", "list").splitlines()), 1)

    def test_every_refusal_that_prints_a_flow_prints_one_that_parses_and_names_a_real_gate(self):
        top, project, base = self.python_repo()
        tip = _git(top, "rev-parse", "HEAD").strip()

        def tracked_change() -> None:
            (project / "pkg/a.py").write_text("def a(x):\n    return x + 1\n")

        def flagged_file() -> None:
            _git(top, "update-index", "--skip-worktree", "pkg/a.py")
            (project / "pkg/a.py").write_text("def a(x):\n    return x + 2\n")

        for label, prepare, sha in (("head elsewhere", None, base),
                                    ("no such commit", None, "not-a-commit"),
                                    ("tracked change", tracked_change, tip),
                                    ("flagged file", flagged_file, tip)):
            with self.subTest(label):
                if prepare is not None:
                    prepare()
                block = self.recipe_from(self.refusal(project, sha))
                if prepare is flagged_file:
                    _git(top, "update-index", "--no-skip-worktree", "pkg/a.py")
                _git(top, "checkout", "-q", "--", ".")
                # The gate names itself by its own path, because nothing puts it on PATH and the
                # installed copy and a checkout copy sit at different ones.
                self.assertIn(str(_GATE_PATH), block)
                self.assertTrue(_GATE_PATH.exists())
                self.assertIn("--no-static", block.split("baseline --sha")[1])
                for fragment in _SHARED_WITH_THE_README:
                    self.assertIn(fragment, block, label)

    def test_the_printed_flow_and_the_readme_block_do_not_drift(self):
        readme = _GATE_PATH.parent.parent / "README.md"
        self.assertTrue(readme.exists(), f"run this from the kit checkout; no README at {readme}")
        text = readme.read_text()
        _, project, base = self.python_repo()
        block = self.recipe_from(self.refusal(project, base))
        for fragment in _SHARED_WITH_THE_README:
            self.assertIn(fragment, block, "the printed flow lost a line the README block has")
            self.assertIn(fragment, text, "the README block lost a line the printed flow has")


class BaselineEmptyOutTests(_RealRepoCase):
    """`--out ""` is what an unset shell variable expands to, and it is what the flow the previous
    revision printed passed. Path("") is Path("."), so baseline wrote its eight files into the tree
    it was scanning and answered {"ok": true} at exit 0 (measured 2026-09-11). Where that surfaced
    depended on where the next command stood: in the documented flow the baseline runs inside the
    worktree, so diff back in the branch checkout died on FileNotFoundError: 'sha.txt' at exit 1,
    and run in one directory diff read the scattered files as its baseline and returned a verdict at
    exit 0 on the branch compared with itself."""

    def project(self) -> tuple[Path, str]:
        return self.repo({"pyproject.toml": "[project]\nname = 'x'\n", "pkg/a.py": "a = 1\n"})

    def baseline_cli(self, top: Path, out: str) -> subprocess.CompletedProcess:
        sha = _git(top, "rev-parse", "HEAD").strip()
        return subprocess.run([sys.executable, str(_GATE_PATH), "baseline", "--no-static",
                               "--sha", sha, "--out", out],
                              cwd=top, capture_output=True, text=True, check=False)

    def test_an_empty_out_is_refused_and_nothing_is_written(self):
        top, _ = self.project()
        before = sorted(p.name for p in top.iterdir())
        for out in ("", "   "):
            with self.subTest(out=repr(out)):
                proc = self.baseline_cli(top, out)
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertEqual(proc.stdout, "", "never {'ok': true} for a baseline not filed")
                self.assertEqual(len(proc.stderr.splitlines()), 1, proc.stderr)
                for token in ("--out is empty", "OUT=$(mktemp -d)", '"Using it"', "README"):
                    self.assertIn(token, proc.stderr)
                self.assertEqual(sorted(p.name for p in top.iterdir()), before)

    def test_negative_control_a_real_out_captures_the_baseline(self):
        top, sha = self.project()
        out = self.scratch / "out"
        proc = self.baseline_cli(top, str(out))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((out / "sha.txt").read_text().strip(), sha)
        self.assertEqual(json.loads(proc.stdout)["ok"], True)


class RunRuffFailClosedTests(unittest.TestCase):
    """The fix that rode along: a ruff that did not run must not read as 'no findings'."""

    def test_non_json_output_raises(self):
        fake = types.SimpleNamespace(returncode=1, stderr="", stdout="not json at all")
        with mock.patch.object(gate.subprocess, "run", return_value=fake):
            with self.assertRaises(gate.ScanOperationalError):
                gate.run_ruff(Path("."))

    def test_exit_2_raises(self):
        fake = types.SimpleNamespace(returncode=2, stderr="error: unknown flag", stdout="")
        with mock.patch.object(gate.subprocess, "run", return_value=fake):
            with self.assertRaises(gate.ScanOperationalError):
                gate.run_ruff(Path("."))

    def test_missing_binary_exit_code_raises(self):
        fake = types.SimpleNamespace(returncode=127, stderr="uv: command not found", stdout="")
        with mock.patch.object(gate.subprocess, "run", return_value=fake):
            with self.assertRaises(gate.ScanOperationalError):
                gate.run_ruff(Path("."))

    def test_negative_control_clean_run_is_empty_counter(self):
        fake = types.SimpleNamespace(returncode=0, stderr="", stdout="")
        with mock.patch.object(gate.subprocess, "run", return_value=fake):
            self.assertEqual(gate.run_ruff(Path(".")), Counter())

    def test_negative_control_findings_are_counted(self):
        body = json.dumps([{"filename": str(Path(".").resolve() / "a.py"), "code": "ARG001"}])
        fake = types.SimpleNamespace(returncode=1, stderr="", stdout=body)
        with mock.patch.object(gate.subprocess, "run", return_value=fake):
            c = gate.run_ruff(Path(".").resolve())
        self.assertEqual(sum(c.values()), 1)


class StaticAnalysisThatCannotRunTests(_RealRepoCase):
    """run_ruff raised ScanOperationalError, but baseline and diff called static_analysis outside any
    handler. Measured 2026-09-10: a ruff that could not run exited 1 with a traceback."""

    def env_with_a_broken_uv(self) -> dict[str, str]:
        bin_dir = self.scratch / "bin"
        bin_dir.mkdir()
        uv = bin_dir / "uv"
        uv.write_text("#!/bin/sh\necho 'error: Failed to spawn: `ruff`' >&2\nexit 2\n")
        uv.chmod(0o755)
        return {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    def gate_cli(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(_GATE_PATH), *args], cwd=cwd, capture_output=True,
                              text=True, check=False, env=self.env_with_a_broken_uv())

    def test_baseline_exits_2_on_one_line_without_a_traceback(self):
        top, sha = self.repo({"pyproject.toml": "[project]\nname = 'x'\n", "pkg/a.py": "a = 1\n"})
        proc = self.gate_cli(top, "baseline", "--sha", sha, "--out", str(self.scratch / "base"))
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        lines = proc.stderr.splitlines()
        self.assertEqual(len(lines), 2, proc.stderr)  # the capture banner, then the refusal
        self.assertIn("ruff exited 2", lines[1])
        self.assertEqual(proc.stdout, "")

    def test_diff_exits_2_on_one_line_without_a_traceback(self):
        top, sha = self.repo({"pyproject.toml": "[project]\nname = 'x'\n", "pkg/a.py": "a = 1\n"})
        base = _baseline_dir(self.scratch / "base", sha=sha, toolchain="python")
        proc = self.gate_cli(top, "diff", "--baseline-dir", str(base))
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(len(proc.stderr.splitlines()), 1, proc.stderr)
        self.assertIn("ruff exited 2", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_uv_missing_from_path_exits_2_at_baseline_and_diff(self):
        # Measured 2026-09-11: with no uv on PATH the spawn raised FileNotFoundError, and the gate
        # exited 1 with a traceback, which the documented block reads as blocked.
        top, sha = self.repo({"pyproject.toml": "[project]\nname = 'x'\n", "pkg/a.py": "a = 1\n"})
        git_only = self.scratch / "git-only"
        git_only.mkdir()
        (git_only / "git").symlink_to(shutil.which("git"))
        env = {**os.environ, "PATH": str(git_only)}

        def gate_cli(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([sys.executable, str(_GATE_PATH), *args], cwd=top,
                                  capture_output=True, text=True, check=False, env=env)

        base = _baseline_dir(self.scratch / "base", sha=sha, toolchain="python")
        for label, args, banner in (
                ("baseline", ("baseline", "--sha", sha, "--out", str(self.scratch / "out")), 1),
                ("diff", ("diff", "--baseline-dir", str(base)), 0)):
            with self.subTest(label):
                proc = gate_cli(*args)
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)
                lines = proc.stderr.splitlines()
                self.assertEqual(len(lines), banner + 1, proc.stderr)
                self.assertIn("'uv'", lines[-1])
                self.assertEqual(proc.stdout, "")


class PythonCheckAToolNotOnPathTests(unittest.TestCase):
    """run_ruff, run_mypy and run_bandit spawn uv or uvx, and a spawn that failed raised
    FileNotFoundError out of them: exit 1 with a traceback (measured 2026-09-11)."""

    def test_each_runner_raises_scan_operational_error(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, {"PATH": td}):
            for runner in (gate.run_ruff, gate.run_mypy, gate.run_bandit):
                with self.subTest(runner=runner.__name__):
                    with self.assertRaises(gate.ScanOperationalError) as cm:
                        runner(Path(td))
                    self.assertIn("uv", str(cm.exception))


class MypyIsStrictTests(unittest.TestCase):
    def test_the_invocation_carries_strict(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
            gate.run_mypy(Path("."))
        self.assertIn("--strict", seen["cmd"], "hallucinated APIs survive to review in Python "
                      "unless mypy runs strict; the other three toolchains get this from the compiler")


class PythonCheckAScannersRunAtRootTests(unittest.TestCase):
    """run_ruff, run_mypy and run_bandit ran in the process cwd rather than at `root`. Measured
    2026-09-10: a --root baseline taken from the branch checkout dropped an A.mypy block and
    demoted A.ruff to an advisory."""

    def setUp(self) -> None:
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve() / "project"
        (self.root / "pkg").mkdir(parents=True)
        self.elsewhere = Path(td.name).resolve() / "elsewhere"
        self.elsewhere.mkdir()
        self.addCleanup(os.chdir, os.getcwd())

    def scan(self) -> tuple[list, dict[str, Counter]]:
        """All three scanners at self.root with the tools faked in their measured path shapes:
        ruff prints absolute paths, mypy root-relative ones, bandit `./`-prefixed ones."""
        cwds: list = []
        abs_file = str(self.root / "pkg" / "x.py")

        def fake_run(cmd, **kw):
            cwds.append(kw.get("cwd"))
            if "ruff" in cmd:
                body = json.dumps([{"filename": abs_file, "code": "F401"}])
                return types.SimpleNamespace(returncode=1, stdout=body, stderr="")
            if "mypy" in cmd:
                return types.SimpleNamespace(returncode=1, stderr="", stdout=(
                    "pkg/x.py:3: error: Function is missing a type annotation  [no-untyped-def]\n"))
            Path(cmd[cmd.index("-o") + 1]).write_text(
                json.dumps({"results": [{"filename": "./pkg/x.py", "test_id": "B101"}]}))
            return types.SimpleNamespace(returncode=1, stdout="", stderr="")

        with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
            counts = {"ruff": gate.run_ruff(self.root), "mypy": gate.run_mypy(self.root),
                      "bandit": gate.run_bandit(self.root)}
        return cwds, counts

    def test_each_scanner_runs_at_root(self):
        os.chdir(self.elsewhere)
        cwds, _ = self.scan()
        self.assertEqual(len(cwds), 3)
        self.assertEqual([None if c is None else Path(c) for c in cwds], [self.root] * 3)

    def test_findings_key_from_root_wherever_the_process_runs(self):
        for cwd in (self.elsewhere, self.root, self.root / "pkg"):
            with self.subTest(cwd=cwd.name):
                os.chdir(cwd)
                _, counts = self.scan()
                self.assertEqual(counts, {"ruff": Counter({("pkg/x.py", "F401"): 1}),
                                          "mypy": Counter({("pkg/x.py", "no-untyped-def"): 1}),
                                          "bandit": Counter({("pkg/x.py", "B101"): 1})})


if __name__ == "__main__":
    unittest.main()

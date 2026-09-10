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
import subprocess
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
    zero-files refusal stays out of the way unless a test wants it."""
    name = "canned"

    def __init__(self, **scans):
        self._scans = scans

    def detect(self, root):  # pragma: no cover - never auto-selected
        return False

    def _get(self, which):
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
        with mock.patch.object(gate.subprocess, "run", return_value=fake):
            added = gate._diff_added_lines("deadbeef")
        self.assertEqual(added["x.py"], {2, 3, 4, 12})
        self.assertNotIn("gone.py", added, "a deleted file adds no lines")

    def test_git_failure_is_operational_not_empty(self):
        fake = types.SimpleNamespace(returncode=128, stderr="fatal: bad object", stdout="")
        with mock.patch.object(gate.subprocess, "run", return_value=fake):
            with self.assertRaises(gate.ScanOperationalError):
                gate._diff_added_lines("nope")


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


if __name__ == "__main__":
    unittest.main()

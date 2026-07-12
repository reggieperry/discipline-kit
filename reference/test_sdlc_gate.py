#!/usr/bin/env python3
"""Tests for sdlc-gate.py — stdlib unittest, no third-party deps (run: python3 -m unittest).

Covers the two fail-open closures ported from the Scala differential gate:
  - the scoverage coverage-drop scanner (parse + diff), and
  - the fail-closed compile precondition (a non-compiling tree must not read as clean).
The subprocess shells (run_coverage / compile_check) are integration seams, exercised
through their pure helpers here exactly as the existing scanners are.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

# sdlc-gate.py has a hyphen, so it is not importable by name — load it by path.
_spec = importlib.util.spec_from_file_location(
    "sdlc_gate", str(Path(__file__).resolve().parent / "sdlc-gate.py")
)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _clazz(filename: str, invoked: int, count: int) -> str:
    return f'<class filename="{filename}" statement-count="{count}" statements-invoked="{invoked}"/>'


def _report(*classes: str) -> str:
    body = "".join(classes)
    return f'<?xml version="1.0"?><scoverage statement-rate="0"><packages><package name="p">{body}</package></packages></scoverage>'


class ParseScoverageTests(unittest.TestCase):
    def test_two_classes_one_package_aggregate_percent_from_counts(self):
        xml = _report(
            _clazz("example/pipeline/A.scala", 3, 6),
            _clazz("example/pipeline/B.scala", 4, 4),
        )
        cov = gate.parse_scoverage(xml)
        self.assertEqual(set(cov), {"src/main/scala/example/pipeline"})
        # (3+4)/(6+4) = 70%
        self.assertAlmostEqual(cov["src/main/scala/example/pipeline"], 70.0, places=9)

    def test_backslash_filename_normalized(self):
        cov = gate.parse_scoverage(_report(_clazz("example\\extract\\Money.scala", 2, 4)))
        self.assertEqual(set(cov), {"src/main/scala/example/extract"})

    def test_zero_statement_package_dropped_never_minted_as_100(self):
        cov = gate.parse_scoverage(_report(_clazz("example/empty/X.scala", 0, 0)))
        self.assertEqual(cov, {})

    def test_doctype_rejected_xxe_closed(self):
        malicious = '<!DOCTYPE foo [<!ENTITY x "y">]>' + _report(_clazz("a/B.scala", 1, 1))
        with self.assertRaises(Exception):
            gate.parse_scoverage(malicious)

    def test_source_root_override(self):
        cov = gate.parse_scoverage(_report(_clazz("p/A.scala", 1, 2)), source_root="src/test/scala")
        self.assertEqual(set(cov), {"src/test/scala/p"})


class DiffCoverageTests(unittest.TestCase):
    def test_drop_beyond_epsilon_blocks(self):
        base = {"src/main/scala/p": 80.0}
        branch = {"src/main/scala/p": 79.0}  # 1.0 drop > 0.5 epsilon
        blocks = gate._diff_coverage(branch, base, {}, gate.COVERAGE_EPSILON)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["items"][0]["package"], "src/main/scala/p")

    def test_drop_within_epsilon_passes(self):
        base = {"src/main/scala/p": 80.0}
        branch = {"src/main/scala/p": 79.7}  # 0.3 drop < 0.5 epsilon
        self.assertEqual(gate._diff_coverage(branch, base, {}, gate.COVERAGE_EPSILON), [])

    def test_package_absent_from_branch_blocks(self):
        base = {"src/main/scala/p": 80.0}
        blocks = gate._diff_coverage({}, base, {}, gate.COVERAGE_EPSILON)
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(blocks[0]["items"][0]["branch"])

    def test_improvement_passes(self):
        base = {"src/main/scala/p": 80.0}
        self.assertEqual(gate._diff_coverage({"src/main/scala/p": 95.0}, base, {}, gate.COVERAGE_EPSILON), [])

    def test_new_package_not_a_drop(self):
        blocks = gate._diff_coverage({"src/main/scala/q": 50.0}, {"src/main/scala/p": 80.0}, {}, gate.COVERAGE_EPSILON)
        # p absent -> that IS a drop; q is new -> not a drop. So exactly one block (for p).
        self.assertEqual({i["package"] for b in blocks for i in b["items"]}, {"src/main/scala/p"})


class CompilePreconditionTests(unittest.TestCase):
    def test_branch_fail_blocks(self):
        blocks = gate._compile_precondition_blocks("fail", "ok")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["check"], "Build")
        self.assertEqual(blocks[0]["kind"], "compile_error")

    def test_baseline_fail_blocks(self):
        blocks = gate._compile_precondition_blocks("ok", "fail")
        self.assertEqual(len(blocks), 1)

    def test_both_ok_no_block(self):
        self.assertEqual(gate._compile_precondition_blocks("ok", "ok"), [])

    def test_skip_no_block(self):
        # sbt not invokable (no toolchain wired) is a no-op, not a fail-closed block.
        self.assertEqual(gate._compile_precondition_blocks("skip", "skip"), [])
        self.assertEqual(gate._compile_precondition_blocks("ok", "skip"), [])


import contextlib
import io
import json
import tempfile
import types
import unittest.mock as mock


def _write_baseline(d: Path, *, build: str = "ok", coverage: dict | None = None) -> None:
    """A minimal scala baseline dir that _load_baseline_snapshots can read."""
    (d / "sha.txt").write_text("deadbeef\n")
    (d / "toolchain.txt").write_text("scala\n")
    (d / "static-scalafix.json").write_text("[]")
    (d / "static-wartremover.json").write_text("[]")
    (d / "suppressions.json").write_text("[]")
    (d / "test-weakening.json").write_text(json.dumps({"skips": {}, "asserts": {}, "params": {}}))
    (d / "build.txt").write_text(build + "\n")
    if coverage is not None:
        (d / "coverage.json").write_text(json.dumps(coverage))


def _run_cmd_diff(base_dir: Path, **argkw) -> tuple[int, dict]:
    """Invoke cmd_diff with git and the sbt toolchain stubbed; return (exit_code, report)."""
    args = types.SimpleNamespace(
        baseline_dir=str(base_dir), no_static=argkw.get("no_static", False),
        coverage=argkw.get("coverage", False), assertion_loss_waiver=None,
    )
    out = io.StringIO()
    code = 0
    with mock.patch.object(gate, "_git_rename_map", return_value=({}, set())), \
            contextlib.redirect_stdout(out):
        try:
            gate.cmd_diff(args)
        except SystemExit as e:
            code = e.code or 0
    body = out.getvalue().strip()
    return code, (json.loads(body) if body else {})


class CmdDiffCompilePreconditionTests(unittest.TestCase):
    def test_non_compiling_branch_blocks_not_passes(self):
        # The fail-open this closes: a branch that does not compile used to scan empty and PASS.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="ok")
            with mock.patch.object(gate.ScalaToolchain, "compile_check", return_value="fail"):
                code, report = _run_cmd_diff(base)
        self.assertEqual(code, 1)  # NOT 0 — the fail-open is closed
        self.assertEqual(report["verdict"], "fail")
        self.assertEqual(report["blocks"][0]["kind"], "compile_error")
        self.assertEqual(report["blocks"][0]["items"][0]["which"], "branch")

    def test_non_compiling_baseline_also_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="fail")
            with mock.patch.object(gate.ScalaToolchain, "compile_check", return_value="ok"):
                code, report = _run_cmd_diff(base)
        self.assertEqual(code, 1)
        self.assertEqual(report["blocks"][0]["items"][0]["which"], "baseline")

    def test_compiling_branch_does_not_short_circuit(self):
        # both compile -> no Build block; with --no-static and no coverage, a clean pass.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="skip")
            code, report = _run_cmd_diff(base, no_static=True)
        self.assertEqual(code, 0)
        self.assertEqual(report["verdict"], "pass")


class CmdDiffCoverageTests(unittest.TestCase):
    def test_coverage_drop_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="skip", coverage={"src/main/scala/p": 80.0})
            with mock.patch.object(gate.ScalaToolchain, "coverage",
                                   return_value={"src/main/scala/p": 70.0}):
                code, report = _run_cmd_diff(base, no_static=True, coverage=True)
        self.assertEqual(code, 1)
        self.assertTrue(any(b["kind"] == "coverage_drop" for b in report["blocks"]))

    def test_coverage_held_passes(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="skip", coverage={"src/main/scala/p": 80.0})
            with mock.patch.object(gate.ScalaToolchain, "coverage",
                                   return_value={"src/main/scala/p": 80.0}):
                code, report = _run_cmd_diff(base, no_static=True, coverage=True)
        self.assertEqual(code, 0)

    def test_coverage_operational_failure_exits_2(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="skip", coverage={"src/main/scala/p": 80.0})
            boom = gate.CoverageOperationalError("scan did not complete")
            with mock.patch.object(gate.ScalaToolchain, "coverage", side_effect=boom):
                code, _ = _run_cmd_diff(base, no_static=True, coverage=True)
        self.assertEqual(code, 2)  # fail-closed, not read as "no coverage to check"


if __name__ == "__main__":
    unittest.main()

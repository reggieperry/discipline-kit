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
import json
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


def _write_baseline(d: Path, *, build: str = "ok", coverage: dict | None = None,
                    no_static: bool | None = None, agent_scans: dict | None = None,
                    static_not_wired: dict | None = None) -> None:
    """A minimal scala baseline dir that _load_baseline_snapshots can read. `no_static=None`
    writes no no-static.txt, the shape of a baseline captured before that file existed, and
    `static_not_wired=None` writes no static-not-wired.json, likewise."""
    (d / "sha.txt").write_text("deadbeef\n")
    (d / "toolchain.txt").write_text("scala\n")
    (d / "static-scalafix.json").write_text("[]")
    (d / "static-wartremover.json").write_text("[]")
    (d / "suppressions.json").write_text("[]")
    (d / "test-weakening.json").write_text(json.dumps({"skips": {}, "asserts": {}, "params": {}}))
    (d / "build.txt").write_text(build + "\n")
    if coverage is not None:
        (d / "coverage.json").write_text(json.dumps(coverage))
    if no_static is not None:
        (d / "no-static.txt").write_text(("true" if no_static else "false") + "\n")
    if agent_scans is not None:
        (d / "agent-scans.json").write_text(json.dumps(agent_scans))
    if static_not_wired is not None:
        (d / "static-not-wired.json").write_text(json.dumps(static_not_wired))


def _run_cmd_diff(base_dir: Path, **argkw) -> tuple[int, dict]:
    """Invoke cmd_diff with git and the sbt toolchain stubbed; return (exit_code, report).
    Pass stderr=io.StringIO() to capture what the gate wrote there, and forbid_git=True to fail
    the test if the gate reaches its first git command."""
    args = types.SimpleNamespace(
        baseline_dir=str(base_dir), no_static=argkw.get("no_static", False),
        coverage=argkw.get("coverage", False), assertion_loss_waiver=None,
    )
    out = io.StringIO()
    err = argkw.get("stderr")
    git = ({"side_effect": AssertionError("_git_rename_map was called")} if argkw.get("forbid_git")
           else {"return_value": ({}, set())})
    code = 0
    with mock.patch.object(gate, "_git_rename_map", **git), \
            contextlib.redirect_stdout(out), \
            (contextlib.redirect_stderr(err) if err is not None else contextlib.nullcontext()):
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
        self.assertIs(report.get("no_static"), False, "the early report carries the mode as well")

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


_SCANNERS = ("compile_check", "static_analysis", "suppressions", "test_weakening",
             "unreferenced", "duplication", "complexity", "abstractions")
_EMPTY_TW = {"skips": {}, "asserts": {}, "params": {}}
_SKIPPED_EH = {c: {"skipped": "--no-static"} for c in "EFGH"}
_CLEAN_EH = {c: {"tool": "stub", "files": 1, "findings": []} for c in "EFGH"}
_REGEX_ONLY = {"suppressions": gate.Counter(), "test_weakening": _EMPTY_TW}


@contextlib.contextmanager
def _scala_scanners(**allowed):
    """Patch every ScalaToolchain scanner and _diff_added_lines. A name in `allowed` returns that
    value; every other one fails the test the moment it is called, so a run that would have
    reached sbt, PMD or scala-cli cannot pass by returning something plausible."""
    with contextlib.ExitStack() as stack:
        mocks = {}
        targets = [(gate.ScalaToolchain, n) for n in _SCANNERS] + [(gate, "_diff_added_lines")]
        for owner, name in targets:
            kw = ({"return_value": allowed[name]} if name in allowed
                  else {"side_effect": AssertionError(f"{name} was called")})
            mocks[name] = stack.enter_context(mock.patch.object(owner, name, **kw))
        yield mocks


class CmdDiffNoStaticTests(unittest.TestCase):
    """--no-static skips Checks E-H as well as Check A, and the report says so."""

    def test_no_static_diff_calls_no_agent_scanner_and_lists_each_skip(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="skip", no_static=True, agent_scans=_SKIPPED_EH)
            with _scala_scanners(**_REGEX_ONLY) as m:
                code, report = _run_cmd_diff(base, no_static=True)
        self.assertEqual(code, 0)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["not_wired"], [f"{c}: skipped by --no-static" for c in "EFGH"])
        self.assertEqual(report["agent_scans"], {})
        self.assertIs(report.get("no_static"), True,
                      "without it a skipped Check A reads the same as a clean one")
        self.assertEqual([n for n, mk in m.items() if mk.called], list(_REGEX_ONLY))

    def test_no_static_baseline_refuses_a_full_diff(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="skip", no_static=True, agent_scans=_SKIPPED_EH)
            err = io.StringIO()
            with _scala_scanners() as m:
                code, report = _run_cmd_diff(base, no_static=False, stderr=err, forbid_git=True)
        self.assertEqual(code, 2)
        self.assertEqual(report, {})
        self.assertEqual([n for n, mk in m.items() if mk.called], [])
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 1, lines)
        for token in ("no-static=true", "no-static=false", "baseline and diff"):
            self.assertIn(token, lines[0])

    def test_full_baseline_refuses_a_no_static_diff(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="ok", no_static=False, agent_scans=_CLEAN_EH)
            err = io.StringIO()
            with _scala_scanners() as m:
                code, report = _run_cmd_diff(base, no_static=True, stderr=err, forbid_git=True)
        self.assertEqual(code, 2)
        self.assertEqual(report, {})
        self.assertEqual([n for n, mk in m.items() if mk.called], [])
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 1, lines)
        for token in ("no-static=true", "no-static=false", "baseline and diff"):
            self.assertIn(token, lines[0])

    def test_full_baseline_is_not_refused_in_full_mode(self):
        # The default run: every new baseline writes no-static.txt=false, and a plain diff follows.
        # Without this case a mode check that refused every default run passed all six files.
        clean = gate.Scan(tool="stub", files=1, findings={})
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="ok", no_static=False, agent_scans=_CLEAN_EH)
            with _scala_scanners(compile_check="ok", static_analysis={}, unreferenced=clean,
                                 duplication=clean, complexity=clean, abstractions=clean,
                                 _diff_added_lines={}, **_REGEX_ONLY):
                code, report = _run_cmd_diff(base, no_static=False)
        self.assertEqual(code, 0)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["not_wired"], [])
        self.assertEqual(sorted(report["agent_scans"]), ["E", "F", "G", "H"])
        self.assertIs(report.get("no_static"), False)

    def test_unrecognized_mode_file_is_refused_with_its_own_message(self):
        for flag in (False, True):
            with self.subTest(no_static=flag), tempfile.TemporaryDirectory() as td:
                base = Path(td)
                _write_baseline(base, build="skip", agent_scans=_SKIPPED_EH)
                (base / "no-static.txt").write_text("True\n")
                err = io.StringIO()
                with _scala_scanners() as m:
                    code, report = _run_cmd_diff(base, no_static=flag, stderr=err, forbid_git=True)
                self.assertEqual(code, 2)
                self.assertEqual(report, {})
                self.assertEqual([n for n, mk in m.items() if mk.called], [])
                self.assertIn("recapture the baseline", err.getvalue())
                self.assertNotIn("pass the same", err.getvalue())

    def test_baseline_without_mode_file_is_not_refused_under_no_static(self):
        # The shape the merged 82c8727 gate wrote: agent-scans.json with real scans, no mode file.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="skip", agent_scans=_CLEAN_EH)
            with _scala_scanners(**_REGEX_ONLY) as m:
                code, report = _run_cmd_diff(base, no_static=True)
        self.assertEqual(code, 0)
        self.assertEqual(report["not_wired"], [f"{c}: skipped by --no-static" for c in "EFGH"])
        self.assertEqual([n for n, mk in m.items() if mk.called], list(_REGEX_ONLY))

    def test_baseline_without_mode_file_is_not_refused_in_full_mode(self):
        clean = gate.Scan(tool="stub", files=1, findings={})
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_baseline(base, build="ok", agent_scans=_CLEAN_EH)
            with _scala_scanners(compile_check="ok", static_analysis={}, unreferenced=clean,
                                 duplication=clean, complexity=clean, abstractions=clean,
                                 _diff_added_lines={}, **_REGEX_ONLY):
                code, report = _run_cmd_diff(base, no_static=False)
        self.assertEqual(code, 0)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["not_wired"], [])
        self.assertEqual(sorted(report["agent_scans"]), ["E", "F", "G", "H"])
        self.assertIs(report.get("no_static"), False)


# --- Check A: a plugin that is not set up is reported, and a scalafix that fails exits 2 --------
# Trimmed from sbt 1.12.11 runs of 2026-09-10 (sbt-scalafix 0.14.7, sbt-wartremover 3.6.1), machine
# paths replaced by <root>; test_sdlc_gate_scala3.py holds the longer captures. Until that day corpus
# P, with neither plugin, and a lab copy with a broken .scalafix.conf both read as Check A clean.

_P_SCALAFIX = "\n".join([
    "[info] set current project to planted (in build file:<root>/)",
    "[error] Not a valid command: scalafix",
    "[error] Not a valid key: scalafix (similar: scalaHome, scalaVersion, scalacOptions)",
    "[error] scalafix --check",
    "[error]         ^",
]) + "\n"
_P_WART = "\n".join([
    "[info] set current project to planted (in build file:<root>/)",
    "[error] Not a valid project ID: wartremoverWarnings",
    "[error] Expected ':'",
    "[error] Not a valid key: wartremoverWarnings (similar: printWarnings)",
    "[error] show wartremoverWarnings",
    "[error]                         ^",
]) + "\n"
_LAB_SCALAFIX_CLEAN = "\n".join([
    "[info] set current project to claim-algebra-lab (in build file:<root>/)",
    "[success] Total time: 29 s, completed Sep 10, 2026, 11:20:14 PM",
]) + "\n"
_LAB_SCALAFIX_UNKNOWN_RULE = "\n".join([
    "[info] set current project to claim-algebra-lab (in build file:<root>/)",
    "[error] (credit / Compile / scalafix) scalafix.sbt.InvalidArgument: Unknown rule 'NoSuchRuleAnywhere'",
    "[error] (Compile / scalafix) scalafix.sbt.InvalidArgument: Unknown rule 'NoSuchRuleAnywhere'",
    "[error] Total time: 9 s, completed Sep 10, 2026, 11:20:46 PM",
]) + "\n"
_W_SCALAFIX_LINT = "\n".join([
    "[info] Running scalafix on 4 Scala sources",
    "[error] <root>/src/main/scala/planted/Text.scala:8:5: error: [DisableSyntax.var] "
    "mutable state should be avoided",
    "[error]     var lastWasSpace = false",
    "[error]     ^^^",
    "[error] <root>/src/main/scala/planted/Text.scala:9:5: error: [DisableSyntax.var] "
    "mutable state should be avoided",
    "[error]     var i = 0",
    "[error]     ^^^",
    "[error] (Compile / scalafix) scalafix.sbt.ScalafixFailed: LinterError",
    "[error] Total time: 8 s, completed Sep 10, 2026, 11:18:34 PM",
]) + "\n"
_W_WART = "\n".join([
    "[info] * org.wartremover.warts.Any",
    "[info] * org.wartremover.warts.Var",
    "[info] Defining Global / concurrentRestrictions",
    "[info] compiling 4 Scala sources to <root>/target/scala-3.3.8/classes ...",
    "[warn] -- Warning: <root>/src/main/scala/planted/Text.scala:8:8 ",
    "[warn] 8 |    var lastWasSpace = false",
    "[warn]   |    ^^^^^^^^^^^^^^^^^^^^^^^^",
    "[warn]   |    [wartremover:Var] var is disabled",
    "[warn] -- Warning: <root>/src/main/scala/planted/Text.scala:9:8 ",
    "[warn] 9 |    var i = 0",
    "[warn]   |    ^^^^^^^^^",
    "[warn]   |    [wartremover:Var] var is disabled",
    "[success] Total time: 5 s, completed Sep 10, 2026, 11:22:59 PM",
]) + "\n"
_W_WART_FOUND = [["src/main/scala/planted/Text.scala", "Var", 2]]
_NOT_SET_UP = {"scalafix": "sbt-scalafix is not set up",
               "wartremover": "sbt-wartremover is not set up"}
# Captured 2026-09-11 on corpus W plus `ThisBuild / scalacOptions += "-Werror"`, where `sbt Test/compile`
# exits 0 and the wart scan's compile fails on the warts it turns on.
_W_WART_WERROR = "\n".join([
    "[info] * org.wartremover.warts.Any",
    "[info] * org.wartremover.warts.Var",
    "[info] Defining Global / concurrentRestrictions",
    "[success] Total time: 0 s, completed Sep 11, 2026, 3:17:01 AM",
    "[info] compiling 4 Scala sources to <root>/target/scala-3.3.8/classes ...",
    "[error] -- Error: <root>/src/main/scala/planted/Text.scala:8:8 ",
    "[error] 8 |    var lastWasSpace = false",
    "[error]   |    ^^^^^^^^^^^^^^^^^^^^^^^^",
    "[error]   |    [wartremover:Var] var is disabled",
    "[error] -- Error: <root>/src/main/scala/planted/Text.scala:9:8 ",
    "[error] 9 |    var i = 0",
    "[error]   |    ^^^^^^^^^",
    "[error]   |    [wartremover:Var] var is disabled",
    "[error] two errors found",
    "[error] (Compile / compileIncremental) Compilation failed",
    "[error] Total time: 4 s, completed Sep 11, 2026, 3:17:05 AM",
]) + "\n"
# Corpus W with a syntax error in Text.scala (2026-09-10), as scalafix's run reports it.
_W_SCALAFIX_COMPILE_FAILED = "\n".join([
    "[error] -- [E040] Syntax Error: <root>/src/main/scala/planted/Text.scala:34:13 ",
    "[error] 34 |  def broken(: Int = 1",
    "[error]    |             ^",
    "[error]    |             an identifier expected, but ':' found",
    "[error] one error found",
    "[error] (Compile / compileIncremental) Compilation failed",
    "[error] Total time: 5 s, completed Sep 10, 2026, 11:19:29 PM",
]) + "\n"


@contextlib.contextmanager
def _sbt_check_a(scalafix: tuple[int, str], wartremover: tuple[int, str], build: str = "ok"):
    """Check A for real, with sbt answered from the captures above: `scalafix` and `wartremover`
    are (exit code, stdout) for each runner's command, and `build` is what the compile precondition
    returns. Every other Scala scanner is stubbed clean, so no test here reaches sbt, PMD or
    scala-cli. <root> becomes the directory cmd_diff scans. Yields the order of the calls:
    "compile_check", then each runner's token as its sbt command runs."""
    clean = gate.Scan(tool="stub", files=1, findings={})
    stubs = {"suppressions": gate.Counter(), "test_weakening": _EMPTY_TW,
             "unreferenced": clean, "duplication": clean, "complexity": clean, "abstractions": clean}
    calls: list[str] = []

    def sbt(cmd, **kw):
        root = str(Path(kw.get("cwd") or ".").resolve())
        for token, (code, out) in (("scalafix --check", scalafix), ("-Dgate.wartScan=true", wartremover)):
            if token in cmd:
                calls.append(token)
                return types.SimpleNamespace(returncode=code, stdout=out.replace("<root>", root), stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    def compile_check(root):
        calls.append("compile_check")
        return build

    with contextlib.ExitStack() as stack:
        for name, value in stubs.items():
            stack.enter_context(mock.patch.object(gate.ScalaToolchain, name, return_value=value))
        stack.enter_context(mock.patch.object(gate.ScalaToolchain, "compile_check", side_effect=compile_check))
        stack.enter_context(mock.patch.object(gate, "_diff_added_lines", return_value={}))
        stack.enter_context(mock.patch.object(gate.subprocess, "run", side_effect=sbt))
        yield calls


def _diff_check_a(scalafix: tuple[int, str], wartremover: tuple[int, str], *,
                  static_not_wired: dict | None, wartremover_baseline: list | None = None,
                  agent_scans: dict | None = None, build: str = "ok") -> tuple[int, dict, str]:
    """cmd_diff in full mode against a Scala baseline that compiled, with Check A answered by
    _sbt_check_a; returns (exit code, report, stderr)."""
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        _write_baseline(base, build="ok", no_static=False, agent_scans=agent_scans or _CLEAN_EH,
                        static_not_wired=static_not_wired)
        if wartremover_baseline is not None:
            (base / "static-wartremover.json").write_text(json.dumps(wartremover_baseline))
        err = io.StringIO()
        with _sbt_check_a(scalafix, wartremover, build):
            code, report = _run_cmd_diff(base, stderr=err)
    return code, report, err.getvalue()


def _baseline_check_a(scalafix: tuple[int, str], wartremover: tuple[int, str], build: str = "ok",
                      calls: list | None = None) -> tuple[int, dict, str, dict[str, str]]:
    """cmd_baseline in full mode with Check A answered by _sbt_check_a; returns (exit code, stdout
    JSON, stderr, {file name: text} written), and extends `calls` with the order _sbt_check_a saw.
    The root is a plain temporary directory, so the clean-checkout check is patched to accept it."""
    with tempfile.TemporaryDirectory() as td, \
            mock.patch.object(gate, "_resolve_baseline_sha", side_effect=lambda root, sha: sha):
        out = Path(td) / "out"
        args = types.SimpleNamespace(sha="deadbeef", out=str(out), root=td, toolchain="scala",
                                     no_static=False, coverage=False)
        stdout, err = io.StringIO(), io.StringIO()
        code = 0
        with _sbt_check_a(scalafix, wartremover, build) as seen, contextlib.redirect_stdout(stdout), \
                contextlib.redirect_stderr(err):
            try:
                gate.cmd_baseline(args)
            except SystemExit as e:
                code = e.code or 0
        if calls is not None:
            calls.extend(seen)
        written = {p.name: p.read_text() for p in out.iterdir()} if out.exists() else {}
    body = stdout.getvalue().strip()
    return code, (json.loads(body) if body else {}), err.getvalue(), written


class CheckANotSetUpTests(unittest.TestCase):
    def test_baseline_records_each_label_that_is_not_set_up_with_no_findings(self):
        code, report, err, written = _baseline_check_a((1, _P_SCALAFIX), (1, _P_WART))
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(written["static-not-wired.json"]), _NOT_SET_UP)
        self.assertEqual(json.loads(written["static-scalafix.json"]), [])
        self.assertEqual(json.loads(written["static-wartremover.json"]), [])
        self.assertEqual(report.get("static_not_wired"), _NOT_SET_UP)

    def test_negative_control_baseline_with_both_set_up_records_none(self):
        code, _, err, written = _baseline_check_a((0, _LAB_SCALAFIX_CLEAN), (0, _W_WART))
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(written["static-not-wired.json"]), {})
        self.assertEqual(json.loads(written["static-wartremover.json"]), _W_WART_FOUND)

    def test_a_scalafix_that_fails_exits_2_at_baseline_on_one_line(self):
        code, report, err, written = _baseline_check_a((1, _LAB_SCALAFIX_UNKNOWN_RULE), (0, _W_WART))
        self.assertEqual(code, 2)
        self.assertEqual(report, {})
        self.assertEqual(len(err.splitlines()), 2, err)  # the capture banner, then the refusal
        self.assertIn("Unknown rule 'NoSuchRuleAnywhere'", err.splitlines()[-1])
        self.assertEqual([n for n in written if n.startswith("static")], [])

    def test_neither_plugin_set_up_is_listed_after_eh_and_blocks_nothing(self):
        eh = {**_CLEAN_EH, "H": {"not_wired": "abstractions: not wired for scala"}}
        code, report, err = _diff_check_a((1, _P_SCALAFIX), (1, _P_WART),
                                          static_not_wired=_NOT_SET_UP, agent_scans=eh)
        self.assertEqual(code, 0, err)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["blocks"], [])
        self.assertEqual(report["not_wired"], ["H: abstractions: not wired for scala",
                                               "A.scalafix: sbt-scalafix is not set up",
                                               "A.wartremover: sbt-wartremover is not set up"])

    def test_a_scalafix_that_fails_exits_2_at_diff_on_one_line(self):
        code, report, err = _diff_check_a((1, _LAB_SCALAFIX_UNKNOWN_RULE), (0, _W_WART),
                                          static_not_wired={}, wartremover_baseline=_W_WART_FOUND)
        self.assertEqual(code, 2)
        self.assertEqual(report, {})
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertIn("Unknown rule 'NoSuchRuleAnywhere'", err)

    def test_a_label_set_up_at_the_baseline_but_not_on_the_branch_exits_2(self):
        code, report, err = _diff_check_a((1, _P_SCALAFIX), (0, _W_WART),
                                          static_not_wired={}, wartremover_baseline=_W_WART_FOUND)
        self.assertEqual(code, 2)
        self.assertEqual(report, {})
        self.assertEqual(len(err.splitlines()), 1, err)
        for token in ("A.scalafix (sbt-scalafix is not set up)", "cannot be judged by it"):
            self.assertIn(token, err)
        self.assertNotIn("older gate", err)

    def test_a_baseline_without_static_not_wired_json_is_not_refused(self):
        code, report, err = _diff_check_a((0, _LAB_SCALAFIX_CLEAN), (0, _W_WART),
                                          static_not_wired=None, wartremover_baseline=_W_WART_FOUND)
        self.assertEqual(code, 0, err)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["not_wired"], [])

    def test_a_baseline_without_static_not_wired_json_counts_every_label_as_set_up(self):
        code, report, err = _diff_check_a((1, _P_SCALAFIX), (0, _W_WART),
                                          static_not_wired=None, wartremover_baseline=_W_WART_FOUND)
        self.assertEqual(code, 2)
        self.assertEqual(report, {})
        self.assertIn("A.scalafix", err)
        self.assertIn("older gate", err)

    def test_a_label_not_set_up_at_the_baseline_but_set_up_on_the_branch_compares_against_none(self):
        code, report, err = _diff_check_a((1, _W_SCALAFIX_LINT), (0, _W_WART),
                                          static_not_wired={"scalafix": _NOT_SET_UP["scalafix"]},
                                          wartremover_baseline=_W_WART_FOUND)
        self.assertEqual(code, 1, err)
        self.assertEqual(report["blocks"], [{
            "check": "A.scalafix", "kind": "new_errors",
            "items": [{"file": "src/main/scala/planted/Text.scala", "code": "DisableSyntax.var",
                       "new": 2, "global_net": 2}]}])
        self.assertEqual(report["not_wired"], [])


class CheckACompileFailureTests(unittest.TestCase):
    """The compile precondition compiles without -Dgate.wartScan=true and the wart scan with it, so a
    build that keeps -Werror under the property fails only inside the scan. Until 2026-09-11 both
    runners read any compile failure as an empty scan: Check A read zero on both sides and a new
    wart passed. The empty scan is now kept only when the precondition itself failed."""

    def test_diff_exits_2_when_only_the_wart_scan_does_not_compile(self):
        code, report, err = _diff_check_a((0, _LAB_SCALAFIX_CLEAN), (1, _W_WART_WERROR),
                                          static_not_wired={}, wartremover_baseline=_W_WART_FOUND)
        self.assertEqual(code, 2, err)
        self.assertEqual(report, {})
        self.assertEqual(len(err.splitlines()), 1, err)
        for token in ("A.wartremover", "Compilation failed", "-Werror", "compile precondition passed"):
            self.assertIn(token, err)

    def test_diff_exits_2_when_only_scalafix_does_not_compile(self):
        code, report, err = _diff_check_a((1, _W_SCALAFIX_COMPILE_FAILED), (0, _W_WART),
                                          static_not_wired={}, wartremover_baseline=_W_WART_FOUND)
        self.assertEqual(code, 2, err)
        self.assertEqual(report, {})
        self.assertEqual(len(err.splitlines()), 1, err)
        for token in ("A.scalafix", "Compilation failed", "compile precondition passed"):
            self.assertIn(token, err)
        self.assertNotIn("A.wartremover", err)

    def test_diff_whose_precondition_could_not_run_exits_2_without_saying_it_passed(self):
        code, report, err = _diff_check_a((0, _LAB_SCALAFIX_CLEAN), (1, _W_WART_WERROR), build="skip",
                                          static_not_wired={}, wartremover_baseline=_W_WART_FOUND)
        self.assertEqual(code, 2, err)
        self.assertEqual(report, {})
        self.assertIn("the compile precondition returned skip, not fail", err)
        self.assertNotIn("passed", err)

    def test_baseline_runs_the_compile_precondition_first_and_exits_2_the_same_way(self):
        calls: list[str] = []
        code, report, err, written = _baseline_check_a((0, _LAB_SCALAFIX_CLEAN), (1, _W_WART_WERROR),
                                                       calls=calls)
        self.assertEqual(calls, ["compile_check", "scalafix --check", "-Dgate.wartScan=true"])
        self.assertEqual(code, 2, err)
        self.assertEqual(report, {})
        self.assertEqual(len(err.splitlines()), 2, err)  # the capture banner, then the refusal
        for token in ("A.wartremover", "-Werror", "compile precondition passed"):
            self.assertIn(token, err.splitlines()[-1])
        self.assertEqual([n for n in written if n.startswith("static") or n == "build.txt"], [])

    def test_negative_control_a_baseline_that_does_not_compile_keeps_the_empty_scans(self):
        """Diff blocks such a baseline as Build, so nothing reads these scans as clean."""
        code, _, err, written = _baseline_check_a((1, _W_SCALAFIX_COMPILE_FAILED), (1, _W_WART_WERROR),
                                                  build="fail")
        self.assertEqual(code, 0, err)
        self.assertEqual(written["build.txt"], "fail\n")
        self.assertEqual(json.loads(written["static-scalafix.json"]), [])
        self.assertEqual(json.loads(written["static-wartremover.json"]), [])
        self.assertEqual(json.loads(written["static-not-wired.json"]), {})

    def test_the_empty_scan_is_kept_only_for_a_precondition_that_failed(self):
        found = gate.Counter({("a/A.scala", "DisableSyntax.var"): 1})
        why = gate.ScanCompileFailed("the wart scan's compile failed (sbt exited 1: Compilation failed)")
        tc = types.SimpleNamespace(static_analysis=lambda root: {"scalafix": found, "wartremover": why})
        self.assertEqual(gate._static_scans(tc, Path("/r"), "fail"),
                         ({"scalafix": found, "wartremover": gate.Counter()}, {}))
        for build in ("ok", "skip"):
            with self.subTest(build=build):
                err = io.StringIO()
                with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(err):
                    gate._static_scans(tc, Path("/r"), build)
                self.assertEqual(cm.exception.code, 2)
                self.assertEqual(len(err.getvalue().splitlines()), 1, err.getvalue())
                self.assertIn("A.wartremover: the wart scan's compile failed", err.getvalue())
                self.assertNotIn("A.scalafix", err.getvalue())


class BaselineToolchainChoicesTests(unittest.TestCase):
    """The baseline parser offered python|scala|java while _TOOLCHAINS also held go and
    typescript, and select_toolchain's own error told the caller to pass --toolchain go."""

    def _main(self, *extra: str) -> mock.MagicMock:
        argv = ["sdlc-gate", "baseline", "--sha", "deadbeef", "--out", "unused", *extra]
        with mock.patch.object(gate, "cmd_baseline") as cmd, \
                mock.patch.object(gate.sys, "argv", argv):
            gate.main()
        return cmd

    def test_every_registered_toolchain_is_accepted(self):
        self.assertTrue({"go", "typescript"} <= set(gate._TOOLCHAINS))
        for name in gate._TOOLCHAINS:
            with contextlib.redirect_stderr(io.StringIO()):
                try:
                    cmd = self._main("--toolchain", name)
                except SystemExit as e:
                    self.fail(f"--toolchain {name} rejected by the parser (exit {e.code})")
            self.assertEqual(cmd.call_args.args[0].toolchain, name)

    def test_negative_control_unknown_toolchain_is_rejected(self):
        err = io.StringIO()
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(err):
            self._main("--toolchain", "cobol")
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("invalid choice", err.getvalue())


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


# ---------------------------------------------------------------------------
# Java toolchain (v1.3.0) — red-first fixtures. Every gate.* symbol referenced
# below is ABSENT from the pre-JavaToolchain gate, so this whole section errors
# red against the shipped gate; that is this wave's observed-red bar. Once the
# JavaToolchain scanners land, it goes green.
# ---------------------------------------------------------------------------


def _write_java(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _write_java_baseline(d: Path, *, build: str = "ok", tw: dict | None = None,
                         checkstyle: list | None = None) -> None:
    """A minimal java baseline dir that _load_baseline_snapshots can read."""
    (d / "sha.txt").write_text("deadbeef\n")
    (d / "toolchain.txt").write_text("java\n")
    (d / "static-checkstyle.json").write_text(json.dumps(checkstyle if checkstyle is not None else []))
    (d / "suppressions.json").write_text("[]")
    (d / "test-weakening.json").write_text(
        json.dumps(tw if tw is not None else {"skips": {}, "asserts": {}, "params": {}}))
    (d / "build.txt").write_text(build + "\n")


class JavaDetectTests(unittest.TestCase):
    def test_pom_detects(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "pom.xml").write_text("<project/>")
            self.assertTrue(gate.JavaToolchain().detect(Path(td)))

    def test_gradle_groovy_and_kts_detect(self):
        for marker in ("build.gradle", "build.gradle.kts"):
            with tempfile.TemporaryDirectory() as td:
                (Path(td) / marker).write_text("")
                self.assertTrue(gate.JavaToolchain().detect(Path(td)))

    def test_no_marker_no_detect(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(gate.JavaToolchain().detect(Path(td)))

    def test_select_toolchain_override_and_auto(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "pom.xml").write_text("<project/>")
            self.assertIsInstance(gate.select_toolchain(Path(td), "java"), gate.JavaToolchain)
            self.assertIsInstance(gate.select_toolchain(Path(td), None), gate.JavaToolchain)


class JavaSuppressionScanTests(unittest.TestCase):
    def test_all_four_directive_families_caught(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_java(root, "src/main/java/A.java",
                        '@SuppressWarnings("unchecked")\n'
                        'class A {\n'
                        '  // CHECKSTYLE:OFF\n'
                        '  int x; // NOPMD\n'
                        '  @SuppressFBWarnings("NP_NULL_ON_SOME_PATH")\n'
                        '  void m() {}\n'
                        '}\n')
            keys = {k for (_f, k) in gate.scan_java_suppressions(root)}
            self.assertIn("SuppressWarnings[unchecked]", keys)
            self.assertIn("CHECKSTYLE:OFF[BLANKET]", keys)
            self.assertTrue(any(k.startswith("NOPMD") for k in keys), keys)
            self.assertTrue(any(k.startswith("SuppressFBWarnings") for k in keys), keys)

    def test_targeted_checkstyle_off_is_its_own_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_java(root, "src/main/java/B.java", "// CHECKSTYLE:OFF: MagicNumber\nclass B {}\n")
            keys = {k for (_f, k) in gate.scan_java_suppressions(root)}
            self.assertIn("CHECKSTYLE:OFF[MagicNumber]", keys)


class JavaTestWeakeningScanTests(unittest.TestCase):
    def test_disabled_skip_asserts_and_jqwik_params(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_java(root, "src/test/java/AT.java",
                        'class AT {\n'
                        '  @Disabled void a() {}\n'
                        '  @Test void b() { assertEquals(1,1); assertThat(x).isTrue();\n'
                        '    assertThrows(E.class, () -> {}); }\n'
                        '  @Property(tries = 10) void p(@ForAll int n) {}\n'
                        '  @Property(shrinking = ShrinkingMode.OFF) void q(@ForAll int n) {}\n'
                        '}\n')
            tw = gate.scan_java_test_weakening(root)
            f = "src/test/java/AT.java"
            self.assertEqual(tw["skips"][f], 1)                 # @Disabled
            self.assertEqual(tw["asserts"][f], 3)               # assertEquals + assertThat + assertThrows
            self.assertEqual(tw["params"][f]["tries"], 10)      # weakest tries in the file
            self.assertEqual(tw["params"][f]["shrinkingOff"], 1)

    def test_shrinkingOff_key_ALWAYS_emitted_even_when_absent(self):
        # The fail-open the committee flagged: a key emitted only-when-present escapes a
        # keys-in-both comparison, so a fresh ShrinkingMode.OFF sails through. Always-emit 0.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_java(root, "src/test/java/CleanT.java",
                        'class CleanT { @Property(tries = 1000) void p(@ForAll int n) {} }\n')
            tw = gate.scan_java_test_weakening(root)
            self.assertEqual(tw["params"]["src/test/java/CleanT.java"]["shrinkingOff"], 0)

    def test_non_test_file_not_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_java(root, "src/main/java/M.java", "@Disabled class M {}\n")
            tw = gate.scan_java_test_weakening(root)
            self.assertNotIn("src/main/java/M.java", tw["skips"])


class JavaParamWeakeningTests(unittest.TestCase):
    def _dirs(self):
        return gate.JavaToolchain().param_directions

    def test_tries_fall_blocks(self):
        base = {"params": {"src/test/java/T.java": {"tries": 1000, "shrinkingOff": 0}}}
        branch = {"params": {"src/test/java/T.java": {"tries": 10, "shrinkingOff": 0}}}
        blocks = gate._check_scalacheck_params(branch, base, self._dirs(), {}, set())
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["items"][0]["param"], "tries")

    def test_shrinkingOff_appearing_blocks(self):
        # 0 -> 1 must be caught; this is the always-emit fix's payoff.
        base = {"params": {"src/test/java/T.java": {"tries": 10, "shrinkingOff": 0}}}
        branch = {"params": {"src/test/java/T.java": {"tries": 10, "shrinkingOff": 1}}}
        blocks = gate._check_scalacheck_params(branch, base, self._dirs(), {}, set())
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["items"][0]["param"], "shrinkingOff")

    def test_held_params_pass(self):
        base = {"params": {"src/test/java/T.java": {"tries": 10, "shrinkingOff": 0}}}
        self.assertEqual(gate._check_scalacheck_params(base, base, self._dirs(), {}, set()), [])


class CmdDiffJavaCompileTests(unittest.TestCase):
    def test_non_compiling_java_branch_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_java_baseline(base, build="ok")
            with mock.patch.object(gate.JavaToolchain, "compile_check", return_value="fail"):
                code, report = _run_cmd_diff(base)
        self.assertEqual(code, 1)
        self.assertEqual(report["blocks"][0]["kind"], "compile_error")
        self.assertEqual(report["blocks"][0]["items"][0]["which"], "branch")

    def test_java_suppression_introduced_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write_java_baseline(base, build="skip")
            # a branch tree with a new suppression, baseline had none
            with mock.patch.object(gate.JavaToolchain, "compile_check", return_value="skip"), \
                    mock.patch.object(gate.JavaToolchain, "static_analysis", return_value={}), \
                    mock.patch.object(gate.JavaToolchain, "suppressions",
                                      return_value=gate.Counter({("src/main/java/A.java",
                                                                  "SuppressWarnings[unchecked]"): 1})), \
                    mock.patch.object(gate.JavaToolchain, "test_weakening",
                                      return_value={"skips": {}, "asserts": {}, "params": {}}):
                code, report = _run_cmd_diff(base)
        self.assertEqual(code, 1)
        self.assertTrue(any(b["check"] == "B" for b in report["blocks"]))


class JavaSpotBugsFailClosedTests(unittest.TestCase):
    def test_spotbugs_no_bytecode_is_operational_not_empty(self):
        # SpotBugs analyzes bytecode; a source-only tree with the tool present must FAIL
        # CLOSED, never scan-empty-and-pass (the committee's catch).
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_java(root, "src/main/java/A.java", "class A {}\n")
            with mock.patch.object(gate, "_spotbugs_tool_present", return_value=True):
                with self.assertRaises(gate.SpotBugsOperationalError):
                    gate.run_spotbugs(root)

    def test_spotbugs_tool_absent_is_a_clean_skip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.object(gate, "_spotbugs_tool_present", return_value=False):
                self.assertEqual(gate.run_spotbugs(root), gate.Counter())


# --- TypeScript toolchain -----------------------------------------------------
# Every format asserted below was captured from the installed tool before this was written:
# `eslint -f json` on a forced violation, `tsc --noEmit -p tsconfig.json` on a type error,
# and istanbul's coverage-final.json from a real vitest --coverage run.

class TypeScriptDetectTests(unittest.TestCase):
    def test_package_json_detects(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "package.json").write_text("{}")
            self.assertTrue(gate.TypeScriptToolchain().detect(Path(td)))

    def test_tsconfig_alone_detects(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "tsconfig.json").write_text("{}")
            self.assertTrue(gate.TypeScriptToolchain().detect(Path(td)))

    def test_no_marker_no_detect(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(gate.TypeScriptToolchain().detect(Path(td)))

    def test_scala_wins_over_package_json(self):
        """A polyglot repo with both markers must not be claimed by TypeScript: the sbt build
        is the one carrying the sources, and package.json is routinely a frontend subdirectory."""
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "build.sbt").write_text("")
            (Path(td) / "package.json").write_text("{}")
            self.assertIsInstance(gate.select_toolchain(Path(td), None), gate.ScalaToolchain)

    def test_override_selects_typescript(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsInstance(
                gate.select_toolchain(Path(td), "typescript"), gate.TypeScriptToolchain)


class EslintParseTests(unittest.TestCase):
    def test_findings_keyed_file_and_rule(self):
        root = Path("/repo")
        payload = json.dumps([{
            "filePath": "/repo/src/a.ts",
            "messages": [
                {"ruleId": "@typescript-eslint/no-unused-vars", "severity": 2, "line": 2},
                {"ruleId": "@typescript-eslint/no-unused-vars", "severity": 2, "line": 9},
                {"ruleId": "no-console", "severity": 1, "line": 4},
            ],
        }])
        self.assertEqual(gate._parse_eslint_json(payload, root), gate.Counter({
            ("src/a.ts", "@typescript-eslint/no-unused-vars"): 2,
            ("src/a.ts", "no-console"): 1,
        }))

    def test_null_ruleid_kept_not_dropped(self):
        """eslint emits ruleId null for directive-level findings ('Unused eslint-disable
        directive') — captured from the real tool. Dropping them loses a real finding class."""
        payload = json.dumps([{"filePath": "/repo/src/a.ts",
                               "messages": [{"ruleId": None, "severity": 1, "line": 1}]}])
        self.assertEqual(gate._parse_eslint_json(payload, Path("/repo")),
                         gate.Counter({("src/a.ts", "(core)"): 1}))

    def test_empty_and_malformed_are_empty_not_crash(self):
        self.assertEqual(gate._parse_eslint_json("", Path("/repo")), gate.Counter())
        self.assertEqual(gate._parse_eslint_json("not json", Path("/repo")), gate.Counter())


class TscParseTests(unittest.TestCase):
    def test_real_error_format(self):
        out = ("src/zz.ts(1,14): error TS2322: Type 'string' is not assignable to type 'number'.\n"
               "src/zz.ts(2,14): error TS2322: Type 'number' is not assignable to type 'string'.\n"
               "src/b.tsx(7,3): error TS2345: Argument of type 'X' is not assignable.\n")
        self.assertEqual(gate._parse_tsc_output(out), gate.Counter({
            ("src/zz.ts", "TS2322"): 2,
            ("src/b.tsx", "TS2345"): 1,
        }))

    def test_non_error_lines_ignored(self):
        self.assertEqual(gate._parse_tsc_output("Version 5.4.2\nFound 0 errors.\n"), gate.Counter())


class TypeScriptSuppressionScanTests(unittest.TestCase):
    def test_all_directive_families_caught_as_distinct_keys(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "a.ts").write_text(
                "// eslint-disable-next-line no-console\n"
                "console.log(1);\n"
                "/* eslint-disable no-shadow */\n"
                "// @ts-ignore\n"
                "const a = 1;\n"
                "// @ts-expect-error\n"
                "const b = 2;\n"
            )
            (root / "src" / "b.ts").write_text("// @ts-nocheck\nexport const c = 3;\n")
            got = gate.scan_ts_suppressions(root)
            self.assertEqual(got[("src/a.ts", "eslint-disable-next-line")], 1)
            self.assertEqual(got[("src/a.ts", "eslint-disable")], 1)
            self.assertEqual(got[("src/a.ts", "ts-ignore")], 1)
            self.assertEqual(got[("src/a.ts", "ts-expect-error")], 1)
            self.assertEqual(got[("src/b.ts", "ts-nocheck")], 1)

    def test_node_modules_never_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "node_modules" / "pkg").mkdir(parents=True)
            (root / "node_modules" / "pkg" / "x.ts").write_text("// @ts-ignore\n")
            self.assertEqual(gate.scan_ts_suppressions(root), gate.Counter())


class TypeScriptTestWeakeningScanTests(unittest.TestCase):
    def test_skip_only_todo_and_assert_counts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "a.test.ts").write_text(
                "describe.skip('x', () => {\n"
                "  it.only('y', () => { expect(1).toBe(1); });\n"
                "  it.todo('z');\n"
                "  xit('w', () => { expect(2).toBe(2); });\n"
                "});\n"
            )
            got = gate.scan_ts_test_weakening(root)
            # .only narrows the run — it disables every sibling — so it belongs with the skips.
            self.assertEqual(got["skips"]["src/a.test.ts"], 4)
            self.assertEqual(got["asserts"]["src/a.test.ts"], 2)

    def test_non_test_file_not_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "app.ts").write_text("it.skip('x', () => {});\n")
            self.assertEqual(gate.scan_ts_test_weakening(root)["skips"], {})

    def test_spec_and_tests_dir_both_recognised(self):
        for rel in ("src/a.test.ts", "src/a.spec.tsx", "src/__tests__/a.ts"):
            self.assertTrue(gate._ts_is_test_file(rel), rel)
        self.assertFalse(gate._ts_is_test_file("src/a.ts"))


class TypeScriptCoverageTests(unittest.TestCase):
    def test_istanbul_statement_coverage_per_directory(self):
        payload = json.dumps({
            "/repo/src/a.ts": {"path": "/repo/src/a.ts", "s": {"0": 1, "1": 0, "2": 3}},
            "/repo/src/b.ts": {"path": "/repo/src/b.ts", "s": {"0": 1}},
            "/repo/lib/c.ts": {"path": "/repo/lib/c.ts", "s": {"0": 0, "1": 0}},
        })
        got = gate.parse_istanbul(payload, Path("/repo"))
        self.assertAlmostEqual(got["src"], 75.0)     # 3 of 4 statements hit
        self.assertAlmostEqual(got["lib"], 0.0)

    def test_zero_statement_file_never_minted_as_100(self):
        payload = json.dumps({"/repo/src/empty.ts": {"path": "/repo/src/empty.ts", "s": {}}})
        self.assertEqual(gate.parse_istanbul(payload, Path("/repo")), {})

    def test_missing_report_is_operational_not_empty(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(gate.CoverageOperationalError):
                gate.run_istanbul_coverage(Path(td))


# --- Go toolchain -------------------------------------------------------------
# Formats captured from golangci-lint 2.12.2 and go 1.26 before these were written. Two of the
# assertions below exist because the captured output differed from the obvious guess.

class GoDetectTests(unittest.TestCase):
    def test_go_mod_detects(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "go.mod").write_text("module example.com/x\n")
            self.assertTrue(gate.GoToolchain().detect(Path(td)))

    def test_no_marker_no_detect(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(gate.GoToolchain().detect(Path(td)))

    def test_go_wins_over_package_json(self):
        """A Go repo with a package.json for its frontend tooling is a Go repo."""
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "go.mod").write_text("module example.com/x\n")
            (Path(td) / "package.json").write_text("{}")
            self.assertIsInstance(gate.select_toolchain(Path(td), None), gate.GoToolchain)

    def test_override_selects_go(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsInstance(gate.select_toolchain(Path(td), "go"), gate.GoToolchain)


class GolangciParseTests(unittest.TestCase):
    def test_trailing_human_summary_does_not_break_the_parse(self):
        """CAPTURED, not assumed: golangci-lint 2.x with --output.json.path stdout writes the JSON
        document on line 1 and then appends a human-readable summary. json.load(stdout) raises
        'Extra data'. A parser that took the whole stream would report zero findings on every
        run — a silent fail-open, and the reason this test exists."""
        payload = (
            '{"Issues":[{"FromLinter":"errcheck","Text":"unchecked",'
            '"Pos":{"Filename":"main.go","Line":7,"Column":15}}],"Report":{}}\n'
            "3 issues:\n* errcheck: 1\n* staticcheck: 2\n")
        self.assertEqual(gate._parse_golangci_json(payload, Path("/repo")),
                         gate.Counter({("main.go", "errcheck"): 1}))

    def test_findings_keyed_file_and_linter(self):
        payload = json.dumps({"Issues": [
            {"FromLinter": "staticcheck", "Pos": {"Filename": "a.go", "Line": 1}},
            {"FromLinter": "staticcheck", "Pos": {"Filename": "a.go", "Line": 9}},
            {"FromLinter": "errcheck", "Pos": {"Filename": "b/c.go", "Line": 2}},
        ]})
        self.assertEqual(gate._parse_golangci_json(payload, Path("/repo")), gate.Counter({
            ("a.go", "staticcheck"): 2, ("b/c.go", "errcheck"): 1}))

    def test_empty_and_malformed_are_empty_not_crash(self):
        self.assertEqual(gate._parse_golangci_json("", Path("/repo")), gate.Counter())
        self.assertEqual(gate._parse_golangci_json("nope", Path("/repo")), gate.Counter())
        self.assertEqual(gate._parse_golangci_json('{"Issues":null}', Path("/repo")), gate.Counter())


class GoSuppressionScanTests(unittest.TestCase):
    def test_bare_and_targeted_are_distinct_keys(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.go").write_text("//nolint\nvar a = 1\n//nolint:errcheck // reason\nvar b = 2\n")
            got = gate.scan_go_suppressions(root)
            self.assertEqual(got[("a.go", "nolint")], 1)
            self.assertEqual(got[("a.go", "nolint:errcheck")], 1)

    def test_each_named_linter_is_its_own_key_so_broadening_is_visible(self):
        """`//nolint:a` widened to `//nolint:a,b` must register as a NEW key, or Check B's
        'broadened suppression' arm cannot see the widening at all."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.go").write_text("//nolint:errcheck,gosec\nvar a = 1\n")
            got = gate.scan_go_suppressions(root)
            self.assertEqual(got[("a.go", "nolint:errcheck")], 1)
            self.assertEqual(got[("a.go", "nolint:gosec")], 1)
            self.assertEqual(got[("a.go", "nolint")], 0)

    def test_vendor_never_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "vendor" / "x").mkdir(parents=True)
            (root / "vendor" / "x" / "y.go").write_text("//nolint\n")
            self.assertEqual(gate.scan_go_suppressions(root), gate.Counter())


class GoTestWeakeningScanTests(unittest.TestCase):
    def test_skip_family_and_assert_sites(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a_test.go").write_text(
                "func TestA(t *testing.T) { t.Skip(\"x\") }\n"
                "func TestB(t *testing.T) { t.Skipf(\"%s\", \"y\") }\n"
                "func TestC(t *testing.T) { t.SkipNow() }\n"
                "func TestD(t *testing.T) { t.Errorf(\"e\"); t.Fatalf(\"f\") }\n"
                "func TestE(t *testing.T) { require.NoError(t, err); assert.Equal(t, 1, 1) }\n"
            )
            got = gate.scan_go_test_weakening(root)
            self.assertEqual(got["skips"]["a_test.go"], 3)
            self.assertEqual(got["asserts"]["a_test.go"], 4)

    def test_non_test_file_not_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.go").write_text("t.Skip()\n")
            self.assertEqual(gate.scan_go_test_weakening(root)["skips"], {})

    def test_is_test_file(self):
        self.assertTrue(gate._go_is_test_file("internal/x/a_test.go"))
        self.assertFalse(gate._go_is_test_file("internal/x/a.go"))


class GoCoverageTests(unittest.TestCase):
    def test_module_path_prefix_is_stripped(self):
        """CAPTURED: a coverprofile names files by MODULE path, not repo-relative path —
        `example.com/goprobe/main.go` for a file at `main.go`. Keys that keep the prefix match
        nothing on the other side of the differential, so every package reads as new."""
        profile = ("mode: set\n"
                   "example.com/m/internal/a/x.go:5.13,12.2 4 1\n"
                   "example.com/m/internal/a/y.go:3.1,4.2 1 0\n"
                   "example.com/m/cmd/z.go:1.1,2.2 2 1\n")
        got = gate.parse_go_coverprofile(profile, "example.com/m")
        self.assertAlmostEqual(got["internal/a"], 80.0)   # 4 of 5 statements
        self.assertAlmostEqual(got["cmd"], 100.0)

    def test_zero_statement_block_never_minted_as_100(self):
        self.assertEqual(gate.parse_go_coverprofile("mode: set\nm/a.go:1.1,2.2 0 0\n", "m"), {})

    def test_missing_profile_is_operational_not_empty(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "go.mod").write_text("module m\n")
            with self.assertRaises(gate.CoverageOperationalError):
                gate.run_go_coverage(Path(td))


if __name__ == "__main__":
    unittest.main()

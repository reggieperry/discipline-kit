#!/usr/bin/env python3
"""Tests for the TypeScript runners behind Checks E-H in sdlc-gate.py. Stdlib unittest, run:
python3 <this file>.

Every tool is mocked at subprocess.run, so the suite runs on a box with none of eslint, knip,
jscpd, node or typescript installed. The canned bodies are the shapes captured from the real
tools on 2026-09-10 (eslint 9.39 `-f json`, sonarjs 4.2's message, knip 6.35's JSON reporter,
jscpd 5.2's JSON and SARIF reports, the embedded walker's own output), trimmed to what the
parsers read. For each check: a positive control, a negative control, and the did-not-run
refusals, each asserted as a raise rather than as an empty Scan.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import types
import unittest
import unittest.mock as mock
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "sdlc_gate", str(Path(__file__).resolve().parent / "sdlc-gate.py")
)
assert _spec and _spec.loader
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


# --- A throwaway TypeScript tree with stub binaries ---------------------------------------------

def _tree(td: str, files: dict[str, str] | None = None, bins=("eslint", "knip", "jscpd")) -> Path:
    root = Path(td)
    (root / "package.json").write_text('{"name": "t"}')
    for b in bins:
        p = root / "node_modules" / ".bin" / b
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("#!/bin/sh\n")
    if files is None:
        files = {"src/a.ts": "export const a = 1;\n", "src/b.tsx": "export const b = 2;\n"}
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


def _proc(rc: int, stdout: str = "", stderr: str = ""):
    return types.SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr)


def _eslint_entry(root: Path, rel: str, messages: list[dict]) -> dict:
    return {"filePath": str(root / rel), "messages": messages, "fatalErrorCount":
            sum(1 for m in messages if m.get("fatal"))}


def _unused(name: str, line: int) -> dict:
    return {"ruleId": "@typescript-eslint/no-unused-vars", "severity": 2, "line": line, "column": 7,
            "message": f"'{name}' is defined but never used."}


def _sonar(cc: int, line: int, column: int) -> dict:
    return {"ruleId": "sonarjs/cognitive-complexity", "severity": 2, "line": line, "column": column,
            "message": f"Refactor this function to reduce its Cognitive Complexity from {cc} to the 0 allowed."}


_FATAL = {"ruleId": None, "fatal": True, "severity": 2, "line": 2, "column": 8,
          "message": "Parsing error: ':' expected."}


class _Tools:
    """One fake subprocess.run for all four tools, dispatched on the binary. Each attribute is a
    callable(cmd, kwargs) -> proc, or a proc; a test overrides the ones it needs. The walker and
    jscpd handlers get to look at the argv (the file list, the --output dir)."""

    def __init__(self, root: Path):
        self.root = root
        self.calls: list[list[str]] = []
        self.eslint = lambda cmd, kw: _proc(0, json.dumps(
            [_eslint_entry(root, f, []) for f in cmd[cmd.index("json") + 1:]]))
        self.knip = _proc(0, json.dumps({"issues": []}))
        self.walker = lambda cmd, kw: _proc(0, json.dumps(
            {"files": len(json.loads(Path(cmd[4]).read_text())),
             "functions" if cmd[2] == "functions" else "abstractions": []}))
        self.jscpd = lambda cmd, kw: self.write_jscpd(cmd, sources=2, clones=[])

    @staticmethod
    def write_jscpd(cmd, sources: int, clones: list[tuple[str, list[tuple[str, int, int]]]],
                    json_extra: int = 0):
        """Both reports, as jscpd 5.2 writes them. `clones` are (hash, [(uri, start, end), ...])."""
        out = Path(cmd[cmd.index("--output") + 1])
        dups = []
        results = []
        for h, occs in clones:
            first, second = occs[0], occs[1]
            dups.append({"format": "typescript", "firstFile": {"name": first[0], "start": first[1], "end": first[2]},
                         "secondFile": {"name": second[0], "start": second[1], "end": second[2]}, "tokens": 96})
            loc = lambda o: {"physicalLocation": {"artifactLocation": {"uri": o[0]},
                                                  "region": {"startLine": o[1], "endLine": o[2]}}}
            results.append({"ruleId": "jscpd/duplicate-code", "properties": {"clone_hash": h, "token_count": 96},
                            "partialFingerprints": {"jscpdCloneHash/v1": h},
                            "locations": [loc(first)], "relatedLocations": [loc(o) for o in occs[1:]]})
        for _ in range(json_extra):
            dups.append(dict(dups[0]) if dups else {"firstFile": {}, "secondFile": {}})
        (out / "jscpd-report.json").write_text(json.dumps(
            {"statistics": {"total": {"sources": sources, "clones": len(dups)}}, "duplicates": dups}))
        (out / "jscpd-report.sarif").write_text(json.dumps({"runs": [{"results": results}]}))
        return _proc(0)

    def run(self, cmd, **kw):
        self.calls.append(list(cmd))
        exe = cmd[0]
        which = ("walker" if exe.endswith("node") else "eslint" if "eslint" in exe
                 else "knip" if "knip" in exe else "jscpd" if "jscpd" in exe else None)
        if which is None:
            raise AssertionError(f"unexpected invocation {cmd}")
        h = getattr(self, which)
        return h(cmd, kw) if callable(h) else h


def _patched(tools: _Tools):
    return (mock.patch.object(gate.subprocess, "run", side_effect=tools.run),
            mock.patch.object(gate.shutil, "which", side_effect=lambda n: "/fake/bin/node" if n == "node" else None))


class _Case(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = _tree(self._td.name)
        self.tools = _Tools(self.root)
        for p in _patched(self.tools):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self._td.cleanup()


# --- Check E: unreferenced --------------------------------------------------------------------

class UnreferencedTests(_Case):
    def test_positive_eslint_and_knip_findings_are_counted_per_file_and_code(self):
        self.tools.eslint = lambda cmd, kw: _proc(1, json.dumps([
            _eslint_entry(self.root, "src/a.ts", [_unused("x", 1), _unused("y", 2),
                                                 {"ruleId": "no-unused-private-class-members", "line": 3, "column": 1,
                                                  "message": "'#p' is defined but never used."},
                                                 {"ruleId": "semi", "line": 4, "column": 1, "message": "irrelevant"}]),
            _eslint_entry(self.root, "src/b.tsx", [])]))
        self.tools.knip = _proc(1, json.dumps({"issues": [
            {"file": "src/a.ts", "exports": [{"name": "a", "line": 1, "col": 14}], "types": [],
             "enumMembers": {"E": [{"name": "M"}, {"name": "N"}]}, "files": []},
            {"file": "src/dead.ts", "files": [{"name": "src/dead.ts"}]}]}))
        s = gate.run_ts_unreferenced(self.root)
        self.assertEqual(s.files, 2)
        self.assertEqual(s.findings, {
            ("src/a.ts", "@typescript-eslint/no-unused-vars"): 2,
            ("src/a.ts", "no-unused-private-class-members"): 1,
            ("src/a.ts", "knip:exports"): 1,
            ("src/a.ts", "knip:enumMembers"): 2,
            ("src/dead.ts", "knip:files"): 1,
        }, "a rule outside the unused family is not Check E's, and knip's dict-shaped types are summed")

    def test_negative_clean_tree_is_an_empty_scan_with_the_denominator(self):
        s = gate.run_ts_unreferenced(self.root)
        self.assertEqual((s.files, s.findings), (2, {}))

    def test_eslint_is_handed_every_tree_file_with_the_gate_config_and_no_repo_lookup(self):
        gate.run_ts_unreferenced(self.root)
        cmd = next(c for c in self.tools.calls if "eslint" in c[0])
        self.assertIn("--no-config-lookup", cmd)
        self.assertEqual(cmd[cmd.index("json") + 1:], ["src/a.ts", "src/b.tsx"])
        self.assertIn('args: "all"', gate._TS_UNREFERENCED_CONFIG)
        self.assertIn('argsIgnorePattern: "^_"', gate._TS_UNREFERENCED_CONFIG)

    def test_eslint_exit_2_raises(self):
        self.tools.eslint = _proc(2, "", "Oops! Something went wrong!")
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_unreferenced(self.root)

    def test_eslint_exit_127_from_a_missing_binary_raises(self):
        self.tools.eslint = _proc(127, "", "sh: 1: eslint: not found")
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_unreferenced(self.root)

    def test_eslint_parse_failure_is_exit_1_and_still_raises(self):
        """Measured: a syntax error is exit 1 with a `fatal` message, the same code as findings."""
        self.tools.eslint = lambda cmd, kw: _proc(1, json.dumps([
            _eslint_entry(self.root, "src/a.ts", [_FATAL]), _eslint_entry(self.root, "src/b.tsx", [])]))
        with self.assertRaises(gate.ScanOperationalError) as cm:
            gate.run_ts_unreferenced(self.root)
        self.assertIn("src/a.ts:2", str(cm.exception))

    def test_eslint_reporting_on_fewer_files_than_handed_raises(self):
        self.tools.eslint = lambda cmd, kw: _proc(0, json.dumps([_eslint_entry(self.root, "src/a.ts", [])]))
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_unreferenced(self.root)

    def test_eslint_non_json_raises(self):
        self.tools.eslint = _proc(1, "not json")
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_unreferenced(self.root)

    def test_knip_exit_2_raises(self):
        self.tools.knip = _proc(2, "", "ERROR: Unable to find package.json")
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_unreferenced(self.root)

    def test_knip_exit_1_without_its_json_shape_raises(self):
        """npx's 'could not determine executable' is also exit 1; the body is what tells them apart."""
        self.tools.knip = _proc(1, "npm error could not determine executable to run")
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_unreferenced(self.root)
        self.tools.knip = _proc(1, json.dumps({"not_issues": []}))
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_unreferenced(self.root)

    def test_missing_node_modules_raises_before_anything_runs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "a.ts").write_text("export const a = 1;\n")
            with self.assertRaises(gate.ScanOperationalError):
                gate.run_ts_unreferenced(root)
        self.assertEqual(self.tools.calls, [])

    def test_scratch_config_is_removed_after_the_run(self):
        gate.run_ts_unreferenced(self.root)
        self.assertEqual([p.name for p in (self.root / "node_modules").iterdir() if p.name.startswith(".sdlc-gate")], [])


# --- Check F: duplication ---------------------------------------------------------------------

class DuplicationTests(_Case):
    def test_positive_a_clone_is_keyed_by_the_tools_hash_with_every_occurrence(self):
        self.tools.jscpd = lambda cmd, kw: _Tools.write_jscpd(cmd, sources=2, clones=[
            ("48d932c1e4c628e4", [("src/a.ts", 2, 17), ("src/a.ts", 19, 34)]),
            ("48d932c1e4c628e4", [("src/a.ts", 19, 34), ("src/b.tsx", 5, 20)]),
            ("0afb6cdfc5b4513a", [("src/b.tsx", 40, 50), ("src/a.ts", 60, 70)])])
        s = gate.run_ts_duplication(self.root)
        self.assertEqual(s.files, 2)
        self.assertEqual(s.findings, {
            "48d932c1e4c628e4": [["src/a.ts", 2, 17], ["src/a.ts", 19, 34], ["src/b.tsx", 5, 20]],
            "0afb6cdfc5b4513a": [["src/a.ts", 60, 70], ["src/b.tsx", 40, 50]],
        }, "pairs of one clone merge under one hash, occurrences deduplicated and sorted")

    def test_negative_no_clones_is_empty_with_the_sources_denominator(self):
        s = gate.run_ts_duplication(self.root)
        self.assertEqual((s.files, s.findings), (2, {}))

    def test_sources_below_the_handed_count_is_healthy(self):
        """Measured: jscpd counts only files at least min-tokens/min-lines long (68 of 81)."""
        self.tools.jscpd = lambda cmd, kw: _Tools.write_jscpd(cmd, sources=1, clones=[])
        self.assertEqual(gate.run_ts_duplication(self.root).files, 1)

    def test_sources_above_the_handed_count_raises(self):
        self.tools.jscpd = lambda cmd, kw: _Tools.write_jscpd(cmd, sources=3, clones=[])
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_duplication(self.root)

    def test_invocation_carries_the_token_floor_and_whole_tree_flags(self):
        old = gate.DUP_MIN_TOKENS
        gate.DUP_MIN_TOKENS = 123
        try:
            gate.run_ts_duplication(self.root)
        finally:
            gate.DUP_MIN_TOKENS = old
        cmd = next(c for c in self.tools.calls if "jscpd" in c[0])
        self.assertEqual(cmd[cmd.index("--min-tokens") + 1], "123")
        self.assertIn("--no-gitignore", cmd)
        self.assertEqual(cmd[cmd.index("--reporters") + 1], "json,sarif")
        self.assertNotIn("--threshold", cmd, "exit-by-percentage would turn findings into did-not-run")
        self.assertNotIn("--baseline", cmd, "the engine does the delta, not the tool")

    def test_jscpd_non_zero_exit_raises(self):
        self.tools.jscpd = _proc(2, "", "error: unexpected argument")
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_duplication(self.root)

    def test_jscpd_exit_0_without_a_report_raises(self):
        self.tools.jscpd = _proc(0)
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_duplication(self.root)

    def test_reports_disagreeing_on_clone_count_raises(self):
        self.tools.jscpd = lambda cmd, kw: _Tools.write_jscpd(cmd, sources=2, clones=[
            ("48d932c1e4c628e4", [("src/a.ts", 2, 17), ("src/a.ts", 19, 34)])], json_extra=1)
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_duplication(self.root)

    def test_a_file_the_parser_rejects_refuses_before_jscpd_runs(self):
        """Measured: jscpd counts a file with a syntax error as a source and finds nothing in it."""
        self.tools.walker = _proc(2, json.dumps({"error": "src/a.ts:2: ':' expected."}))
        with self.assertRaises(gate.ScanOperationalError) as cm:
            gate.run_ts_duplication(self.root)
        self.assertIn("src/a.ts:2", str(cm.exception))
        self.assertFalse(any("jscpd" in c[0] for c in self.tools.calls))


# --- Check G: complexity ----------------------------------------------------------------------

class ComplexityTests(_Case):
    def _walker_with(self, functions):
        self.tools.walker = lambda cmd, kw: _proc(0, json.dumps(
            {"files": len(json.loads(Path(cmd[4]).read_text())), "functions": functions}))

    def test_positive_the_value_in_the_message_is_keyed_by_the_walkers_name_at_that_anchor(self):
        self._walker_with([["src/a.ts", "twisty", 2, 17], ["src/a.ts", "K.method", 15, 3],
                           ["src/b.tsx", 'describe("x").it("y")', 20, 41]])
        self.tools.eslint = lambda cmd, kw: _proc(1, json.dumps([
            _eslint_entry(self.root, "src/a.ts", [_sonar(22, 2, 17), _sonar(1, 15, 3)]),
            _eslint_entry(self.root, "src/b.tsx", [_sonar(3, 20, 41)])]))
        s = gate.run_ts_complexity(self.root)
        self.assertEqual(s.files, 2)
        self.assertEqual(s.findings, {("src/a.ts", "twisty"): 22, ("src/a.ts", "K.method"): 1,
                                      ("src/b.tsx", 'describe("x").it("y")'): 3})

    def test_an_anchor_the_table_lacks_is_kept_under_its_line_not_dropped(self):
        self._walker_with([])
        self.tools.eslint = lambda cmd, kw: _proc(1, json.dumps([
            _eslint_entry(self.root, "src/a.ts", [_sonar(30, 7, 9)]), _eslint_entry(self.root, "src/b.tsx", [])]))
        self.assertEqual(gate.run_ts_complexity(self.root).findings, {("src/a.ts", "<line 7>"): 30})

    def test_negative_no_report_means_every_function_is_at_zero(self):
        s = gate.run_ts_complexity(self.root)
        self.assertEqual((s.files, s.findings), (2, {}))

    def test_the_rule_runs_at_threshold_zero_so_the_gate_owns_the_threshold(self):
        self.assertIn('["error", 0]', gate._TS_COMPLEXITY_CONFIG)

    def test_eslint_exit_2_raises(self):
        self.tools.eslint = _proc(2, "", "Cannot find package 'eslint-plugin-sonarjs'")
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_complexity(self.root)

    def test_parse_failure_raises(self):
        self.tools.eslint = lambda cmd, kw: _proc(1, json.dumps([
            _eslint_entry(self.root, "src/a.ts", [_FATAL]), _eslint_entry(self.root, "src/b.tsx", [])]))
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_complexity(self.root)

    def test_walker_refusal_raises(self):
        self.tools.walker = _proc(2, json.dumps({"error": "typescript not resolvable"}))
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_complexity(self.root)

    def test_a_message_without_the_number_raises(self):
        """The format this parser reads was captured from sonarjs 4.2; a change must not read as 0."""
        self.tools.eslint = lambda cmd, kw: _proc(1, json.dumps([
            _eslint_entry(self.root, "src/a.ts", [{"ruleId": "sonarjs/cognitive-complexity", "line": 2, "column": 17,
                                                  "message": "Refactor this function."}]),
            _eslint_entry(self.root, "src/b.tsx", [])]))
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_complexity(self.root)


# --- Check H: abstractions --------------------------------------------------------------------

class AbstractionsTests(_Case):
    def _walker_with(self, abstractions):
        self.tools.walker = lambda cmd, kw: _proc(0, json.dumps(
            {"files": len(json.loads(Path(cmd[4]).read_text())), "abstractions": abstractions}))

    def test_positive_abstract_classes_always_and_hierarchies_with_a_member(self):
        self._walker_with([["src/a.ts", "PlantedContract", "interface", 1],
                           ["src/a.ts", "PlantedBase", "abstract", 0],
                           ["src/a.ts", "Shape", "interface", 3],
                           ["src/a.ts", "Plain", "class", 1],
                           ["src/b.tsx", "NS.Inner", "interface", 1]])
        s = gate.run_ts_abstractions(self.root)
        self.assertEqual(s.files, 2)
        self.assertEqual(s.findings, {("src/a.ts", "PlantedContract"): 1, ("src/a.ts", "PlantedBase"): 0,
                                      ("src/a.ts", "Shape"): 3, ("src/a.ts", "Plain"): 1, ("src/b.tsx", "NS.Inner"): 1})

    def test_a_props_interface_and_an_unextended_class_are_not_abstractions(self):
        """Structural typing: an interface nothing implements is a type, and reporting it at 0 would
        block nearly every new component. A concrete class nobody extends is just a class."""
        self._walker_with([["src/b.tsx", "PanelProps", "interface", 0], ["src/a.ts", "MockSource", "class", 0]])
        self.assertEqual(gate.run_ts_abstractions(self.root).findings, {})

    def test_negative_a_tree_without_hierarchies_is_empty_with_the_denominator(self):
        s = gate.run_ts_abstractions(self.root)
        self.assertEqual((s.files, s.findings), (2, {}))

    def test_walker_refusal_raises(self):
        self.tools.walker = _proc(2, json.dumps({"error": "src/a.ts:2: ':' expected."}))
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_abstractions(self.root)

    def test_walker_examining_fewer_files_than_handed_raises(self):
        self.tools.walker = _proc(0, json.dumps({"files": 1, "abstractions": []}))
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_abstractions(self.root)

    def test_walker_dying_without_json_raises(self):
        self.tools.walker = _proc(1, "", "node: bad option")
        with self.assertRaises(gate.ScanOperationalError):
            gate.run_ts_abstractions(self.root)

    def test_missing_node_raises(self):
        with mock.patch.object(gate.shutil, "which", return_value=None):
            with self.assertRaises(gate.ScanOperationalError):
                gate.run_ts_abstractions(self.root)

    def test_the_walker_is_handed_every_tree_file_and_run_from_under_node_modules(self):
        seen = {}

        def walker(cmd, kw):
            seen["listing"] = json.loads(Path(cmd[4]).read_text())
            seen["script"] = Path(cmd[1]).read_text()
            return _proc(0, json.dumps({"files": 2, "abstractions": []}))

        self.tools.walker = walker
        gate.run_ts_abstractions(self.root)
        cmd = next(c for c in self.tools.calls if c[0].endswith("node"))
        self.assertEqual(cmd[2], "abstractions")
        self.assertTrue(cmd[1].startswith(str(self.root / "node_modules")), cmd[1])
        self.assertEqual(sorted(Path(f).name for f in seen["listing"]), ["a.ts", "b.tsx"])
        self.assertEqual(seen["script"], gate._TS_WALKER)
        # The scratch dir under node_modules is gone once the run is over.
        self.assertEqual([p.name for p in (self.root / "node_modules").iterdir() if p.name.startswith(".sdlc-gate")], [])


# --- The four are wired on the toolchain ----------------------------------------------------------

class WiringTests(unittest.TestCase):
    def test_typescript_overrides_all_four(self):
        tc = gate.TypeScriptToolchain()
        for m, fn in (("unreferenced", "run_ts_unreferenced"), ("duplication", "run_ts_duplication"),
                      ("complexity", "run_ts_complexity"), ("abstractions", "run_ts_abstractions")):
            with mock.patch.object(gate, fn, return_value=gate.Scan("x", 1, {})) as p:
                self.assertIs(getattr(tc, m)(Path(".")).tool, "x")
            p.assert_called_once()

    def test_capture_records_all_four_as_wired(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td)
            tools = _Tools(root)
            with mock.patch.object(gate.subprocess, "run", side_effect=tools.run), \
                    mock.patch.object(gate.shutil, "which", side_effect=lambda n: "/fake/bin/node" if n == "node" else None):
                out = gate._capture_agent_scans(gate.TypeScriptToolchain(), root)
        self.assertEqual({k: v["files"] for k, v in out.items()}, {"E": 2, "F": 2, "G": 2, "H": 2})

    def test_an_empty_tree_reports_zero_files_and_runs_no_tool(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, files={})
            with mock.patch.object(gate.subprocess, "run", side_effect=AssertionError("no tool should run")):
                for fn in (gate.run_ts_unreferenced, gate.run_ts_duplication, gate.run_ts_complexity,
                           gate.run_ts_abstractions):
                    self.assertEqual(fn(root).files, 0)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for the Go runners of Checks E-H in sdlc-gate.py — stdlib unittest, run: python3 <this file>.

The tool outputs here were CAPTURED from golangci-lint 2.12.2 and go 1.26.4 on a planted module
(a single-implementor interface, an unused helper, an unused parameter, an always-nil result, a
cognitive-complexity-18 function, and a verbatim 17-line clone) on 2026-09-10, then trimmed.
Every subprocess is mocked, dispatched on argv, so the suite runs on a box without either tool.

For each check: a positive control, a negative control, and the did-not-run refusals — the one
that matters most being the MEASURED fail-open, a syntax error that leaves golangci-lint at exit
1 with one `typecheck` issue and every other linter's findings gone.
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


# --- Captured tool output, and a subprocess that serves it by argv --------------------------

def _proc(rc: int, stdout: str = "", stderr: str = ""):
    return types.SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr)


def _golangci_doc(issues: list[dict], report: dict | None = None) -> str:
    """The JSON document golangci-lint writes, followed by the human summary it appends even
    with `--output.json.path stdout` (captured; the parser must stop at the first document)."""
    return json.dumps({"Issues": issues or None, "Report": report or {"Linters": [{"Name": "unused"}]}}) + \
        "\n2 issues:\n* unused: 2\n"


def _issue(linter: str, text: str, file: str, line: int, line_range: dict | None = None) -> dict:
    d = {"FromLinter": linter, "Text": text, "Severity": "", "SourceLines": [""],
         "Pos": {"Filename": file, "Offset": 0, "Line": line, "Column": 1},
         "ExpectNoLint": False, "ExpectedNoLintLinter": ""}
    if line_range:
        d["LineRange"] = line_range
    return d


def _go_list_doc(root: Path, tests: bool = True) -> str:
    """`go list -json` writes objects back to back, no array, one per package."""
    pkg = {"Dir": str(root / "store"), "GoFiles": ["store.go", "complex.go", "dup.go"]}
    if tests:
        pkg["TestGoFiles"] = ["store_test.go"]
    other = {"Dir": str(root / "cmd"), "GoFiles": ["main.go"]}
    return json.dumps(pkg, indent=1) + "\n" + json.dumps(other, indent=1) + "\n"


class _Dispatcher:
    """A subprocess.run stand-in keyed on what is being run; records every invocation and the
    config file golangci-lint was pointed at, since that file is gone by the time run returns."""

    def __init__(self, root: Path, golangci=None, go_list=None, go_run=None):
        self.root = root
        self.golangci = golangci if golangci is not None else _proc(0, _golangci_doc([]))
        self.go_list = go_list if go_list is not None else _proc(0, _go_list_doc(root))
        self.go_run = go_run if go_run is not None else _proc(0, json.dumps({"files": 4, "interfaces": []}))
        self.calls: list[list[str]] = []
        self.configs: list[str] = []

    def __call__(self, cmd, **kw):
        self.calls.append(list(cmd))
        if cmd[:2] == ["golangci-lint", "run"]:
            self.configs.append(Path(cmd[cmd.index("--config") + 1]).read_text())
            r = self.golangci
        elif cmd[:2] == ["go", "list"]:
            r = self.go_list
        elif cmd[:2] == ["go", "run"]:
            r = self.go_run
        else:  # pragma: no cover
            raise AssertionError(f"unexpected command {cmd}")
        if isinstance(r, Exception):
            raise r
        return r


def _with(disp: _Dispatcher):
    return mock.patch.object(gate.subprocess, "run", side_effect=disp)


class _GoCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()
        (self.root / "store").mkdir()
        (self.root / "go.mod").write_text("module example.com/planted\n\ngo 1.26\n")

    def tearDown(self):
        self._td.cleanup()

    def abs(self, rel: str) -> str:
        return str(self.root / rel)


# --- Check E: unreferenced ------------------------------------------------------------------

_E_ISSUES = [
    ("revive", "unused-parameter: parameter 'b' seems to be unused, consider removing or renaming it as _", 34),
    ("unparam", "alwaysNil - result 1 (error) is always nil", 37),
    ("unused", "type sinkA is unused", 21),
    ("unused", "type sinkB is unused", 22),
    ("unused", "func sinkA.Write is unused", 24),
    ("unused", "func helperNeverCalled is unused", 31),
]


class UnreferencedTests(_GoCase):
    def _issues(self):
        return [_issue(l, t, self.abs("store/store.go"), n) for l, t, n in _E_ISSUES]

    def test_positive_planted_smells_are_keyed_by_linter_and_kind(self):
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(self._issues())))
        with _with(disp):
            s = gate.go_unreferenced(self.root)
        self.assertEqual(s.findings, {
            ("store/store.go", "revive/unused-parameter"): 1,
            ("store/store.go", "unparam/result"): 1,
            ("store/store.go", "unused/type"): 2,
            ("store/store.go", "unused/func"): 2,
        })
        self.assertEqual(s.files, 5, "GoFiles + TestGoFiles across both packages")

    def test_negative_clean_tree_is_empty_with_a_nonzero_denominator(self):
        disp = _Dispatcher(self.root, golangci=_proc(0, _golangci_doc([])))
        with _with(disp):
            s = gate.go_unreferenced(self.root)
        self.assertEqual(s.findings, {})
        self.assertEqual(s.files, 5)

    def test_the_config_disables_every_count_truncation(self):
        """The three defaults that each silently cap a count, and the linters E stands on."""
        disp = _Dispatcher(self.root)
        with _with(disp):
            gate.go_unreferenced(self.root)
        cfg = disp.configs[0]
        for line in ("max-issues-per-linter: 0", "max-same-issues: 0", "uniq-by-line: false",
                     "- unused", "- unparam", "- revive", "name: unused-parameter", 'version: "2"'):
            self.assertIn(line, cfg)
        self.assertNotIn("unused-receiver", cfg, "measured at 352 healthy hits on the corpus")
        self.assertNotIn("check-exported", cfg, "measured at 15 exported interface methods")
        lint = next(c for c in disp.calls if c[0] == "golangci-lint")
        self.assertIn("abs", lint, "paths come back relative to the config dir otherwise")
        self.assertIn("--allow-parallel-runners", lint)

    def test_did_not_run_exit_3_raises(self):
        disp = _Dispatcher(self.root, golangci=_proc(3, "", "Error: can't load config"))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_unreferenced(self.root)

    def test_did_not_run_missing_binary_raises(self):
        disp = _Dispatcher(self.root, golangci=FileNotFoundError("golangci-lint"))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_unreferenced(self.root)

    def test_did_not_run_non_json_raises(self):
        disp = _Dispatcher(self.root, golangci=_proc(1, "level=error msg=oops"))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_unreferenced(self.root)

    def test_did_not_run_a_linter_warning_raises(self):
        doc = _golangci_doc([], report={"Warnings": [{"Tag": "runner", "Text": "Can't run linter unparam: boom"}]})
        disp = _Dispatcher(self.root, golangci=_proc(0, doc))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_unreferenced(self.root)

    def test_did_not_run_go_list_failure_is_not_a_zero_denominator(self):
        disp = _Dispatcher(self.root, go_list=_proc(1, "", "go: cannot find main module"))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_unreferenced(self.root)


# --- Check G: complexity --------------------------------------------------------------------

class ComplexityTests(_GoCase):
    def test_positive_functions_and_methods_are_keyed_by_name(self):
        issues = [
            _issue("gocognit", "cognitive complexity 18 of func `Tangled` is high (> 0)", self.abs("store/complex.go"), 4),
            _issue("gocognit", "cognitive complexity 1 of func `Simple` is high (> 0)", self.abs("store/complex.go"), 29),
            _issue("gocognit", "cognitive complexity 8 of func `(*memStore).Get` is high (> 0)", self.abs("store/store.go"), 18),
        ]
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(issues)))
        with _with(disp):
            s = gate.go_complexity(self.root)
        self.assertEqual(s.findings, {("store/complex.go", "Tangled"): 18,
                                      ("store/complex.go", "Simple"): 1,
                                      ("store/store.go", "(*memStore).Get"): 8})
        self.assertIn("min-complexity: 0", disp.configs[0])

    def test_a_repeated_init_keeps_the_larger_value(self):
        issues = [
            _issue("gocognit", "cognitive complexity 2 of func `init` is high (> 0)", self.abs("store/a.go"), 3),
            _issue("gocognit", "cognitive complexity 7 of func `init` is high (> 0)", self.abs("store/a.go"), 30),
        ]
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(issues)))
        with _with(disp):
            s = gate.go_complexity(self.root)
        self.assertEqual(s.findings, {("store/a.go", "init"): 7})

    def test_negative_clean_tree(self):
        disp = _Dispatcher(self.root, golangci=_proc(0, _golangci_doc([])))
        with _with(disp):
            s = gate.go_complexity(self.root)
        self.assertEqual(s.findings, {})
        self.assertGreater(s.files, 0)

    def test_did_not_run_the_measured_fail_open_a_syntax_error_at_exit_1(self):
        """One broken file: exit 1, one typecheck issue, zero gocognit rows for the whole tree.
        Read naively this is 'no complex functions' — the reading the check exists to refuse."""
        issues = [_issue("typecheck", "expected ')', found '{'", self.abs("store/store.go"), 129)]
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(issues)))
        with _with(disp), self.assertRaises(gate.ScanOperationalError) as cm:
            gate.go_complexity(self.root)
        self.assertIn("typecheck", str(cm.exception))

    def test_did_not_run_unrecognised_message_raises_rather_than_dropping(self):
        issues = [_issue("gocognit", "some new message shape for `F`", self.abs("store/a.go"), 1)]
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(issues)))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_complexity(self.root)

    def test_did_not_run_timeout_exit_4_raises(self):
        disp = _Dispatcher(self.root, golangci=_proc(4, "", "Timeout exceeded"))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_complexity(self.root)


# --- Check F: duplication -------------------------------------------------------------------

_RENDER_A = '''func RenderA(items []string, title string) string {
	var b strings.Builder
	b.WriteString("# ")
	b.WriteString(title)
	for i, it := range items {
		if it == "" {
			continue
		}
		b.WriteString(strings.Repeat(" ", i))
		b.WriteString(strings.ToUpper(it))
	}
	return b.String()
}
'''
_RENDER_B = _RENDER_A.replace("RenderA", "RenderB").replace("items", "rows").replace("title", "heading") \
    .replace(" b.", " sb.").replace("var b ", "var sb ").replace("return b.", "return sb.").replace('"# "', '"## "')


class DuplicationTests(_GoCase):
    def _write_dup(self, blank_lines_before_b: int = 1) -> tuple[int, int]:
        """dup.go with RenderA at lines 5-17 and RenderB after `blank_lines_before_b` blanks."""
        header = "package store\n\nimport \"strings\"\n\n"
        text = header + _RENDER_A + "\n" * blank_lines_before_b + _RENDER_B
        (self.root / "store" / "dup.go").write_text(text)
        b_start = 5 + _RENDER_A.count("\n") + blank_lines_before_b
        return b_start, b_start + _RENDER_A.count("\n") - 1

    def _ring(self, a: tuple[int, int], b: tuple[int, int]) -> list[dict]:
        f = self.abs("store/dup.go")
        return [
            _issue("dupl", f"{a[0]}-{a[1]} lines are duplicate of `store/dup.go:{b[0]}-{b[1]}`", f, a[0],
                   {"From": a[0], "To": a[1]}),
            _issue("dupl", f"{b[0]}-{b[1]} lines are duplicate of `store/dup.go:{a[0]}-{a[1]}`", f, b[0],
                   {"From": b[0], "To": b[1]}),
        ]

    def _pair_fingerprint(self) -> str:
        b = self._write_dup()
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(self._ring((5, 17), b))))
        with _with(disp):
            s = gate.go_duplication(self.root)
        self.assertEqual(len(s.findings), 1)
        (fp, occs), = s.findings.items()
        self.assertEqual(occs, [["store/dup.go", 5, 17], ["store/dup.go", b[0], b[1]]])
        self.assertEqual(s.files, 4, "tests are not loaded for F: GoFiles only")
        self.assertIn("tests: false", disp.configs[0])
        self.assertIn(f"threshold: {gate.DUP_MIN_TOKENS}", disp.configs[0])
        return fp

    def test_positive_a_reported_pair_is_one_fingerprint_with_both_occurrences(self):
        self.assertEqual(len(self._pair_fingerprint()), 24)

    def test_fingerprint_survives_a_line_shift_a_rename_and_a_changed_literal(self):
        """The baseline's clone must not read as new on the branch because code above it moved,
        a variable in one copy was renamed, or a constant changed: those are the edits that
        happen near a clone without creating one."""
        fp_before = self._pair_fingerprint()
        b = self._write_dup(blank_lines_before_b=4)
        text = (self.root / "store" / "dup.go").read_text().replace("sb.", "out.").replace("var sb ", "var out ") \
            .replace('"## "', '"### "')
        (self.root / "store" / "dup.go").write_text(text)
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(self._ring((5, 17), b))))
        with _with(disp):
            s = gate.go_duplication(self.root)
        self.assertEqual(list(s.findings), [fp_before])

    def test_a_third_copy_is_a_new_fingerprint(self):
        """The engine skips a fingerprint the baseline had; a pair growing to a triple must not
        hide behind the pair's fingerprint."""
        fp_pair = self._pair_fingerprint()
        b = self._write_dup()
        c_text = _RENDER_A.replace("RenderA", "RenderC")
        path = self.root / "store" / "dup.go"
        path.write_text(path.read_text() + "\n" + c_text)
        c = (b[1] + 2, b[1] + 2 + _RENDER_A.count("\n") - 1)
        f = self.abs("store/dup.go")
        ring = [
            _issue("dupl", f"5-17 lines are duplicate of `store/dup.go:{b[0]}-{b[1]}`", f, 5, {"From": 5, "To": 17}),
            _issue("dupl", f"{b[0]}-{b[1]} lines are duplicate of `store/dup.go:{c[0]}-{c[1]}`", f, b[0], {"From": b[0], "To": b[1]}),
            _issue("dupl", f"{c[0]}-{c[1]} lines are duplicate of `store/dup.go:5-17`", f, c[0], {"From": c[0], "To": c[1]}),
        ]
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(ring)))
        with _with(disp):
            s = gate.go_duplication(self.root)
        (fp, occs), = s.findings.items()
        self.assertNotEqual(fp, fp_pair)
        self.assertEqual(len(occs), 3)

    def test_negative_clean_tree(self):
        self._write_dup()
        disp = _Dispatcher(self.root, golangci=_proc(0, _golangci_doc([])))
        with _with(disp):
            s = gate.go_duplication(self.root)
        self.assertEqual(s.findings, {})
        self.assertEqual(s.files, 4)

    def test_did_not_run_exit_5_no_go_files_raises(self):
        disp = _Dispatcher(self.root, golangci=_proc(5, "", "no go files to analyze"))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_duplication(self.root)

    def test_did_not_run_syntax_error_raises(self):
        issues = [_issue("typecheck", "expected ';', found 'EOF'", self.abs("store/dup.go"), 40)]
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(issues)))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_duplication(self.root)

    def test_did_not_run_unrecognised_message_raises(self):
        issues = [_issue("dupl", "duplicate somewhere", self.abs("store/dup.go"), 5)]
        disp = _Dispatcher(self.root, golangci=_proc(1, _golangci_doc(issues)))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_duplication(self.root)


class NormalizedTokensTests(unittest.TestCase):
    def test_identifiers_literals_comments_and_whitespace_normalize_keywords_and_operators_stay(self):
        a = gate._go_normalized_tokens('if x > 10 { // note\n\treturn fmt.Sprintf("a%d", x) }')
        b = gate._go_normalized_tokens('if y >= 2 { /* other */ return log.Printf("zz", y) }')
        self.assertNotEqual(a, b, "operator differs: > vs >=")
        c = gate._go_normalized_tokens('if y > 2 { /* other */ return log.Printf("zz", y) }')
        self.assertEqual(a, c)
        self.assertEqual(a, "if I > L { return I . I ( L , I ) }")

    def test_raw_strings_runes_and_exponents_are_single_literals(self):
        self.assertEqual(gate._go_normalized_tokens("x := `a // b` + 'c' + 1.5e-3"), "I := L + L + L")


# --- Check H: abstractions ------------------------------------------------------------------

class AbstractionsTests(_GoCase):
    def _go_list_h(self):
        return _proc(0, json.dumps({"ImportPath": "example.com/planted/store", "Dir": str(self.root / "store"),
                                    "GoFiles": ["store.go"], "Export": "/cache/x-d",
                                    "Module": {"Main": True}}) + "\n")

    def test_positive_interfaces_are_keyed_with_their_implementor_count(self):
        out = json.dumps({"files": 4, "interfaces": [
            {"file": "store/store.go", "name": "Sink", "implementors": 2},
            {"file": "store/store.go", "name": "Store", "implementors": 1}]})
        disp = _Dispatcher(self.root, go_list=self._go_list_h(), go_run=_proc(0, out))
        with _with(disp):
            s = gate.go_abstractions(self.root)
        self.assertEqual(s.findings, {("store/store.go", "Sink"): 2, ("store/store.go", "Store"): 1})
        self.assertEqual(s.files, 4)
        run = next(c for c in disp.calls if c[:2] == ["go", "run"])
        self.assertTrue(run[2].endswith(".go"))
        listing = next(c for c in disp.calls if c[:2] == ["go", "list"])
        for flag in ("-export", "-deps", "-test"):
            self.assertIn(flag, listing)

    def test_negative_no_interfaces_is_empty_with_the_files_it_read(self):
        disp = _Dispatcher(self.root, go_list=self._go_list_h(),
                           go_run=_proc(0, json.dumps({"files": 3, "interfaces": []})))
        with _with(disp):
            s = gate.go_abstractions(self.root)
        self.assertEqual(s.findings, {})
        self.assertEqual(s.files, 3)

    def test_did_not_run_type_error_exits_nonzero_and_raises(self):
        disp = _Dispatcher(self.root, go_list=self._go_list_h(),
                           go_run=_proc(1, "", "3 type errors; first: store.go:9:2: undefined: Foo\nexit status 3"))
        with _with(disp), self.assertRaises(gate.ScanOperationalError) as cm:
            gate.go_abstractions(self.root)
        self.assertIn("undefined: Foo", str(cm.exception))

    def test_did_not_run_no_go_toolchain_raises(self):
        disp = _Dispatcher(self.root, go_list=FileNotFoundError("go"))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_abstractions(self.root)

    def test_did_not_run_unreadable_result_raises(self):
        disp = _Dispatcher(self.root, go_list=self._go_list_h(), go_run=_proc(0, "not json"))
        with _with(disp), self.assertRaises(gate.ScanOperationalError):
            gate.go_abstractions(self.root)

    def test_the_program_source_is_what_go_run_receives(self):
        seen = {}

        def capture(cmd, **kw):
            if cmd[:2] == ["go", "run"]:
                seen["src"] = Path(cmd[2]).read_text()
                seen["stdin"] = kw.get("input")
                return _proc(0, json.dumps({"files": 1, "interfaces": []}))
            return self._go_list_h()

        with mock.patch.object(gate.subprocess, "run", side_effect=capture):
            gate.go_abstractions(self.root)
        self.assertTrue(seen["src"].startswith("package main"))
        self.assertIn("types.Implements", seen["src"])
        self.assertIn('"ImportPath": "example.com/planted/store"', seen["stdin"])


# --- The toolchain is wired -----------------------------------------------------------------

class GoToolchainWiringTests(_GoCase):
    def test_all_four_checks_are_wired_and_captured_with_denominators(self):
        disp = _Dispatcher(self.root)
        with _with(disp):
            out = gate._capture_agent_scans(gate.GoToolchain(), self.root)
        for check in "EFGH":
            self.assertNotIn("not_wired", out[check], check)
            self.assertGreater(out[check]["files"], 0, check)

    def test_go_list_stream_parser_reads_back_to_back_objects(self):
        self.assertEqual(gate._go_json_stream('{"a": 1}\n{"b": [2]}\n'), [{"a": 1}, {"b": [2]}])
        self.assertEqual(gate._go_json_stream(""), [])


if __name__ == "__main__":
    unittest.main()

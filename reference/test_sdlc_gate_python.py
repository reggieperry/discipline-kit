#!/usr/bin/env python3
"""Tests for the PYTHON runners of Checks E-H in sdlc-gate.py — stdlib unittest, run:
python3 <this file>. The engine half is in test_sdlc_gate_contract.py; this file pins what the
Python toolchain feeds it: ruff (E), PMD CPD (F), complexipy (G) and the stdlib-ast scan (H).

The three shelled tools are mocked at `subprocess.run`, so the suite runs on a box without any
of them; each fake answers in the exact shape measured from the pinned version (ruff 0.16.7,
complexipy 8.0.1, PMD 7.27.0 — see the region's comments). For every wired check there is a
positive control (a planted smell is found), a negative control (clean input finds nothing, with
the denominator intact), and a did-not-run test (the tool missing, erroring, or pointed at a
syntax error raises ScanOperationalError and does NOT read as empty).
"""

from __future__ import annotations

import importlib.util
import json
import os
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


# --- Scratch trees and tool fakes ------------------------------------------------------------

_CLEAN = "def f(a):\n    return a\n"
_CLONE_BODY = "".join(f"    total = total + item_{i} * factor_{i} - offset_{i}\n" for i in range(20))
_CLONE = "def compute(items, factor):\n    total = 0\n" + _CLONE_BODY + "    return total\n"


class _Tree:
    """A temp dir with a resolved root (macOS-style symlinked temp dirs would otherwise defeat
    `relative_to`) and a writer that creates parents."""

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()
        return self

    def __exit__(self, *exc):
        self._td.cleanup()

    def write(self, rel: str, text: str) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p


def _arg_after(cmd: list, flag: str) -> str:
    return cmd[cmd.index(flag) + 1]


def _ruff_row(root: Path, rel: str, code: str, row: int = 1, message: str = "") -> dict:
    return {"filename": str(root / rel), "code": code, "message": message,
            "location": {"row": row, "column": 1}}


def _cpd_xml(root: Path, files: list[str], dups: list[dict] = (), errors: list[str] = ()) -> str:
    """The 7.27.0 report shape: namespaced, every analysed file listed, then duplications."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<pmd-cpd xmlns="https://pmd-code.org/schema/cpd-report" pmdVersion="7.27.0">']
    for f in files:
        out.append(f'   <file path="{root / f}" totalNumberOfTokens="10"/>')
    for e in errors:
        out.append(f'   <error filename="{root / e}" msg="LexException: Lexical error in {e}"/>')
    for d in dups:
        out.append(f'   <duplication lines="{d["lines"]}" tokens="{d["tokens"]}">')
        for f, line, endline, col, endcol in d["occ"]:
            out.append(f'      <file path="{root / f}" line="{line}" endline="{endline}" '
                       f'column="{col}" endcolumn="{endcol}"/>')
        out.append('      <codefragment><![CDATA[irrelevant]]></codefragment>')
        out.append('   </duplication>')
    out.append('</pmd-cpd>')
    return "\n".join(out)


def _fake_run(*, ruff=None, cpd=None, cx=None):
    """A `subprocess.run` that answers per tool. Each value is either a (returncode, stdout,
    stderr) triple (ruff, whose JSON is stdout) or a (returncode, report_text, stderr) triple
    written to the tool's report/output path (cpd's --report-file, complexipy's --output). A
    tool given None makes the fake raise, so a test that did not expect a shell-out notices."""
    seen: list[list] = []

    def run(cmd, **kw):
        seen.append(list(cmd))
        tool = " ".join(cmd[:2])
        if tool.startswith("uvx ruff@"):
            assert ruff is not None, f"unexpected ruff invocation: {cmd}"
            rc, out, err = ruff
            return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)
        if tool.startswith("uvx complexipy@"):
            assert cx is not None, f"unexpected complexipy invocation: {cmd}"
            rc, report, err = cx
            if report is not None:
                Path(_arg_after(cmd, "--output")).write_text(report)
            return types.SimpleNamespace(returncode=rc, stdout="", stderr=err)
        if cmd[1:2] == ["cpd"]:
            assert cpd is not None, f"unexpected cpd invocation: {cmd}"
            rc, report, err = cpd
            if report is not None:
                Path(_arg_after(cmd, "--report-file")).write_text(report)
            return types.SimpleNamespace(returncode=rc, stdout="", stderr=err)
        raise AssertionError(f"unexpected subprocess: {cmd}")

    run.seen = seen
    return run


# --- The precondition every runner shares ---------------------------------------------------

class ParsePreconditionTests(unittest.TestCase):
    def test_a_syntax_error_anywhere_is_operational_and_names_the_file(self):
        with _Tree() as t:
            t.write("ok.py", _CLEAN)
            t.write("pkg/bad.py", "def x(:\n    pass\n")
            with self.assertRaises(gate.ScanOperationalError) as cm:
                gate._python_files(t.root)
            self.assertIn("pkg/bad.py", str(cm.exception))

    def test_a_nul_byte_is_operational_not_skipped(self):
        with _Tree() as t:
            (t.root / "nul.py").write_bytes(b"x = 1\n\x00\n")
            with self.assertRaises(gate.ScanOperationalError):
                gate._python_files(t.root)

    def test_negative_control_every_walked_file_is_listed_sorted(self):
        with _Tree() as t:
            t.write("b.py", _CLEAN)
            t.write("a/z.py", _CLEAN)
            t.write(".hidden/skipped.py", "def x(:\n")   # hidden dirs are outside the walk
            t.write(".venv/lib/skipped.py", "def x(:\n")
            self.assertEqual(gate._python_files(t.root), ["a/z.py", "b.py"])

    def test_an_unspawnable_tool_is_operational_not_a_traceback(self):
        """No `uvx` on PATH is FileNotFoundError from subprocess.run, not an exit code."""
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            with mock.patch.object(gate.subprocess, "run", side_effect=FileNotFoundError(2, "No such file", "uvx")), \
                    mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"):
                for fn in (gate.run_ruff_unreferenced, gate.run_cpd, gate.run_complexipy):
                    with self.assertRaises(gate.ScanOperationalError, msg=fn.__name__) as cm:
                        fn(t.root)
                    self.assertIn("cannot run", str(cm.exception))

    def test_runners_refuse_before_shelling_out(self):
        """The tool is never asked about a tree that does not parse: its answer would be partial."""
        with _Tree() as t:
            t.write("bad.py", "def x(:\n")
            run = _fake_run()
            with mock.patch.object(gate.subprocess, "run", side_effect=run):
                for fn in (gate.run_ruff_unreferenced, gate.run_cpd, gate.run_complexipy):
                    with self.assertRaises(gate.ScanOperationalError, msg=fn.__name__):
                        fn(t.root)
            self.assertEqual(run.seen, [], "no tool was invoked")


# --- Check E: ruff ---------------------------------------------------------------------------

class RuffUnreferencedTests(unittest.TestCase):
    def test_positive_control_planted_unused_import_is_counted(self):
        with _Tree() as t:
            t.write("mod.py", "import os\n\ndef f(a):\n    return a\n")
            t.write("clean.py", _CLEAN)
            body = json.dumps([_ruff_row(t.root, "mod.py", "F401", 1, "`os` imported but unused")])
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(ruff=(1, body, ""))):
                s = gate.run_ruff_unreferenced(t.root)
        self.assertEqual(s.tool, "ruff")
        self.assertEqual(s.files, 2, "the walk is the denominator, not the findings")
        self.assertEqual(s.findings, {("mod.py", "F401"): 1})

    def test_negative_control_clean_tree_is_empty_with_denominator(self):
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            t.write("b/c.py", _CLEAN)
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(ruff=(0, "[]", ""))):
                s = gate.run_ruff_unreferenced(t.root)
        self.assertEqual(s.findings, {})
        self.assertEqual(s.files, 2)

    def test_exit_2_is_operational(self):
        """The message names the exit code: with an empty stdout the JSON guard would raise too,
        and a first draft of this test passed on that guard alone."""
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            fake = _fake_run(ruff=(2, "", "error: unrecognized option"))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.run_ruff_unreferenced(t.root)
        self.assertIn("exited 2", str(cm.exception))

    def test_uvx_resolution_failure_exit_1_empty_stdout_is_operational(self):
        """uvx failing to fetch ruff exits 1 with nothing on stdout — the same code ruff uses for
        'findings'. A clean ruff prints `[]`, so an empty body is a tool that did not run."""
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            fake = _fake_run(ruff=(1, "", "No solution found when resolving tool dependencies"))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.run_ruff_unreferenced(t.root)

    def test_failed_to_lint_warning_is_operational_even_at_exit_0(self):
        """Measured: a path ruff cannot read is exit 0, `[]`, and a stderr warning."""
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            fake = _fake_run(ruff=(0, "[]", "warning: Failed to lint a.py: No such file or directory"))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.run_ruff_unreferenced(t.root)

    def test_invalid_syntax_finding_is_operational_not_a_count(self):
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            body = json.dumps([_ruff_row(t.root, "a.py", "invalid-syntax", 1, "Expected `)`")])
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(ruff=(1, body, ""))):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.run_ruff_unreferenced(t.root)

    def test_missing_uvx_exit_127_is_operational(self):
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            fake = _fake_run(ruff=(127, "", "uvx: command not found"))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.run_ruff_unreferenced(t.root)
        self.assertIn("exited 127", str(cm.exception))

    def test_invocation_is_isolated_pinned_and_explicit(self):
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            fake = _fake_run(ruff=(0, "[]", ""))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake):
                gate.run_ruff_unreferenced(t.root)
        cmd = fake.seen[0]
        self.assertEqual(cmd[:2], ["uvx", gate._PY_RUFF])
        self.assertIn("--isolated", cmd, "the repo's ruff config must not make E blind")
        self.assertEqual(_arg_after(cmd, "--select"), gate._PY_E_RULES)
        self.assertNotIn("ARG005", gate._PY_E_RULES, "a lambda's parameters are its caller's")
        self.assertEqual(cmd[-1], "a.py", "explicit files: the walk is the denominator")
        self.assertIn("__init__.py:F401", cmd)

    def test_override_of_an_in_tree_ancestor_is_dropped(self):
        """ruff flags an unused parameter on an override it cannot see; the signature is the
        ancestor's, so the finding is not the branch's smell."""
        with _Tree() as t:
            t.write("base.py", "class Base:\n    def detect(self, root):\n        return False\n")
            t.write("impl.py", "from base import Base\n\nclass Impl(Base):\n    def detect(self, root):\n"
                               "        return True\n")
            body = json.dumps([_ruff_row(t.root, "impl.py", "ARG002", 4, "Unused method argument: `root`")])
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(ruff=(1, body, ""))):
                s = gate.run_ruff_unreferenced(t.root)
        self.assertEqual(s.findings, {})

    def test_negative_control_a_method_with_no_ancestor_keeps_its_finding(self):
        with _Tree() as t:
            t.write("impl.py", "class Impl:\n    def detect(self, root):\n        return True\n")
            body = json.dumps([_ruff_row(t.root, "impl.py", "ARG002", 2, "Unused method argument: `root`")])
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(ruff=(1, body, ""))):
                s = gate.run_ruff_unreferenced(t.root)
        self.assertEqual(s.findings, {("impl.py", "ARG002"): 1})

    def test_negative_control_an_out_of_tree_base_cannot_vouch(self):
        with _Tree() as t:
            t.write("impl.py", "import unittest\n\nclass T(unittest.TestCase):\n"
                               "    def helper(self, x):\n        return 1\n")
            body = json.dumps([_ruff_row(t.root, "impl.py", "ARG002", 4, "Unused method argument: `x`")])
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(ruff=(1, body, ""))):
                s = gate.run_ruff_unreferenced(t.root)
        self.assertEqual(s.findings, {("impl.py", "ARG002"): 1})

    def test_empty_tree_is_zero_files_not_a_shell_out(self):
        with _Tree() as t:
            run = _fake_run()
            with mock.patch.object(gate.subprocess, "run", side_effect=run):
                s = gate.run_ruff_unreferenced(t.root)
        self.assertEqual((s.files, s.findings), (0, {}))
        self.assertEqual(run.seen, [])


# --- Check F: PMD CPD ------------------------------------------------------------------------

class CpdDuplicationTests(unittest.TestCase):
    def _clone_tree(self, t: _Tree) -> list[str]:
        t.write("pkg/one.py", "import os\n\n" + _CLONE)
        t.write("pkg/two.py", "import sys\n\n" + _CLONE.replace("compute", "compute_again"))
        t.write("pkg/plain.py", _CLEAN)
        return ["pkg/one.py", "pkg/plain.py", "pkg/two.py"]

    def _dup(self) -> dict:
        # The clone starts after the differing name: column 12 in one.py, 18 in two.py (measured).
        return {"lines": 23, "tokens": 191,
                "occ": [("pkg/one.py", 3, 25, 12, 17), ("pkg/two.py", 3, 25, 18, 17)]}

    def test_positive_control_planted_clone_is_one_fingerprint_with_both_occurrences(self):
        with _Tree() as t:
            files = self._clone_tree(t)
            fake = _fake_run(cpd=(4, _cpd_xml(t.root, files, [self._dup()]), ""))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake), \
                    mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"):
                s = gate.run_cpd(t.root)
        self.assertEqual((s.tool, s.files), ("pmd-cpd", 3))
        self.assertEqual(len(s.findings), 1)
        [(fp, occs)] = s.findings.items()
        self.assertEqual(occs, [["pkg/one.py", 3, 25], ["pkg/two.py", 3, 25]])
        self.assertRegex(fp, r"^[0-9a-f]{16}$")

    def test_fingerprint_is_the_same_from_either_occurrence(self):
        """A rename can reorder which occurrence CPD lists first; the hash must not move."""
        with _Tree() as t:
            self._clone_tree(t)
            a = gate._cpd_occurrence_text(t.root, "pkg/one.py", 3, 25, 12, 17)
            b = gate._cpd_occurrence_text(t.root, "pkg/two.py", 3, 25, 18, 17)
        self.assertTrue(a.startswith("(items, factor):"), a[:30])
        self.assertEqual(gate._cpd_fingerprint(a), gate._cpd_fingerprint(b))

    def test_fingerprint_ignores_comments_and_whitespace_but_not_code(self):
        base = "x = compute(a, b)\nreturn x\n"
        self.assertEqual(gate._cpd_fingerprint(base),
                         gate._cpd_fingerprint("x = compute(a,   b)  # note\n\n\nreturn   x\n"))
        self.assertNotEqual(gate._cpd_fingerprint(base), gate._cpd_fingerprint("x = compute(a, c)\nreturn x\n"))
        self.assertNotEqual(gate._cpd_fingerprint('s = "a b"'), gate._cpd_fingerprint('s = "a  b"'),
                            "a string's contents are code")

    def test_negative_control_no_clones_is_empty_with_denominator(self):
        with _Tree() as t:
            files = self._clone_tree(t)
            fake = _fake_run(cpd=(0, _cpd_xml(t.root, files), ""))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake), \
                    mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"):
                s = gate.run_cpd(t.root)
        self.assertEqual((s.files, s.findings), (3, {}))

    def test_exit_5_recoverable_error_is_operational_even_with_a_report(self):
        """5 = a file CPD could not lex or find. The report still lists clones, and the skipped
        file is exactly the one reading clean, so the report is not consumed."""
        with _Tree() as t:
            files = self._clone_tree(t)
            # Every file listed and no <error>: the exit code is the ONLY signal here, which is
            # what this test pins (a first draft listed 2 of 3 files and passed on the count).
            fake = _fake_run(cpd=(5, _cpd_xml(t.root, files, [self._dup()]), "[ERROR] No such file"))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake), \
                    mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.run_cpd(t.root)
        self.assertIn("exited 5", str(cm.exception))

    def test_error_element_in_the_report_is_operational(self):
        with _Tree() as t:
            files = self._clone_tree(t)
            fake = _fake_run(cpd=(4, _cpd_xml(t.root, files, [self._dup()], errors=["pkg/plain.py"]), ""))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake), \
                    mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.run_cpd(t.root)
        self.assertIn("plain.py", str(cm.exception))

    def test_fewer_files_reported_than_handed_over_is_operational(self):
        with _Tree() as t:
            files = self._clone_tree(t)
            fake = _fake_run(cpd=(0, _cpd_xml(t.root, files[:2]), ""))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake), \
                    mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.run_cpd(t.root)
        self.assertIn("2 files analysed but was handed 3", str(cm.exception))

    def test_exit_1_exception_and_exit_2_usage_are_operational(self):
        with _Tree() as t:
            files = self._clone_tree(t)
            for rc in (1, 2):
                fake = _fake_run(cpd=(rc, _cpd_xml(t.root, files), "Unknown language"))
                with mock.patch.object(gate.subprocess, "run", side_effect=fake), \
                        mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"):
                    with self.assertRaises(gate.ScanOperationalError, msg=f"exit {rc}") as cm:
                        gate.run_cpd(t.root)
                self.assertIn(f"exited {rc}", str(cm.exception))

    def test_pmd_absent_everywhere_is_operational(self):
        with _Tree() as t, _Tree() as home:
            self._clone_tree(t)
            run = _fake_run()
            with mock.patch.object(gate.shutil, "which", return_value=None), \
                    mock.patch.dict(os.environ, {"PMD_HOME": str(home.root / "nowhere")}), \
                    mock.patch.object(gate.Path, "home", return_value=home.root), \
                    mock.patch.object(gate.subprocess, "run", side_effect=run):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.run_cpd(t.root)
        self.assertIn("pmd not found", str(cm.exception))
        self.assertEqual(run.seen, [])

    def test_pmd_is_found_under_local_opt_newest_first(self):
        with _Tree() as home:
            for v in ("7.9.0", "7.27.0", "7.10.0"):
                p = home.write(f".local/opt/pmd-bin-{v}/bin/pmd", "#!/bin/sh\n")
            with mock.patch.object(gate.shutil, "which", return_value=None), \
                    mock.patch.dict(os.environ, {"PMD_HOME": ""}), \
                    mock.patch.object(gate.Path, "home", return_value=home.root):
                self.assertTrue(gate._pmd_bin().endswith("pmd-bin-7.27.0/bin/pmd"),
                                "numeric sort, not lexical (7.9 < 7.10 < 7.27)")

    def test_invocation_never_folds_the_failing_exit_codes_into_0(self):
        with _Tree() as t:
            files = self._clone_tree(t)
            fake = _fake_run(cpd=(0, _cpd_xml(t.root, files), ""))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake), \
                    mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"), \
                    mock.patch.object(gate, "DUP_MIN_TOKENS", 42):
                gate.run_cpd(t.root)
        cmd = fake.seen[0]
        self.assertEqual(cmd[1:2], ["cpd"])
        self.assertEqual(_arg_after(cmd, "--minimum-tokens"), "42", "the threshold is the global")
        self.assertEqual(_arg_after(cmd, "--language"), "python")
        for forbidden in ("--no-fail-on-violation", "--no-fail-on-error", "--skip-lexical-errors"):
            self.assertNotIn(forbidden, cmd)
        listing = Path(_arg_after(cmd, "--file-list"))
        self.assertFalse(listing.exists(), "the temp listing is cleaned up")

    def test_doctype_is_refused(self):
        with _Tree() as t:
            with self.assertRaises(gate.ScanOperationalError):
                gate.parse_cpd('<!DOCTYPE x [<!ENTITY e "y">]><pmd-cpd/>', t.root)

    def test_non_xml_report_is_operational(self):
        with _Tree() as t:
            with self.assertRaises(gate.ScanOperationalError):
                gate.parse_cpd("not xml", t.root)


# --- Check G: complexipy ---------------------------------------------------------------------

class ComplexipyTests(unittest.TestCase):
    def _rows(self, *rows) -> str:
        return json.dumps([{"complexity": c, "file_name": Path(p).name, "function_name": fn,
                            "path": p, "refactor_plans": []} for p, fn, c in rows])

    def test_positive_control_planted_functions_are_keyed_file_function(self):
        with _Tree() as t:
            t.write("pkg/a.py", "class K:\n    def m(self, x):\n        return x\n\ndef f(a):\n    return a\n")
            t.write("pkg/empty.py", "X = 1\n")
            report = self._rows(("pkg/a.py", "K::m", 7), ("pkg/a.py", "f", 3))
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(cx=(0, report, ""))):
                s = gate.run_complexipy(t.root)
        self.assertEqual((s.tool, s.files), ("complexipy", 2), "a file with no functions still counts")
        self.assertEqual(s.findings, {("pkg/a.py", "K::m"): 7, ("pkg/a.py", "f"): 3})

    def test_negative_control_no_functions_is_empty_with_denominator(self):
        with _Tree() as t:
            t.write("a.py", "X = 1\n")
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(cx=(0, "[]", ""))):
                s = gate.run_complexipy(t.root)
        self.assertEqual((s.files, s.findings), (1, {}))

    def test_exit_1_is_operational_even_though_the_json_was_written(self):
        """Measured: a file complexipy fails to process is exit 1 AND a complete JSON for the
        rest, its error on stdout. The JSON is not consumed."""
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            report = self._rows(("a.py", "f", 1))
            fake = _fake_run(cx=(1, report, ""))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.run_complexipy(t.root)
        self.assertIn("exited 1", str(cm.exception))

    def test_no_output_file_is_operational(self):
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(cx=(0, None, ""))):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.run_complexipy(t.root)

    def test_missing_uvx_exit_127_is_operational(self):
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            fake = _fake_run(cx=(127, None, "uvx: command not found"))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.run_complexipy(t.root)
        self.assertIn("exited 127", str(cm.exception))

    def test_same_name_twice_in_one_file_keeps_the_higher_value(self):
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            report = self._rows(("a.py", "f", 2), ("a.py", "f", 9))
            with mock.patch.object(gate.subprocess, "run", side_effect=_fake_run(cx=(0, report, ""))):
                s = gate.run_complexipy(t.root)
        self.assertEqual(s.findings, {("a.py", "f"): 9})

    def test_invocation_is_whole_tree_pinned_and_keeps_out_of_the_tree(self):
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            fake = _fake_run(cx=(0, "[]", ""))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake):
                gate.run_complexipy(t.root)
        cmd = fake.seen[0]
        self.assertEqual(cmd[:2], ["uvx", gate._PY_COMPLEXIPY])
        self.assertNotIn("--diff", cmd, "the engine does the delta")
        self.assertEqual(_arg_after(cmd, "--max-complexity-allowed"), "1000000",
                         "under it exit 1 has one meaning: a file it failed to process")
        self.assertFalse(Path(_arg_after(cmd, "--output")).is_relative_to(t.root),
                         "its results file must not land in the tree under test")
        self.assertFalse(Path(_arg_after(cmd, "--cache-dir")).is_relative_to(t.root))
        self.assertEqual(cmd[-1], "a.py")


# --- Check H: the ast scan -------------------------------------------------------------------

class AbstractionsTests(unittest.TestCase):
    def test_positive_control_abc_with_one_subclass(self):
        with _Tree() as t:
            t.write("base.py", "from abc import ABC, abstractmethod\n\nclass Base(ABC):\n"
                               "    @abstractmethod\n    def run(self): ...\n")
            t.write("impl.py", "from base import Base\n\nclass Only(Base):\n    def run(self):\n"
                               "        return 1\n")
            s = gate.scan_python_abstractions(t.root)
        self.assertEqual((s.tool, s.files), ("ast", 2))
        self.assertEqual(s.findings, {("base.py", "Base"): 1})

    def test_each_declaration_form_is_seen(self):
        with _Tree() as t:
            t.write("a.py", "import abc\n\nclass A(abc.ABC):\n    pass\n")
            t.write("b.py", "import abc\n\nclass B(metaclass=abc.ABCMeta):\n    pass\n")
            t.write("c.py", "import abc\n\nclass C:\n    @abc.abstractmethod\n    def m(self): ...\n")
            t.write("d.py", "from typing import Generic, TypeVar\nfrom abc import ABC\nT = TypeVar('T')\n"
                            "class D(Generic[T], ABC):\n    pass\n")
            s = gate.scan_python_abstractions(t.root)
        self.assertEqual(set(s.findings), {("a.py", "A"), ("b.py", "B"), ("c.py", "C"), ("d.py", "D")})
        self.assertEqual(set(s.findings.values()), {0})

    def test_implementors_are_transitive_and_exclude_abstract_layers(self):
        with _Tree() as t:
            t.write("h.py", "from abc import ABC, abstractmethod\n\n"
                            "class A(ABC):\n    @abstractmethod\n    def m(self): ...\n\n"
                            "class B(A):\n    @abstractmethod\n    def n(self): ...\n\n"
                            "class C(B):\n    def m(self): return 1\n    def n(self): return 2\n\n"
                            "class D(C):\n    pass\n")
            s = gate.scan_python_abstractions(t.root)
        self.assertEqual(s.findings, {("h.py", "A"): 2, ("h.py", "B"): 2},
                         "C and D implement both layers; B is a layer, not an implementor")

    def test_negative_control_plain_and_protocol_classes_are_not_abstractions(self):
        with _Tree() as t:
            t.write("plain.py", "class Base:\n    def m(self):\n        return 1\n\nclass Only(Base):\n"
                                "    pass\n\nclass Err(Exception):\n    pass\n")
            t.write("proto.py", "from typing import Protocol\n\nclass Sized(Protocol):\n"
                                "    def size(self) -> int: ...\n")
            s = gate.scan_python_abstractions(t.root)
        self.assertEqual((s.files, s.findings), (2, {}))

    def test_syntax_error_is_operational_not_zero_abstractions(self):
        with _Tree() as t:
            t.write("base.py", "from abc import ABC\n\nclass Base(ABC):\n    pass\n")
            t.write("bad.py", "class (:\n")
            with self.assertRaises(gate.ScanOperationalError):
                gate.scan_python_abstractions(t.root)


# --- The four methods are wired, and the engine sees all four with denominators -----------------

class PythonToolchainWiringTests(unittest.TestCase):
    def test_capture_records_all_four_with_the_walk_as_denominator(self):
        with _Tree() as t:
            t.write("a.py", "from abc import ABC\n\nclass Base(ABC):\n    pass\n\ndef f(a):\n    return a\n")
            t.write("b.py", _CLEAN)
            fake = _fake_run(ruff=(0, "[]", ""), cx=(0, "[]", ""), cpd=(0, _cpd_xml(t.root, ["a.py", "b.py"]), ""))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake), \
                    mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"):
                out = gate._capture_agent_scans(gate.PythonToolchain(), t.root)
        for check, tool in (("E", "ruff"), ("F", "pmd-cpd"), ("G", "complexipy"), ("H", "ast")):
            self.assertNotIn("not_wired", out[check], check)
            self.assertEqual(out[check]["tool"], tool)
            self.assertEqual(out[check]["files"], 2, check)
        self.assertEqual(out["H"]["findings"], [[["a.py", "Base"], 0]])

    def test_a_tool_that_did_not_run_stops_the_capture_with_exit_2(self):
        import contextlib
        import io
        with _Tree() as t:
            t.write("a.py", _CLEAN)
            fake = _fake_run(ruff=(0, "[]", ""), cx=(0, "[]", ""), cpd=(5, _cpd_xml(t.root, []), "boom"))
            with mock.patch.object(gate.subprocess, "run", side_effect=fake), \
                    mock.patch.object(gate, "_pmd_bin", return_value="/opt/pmd/bin/pmd"), \
                    self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
                gate._capture_agent_scans(gate.PythonToolchain(), t.root)
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

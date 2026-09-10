#!/usr/bin/env python3
"""Tests for the Scala 3 runners behind Checks E-H in sdlc-gate.py — stdlib unittest, run:
python3 <this file>.

Every tool is mocked at subprocess.run, so the suite runs on a box without sbt, PMD or scala-cli.
The mocked outputs are the captured ones (sbt 1.12.11 + Scala 3.3.8, PMD CPD 7.27.0, the
scalameta script's own TSV), trimmed, never invented. Each wired check has a positive control (a
planted smell is found), a negative control (clean input finds nothing), and a did-not-run case
(the tool missing, erroring, or pointed at a syntax error raises ScanOperationalError rather than
reading as empty). The engine half is in test_sdlc_gate_contract.py.
"""

from __future__ import annotations

import importlib.util
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


def _proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> types.SimpleNamespace:
    return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _tree(td: str, *rel: str) -> Path:
    """A throwaway Scala tree with the named files, so the runners' own file walk has something
    to hand the (mocked) tool and the CPD denominator check has a list to compare against."""
    root = Path(td).resolve()
    for r in rel:
        p = root / r
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("object X\n")
    return root


# --- Check E: sbt -Wunused:all ---------------------------------------------------------------

def _sbt_out(root: Path, warnings: list[tuple[str, str]], compiled: int = 3) -> str:
    """Captured 2026-09-10 from sbt 1.12.11 / Scala 3.3.8: header, source line, caret, message."""
    lines = ["[info] Defining Global / commands",
             f"[info] compiling {compiled} Scala sources to {root}/claimos-core/target/scala-3.3.8/classes ..."]
    for rel, msg in warnings:
        lines += [f"[warn] -- [E198] Unused Symbol Warning: {root}/{rel}:7:16 ",
                  "[warn] 7 |  def f(x: Int, unusedParam: Int): Int = {",
                  "[warn]   |                ^^^^^^^^^^^",
                  f"[warn]   |                {msg}"]
    lines += ["[info] done compiling", "[success] Total time: 21 s"]
    return "\n".join(lines) + "\n"


class UnreferencedTests(unittest.TestCase):
    def test_positive_planted_unused_symbols_are_keyed_by_file_and_kind(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            out = _sbt_out(root, [("a/A.scala", "unused explicit parameter"),
                                  ("a/A.scala", "unused explicit parameter"),
                                  ("a/A.scala", "unused import"),
                                  ("b/B.scala", "unused private member")])
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, out)):
                scan = gate.ScalaToolchain().unreferenced(root)
        self.assertEqual(scan.files, 3)
        self.assertEqual(scan.findings[("a/A.scala", "unused-explicit-parameter")], 2)
        self.assertEqual(scan.findings[("a/A.scala", "unused-import")], 1)
        self.assertEqual(scan.findings[("b/B.scala", "unused-private-member")], 1)

    def test_a_source_line_containing_the_word_unused_is_not_a_finding(self):
        """`[warn] 7 |  val unused = ...` is the echoed source, not the message: it carries a line
        number before the pipe and must not be read as a second finding."""
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td)
            out = _sbt_out(root, [("a/A.scala", "unused local definition")]).replace(
                "def f(x: Int, unusedParam: Int): Int = {", "val unused = 3")
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, out)):
                scan = gate.ScalaToolchain().unreferenced(root)
        self.assertEqual(sum(scan.findings.values()), 1)

    def test_negative_clean_compile_finds_nothing_but_counts_its_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td)
            out = _sbt_out(root, [], compiled=28) + \
                f"[info] compiling 61 Scala sources to {root}/x/target/scala-3.3.8/test-classes ...\n"
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, out)):
                scan = gate.ScalaToolchain().unreferenced(root)
        self.assertEqual(scan.findings, {})
        self.assertEqual(scan.files, 89, "both source sets are in the denominator")

    def test_did_not_run_compile_failure_raises(self):
        out = ("[error] -- [E040] Syntax Error: /r/a/A.scala:84:9\n[error] 84 |  def f( = \n"
               "[error] (claimosCore / Compile / compileIncremental) Compilation failed\n")
        with mock.patch.object(gate.subprocess, "run", return_value=_proc(1, out)):
            with self.assertRaises(gate.ScanOperationalError) as cm:
                gate.ScalaToolchain().unreferenced(Path("/r"))
        self.assertIn("Syntax Error", str(cm.exception))

    def test_did_not_run_sbt_missing_raises(self):
        with mock.patch.object(gate.subprocess, "run", side_effect=OSError("No such file: sbt")):
            with self.assertRaises(gate.ScanOperationalError):
                gate.ScalaToolchain().unreferenced(Path("/r"))

    def test_did_not_run_warm_cache_zero_sources_raises(self):
        """Measured: right after a full compile, the same command without `clean` exits 0 having
        compiled 0 sources and reports 0 warnings while the planted parameter is still there.
        Exit 0 with no `compiling N Scala sources` line is that trap, not a clean tree."""
        out = "[info] Defining Global / commands\n[success] Total time: 3 s\n"
        with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, out)):
            with self.assertRaises(gate.ScanOperationalError) as cm:
                gate.ScalaToolchain().unreferenced(Path("/r"))
        self.assertIn("no Scala sources", str(cm.exception))

    def test_did_not_run_a_scala_2_build_is_refused_not_read_as_clean(self):
        """2.13 prints `path:line:col: Unused import`, which the Scala 3 header never matches; a
        non-zero denominator with no findings would otherwise pass a 2.13 tree unexamined."""
        out = ("[info] compiling 3 Scala sources to /r/target/scala-2.13/classes ...\n"
               "[warn] /r/a/A.scala:3:8: Unused import\n[info] done compiling\n")
        with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, out)):
            with self.assertRaises(gate.ScanOperationalError) as cm:
                gate.ScalaToolchain().unreferenced(Path("/r"))
        self.assertIn("Scala 2", str(cm.exception))

    def test_a_scala_3_target_with_java_sources_alongside_still_counts_its_scala_files(self):
        out = ("[info] compiling 2 Scala sources and 1 Java source to /r/target/scala-3.3.8/classes ...\n"
               "[info] done compiling\n")
        with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, out)):
            scan = gate.ScalaToolchain().unreferenced(Path("/r"))
        self.assertEqual(scan.files, 2)

    def test_the_invocation_cleans_first_and_strips_werror_in_every_project(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return _proc(0, _sbt_out(Path("/r"), []))

        with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
            gate.ScalaToolchain().unreferenced(Path("/r"))
        cmd = seen["cmd"]
        self.assertEqual(cmd[-2:], ["clean", "Test/compile"], "a warm zinc cache reports nothing")
        injected = cmd[3]
        self.assertIn("allProjectRefs", injected, "ThisBuild alone misses a per-project -Werror")
        self.assertIn('"-Werror"', injected)
        self.assertIn('"-Wunused:all"', injected)
        self.assertIn("compile / scalacOptions", injected, "the key compile actually reads")


# --- Check F: PMD CPD ------------------------------------------------------------------------

_CPD_HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<pmd-cpd xmlns="https://pmd-code.org/schema/cpd-report" pmdVersion="7.27.0">\n')


def _cpd_xml(root: Path, files: list[str], dups: list[tuple[list[tuple[str, int, int]], str]]) -> str:
    """Captured 2026-09-10 from `pmd cpd --format xml` 7.27.0: namespaced, one `<file>` per
    tokenized file, then `<duplication>` blocks each with their `<file>`s and a `<codefragment>`."""
    body = "".join(f'   <file path="{root}/{f}" totalNumberOfTokens="120"/>\n' for f in files)
    for occs, fragment in dups:
        body += '   <duplication lines="9" tokens="81">\n'
        for f, line, end in occs:
            body += f'      <file column="3" endcolumn="10" endline="{end}" line="{line}" path="{root}/{f}"/>\n'
        body += f"      <codefragment><![CDATA[{fragment}]]></codefragment>\n   </duplication>\n"
    return _CPD_HEAD + body + "</pmd-cpd>\n"


class DuplicationTests(unittest.TestCase):
    def setUp(self):
        self._which = mock.patch.object(gate, "_pmd_binary", return_value="/opt/pmd/bin/pmd")
        self._which.start()

    def tearDown(self):
        self._which.stop()

    def test_positive_a_clone_is_keyed_by_content_and_lists_every_occurrence(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "b/B.scala")
            xml = _cpd_xml(root, ["a/A.scala", "b/B.scala"],
                           [([("a/A.scala", 25, 46), ("b/B.scala", 19, 40)], "def rows(r: RawValue) =\n  r.utf8")])
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(4, xml)):
                scan = gate.ScalaToolchain().duplication(root)
        self.assertEqual(scan.files, 2)
        self.assertEqual(len(scan.findings), 1)
        (fp, occs), = scan.findings.items()
        self.assertEqual(occs, [["a/A.scala", 25, 46], ["b/B.scala", 19, 40]])
        # Same fragment, other whitespace: the same fingerprint, so a moved clone keys the same.
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "b/B.scala")
            xml = _cpd_xml(root, ["a/A.scala", "b/B.scala"],
                           [([("a/A.scala", 30, 51), ("b/B.scala", 19, 40)], "def rows(r: RawValue) =   r.utf8")])
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(4, xml)):
                again = gate.ScalaToolchain().duplication(root)
        self.assertIn(fp, again.findings)

    def test_negative_no_clones_is_empty_with_the_denominator_kept(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "b/B.scala")
            xml = _cpd_xml(root, ["a/A.scala", "b/B.scala"], [])
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, xml)):
                scan = gate.ScalaToolchain().duplication(root)
        self.assertEqual(scan.findings, {})
        self.assertEqual(scan.files, 2)

    def test_sc_scripts_are_not_handed_to_cpd(self):
        """Measured: CPD drops a `.sc` from a file list silently and exits 0, so it is never in the
        list and never in the denominator."""
        seen = {}

        def fake_run(cmd, **kw):
            seen["list"] = Path(cmd[cmd.index("--file-list") + 1]).read_text().split()
            return _proc(0, _cpd_xml(Path(kw["cwd"]), ["a/A.scala"], []))

        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "a/script.sc")
            with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
                scan = gate.ScalaToolchain().duplication(root)
        self.assertEqual(seen["list"], ["a/A.scala"])
        self.assertEqual(scan.files, 1)

    def test_did_not_run_exit_5_recoverable_error_raises(self):
        """CPD's exit 5 is "a recoverable error occurred" (measured: a listed file it could not
        read). The exit code alone must refuse the scan, so the report here is deliberately
        complete: the file-count check below is not what this test leans on."""
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "b/B.scala")
            xml = _cpd_xml(root, ["a/A.scala", "b/B.scala"], [])
            with mock.patch.object(gate.subprocess, "run",
                                   return_value=_proc(5, xml, "[ERROR] Lexical error in b/B.scala")):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.ScalaToolchain().duplication(root)
        self.assertIn("exited 5", str(cm.exception))

    def test_did_not_run_a_file_dropped_from_the_report_raises_even_at_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "b/B.scala")
            xml = _cpd_xml(root, ["a/A.scala"], [])
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, xml)):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.ScalaToolchain().duplication(root)
        self.assertIn("1 of the 2", str(cm.exception))

    def test_did_not_run_exit_1_and_exit_2_raise(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            for rc in (1, 2, 127):
                with mock.patch.object(gate.subprocess, "run", return_value=_proc(rc, "", "boom")):
                    with self.assertRaises(gate.ScanOperationalError, msg=f"exit {rc}"):
                        gate.ScalaToolchain().duplication(root)

    def test_did_not_run_pmd_missing_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            with mock.patch.object(gate, "_pmd_binary", return_value=None):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.ScalaToolchain().duplication(root)

    def test_did_not_run_non_xml_output_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, "not xml")):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.ScalaToolchain().duplication(root)

    def test_the_threshold_comes_from_the_module_global(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return _proc(0, _cpd_xml(Path(kw["cwd"]), ["a/A.scala"], []))

        old = gate.DUP_MIN_TOKENS
        gate.DUP_MIN_TOKENS = 33
        try:
            with tempfile.TemporaryDirectory() as td:
                root = _tree(td, "a/A.scala")
                with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
                    gate.ScalaToolchain().duplication(root)
        finally:
            gate.DUP_MIN_TOKENS = old
        cmd = seen["cmd"]
        self.assertEqual(cmd[cmd.index("--minimum-tokens") + 1], "33")
        self.assertEqual(cmd[cmd.index("--language") + 1], "scala")


# --- Checks G and H: the scalameta script ----------------------------------------------------

_TSV_PLANTED = ("G\ta/A.scala\tPlantedSmells.tangled\t26\n"
                "G\ta/A.scala\tPlantedSmells.withUnused\t0\n"
                "G\tb/B.scala\tB.apply\t3\n"
                "H\ta/A.scala\tPlantedPort\t1\n"
                "H\tb/B.scala\tShape\t3\n"
                "FILES\t2\n")


class ScalametaScanTests(unittest.TestCase):
    def setUp(self):
        self._which = mock.patch.object(gate, "_scala_cli_binary", return_value="/opt/scala-cli")
        self._which.start()

    def tearDown(self):
        self._which.stop()

    def test_positive_complexity_is_keyed_by_file_and_qualified_def(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "b/B.scala")
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, _TSV_PLANTED)):
                scan = gate.ScalaToolchain().complexity(root)
        self.assertEqual(scan.files, 2)
        self.assertEqual(scan.findings[("a/A.scala", "PlantedSmells.tangled")], 26)
        self.assertEqual(scan.findings[("b/B.scala", "B.apply")], 3)
        self.assertNotIn(("a/A.scala", "PlantedPort"), scan.findings, "H rows stay out of G")
        old = gate.COMPLEXITY_THRESHOLD
        gate.COMPLEXITY_THRESHOLD = 15
        try:
            blocks = gate._diff_complexity(scan.findings, {}, {}, set(), {})
        finally:
            gate.COMPLEXITY_THRESHOLD = old
        self.assertEqual([i["function"] for i in blocks[0]["items"]], ["PlantedSmells.tangled"])

    def test_positive_abstractions_are_keyed_by_file_and_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "b/B.scala")
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, _TSV_PLANTED)):
                scan = gate.ScalaToolchain().abstractions(root)
        self.assertEqual(scan.files, 2)
        self.assertEqual(scan.findings, {("a/A.scala", "PlantedPort"): 1, ("b/B.scala", "Shape"): 3})
        blocks = gate._diff_abstractions(scan.findings, {}, {}, set(), {})
        self.assertEqual([i["name"] for i in blocks[0]["items"]], ["PlantedPort"])

    def test_negative_simple_defs_and_well_used_traits_block_nothing(self):
        tsv = "G\ta/A.scala\tA.f\t0\nG\ta/A.scala\tA.g\t2\nH\ta/A.scala\tPort\t4\nFILES\t1\n"
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, tsv)):
                g = gate.ScalaToolchain().complexity(root)
                h = gate.ScalaToolchain().abstractions(root)
        self.assertEqual(g.files, 1)
        self.assertEqual(gate._diff_complexity(g.findings, {}, {}, set(), {}), [])
        self.assertEqual(gate._diff_abstractions(h.findings, {}, {}, set(), {}), [])

    def test_negative_a_tree_with_no_abstractions_is_an_empty_scan_with_files(self):
        tsv = "G\ta/A.scala\tA.f\t0\nFILES\t1\n"
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, tsv)):
                h = gate.ScalaToolchain().abstractions(root)
        self.assertEqual(h.findings, {})
        self.assertEqual(h.files, 1)

    def test_did_not_run_a_syntax_error_raises_and_names_the_file(self):
        """The script's exit 3: a file it could not parse. Measured against the corpus with a
        planted `def f( =`: `ERR <file> 84:10: identifier expected but = found`."""
        out = "G\tb/B.scala\tB.apply\t3\nERR\ta/A.scala\t84:10: `identifier` expected but `=` found\nFILES\t1\n"
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "b/B.scala")
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(3, out)):
                for method in ("complexity", "abstractions"):
                    with self.assertRaises(gate.ScanOperationalError, msg=method) as cm:
                        getattr(gate.ScalaToolchain(), method)(root)
                    self.assertIn("a/A.scala", str(cm.exception))

    def test_did_not_run_scala_cli_failure_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            with mock.patch.object(gate.subprocess, "run",
                                   return_value=_proc(1, "", "Compilation failed")):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.ScalaToolchain().complexity(root)
            with mock.patch.object(gate.subprocess, "run", side_effect=OSError("no scala-cli")):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.ScalaToolchain().abstractions(root)

    def test_did_not_run_scala_cli_missing_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            with mock.patch.object(gate, "_scala_cli_binary", return_value=None):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.ScalaToolchain().complexity(root)

    def test_did_not_run_output_without_the_files_line_raises(self):
        """Exit 0 with G rows but no FILES line is a script that did not reach its end."""
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, "G\ta/A.scala\tA.f\t0\n")):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.ScalaToolchain().complexity(root)

    def test_did_not_run_zero_files_parsed_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala")
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, "FILES\t0\n")):
                with self.assertRaises(gate.ScanOperationalError):
                    gate.ScalaToolchain().abstractions(root)

    def test_the_script_and_file_list_are_written_beside_each_other_and_run_without_a_server(self):
        seen = {}

        def fake_run(cmd, **kw):
            cwd = Path(kw["cwd"])
            seen["cmd"] = cmd
            seen["script"] = (cwd / "Gate.scala").read_text()
            seen["list"] = (cwd / "files.txt").read_text().split()
            return _proc(0, "FILES\t1\n")

        with tempfile.TemporaryDirectory() as td:
            root = _tree(td, "a/A.scala", "a/script.sc", "target/scala-3.3.8/Gen.scala")
            with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
                gate.ScalaToolchain().complexity(root)
        self.assertIn("--server=false", seen["cmd"], "no build daemon left behind by a hook")
        self.assertEqual(seen["cmd"][-2:], [str(root), "files.txt"])
        self.assertEqual(seen["list"], ["a/A.scala"], "no .sc, nothing under target/")
        self.assertIn("scalameta", seen["script"])
        self.assertIn("dialects.Scala3", seen["script"])


if __name__ == "__main__":
    unittest.main()

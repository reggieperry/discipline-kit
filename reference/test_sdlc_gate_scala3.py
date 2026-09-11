#!/usr/bin/env python3
"""Tests for the Scala 3 runners behind Checks E-H in sdlc-gate.py — stdlib unittest, run:
python3 <this file>.

Every tool is mocked at subprocess.run, so the suite runs on a box without sbt, PMD or scala-cli.
The mocked outputs are the captured ones (sbt 1.12.11 + Scala 3.3.8, PMD CPD 7.27.0, the
scalameta script's own TSV), trimmed, never invented. Each wired check has a positive control (a
planted smell is found), a negative control (clean input finds nothing), and a did-not-run case
(the tool missing, erroring, or pointed at a syntax error raises ScanOperationalError rather than
reading as empty). The engine half is in test_sdlc_gate_contract.py. Check A's two runners are
tested here too: the wartremover parse, with one Scala 2.13.18 sample beside the Scala 3 ones, and
how scalafix and the wart scan read a plugin that is not set up or a run that failed.
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


_SERIAL_COMPILE = "set Global / concurrentRestrictions += Tags.limit(Tags.Compile, 1)"


def _at(out: str, root: Path) -> str:
    return out.replace("<root>", str(root))


# Captured 2026-09-10, sbt 1.12.11 / Scala 3.3.8, a 3-module build with 15 planted warnings per
# module; trimmed to the first ones, machine paths replaced by <root>. Without serialization:
_E_INTERLEAVED = "\n".join([
    "[info] compiling 7 Scala sources to <root>/gamma/target/scala-3.3.8/classes ...",
    "[info] compiling 7 Scala sources to <root>/beta/target/scala-3.3.8/classes ...",
    "[info] compiling 7 Scala sources to <root>/alpha/target/scala-3.3.8/classes ...",
    "[warn] -- [E198] Unused Symbol Warning: <root>/gamma/src/main/scala/gamma/PlantedGamma.scala:6:17 ",
    "[warn] -- [E198] Unused Symbol Warning: <root>/alpha/src/main/scala/alpha/PlantedAlpha.scala:6:17 ",
    "[warn] -- [E198] Unused Symbol Warning: <root>/beta/src/main/scala/beta/PlantedBeta.scala:6:17 ",
    "[warn] 6 |  def m1(a: Int, unused1: Int): Int = a + 1",
    "[warn]   |                 ^^^^^^^",
    "[warn] 6 |  def m1(a: Int, unused1: Int): Int = a + 1",
    "[warn] 6 |  def m1(a: Int, unused1: Int): Int = a + 1",
    "[warn]   |                 unused explicit parameter",
    "[warn]   |                 ^^^^^^^",
    "[warn]   |                 ^^^^^^^",
    "[warn]   |                 unused explicit parameter",
    "[warn]   |                 unused explicit parameter",
    "[info] done compiling",
    "[info] done compiling",
    "[info] done compiling",
]) + "\n"

# The same build with the serializing element, one kind planted per module:
_E_SERIALIZED = "\n".join([
    "[info] compiling 7 Scala sources to <root>/gamma/target/scala-3.3.8/classes ...",
    "[warn] -- [E198] Unused Symbol Warning: <root>/gamma/src/main/scala/gamma/PlantedGamma.scala:7:8 ",
    "[warn] 7 |    val local1 = a * 1",
    "[warn]   |        ^^^^^^",
    "[warn]   |        unused local definition",
    "[warn] -- [E198] Unused Symbol Warning: <root>/gamma/src/main/scala/gamma/PlantedGamma.scala:11:8 ",
    "[warn] 11 |    val local2 = a * 2",
    "[warn]    |        ^^^^^^",
    "[warn]    |        unused local definition",
    "[info] done compiling",
    "[info] compiling 7 Scala sources to <root>/beta/target/scala-3.3.8/classes ...",
    "[warn] -- [E198] Unused Symbol Warning: <root>/beta/src/main/scala/beta/PlantedBeta.scala:8:14 ",
    "[warn] 8 |  private def p1: Int = 1",
    "[warn]   |              ^^",
    "[warn]   |              unused private member",
    "[warn] -- [E198] Unused Symbol Warning: <root>/beta/src/main/scala/beta/PlantedBeta.scala:10:14 ",
    "[warn] 10 |  private def p2: Int = 2",
    "[warn]    |              ^^",
    "[warn]    |              unused private member",
    "[info] done compiling",
    "[info] compiling 7 Scala sources to <root>/alpha/target/scala-3.3.8/classes ...",
    "[warn] -- [E198] Unused Symbol Warning: <root>/alpha/src/main/scala/alpha/PlantedAlpha.scala:6:17 ",
    "[warn] 6 |  def m1(a: Int, unused1: Int): Int = a + 1",
    "[warn]   |                 ^^^^^^^",
    "[warn]   |                 unused explicit parameter",
    "[warn] -- [E198] Unused Symbol Warning: <root>/alpha/src/main/scala/alpha/PlantedAlpha.scala:8:17 ",
    "[warn] 8 |  def m2(a: Int, unused2: Int): Int = a + 2",
    "[warn]   |                 ^^^^^^^",
    "[warn]   |                 unused explicit parameter",
    "[info] done compiling",
]) + "\n"


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

    def test_the_scan_compiles_one_module_at_a_time(self):
        """sbt compiles modules in parallel and interleaves their diagnostics line by line; on the
        lab, a 9-module build, four unserialized runs gave 13/15/12, 15/15/12, 14/15/15 and 14/15/14
        of 15 findings per file. With this element before gateUnusedScan the scan was exact in 4 of 4
        runs on a 3-module tree and 2 of 2 on the lab."""
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return _proc(0, _sbt_out(Path("/r"), []))

        with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
            gate.ScalaToolchain().unreferenced(Path("/r"))
        cmd = seen["cmd"]
        self.assertIn(_SERIAL_COMPILE, cmd)
        self.assertLess(cmd.index(_SERIAL_COMPILE), cmd.index("gateUnusedScan"))

    def test_did_not_run_interleaved_diagnostics_are_refused_not_miscounted(self):
        """Three modules' first warnings, as sbt printed them without serialization: three headers,
        then the three bodies. A single pending header credited all of it to the last file."""
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td)
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, _at(_E_INTERLEAVED, root))):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.ScalaToolchain().unreferenced(root)
        self.assertIn("interleaved", str(cm.exception))

    def test_serialized_multi_module_output_gives_exact_counts_per_file_and_kind(self):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td)
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, _at(_E_SERIALIZED, root))):
                scan = gate.ScalaToolchain().unreferenced(root)
        self.assertEqual(scan.files, 21)
        self.assertEqual(scan.findings, {
            ("gamma/src/main/scala/gamma/PlantedGamma.scala", "unused-local-definition"): 2,
            ("beta/src/main/scala/beta/PlantedBeta.scala", "unused-private-member"): 2,
            ("alpha/src/main/scala/alpha/PlantedAlpha.scala", "unused-explicit-parameter"): 2,
        })

    def test_did_not_run_a_message_with_no_header_waiting_is_refused(self):
        out = _E_SERIALIZED.replace(
            "[warn] -- [E198] Unused Symbol Warning: <root>/gamma/src/main/scala/gamma/PlantedGamma.scala:7:8 \n", "")
        self.assertEqual(out.count("Unused Symbol Warning"), 5, "the fixture lost exactly one header")
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td)
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, _at(out, root))):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    gate.ScalaToolchain().unreferenced(root)
        self.assertIn("interleaved", str(cm.exception))

    def test_did_not_run_a_header_whose_message_never_came_is_refused(self):
        """Mid-output, the next header arrives first; at the end, the output runs out. Either way
        the count would be one short, with the other message still paired and nothing orphaned."""
        cases = {
            "mid-output": ("[warn]   |        unused local definition\n[warn] -- ", "[warn] -- ",
                           "unused local definition", "PlantedGamma.scala"),
            "at the end": ("[warn]   |                 unused explicit parameter\n[info] done", "[info] done",
                           "unused explicit parameter", "PlantedAlpha.scala"),
        }
        for label, (old, new, message, named) in cases.items():
            with self.subTest(label):
                out = _E_SERIALIZED.replace(old, new)
                self.assertEqual(out.count(message), 1, "the fixture lost exactly one message")
                with tempfile.TemporaryDirectory() as td:
                    root = _tree(td)
                    with mock.patch.object(gate.subprocess, "run", return_value=_proc(0, _at(out, root))):
                        with self.assertRaises(gate.ScanOperationalError) as cm:
                            gate.ScalaToolchain().unreferenced(root)
                self.assertIn(named, str(cm.exception))


# --- Check A: wartremover ----------------------------------------------------------------------

# Captured 2026-09-10 with `-Dgate.wartScan=true Test/compile` on a 368-file Scala 3.3.8 build
# (wartremover 3.6.1), trimmed, machine paths replaced by <root>. Scala 3 names the file on a
# header and prints the wart tag lines later, sometimes with no space after the pipe.
_WART_SCALA3 = "\n".join([
    "[info] compiling 12 Scala sources to <root>/gate/target/scala-3.3.8/classes ...",
    "[info] compiling 28 Scala sources to <root>/claim-algebra/target/scala-3.3.8/classes ...",
    "[info] compiling 25 Scala sources to <root>/claimos-core/target/scala-3.3.8/classes ...",
    "[warn] -- Warning: <root>/claim-algebra/src/main/scala/claimalgebra/decision/Tally.scala:12:8 ",
    "[warn] 12 |    var sum = 0",
    "[warn]    |    ^^^^^^^^^^^",
    "[warn]    |    [wartremover:Var] var is disabled",
    "[warn] -- Warning: <root>/gate/src/main/scala/gate/CoverageScan.scala:32:25 ",
    '[warn] 32 |  def parse(xml: String, sourceRoot: String = "src/main/scala"): Map[String, Double] =',
    "[warn]    |                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^",
    "[warn]    |           [wartremover:DefaultArguments] Function has default arguments",
    "[info] done compiling",
    "[info] compiling 10 Scala sources and 1 Java source to <root>/workbench/target/scala-3.3.8/classes ...",
    "[warn] -- Warning: <root>/workbench/src/main/scala/claimalgebra/workbench/CitationsGrounder.scala:92:23 ",
    "[warn] 92 |      case many => many.reduce((a, b) => Testimony.corroborate(a, b))",
    "[warn]    |                       ^^^^^^^",
    "[warn]    |[wartremover:IterableOps] reduce is disabled - use reduceOption or fold instead",
    "[warn] -- Warning: <root>/workbench/src/main/scala/claimalgebra/workbench/ConceptScope.scala:98:7 ",
    "[warn] 98 |      }.max",
    "[warn]    |       ^^^^",
    "[warn]    |[wartremover:IterableOps] max is disabled - use foldLeft or foldRight instead",
    "[info] done compiling",
]) + "\n"

# The same build on another branch: an unused-symbol warning, which carries no wart tag, between
# wart warnings. The tag after it belongs to the next header, not to Label.scala.
_WART_SCALA3_WITH_OTHER_WARNING = "\n".join([
    "[warn] -- Warning: <root>/gate/src/main/scala/gate/ReportJson.scala:60:37 ",
    '[warn] 60 |        case other if other < \' \' => f"\\\\u${other.toInt}%04x"',
    "[warn]    |                                     ^^^^^^^^^^^^^^^^^^^^^^^^",
    "[warn]    |                     [wartremover:Any] Inferred type containing Any: Any",
    "[warn] -- Warning: <root>/claimos-core/src/main/scala/claimos/universe/Universe.scala:98:35 ",
    '[warn] 98 |  def hex: String = bytes.map(b => f"${b & 0xff}%02x").mkString',
    "[warn]    |                                   ^^^^^^^^^^^^^^^^^^",
    "[warn]    |                     [wartremover:Any] Inferred type containing Any: Any",
    "[warn] -- [E198] Unused Symbol Warning: <root>/claim-algebra/src/main/scala/claimalgebra/decision/Label.scala:6:30 ",
    '[warn] 6 |  def label(decision: String, width: Int): String = s"decision: $decision"',
    "[warn]   |                              ^^^^^",
    "[warn]   |                              unused explicit parameter",
    "[info] done compiling",
    "[info] compiling 9 Scala sources and 2 Java sources to <root>/extract/target/scala-3.3.8/classes ...",
    "[info] done compiling",
    "[warn] -- Warning: <root>/extract/src/main/scala/claimalgebra/extract/AnthropicCitations.scala:88:6 ",
    "[warn] 88 |      model: Model = AnthropicLlmCall.DefaultModel,",
    "[warn]    |      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^",
    "[warn]    |      [wartremover:DefaultArguments] Function has default arguments",
]) + "\n"

# The same scan on the lab baseline, before compiles were serialized: two modules' headers arrived
# before either body, so each tag's file is a guess.
_WART_INTERLEAVED = "\n".join([
    "[info] compiling 12 Scala sources to <root>/gate/target/scala-3.3.8/classes ...",
    "[info] compiling 27 Scala sources to <root>/claim-algebra/target/scala-3.3.8/classes ...",
    "[info] compiling 25 Scala sources to <root>/claimos-core/target/scala-3.3.8/classes ...",
    "[warn] -- Warning: <root>/claim-algebra/src/main/scala/claimalgebra/provenance/Lineage.scala:35:24 ",
    "[warn] -- Warning: <root>/gate/src/main/scala/gate/CoverageScan.scala:32:25 ",
    "[warn] 35 |  def from(raw: String, kind: Option[Kind] = None): Option[Lineage] =",
    '[warn] 32 |  def parse(xml: String, sourceRoot: String = "src/main/scala"): Map[String, Double] =',
    "[warn]    |                        ^^^^^^^^^^^^^^^^^^^^^^^^^",
    "[warn]    |           [wartremover:DefaultArguments] Function has default arguments",
    "[warn]    |                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^",
    "[warn]    |           [wartremover:DefaultArguments] Function has default arguments",
    "[warn] -- Warning: <root>/gate/src/main/scala/gate/Diff.scala:159:18 ",
    '[warn] 159 |                  f"statement coverage $baseCov%.1f%% -> none (package absent)"',
    "[warn]     |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^",
    "[warn]     |                  [wartremover:Any] Inferred type containing Any: Any",
]) + "\n"

# Captured 2026-09-10 from Scala 2.13.18 with sbt-wartremover 3.6.1: one line names the file and
# carries the tag.
_WART_SCALA2 = "\n".join([
    "[info] compiling 1 Scala source to <root>/target/scala-2.13/classes ...",
    "[warn] <root>/src/main/scala/demo/Tally.scala:5:9: [wartremover:Var] var is disabled",
    "[warn]     var sum = 0",
    "[warn]         ^",
    "[warn] <root>/src/main/scala/demo/Tally.scala:10:50: [wartremover:Null] null is disabled",
    "[warn]   def orNull(s: String): String = if (s.isEmpty) null else s",
    "[warn]                                                  ^",
    "[warn] <root>/src/main/scala/demo/Tally.scala:14:39: [wartremover:Option2Iterable] Implicit "
    "conversion from Option to Iterable is disabled - use Option#toList instead",
    "[warn]   val asIterable: Iterable[Int] = Some(1)",
    "[warn]                                       ^",
    "[info] done compiling",
]) + "\n"


class WartremoverTests(unittest.TestCase):
    def _scan(self, out: str):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td)
            # A real run prints the wartremoverWarnings probe before compiling; the lab's here.
            with mock.patch.object(gate.subprocess, "run",
                                   return_value=_proc(0, _at(_WART_PROBE_ON_AGGREGATE + out, root))):
                return gate.run_wartremover(root)

    def test_positive_scala_3_warts_are_credited_to_their_header_file(self):
        """Measured: the one-line pattern read 0 of 135 Scala 3 warnings and passed a planted var."""
        self.assertEqual(self._scan(_WART_SCALA3), {
            ("claim-algebra/src/main/scala/claimalgebra/decision/Tally.scala", "Var"): 1,
            ("gate/src/main/scala/gate/CoverageScan.scala", "DefaultArguments"): 1,
            ("workbench/src/main/scala/claimalgebra/workbench/CitationsGrounder.scala", "IterableOps"): 1,
            ("workbench/src/main/scala/claimalgebra/workbench/ConceptScope.scala", "IterableOps"): 1,
        })

    def test_negative_a_warning_with_no_wart_tag_is_neither_a_wart_nor_a_refusal(self):
        self.assertEqual(self._scan(_WART_SCALA3_WITH_OTHER_WARNING), {
            ("gate/src/main/scala/gate/ReportJson.scala", "Any"): 1,
            ("claimos-core/src/main/scala/claimos/universe/Universe.scala", "Any"): 1,
            ("extract/src/main/scala/claimalgebra/extract/AnthropicCitations.scala", "DefaultArguments"): 1,
        })

    def test_positive_the_scala_2_one_line_shape_still_counts(self):
        self.assertEqual(self._scan(_WART_SCALA2), {
            ("src/main/scala/demo/Tally.scala", "Var"): 1,
            ("src/main/scala/demo/Tally.scala", "Null"): 1,
            ("src/main/scala/demo/Tally.scala", "Option2Iterable"): 1,
        })

    def test_did_not_run_a_wart_tag_with_no_header_is_refused(self):
        out = _WART_SCALA3.replace(
            "[warn] -- Warning: <root>/claim-algebra/src/main/scala/claimalgebra/decision/Tally.scala:12:8 \n", "")
        self.assertEqual(out.count("-- Warning:"), 3, "the fixture lost exactly one header")
        with self.assertRaises(gate.ScanOperationalError) as cm:
            self._scan(out)
        self.assertIn("4 [wartremover: tags", str(cm.exception))

    def test_did_not_run_a_tag_under_a_header_with_no_readable_position_is_refused(self):
        """A header ends the diagnostic before it even when its path cannot be read, so the tag
        after it is refused rather than credited to the unused-symbol warning's file."""
        out = _WART_SCALA3_WITH_OTHER_WARNING.replace("AnthropicCitations.scala:88:6 ", "AnthropicCitations.scala ")
        self.assertEqual(out.count(":88:6"), 0, "the fixture lost exactly one position")
        with self.assertRaises(gate.ScanOperationalError):
            self._scan(out)

    def test_did_not_run_two_warnings_whose_lines_interleave_are_refused(self):
        """Only the first tag after a header is that header's, so the second body's tag is left
        over. Measured: 8 of the 10 saved lab wart scans, all unserialized, hold such a pair."""
        with self.assertRaises(gate.ScanOperationalError) as cm:
            self._scan(_WART_INTERLEAVED)
        self.assertIn("3 [wartremover: tags but credited 2", str(cm.exception))

    def test_the_wart_scan_compiles_one_module_at_a_time(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return _proc(0, _WART_PROBE_ON_ONE_PROJECT + _WART_SET_AND_COMPILE)

        with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
            gate.run_wartremover(Path("/r"))
        cmd = seen["cmd"]
        self.assertIn("-Dgate.wartScan=true", cmd)
        self.assertIn(_SERIAL_COMPILE, cmd)
        self.assertLess(cmd.index(_SERIAL_COMPILE), cmd.index("Test/compile"))


# --- Check A: set up, ran, or could not run ---------------------------------------------------
# Captured 2026-09-10 with sbt 1.12.11 and sbt-scalafix 0.14.7 / sbt-wartremover 3.6.1 (the lab's
# pins), trimmed, machine paths replaced by <root>. Corpus P has neither plugin, corpus W is P with
# both, and the lab is the 9-module build. Until 2026-09-10 every one of these was parsed whatever
# sbt's exit, so a plugin that was not set up, or a scalafix that failed, read as zero findings.

_SCALAFIX_NOT_SET_UP = "\n".join([  # corpus P
    "[info] welcome to sbt 1.12.11 (Ubuntu Java 25.0.4)",
    "[info] loading project definition from <root>/project",
    "[info] loading settings for project root from build.sbt...",
    "[info] set current project to planted (in build file:<root>/)",
    "[error] Expected ID character",
    "[error] Not a valid command: scalafix",
    "[error] Expected project ID",
    "[error] Expected configuration",
    "[error] Expected ':'",
    "[error] Expected key",
    "[error] Not a valid key: scalafix (similar: scalaHome, scalaVersion, scalacOptions)",
    "[error] scalafix --check",
    "[error]         ^",
]) + "\n"

_SCALAFIX_HEAD = "\n".join([  # the lab
    "[info] welcome to sbt 1.12.11 (Ubuntu Java 25.0.4)",
    "[info] loading settings for project lab-build from plugins.sbt...",
    "[info] loading project definition from <root>/project",
    "[info] loading settings for project root from build.sbt...",
    "[info] resolving key references (10516 settings) ...",
    "[info] set current project to claim-algebra-lab (in build file:<root>/)",
]) + "\n"

_SCALAFIX_CLEAN = _SCALAFIX_HEAD + "[success] Total time: 29 s, completed Sep 10, 2026, 11:20:14 PM\n"

_SCALAFIX_LINT = _SCALAFIX_HEAD + "\n".join([
    "[info] compiling 1 Scala source to <root>/claim-algebra/target/scala-3.3.8/classes ...",
    "[info] done compiling",
    "[info] Running scalafix on 1 Scala sources (incremental)",
    "[error] <root>/claim-algebra/src/main/scala/claimalgebra/decision/Tally.scala:12:5: error: "
    "[DisableSyntax.var] mutable state should be avoided",
    "[error]     var sum = 0",
    "[error]     ^^^",
    "[error] (claimAlgebra / Compile / scalafix) scalafix.sbt.ScalafixFailed: LinterError",
    "[error] Total time: 14 s, completed Sep 10, 2026, 11:21:42 PM",
]) + "\n"

_SCALAFIX_REWRITE_DIFF = "\n".join([
    "[error] --- <root>/claim-algebra/src/main/scala/claimalgebra/decision/Tally.scala",
    "[error] +++ <expected fix>",
    "[error] @@ -1,7 +1,7 @@",
    "[error]  package claimalgebra.decision",
    "[error]  ",
    "[error] -import cats.kernel.Order",
    "[error]  import algebra.ring.CommutativeRig",
    "[error] +import cats.kernel.Order",
]) + "\n"

_SCALAFIX_REWRITE = _SCALAFIX_HEAD + _SCALAFIX_REWRITE_DIFF + "\n".join([
    "[error] (claimAlgebra / Compile / scalafix) scalafix.sbt.ScalafixFailed: TestError",
    "[error] Total time: 15 s, completed Sep 10, 2026, 11:22:04 PM",
]) + "\n"

_SCALAFIX_LINT_AND_REWRITE = _SCALAFIX_HEAD + "\n".join([
    "[error] <root>/claim-algebra/src/main/scala/claimalgebra/decision/Tally.scala:12:5: error: "
    "[DisableSyntax.var] mutable state should be avoided",
    "[error]     var sum = 0",
    "[error]     ^^^",
]) + "\n" + _SCALAFIX_REWRITE_DIFF + "\n".join([
    "[error] (claimAlgebra / Compile / scalafix) scalafix.sbt.ScalafixFailed: TestError LinterError",
    "[error] Total time: 16 s, completed Sep 10, 2026, 5:44:04 PM",
]) + "\n"

# A syntax error planted in `gate` beside the var in `claim-algebra`.
_SCALAFIX_COMPILE_FAILED_BESIDE_LINT = _SCALAFIX_HEAD + "\n".join([
    "[info] compiling 1 Scala source to <root>/gate/target/scala-3.3.8/classes ...",
    "[error] -- [E040] Syntax Error: <root>/gate/src/main/scala/gate/Model.scala:152:13 ",
    "[error] 152 |  def broken(: Int = 1",
    "[error]     |             ^",
    "[error]     |             an identifier expected, but ':' found",
    "[error] one error found",
    "[info] Running scalafix on 1 Scala sources (incremental)",
    "[error] <root>/claim-algebra/src/main/scala/claimalgebra/decision/Tally.scala:12:5: error: "
    "[DisableSyntax.var] mutable state should be avoided",
    "[error]     var sum = 0",
    "[error]     ^^^",
    "[error] (gate / Compile / compileIncremental) Compilation failed",
    "[error] (claimAlgebra / Compile / scalafix) scalafix.sbt.ScalafixFailed: LinterError",
    "[error] Total time: 15 s, completed Sep 10, 2026, 11:22:35 PM",
]) + "\n"

# Corpus W with a syntax error in Text.scala and nothing else.
_SCALAFIX_COMPILE_FAILED = "\n".join([
    "[info] set current project to planted (in build file:<root>/)",
    "[error] -- [E040] Syntax Error: <root>/src/main/scala/planted/Text.scala:34:13 ",
    "[error] 34 |  def broken(: Int = 1",
    "[error]    |             ^",
    "[error]    |             an identifier expected, but ':' found",
    "[error]    |",
    "[error]    | longer explanation available when compiling with `-explain`",
    "[error] one error found",
    "[error] (Compile / compileIncremental) Compilation failed",
    "[error] Total time: 5 s, completed Sep 10, 2026, 11:19:29 PM",
]) + "\n"

# `rules = [` left unclosed; one line per project, two of nine kept, plus the root's.
_SCALAFIX_BAD_CONF = _SCALAFIX_HEAD + "\n".join([
    *[f"[error] ({p}Compile / scalafix) scalafix.sbt.InvalidArgument: <root>/.scalafix.conf:28:0 error: "
      "<root>/.scalafix.conf: 28: List should have ended with ] or had a comma, instead had token: "
      "'=' (if you want '=' to be part of a string value, then double-quote it)\n"
      "[error] DisableSyntax.noNulls = true\n[error] ^" for p in ("credit / ", "gate / ", "")],
    "[error] Total time: 3 s, completed Sep 10, 2026, 11:20:23 PM",
]) + "\n"

_SCALAFIX_UNKNOWN_RULE = _SCALAFIX_HEAD + "\n".join([
    "[error] (credit / Compile / scalafix) scalafix.sbt.InvalidArgument: Unknown rule 'NoSuchRuleAnywhere'",
    "[error] (gate / Compile / scalafix) scalafix.sbt.InvalidArgument: Unknown rule 'NoSuchRuleAnywhere'",
    "[error] (Compile / scalafix) scalafix.sbt.InvalidArgument: Unknown rule 'NoSuchRuleAnywhere'",
    "[error] Total time: 9 s, completed Sep 10, 2026, 11:20:46 PM",
]) + "\n"

# `ThisBuild / semanticdbEnabled := true` removed; the lab's semantic rules then cannot run.
_SCALAFIX_NO_SEMANTICDB = _SCALAFIX_HEAD + "\n".join([
    "[error] (credit / Compile / scalafix) scalafix.sbt.InvalidArgument: The scalac compiler should "
    "produce semanticdb files to run semantic rules like OrganizeImports, TypelevelMapSequence, EffectMapConst.",
    "[error] To fix this problem for this sbt shell session, run `scalafixEnable` and try again.",
    "[error] To fix this problem permanently for your build, add the following settings to build.sbt:",
    "[error] ",
    "[error] inThisBuild(",
    "[error]   List(",
    '[error]     scalaVersion := "3.3.8",',
    "[error]     semanticdbEnabled := true,",
    "[error]     semanticdbVersion := scalafixSemanticdb.revision",
    "[error]   )",
    "[error] )",
    "[error] ",
    "[error] Total time: 11 s, completed Sep 10, 2026, 11:21:04 PM",
]) + "\n"

_W_HEAD = "\n".join([  # corpus W
    "[info] welcome to sbt 1.12.11 (Ubuntu Java 25.0.4)",
    "[info] loading settings for project w-build from plugins.sbt...",
    "[info] loading project definition from <root>/project",
    "[info] loading settings for project root from build.sbt...",
    "[info] set current project to planted (in build file:<root>/)",
]) + "\n"

# sbt-scalafix present, .scalafix.conf removed.
_SCALAFIX_NO_RULES = _W_HEAD + "\n".join([
    "[info] Running scalafix on 4 Scala sources",
    "[error] No rules requested to run",
    "[error] (Compile / scalafix) scalafix.sbt.ScalafixFailed: NoRulesError",
    "[error] Total time: 3 s, completed Sep 10, 2026, 11:18:50 PM",
]) + "\n"

# build.sbt ends inside an unclosed parenthesis; no command runs.
_SBT_BUILD_DID_NOT_LOAD = "\n".join([
    "[info] welcome to sbt 1.12.11 (Ubuntu Java 25.0.4)",
    "[info] loading settings for project w-build from plugins.sbt...",
    "[info] loading project definition from <root>/project",
    "[error] [<root>/build.sbt]:16: ')' expected but eof found.",
    "[warn] Project loading failed: (r)etry, (q)uit, (l)ast, or (i)gnore? (default: r)",
]) + "\n"

# sbt on PATH, java not: exit 127, nothing on stdout.
_SBT_NO_JAVA_STDERR = "\n".join([
    "<bin>/sbt: line 524: java: command not found",
    "mkdir: cannot create directory ‘’: No such file or directory",
    "<bin>/sbt: line 530: java: command not found",
    "<bin>/sbt: line 252: exec: java: not found",
]) + "\n"

# The wart scan's command until 2026-09-11: `-Dgate.wartScan=true "show wartremoverWarnings" "set ..."
# Test/compile`. It now shows two more scopes of the key and runs `clean` before Test/compile; the
# captures further down dated 2026-09-11 come from that command unless they say otherwise.
_WART_NOT_SET_UP = "\n".join([  # corpus P
    "[info] welcome to sbt 1.12.11 (Ubuntu Java 25.0.4)",
    "[info] loading project definition from <root>/project",
    "[info] loading settings for project root from build.sbt...",
    "[info] set current project to planted (in build file:<root>/)",
    "[error] Not a valid project ID: wartremoverWarnings",
    "[error] Expected ':'",
    "[error] Not a valid key: wartremoverWarnings (similar: printWarnings)",
    "[error] show wartremoverWarnings",
    "[error]                         ^",
]) + "\n"

_WART_SET_AND_COMPILE = "\n".join([
    "[info] Defining Global / concurrentRestrictions",
    "[info] The new value will be used by no settings or tasks.",
    "[info] Reapplying settings...",
    "[info] set current project to planted (in build file:<root>/)",
    "[info] compiling 4 Scala sources to <root>/target/scala-3.3.8/classes ...",
]) + "\n"

_WART_PROBE_ON_ONE_PROJECT = _W_HEAD + "\n".join([  # 17 warts listed; three kept
    "[info] * org.wartremover.warts.Any",
    "[info] * org.wartremover.warts.AsInstanceOf",
    "[info] * org.wartremover.warts.Var",
]) + "\n"

_WART_W_BASE = _WART_PROBE_ON_ONE_PROJECT + _WART_SET_AND_COMPILE + "\n".join([
    "[warn] -- Warning: <root>/src/main/scala/planted/Text.scala:8:8 ",
    "[warn] 8 |    var lastWasSpace = false",
    "[warn]   |    ^^^^^^^^^^^^^^^^^^^^^^^^",
    "[warn]   |    [wartremover:Var] var is disabled",
    "[warn] -- Warning: <root>/src/main/scala/planted/Text.scala:9:8 ",
    "[warn] 9 |    var i = 0",
    "[warn]   |    ^^^^^^^^^",
    "[warn]   |    [wartremover:Var] var is disabled",
    "[warn] two warnings found",
    "[success] Total time: 5 s, completed Sep 10, 2026, 11:22:59 PM",
]) + "\n"

# `ThisBuild / wartremoverWarnings := ...` removed from build.sbt: the plugin's own empty default.
_WART_PROBE_EMPTY_ONE_PROJECT = _W_HEAD + "[info] * \n" + _WART_SET_AND_COMPILE + \
    "[success] Total time: 5 s, completed Sep 10, 2026, 11:23:11 PM\n"

_LAB_WARTS = ("List(org.wartremover.warts.Any, org.wartremover.warts.AsInstanceOf, "
              "org.wartremover.warts.DefaultArguments, org.wartremover.warts.EitherProjectionPartial, "
              "org.wartremover.warts.IsInstanceOf, org.wartremover.warts.IterableOps, "
              "org.wartremover.warts.NonUnitStatements, org.wartremover.warts.Null, "
              "org.wartremover.warts.OptionPartial, org.wartremover.warts.Product, "
              "org.wartremover.warts.Return, org.wartremover.warts.Serializable, "
              "org.wartremover.warts.StringPlusAny, org.wartremover.warts.Throw, "
              "org.wartremover.warts.TripleQuestionMark, org.wartremover.warts.TryPartial, "
              "org.wartremover.warts.Var)")


def _lab_probe(value: str) -> str:
    """The lab's probe, one `<project> / wartremoverWarnings` heading and a tab-indented value per
    project; two of nine projects kept, plus the root's unprefixed one."""
    return _SCALAFIX_HEAD + "".join(f"[info] {p}wartremoverWarnings\n[info] \t{value}\n"
                                    for p in ("credit / ", "gate / ", ""))


_WART_PROBE_ON_AGGREGATE = _lab_probe(_LAB_WARTS)
_WART_PROBE_EMPTY_AGGREGATE = _lab_probe("List()") + _WART_SET_AND_COMPILE + \
    "[success] Total time: 43 s, completed Sep 10, 2026, 11:25:49 PM\n"

_WART_COMPILE_FAILED = _WART_PROBE_ON_ONE_PROJECT + _WART_SET_AND_COMPILE + "\n".join([
    "[error] -- [E040] Syntax Error: <root>/src/main/scala/planted/Text.scala:34:13 ",
    "[error] 34 |  def broken(: Int = 1",
    "[error]    |             ^",
    "[error]    |             an identifier expected, but ':' found",
    "[error] one error found",
    "[error] (Compile / compileIncremental) Compilation failed",
    "[error] Total time: 3 s, completed Sep 10, 2026, 11:23:43 PM",
]) + "\n"

# Captured 2026-09-11 on copies of corpus W, one build.sbt change each, trimmed, machine paths
# replaced by <root>; each listing of 17 warts keeps three.
_W_HEAD_0911 = "\n".join([
    "[info] welcome to sbt 1.12.11 (Ubuntu Java 25.0.4)",
    "[info] loading settings for project w-build from plugins.sbt...",
    "[info] loading project definition from <root>/project",
    "[info] loading settings for project root from build.sbt...",
    "[info] set current project to planted (in build file:<root>/)",
]) + "\n"
_WART_THREE = "\n".join([
    "[info] * org.wartremover.warts.Any",
    "[info] * org.wartremover.warts.AsInstanceOf",
    "[info] * org.wartremover.warts.Var",
]) + "\n"
_WART_SET_CLEAN = "\n".join([
    "[info] Defining Global / concurrentRestrictions",
    "[info] The new value will be used by no settings or tasks.",
    "[info] Reapplying settings...",
    "[info] set current project to planted (in build file:<root>/)",
    "[success] Total time: 0 s, completed Sep 11, 2026, 3:18:53 AM",
]) + "\n"
_WART_TWO_VARS = "\n".join([
    "[info] compiling 4 Scala sources to <root>/target/scala-3.3.8/classes ...",
    "[warn] -- Warning: <root>/src/main/scala/planted/Text.scala:8:8 ",
    "[warn] 8 |    var lastWasSpace = false",
    "[warn]   |    ^^^^^^^^^^^^^^^^^^^^^^^^",
    "[warn]   |    [wartremover:Var] var is disabled",
    "[warn] -- Warning: <root>/src/main/scala/planted/Text.scala:9:8 ",
    "[warn] 9 |    var i = 0",
    "[warn]   |    ^^^^^^^^^",
    "[warn]   |    [wartremover:Var] var is disabled",
    "[warn] two warnings found",
    "[info] done compiling",
]) + "\n"
_WART_TEST_COMPILE = "\n".join([
    "[info] compiling 1 Scala source to <root>/target/scala-3.3.8/test-classes ...",
    "[info] done compiling",
    "[success] Total time: 6 s, completed Sep 11, 2026, 3:18:59 AM",
]) + "\n"
_WART_TWO_VARS_AS_ERRORS = "\n".join([
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

# `Compile / compile / wartremoverWarnings ++= (if (wartScanMode) Warts.unsafe else Nil)` in place of
# the ThisBuild line: the project-scoped key lists nothing, and Test / compile delegates to Compile.
_WART_PER_TASK = _W_HEAD_0911 + "[info] * \n" + _WART_THREE + _WART_THREE + _WART_SET_CLEAN + \
    _WART_TWO_VARS + _WART_TEST_COMPILE
# The same run with its two warnings cut out: the listings of a per-task build whose tree has none.
_WART_PER_TASK_NO_WARTS = _W_HEAD_0911 + "[info] * \n" + _WART_THREE + _WART_THREE + _WART_SET_CLEAN + \
    "[info] compiling 4 Scala sources to <root>/target/scala-3.3.8/classes ...\n[info] done compiling\n" + \
    _WART_TEST_COMPILE
# The per-task build under the command of 2026-09-10, which showed only the project-scoped key.
_WART_PER_TASK_PROJECT_KEY_ONLY = _W_HEAD_0911 + "[info] * \n" + _WART_SET_AND_COMPILE.replace(
    "[info] compiling 4 Scala sources to <root>/target/scala-3.3.8/classes ...\n", "") + _WART_TWO_VARS + \
    "[success] Total time: 5 s, completed Sep 11, 2026, 3:18:46 AM\n"
# `ThisBuild / wartremoverErrors := (if (wartScanMode) Warts.unsafe else Nil)` and no
# wartremoverWarnings: every listing is empty and the warts fail the compile.
_WART_ERRORS_ONLY = _W_HEAD_0911 + "[info] * \n[info] * \n[info] * \n" + _WART_SET_CLEAN + \
    _WART_TWO_VARS_AS_ERRORS
# W as committed plus `ThisBuild / scalacOptions += "-Werror"`: Scala 3.3.8 reports each wart as an
# error, and `sbt Test/compile` without the property still exits 0.
_WART_WERROR_KEPT = _W_HEAD_0911 + _WART_THREE * 3 + _WART_SET_CLEAN + _WART_TWO_VARS_AS_ERRORS
# `ThisBuild / wartremoverWarnings := Warts.unsafe` (warts on all the time), the command of 2026-09-10
# run after `sbt Test/compile`: the options match, zinc compiles nothing, and no tag is printed.
_WART_ALWAYS_ON_NOTHING_COMPILED = _W_HEAD_0911 + _WART_THREE + \
    _WART_SET_CLEAN.replace("Total time: 0 s, completed Sep 11, 2026, 3:18:53 AM",
                            "Total time: 1 s, completed Sep 11, 2026, 3:15:58 AM")


class ScalafixRunTests(unittest.TestCase):
    """run_scalafix reads sbt's exit and its task-failure lines before it reads any finding."""

    def _run(self, returncode: int, out: str, stderr: str = ""):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td)
            with mock.patch.object(gate.subprocess, "run",
                                   return_value=_proc(returncode, _at(out, root), stderr)):
                return gate.run_scalafix(root)

    def test_not_set_up_is_not_wired_rather_than_zero_findings(self):
        with self.assertRaises(gate.NotWired) as cm:
            self._run(1, _SCALAFIX_NOT_SET_UP)
        self.assertEqual(str(cm.exception), "sbt-scalafix is not set up")

    def test_positive_lint_findings_are_counted_though_sbt_exits_1(self):
        tally = ("claim-algebra/src/main/scala/claimalgebra/decision/Tally.scala", "DisableSyntax.var")
        for name, out in (("lint", _SCALAFIX_LINT), ("lint beside a rewrite diff", _SCALAFIX_LINT_AND_REWRITE)):
            with self.subTest(name):
                self.assertEqual(self._run(1, out), {tally: 1})

    def test_a_rewrite_diff_alone_reads_as_zero_the_known_gap(self):
        self.assertEqual(self._run(1, _SCALAFIX_REWRITE), {})

    def test_negative_exit_0_is_an_empty_scan(self):
        self.assertEqual(self._run(0, _SCALAFIX_CLEAN), {})

    def test_a_compile_failure_is_passed_back_for_the_compile_precondition_to_judge(self):
        """Neither empty nor refused here: an empty scan only when the tree itself does not compile,
        which the runner cannot tell, and a lint line beside the compile failure is not counted."""
        for name, out in (("compile failure", _SCALAFIX_COMPILE_FAILED),
                          ("compile failure beside a lint finding", _SCALAFIX_COMPILE_FAILED_BESIDE_LINT)):
            with self.subTest(name):
                with self.assertRaises(gate.ScanCompileFailed) as cm:
                    self._run(1, out)
                self.assertIn("Compilation failed", str(cm.exception))
                self.assertEqual(len(str(cm.exception).splitlines()), 1, str(cm.exception))

    def test_did_not_run_a_failure_that_is_not_a_finding_raises_and_names_the_cause(self):
        for name, out, cause in (
                ("broken .scalafix.conf", _SCALAFIX_BAD_CONF, "List should have ended with ]"),
                ("unknown rule", _SCALAFIX_UNKNOWN_RULE, "Unknown rule 'NoSuchRuleAnywhere'"),
                ("no SemanticDB", _SCALAFIX_NO_SEMANTICDB, "should produce semanticdb files"),
                ("build did not load", _SBT_BUILD_DID_NOT_LOAD, "')' expected but eof found")):
            with self.subTest(name):
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    self._run(1, out)
                self.assertIn(cause, str(cm.exception))
                self.assertEqual(len(str(cm.exception).splitlines()), 1, str(cm.exception))

    def test_no_rules_configured_is_not_wired(self):
        """sbt-scalafix present with no .scalafix.conf runs no rule at all, the same position as no
        plugin: listed as not set up rather than an exit 2 that would push the repo off full mode.
        A branch that deletes the file still exits 2, because the label ran at the baseline."""
        with self.assertRaises(gate.NotWired) as cm:
            self._run(1, _SCALAFIX_NO_RULES)
        self.assertEqual(str(cm.exception), "no rules configured (no .scalafix.conf)")

    def test_did_not_run_sbt_without_a_jdk_raises(self):
        with self.assertRaises(gate.ScanOperationalError) as cm:
            self._run(127, "", _SBT_NO_JAVA_STDERR)
        self.assertIn("127", str(cm.exception))
        self.assertIn("java: not found", str(cm.exception))

    def test_did_not_run_sbt_missing_or_timed_out_raises(self):
        for err in (FileNotFoundError("sbt"), gate.subprocess.TimeoutExpired(["sbt"], 1800)):
            with self.subTest(type(err).__name__):
                with mock.patch.object(gate.subprocess, "run", side_effect=err):
                    with self.assertRaises(gate.ScanOperationalError):
                        gate.run_scalafix(Path("/r"))

    def test_did_not_run_failure_kinds_mixed_across_projects_raise(self):
        """One project's task line of each kind, the shapes captured above: a kind that means scalafix
        did not run makes the whole scan could-not-run, even beside a real lint finding."""
        lint = _SCALAFIX_LINT.replace("[error] Total time: 14 s, completed Sep 10, 2026, 11:21:42 PM\n", "")
        no_rules = "[error] (credit / Compile / scalafix) scalafix.sbt.ScalafixFailed: NoRulesError\n"
        unknown = ("[error] (gate / Compile / scalafix) scalafix.sbt.InvalidArgument: Unknown rule "
                   "'NoSuchRuleAnywhere'\n")
        end = "[error] Total time: 14 s, completed Sep 10, 2026, 11:21:42 PM\n"
        for name, out, named in (("NoRulesError beside LinterError", lint + no_rules + end, "NoRulesError"),
                                 ("InvalidArgument beside LinterError", lint + unknown + end,
                                  "Unknown rule 'NoSuchRuleAnywhere'")):
            with self.subTest(name):
                self.assertEqual(out.count("scalafix.sbt."), 2, "the fixture holds exactly two task lines")
                with self.assertRaises(gate.ScanOperationalError) as cm:
                    self._run(1, out)
                self.assertIn(named, str(cm.exception))
                self.assertIn("LinterError", str(cm.exception))

    def test_did_not_run_a_lint_failure_with_no_finding_this_parse_reads_is_refused(self):
        out = _SCALAFIX_LINT.replace("Tally.scala:12:5: error:", "Tally.scala: error:")
        self.assertNotIn(":12:5:", out, "the fixture lost exactly the position")
        with self.assertRaises(gate.ScanOperationalError) as cm:
            self._run(1, out)
        self.assertIn("LinterError", str(cm.exception))


class WartScanSetUpTests(unittest.TestCase):
    """run_wartremover asks sbt for wartremoverWarnings before compiling, in the same invocation."""

    def _run(self, returncode: int, out: str):
        with tempfile.TemporaryDirectory() as td:
            root = _tree(td)
            with mock.patch.object(gate.subprocess, "run", return_value=_proc(returncode, _at(out, root))):
                return gate.run_wartremover(root)

    def test_plugin_absent_is_not_wired(self):
        with self.assertRaises(gate.NotWired) as cm:
            self._run(1, _WART_NOT_SET_UP)
        self.assertEqual(str(cm.exception), "sbt-wartremover is not set up")

    def test_warts_left_off_for_the_scan_are_not_wired(self):
        """The measured cases: a lab copy and a W copy with the wartremoverWarnings line removed.
        Until 2026-09-10 each compiled clean and read as a wart scan with zero findings."""
        for name, out in (("one project", _WART_PROBE_EMPTY_ONE_PROJECT),
                          ("nine projects", _WART_PROBE_EMPTY_AGGREGATE)):
            with self.subTest(name):
                with self.assertRaises(gate.NotWired) as cm:
                    self._run(0, out)
                self.assertEqual(str(cm.exception), "no wartremoverWarnings under -Dgate.wartScan=true "
                                                    "(wartremoverErrors is not read)")

    def test_positive_a_probe_that_lists_warts_lets_the_scan_count(self):
        self.assertEqual(self._run(0, _WART_W_BASE), {("src/main/scala/planted/Text.scala", "Var"): 2})
        self.assertEqual(self._run(0, _WART_PROBE_ON_AGGREGATE + _WART_SET_AND_COMPILE), {})

    def test_a_compile_failure_is_passed_back_for_the_compile_precondition_to_judge(self):
        with self.assertRaises(gate.ScanCompileFailed) as cm:
            self._run(1, _WART_COMPILE_FAILED)
        self.assertIn("Compilation failed", str(cm.exception))

    def test_werror_kept_under_the_property_is_a_compile_failure_that_names_the_likely_cause(self):
        """Measured on W: `sbt Test/compile` exits 0, and the wart scan's compile fails on its warts.
        Until 2026-09-11 this read as an empty scan, so a new wart passed."""
        with self.assertRaises(gate.ScanCompileFailed) as cm:
            self._run(1, _WART_WERROR_KEPT)
        for token in ("Compilation failed", "Text.scala:8:8", "-Werror", "-Dgate.wartScan=true", "as errors"):
            self.assertIn(token, str(cm.exception))
        self.assertEqual(len(str(cm.exception).splitlines()), 1, str(cm.exception))

    def test_warts_turned_on_as_errors_are_a_compile_failure_not_a_scan_that_is_not_set_up(self):
        """Every listing is empty, but the run printed wart tags, so the plugin did run."""
        with self.assertRaises(gate.ScanCompileFailed):
            self._run(1, _WART_ERRORS_ONLY)

    def test_positive_warts_set_on_the_compile_task_are_read(self):
        """sbt-wartremover's per-task form leaves the project-scoped key empty. Until 2026-09-11 the
        probe read only that key, so this build was not set up and its printed warts were dropped."""
        var = {("src/main/scala/planted/Text.scala", "Var"): 2}
        self.assertEqual(self._run(0, _WART_PER_TASK), var)
        self.assertEqual(self._run(0, _WART_PER_TASK_PROJECT_KEY_ONLY), var)
        self.assertEqual(self._run(0, _WART_PER_TASK_NO_WARTS), {})

    def test_the_probe_shows_the_scopes_compile_reads(self):
        seen = []

        def fake_run(cmd, **kw):
            seen.append(cmd)
            return _proc(0, _WART_PER_TASK)

        with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
            gate.run_wartremover(Path("/r"))
        cmd = seen[0]
        for key in ("wartremoverWarnings", "Compile / compile / wartremoverWarnings",
                    "Test / compile / wartremoverWarnings"):
            self.assertLess(cmd.index(f"show {key}"), cmd.index("Test/compile"), key)

    def test_the_scan_compiles_from_clean(self):
        """Measured on W with warts on all the time: after `sbt Test/compile`, the scan without
        `clean` compiled nothing and printed no tag, and read as zero warts."""
        seen = []

        def fake_run(cmd, **kw):
            seen.append(cmd)
            return _proc(0, _WART_PER_TASK)

        with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
            gate.run_wartremover(Path("/r"))
        cmd = seen[0]
        self.assertEqual(cmd[-2:], ["clean", "Test/compile"])
        self.assertLess(cmd.index(_SERIAL_COMPILE), cmd.index("clean"))

    def test_did_not_run_a_scan_that_compiled_nothing_raises(self):
        with self.assertRaises(gate.ScanOperationalError) as cm:
            self._run(0, _WART_ALWAYS_ON_NOTHING_COMPILED)
        self.assertIn("compiled no Scala sources", str(cm.exception))

    def test_warts_left_off_are_not_wired_even_when_the_tree_does_not_compile(self):
        """The listing is printed before the compile starts, so the baseline records the label as
        not set up rather than as a scan that ran. Measured on W with the wart line removed and a
        syntax error planted: exit 1, `[info] * `, then `Compilation failed`."""
        out = _WART_PROBE_EMPTY_ONE_PROJECT.replace(
            "[success] Total time: 5 s, completed Sep 10, 2026, 11:23:11 PM\n", "") + "\n".join([
                "[error] -- [E040] Syntax Error: <root>/src/main/scala/planted/Text.scala:34:13 ",
                "[error] 34 |  def broken(: Int = 1",
                "[error] one error found",
                "[error] (Compile / compileIncremental) Compilation failed",
                "[error] Total time: 3 s, completed Sep 10, 2026, 11:42:56 PM",
            ]) + "\n"
        self.assertEqual(out.count("[info] * \n"), 1)
        with self.assertRaises(gate.NotWired):
            self._run(1, out)

    def test_did_not_run_a_build_that_does_not_load_raises(self):
        with self.assertRaises(gate.ScanOperationalError) as cm:
            self._run(1, _SBT_BUILD_DID_NOT_LOAD)
        self.assertIn("')' expected but eof found", str(cm.exception))

    def test_did_not_run_exit_0_without_the_probe_raises(self):
        with self.assertRaises(gate.ScanOperationalError):
            self._run(0, _W_HEAD + _WART_SET_AND_COMPILE)

    def test_did_not_run_sbt_missing_raises(self):
        with mock.patch.object(gate.subprocess, "run", side_effect=FileNotFoundError("sbt")):
            with self.assertRaises(gate.ScanOperationalError):
                gate.run_wartremover(Path("/r"))

    def test_the_probe_runs_before_the_compile_in_one_invocation(self):
        seen = []

        def fake_run(cmd, **kw):
            seen.append(cmd)
            return _proc(0, _WART_PROBE_ON_ONE_PROJECT + _WART_SET_AND_COMPILE)

        with mock.patch.object(gate.subprocess, "run", side_effect=fake_run):
            gate.run_wartremover(Path("/r"))
        self.assertEqual(len(seen), 1)
        cmd = seen[0]
        self.assertLess(cmd.index("-Dgate.wartScan=true"), cmd.index("show wartremoverWarnings"))
        self.assertLess(cmd.index("show wartremoverWarnings"), cmd.index("Test/compile"))


class ScalaCheckAIndependenceTests(unittest.TestCase):
    def test_a_runner_that_is_not_set_up_does_not_hide_the_other(self):
        found = {("a/A.scala", "Var"): 1}
        for missing, present in (("run_scalafix", "run_wartremover"), ("run_wartremover", "run_scalafix")):
            with self.subTest(missing=missing):
                why = gate.NotWired(f"{missing}: not set up")
                with mock.patch.object(gate, missing, side_effect=why) as m, \
                        mock.patch.object(gate, present, return_value=gate.Counter(found)) as p:
                    out = gate.ScalaToolchain().static_analysis(Path("/r"))
                m.assert_called_once()
                p.assert_called_once()
                self.assertEqual(sorted(out), ["scalafix", "wartremover"])
                label = {"run_scalafix": "scalafix", "run_wartremover": "wartremover"}
                self.assertIs(out[label[missing]], why)
                self.assertEqual(out[label[present]], found)

    def test_a_runner_whose_compile_failed_is_passed_back_and_does_not_hide_the_other(self):
        found = {("a/A.scala", "Var"): 1}
        for failed, present in (("run_scalafix", "run_wartremover"), ("run_wartremover", "run_scalafix")):
            with self.subTest(failed=failed):
                why = gate.ScanCompileFailed(f"{failed}: Compilation failed")
                with mock.patch.object(gate, failed, side_effect=why) as m, \
                        mock.patch.object(gate, present, return_value=gate.Counter(found)) as p:
                    out = gate.ScalaToolchain().static_analysis(Path("/r"))
                m.assert_called_once()
                p.assert_called_once()
                label = {"run_scalafix": "scalafix", "run_wartremover": "wartremover"}
                self.assertIs(out[label[failed]], why)
                self.assertEqual(out[label[present]], found)


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

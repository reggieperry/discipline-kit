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

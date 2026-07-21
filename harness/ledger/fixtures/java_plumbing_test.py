#!/usr/bin/env python3
"""Red-first fixture for gate.py's Java build-marker plumbing (v1.3.0).

A pom.xml root check_command()s to `mvn -B -q verify`; a gradle-only root to the hermetic gradle
wrapper (`--no-daemon --console=plain`); code_exts() auto-detects `.java` for pom.xml/build.gradle
roots and does NOT add `.java` for a non-Java root (e.g. build.sbt) carrying a vendored .java file,
so a vendored .java never fires the gate. Red against a gate.py with no Java-marker detection
(pom.xml check_command() is None; a pom.xml root's code_exts() falls back to the broad CODE_EXTS).

Run: python3 harness/ledger/fixtures/java_plumbing_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / "gate.py"
MODEL = Path(__file__).resolve().parent.parent / "model.py"


def load_gate(root: Path):
    (root / "ledger").mkdir(parents=True, exist_ok=True)
    dst = root / "ledger" / "gate.py"
    shutil.copy(GATE, dst)
    shutil.copy(MODEL, root / "ledger" / "model.py")  # gate.py imports the shared calculus
    spec = importlib.util.spec_from_file_location("gate_under_test", dst)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        # (a) a Maven repo → mvn verify, and .java is the auto-detected extension
        root = Path(td) / "maven"
        (root / "ledger").mkdir(parents=True)
        (root / "pom.xml").write_text("<project/>")
        g = load_gate(root)
        assert g.check_command() == ["mvn", "-B", "-q", "verify"], \
            f"pom.xml must check_command() to mvn verify, got {g.check_command()!r}"
        assert g.code_exts() == (".java",), \
            f"pom.xml must auto-detect exactly .java, got {g.code_exts()!r}"

    with tempfile.TemporaryDirectory() as td:
        # (b) a Gradle-wrapper-only repo → the hermetic wrapper (no daemon)
        root = Path(td) / "gradlew"
        (root / "ledger").mkdir(parents=True)
        (root / "build.gradle").write_text("")
        (root / "gradlew").write_text("")
        g = load_gate(root)
        assert g.check_command() == ["./gradlew", "--no-daemon", "--console=plain", "check"], \
            f"gradlew root must check_command() to the wrapper, got {g.check_command()!r}"
        assert ".java" in g.code_exts(), f"build.gradle must auto-detect .java, got {g.code_exts()!r}"

    with tempfile.TemporaryDirectory() as td:
        # (c) a Gradle repo WITHOUT the wrapper → bare gradle, still hermetic
        root = Path(td) / "gradle"
        (root / "ledger").mkdir(parents=True)
        (root / "build.gradle.kts").write_text("")
        g = load_gate(root)
        assert g.check_command() == ["gradle", "--no-daemon", "--console=plain", "check"], \
            f"build.gradle.kts (no wrapper) must check_command() to gradle, got {g.check_command()!r}"

    with tempfile.TemporaryDirectory() as td:
        # (d) a non-Java (Scala) repo with a VENDORED .java → .java must NOT be a detected ext,
        #     so a change to the vendored file never fires the gate.
        root = Path(td) / "scala"
        (root / "ledger").mkdir(parents=True)
        (root / "build.sbt").write_text("")
        (root / "vendor").mkdir()
        (root / "vendor" / "Reference.java").write_text("class Reference {}\n")
        g = load_gate(root)
        exts = g.code_exts()
        assert exts == (".scala", ".sc", ".sbt"), \
            f"a Scala repo must detect only scala exts, got {exts!r}"
        assert ".java" not in exts, "a vendored .java under a Scala repo must NOT fire the gate"

    print("java_plumbing_test: PASS (mvn/gradle check_command, .java auto-detect, vendored-java inert)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

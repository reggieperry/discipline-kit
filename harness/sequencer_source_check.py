#!/usr/bin/env python3
"""ADR-0001/D5's court: no sequencer source decides from harness-written state.

That record's Falsification section names this check and says plainly why it was not claimed
when the record landed: "a grep-shaped source check that activates with the first sequencer
source; today it would grep nothing and prove nothing." The sources exist now, so it activates,
and its denominators are printed on every run for the reason the whole kit exists: a clean report
over an empty corpus and a clean report over a real one look identical from outside.

WHAT THIS DOES NOT CATCH, stated so it is not mistaken for caught: a forbidden key composed at
runtime ("is_" + "error", an f-string building the denials key) greps clean, because the check
strips comments and docstrings and then matches literals — the ADR's own grep-shaped scope.
Measured: two composed-key shapes read clean against this check. The real exposure is drift
under review, not evasion — a hostile author of sequencer source has better options than
hiding a key, and the review discipline is the court for both.

WHAT IT LOOKS FOR, each pattern carrying the decision it serves:

    status-frontmatter   a story spec's `status:` field read for control flow. ADR-0001/D5, and
                         the design's own conclusion that status fields are advisory.
    event-log            the append-only audit store opened. It is sequencer-written and
                         agent-writable with friction-only protection, which is exactly why
                         nothing is decided from it.
    stream-verdict       `is_error`, `subtype`, `permission_denials` and the rest of the
                         conjunction the denial probe returned on a phase that did nothing.
    result-string        a wrapper's own return text consumed, which ADR-0004/D1 names as a
                         falsifier of the bare-invocation substrate.
    harness-json         a harness-written stream parsed anywhere but the admitted reader.
    stream-file          a `.jsonl` named anywhere but the admitted reader.
    subagent-spawn       a phase run as a subagent, which ADR-0004/D1 forbids on the
                         advancement path.
    session-resume       `--resume`, which ADR-0004/D4 rules out and which is unmeasured under
                         headless invocation.

THE ONE ADMITTED READER. ADR-0001/D5 admits session ids and liveness signals, so exactly one
function may touch a stream: `admitted_signals`. The two stream-shaped patterns are exempt
inside its body and nowhere else, and the verdict-shaped patterns are exempt nowhere at all,
including inside it. The check refuses to report clean when that function is absent: with
nothing to exempt it has not established the property it exists for, and that reads
could-not-run rather than pass.

THE ALLOWLIST IS DATA, AND IT IS READ. The reader keeps `ADMITTED_KEYS` and drops every other
field, so widening that set widens what the runtime admits without changing a line of control
flow. The set is parsed out of the source and compared against what the record admits, which is
the session id and the record kind. A pattern sweep alone would not see that edit.

IT IS GREP-SHAPED OVER CODE RATHER THAN OVER TEXT, and the distinction is what keeps it from
crying wolf. Comments and docstrings are dropped before the patterns run, because a record that
may not name `is_error` cannot state its own reason for refusing to read it, and a check that
punishes the explanation gets edited into silence. Comments come out through `tokenize` and
docstrings through the parse tree, so nothing depends on a regex guessing where a string ends.

    exit 0   clean, with the denominators printed
    exit 1   at least one finding, each named with pattern, file and line
    exit 2   NOTHING WAS ESTABLISHED: no directory, no sources, no admitted reader, no readable
             allowlist, or a source that will not parse. Never a pass.

Usage: python3 harness/sequencer_source_check.py [--dir <directory>]

`--dir` defaults to `harness/chain`, the sequencer runtime. It is what lets
`harness/fixtures/core_test.py` point the check at throwaway trees with planted violations,
which is the only way to observe it firing.
"""
from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

CLEAN = 0
FINDING = 1
COULD_NOT_RUN = 2

ADMITTED_READER = "admitted_signals"
ALLOWLIST_CONSTANT = "ADMITTED_KEYS"

# What ADR-0001/D5 admits from harness-written state: the session id, for resumption and
# diagnosis, and the record kind, for the liveness read. Anything else in the runtime's own
# allowlist is a widening of what it admits and is a finding here.
ALLOWED_KEYS = frozenset({"session_id", "type"})


@dataclass(frozen=True)
class Pattern:
    name: str
    regex: re.Pattern[str]
    why: str
    exempt_in_reader: bool


PATTERNS = (
    Pattern("status-frontmatter", re.compile(r"status\s*:|frontmatter"),
            "a story spec's status field is advisory, and git is authority (ADR-0001/D5)",
            False),
    Pattern("event-log", re.compile(r"event[_-]?logs?|/var/log|chain[_-]?log"),
            "the event log is audit, never a decision (ADR-0001/D5)", False),
    Pattern("stream-verdict",
            re.compile(r"\b(is_error|subtype|permission_denials|stop_reason|num_turns"
                       r"|total_cost_usd)\b"),
            "every one of these reported success on a phase that did nothing (ADR-0001/D2)",
            False),
    Pattern("result-string",
            re.compile(r"\[\s*['\"]result['\"]\s*\]|\.get\(\s*['\"]result['\"]"),
            "a wrapper's return string on an advancement path (ADR-0004/D1)", False),
    Pattern("harness-json", re.compile(r"\bjson\.loads?\s*\("),
            "harness-written state parsed outside the admitted reader (ADR-0001/D5)", True),
    Pattern("stream-file", re.compile(r"\.jsonl\b"),
            "a harness stream named outside the admitted reader (ADR-0001/D5)", True),
    Pattern("subagent-spawn", re.compile(r"\bTask\s*\(|subagent"),
            "no phase runs as a subagent on the advancement path (ADR-0004/D1)", False),
    Pattern("session-resume", re.compile(r"--resume\b"),
            "resumption under headless invocation is unmeasured (ADR-0004/D4)", False),
)


class CouldNotRun(Exception):
    """Nothing was established, and the reason is named. Never a pass."""


@dataclass(frozen=True)
class Source:
    path: Path
    code: dict[int, str]
    dropped: int
    reader: tuple[int, int] | None
    allowlist: frozenset[str] | None


def docstring_lines(tree: ast.AST) -> set[int]:
    """Every line held by a module, class or function docstring."""
    held: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            held.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return held


def reader_span(tree: ast.AST) -> tuple[int, int] | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == ADMITTED_READER:
            return node.lineno, node.end_lineno or node.lineno
    return None


def literal_keys(value: ast.AST) -> frozenset[str] | None:
    """The declared allowlist as data, or None when it is not a literal a court can read."""
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) \
            and value.func.id in {"frozenset", "set"}:
        if not value.args:
            return frozenset()
        value = value.args[0]
    try:
        members = ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError):
        return None
    if not isinstance(members, (set, frozenset, list, tuple)):
        return None
    return frozenset(str(m) for m in members)


def declared_allowlist(tree: ast.AST) -> frozenset[str] | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == ALLOWLIST_CONSTANT for t in node.targets):
            return literal_keys(node.value)
    return None


def code_view(path: Path) -> Source:
    """The file with its comments and docstrings removed, keyed by original line number."""
    try:
        text = path.read_text(errors="replace")
    except OSError as e:
        raise CouldNotRun(f"{path} could not be read: {e}") from e
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as e:
        raise CouldNotRun(f"{path} does not parse, so nothing in it was examined: {e}") from e

    lines = text.splitlines()
    view = list(lines)
    held = docstring_lines(tree)
    for n in held:
        if 1 <= n <= len(view):
            view[n - 1] = ""
    comment_lines = 0
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type != tokenize.COMMENT:
                continue
            row, col = token.start
            if 1 <= row <= len(view):
                view[row - 1] = view[row - 1][:col]
                comment_lines += 1
    except (tokenize.TokenError, IndentationError) as e:
        raise CouldNotRun(f"{path} could not be tokenized, so nothing in it was examined: {e}") \
            from e

    code = {n: line for n, line in enumerate(view, start=1) if line.strip()}
    return Source(path=path, code=code, dropped=len(held) + comment_lines,
                  reader=reader_span(tree), allowlist=declared_allowlist(tree))


def sources(directory: Path) -> list[Source]:
    if not directory.is_dir():
        raise CouldNotRun(f"{directory} is not a directory, so no sequencer source was examined")
    found = [p for p in sorted(directory.rglob("*.py")) if "__pycache__" not in p.parts]
    if not found:
        raise CouldNotRun(f"no python source under {directory}, so a clean report would say "
                          "nothing")
    return [code_view(p) for p in found]


def sweep(source: Source) -> list[str]:
    """Every finding in one file, as a printable line."""
    out: list[str] = []
    for number, line in sorted(source.code.items()):
        inside = source.reader is not None and source.reader[0] <= number <= source.reader[1]
        for pattern in PATTERNS:
            if pattern.exempt_in_reader and inside:
                continue
            if pattern.regex.search(line):
                out.append(f"{pattern.name}: {source.path}:{number}: {line.strip()[:90]} "
                           f"({pattern.why})")
    return out


def examine(directory: Path, say) -> int:
    found = sources(directory)
    code_lines = sum(len(s.code) for s in found)
    dropped = sum(s.dropped for s in found)
    readers = [s for s in found if s.reader is not None]
    say(f"source-check: {len(found)} file(s) examined under {directory}, {code_lines} code "
        f"line(s), {dropped} comment and docstring line(s) dropped")
    say(f"source-check: {len(PATTERNS)} pattern(s) applied, {len(readers)} admitted reader(s)"
        + (": " + ", ".join(f"{s.path.name}::{ADMITTED_READER} lines {s.reader[0]}-{s.reader[1]}"
                            for s in readers) if readers else ""))

    if not readers:
        raise CouldNotRun(
            f"no {ADMITTED_READER} in {directory}, so the one admitted reader of harness-written "
            "state does not exist and nothing here has been established (ADR-0001/D5)"
        )
    declaring = [s for s in found if s.allowlist is not None]
    if not declaring:
        raise CouldNotRun(
            f"no readable {ALLOWLIST_CONSTANT} in {directory}: the admitted reader keeps a "
            "declared key set, and a set no court can read is not a declaration"
        )

    findings = [f for s in found for f in sweep(s)]
    for s in declaring:
        widened = sorted(s.allowlist - ALLOWED_KEYS)
        say(f"source-check: allowlist {ALLOWLIST_CONSTANT} in {s.path.name}: "
            f"{', '.join(sorted(s.allowlist)) or 'empty'}")
        if widened:
            findings.append(
                f"allowlist-widened: {s.path}: {ALLOWLIST_CONSTANT} admits "
                f"{', '.join(widened)}, which ADR-0001/D5 does not: harness state is admitted "
                f"for {', '.join(sorted(ALLOWED_KEYS))} and nothing else"
            )
    for finding in findings:
        say(f"source-check: FINDING: {finding}")
    if findings:
        return FINDING
    say("source-check: clean (no sequencer source decides from harness state, and the stream is "
        "read in one place)")
    return CLEAN


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent / "chain"),
                    help="the sequencer runtime to examine")
    a = ap.parse_args()
    try:
        return examine(Path(a.dir), print)
    except CouldNotRun as e:
        print(f"source-check: VOID: {e}; not a pass", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    raise SystemExit(main())

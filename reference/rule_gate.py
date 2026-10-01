#!/usr/bin/env python3
"""rule_gate: refuse a write whose path-scoped rules are not in the calling agent's context.

A PreToolUse hook for Write, Edit, MultiEdit and NotebookEdit. Wire it in the user's
settings.json (the kit's claude-user/settings.json carries the block) and install this file to
~/.claude/discipline/rule_gate.py, or vendor it into a repository at .claude/hooks/rule_gate.py
and wire it in that repository's .claude/settings.json (`install.sh --refresh-rules` does both,
from the same release tag as the rules). It reads the hook's JSON on stdin, prints at most one JSON
object on stdout, and ALWAYS exits 0, because exit 2 is how a hook blocks a call and a crash that
happened to exit 2 would block every write on the machine.

WHY IT EXISTS. Claude Code 2.1.286 loads a path-scoped `.claude/rules/*.md` only after a Read
of a matching file, or an @-mention. Write and Edit never load one. A session that writes a
Python file it never read writes it without the Python rules, and nothing says so: measured in
one real session, 12 of 37 writes ran without their language pack. This gate makes the rule's
presence a precondition of the write rather than an accident of what was read first.

WHAT COUNTS AS LOADED. Only the calling agent's own transcript, after its last
compact_boundary, is evidence. The main thread reads `transcript_path`; a subagent (the hook
input carries `agent_id`) reads `<transcript_path minus .jsonl>/subagents/**/agent-<id>.jsonl`,
because a subagent starts with no path rules and does not inherit the parent's. A rule counts on
any of:

  nested_memory attachment      attachment.path, the automatic load after a matching Read
  instructions attachment       attachment.files[].path, the session-start and post-compact set
  file attachment               attachment.filename, a restore after compaction
  full Read of the rule         the Read tool_use (no offset, no limit) paired by tool_use_id with
                                a tool_result that is not an error; toolUseResult is NOT required,
                                because subagent transcripts mostly lack it
  this gate's own inlined text  a tool_result holding the line
                                `rule-gate: inlined sha256=<hex> path=<abs>`
  file_unchanged                only when a counted load of the same path precedes it

The compaction summary never counts: it can paraphrase a rule without carrying it. Loads before
the last compact_boundary never count: compaction clears them. A rule also counts when ANY loaded
file has the same sha256 as its content, which covers worktree copies of one rule. A tool_result
(a Read, or this gate's own refusal) counts only once the model has seen it, which is in its next
response: a result answering another call of the response the checked call belongs to does not
count, because the checked call was generated before that result existed. The response is named
by message.id, which every entry of one response carries; see _current_message.

WHAT IT DOES ON A MISS. It refuses the call and puts the full text of every missing rule in the
refusal, each after its marker line, so the model has the rule in view when it regenerates.
Adding context instead of refusing would not help: by the time a PreToolUse hook runs, the
content it would have shaped already exists. Above DISCIPLINE_RULE_GATE_MAX_INLINE bytes (default
400000) the refusal lists the paths and says to Read each one whole instead.

THE PENDING SET AND THE BREAKER. Per (session, agent), a small JSON file records each rule the
gate has given, when, and the tool_use_id of the call it refused. A later call that needs a
pending rule looks for that call's result in the transcript (_refusal_fate):
  - the rule is counted: the entry is cleared;
  - the result holds the rule but answers a call of this same response: a sibling call, refused
    with a SHORT reason, since the text was already given;
  - the result is there without the rule: Claude Code keeps only one reason when several hooks
    refuse a call, so another hook's refusal took the place of this one. The rule is given again;
  - the result is not on disk yet: a sibling, until 120 s have passed;
  - the model has seen the rule given and the gate still cannot count it, or the result has
    been missing for 120 s, or the rule has been given REFUSAL_LIMIT times without the model
    seeing it: the gate cannot see its own remedy. It allows, logs a BLIND line, and warns the
    model by name. A blind rule is never refused again for that session and agent, which is what
    stops a refusal loop.
An entry given before the current compact_boundary is stale rather than blind: compaction
dropped the text, so the gate gives it again.

TWO COPIES DEFER TO THE PROJECT'S. With both wired, each would refuse the same write. A copy
that is not the project's own (the user-level one) allows silently and logs one DEFER line when
a project rule applies and the project's .claude/settings.json or .claude/settings.local.json has
a PreToolUse command hook whose matcher selects the tool and whose command runs that project's
.claude/hooks/rule_gate.py, and that file exists. A command runs it when its script, after an
optional python interpreter, is $CLAUDE_PROJECT_DIR/.claude/hooks/rule_gate.py (counted only
while that variable is set), .claude/hooks/rule_gate.py relative to the project, or an absolute
path to that same file; a command that merely mentions the path runs nothing. The project's copy
never defers, so a repository pins the gate it was refreshed to. It knows itself by the path it
was run from, not by where symlinks resolve: a .claude/hooks linked out of the repository must
not make it defer to itself.

FAIL OPEN, NEVER SILENTLY. A missing or unreadable transcript, a tool input of an unknown shape,
or any internal error allows the call, appends a line to the log, and adds a one-line warning to
the model's context. A format change in Claude Code must not block every edit on the machine,
and the log keeps "the gate was not looking" apart from "nothing was wrong".

WHAT IT DOES NOT CHECK. Bash. Of 3,024 code-file write targets in 34,340 real commands, 71 were
literal paths inside the repository; parsing the rest produced only false refusals. A target
outside the session's project root (CLAUDE_PROJECT_DIR, else the hook's cwd) is not checked
either. That follows Claude Code's loader as read in the 2.1.286 binary, not a measurement: it
loads no path-scoped rule for a file outside every working directory. A directory added with
--add-dir is a working directory too, and the gate does not check files there.

ENVIRONMENT.
  DISCIPLINE_RULE_GATE=off            disables the gate
  DISCIPLINE_RULE_GATE_LOG            log file (default ~/.claude/discipline/rule-gate.log)
  DISCIPLINE_RULE_GATE_STATE          state directory (default ~/.claude/discipline/state)
  DISCIPLINE_RULE_GATE_MAX_INLINE     inline cap in bytes (default 400000)

Standard library only; Python 3.8 or later.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
import time
import warnings
from functools import lru_cache
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

# The tools the gate checks, and the input key that names each one's target. MultiEdit is absent
# from 2.1.286's tool list but still present in its hook code, so it stays.
GATED: Dict[str, str] = {
    "Write": "file_path",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
}

MARKER_PREFIX = "rule-gate: inlined"
MARKER_RE = re.compile(r"^rule-gate: inlined sha256=([0-9a-f]{64}) path=(.+)$", re.M)
RETRY_LINE = ("These rules are now in your context. Apply them and retry the write in your NEXT "
              "message, not in this one.")

SIBLING_WINDOW_S = 120
REFUSAL_LIMIT = 3
STATE_TTL_S = 7 * 24 * 3600
DEFAULT_MAX_INLINE = 400000
CHUNK = 1 << 20

# Claude Code's file-unchanged stub, the only way to recognize it where toolUseResult is absent.
UNCHANGED_TEXT = "file unchanged since your last Read"


class TranscriptUnreadable(Exception):
    """The transcript exists but nothing in the scan window parses as a transcript entry."""


class Rule(NamedTuple):
    path: str
    sha: str
    data: bytes


class Loaded(NamedTuple):
    paths: Set[str]          # files in context, by path
    shas: Set[str]           # rule contents the gate inlined, in results the model has seen
    results: Dict[str, str]  # tool_use_id -> result text, for the calls the caller watches
    unseen: Set[str]         # tool_use_ids whose results the current response has not seen


# --- frontmatter --------------------------------------------------------------------------------
#
# Claude Code reads `paths:` with a YAML parser, flattens a list, splits each string on commas
# outside braces, expands braces, strips one trailing `/**` from each glob, and treats an empty
# result, or one where every glob is `**`, as no paths at all: the rule is unconditional, in
# context from session start, and this gate skips it. The parser below covers the YAML shapes a
# rule's frontmatter uses (a block list, quoted or not; a flow list; a plain or quoted string, on
# the key's line or the lines after it; a `|` or `>` block scalar; a quoted key), not YAML in
# general: anchors, aliases and tags are not read.

def _frontmatter(text: str) -> Optional[str]:
    if text.startswith("﻿"):
        text = text[1:]
    m = re.match(r"---[ \t]*\r?\n(.*?)^---[ \t]*(?:\r?\n|\Z)", text, re.S | re.M)
    return m.group(1) if m else None


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return str(json.loads(s))
        except ValueError:
            return s[1:-1]
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    return s


def _scalar(s: str) -> str:
    """One YAML scalar: a quoted string up to its closing quote, or a plain one minus a comment."""
    s = s.strip()
    if s[:1] in ('"', "'"):
        q = s[0]
        i = 1
        while i < len(s):
            if q == '"' and s[i] == "\\":
                i += 2
                continue
            if s[i] == q:
                if q == "'" and s[i + 1:i + 2] == "'":
                    i += 2
                    continue
                return _unquote(s[:i + 1])
            i += 1
        return s[1:]
    return re.split(r"\s+#", s, maxsplit=1)[0].strip()


def _split_top(s: str, sep: str = ",") -> List[str]:
    """Split on `sep` outside quotes and braces."""
    out, cur, depth, quote = [], "", 0, ""
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = ""
        elif ch in ("'", '"'):
            quote = ch
            cur += ch
        elif ch == "{":
            depth += 1
            cur += ch
        elif ch == "}":
            depth -= 1
            cur += ch
        elif ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def _block_scalar(header: str, body: List[str]) -> str:
    """A `|` or `>` block scalar: the indented lines after the key, kept or folded, then chomped."""
    indent = min((len(ln) - len(ln.lstrip(" \t")) for ln in body if ln.strip()), default=0)
    lines = [ln[indent:] if ln.strip() else "" for ln in body]
    while lines and not lines[-1]:
        lines.pop()
    if header.startswith("|"):
        text = "\n".join(lines)
    else:
        # Folding joins neighbouring lines with a space; an empty line stands for one newline.
        text, gap = "", False
        for ln in lines:
            if not ln:
                text += "\n"
                gap = True
            else:
                text += ("" if not text or gap else " ") + ln
                gap = False
    if "-" in header:
        return text
    return text + "\n" if text else text


def raw_paths(text: str) -> Optional[list]:
    """The `paths:` value as written: None without frontmatter or key, [] for an empty value."""
    fm = _frontmatter(text)
    if fm is None:
        return None
    lines = fm.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"(?:paths|\"paths\"|'paths')[ \t]*:(.*)$", line)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest.startswith("#"):
            rest = ""
        if rest.startswith("["):
            flow = rest
            j = i + 1
            while "]" not in _strip_quoted(flow) and j < len(lines):
                flow += " " + lines[j].strip()
                j += 1
            inner = flow[1:flow.rfind("]")] if "]" in flow else flow[1:]
            return [_scalar(x) for x in _split_top(inner) if x.strip()]
        # The lines that belong to the value: indented ones, and blank ones between them.
        body: List[str] = []
        for nxt in lines[i + 1:]:
            if nxt.strip() and nxt[:1] not in (" ", "\t"):
                break
            body.append(nxt)
        if re.match(r"[|>][0-9+-]*(?:\s+#.*)?$", rest):
            return [_block_scalar(rest, body)]
        if rest:
            return [_scalar(rest)]
        items: List[str] = []
        for nxt in lines[i + 1:]:
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                continue
            item = re.match(r"[ \t]*-[ \t]+(.*)$|[ \t]*-$", nxt)
            if item:
                if item.group(1) is not None:
                    items.append(_scalar(item.group(1)))
                continue
            if nxt[:1] in (" ", "\t"):
                if not items:
                    # A scalar on the lines after the key: YAML joins them with single spaces.
                    flat = " ".join(ln.strip() for ln in body
                                    if ln.strip() and not ln.lstrip().startswith("#"))
                    return [_scalar(flat)]
                continue
            break
        return items
    return None


def _strip_quoted(s: str) -> str:
    return re.sub(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^']|'')*'", "", s)


def expand_braces(glob_text: str, limit: int = 1000) -> List[str]:
    """Claude Code's brace expansion: innermost-first `{a,b}` alternatives, trimmed, capped."""
    if "{" not in glob_text:
        return [glob_text]
    done: List[str] = []
    stack = [glob_text]
    while stack:
        cur = stack.pop()
        m = re.match(r"^([^{]*)\{([^}]+)\}(.*)$", cur, re.S)
        if not m:
            done.append(cur)
            continue
        alts = [a.strip() for a in m.group(2).split(",")]
        if len(done) + len(stack) + len(alts) > limit:
            return [glob_text]
        for alt in reversed(alts):
            stack.append(m.group(1) + alt + m.group(3))
    return done


def split_paths_value(value) -> List[str]:
    """Claude Code's reading of a `paths:` value into globs, before normalization."""
    if isinstance(value, list):
        return [g for v in value for g in split_paths_value(v)]
    if not isinstance(value, str):
        return []
    parts = [p.strip() for p in _split_top_braces(value)]
    return [g for p in parts if p for g in expand_braces(p)]


def _split_top_braces(s: str) -> List[str]:
    out, cur, depth = [], "", 0
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        cur += ch
    out.append(cur)
    return out


def normalize_globs(globs: Sequence[str]) -> Optional[List[str]]:
    """Strip one trailing `/**`, drop empties; None when the rule is unconditional."""
    out = [g[:-3] if g.endswith("/**") else g for g in globs]
    out = [g for g in out if g]
    if not out or all(g == "**" for g in out):
        return None
    return out


def parse_paths_frontmatter(text: str) -> Optional[List[str]]:
    """The globs a rule is scoped to, or None for a rule with no usable `paths:`."""
    raw = raw_paths(text)
    if raw is None:
        return None
    return normalize_globs(split_paths_value(raw))


# --- the matcher --------------------------------------------------------------------------------
#
# A port of node-ignore as bundled in Claude Code 2.1.286, which Claude Code calls as
# `ignore().add(globs).ignores(relpath)` with the path relative to the directory holding
# `.claude`. The replacer list below is node-ignore's, in its order; each step rewrites the
# pattern toward a regular expression. Golden vectors generated by the bundled copy pin it
# (harness/fixtures/rule_gate_vectors.json). The source the replacers build is JavaScript's
# dialect, so _js_regex_to_py rewrites the places where Python's `re` reads it differently (an
# empty class, a `[` inside a class, an escaped letter) before it is compiled. A pattern that
# still does not compile is dropped, as Claude Code drops a pattern it cannot compile.

def _sanitize_range(s: str) -> str:
    return re.sub(r"([0-z])-([0-z])",
                  lambda m: m.group(0) if ord(m.group(1)) <= ord(m.group(2)) else "", s)


def _range_class(m) -> str:
    esc, body, slashes, close = m.group(1), m.group(2), m.group(3), m.group(4)
    if esc == "\\":
        return "\\[" + body + slashes[:len(slashes) - len(slashes) % 2] + close
    if close == "]":
        return "[" + _sanitize_range(body) + slashes + "]" if len(slashes) % 2 == 0 else "[]"
    return "[]"


def _make_regex_source(pattern: str) -> str:
    original = pattern
    s = pattern
    s = re.sub(r"^﻿", "", s, count=1)
    s = re.sub(r"((?:\\\\)*?)(\\?\s+)$",
               lambda m: m.group(1) + (" " if m.group(2).startswith("\\") else ""), s, count=1)
    s = re.sub(r"(\\+?)\s",
               lambda m: m.group(1)[:len(m.group(1)) - len(m.group(1)) % 2] + " ", s)
    s = re.sub(r"[\\$.|*+(){^]", lambda m: "\\" + m.group(0), s)
    s = re.sub(r"(?!\\)\?", lambda m: "[^/]", s)
    s = re.sub(r"^/", lambda m: "^", s, count=1)
    s = re.sub(r"/", lambda m: "\\/", s)
    s = re.sub(r"^\^*\\\*\\\*\\/", lambda m: "^(?:.*\\/)?", s, count=1)
    anywhere = not re.search(r"/(?!$)", original)
    s = re.sub(r"^(?=[^^])", lambda m: "(?:^|\\/)" if anywhere else "^", s, count=1)
    cur = s
    s = re.sub(r"\\/\\\*\\\*(?=\\/|$)",
               lambda m: "(?:\\/[^\\/]+)*" if m.start() + 6 < len(cur) else "\\/.+", s)
    s = re.sub(r"(^|[^\\]+)(\\\*)+(?=.+)", lambda m: m.group(1) + "[^\\/]*", s)
    s = re.sub(r"\\\\\\(?=[$.|*+(){^])", lambda m: "\\", s)
    s = re.sub(r"\\\\", lambda m: "\\", s)
    s = re.sub(r"(\\)?\[([^\]/]*?)(\\*)($|\])", _range_class, s)
    s = re.sub(r"(?:[^*])\Z",
               lambda m: m.group(0) + ("$" if m.group(0).endswith("/") else "(?=$|\\/$)"),
               s, count=1)
    s = re.sub(r"(^|\\/)?\\\*\Z",
               lambda m: (m.group(1) + "[^/]+" if m.group(1) else "[^/]*") + "(?=$|\\/$)",
               s, count=1)
    return s


_HEX = "0123456789abcdefABCDEF"


def _js_escape(src: str, i: int, in_class: bool) -> Tuple[str, int]:
    """The Python spelling of the JavaScript escape at src[i] (the backslash), and where it ends.

    JavaScript without the `u` flag reads an escaped letter that names no escape as the letter
    itself; Python reads `\\a` as BEL and `\\A`, `\\Z` as anchors, and rejects most others.
    """
    if i + 1 >= len(src):
        return "\\", i + 1
    c = src[i + 1]
    if c in "dDwWsSnrtfv" or (c in "bB" and not in_class) or (c == "b" and in_class):
        return "\\" + c, i + 2
    if c == "x" and len(src) >= i + 4 and all(h in _HEX for h in src[i + 2:i + 4]):
        return src[i:i + 4], i + 4
    if c == "u" and len(src) >= i + 6 and all(h in _HEX for h in src[i + 2:i + 6]):
        return src[i:i + 6], i + 6
    if c == "c" and i + 2 < len(src) and src[i + 2].isascii() and src[i + 2].isalpha():
        return "\\x%02x" % (ord(src[i + 2]) % 32), i + 3
    if c == "c":
        return "\\\\c", i + 2
    if c in "01234567":
        # No pattern this port builds has a capturing group, so a digit escape is a legacy octal
        # escape in JavaScript: up to three octal digits, at most 0o377.
        j = i + 2
        while j < len(src) and j < i + 4 and src[j] in "01234567" \
                and int(src[i + 1:j + 1], 8) <= 0o377:
            j += 1
        return "\\x%02x" % int(src[i + 1:j], 8), j
    if c.isascii() and c.isalnum():
        return c, i + 2
    return re.escape(c), i + 2


def _js_regex_to_py(src: str) -> str:
    """Rewrite a JavaScript regular expression source, as node-ignore builds it, for Python `re`.

    Character classes are where the two dialects part: in JavaScript `[]` matches nothing and
    `[^]` matches anything, and a `[` inside a class is a plain character. Escapes go through
    _js_escape. Everything else node-ignore emits reads the same in both.
    """
    out: List[str] = []
    i = 0
    while i < len(src):
        ch = src[i]
        if ch == "\\":
            piece, i = _js_escape(src, i, False)
            out.append(piece)
            continue
        if ch != "[":
            out.append(ch)
            i += 1
            continue
        j = i + 1
        negate = j < len(src) and src[j] == "^"
        if negate:
            j += 1
        if j < len(src) and src[j] == "]":
            out.append("[\\s\\S]" if negate else "(?!)")
            i = j + 1
            continue
        cls = ["[^" if negate else "["]
        while j < len(src) and src[j] != "]":
            if src[j] == "\\":
                piece, j = _js_escape(src, j, True)
                cls.append(piece)
            elif src[j] in "[&~|":
                cls.append("\\" + src[j])
                j += 1
            else:
                cls.append(src[j])
                j += 1
        if j >= len(src):
            # An unclosed class is a syntax error in both; leave it for re.compile to refuse.
            out.extend(cls)
            i = j
            continue
        out.extend(cls)
        out.append("]")
        i = j + 1
    return "".join(out)


class _IgnoreRule(NamedTuple):
    negative: bool
    regex: "re.Pattern[str]"


@lru_cache(maxsize=256)
def _compile(globs: Tuple[str, ...]) -> Tuple[_IgnoreRule, ...]:
    rules = []
    for g in globs:
        if not isinstance(g, str) or not g or re.match(r"^\s+$", g) \
                or re.search(r"(?:[^\\]|^)\\$", g) or g.startswith("#"):
            continue
        negative = g.startswith("!")
        body = g[1:] if negative else g
        body = re.sub(r"^\\!", "!", body)
        body = re.sub(r"^\\#", "#", body)
        try:
            source = _js_regex_to_py(_make_regex_source(body))
            with warnings.catch_warnings():
                # `--` or `&&` in a class draws a FutureWarning about set operations Python may
                # add one day; today it reads the class as JavaScript does.
                warnings.simplefilter("ignore", FutureWarning)
                rules.append(_IgnoreRule(negative, re.compile(source, re.I)))
        except re.error:
            continue
    return tuple(rules)


def _test(rules: Sequence[_IgnoreRule], path: str) -> bool:
    ignored = unignored = False
    for rule in rules:
        if (unignored == rule.negative and ignored != unignored) or \
                (rule.negative and not ignored and not unignored):
            continue
        if not rule.regex.search(path):
            continue
        ignored, unignored = not rule.negative, rule.negative
    return ignored


def match(globs: Sequence[str], relpath: str) -> bool:
    """Whether node-ignore, given `globs`, ignores `relpath`: Claude Code's rule-to-file test.

    `globs` are normalized already (see normalize_globs). `relpath` is relative to the directory
    holding `.claude`, with `/` separators. A path starting with `..`, an absolute path, and the
    forms node-ignore refuses (`./x`, `.`, empty) never match.
    """
    if not relpath or relpath.startswith("..") or relpath.startswith("/") \
            or re.match(r"^\.{0,2}/|^\.{1,2}$", relpath):
        return False
    rules = _compile(tuple(globs))
    if not rules:
        return False
    slices = [s for s in relpath.split("/") if s]
    # A pattern that matches a directory matches every file under it, so each ancestor is tried
    # first, as `dir/`, shallowest first; the first ancestor ignored decides.
    for depth in range(1, len(slices)):
        if _test(rules, "/".join(slices[:depth]) + "/"):
            return True
    return _test(rules, relpath)


# --- which rules apply --------------------------------------------------------------------------

def _within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _rule_files(rules_dir: str, project_root: str) -> List[str]:
    """Every `.md` under `rules_dir`, following symlinks as Claude Code's walker does.

    A symlinked subdirectory or file is followed when it resolves inside the project and skipped
    when it resolves outside it, which is Claude Code's rule for project rules. A directory
    reached twice, through a cycle or two links, is walked once.
    """
    real_root = os.path.realpath(project_root)

    def outside(path: str) -> bool:
        return os.path.islink(path) and not _within(os.path.realpath(path), real_root)

    found = []
    seen = {os.path.realpath(rules_dir)}
    for dirpath, dirnames, filenames in os.walk(rules_dir, followlinks=True):
        keep = []
        for d in sorted(dirnames):
            full = os.path.join(dirpath, d)
            real = os.path.realpath(full)
            if real in seen or outside(full):
                continue
            seen.add(real)
            keep.append(d)
        dirnames[:] = keep
        for f in sorted(filenames):
            full = os.path.join(dirpath, f)
            if f.endswith(".md") and not outside(full):
                found.append(full)
    return found


def _nested_worktree(project_root: str) -> Optional[Tuple[str, str]]:
    """(worktree root, main repository root) when the project is a git worktree inside its repo.

    Claude Code creates worktrees under `<repo>/.claude/worktrees/<name>`, and a session there
    does not read project rules from the directories of the main checkout around it.
    """
    d = project_root
    while not os.path.lexists(os.path.join(d, ".git")):
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    dot_git = os.path.join(d, ".git")
    if not os.path.isfile(dot_git):
        return None
    try:
        with open(dot_git, encoding="utf-8") as f:
            m = re.match(r"gitdir:\s*(.+?)\s*$", f.readline())
        if not m:
            return None
        gitdir = os.path.normpath(os.path.join(d, m.group(1)))
        common_file = os.path.join(gitdir, "commondir")
        if os.path.isfile(common_file):
            with open(common_file, encoding="utf-8") as f:
                common = os.path.normpath(os.path.join(gitdir, f.read().strip()))
        else:
            return None
    except OSError:
        return None
    main = os.path.dirname(common)
    if main != d and _within(d, main):
        return d, main
    return None


def applicable_rules(target: str, project_root: str, home: str) -> List[Rule]:
    """Every path-scoped rule whose globs match `target`, deduplicated by content.

    Rules come from `.claude/rules/**/*.md` in the target's directory and in each ancestor up to
    `/`, except `$HOME/.claude/rules`, which is user scope and matched differently, and except
    the main checkout's directories around a worktree nested in it (_nested_worktree). Each
    rule's globs are matched against the target's path relative to the directory holding its
    `.claude`. A target outside `project_root` gets no rules.
    """
    target = os.path.normpath(os.path.abspath(target))
    project_root = os.path.normpath(os.path.abspath(project_root))
    if not _within(target, project_root):
        return []
    user_rules = os.path.normpath(os.path.join(home, ".claude", "rules")) if home else ""
    worktree = _nested_worktree(project_root)
    out: List[Rule] = []
    seen: Set[str] = set()
    d = os.path.dirname(target)
    while True:
        rules_dir = os.path.join(d, ".claude", "rules")
        in_main_only = worktree is not None and _within(d, worktree[1]) \
            and not _within(d, worktree[0])
        if os.path.normpath(rules_dir) != user_rules and not in_main_only \
                and os.path.isdir(rules_dir):
            rel = os.path.relpath(target, d).replace(os.sep, "/")
            for f in _rule_files(rules_dir, project_root):
                try:
                    with open(f, "rb") as fh:
                        data = fh.read()
                except OSError:
                    continue
                globs = parse_paths_frontmatter(data.decode("utf-8", "replace"))
                if globs is None or not match(globs, rel):
                    continue
                sha = hashlib.sha256(data).hexdigest()
                if sha not in seen:
                    seen.add(sha)
                    out.append(Rule(os.path.normpath(f), sha, data))
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return out


# --- the transcript -----------------------------------------------------------------------------

def transcript_for(hook_input: dict) -> Optional[str]:
    """The calling agent's own transcript file, or None when it cannot be found."""
    tp = hook_input.get("transcript_path")
    if not isinstance(tp, str) or not tp:
        return None
    agent = hook_input.get("agent_id")
    if not agent:
        return tp
    base = tp[:-len(".jsonl")] if tp.endswith(".jsonl") else tp
    pattern = os.path.join(glob.escape(base), "subagents", "**",
                           "agent-" + glob.escape(str(agent)) + ".jsonl")
    hits = glob.glob(pattern, recursive=True)
    if not hits:
        return None
    return max(hits, key=lambda p: os.path.getmtime(p))


def _boundary_id(line: bytes) -> Optional[str]:
    """The uuid of a compact_boundary entry, '' when it has none, None for any other line."""
    if b"compact_boundary" not in line:
        return None
    try:
        e = json.loads(line)
    except ValueError:
        return None
    if isinstance(e, dict) and e.get("type") == "system" and e.get("subtype") == "compact_boundary":
        return str(e.get("uuid") or "")
    return None


def window_lines(path: str, chunk: int = CHUNK) -> Tuple[List[bytes], str]:
    """The lines after the last compact_boundary, oldest first, and that boundary's uuid.

    Read backward in chunks so a long transcript costs only its tail. Lines are split on the
    newline byte, which never occurs inside a multi-byte UTF-8 sequence, so a chunk edge cannot
    split a character into a line; decoding happens per line later. The pieces of a line longer
    than a chunk are collected and joined once, when its start is found, so a line of N chunks
    costs N reads rather than N squared copies.
    """
    out: List[bytes] = []
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        pieces: List[bytes] = []  # the line in progress, newest piece first
        while pos > 0:
            n = min(chunk, pos)
            pos -= n
            f.seek(pos)
            parts = f.read(n).split(b"\n")
            if len(parts) == 1:
                pieces.append(parts[0])
                continue
            pieces.append(parts[-1])
            done = [b"".join(reversed(pieces))] + parts[-2:0:-1]
            pieces = [parts[0]]
            for line in done:
                bid = _boundary_id(line)
                if bid is not None:
                    out.reverse()
                    return out, bid
                out.append(line)
        carry = b"".join(reversed(pieces))
        if carry:
            bid = _boundary_id(carry)
            if bid is not None:
                out.reverse()
                return out, bid
            out.append(carry)
    out.reverse()
    return out, ""


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def _read_outcome(entry: dict, text: str) -> str:
    """'full', 'unchanged' or 'other' for a successful Read's tool_result."""
    tur = entry.get("toolUseResult")
    if isinstance(tur, dict):
        kind = tur.get("type")
        if kind == "file_unchanged":
            return "unchanged"
        if kind != "text":
            return "other"
        f = tur.get("file") if isinstance(tur.get("file"), dict) else {}
        if f.get("startLine", 1) != 1:
            return "other"
        if "numLines" in f and "totalLines" in f and f["numLines"] != f["totalLines"]:
            return "other"
        return "full"
    if UNCHANGED_TEXT in text[:200]:
        return "unchanged"
    return "full"


def loaded_rules(transcript_lines: Iterable, current_call: Optional[str] = None,
                 watch: Iterable[str] = ()) -> Loaded:
    """Which files the transcript shows in context, by path, plus the shas the gate inlined.

    Takes the lines of one agent's transcript, oldest first, as str or bytes. A compact_boundary
    among them resets everything before it, so the whole file may be passed. Raises
    TranscriptUnreadable when no line parses as a transcript entry.

    A tool_result counts only once the model has seen it, which is in its next response. So a
    result answering a call of the response that `current_call` (the hook input's tool_use_id)
    belongs to does not count: the call being checked was generated before that result existed.
    See _current_message for how that response is found. The text of each result answering a
    call named in `watch` is kept in Loaded.results, so the caller can tell whether its own
    refusal reached the transcript.
    """
    paths: Set[str] = set()
    loads: List[Tuple[str, Set[str], Optional[str]]] = []  # (tool_use_id, marker shas, read path)
    reads: Dict[str, str] = {}
    msg_of: Dict[str, Optional[str]] = {}
    calls_in: Dict[Optional[str], List[str]] = {}
    last_msg: Optional[str] = None
    results: Dict[str, str] = {}
    answered: Set[str] = set()
    watched = set(watch)
    parsed_any = False
    keys = ('"attachment"', '"tool_use"', '"tool_result"', "compact_boundary")
    nonempty = 0
    for raw in transcript_lines:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        if not line.strip():
            continue
        nonempty += 1
        if parsed_any and not any(k in line for k in keys):
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        parsed_any = parsed_any or "type" in e
        if e.get("type") == "system" and e.get("subtype") == "compact_boundary":
            paths.clear()
            loads.clear()
            reads.clear()
            msg_of.clear()
            calls_in.clear()
            last_msg = None
            results.clear()
            answered.clear()
            continue
        if e.get("isCompactSummary"):
            continue
        att = e.get("attachment")
        if isinstance(att, dict):
            kind = att.get("type")
            if kind == "nested_memory" and isinstance(att.get("path"), str):
                paths.add(os.path.normpath(att["path"]))
            elif kind == "instructions" and isinstance(att.get("files"), list):
                for f in att["files"]:
                    if isinstance(f, dict) and isinstance(f.get("path"), str):
                        paths.add(os.path.normpath(f["path"]))
            elif kind == "file" and isinstance(att.get("filename"), str):
                paths.add(os.path.normpath(att["filename"]))
        msg = e.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        msg_id = msg.get("id") if isinstance(msg.get("id"), str) else None
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                # Claude Code writes each block of one model response as its own entry, all
                # carrying that response's message.id.
                msg_of[block["id"]] = msg_id
                calls_in.setdefault(msg_id, []).append(block["id"])
                last_msg = msg_id
                if block.get("name") == "Read":
                    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                    fp = inp.get("file_path")
                    if isinstance(fp, str) and "offset" not in inp and "limit" not in inp:
                        reads[block["id"]] = os.path.normpath(fp)
            elif block.get("type") == "tool_result":
                tid = str(block.get("tool_use_id"))
                text = _result_text(block.get("content"))
                answered.add(tid)
                if tid in watched:
                    results[tid] = text
                shas = set(m.group(1) for m in MARKER_RE.finditer(text)) \
                    if MARKER_PREFIX in text else set()
                fp = reads.pop(tid, None)
                if fp is not None and (block.get("is_error") or _read_outcome(e, text) != "full"):
                    # A file_unchanged stub is possible only after a full Read since the last
                    # boundary, so it adds nothing a counted load did not; alone it proves nothing.
                    fp = None
                if shas or fp:
                    loads.append((tid, shas, fp))
    if nonempty and not parsed_any:
        raise TranscriptUnreadable(f"none of {nonempty} line(s) after the last boundary parse")
    current = _current_message(current_call, msg_of, calls_in, last_msg, answered)
    unseen = {t for t in answered if current is not None and msg_of.get(t) == current}
    shas_out: Set[str] = set()
    for tid, shas, fp in loads:
        if tid in unseen:
            continue
        shas_out.update(shas)
        if fp:
            paths.add(fp)
    return Loaded(paths, shas_out, results, unseen)


def _current_message(current_call: Optional[str], msg_of: Dict[str, Optional[str]],
                     calls_in: Dict[Optional[str], List[str]], last_msg: Optional[str],
                     answered: Set[str]) -> Optional[str]:
    """The message.id of the model response the call being checked belongs to, or None.

    Its own tool_use entry names it when that entry is on disk; it often is not, because Claude
    Code writes a response's entries when the response ends and a call can run before that. Then
    the newest response with a call still unanswered on disk is the current one, since the model
    cannot start a new response before every call of the last one has a result. Otherwise the
    call is taken to open a new response, which counts everything on disk as seen.
    """
    if current_call and msg_of.get(current_call) is not None:
        return msg_of[current_call]
    if last_msg is not None and any(t not in answered for t in calls_in.get(last_msg, [])):
        return last_msg
    return None


# --- state, log and output ----------------------------------------------------------------------

def _home(env) -> str:
    return env.get("HOME") or os.path.expanduser("~")


def _log_path(env) -> str:
    return env.get("DISCIPLINE_RULE_GATE_LOG") or os.path.join(
        _home(env), ".claude", "discipline", "rule-gate.log")


def _state_dir(env) -> str:
    return env.get("DISCIPLINE_RULE_GATE_STATE") or os.path.join(
        _home(env), ".claude", "discipline", "state")


def log_line(env, kind: str, hook_input: dict, detail: str, now: float) -> None:
    """Append one tab-separated line; a log that cannot be written is not a reason to block."""
    try:
        path = _log_path(env)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tool_input = hook_input.get("tool_input") if isinstance(hook_input, dict) else None
        target = ""
        if isinstance(tool_input, dict):
            target = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        fields = [
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), kind,
            str(hook_input.get("session_id", "")) if isinstance(hook_input, dict) else "",
            str(hook_input.get("agent_id", "") or "main") if isinstance(hook_input, dict) else "",
            str(hook_input.get("tool_name", "")) if isinstance(hook_input, dict) else "",
            target, detail,
        ]
        with open(path, "a", encoding="utf-8") as f:
            f.write("\t".join(x.replace("\t", " ").replace("\n", " ") for x in fields) + "\n")
    except Exception:
        pass


# --- deferring to the project's own copy ---------------------------------------------------------

# Where `install.sh --refresh-rules` vendors the gate inside a repository, and this file's path
# as run and as resolved, which is how a copy tells whether it is that one.
PROJECT_COPY = os.path.join(".claude", "hooks", "rule_gate.py")
SELF = os.path.realpath(__file__)
SELF_AS_RUN = os.path.abspath(__file__)
# The script spellings that reach the project copy from a project hook. The relative ones resolve
# against the hook's working directory, which Claude Code sets to the project directory.
_PROJECT_DIR_SPELLINGS = ("$CLAUDE_PROJECT_DIR/.claude/hooks/rule_gate.py",
                          "${CLAUDE_PROJECT_DIR}/.claude/hooks/rule_gate.py")
_RELATIVE_SPELLINGS = (".claude/hooks/rule_gate.py", "./.claude/hooks/rule_gate.py")
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")


def _matcher_covers(matcher, tool: str) -> bool:
    """Whether a PreToolUse matcher selects `tool`: empty or `*` selects every tool, a plain
    `A|B` list selects those names exactly, and anything else is a regular expression. The
    project-level wiring check in install.sh (RULE_GATE_PROJECT_WIRE) reads matchers the same
    way, and counts an entry as wired only when it selects every tool in WRITE_TOOLS."""
    if matcher is None or matcher in ("", "*"):
        return True
    if not isinstance(matcher, str):
        return False
    if re.fullmatch(r"[A-Za-z0-9_|]+", matcher):
        return tool in matcher.split("|")
    try:
        return re.search(matcher, tool) is not None
    except re.error:
        return False


def runs_project_copy(cmd, root: str, env) -> bool:
    """Whether a hook command runs `root`'s own .claude/hooks/rule_gate.py.

    Only the script position counts: the first word, or the word after a python interpreter.
    It must be one of the spellings above or an absolute path to that same file. A command that
    names the path anywhere else, a sibling such as rule_gate.py.orig, or another checkout's
    copy runs something else or nothing, and deferring to it would leave no copy checking."""
    if not isinstance(cmd, str):
        return False
    try:
        words = shlex.split(cmd)
    except ValueError:
        return False
    if words and re.fullmatch(r"python[0-9.]*", os.path.basename(words[0])):
        words = words[1:]
    if not words:
        return False
    script = words[0]
    if script in _PROJECT_DIR_SPELLINGS:
        return bool(env.get("CLAUDE_PROJECT_DIR"))
    if script in _RELATIVE_SPELLINGS:
        return True
    if os.path.isabs(script):
        try:
            return os.path.samefile(script, os.path.join(root, PROJECT_COPY))
        except OSError:
            return False
    return False


def project_copy_wired(root: str, tool: str, env) -> Optional[str]:
    """The project settings file that runs the project's own copy of this gate for `tool`, or
    None when no such hook would run.

    Two copies wired at once, one from the user's settings and one from the project's, would
    each refuse the same write. So a copy that is not the project's own steps aside when the
    project's `.claude/settings.json` or `.claude/settings.local.json` has a PreToolUse command
    hook whose matcher selects this tool and whose command runs that project's copy (see
    runs_project_copy), and that file exists. A settings file that cannot be read or parsed, or
    an entry of a shape Claude Code would not run, wires nothing, which leaves this copy
    checking: the safe direction is two refusals, never none.
    """
    if not os.path.isfile(os.path.join(root, PROJECT_COPY)):
        return None
    for name in ("settings.json", "settings.local.json"):
        path = os.path.join(root, ".claude", name)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        hooks = data.get("hooks") if isinstance(data, dict) else None
        entries = hooks.get("PreToolUse") if isinstance(hooks, dict) else None
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict) or not _matcher_covers(e.get("matcher"), tool):
                continue
            for h in e.get("hooks") if isinstance(e.get("hooks"), list) else []:
                if (isinstance(h, dict) and h.get("type") == "command"
                        and runs_project_copy(h.get("command"), root, env)):
                    return path
    return None


def is_project_copy(root: str) -> bool:
    """Whether this file is `root`'s own copy, or lies inside the project at all.

    By the path it was run from and by file identity, never by resolved path alone: with
    .claude/hooks a symlink to a directory outside the repository, the project copy resolves
    outside the root, and a copy that took that for "not mine" would defer to itself."""
    if _within(SELF, os.path.realpath(root)) or _within(SELF_AS_RUN, os.path.abspath(root)):
        return True
    mine = os.path.join(root, PROJECT_COPY)
    try:
        return os.path.samefile(SELF_AS_RUN, mine)
    except OSError:
        return False


def _context(text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}


def _deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def fail_open(env, hook_input: dict, why: str, now: float) -> dict:
    log_line(env, "FAIL-OPEN", hook_input if isinstance(hook_input, dict) else {}, why, now)
    return _context(f"rule-gate: could not check which project rules apply to this write, so it "
                    f"was allowed unchecked ({why}). Read any .claude/rules file that applies to "
                    f"the file before writing it.")


def _state_file(env, session: str, agent: str) -> str:
    key = hashlib.sha256((session + "\0" + agent).encode("utf-8")).hexdigest()[:32]
    return os.path.join(_state_dir(env), key + ".json")


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return {"pending": {}, "blind": {}}
    if not isinstance(st, dict):
        return {"pending": {}, "blind": {}}
    st["pending"] = st.get("pending") if isinstance(st.get("pending"), dict) else {}
    st["blind"] = st.get("blind") if isinstance(st.get("blind"), dict) else {}
    return st


def save_state(path: str, state: dict) -> None:
    """Write through a temporary file and rename, so a concurrent reader sees old or new, whole."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    prune_state(d)


def prune_state(state_dir: str) -> None:
    """Remove state files untouched for STATE_TTL_S, by the wall clock their mtimes use."""
    now = time.time()
    try:
        names = os.listdir(state_dir)
    except OSError:
        return
    for n in names:
        p = os.path.join(state_dir, n)
        try:
            if now - os.path.getmtime(p) > STATE_TTL_S:
                os.unlink(p)
        except OSError:
            pass


# --- the decision -------------------------------------------------------------------------------

def _sha_of(path: str) -> Optional[str]:
    try:
        if os.path.getsize(path) > 4 * 1024 * 1024:
            return None
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def _max_inline(env) -> int:
    try:
        return int(env.get("DISCIPLINE_RULE_GATE_MAX_INLINE", DEFAULT_MAX_INLINE))
    except ValueError:
        return DEFAULT_MAX_INLINE


def _inline_reason(tool: str, target: str, new: List[Rule], sibling: List[Rule],
                   unconfirmed: List[Rule], cap: int) -> str:
    total = sum(len(r.data) for r in new)
    head = (f"rule-gate: refused this {tool} of {target}. {len(new)} project rule(s) apply to "
            f"that file and are not in your context.")
    tail = []
    if sibling:
        tail.append("These also apply; their full text was given in a sibling call's refusal "
                    "in this batch: " + ", ".join(r.path for r in sibling))
    if unconfirmed:
        tail.append("These also apply, and the gate cannot confirm they are in your context; "
                    "Read each whole with the Read tool: " + ", ".join(r.path for r in unconfirmed))
    if total > cap:
        listing = "\n".join("  " + r.path for r in new)
        return (f"{head} Together they are {total} bytes, over the {cap}-byte inline cap, so "
                f"they are listed instead. Read each of these files whole with the Read tool "
                f"(no offset, no limit):\n{listing}\n\n" + "\n".join(tail + [
                    "Then apply them and retry the write in your NEXT message, not in this one."]))
    body = [head + " Their full text follows."]
    for r in new:
        body.append(f"{MARKER_PREFIX} sha256={r.sha} path={r.path}\n"
                    + r.data.decode("utf-8", "replace").rstrip("\n"))
    return "\n\n".join(body + tail + [RETRY_LINE])


BLIND_WHY = {
    "blind": "was given and the refusal is in the transcript, but the gate does not count it; "
             "the transcript shape may have changed",
    "blind-late": f"was given {SIBLING_WINDOW_S}s+ ago and the refused call still has no result "
                  f"the gate can find; the transcript shape may have changed",
    "blind-again": f"was refused {REFUSAL_LIMIT} times and the model never saw it given: each "
                   f"refusal's text was missing from the transcript, or the model did not Read "
                   f"the listed file",
}


def _refusal_fate(entry: dict, r: Rule, loaded: Loaded, lines: Sequence[bytes],
                  now: float) -> str:
    """What to do about a rule the gate gave in this window that is still not counted.

    'sibling': the refusal carrying it reached the transcript, but in the response this call
    belongs to, so the model has not seen it yet; refuse briefly, without giving it again.
    'again': the refused call's result is there without the rule. Claude Code keeps one reason
    when several hooks refuse a call, so another hook's refusal can take the place of this
    gate's; or, for a listed rule, the model did not Read it. Give it again.
    'blind': the gate's text is in a result the model has seen and the gate still cannot count
    it, so the transcript has a shape the gate does not read.
    'blind-late': the refused call has had no result for SIBLING_WINDOW_S.
    """
    at = float(entry.get("at", 0) or 0)
    late = "blind-late" if now - at >= SIBLING_WINDOW_S else "sibling"
    call = entry.get("tool_use_id")
    if not isinstance(call, str):
        return late
    text = loaded.results.get(call)
    raw = [ln for ln in lines if call.encode() in ln and b'"tool_result"' in ln]
    if text is None and not raw:
        # Claude Code writes a response's entries when the response ends, so a sibling call can
        # run before the refused call's result is on disk.
        return late
    inlined = entry.get("inlined", True)
    token = f"{MARKER_PREFIX} sha256={r.sha}" if inlined else r.path
    if text is not None and token in text:
        if call in loaded.unseen:
            return "sibling"
        return "blind" if inlined else "again"
    if inlined and any(f"sha256={r.sha}".encode() in ln for ln in raw):
        return "blind"  # the text is on disk where the gate does not read it
    return "again"


def decide(hook_input: dict, env=None, now: Optional[float] = None) -> Optional[dict]:
    """The hook's output for one PreToolUse call, or None to allow silently.

    `env` defaults to os.environ and `now` to the wall clock; tests pass both.
    """
    env = os.environ if env is None else env
    now = time.time() if now is None else now
    if env.get("DISCIPLINE_RULE_GATE", "").strip().lower() == "off":
        return None
    if not isinstance(hook_input, dict):
        return fail_open(env, {}, "the hook input is not a JSON object", now)
    tool = hook_input.get("tool_name")
    if tool not in GATED:
        return None
    tool_input = hook_input.get("tool_input")
    target = tool_input.get(GATED[tool]) if isinstance(tool_input, dict) else None
    if not isinstance(target, str) or not target:
        return fail_open(env, hook_input, f"{tool} input carries no {GATED[tool]}", now)
    cwd = hook_input.get("cwd") if isinstance(hook_input.get("cwd"), str) else os.getcwd()
    target = os.path.normpath(os.path.join(cwd, target))
    root = env.get("CLAUDE_PROJECT_DIR") or cwd

    rules = applicable_rules(target, root, _home(env))
    if not rules:
        return None

    # After the rules, so a write no rule covers logs nothing here either, as the README says.
    if not is_project_copy(root):
        wired_in = project_copy_wired(root, tool, env)
        if wired_in:
            log_line(env, "DEFER", hook_input,
                     f"{os.path.join(root, PROJECT_COPY)} is wired in {wired_in}; this copy "
                     f"did not check the write, which is covered only if this session loads "
                     f"project hooks", now)
            return None

    tpath = transcript_for(hook_input)
    if not tpath or not os.path.isfile(tpath):
        which = f"subagent {hook_input.get('agent_id')}" if hook_input.get("agent_id") else "main"
        return fail_open(env, hook_input, f"no transcript found for the {which} thread", now)

    session = str(hook_input.get("session_id") or "")
    agent = str(hook_input.get("agent_id") or "main")
    spath = _state_file(env, session, agent)
    state = load_state(spath) if os.path.exists(spath) else {"pending": {}, "blind": {}}
    pending, blind = state["pending"], state["blind"]
    call = hook_input.get("tool_use_id") if isinstance(hook_input.get("tool_use_id"), str) \
        else None
    watch = [e["tool_use_id"] for e in pending.values()
             if isinstance(e, dict) and isinstance(e.get("tool_use_id"), str)]
    try:
        lines, window = window_lines(tpath)
        loaded = loaded_rules(lines, call, watch)
    except (OSError, TranscriptUnreadable) as e:
        return fail_open(env, hook_input, f"transcript unreadable: {e}", now)

    def counted(r: Rule, shas: Set[str]) -> bool:
        return r.path in loaded.paths or r.sha in shas

    shas = set(loaded.shas)
    if any(not counted(r, shas) for r in rules):
        for p in loaded.paths:
            if p.endswith(".md"):
                s = _sha_of(p)
                if s:
                    shas.add(s)
    missing = [r for r in rules if not counted(r, shas)]

    changed = False
    for r in rules:
        if counted(r, shas) and r.sha in pending:
            del pending[r.sha]
            changed = True

    cap = _max_inline(env)
    new: List[Rule] = []
    sibling: List[Rule] = []
    gone_blind: List[Tuple[Rule, str]] = []
    still_blind: List[Rule] = []
    misses: Dict[str, int] = {}
    for r in missing:
        if r.sha in blind:
            still_blind.append(r)
            continue
        entry = pending.get(r.sha)
        fate = "new"
        if isinstance(entry, dict) and entry.get("window") == window:
            fate = _refusal_fate(entry, r, loaded, lines, now)
            if fate == "again":
                misses[r.sha] = int(entry.get("misses", 0) or 0) + 1
                if misses[r.sha] >= REFUSAL_LIMIT:
                    fate = "blind-again"
        if fate == "sibling":
            sibling.append(r)
            continue
        if fate.startswith("blind"):
            gone_blind.append((r, fate))
            del pending[r.sha]
            blind[r.sha] = r.path
            changed = True
            continue
        new.append(r)
    inlined = sum(len(r.data) for r in new) <= cap
    for r in new:
        pending[r.sha] = {"at": now, "window": window, "path": r.path, "tool_use_id": call,
                          "inlined": inlined, "misses": misses.get(r.sha, 0)}
        changed = True

    if changed:
        save_state(spath, state)

    for r, fate in gone_blind:
        log_line(env, "BLIND", hook_input, f"{r.path} {BLIND_WHY[fate]}", now)

    unconfirmed = [r for r, _ in gone_blind] + still_blind
    if new:
        log_line(env, "DENY", hook_input, " ".join(r.path for r in new), now)
        return _deny(_inline_reason(tool, target, new, sibling, unconfirmed, cap))
    if sibling:
        log_line(env, "DENY-SIBLING", hook_input, " ".join(r.path for r in sibling), now)
        return _deny(f"rule-gate: refused this {tool} of {target}. These project rules apply to "
                     f"it, and their full text was given in a sibling call's refusal in this "
                     f"batch: " + ", ".join(r.path for r in sibling) +
                     ". Apply them and retry the write in your NEXT message, not in this one.")
    if unconfirmed:
        return _context(
            "rule-gate: allowed without confirming these rules are in your context; the gate "
            "could not see them loaded after giving them. Read each whole with the Read tool "
            f"before writing {target}: " + ", ".join(r.path for r in unconfirmed))
    return None


def main() -> int:
    env = os.environ
    now = time.time()
    hook_input: dict = {}
    try:
        raw = sys.stdin.read()
        try:
            hook_input = json.loads(raw)
        except ValueError:
            out: Optional[dict] = fail_open(env, {}, "the hook input is not JSON", now)
        else:
            out = decide(hook_input, env, now)
    except Exception as e:
        out = fail_open(env, hook_input if isinstance(hook_input, dict) else {},
                        f"internal error: {type(e).__name__}: {e}", now)
    if out is not None:
        try:
            sys.stdout.write(json.dumps(out))
            sys.stdout.flush()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    try:
        main()
    finally:
        # Exit 2 blocks the call. Whatever happened above, this process exits 0.
        os._exit(0)

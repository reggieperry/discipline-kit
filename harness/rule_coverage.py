#!/usr/bin/env python3
"""rule_coverage — a rule that cannot fire is indistinguishable from one that works.

A path-scoped rule loads into context when Claude reads a file matching its `paths:` globs with
the Read tool, or when such a file is @-mentioned. Write, Edit and Bash do not load it; the kit's
rule gate, where installed, refuses a Write or Edit until the matching rules are in context. Either
way the globs decide which files a rule reaches. So a rule whose globs never match a file a
consumer works on has never loaded, and nothing says so: a silent rule and a satisfied rule
produce identical output, which is no output.

The globs are read and matched by the rule gate's own code (`reference/rule_gate.py`), which is
pinned to Claude Code's matcher by golden vectors. A check that matched with different semantics
would report coverage Claude Code does not give.

WHAT THIS CHECKS.

  1. Structure. Every rule parses, carries `paths:` frontmatter, and declares at least one glob.
     A rule with no frontmatter can never fire anywhere.

  2. Testing coverage, per language, DERIVED rather than listed. The kit declares which languages
     it supports by shipping `<lang>-testing.md`. For each such overlay, a probe path is
     synthesized FROM THAT OVERLAY'S OWN GLOBS, and the check asks whether any language-neutral
     `craft-*` testing rule fires on it. A language whose test files reach an overlay but no craft
     testing discipline is a gap, and the gap is invisible without this.

  3. Source coverage, per language. Every `craft-*` rule that reaches source code in any declared
     language must reach it in all of them. A language's source probes come from its own
     `<lang>-*.md` rules other than the testing overlay. A craft rule that reaches no language's
     source (craft-xunit, which is scoped to test files) is left to check 2.

  4. The kit's own templates. The ADR and story templates each name the path their copies are
     written to (`docs/adrs/ADR-NNNN-<slug>.md`, `stories/<ID>-<slug>.md`). Each such path, with
     its placeholders filled in, must reach every craft design rule: a `craft-*` rule declaring a
     Markdown glob. The craft design rules once matched `**/adr/*.md` and no `adrs/` or `stories/`
     directory, so an ADR or story written from the kit's own templates loaded one only when its
     file name happened to match a name glob such as `**/*design*.md`.

     Derived, never listed, for the reason the kit's own measurement rules give: a scope written
     as a literal goes stale the moment the set changes, and then reports coverage it no longer has.

WHAT THIS DOES NOT CHECK, and cannot.

  Whether a rule's globs match anything in a CONSUMER repository. The kit is a pack of rules, not
  a codebase: it holds almost no Go, Scala or TypeScript, so "matches a tracked file here" would
  flag nearly every language rule and mean nothing. That question is real but belongs downstream,
  against the consumer's own tree, and this check makes no claim about it.

  Whether a rule that DOES fire is the right rule, or whether its content suits the files it
  reaches. `craft-xunit` carried Python-test-convention globs while holding language-neutral
  Meszaros vocabulary; no scanner reads a rule and decides that. What a scanner can say is which
  languages it reaches, which is what the table below prints.

MEASURED 2026-09-07, which is why this exists. Two gaps, both invisible until the table was
printed: `craft-xunit` fired for Python and shell and for no other language, so a Go, Scala or
TypeScript author writing a test never met the Test Double taxonomy or Assertion Roulette; and
TypeScript test files fired NO craft testing rule at all, in a kit shipping nine `ts-*` rules.

Usage: rule_coverage.py [RULES_DIR [TEMPLATES_DIR]]. Exit 0 clean, 1 on a finding, 2 when the
check could not run.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RULES = os.path.join(HERE, "claude-project", "rules")
DEFAULT_TEMPLATES = os.path.join(HERE, "harness", "templates")

# The rule gate's frontmatter reader and matcher, loaded by path so this check and the gate read
# a rule's globs the same way and match them with one set of semantics: node-ignore's, as Claude
# Code applies them, pinned by the gate's golden vectors.
_spec = importlib.util.spec_from_file_location(
    "rule_gate", os.path.join(HERE, "reference", "rule_gate.py"))
assert _spec and _spec.loader
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def read_globs(path: str) -> list[str] | None:
    """The rule's normalized globs, [] when `paths:` yields none, None with no `paths:` at all."""
    raw = gate.raw_paths(open(path, encoding="utf-8").read())
    if raw is None:
        return None
    return gate.normalize_globs(gate.split_paths_value(raw)) or []


def probe_for(glob: str) -> str | None:
    """A concrete path that the given glob matches, or None when one cannot be synthesized.

    `**/*_test.go` becomes `probe/x_test.go`. The result is verified against the glob before it is
    returned, so a probe this function gets wrong is dropped rather than silently testing nothing —
    which would be a check reporting coverage from a path no rule could ever match.
    """
    p = glob.replace("**/", "probe/").replace("**", "probe")
    p = re.sub(r"(?<![.\w])\*(?![\w.])", "x", p)
    p = p.replace("*", "x")
    if p.endswith("/"):
        p += "file.txt"
    return p if gate.match([glob], p) else None


def fires(rules: dict[str, list[str]], path: str) -> set[str]:
    return {name for name, globs in rules.items() if gate.match(globs, path)}


# Ordinary words that hold a test shape's letters: "latest" ends in "test", "contests" in "tests",
# and "attest" and "protest" do both. Each is tried with every declared language's source
# extensions. A short literal list, because no glob can derive a word that is not a test name.
ORDINARY_WORDS = ("latest", "contest", "contests", "attest", "protest")

# A path a template names for its copies: directories, then a file name holding a placeholder.
TEMPLATE_PATH = re.compile(r"(?:[\w.-]+/)+[\w<>.-]+\.md")


def template_paths(templates_dir: str) -> list[tuple[str, str]] | None:
    """(template, concrete path) for each path a `*-template.md` says its copies are written to.

    Only a path holding a placeholder (`NNNN` or `<...>`) is taken, so `docs/adrs/README.md`, which
    the ADR template mentions as the registry, is not mistaken for where an ADR goes. Placeholders
    become `0001` and `x`. None when the directory does not exist.
    """
    if not os.path.isdir(templates_dir):
        return None
    out: list[tuple[str, str]] = []
    for name in sorted(os.listdir(templates_dir)):
        if not name.endswith("-template.md"):
            continue
        text = open(os.path.join(templates_dir, name), encoding="utf-8").read()
        for m in TEMPLATE_PATH.finditer(text):
            raw = m.group(0)
            if "<" not in raw and "NNNN" not in raw:
                continue
            concrete = re.sub(r"<[^<>]*>", "x", raw.replace("NNNN", "0001"))
            if (name, concrete) not in out:
                out.append((name, concrete))
    return out


def main(argv: list[str]) -> int:
    rules_dir = argv[1] if len(argv) > 1 else DEFAULT_RULES
    templates_dir = argv[2] if len(argv) > 2 else DEFAULT_TEMPLATES
    if not os.path.isdir(rules_dir):
        print(f"rule-coverage: {rules_dir} does not exist — nothing examined", file=sys.stderr)
        return 2

    names = sorted(f for f in os.listdir(rules_dir) if f.endswith(".md"))
    if not names:
        print(f"rule-coverage: {rules_dir} holds no rules — nothing examined", file=sys.stderr)
        return 2

    rules: dict[str, list[str]] = {}
    structural: list[str] = []
    for n in names:
        g = read_globs(os.path.join(rules_dir, n))
        if g is None:
            structural.append(f"{n}: no paths: frontmatter, so it can never fire")
        elif not g:
            structural.append(f"{n}: paths: frontmatter declares no glob")
        else:
            rules[n] = g

    overlays = sorted(n for n in rules if n.endswith("-testing.md") and not n.startswith("craft-"))
    craft = sorted(n for n in rules if n.startswith("craft-"))
    craft_testing = {n for n in craft if "tdd" in n or "xunit" in n}

    print("== rule coverage ==")
    print(f"  {len(names)} rule(s) · {len(overlays)} language(s) declared by a testing overlay")

    gaps: list[str] = []
    if not craft_testing:
        print("  no craft-* testing rule ships — per-language coverage not asked", file=sys.stderr)
    for overlay in overlays:
        lang = overlay[: -len("-testing.md")]
        probes = [p for p in (probe_for(g) for g in rules[overlay]) if p]
        if not probes:
            gaps.append(f"{lang}: no probe path could be synthesized from {overlay}'s globs")
            continue
        reached: set[str] = set()
        for p in probes:
            reached |= fires(rules, p) & craft_testing
        shown = ", ".join(sorted(r[:-3] for r in reached)) if reached else "NONE"
        print(f"    {lang:<12} test files reach: {shown}")
        if not reached:
            gaps.append(
                f"{lang}: test files reach no craft-* testing rule "
                f"(probed {probes[0]!r} and {len(probes) - 1} more)"
            )

    # Source probes per language: every glob of the language's own rules except its testing overlay.
    source: dict[str, list[str]] = {}
    for overlay in overlays:
        lang = overlay[: -len("-testing.md")]
        globs = [g for n in rules if n.startswith(lang + "-") and n != overlay for g in rules[n]]
        probes = sorted({p for p in (probe_for(g) for g in globs) if p})
        if probes:
            source[lang] = probes
    reach_gaps: list[str] = []
    reaches_source: set[str] = set()
    for c in craft:
        reached_langs = {
            lang for lang, ps in source.items() if any(gate.match(rules[c], p) for p in ps)
        }
        if not reached_langs:
            continue
        reaches_source.add(c)
        print(f"    {c[:-3]:<22} reaches source in: {', '.join(sorted(reached_langs))}")
        for lang in sorted(set(source) - reached_langs):
            reach_gaps.append(
                f"{c}: reaches no {lang} source file "
                f"(probed {source[lang][0]!r} and {len(source[lang]) - 1} more)"
            )

    # A craft testing rule that reaches no source is scoped to test files. It must not reach an
    # ordinary file whose name merely contains a test shape's letters, which case-insensitive
    # matching makes easy: `**/*Test.*` reached src/latest.py. A name the language's own testing
    # overlay calls a test file (Latest.java, for a `**/*Test.java` overlay) is not ordinary.
    overmatch: list[str] = []
    for c in sorted(craft_testing - reaches_source):
        probed = 0
        for overlay in overlays:
            lang = overlay[: -len("-testing.md")]
            exts = sorted({os.path.splitext(p)[1] for p in source.get(lang, [])} - {""})
            for word in ORDINARY_WORDS:
                for ext in exts:
                    p = f"src/{word}{ext}"
                    if gate.match(rules[overlay], p):
                        continue
                    probed += 1
                    if gate.match(rules[c], p):
                        overmatch.append(f"{c}: reaches {p}, which {overlay} does not call a test")
        print(f"    {c[:-3]:<22} test files only; {probed} ordinary source name(s) probed")

    design = [c for c in craft if any(g.lower().endswith(".md") for g in rules[c])]
    template_gaps: list[str] = []
    could_not_run: list[str] = []
    if design:
        written = template_paths(templates_dir)
        if written is None:
            could_not_run.append(f"{templates_dir} does not exist, so no template path was probed")
        elif not written:
            could_not_run.append(
                f"no *-template.md under {templates_dir} names a path for its copies")
        for template, path in written or []:
            reached = fires(rules, path) & set(design)
            shown = ", ".join(sorted(r[:-3] for r in reached)) if reached else "NONE"
            print(f"    {path} ({template}) reaches: {shown}")
            for d in design:
                if d not in reached:
                    template_gaps.append(f"{d}: does not reach {path}, where {template} is copied")

    rc = 0
    if structural:
        print("  DEFECT: rule(s) that can never fire:", file=sys.stderr)
        for s in structural:
            print(f"    {s}", file=sys.stderr)
        rc = 1
    if gaps:
        print("  DEFECT: a language the kit ships a testing overlay for, whose test files", file=sys.stderr)
        print("  reach no language-neutral testing rule:", file=sys.stderr)
        for g in gaps:
            print(f"    {g}", file=sys.stderr)
        rc = 1
    if reach_gaps:
        print("  DEFECT: a craft rule that reaches source in some declared language but not all:",
              file=sys.stderr)
        for g in reach_gaps:
            print(f"    {g}", file=sys.stderr)
        rc = 1
    if overmatch:
        print("  DEFECT: a test-scoped craft rule that reaches an ordinary source file:",
              file=sys.stderr)
        for g in overmatch:
            print(f"    {g}", file=sys.stderr)
        rc = 1
    if template_gaps:
        print("  DEFECT: a path the kit's own templates write to that a craft design rule misses:",
              file=sys.stderr)
        for g in template_gaps:
            print(f"    {g}", file=sys.stderr)
        rc = 1
    if could_not_run:
        print("  COULD NOT RUN: the template check examined nothing:", file=sys.stderr)
        for g in could_not_run:
            print(f"    {g}", file=sys.stderr)
        return 2
    if rc == 0:
        print("  every rule can fire, and every declared language reaches a craft testing rule")
        print("  every craft source rule reaches every language, and every template path reaches"
              f" every craft design rule ({len(design)})")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))

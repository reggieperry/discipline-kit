#!/usr/bin/env python3
"""rule_coverage — a rule that cannot fire is indistinguishable from one that works.

A rule injects when a file matching its `paths:` glob is edited. So a rule whose globs never
match anything a consumer edits has never fired, and nothing says so: a silent rule and a
satisfied rule produce identical output, which is no output.

WHAT THIS CHECKS.

  1. Structure. Every rule parses, carries `paths:` frontmatter, and declares at least one glob.
     A rule with no frontmatter can never fire anywhere.

  2. Testing coverage, per language, DERIVED rather than listed. The kit declares which languages
     it supports by shipping `<lang>-testing.md`. For each such overlay, a probe path is
     synthesized FROM THAT OVERLAY'S OWN GLOBS, and the check asks whether any language-neutral
     `craft-*` testing rule fires on it. A language whose test files reach an overlay but no craft
     testing discipline is a gap, and the gap is invisible without this.

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

Exit 0 clean, 1 on a finding, 2 when the check could not run.
"""
from __future__ import annotations

import fnmatch
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RULES = os.path.join(HERE, "claude-project", "rules")


def read_globs(path: str) -> list[str] | None:
    """The rule's declared globs, or None when it carries no frontmatter at all."""
    m = re.match(r"---\n(.*?)\n---\n", open(path, encoding="utf-8").read(4096), re.S)
    if not m:
        return None
    return re.findall(r'-\s*"([^"]+)"', m.group(1))


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
    return p if fnmatch.fnmatch(p, glob) else None


def fires(rules: dict[str, list[str]], path: str) -> set[str]:
    out = set()
    for name, globs in rules.items():
        for g in globs:
            # A `**/` prefix means "at any depth INCLUDING none", which fnmatch does not model.
            if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.replace("**/", "", 1)):
                out.add(name)
                break
    return out


def main(argv: list[str]) -> int:
    rules_dir = argv[1] if len(argv) > 1 else DEFAULT_RULES
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
    craft_testing = {n for n in rules if n.startswith("craft-") and ("tdd" in n or "xunit" in n)}

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
    if rc == 0:
        print("  every rule can fire, and every declared language reaches a craft testing rule")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))

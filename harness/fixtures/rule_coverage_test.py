#!/usr/bin/env python3
"""Red-first fixture for `harness/rule_coverage.py`.

An instrument that has never been observed failing is not known to be watching. Each case builds a
throwaway rules directory and asserts the checker's exit code:

  covered         a declared language's test files reach a craft testing rule      -> 0
  uncovered       an overlay ships, but no craft testing rule reaches it           -> 1
  no-frontmatter  a rule carries no paths: block, so it can never fire             -> 1
  no-globs        a rule declares paths: with nothing under it                     -> 1
  source-covered  a craft rule reaches source in every declared language           -> 0
  source-gap      a craft rule reaches one language's source and misses another's  -> 1
  design-adrs     a craft design rule reaches the kit's ADR and story paths        -> 0
  design-adr-only a craft design rule with the old `**/adr/*.md` globs, run
                  against the kit's real templates                                 -> 1
  template-own    a planted template's path, which the design rule reaches         -> 0
  template-blind  a planted template's path, which the design rule misses          -> 1
  test-only-clean a test-scoped craft rule reaches test files and nothing else      -> 0
  test-only-overmatch
                  a test-scoped craft rule whose `**/*Test.*` reaches latest.zz     -> 1
  no-templates    a design rule ships but the templates directory does not exist   -> 2 (never a pass)
  no-template-path a template names no path for its copies                         -> 2 (never a pass)
  empty           the directory exists but holds no rules                          -> 2 (never a pass)
  missing         the directory does not exist                                     -> 2 (never a pass)

THE FIXTURES ENCODE THE FAILING CONDITION, never a copy of the shipped rules. A fixture that
snapshots live data goes stale and then fires for a reason unrelated to what it tests; these cannot,
because a language with no craft testing rule is DEFINED by having none.

Each case also asserts the string the checker prints, not merely its exit code. A control that
demands only a non-zero exit is satisfied by every way the checker can break, including the ways
that mean it never ran.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HARNESS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKER = os.path.join(HARNESS, "rule_coverage.py")

OVERLAY = '---\npaths:\n  - "**/*_test.zz"\n---\n\n# The zz testing overlay\n'
CRAFT_TDD = '---\npaths:\n  - "**/*_test.zz"\n---\n\n# craft-tdd\n'
CRAFT_TDD_BLIND = '---\npaths:\n  - "**/*.other"\n---\n\n# craft-tdd\n'
NO_FRONTMATTER = "# A rule with no paths: block\n\nNothing says when to inject this.\n"
NO_GLOBS = "---\npaths:\n---\n\n# A rule declaring no glob\n"


def rule(*globs: str) -> str:
    return "---\npaths:\n" + "".join(f'  - "{g}"\n' for g in globs) + "---\n\n# a rule\n"


# Two declared languages, each with a source rule beside its testing overlay.
TWO_LANGS = {
    "zz-testing.md": OVERLAY,
    "zz-style.md": rule("**/*.zz"),
    "yy-testing.md": rule("**/*_test.yy"),
    "yy-style.md": rule("**/*.yy"),
    "craft-tdd.md": rule("**/*_test.zz", "**/*_test.yy"),
}
# The design globs the craft rules shipped before the kit's own template paths were checked.
ADR_ONLY = ("**/adr/*.md", "**/*design*.md", "**/*PLAN*.md", "**/*plan*.md", "**/*stories*.md")


def run(rules_dir: str, templates_dir: str | None = None) -> tuple[int, str]:
    args = [sys.executable, CHECKER, rules_dir] + ([templates_dir] if templates_dir else [])
    p = subprocess.run(args, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def case(
    name: str,
    files: dict[str, str],
    expect_rc: int,
    expect_text: str,
    templates: dict[str, str] | None = None,
) -> bool:
    """`templates` None runs against the kit's own templates; {} names a directory that is absent."""
    with tempfile.TemporaryDirectory() as d:
        rules_dir = os.path.join(d, "rules")
        os.mkdir(rules_dir)
        for fn, body in files.items():
            open(os.path.join(rules_dir, fn), "w", encoding="utf-8").write(body)
        templates_dir = None
        if templates is not None:
            templates_dir = os.path.join(d, "templates")
            if templates:
                os.mkdir(templates_dir)
            for fn, body in templates.items():
                open(os.path.join(templates_dir, fn), "w", encoding="utf-8").write(body)
        rc, out = run(rules_dir, templates_dir)
    ok = rc == expect_rc and expect_text in out
    mark = "ok  " if ok else "FAIL"
    print(f"  {mark} {name:<17} expected rc={expect_rc} + {expect_text!r}, got rc={rc}")
    if not ok:
        print("       " + out.strip().replace("\n", "\n       "))
    return ok


def main() -> int:
    results = [
        case(
            "covered",
            {"zz-testing.md": OVERLAY, "craft-tdd.md": CRAFT_TDD},
            0,
            "every declared language reaches a craft testing rule",
        ),
        case(
            "uncovered",
            {"zz-testing.md": OVERLAY, "craft-tdd.md": CRAFT_TDD_BLIND},
            1,
            "reach no craft-* testing rule",
        ),
        case(
            "no-frontmatter",
            {"zz-testing.md": OVERLAY, "craft-tdd.md": CRAFT_TDD, "broken.md": NO_FRONTMATTER},
            1,
            "no paths: frontmatter",
        ),
        case(
            "no-globs",
            {"zz-testing.md": OVERLAY, "craft-tdd.md": CRAFT_TDD, "bare.md": NO_GLOBS},
            1,
            "declares no glob",
        ),
        case(
            "source-covered",
            {**TWO_LANGS, "craft-refactoring.md": rule("**/*.zz", "**/*.yy")},
            0,
            "every craft source rule reaches every language",
        ),
        case(
            "source-gap",
            {**TWO_LANGS, "craft-refactoring.md": rule("**/*.zz")},
            1,
            "craft-refactoring.md: reaches no yy source file",
        ),
        case(
            "design-adrs",
            {**TWO_LANGS, "craft-abstraction.md": rule(
                "**/*.zz", "**/*.yy", *ADR_ONLY, "**/adrs/*.md", "**/stories/*.md")},
            0,
            "every template path reaches every craft design rule (1)",
        ),
        case(
            "design-adr-only",
            {**TWO_LANGS, "craft-abstraction.md": rule("**/*.zz", "**/*.yy", *ADR_ONLY)},
            1,
            "craft-abstraction.md: does not reach docs/adrs/ADR-0001-x.md",
        ),
        case(
            "template-own",
            {**TWO_LANGS, "craft-abstraction.md": rule("**/*.zz", "**/*.yy", "**/notes/*.md")},
            0,
            "notes/NOTE-0001-x.md (note-template.md) reaches: craft-abstraction",
            templates={"note-template.md": "Copy this file to notes/NOTE-NNNN-<slug>.md.\n"},
        ),
        case(
            "template-blind",
            {**TWO_LANGS, "craft-abstraction.md": rule("**/*.zz", "**/*.yy", "**/adr/*.md")},
            1,
            "does not reach notes/NOTE-0001-x.md, where note-template.md is copied",
            templates={"note-template.md": "Copy this file to notes/NOTE-NNNN-<slug>.md.\n"},
        ),
        case(
            "test-only-clean",
            {**TWO_LANGS, "craft-xunit.md": rule("**/*_test.zz", "**/*_test.yy")},
            0,
            "craft-xunit            test files only; 10 ordinary source name(s) probed",
        ),
        case(
            "test-only-overmatch",
            {**TWO_LANGS, "craft-xunit.md": rule("**/*_test.zz", "**/*Test.*")},
            1,
            "craft-xunit.md: reaches src/latest.zz, which zz-testing.md does not call a test",
        ),
        case(
            "no-templates",
            {**TWO_LANGS, "craft-abstraction.md": rule("**/*.zz", "**/*.yy", "**/adrs/*.md")},
            2,
            "does not exist, so no template path was probed",
            templates={},
        ),
        case(
            "no-template-path",
            {**TWO_LANGS, "craft-abstraction.md": rule("**/*.zz", "**/*.yy", "**/adrs/*.md")},
            2,
            "names a path for its copies",
            templates={"note-template.md": "A template that says nothing about where it goes.\n"},
        ),
        case("empty", {}, 2, "holds no rules"),
    ]

    rc, out = run(os.path.join(tempfile.gettempdir(), "rule-coverage-absent-dir"))
    ok = rc == 2 and "does not exist" in out
    print(f"  {'ok  ' if ok else 'FAIL'} {'missing':<17} expected rc=2 + 'does not exist', got rc={rc}")
    results.append(ok)

    passed = sum(1 for r in results if r)
    print(f"rule-coverage fixture: {passed} of {len(results)} case(s) as specified")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

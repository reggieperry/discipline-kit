#!/usr/bin/env python3
"""chain-graph — the story graph's six commit-path integrity checks (walkthrough A5).

Stories under `stories/` declare their own edges in frontmatter; the graph is derived from
those files and never declared centrally (design §3.10). This reads every story and every
registered ADR and answers six questions, each printing its denominator, because "found
nothing" and "looked at nothing" are the same green otherwise:

  1 parse             unknown key, duplicate key, duplicate id across files. All fatal:
                      a graph read from files the parser could not agree with itself about
                      is not a graph, so checks 2 to 6 are not evaluated when one fires.
  2 dangling deps     a `deps:` id no story file declares
  3 cycles            the Kahn residual, over the edges that resolve
  4 adr references    `adr:` naming no registered ADR, `decisions:` naming no such D
  5 orphan ratio      how many stories claim the ADR-0000 escape hatch, printed EVERY run
  6 reverse coverage  every non-superseded Decision cited by a story or waived in the ADR

THE SCOPE IS EVERY STORY AND EVERY ADR, not the agreed set: a cycle inside an unagreed ADR
is still a cycle.

EXIT CODES, AND THE ONE PLACE THIS DEPARTS FROM THE WALKTHROUGH. The contract is the kit's
canonical three: 0 clean, 1 findings, 2 could-not-run, with 2 never readable as a pass. A5
asks for dangling ids to carry "its own exit code, separate from cycles", because the two
produce the same Kahn residual and send the operator to different remedies. A fourth exit
code cannot be spent here: ADR-0003/D2 closes the vocabulary a sequencer may consume at
0/1/2 and reads ANY other code as could-not-run, so an exit 3 would report a real graph
defect as a broken instrument. The requirement is met inside exit 1 instead, as named finding
CLASSES: `DANGLING-DEP` and `CYCLE ` print under separate headings with separate remedies,
the summary line carries a per-class count (`dangling=2 cycle=0`), and a dangling edge is
dropped from the graph before Kahn runs so one defect cannot be reported as the other. What
the operator reads to choose a remedy is the class, not the code.

COULD-NOT-RUN IS EVERY EMPTY DENOMINATOR, and that is the honest reading rather than a
lenient one. A run with no stories and no registered ADRs has nothing to check, and reporting
that as a clean pass makes a wrong root, an unmounted checkout and a genuinely empty chain
indistinguishable at the exit code the caller branches on. The same argument covers the
halves: stories with no registered ADR cannot be coverage-checked, and ADRs with no stories
cannot be either. So each of the two inputs must be non-empty or the run is VOID, exit 2,
naming which input was empty.

THE FRONTMATTER SUBSET, and everything outside it is a parse error rather than a guess.
PyYAML is not a dependency of this kit, and a permissive hand-rolled parser is worse than a
strict one: a key it silently mis-reads produces a wrong readiness answer, which is exactly
what §3.10's admission rule forbids. Supported:

  - the file opens with a line that is exactly `---`, and the block ends at the next such line
  - `key: value` at column 0, where value is a plain scalar, a fully quoted scalar,
    a flow sequence `[a, b]`, or empty
  - a block sequence: an empty value followed by indented `  - item` lines
  - a comment: `#` at the start of a line, or a `#` preceded by whitespace outside a quoted
    scalar (a quote opens a span only at the start of the content or after whitespace, so an
    apostrophe inside a word is literal)

  Rejected, each naming its line: a tab, a nested mapping, a block scalar (`|`, `>`), an
  anchor, alias or tag (`&`, `*`, `!`), a nested flow collection, an unclosed flow sequence,
  a sequence item belonging to no key, a line with no colon, a list where a scalar belongs
  or a scalar where a list belongs, and a missing `id:` or `title:`.

THE KEY LIST IS CLOSED (§3.10: an unknown key is a typo that silently does nothing, so it is
fatal). `id`, `title`, `deps`, `labels`, `sensitive_files` and `status` are the kit's plain
story fields; `adr`, `decisions`, `group`, `milestone` and `cites` are the chain fields, all
five optional, and a story carrying none of them is a plain kit story that this checker still
counts. `acceptance:` is deliberately NOT a key: the walkthrough's A4 sketch shows one in
frontmatter, and the kit's template keeps acceptance criteria in the body as checkboxes,
which is the form the anti-weakening contract is written in. The template is the schema's
human-facing statement and this list its machine-facing one; `chain_graph_test.py` parses the
shipped template through this parser so the two cannot drift apart unobserved.

ADR-0000 IS THE RESERVED ESCAPE HATCH. It resolves to no file by design, so a story naming it
is exempt from check 4 and counted by check 5 instead. It cannot carry `decisions:`, because
there is no document for a decision reference to resolve against; that is `ORPHAN-REF`.

THE WAIVER FORM. A Decision with no story carries, in its own body, a line
`Covered-by: none` followed by a reason after an em dash, a colon, a hyphen or a space. The
walkthrough writes the spaced-em-dash form; the kit's own em-dash rule forbids spaced dashes
in the unexempted markdown an ADR is, so both are accepted and the reason is what is
required. `Covered-by: none` with nothing after it is not a waiver, and reads as uncovered.

WHAT THIS DELIBERATELY DOES NOT DO. It does not read git: A5's checks are over trunk blobs
and the caller supplies the tree. It does not resolve `cites:` targets, derive completeness
modes, read `.chain/set`, or check that `id:` matches its filename. It does not descend into
`stories/_archive/`, whose closing records carry keys (`merged_sha`, `deviations`, `lessons`)
this schema does not define, with the consequence stated plainly: a `deps:` edge onto an
archived story reads as dangling.

Usage:
    python3 harness/chain_graph.py [--root DIR]

With no argument the root is the directory above this script, which is the kit layout
(`<root>/harness/chain_graph.py`); `--root` points it at any other tree.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

BASE_KEYS = frozenset({"id", "title", "deps", "labels", "sensitive_files", "status"})
CHAIN_KEYS = frozenset({"adr", "decisions", "group", "milestone", "cites"})
KNOWN_KEYS = BASE_KEYS | CHAIN_KEYS
REQUIRED_KEYS = ("id", "title")
LIST_KEYS = frozenset({"deps", "labels", "sensitive_files", "decisions", "cites"})
ORPHAN_ADR = "ADR-0000"

DECISION_HEADING = re.compile(r"(?m)^###\s+(D\d+)\s*:")
NEXT_HEADING = re.compile(r"(?m)^#{1,3}\s+")
REGISTRY_HEADING = re.compile(r"(?m)^## The registry\s*$")
REGISTRY_ROW = re.compile(r"\[(ADR-\d{4})\]\(([^)]+)\)")
SUPERSEDED = re.compile(r"supersed(?:ed|es)(?:-in-part)?\s+by\s+\[?ADR-\d{4}", re.I)
WAIVER = re.compile(r"(?m)^\s*>?\s*Covered-by:\s*none\b(.*)$")
WAIVER_REASON = re.compile(r"^\s*(?:[—:-]\s*|\s+)(\S.*)$")


def strip_comment(line: str) -> str:
    """Drop a trailing `#` comment, respecting a quoted scalar.

    A quote opens a span only at the start of the content or after whitespace, so the
    apostrophe in a word stays literal and does not swallow the rest of the line.
    """
    out: list[str] = []
    quote = ""
    prev = ""
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'" and (prev == "" or prev.isspace()):
            quote = ch
            out.append(ch)
        elif ch == "#" and (prev == "" or prev.isspace()):
            break
        else:
            out.append(ch)
        prev = ch
    return "".join(out).rstrip()


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_flow(value: str, where: str, errors: list[str]) -> list[str] | None:
    if not value.endswith("]"):
        errors.append(f"{where}: flow sequence is not closed by ']'")
        return None
    inner = value[1:-1].strip()
    if not inner:
        return []
    items = []
    for raw in inner.split(","):
        item = unquote(raw.strip())
        if not item:
            errors.append(f"{where}: empty item in the flow sequence")
            return None
        if any(c in item for c in "[]{}"):
            errors.append(f"{where}: nested collections are not in the subset: {item!r}")
            return None
        items.append(item)
    return items


def parse_frontmatter(text: str) -> tuple[dict[str, object], list[str]]:
    """The strict subset parser. Returns (fields, errors); any error means do not trust fields."""
    errors: list[str] = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, ["no frontmatter: the file must open with a line that is exactly '---'"]
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, ["the frontmatter block is never closed by a line that is exactly '---'"]

    fields: dict[str, object] = {}
    open_list: str | None = None
    for number, raw in enumerate(lines[1:end], start=2):
        where = f"line {number}"
        if "\t" in raw:
            errors.append(f"{where}: a tab; the subset is space-indented")
            continue
        line = strip_comment(raw)
        if not line.strip():
            open_list = None
            continue
        if line.lstrip().startswith("- "):
            if open_list is None or not line.startswith(" "):
                errors.append(f"{where}: a sequence item that belongs to no key")
                continue
            item = unquote(line.lstrip()[2:].strip())
            if not item:
                errors.append(f"{where}: an empty sequence item")
                continue
            fields[open_list].append(item)  # type: ignore[union-attr]
            continue
        if line.startswith(" "):
            errors.append(f"{where}: a nested mapping is not in the subset: {line.strip()[:40]!r}")
            open_list = None
            continue
        key, sep, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not sep or not key:
            errors.append(f"{where}: not a 'key: value' line: {line.strip()[:40]!r}")
            continue
        if key in fields:
            errors.append(f"DUPLICATE-KEY {where}: '{key}' is set twice")
            continue
        if value[:1] in ("|", ">", "&", "*", "!"):
            errors.append(f"{where}: '{value[:1]}' constructs are not in the subset")
            continue
        open_list = None
        if value == "":
            fields[key] = []
            open_list = key
        elif value.startswith("["):
            items = parse_flow(value, where, errors)
            if items is None:
                continue
            fields[key] = items
        else:
            fields[key] = unquote(value)
    return fields, errors


@dataclass
class Story:
    rel: str
    ident: str
    deps: list[str]
    adr: str | None
    decisions: list[str]
    cites: list[str] = field(default_factory=list)


@dataclass
class Decision:
    ident: str
    adr: str
    superseded: bool
    waiver: str | None


def read_story(path: Path, rel: str, findings: list[tuple[str, str]]) -> Story | None:
    fields, errors = parse_frontmatter(path.read_text(encoding="utf-8"))
    ok = True
    for message in errors:
        if message.startswith("DUPLICATE-KEY "):
            findings.append(("PARSE-DUPLICATE-KEY", f"{rel}: {message[len('DUPLICATE-KEY '):]}"))
        else:
            findings.append(("PARSE-MALFORMED", f"{rel}: {message}"))
        ok = False
    for key in sorted(set(fields) - KNOWN_KEYS):
        findings.append((
            "PARSE-UNKNOWN-KEY",
            f"{rel}: '{key}' is not a story field; the key list is closed",
        ))
        ok = False
    for key in REQUIRED_KEYS:
        if key not in fields:
            findings.append(("PARSE-MALFORMED", f"{rel}: required key '{key}' is missing"))
            ok = False
    for key, value in sorted(fields.items()):
        if key not in KNOWN_KEYS:
            continue
        wants_list = key in LIST_KEYS
        if wants_list and not isinstance(value, list):
            findings.append(("PARSE-MALFORMED", f"{rel}: '{key}' takes a sequence, not a scalar"))
            ok = False
        if not wants_list and not isinstance(value, str):
            findings.append(("PARSE-MALFORMED", f"{rel}: '{key}' takes a scalar, not a sequence"))
            ok = False
    if not ok:
        return None
    return Story(
        rel=rel,
        ident=str(fields["id"]),
        deps=list(fields.get("deps", [])),  # type: ignore[arg-type]
        adr=str(fields["adr"]) if "adr" in fields else None,
        decisions=list(fields.get("decisions", [])),  # type: ignore[arg-type]
        cites=list(fields.get("cites", [])),  # type: ignore[arg-type]
    )


def parse_decisions(text: str, adr: str) -> list[Decision]:
    out: list[Decision] = []
    for match in DECISION_HEADING.finditer(text):
        following = NEXT_HEADING.search(text, match.end())
        body = text[match.end(): following.start() if following else len(text)]
        waiver = None
        waiver_match = WAIVER.search(body)
        if waiver_match:
            reason = WAIVER_REASON.match(waiver_match.group(1))
            waiver = reason.group(1).strip() if reason else None
        out.append(Decision(match.group(1), adr, bool(SUPERSEDED.search(body)), waiver))
    return out


def kahn_residual(nodes: list[str], edges: dict[str, list[str]]) -> list[str]:
    """The nodes left when no further node has all its dependencies removed."""
    remaining = set(nodes)
    while True:
        ready = {n for n in remaining if not (set(edges.get(n, [])) & remaining)}
        if not ready:
            return sorted(remaining)
        remaining -= ready


def resolve_root(argv: list[str]) -> Path:
    parser = argparse.ArgumentParser(description="the story graph's integrity checks")
    parser.add_argument("--root", default=None, help="the repository root to read")
    args = parser.parse_args(argv)
    if args.root:
        return Path(args.root).resolve()
    return Path(__file__).resolve().parent.parent


def void(reasons: list[str]) -> int:
    print("== chain-graph ==")
    print("  parse             0 story file(s) read")
    print("  dangling deps     0 dep edge(s) over 0 story id(s)")
    print("  cycles            0 node(s)")
    print("  adr references    0 registered ADR(s)")
    print("  ORPHAN-RATIO      0 of 0 story(ies)")
    print("  reverse coverage  0 decision(s) in 0 ADR(s)")
    for reason in reasons:
        print(f"  VOID  {reason}")
    print("chain-graph: VOID, nothing was examined; never a pass")
    return 2


def main(argv: list[str]) -> int:
    root = resolve_root(argv)
    stories_dir = root / "stories"
    adr_dir = root / "docs" / "adrs"

    story_paths = (
        sorted(p for p in stories_dir.glob("*.md") if p.name != "README.md")
        if stories_dir.is_dir()
        else []
    )
    registry: dict[str, str] = {}
    registry_problem: str | None = None
    readme = adr_dir / "README.md"
    if not readme.is_file():
        registry_problem = f"no ADR registry at {readme.relative_to(root) if readme.is_relative_to(root) else readme}"
    else:
        text = readme.read_text(encoding="utf-8")
        heading = REGISTRY_HEADING.search(text)
        if not heading:
            registry_problem = "docs/adrs/README.md carries no '## The registry' heading"
        else:
            registry = dict(REGISTRY_ROW.findall(text[heading.end():]))
            if not registry:
                registry_problem = "docs/adrs/README.md registers no ADR"

    reasons = []
    if not story_paths:
        reasons.append(
            "no story files under stories/ (absent directory or none written); the graph,"
            " the orphan ratio and reverse coverage all have an empty denominator"
        )
    if registry_problem:
        reasons.append(f"{registry_problem}; ADR references and reverse coverage cannot be evaluated")
    if reasons:
        return void(reasons)

    findings: list[tuple[str, str]] = []
    stories: list[Story] = []
    for path in story_paths:
        story = read_story(path, f"stories/{path.name}", findings)
        if story is not None:
            stories.append(story)

    seen: dict[str, str] = {}
    for story in stories:
        if story.ident in seen:
            findings.append((
                "PARSE-DUPLICATE-ID",
                f"id '{story.ident}' is declared by both {seen[story.ident]} and {story.rel}",
            ))
        else:
            seen[story.ident] = story.rel

    print("== chain-graph ==")
    print(f"  parse             {len(story_paths)} story file(s) read, {len(stories)} parsed, "
          f"{len(findings)} finding(s)")
    if findings:
        for marker, message in findings:
            print(f"  {marker}  {message}")
        print("  checks 2 to 6 NOT EVALUATED: the graph is only as real as the files that parsed")
        print(f"chain-graph: FINDINGS parse={len(findings)}")
        return 1

    by_id = {s.ident: s for s in stories}
    edges = {s.ident: s.deps for s in stories}
    dangling = [(s, dep) for s in stories for dep in s.deps if dep not in by_id]
    resolved = {s.ident: [d for d in s.deps if d in by_id] for s in stories}
    residual = kahn_residual(sorted(by_id), resolved)

    print(f"  dangling deps     {sum(len(s.deps) for s in stories)} dep edge(s) over "
          f"{len(by_id)} story id(s), {len(dangling)} finding(s)")
    for story, dep in dangling:
        print(f"  DANGLING-DEP  {story.rel}: deps '{dep}', which no story file declares. "
              f"Remedy: write that story, or correct the id.")
    print(f"  cycles            {len(by_id)} node(s), {sum(len(v) for v in resolved.values())} "
          f"resolved edge(s), {len(residual)} in the residual")
    for ident in residual:
        loop = ", ".join(d for d in resolved[ident] if d in residual)
        print(f"  CYCLE  {ident} is in a dependency cycle, through {loop}. "
              f"Remedy: break the edge; no ordering exists until you do.")

    adr_texts: dict[str, str] = {}
    decisions: list[Decision] = []
    coverage_findings: list[tuple[str, str]] = []
    for adr, target in sorted(registry.items()):
        path = adr_dir / target
        if not path.is_file():
            coverage_findings.append((
                "ZERO-DECISIONS",
                f"{adr} is registered as '{target}', which does not exist, so it yields no "
                f"decisions; a zero-decision parse is indistinguishable from full coverage",
            ))
            continue
        text = path.read_text(encoding="utf-8")
        adr_texts[adr] = text
        parsed = parse_decisions(text, adr)
        if not parsed:
            coverage_findings.append((
                "ZERO-DECISIONS",
                f"{adr} parses to no numbered Decision; a zero-decision parse is "
                f"indistinguishable from full coverage",
            ))
        decisions.extend(parsed)

    known_decisions = {(d.adr, d.ident) for d in decisions}
    ref_findings: list[tuple[str, str]] = []
    orphan_findings: list[tuple[str, str]] = []
    orphans_hatch = [s for s in stories if s.adr == ORPHAN_ADR]
    orphans_absent = [s for s in stories if s.adr is None]
    for story in stories:
        if story.adr == ORPHAN_ADR:
            if story.decisions:
                orphan_findings.append((
                    "ORPHAN-REF",
                    f"{story.rel}: {ORPHAN_ADR} is the escape hatch and is no document, so "
                    f"'decisions: {story.decisions}' resolves against nothing",
                ))
            continue
        if story.adr is None:
            if story.decisions:
                ref_findings.append((
                    "ADR-REF",
                    f"{story.rel}: declares decisions {story.decisions} with no 'adr:' to resolve them against",
                ))
            continue
        if story.adr not in adr_texts:
            ref_findings.append((
                "ADR-REF",
                f"{story.rel}: '{story.adr}' is not a registered, readable ADR",
            ))
            continue
        if not story.decisions:
            ref_findings.append((
                "ADR-REF",
                f"{story.rel}: names {story.adr} but no decisions, so it covers nothing reverse "
                f"coverage can see",
            ))
            continue
        for ident in story.decisions:
            if (story.adr, ident) not in known_decisions:
                ref_findings.append((
                    "ADR-REF",
                    f"{story.rel}: {story.adr} has no decision '{ident}'",
                ))

    print(f"  adr references    {sum(1 for s in stories if s.adr)} story ADR reference(s), "
          f"{sum(len(s.decisions) for s in stories)} decision reference(s), "
          f"{len(registry)} registered ADR(s), {len(ref_findings)} finding(s)")
    for marker, message in ref_findings:
        print(f"  {marker}  {message}")

    orphans = len(orphans_hatch) + len(orphans_absent)
    print(f"  ORPHAN-RATIO      {orphans} of {len(stories)} story(ies) resolve to no ADR "
          f"({ORPHAN_ADR}: {len(orphans_hatch)}, no adr: field: {len(orphans_absent)})")
    for marker, message in orphan_findings:
        print(f"  {marker}  {message}")

    cited = {
        (s.adr, ident) for s in stories if s.adr and s.adr != ORPHAN_ADR for ident in s.decisions
    }
    live = [d for d in decisions if not d.superseded]
    waived = [d for d in live if d.waiver]
    uncovered = [d for d in live if not d.waiver and (d.adr, d.ident) not in cited]
    covered = len(live) - len(waived) - len(uncovered)
    print(f"  reverse coverage  {len(decisions)} decision(s) in {len(adr_texts)} ADR(s): "
          f"cited={covered} waived={len(waived)} superseded={len(decisions) - len(live)} "
          f"uncovered={len(uncovered)}")
    for decision in uncovered:
        coverage_findings.append((
            "UNCOVERED-DECISION",
            f"{decision.adr}/{decision.ident} is cited by no story and carries no "
            f"'Covered-by: none' waiver with a reason",
        ))
    for marker, message in coverage_findings:
        print(f"  {marker}  {message}")
    for decision in waived:
        print(f"  waiver  {decision.adr}/{decision.ident}: {decision.waiver}")

    counts = {
        "parse": 0,
        "dangling": len(dangling),
        "cycle": len(residual),
        "adr-ref": len(ref_findings),
        "orphan-ref": len(orphan_findings),
        "coverage": len(coverage_findings),
    }
    total = sum(counts.values())
    if total:
        summary = " ".join(f"{name}={n}" for name, n in counts.items())
        print(f"chain-graph: FINDINGS {summary}")
        return 1
    print(f"chain-graph: OK ({len(stories)} story(ies), {len(registry)} registered ADR(s), "
          f"{len(live)} live decision(s), 6 checks evaluated)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""ADR-0004/D1's transcript court: no phase transcript carries a spawn event.

The record's falsification condition names this check beside the widened source check: a phase
executed as a subagent, or a spawn event in any phase transcript, falsifies the bare-invocation
substrate. The source check holds the property at the source level — no sequencer code composes
a spawn — and this audit holds it at the evidence level, over what the phases actually emitted.
It runs AFTER a batch, which is the shape ADR-0001/D5 allows: audit, not control flow. No
advancement decision reads its output; a finding here is an operator's to act on, which is why
it can read record fields the sequencer runtime may not.

It lives outside `harness/chain/` deliberately. The D5 source check examines the sequencer
runtime and admits exactly one stream reader there; this file is a court over transcripts, like
the check itself is a court over sources, and putting it inside the runtime directory would
make the court its own subject.

WHAT IT FLAGS: any record whose `subtype` begins `task_` — the D7 probe measured the spawn
events at 2.1.224 as `{"type": "system", "subtype": "task_started", ...}` with
`task_notification` following (`docs/probe/probe-stream.jsonl`, lines 45 and 61; the parser was
grounded in those retained records before it was written). The prefix is deliberately wider
than `task_started` alone: a truncated transcript can carry a notification without its start,
and any task event in a phase transcript means a task ran.

THE DENOMINATORS PRINT ON EVERY RUN, for the reason the whole kit exists: a clean report over
an empty corpus and a clean report over a real one look identical from outside. No transcripts
at all reads could-not-run rather than clean — a batch that ran phases wrote streams, so an
empty corpus means this audit was pointed at the wrong place, not that nothing spawned.

    exit 0   clean, with the denominators printed
    exit 1   at least one spawn event, each named with file, line and subtype
    exit 2   NOTHING WAS EXAMINED: no directory, or no transcript in it. Never a pass.

Usage: python3 harness/transcript_audit.py --dir <transcripts>

`--dir` is the directory a batch's phase streams landed in; every `*.jsonl` under it is read.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

CLEAN = 0
FINDING = 1
COULD_NOT_RUN = 2

SPAWN_PREFIX = "task_"


class CouldNotRun(Exception):
    """Nothing was examined, and the reason is named. Never a pass."""


@dataclass(frozen=True)
class Scan:
    path: Path
    records: int
    unreadable: int
    findings: tuple[str, ...]


def scan(path: Path) -> Scan:
    """One transcript: every record read, every spawn-shaped subtype named."""
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError as e:
        raise CouldNotRun(f"{path} could not be read: {e}") from e
    records = 0
    unreadable = 0
    findings: list[str] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            whole = json.loads(line)
        except ValueError:
            unreadable += 1
            continue
        if not isinstance(whole, dict):
            unreadable += 1
            continue
        records += 1
        kind = whole.get("subtype")
        if isinstance(kind, str) and kind.startswith(SPAWN_PREFIX):
            findings.append(
                f"spawn-event: {path}:{number}: subtype {kind} — a task ran inside a phase "
                "session, and no phase spawns on the advancement path (ADR-0004/D1)"
            )
    return Scan(path=path, records=records, unreadable=unreadable, findings=tuple(findings))


def transcripts(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise CouldNotRun(f"{directory} is not a directory, so no transcript was examined")
    found = sorted(directory.rglob("*.jsonl"))
    if not found:
        raise CouldNotRun(f"no transcript under {directory}: a batch that ran phases wrote "
                          "streams, so an empty corpus is the wrong place, not a clean one")
    return found


def examine(directory: Path, say) -> int:
    scanned = [scan(path) for path in transcripts(directory)]
    records = sum(s.records for s in scanned)
    unreadable = sum(s.unreadable for s in scanned)
    say(f"transcript-audit: {len(scanned)} transcript(s) examined under {directory}, "
        f"{records} record(s), {unreadable} unreadable line(s)")
    findings = [f for s in scanned for f in s.findings]
    for finding in findings:
        say(f"transcript-audit: FINDING: {finding}")
    if findings:
        return FINDING
    say("transcript-audit: clean (no spawn event in any phase transcript)")
    return CLEAN


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", required=True, help="the directory a batch's phase streams landed in")
    a = ap.parse_args()
    try:
        return examine(Path(a.dir), print)
    except CouldNotRun as e:
        print(f"transcript-audit: VOID: {e}; not a pass", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    raise SystemExit(main())

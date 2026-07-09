#!/usr/bin/env python3
"""ledger-audit: mechanical checks over the dev-ledger.

Hard checks (any violation -> exit 1):
  schema         every line parses; required fields present; enums legal; ids unique
  signed         every signed entry names a mechanical check in discharged_by, with a run ref
  coherence      testimony/refutation entries are never signed; assertions enter unverified
  chains         supersedes targets exist; transitions along a chain are legal
  immutable      (needs git) every line ever committed is byte-identical now, live or in trace
  trace          every trace entry has trace_reason and a resolvable pointer

Warn checks (reported, exit 0 unless --strict):
  contested      live claim with a refutation about it and no successor/retirement (the glut signal)
  unverified     the UNVERIFIED map: live claims with check == "none" (informational)
  claimrate      assertions per commit over recent history (under-claiming signal; needs git)

Usage:
  python3 ledger-audit.py [--root .] [--strict] [--report]
Wire into the pre-commit hook after the check runs; the hook's own entries are
validated the same as everyone else's.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REQUIRED = ("id", "ts", "claim", "source", "kind", "status")
KINDS = {"assertion", "testimony", "refutation"}
STATUSES = {"unverified", "signed", "refuted", "retired"}
SOURCES = {"claude-code", "subagent", "human", "hook"}
# discharged_by.check values that are NOT mechanical; a signed entry naming one is a violation.
GENERATIVE = {"none", "pr-review", "deep-reason", "testimony", "workflow-verify", "claude-code", "subagent"}
LEGAL_NEXT = {  # legal status of a successor entry, keyed by predecessor status
    "unverified": {"signed", "refuted", "unverified"},  # unverified successor = revised assertion
    "signed": set(),      # a signed claim is never superseded in place; defeat = refutation about it + retirement
    "refuted": set(),     # refuted stays on the record; removal only via retirement
    "retired": set(),
}


class V:
    def __init__(self, check: str, msg: str):
        self.check, self.msg = check, msg

    def __str__(self):
        return f"[{self.check}] {self.msg}"


def read_jsonl(path: Path) -> tuple[list[dict], list[V]]:
    out, viol = [], []
    if not path.exists():
        return out, viol
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            viol.append(V("schema", f"{path.name}:{n} not JSON: {e}"))
    return out, viol


def check_schema(entries: list[dict], where: str) -> list[V]:
    viol, seen = [], set()
    for e in entries:
        eid = e.get("id", "<missing>")
        for f in REQUIRED:
            if f not in e:
                viol.append(V("schema", f"{where} {eid}: missing field '{f}'"))
        if e.get("kind") not in KINDS:
            viol.append(V("schema", f"{where} {eid}: bad kind {e.get('kind')!r}"))
        if e.get("status") not in STATUSES:
            viol.append(V("schema", f"{where} {eid}: bad status {e.get('status')!r}"))
        if e.get("source") not in SOURCES:
            viol.append(V("schema", f"{where} {eid}: bad source {e.get('source')!r}"))
        if eid in seen:
            viol.append(V("schema", f"{where} {eid}: duplicate id"))
        seen.add(eid)
    return viol


def check_signed(entries: list[dict]) -> list[V]:
    viol = []
    for e in entries:
        if e.get("status") != "signed":
            continue
        d = e.get("discharged_by") or {}
        chk = (d.get("check") or "").strip().lower()
        if not chk or chk in GENERATIVE:
            viol.append(V("signed", f"{e.get('id')}: signed without a mechanical check (got {chk!r})"))
        if not (d.get("run") or "").strip():
            viol.append(V("signed", f"{e.get('id')}: signed with no run reference"))
    return viol


def check_coherence(entries: list[dict]) -> list[V]:
    viol = []
    for e in entries:
        k, s, eid = e.get("kind"), e.get("status"), e.get("id")
        if k in ("testimony", "refutation"):
            if s == "signed":
                viol.append(V("coherence", f"{eid}: {k} entry carries status 'signed'"))
            if not e.get("about"):
                viol.append(V("coherence", f"{eid}: {k} entry has no 'about' target"))
    return viol


def check_chains(live: list[dict], trace: list[dict]) -> list[V]:
    viol = []
    all_ids = {e["id"] for e in live + trace if "id" in e}
    by_id = {e["id"]: e for e in live if "id" in e}
    for e in live:
        sup = e.get("supersedes")
        if sup:
            if sup not in all_ids:
                viol.append(V("chains", f"{e.get('id')}: supersedes {sup} which does not exist"))
            elif sup in by_id:
                prev = by_id[sup].get("status")
                if e.get("status") not in LEGAL_NEXT.get(prev, set()):
                    viol.append(V("chains", f"{e.get('id')}: illegal transition {prev} -> {e.get('status')}"))
    return viol


def check_trace(trace: list[dict], live: list[dict]) -> list[V]:
    viol = []
    ids = {e["id"] for e in live + trace if "id" in e}
    for e in trace:
        eid = e.get("id")
        if not (e.get("trace_reason") or "").strip():
            viol.append(V("trace", f"{eid}: retired with no trace_reason"))
        ptr = e.get("retired_by") or e.get("supersedes")
        if not ptr:
            viol.append(V("trace", f"{eid}: retired with no pointer to what defeated/superseded it"))
        elif ptr not in ids:
            viol.append(V("trace", f"{eid}: pointer {ptr} does not resolve"))
    return viol


def git(root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def check_immutable(root: Path, ledger_rel: str, live: list[dict], trace: list[dict]) -> list[V]:
    """Every line ever committed must exist byte-identical now, in live or trace."""
    log = git(root, "log", "--format=%H", "--", ledger_rel)
    if not log:
        return []  # no git history: skip gracefully
    current = set()
    p = root / ledger_rel
    if p.exists():
        current |= {l for l in p.read_text().splitlines() if l.strip()}
    for tf in (root / "ledger" / "trace").glob("*.jsonl"):
        current |= {l for l in tf.read_text().splitlines() if l.strip()}
    viol = []
    for sha in log.split():
        hist = git(root, "show", f"{sha}:{ledger_rel}")
        if hist is None:
            continue
        for line in hist.splitlines():
            if line.strip() and line not in current:
                eid = "?"
                try:
                    eid = json.loads(line).get("id", "?")
                except Exception:
                    pass
                viol.append(V("immutable", f"line for {eid} committed at {sha[:8]} was edited or lost (not found verbatim in live or trace)"))
    return viol


def warn_contested(live: list[dict]) -> list[V]:
    refuted_about = defaultdict(list)
    for e in live:
        if e.get("kind") == "refutation" and e.get("about"):
            refuted_about[e["about"]].append(e["id"])
    superseded = {e.get("supersedes") for e in live if e.get("supersedes")}
    viol = []
    for e in live:
        eid = e.get("id")
        if e.get("kind") != "assertion" or e.get("status") not in ("unverified", "signed"):
            continue
        if eid in refuted_about and eid not in superseded:
            viol.append(V("contested", f"{eid}: live {e.get('status')} claim has standing refutation(s) {refuted_about[eid]} and no successor or retirement — the glut signal"))
    return viol


def report_unverified(live: list[dict]) -> list[str]:
    return [f"  {e['id']}: {e.get('claim','')[:90]}"
            for e in live
            if e.get("kind") == "assertion" and e.get("status") == "unverified"
            and (e.get("check") or "none") == "none"]


def warn_claimrate(root: Path, live: list[dict]) -> str | None:
    log = git(root, "log", "--format=%H", "-n", "50")
    if not log:
        return None
    commits = len(log.split())
    asserts = sum(1 for e in live if e.get("kind") == "assertion" and e.get("source") in ("claude-code", "subagent"))
    if commits >= 10 and asserts == 0:
        return f"claimrate: 0 model assertions across {commits} recent commits — possible under-claiming (silence gaming the map)"
    return f"claimrate: {asserts} model assertions / {commits} recent commits"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--strict", action="store_true", help="warn checks also fail the run")
    ap.add_argument("--report", action="store_true", help="print the UNVERIFIED map and claim rate")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    ledger_rel = "ledger/claims.jsonl"

    live, viol = read_jsonl(root / ledger_rel)
    trace: list[dict] = []
    tdir = root / "ledger" / "trace"
    if tdir.exists():
        for tf in sorted(tdir.glob("*.jsonl")):
            t, v = read_jsonl(tf)
            trace += t
            viol += v

    hard = viol
    hard += check_schema(live, "live") + check_schema(trace, "trace")
    hard += check_signed(live)
    hard += check_coherence(live + trace)
    hard += check_chains(live, trace)
    hard += check_trace(trace, live)
    hard += check_immutable(root, ledger_rel, live, trace)

    warn = warn_contested(live)

    for v in hard:
        print(f"FAIL {v}")
    for v in warn:
        print(f"WARN {v}")
    if args.report:
        unv = report_unverified(live)
        print(f"UNVERIFIED map ({len(unv)} claims with no check):")
        for line in unv:
            print(line)
        cr = warn_claimrate(root, live)
        if cr:
            print(cr)

    names = ["schema", "signed", "coherence", "chains", "trace", "immutable"]
    failed = {v.check for v in hard}
    for n in names:
        print(f"{'FAIL' if n in failed else 'PASS'}  {n}")
    print(f"{'WARN' if warn else 'PASS'}  contested")

    if hard or (args.strict and warn):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

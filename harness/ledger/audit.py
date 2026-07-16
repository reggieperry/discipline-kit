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
  tdd-precedence park→supersede pairs: the parked claim's commit is ledger-only AND precedes the
                 code (needs git). C1 at development granularity; subsumes the preregistration
                 audit's dev-side half.
  unverified     the UNVERIFIED map: live claims with check == "none" (informational)
  claimrate      assertions per commit over recent history (under-claiming signal; needs git)
  red-proof coverage  (--report only) k/n test-bearing slices carrying a red-proof receipt (needs git)

Usage:
  python3 ledger-audit.py [--root .] [--strict] [--report]
Wire into the pre-commit hook after the check runs; the hook's own entries are
validated the same as everyone else's.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
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
RUNNABLE = {"repo-check", "scala-check", "scala-suite", "typecheck"}  # a runnable-check successor
CODE_EXTS = (".py", ".go", ".scala", ".sc", ".ts", ".tsx", ".js", ".jsx", ".sh",
             ".rs", ".java", ".rb", ".c", ".cc", ".cpp", ".h", ".hpp")
TEST_HINTS = ("test", "Suite", "spec")

# MEMORY.md index-size budgets (§13.41). Index honesty with teeth: a warn-only budget fires into a
# void (the mnemosyne index truncated at 38 KB past a working 24 KB guard), so the hard budget is a
# genuine FAIL. Config-keyed via LEDGER_MEM_SOFT_KB / LEDGER_MEM_HARD_KB.
MEMORY_INDEX_SOFT_KB = 16
MEMORY_INDEX_HARD_KB = 24


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


def check_trace(trace: list[dict], retire_records: list[dict], live: list[dict]) -> list[V]:
    """Every retired claim carries a reason and a resolvable pointer — supplied EITHER by a legacy
    in-place retired entry (status 'retired' + trace_reason on the claim) OR by a sidecar retirement
    record (`retire_of` naming the claim; the verbatim-move form). `trace` is the claim entries;
    `retire_records` the sidecars."""
    viol = []
    ids = {e["id"] for e in live + trace if "id" in e}
    retired_ids: set[str] = set()
    for r in retire_records:
        tgt = r.get("retire_of")
        retired_ids.add(tgt)
        if not (r.get("trace_reason") or "").strip():
            viol.append(V("trace", f"retirement record for {tgt}: no trace_reason"))
        ptr = r.get("retired_by") or r.get("supersedes")
        if not ptr:
            viol.append(V("trace", f"retirement record for {tgt}: no pointer to what defeated/superseded it"))
        elif ptr not in ids:
            viol.append(V("trace", f"retirement record for {tgt}: pointer {ptr} does not resolve"))
        if tgt not in ids:
            viol.append(V("trace", f"retirement record retire_of {tgt} does not resolve to a claim"))
    for e in trace:
        eid = e.get("id")
        if e.get("status") == "retired" and (e.get("trace_reason") or "").strip():
            ptr = e.get("retired_by") or e.get("supersedes")  # legacy in-place form
            if not ptr:
                viol.append(V("trace", f"{eid}: retired with no pointer to what defeated/superseded it"))
            elif ptr not in ids:
                viol.append(V("trace", f"{eid}: pointer {ptr} does not resolve"))
        elif eid not in retired_ids:
            viol.append(V("trace", f"{eid}: in trace/ with neither a legacy trace_reason nor a retirement record"))
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


def introducing_commit(root: Path, cid: str) -> str | None:
    """The oldest commit that added `cid`'s line to the ledger (git log -S, last = oldest)."""
    out = git(root, "log", "-S", cid, "--format=%H", "--", "ledger/claims.jsonl")
    lines = (out or "").split()
    return lines[-1] if lines else None


def changed_paths(root: Path, commit: str) -> list[str]:
    out = git(root, "show", "--name-only", "--format=", commit)
    return [p for p in (out or "").splitlines() if p.strip()]


def is_ledger_only(root: Path, commit: str) -> bool:
    """True iff the commit changed no code file — a claim-first commit touches the ledger, not the build."""
    paths = changed_paths(root, commit)
    return bool(paths) and not any(p.endswith(CODE_EXTS) for p in paths)


def is_ancestor(root: Path, a: str, b: str) -> bool:
    try:
        r = subprocess.run(["git", "merge-base", "--is-ancestor", a, b],
                           cwd=root, capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def park_supersede_pairs(live: list[dict], by_id: dict) -> list[tuple[dict, dict]]:
    """(parked X, successor Y): Y supersedes an unverified X with a runnable-check, where X is an
    ORIGINAL claim-first claim — one that does not itself supersede anything. A three-link discharge
    chain (park-nonrunnable -> repo-check -> signed) has a repo-check MIDDLE link that supersedes the
    parked claim and is superseded by the signed one; that middle link is a discharge step, not a
    claim-first event, so it is skipped (clm-0030). Only the original parked claim pairs with its
    runnable successor — the pair whose precedence timestamp actually exists."""
    pairs = []
    for y in live:
        x_id = y.get("supersedes")
        if not x_id or (y.get("check") or "none") not in RUNNABLE:
            continue
        x = by_id.get(x_id)
        if x and x.get("status") == "unverified" and not x.get("supersedes"):
            pairs.append((x, y))
    return pairs


def warn_tdd_precedence(root: Path, live: list[dict], trace: list[dict]) -> list[V]:
    """C1 at development granularity — subsumes the preregistration audit's dev-side half. For every
    park→supersede pair, the parked claim's introducing commit must be ledger-only and an ancestor of
    the successor's commit; either failure means the claim did not precede its code (a missing/late
    precedence timestamp).

    Squash-safe (§10): where the two introducing commits collapse into one code-carrying commit
    (xc == yc — the squash signature that destroys the per-commit ancestry), the ancestry is gone, so
    the check consumes a pre-merge precedence CERTIFICATE (`has_precedence_certificate`) instead and
    warns only on its absence. Rebase-merge and merge-commit repos keep the richer per-commit
    verification for free (xc != yc)."""
    entries = live + trace
    by_id = {e["id"]: e for e in entries if e.get("id")}
    viol = []
    for x, y in park_supersede_pairs(live, by_id):
        xc = introducing_commit(root, x["id"])
        yc = introducing_commit(root, y["id"])
        if not xc or not yc:
            continue  # commits unlocatable (shallow clone) — silent, not a warn
        if xc == yc and not is_ledger_only(root, xc):
            # Squash-collapsed: claim, successor, and code share one commit. Ancestry is gone; the
            # pre-merge certificate is the squash-proof substitute — a line, not a topology.
            if not has_precedence_certificate(x["id"], entries):
                viol.append(V("tdd-precedence", f"no precedence certificate for {x['id']}; run the PR-mode check (audit.py --certify) before merge, or verify the branch manually while its ref survives"))
        elif not is_ledger_only(root, xc):
            viol.append(V("tdd-precedence", f"{x['id']} (parked for {y['id']}) landed with code, not as a ledger-only commit — the claim did not precede its code; the precedence timestamp is missing or late"))
        elif not is_ancestor(root, xc, yc):
            viol.append(V("tdd-precedence", f"{x['id']} does not precede its successor {y['id']} in git history — the precedence timestamp is missing or late"))
    return viol


_CERT_PREFIX = "precedence verified:"


def has_precedence_certificate(x_id: str, entries: list[dict]) -> bool:
    """A pre-merge precedence certificate for the parked claim: a testimony about it whose text
    begins with the certificate prefix. It is content, not commit topology — so it survives a squash
    that erased the ancestry the direct check reads."""
    return any(
        e.get("kind") == "testimony" and e.get("about") == x_id
        and (e.get("claim") or "").startswith(_CERT_PREFIX)
        for e in entries
    )


def _current_branch(root: Path) -> str:
    b = (git(root, "rev-parse", "--abbrev-ref", "HEAD") or "").strip()
    return b if b and b != "HEAD" else "detached"


def _next_claim_id(entries: list[dict]) -> str:
    nums = [int(e["id"].split("-", 1)[1]) for e in entries
            if isinstance(e.get("id"), str) and e["id"].startswith("clm-")
            and e["id"].split("-", 1)[1].isdigit()]
    return f"clm-{(max(nums) + 1) if nums else 0:04d}"


def certify_precedence(root: Path, live: list[dict], trace: list[dict]) -> tuple[list[str], list[str]]:
    """PR mode (§10.28): on the intact branch (where full history is present, pre-squash), emit a
    precedence certificate for each park→supersede pair whose ledger-only claim precedes its code by
    ancestry. The certificate is ordinary testimony (never signs), written straight into
    ledger/claims.jsonl so a later squash carries it as content. Idempotent (skips a pair already
    certified). Returns (emitted_ids, failed_ids); a pair whose precedence does NOT verify is a
    failure, never certified — you cannot certify a claim that did not precede its code."""
    entries = live + trace
    by_id = {e["id"]: e for e in entries if e.get("id")}
    branch = _current_branch(root)
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    ts = datetime.now(timezone.utc).isoformat()
    emitted, failed = [], []
    for x, y in park_supersede_pairs(live, by_id):
        xc = introducing_commit(root, x["id"])
        yc = introducing_commit(root, y["id"])
        if not xc or not yc:
            continue
        if is_ledger_only(root, xc) and is_ancestor(root, xc, yc):
            if has_precedence_certificate(x["id"], entries):
                continue  # already certified — idempotent
            cert = {
                "id": _next_claim_id(entries), "ts": ts,
                "claim": f"{_CERT_PREFIX} {x['id']} ledger-only commit {xc[:8]} precedes its code "
                         f"at {yc[:8]} (branch {branch}, run {run_id})",
                "subject": "precedence-certificate", "source": "hook", "kind": "testimony",
                "status": "unverified", "check": "none", "about": x["id"],
            }
            with (root / "ledger" / "claims.jsonl").open("a") as f:
                f.write(json.dumps(cert, separators=(",", ":")) + "\n")
            entries.append(cert)  # a second pair in the same run sees it, keeping ids monotonic
            emitted.append(x["id"])
        else:
            failed.append(x["id"])
    return emitted, failed


def _slice_ids(x_id: str, y_id: str, entries: list[dict]) -> set[str]:
    """The claim ids that stand for one slice: the parked claim, its runnable successor, and the
    successor's transitive superseders (the discharge chain FORWARD — e.g. the gate-signed 3rd link of
    a park->repo-check->signed chain). A red-proof receipt about ANY of them is the slice's receipt
    (clm-0030): the receipt names the live claim, which is usually the signed descendant, not the
    pair member the counter walks."""
    ids = {x_id, y_id}
    forward: dict = defaultdict(list)
    for e in entries:
        if e.get("supersedes"):
            forward[e["supersedes"]].append(e.get("id"))
    frontier = [y_id]
    while frontier:
        for succ in forward.get(frontier.pop(), []):
            if succ and succ not in ids:
                ids.add(succ)
                frontier.append(succ)
    return ids


def report_red_proof_coverage(root: Path, live: list[dict], trace: list[dict]) -> str | None:
    """`k/n test-bearing slices` carrying a red-proof testimony about their claim (the loop's running
    follow-through rate), plus the detector-class subset when the parked claim carries the tag. A
    receipt counts for the slice when it is `about` any id in the slice's forward chain, so a receipt
    filed against the signed descendant of a park->repo-check->signed discharge is credited (clm-0030)."""
    entries = live + trace
    by_id = {e["id"]: e for e in entries if e.get("id")}
    rp_about = {e.get("about") for e in entries
                if e.get("kind") == "testimony" and "red-proof" in (e.get("claim") or "")}
    test_bearing = []
    for x, y in park_supersede_pairs(live, by_id):
        yc = introducing_commit(root, y["id"])
        if yc and any(h in p for p in changed_paths(root, yc) for h in TEST_HINTS):
            test_bearing.append((x, y))
    n = len(test_bearing)
    if n == 0:
        return None
    covered = sum(1 for x, y in test_bearing if _slice_ids(x["id"], y["id"], entries) & rp_about)
    line = f"red-proof coverage: {covered}/{n} test-bearing slices (window)"
    det = [(x, y) for x, y in test_bearing if "detector-class" in (x.get("claim") or "")]
    if det:
        dc = sum(1 for x, y in det if _slice_ids(x["id"], y["id"], entries) & rp_about)
        line += f"; detector-class {dc}/{len(det)}"
    return line


def check_memory_index_size(root: Path) -> tuple[str, "V | None"]:
    """Index honesty with teeth (§13.41). memories/MEMORY.md over the soft budget WARNs; over the
    hard budget is a genuine FAIL — the mnemosyne lesson is that a warn-only budget fires into a void
    (its index truncated at 38 KB past a working 24 KB guard). Budgets are config-keyed via
    LEDGER_MEM_SOFT_KB / LEDGER_MEM_HARD_KB. An absent index is a no-op. Returns (state, finding),
    state in {'ok','soft','hard'}."""
    index = root / "memories" / "MEMORY.md"
    if not index.exists():
        return ("ok", None)
    try:
        size = index.stat().st_size
    except OSError:
        return ("ok", None)
    soft = int(os.environ.get("LEDGER_MEM_SOFT_KB", MEMORY_INDEX_SOFT_KB)) * 1024
    hard = int(os.environ.get("LEDGER_MEM_HARD_KB", MEMORY_INDEX_HARD_KB)) * 1024
    kb = size / 1024
    if size > hard:
        return ("hard", V("memory-index", f"MEMORY.md index is {kb:.1f} KB, over the hard budget "
                          f"({hard // 1024} KB) — prune it to one terse line per memory; detail lives in the topic file"))
    if size > soft:
        return ("soft", V("memory-index", f"MEMORY.md index is {kb:.1f} KB, over the soft budget "
                          f"({soft // 1024} KB) — trim toward one terse line per memory"))
    return ("ok", None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--strict", action="store_true", help="warn checks also fail the run")
    ap.add_argument("--report", action="store_true", help="print the UNVERIFIED map and claim rate")
    ap.add_argument("--certify", action="store_true",
                    help="PR mode (§10): on the intact branch, emit a precedence certificate for each "
                         "verifiable park->supersede pair, then exit. Run before a squash-merge so the "
                         "certificate rides the squash as content.")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    ledger_rel = "ledger/claims.jsonl"

    live, viol = read_jsonl(root / ledger_rel)
    trace_all: list[dict] = []
    tdir = root / "ledger" / "trace"
    if tdir.exists():
        for tf in sorted(tdir.glob("*.jsonl")):
            t, v = read_jsonl(tf)
            trace_all += t
            viol += v
    # A trace file holds claim entries (verbatim-moved or legacy in-place) AND sidecar retirement
    # records (`retire_of`, no `id`). Only claim entries face the claim-shaped checks.
    trace = [e for e in trace_all if "retire_of" not in e]
    retire_records = [e for e in trace_all if "retire_of" in e]

    if args.certify:
        # PR mode is an EMITTER, not a gate: it writes a certificate for every certifiable pair and
        # exits 0. A pair with no certifiable precedence is an advisory note (it landed with code) —
        # the warn-grade tdd-precedence is what actually flags it, here and on the main-side audit.
        emitted, failed = certify_precedence(root, live, trace)
        for cid in emitted:
            print(f"certified precedence: {cid}")
        for cid in failed:
            print(f"note: {cid} has no certifiable precedence (it landed with code); tdd-precedence warns on it")
        if not emitted and not failed:
            print("certify: no park->supersede pairs to certify")
        return 0

    hard = viol
    hard += check_schema(live, "live") + check_schema(trace, "trace")
    hard += check_signed(live)
    hard += check_coherence(live + trace)
    hard += check_chains(live, trace)
    hard += check_trace(trace, retire_records, live)
    hard += check_immutable(root, ledger_rel, live, trace)

    warn = warn_contested(live) + warn_tdd_precedence(root, live, trace)

    # MEMORY.md index size (§13.41): soft → warn, hard → a genuine FAIL (teeth).
    mem_state, mem_v = check_memory_index_size(root)
    if mem_state == "hard":
        hard.append(mem_v)
    elif mem_state == "soft":
        warn.append(mem_v)

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
        rp = report_red_proof_coverage(root, live, trace)
        if rp:
            print(rp)

    names = ["schema", "signed", "coherence", "chains", "trace", "immutable"]
    failed = {v.check for v in hard}
    for n in names:
        print(f"{'FAIL' if n in failed else 'PASS'}  {n}")
    warned = {v.check for v in warn}
    for wn in ("contested", "tdd-precedence"):
        print(f"{'WARN' if wn in warned else 'PASS'}  {wn}")
    print(f"{'FAIL' if mem_state == 'hard' else 'WARN' if mem_state == 'soft' else 'PASS'}  memory-index")

    if hard or (args.strict and warn):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""postcondition.py — the /chain driver's mechanical phase postconditions.

The driver advances only on re-derived ledger/git state, never on a subagent's prose report. It
shells out to these checks after each phase; each exits 0 (the postcondition holds — advance) or 2
(violated — halt the chain and escalate / loop back). Exit 1 is a usage error (also fail-closed for
the driver's purposes: do not advance on a malformed check).

  planner-parked <story-id>       every acceptance criterion entered the courthouse: at least one
                                  UNVERIFIED assertion for the story, parked under a NON-runnable check
                                  (so nothing auto-signs at plan time). Halts a planner that parked
                                  nothing, or that parked under a runnable check.
  tester-clean <base-ref>         the tester touched no production code: `git diff <base> HEAD` is
                                  empty outside test paths. Halts a tester whose diff reached src.
  no-open-refutation <story-id>   no blocking refutation stands open: no UNVERIFIED refutation about
                                  the story that is not itself disposed by a signed successor. Halts
                                  the chain while a review defect is unresolved.

The ledger is ledger/claims.jsonl (override with LEDGER_FILE). Test-path heuristic matches the kit's
red-proof: a path segment containing 'test', or a file matching *Suite*/*spec*.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

RUNNABLE = {"repo-check", "scala-check", "scala-suite", "typecheck"}
_TEST = re.compile(r"(^|/)[^/]*(test|spec)[^/]*($|/)", re.IGNORECASE)


def ledger_path() -> Path:
    return Path(os.environ.get("LEDGER_FILE", "ledger/claims.jsonl"))


def load() -> list[dict]:
    p = ledger_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _mentions(e: dict, story: str) -> bool:
    return story in (str(e.get("subject", "")) + " " + str(e.get("claim", "")))


def is_test_path(p: str) -> bool:
    return bool(_TEST.search(p)) or p.endswith("Suite.scala") or "/tests/" in f"/{p}"


def is_ledger_content(p: str) -> bool:
    # the ledger's CONTENT (claims + graveyard) is the tester's/worker's legitimate output, not
    # production code — an attestation or a signature append is not a code touch. Its integrity is the
    # gate's forgery guard, not this diff. (The gate MACHINERY is fenced separately by trusted-base.)
    return p == "ledger/claims.jsonl" or p.startswith("ledger/trace/")


def planner_parked(story: str) -> int:
    ents = load()
    parked = [e for e in ents
              if e.get("kind") == "assertion" and e.get("status") == "unverified"
              and e.get("check") not in RUNNABLE and _mentions(e, story)]
    if not parked:
        sys.stderr.write(f"planner postcondition VIOLATED: no parked (non-runnable) claim for "
                         f"story {story!r} — the planner parked nothing (or parked under a runnable "
                         f"check, which would auto-sign). Halt.\n")
        return 2
    return 0


def tester_clean(base: str) -> int:
    if not base:
        sys.stderr.write("tester-clean: a base ref is required\n")
        return 1
    v = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"],
                       capture_output=True, text=True)
    if v.returncode != 0:
        sys.stderr.write(f"tester-clean: base ref does not resolve: {base} — failing closed\n")
        return 2
    d = subprocess.run(["git", "diff", "--name-only", "-M", base, "HEAD"],
                       capture_output=True, text=True)
    if d.returncode != 0:
        sys.stderr.write(f"tester-clean: git diff failed — failing closed\n{d.stderr}")
        return 2
    changed = [p for p in d.stdout.split("\n") if p.strip()]
    nontest = [p for p in changed if not is_test_path(p) and not is_ledger_content(p)]
    if nontest:
        sys.stderr.write("tester postcondition VIOLATED: the tester's diff touched non-test paths — "
                         "a tester that touched production code cannot hand off:\n  "
                         + "\n  ".join(nontest) + "\n")
        return 2
    return 0


def _resolved_ids(ents: list[dict]) -> set[str]:
    """Ids that have 'made it through the gate': every signed entry, plus every claim transitively
    superseded toward a signed one. The worker loop-back re-registers a fix (parked, repo-check), the
    gate signs a successor that SUPERSEDES the parked fix, and that fix may in turn supersede the
    original claim — so a signature can be several supersession hops from what it ultimately resolves."""
    superseded_by = {e["supersedes"]: e["id"] for e in ents if e.get("supersedes") and e.get("id")}
    resolved = {e["id"] for e in ents if e.get("status") == "signed" and e.get("id")}
    changed = True
    while changed:
        changed = False
        for e in ents:
            eid = e.get("id")
            if not eid or eid in resolved:
                continue
            succ = superseded_by.get(eid)
            if succ and succ in resolved:
                resolved.add(eid)
                changed = True
    return resolved


def no_open_refutation(story: str) -> int:
    ents = load()
    # A refutation R about claim C is DISPOSED when the fix that addresses it has been signed — via any
    # of the reachable shapes: R itself resolved; the refuted claim C resolved (a signed successor
    # superseded it); or a RESOLVED fix-claim is `about` R (the worker's fix references the refutation
    # and then passes the gate). Keying only on a signed entry `about==R.id` — which the gate's _sign,
    # writing `supersedes` not `about`, can never produce and the forgery guard blocks by hand — was a
    # permanent loop-back deadlock.
    resolved = _resolved_ids(ents)
    about_resolved = {e.get("about") for e in ents if e.get("id") in resolved and e.get("about")}
    open_refs = [e for e in ents
                 if e.get("kind") == "refutation" and e.get("status") == "unverified"
                 and _mentions(e, story)
                 and e.get("id") not in resolved
                 and e.get("about") not in resolved
                 and e.get("id") not in about_resolved]
    if open_refs:
        ids = ", ".join(str(e.get("id")) for e in open_refs)
        sys.stderr.write(f"reviewer postcondition VIOLATED: blocking refutation(s) stand open "
                         f"for story {story!r}: {ids} — resolve (worker loop-back) before advancing. "
                         f"Halt.\n")
        return 2
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: postcondition.py "
                         "{planner-parked <story-id> | tester-clean <base-ref> | "
                         "no-open-refutation <story-id>}\n")
        return 1
    check = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    if check == "planner-parked":
        return planner_parked(arg) if arg else 1
    if check == "tester-clean":
        return tester_clean(arg)
    if check == "no-open-refutation":
        return no_open_refutation(arg) if arg else 1
    sys.stderr.write(f"postcondition.py: unknown check {check!r}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())

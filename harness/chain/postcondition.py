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

import os
import re
import subprocess
import sys
from pathlib import Path

# CROSS-DIR IMPORT of the dev-ledger algebra library. `model.py` lives in the repo's `ledger/`
# (base-installed); this predicate installs to `.claude/chain/`, so it puts `ledger/` on the path via
# the repo root. This is the one genuine cross-directory bridge — same-dir tools (gate/audit) import
# `model` natively; see ledger/README.md "Layout".
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ledger"))
import model  # noqa: E402  (RUNNABLE, load, resolved_ids, mentions, is_signed, Claim)

_TEST = re.compile(r"(^|/)[^/]*(test|spec)[^/]*($|/)", re.IGNORECASE)


def ledger_path() -> Path:
    return Path(os.environ.get("LEDGER_FILE", "ledger/claims.jsonl"))


def is_test_path(p: str) -> bool:
    return bool(_TEST.search(p)) or p.endswith("Suite.scala") or "/tests/" in f"/{p}"


def is_ledger_content(p: str) -> bool:
    # the ledger's CONTENT (claims + graveyard) is the tester's/worker's legitimate output, not
    # production code — an attestation or a signature append is not a code touch. Its integrity is the
    # gate's forgery guard, not this diff. (The gate MACHINERY is fenced separately by trusted-base.)
    return p == "ledger/claims.jsonl" or p.startswith("ledger/trace/")


def planner_parked(story: str) -> int:
    ents = model.load(ledger_path())
    parked = [e for e in ents
              if e.get("kind") == "assertion" and e.get("status") == "unverified"
              and not model.is_runnable(e) and model.mentions(e, story)]
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
    # test-path changes must be purely ADDITIVE — new tests/assertions only, no edit to an existing
    # line. A count-based check misses an in-place weakening (assertEquals(x,5) -> assertEquals(x,x)),
    # so require zero removed lines in each test-path diff; the attest-only tester has no legitimate
    # reason to modify an existing grader.
    for tp in [p for p in changed if is_test_path(p)]:
        hd = subprocess.run(["git", "diff", "--unified=0", "-M", base, "HEAD", "--", tp],
                            capture_output=True, text=True)
        removed = [l for l in hd.stdout.splitlines()
                   if l.startswith("-") and not l.startswith("---")]
        if removed:
            sys.stderr.write(f"tester postcondition VIOLATED: {tp} was modified in place, not purely "
                             f"added to — a tester must not weaken or rewrite an existing grader "
                             f"({len(removed)} removed/changed line(s)). Halt.\n")
            return 2
    return 0


def worker_complete(story: str) -> int:
    ents = model.load(ledger_path())
    resolved = model.resolved_ids(ents)
    superseded = model.superseded_ids(ents)
    # An UNTOUCHED planner criterion is an open obligation the worker never addressed: an unverified,
    # non-runnable claim that names the story, supersedes NOTHING (a planner original, not a re-park),
    # and has NO successor (not superseded). A BUILT criterion is superseded toward a signature; a
    # DEFERRED one is re-parked (it supersedes the original, carrying its reason) — both are addressed.
    untouched = [e for e in ents
                 if e.get("kind") == "assertion" and e.get("status") == "unverified"
                 and not model.is_runnable(e) and model.mentions(e, story)
                 and not e.get("supersedes")
                 and e.get("id") not in superseded and e.get("id") not in resolved]
    if untouched:
        ids = ", ".join(str(e.get("id")) for e in untouched)
        sys.stderr.write(f"worker postcondition VIOLATED: criterion(s) never built or deferred for "
                         f"story {story!r}: {ids} — the worker cannot hand off an open obligation. "
                         f"Halt.\n")
        return 2
    return 0


def no_open_refutation(story: str) -> int:
    ents = model.load(ledger_path())
    by_id: dict[str, model.Claim] = {e["id"]: e for e in ents if e.get("id")}
    resolved = model.resolved_ids(ents)

    # A refutation R about claim C BELONGS to the story if R's own text names it, OR — the reviewer's
    # real shape — R carries `about: C` and the refuted claim C names the story (the reviewer is never
    # told to embed the story id in the refutation, so scope must follow the about-edge).
    def in_story(r: model.Claim) -> bool:
        if model.mentions(r, story):
            return True
        about = r.get("about")
        c = by_id.get(about) if about else None
        return c is not None and model.mentions(c, story)

    # A refutation R about C is DISPOSED only when a FIX has passed the gate — a resolved successor
    # SUPERSEDES C (C got fixed and re-signed), or a resolved claim is `about` R (the fix references
    # the refutation), or R itself was resolved/retired. C's own PRE-EXISTING signature does NOT
    # dispose R: a refutation says the signed claim is now known-wrong, and only a superseding fix
    # answers it — keying on "C is resolved" would fail open on a fresh refutation about an old sign.
    superseded_by_resolved = {e.get("supersedes") for e in ents
                              if e.get("supersedes") and e.get("id") in resolved}
    about_resolved = {e.get("about") for e in ents if e.get("id") in resolved and e.get("about")}

    def disposed(r: model.Claim) -> bool:
        rid, c = r.get("id"), r.get("about")
        return (rid in resolved or rid in about_resolved
                or (c is not None and c in superseded_by_resolved))

    open_refs = [e for e in ents
                 if e.get("kind") == "refutation" and e.get("status") == "unverified"
                 and in_story(e) and not disposed(e)]
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
                         "{planner-parked <story-id> | worker-complete <story-id> | "
                         "tester-clean <base-ref> | no-open-refutation <story-id>}\n")
        return 1
    check = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    if check == "planner-parked":
        return planner_parked(arg) if arg else 1
    if check == "worker-complete":
        return worker_complete(arg) if arg else 1
    if check == "tester-clean":
        return tester_clean(arg)
    if check == "no-open-refutation":
        return no_open_refutation(arg) if arg else 1
    sys.stderr.write(f"postcondition.py: unknown check {check!r}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())

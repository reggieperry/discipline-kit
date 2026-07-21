#!/usr/bin/env python3
"""verdict.py — the /chain reviewer committee's four-state verdict, aggregated MECHANICALLY.

The reviewer phase runs a manifest of roles (e.g. logic-and-state, abuse-and-boundaries), each of
which files a structured verdict. The verdict must NOT be aggregated by a mind — an LLM that folds an
errored or absent reviewer into "CLEAN" is the confidently-wrong-at-signature failure this whole
system exists to expose. This computes the four-state Belnap read FAIL-CLOSED from the role files:

  CLEAN (True)          every launched role produced a well-formed `clean` completion. This is
                        POSITIVE-EXISTENCE against the manifest — N launched must yield N well-formed
                        clean verdicts — never "no refutation was filed, so CLEAN".
  REFUTED (False)       at least one role returned `refuted` (a blocking defect with a disposing
                        check). Dominates a co-present contest — a real defect is the signal to act on.
  CONTESTED (Both/glut) at least one role returned `contested` (reviewers split, a finding with no
                        disposing check, or the diff touches the judge) and none refuted.
  INDETERMINATE (gap)   any launched role is missing, malformed, errored, or carries an unrecognized
                        verdict word. An absent or unreadable reviewer is never a clean vote.

CLEAN authorizes nothing on its own — in the veto-only design the mechanical envelope is the merge
warrant and this verdict can only BLOCK. It drives routing:

  CLEAN          -> advance; an LGTM is sufficient (no reviewer objected)         exit 0
  REFUTED        -> worker loop-back (fix the disposing check, re-review)          exit 2
  CONTESTED      -> escalate to the operator (deep review)                         exit 3
  INDETERMINATE  -> escalate to the operator (deep review; incomplete committee)   exit 4

Usage: verdict.py <manifest.json> <verdicts-dir>
  manifest.json : a JSON array of the role names that were launched.
  verdicts-dir  : one <role>.json per role, each an object with a "verdict" of
                  clean | refuted | contested | error (anything else => INDETERMINATE).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CLEAN, REFUTED, CONTESTED, INDETERMINATE = "CLEAN", "REFUTED", "CONTESTED", "INDETERMINATE"
EXIT = {CLEAN: 0, REFUTED: 2, CONTESTED: 3, INDETERMINATE: 4}
ROUTE = {
    CLEAN: "advance; an LGTM is sufficient (no reviewer objected)",
    REFUTED: "worker loop-back (resolve the disposing check, then re-review fresh)",
    CONTESTED: "escalate to the operator (deep review)",
    INDETERMINATE: "escalate to the operator (deep review; the committee did not complete)",
}
KNOWN = {"clean", "refuted", "contested", "error"}


def read_role(vdir: Path, role: str) -> str:
    """Return the recognized verdict word for a role, or a reason it is INDETERMINATE."""
    f = vdir / f"{role}.json"
    if not f.exists():
        return f"__missing__:{role}"
    try:
        v = str(json.loads(f.read_text()).get("verdict", "")).strip().lower()
    except Exception:
        return f"__malformed__:{role}"
    if v not in KNOWN:
        return f"__unknown__:{role}:{v or '(empty)'}"
    return v


def aggregate(manifest: list[str], vdir: Path) -> tuple[str, list[str]]:
    if not manifest:
        return INDETERMINATE, ["empty manifest — an empty committee cannot be CLEAN"]
    verdicts = {role: read_role(vdir, role) for role in manifest}
    problems = [v for v in verdicts.values() if v.startswith("__") or v == "error"]
    refuted = [r for r, v in verdicts.items() if v == "refuted"]
    contested = [r for r, v in verdicts.items() if v == "contested"]

    # order matters: a real defect (REFUTED) is the strongest signal and dominates. Incompleteness
    # (INDETERMINATE) fails closed above a mere CLEAN, but a filed refutation still wins — it names a
    # concrete disposing check the worker can act on, which is more actionable than "re-run everyone".
    if refuted:
        return REFUTED, [f"{r}: refuted" for r in refuted]
    if problems:
        return INDETERMINATE, problems
    if contested:
        return CONTESTED, [f"{r}: contested" for r in contested]
    return CLEAN, [f"{r}: clean" for r in manifest]


def main() -> int:
    if len(sys.argv) != 3:
        sys.stderr.write("usage: verdict.py <manifest.json> <verdicts-dir>\n")
        return 4  # fail closed
    try:
        manifest = json.loads(Path(sys.argv[1]).read_text())
        assert isinstance(manifest, list)
    except Exception as e:
        sys.stderr.write(f"verdict.py: cannot read manifest — failing closed: {e}\n")
        return 4
    vdir = Path(sys.argv[2])
    verdict, detail = aggregate([str(r) for r in manifest], vdir)
    print(f"{verdict}  ->  {ROUTE[verdict]}")
    for d in detail:
        print(f"  {d}")
    return EXIT[verdict]


if __name__ == "__main__":
    sys.exit(main())

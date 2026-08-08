# ADR-0001 acceptance gate: the deep-reason record

Two fresh-context adversarial passes, per `harness/skills/adr-write/SKILL.md` (a pass before
the draft, another before the second draft). Each pass is testimony: a reader hunted and
reported what it found, which attests and never signs.

## Pass 1 (pre-draft), 2026-08-07: qualified no on the framing

Attacked the proposal to write ADR-0001 on "the state-authority fork" with a four-decision set.
Verdict: the area is real, the framing wrong in two places, and the decision set decided the
substrate rather than the property. Corrections taken into the draft:

- The cited anchor (§4.2(a), "the driver holds the decision") is an item of the containment
  section and is marked PROPOSED; the ADR-shaped object is §7's fork-independent invariant,
  "advancement is re-derived, never reported," written sequencer-agnostically.
- The original D1 contained a fail-open: a phase agent writing its own completion ref is a
  self-report in git's clothing. Rewritten as sequencer-only writes.
- Verdicts must be three-valued (could-not-run is never a pass), postconditions must
  demonstrate red and green before counting, and the examiner must never come from the judged
  tree; all three were missing and are now D2 through D4.
- The refspec ban was demoted from a Decision to a Consequence with the one court available
  today (`scripts/chain-refspec-check.sh`).
- The clm- contradiction (the ADR conventions cited a claim registry the 2026-07-30 ledger
  removal deleted) was adjudicated: fix `docs/adrs/README.md` in the ADR's own commit; rewrite
  `harness/skills/adr-write/SKILL.md` in a follow-up slice, since its worked examples need
  re-authoring rather than deletion.
- Flagged a missing fourth record beyond the design doc's three: the merge posture (the struck
  §2 invariant and §4.12's expiry conditions).

## Pass 2 (draft attack), 2026-08-07: REVISE, four blocking findings

Attacked the actual draft plus the pending slice. All four blockers and the should-fix findings
were resolved before acceptance:

- B1: the draft's spaced em dashes (status line, decision headings) would fail
  `scripts/em-dash-check.sh` the moment the file was staged. Resolved: colon-form headings,
  closed dashes throughout. The upstream trap stands for the follow-up slice: the exempt ADR
  template itself prescribes the failing forms.
- B2: the status line cited this review record before it existed. Resolved: this file.
- B3: the registry row is mandatory in the same commit as the ADR. Resolved: registered.
- B4: a draft-invented clause had the sequencer re-running postconditions on resume, which
  deadlocks on non-monotonic postconditions (red-proof is a historical property; a tester's
  red phase legitimately leaves a red suite). Resolved: verdicts are evaluated once at the
  seam; position alone is re-derived on resume; the forged-ref residue moved to the
  Consequences as a disclosed gap for the containment record.
- Court hardening (S1, S2, S3): the refspec check failed open when git itself was unreadable
  (now exits could-not-run), missed bare-wildcard and mirror configurations (now matched), and
  carries the D3 acknowledgment that a sequencer must run a pinned copy.
- Accuracy fixes: the five-of-six evasion citation (§4.1, not §4.5), the substrate-flip
  attribution (Workflow to shell per §1.1, with §4.8 entertaining the reverse), the trailer
  rejection reduced to its one decisive count, D5's heading matched to its two admitted uses
  with the §4.6 wall-clock qualifier.

## Pass 3 (re-verification of the revised slice), 2026-08-07: CLEAN

The same adversary as pass 2, resumed against the staged slice. Verdict returned: CLEAN, no
blocking findings; all four blockers and all nine should-fixes verified resolved against the
staged content rather than taken on report (the em-dash check run live against the index; the
court re-probed with nine git stubs covering VOID, clean, false-positive, wildcard, mirror,
and push cases; every corrected citation re-checked against the design doc's line numbers).
Residuals returned as non-blocking and taken in the same slice: this section rewritten from
the returned verdict rather than its pre-written placeholder, D2's post-seam single-term
honesty, the push half of the refspec harm mechanism, and the check.sh comment widened to
match its check. Acceptance was flipped only after this verdict arrived.

## Follow-ups this gate created (not part of the ADR's commit)

1. Re-author the authoring surface off the retired clm- apparatus. Widened by the 2026-08-07
   latent-assumption audit from adr-write alone to three artifacts, in priority order:
   `harness/skills/story-intake/SKILL.md` first (its declared handoff is a set of parked
   claims citing a board id—unexecutable since the ledger's deletion, and the artifact a
   chain would consume), then `harness/skills/adr-write/SKILL.md` (six sites, including the
   worked example and the scar paragraph), then `harness/templates/story-template.md` (whose
   guidance comments teach the park step). The walkthrough's misattribution of the stale
   citation to the ADR template was fixed directly—the template was already scrubbed in
   `60d9ee8`.
2. Fix `harness/templates/ADR-template.md`'s prescribed status-line and heading forms, which
   trip the em-dash check for every non-exempt ADR authored from them.
3. Restore a structural guard for ADR shape: `authoring_artifacts_test.py` was deleted with
   the ledger removal while the CHANGELOG still advertises it; today nothing checks that an
   ADR carries a Falsification condition at all.

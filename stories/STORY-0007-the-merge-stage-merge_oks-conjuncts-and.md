---
id: STORY-0007
title: The merge stage: merge_ok's conjuncts and the declared terminal act
deps: [STORY-0003, STORY-0006]
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0002
decisions: [D1, D3, D5]
group: A
---

# Problem / Context

No conjunct of `merge_ok` is evaluated anywhere; neither terminal act exists; the push-scope guard and the merge record naming the forged-ref residue are future by the ADR's own text.

Grounding: `docs/adrs/ADR-0002-merge-posture.md`, D1, D3, and D5. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

The trial merge against one pinned candidate sha; the eight conjuncts with a per-conjunct receipt; conjunct 8's mechanism chosen here as the ADR reserves; both terminal acts behind the profile; the push-scope guard; the residue-naming merge record.

# Scope and non-goals

In scope:

- merge stage, terminal acts, push-scope guard, merge record

Out of scope:

- the PR-merge rules themselves (operator-side, per D1)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] merge_ok holds only when all eight conjuncts pass against the pinned sha—verified by
      `per-conjunct known-bad fixtures`: every conjunct has its known-bad in
      `harness/fixtures/merge_test.py` reading exit 1 against the pinned candidate
      (`c1-check-red-1`, `c2-trusted-touch-1` and `c2-rename-delete-1`, `c3-undeclared-1`,
      `c4-receipt-red-1`, `c5-refutation-1`, `c6-park-1`, `local-main-moved-1` for conjunct 7,
      `c1-check-dirties-1` and `c1-check-commits-1` for conjunct 8), the could-not-run arms
      read exit 2 and never pass (`c1-check-exit-3-2`, `c1-check-untrusted-2`,
      `c3-plan-absent-2`, `c4-receipt-pc-absent-2`, `git-too-old-2`), the pinning blocks read
      exit 1 (`pin-tip-diverged-1`, `pin-non-ancestor-1`, `trial-conflict-1`) or exit 2 for
      premature invocation (`pin-premature-2`, `pin-gap-2`), and the ordering is itself
      asserted—`c2-trusted-touch-1` and `trial-conflict-1` require the commit-path check's log
      ABSENT, so judged code demonstrably runs only over a tree everything cheaper cleared
- [x] a chain push of main is impossible under both terminal acts—verified by `the push-scope
      guard's fixture`: `push-main-uncomposable` calls `guarded_push` directly and requires
      `/`-carrying and `..` ids refused, any push refused under scope `"never"` (which is
      merge-local's paired scope, so under merge-local nothing pushes at all), and the
      shape-valid id `main` landing at `refs/heads/story/main` with remote `main` unmoved;
      `pr-green-0` and `pr-forge-fails-2` read remote heads back and require `main` unmoved
      under open-pr, and `local-cas-and-revert-0`'s git spy pins the merge-local act to one
      compare-and-swap on the local ref with no push in its log
- [x] the merge record names the forged-ref residue as open—verified by `a record-content
      assertion in the merge-stage fixture`: `forged-chain-residue-0` (a chain whose every ref
      the fixture itself planted, which IS the forged shape, passing as ADR-0002/D5 rules) and
      `local-cas-and-revert-0` assert the record's residue line VERBATIM, one per terminal
      act's blast radius, and `record_faults` requires exactly two `testimony:` lines on every
      outcome it reads

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [x] The assertion count is not reduced versus the merge-base. Every existing fixture is
      byte-untouched (`git diff 033a1b3` shows only `harness/chain/core.py` +1 line and
      `scripts/check.sh` +6); `merge_test.py` is a net add of 31 cases and `scripts/check.sh`
      gains one invocation and loses none.
- [x] No new suppressions are introduced versus the merge-base beyond the disclosed shape:
      `merge.py` carries five `# noqa: E402` markers on its `sys.path` import lines, copied
      verbatim from the identical disclosed shape in `invoke.py` (4 at base), `core.py`,
      `advance.py` and `attempt.py`. No linter on the commit path reads them; they are named
      because a marker nobody reads is still a marker. Repo total 14 to 19, all five the same
      mechanical import-resolution shape.
- [x] No new skipped tests versus the merge-base. The fixture has no skip mechanism and every
      case runs on every invocation.

# Risks and rollback

- Risk: a conjunct evaluated against the wrong tree signs the wrong work—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- Owed reconciliation: conjunct 4 composes with STORY-0008's shipped `receipt.py` only through
  an operator-authored `receipt-complete` postcondition wrapper at
  `<pinned_root>/postconditions/receipt-complete/`—it translates the loader's positional
  merged-tree argument into `--receipt <tree>/<receipt-path> --root <kit>`, fixes the in-tree
  receipt-file convention, and supplies the red and green fixture trees the loader demonstrates
  against. The exit contracts already align: the receipt court's park (exit 1) reads as
  conjunct 4 FAIL, the intended mapping. The wrapper is owed, not shipped.
- Recorded by STORY-0005's merge review: that story's seam discloses three residues the merge
  stage is the natural reader of, and how it consumes them is this story's interface call rather
  than the seam's. The seam reads porcelain once, before the postcondition runs and not after, so
  a postcondition that dirties the tree it grades is not caught there. It grades the WORKING TREE
  at the path it was given rather than a fresh checkout of the sha it records, which is the same
  question ADR-0002/D3.8 leaves open as a conjunct owed a mechanism—source-set integrity, the
  tree the checks graded being the tree being merged. And the forged-ref residue ADR-0001
  discloses stands: an agent holding Bash writes the same ref the seam writes, and D3.7's
  one-pinned-candidate-sha conjunct is evaluated over refs that carry that residue with them.

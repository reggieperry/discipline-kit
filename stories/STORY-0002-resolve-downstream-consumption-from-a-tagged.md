---
id: STORY-0002
title: Resolve downstream consumption from a tagged release, and check it
deps: []
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0002
decisions: [D7]
group: B
---

# Problem / Context

`install.sh --refresh-rules` copies from whatever tree the checkout holds and scrapes a version from `CHANGELOG.md`; no tag is resolved, so a bad merge on `main` reaches consumers before any backstop acts. ADR-0002/D7 decides consumers resolve tags the operator mints.

Grounding: `docs/adrs/ADR-0002-merge-posture.md`, D7. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

Make the installer resolve a tagged release (checkout or archive of the tag) and refuse a bare tree; add a check that fails when a consumer path would resolve `main`.

# Scope and non-goals

In scope:

- `install.sh` tag resolution and its check

Out of scope:

- release automation, tag minting policy (operator acts, per D7)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] `install.sh --refresh-rules` resolves a tag, never the checkout tree—verified by `a new
      fixture case driving the installer against a repo where HEAD differs from the latest tag`:
      `harness/fixtures/install_test.py` `refresh-resolves-latest-tag-0` builds a scratch kit
      whose HEAD rule body no tag carries and whose two release tags differ from each other, and
      requires the refreshed rule to be the newest tag's body under VERSION sort (v0.10.0 over
      v0.9.0, so a lexical resolution fails the case) with the pre-fix CHANGELOG decoy version
      absent from the report; `refresh-explicit-tag-0` pins `--tag`, and `bare-tree-refusal-1`,
      `no-tags-refusal-1`, and `refresh-unknown-tag-1` each require a named refusal with nothing
      copied—no working-tree fallback anywhere. On the commit path via `scripts/check.sh`.
- [x] a consumer path resolving `main` fails the build—verified by `the D7 court named in
      ADR-0002's Falsification section, wired into scripts/check.sh`:
      `scripts/tag-consumption-check.sh` runs on every commit; its known-bad plant is the
      pre-fix refresh region VERBATIM (`court-pre-fix-1`, asserting one marker per pattern so a
      single neutered pattern is caught while the others still drive the exit code), plus
      `court-main-rev-1` and `court-head-rev-1` for D7's named falsifier; the clean cases are
      the real repository and a tag-resolving plant; an empty corpus or a refresh region the
      extractor cannot find reads could-not-run (exit 2), never a pass, and denominators print
      on every run.

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [x] The assertion count is not reduced versus the merge-base. The change is net-add: one new
      fixture (14 cases) and one new court, both wired into `scripts/check.sh`; no existing
      fixture, case, or check was touched or removed.
- [x] No new suppressions are introduced versus the merge-base. The one shellcheck note the
      court's patterns provoked (SC2016, a literal `$` inside single quotes) was resolved by
      restructuring the pattern to `[$]`, not by a disable directive.
- [x] No new skipped tests versus the merge-base. The fixture has no skip mechanism; every case
      runs on every invocation.

# Risks and rollback

- Risk: installer behavior change breaks existing refresh flows—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.

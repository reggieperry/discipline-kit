---
id: STORY-0001
title: Run ADR-0003/D7's headless substrate probe and record its three limbs
deps: []
labels: [chain, measurement]
sensitive_files: []
status: draft
adr: ADR-0003
decisions: [D7]
group: A
milestone: v1-sequencer
cites:
  - docs/adrs/ADR-0003-sequencer-obligations.md#d7-the-substrate-is-open-and-one-measurement-closes-it
  - docs/sdlc-chain-design.md
---

# Problem / Context

ADR-0003 decided the sequencer's obligations and deliberately left the substrate open: an
interactive main-loop session, an external process driving headless phases, and an external
process driving one-shot wrapper sessions are all still admissible, because D1 to D6 hold for
every one of them by construction. What separates them is whether the session properties the
design measured—the worktree handoff for the attest-only phases, and hook inheritance—survive
headlessly, and nobody has measured that. Until the probe runs, choosing a substrate means
deciding on a premise nobody has checked, and building the sequencer means guessing.

Grounding against HEAD:

- `docs/adrs/ADR-0003-sequencer-obligations.md:107–124`—D7 states the probe in full: the
  scratch repository's contents, the headless invocation, and the three limbs with their named
  observables. This story runs exactly that and adds nothing to it.
- `docs/adrs/ADR-0003-sequencer-obligations.md:33–36`—the Context records why: every VERIFIED
  session-property probe in the design's §4.8 ran inside an interactive session, so headless
  equivalence is unmeasured in both directions.
- `docs/adrs/ADR-0003-sequencer-obligations.md:128–130`—the Consequences make this the
  sequencer build's first commit, which is why this is STORY-0001 rather than a later one.
- `docs/adrs/ADR-0003-sequencer-obligations.md:186–188`—D7's falsification condition is review
  of that first commit, which must carry the measurement's record. The record is the artifact
  this story delivers; the substrate choice is not.

# Proposed approach

Build the scratch repository outside this checkout, exactly as D7 specifies and with nothing
else in it: a project `.claude/` holding one agent definition that declares
`isolation: worktree` and one project-scope PreToolUse hook that writes a marker file. Invoke
the installed harness headlessly with `claude -p`, recording the version from `claude --version`
in the same result, and prompt the main agent to spawn that subagent, which commits one file.

Retain every raw output under the probe's own directory, then write the record: three limbs,
each PASS or FAIL against its named observable.

- limb (a), the subagent ran: its completion appears in the stream output.
- limb (b), worktree isolation held: the completion's reported worktree path or branch differs
  from the parent checkout, the committed file is reachable from that branch, and the parent
  tree is untouched by `git status`.
- limb (c), hooks fired headlessly: the marker file exists.

Limb (a) is the only one read from the harness's own stream, and ADR-0001/D2's denial probe is
the reason that matters: every stream field reported success while the phase did nothing. So
(a) is never read alone—limb (b)'s committed file is the filesystem corroboration that the
subagent did work rather than reported it.

# Scope and non-goals

In scope:

- The scratch repository, the headless invocation, the retained raw outputs, and the record of
  the three limbs with the harness version.

Out of scope:

- Choosing the substrate. That is D7's successor record, and it weighs disinterest of the
  looker and bounded context on top of whatever this probe returns.
- The advance scripts of D2/D3, the profile schema D5 reads, and ADR-0004's unattended run
  envelope. None of them wait on this measurement in the way the substrate choice does.
- Re-running the probe until it comes out green. A FAIL is the measurement's result, not a
  failed attempt at one.

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] The scratch repository's project `.claude/` holds exactly the agent definition and the
      PreToolUse hook—verified by `find .claude -type f` in the retained record listing those
      two files and no others.
- [x] The harness version is recorded in the result—verified by the record carrying the
      `claude --version` output as a literal string.
- [x] Limb (a) is recorded PASS or FAIL against the subagent's completion in the stream
      output—verified by the retained raw stream containing (or not containing) that record.
- [x] Limb (b) is recorded PASS or FAIL against three observables—verified by
      `git cat-file -e <branch>:<file>` for reachability and `git status --porcelain` printing
      nothing in the parent checkout.
- [x] Limb (c) is recorded PASS or FAIL against the marker file—verified by `test -f` on it.
- [x] Every limb carries PASS or FAIL and no third value—verified by reading the record; an
      unrunnable limb reads FAIL with its reason, never "inconclusive" and never a blank.
- [x] The raw outputs are retained beside the record—verified by the record naming each file
      and each file existing.

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: the probe is read as a substrate decision rather than as a measurement—likely, because
  a green result is suggestive. Mitigation: the record states the limbs and nothing else; the
  choice is D7's successor record, and this story's scope names that boundary.
- Risk: the harness version drifts between the probe and the sequencer build, so the result
  describes a version nobody runs—mitigation: the version is a recorded observable, so the gap
  is visible rather than assumed away.
- Risk: a limb that could not run is recorded as a pass—mitigation: the sixth criterion admits
  no third value, matching the kit's could-not-run posture, where an unrunnable check is never
  green.
- Rollback: the probe writes only inside its own scratch repository, so deleting that directory
  reverts the run entirely; the record is one commit to back out.

# Notes

- **Discharged 2026-08-12**: the probe ran, two legs; the record and raw outputs are
  `docs/probe/D7-headless-probe-2026-08-12.md` and its siblings. Headless verdicts: limbs (a)
  capability, (b), (c) all PASS at harness 2.1.224, with the registration finding (repo-level
  agent definitions not loaded headlessly; the `--agents` route works) and the one-source rule
  it implies. The substrate choice is the successor record's, per ADR-0003/D7.


- This is the chain's first real story, so it is also what makes reverse coverage non-vacuous:
  before it, `harness/chain_graph.py` had no cited Decision to find.
- The other non-superseded Decisions across ADR-0001, ADR-0002 and ADR-0003 currently read
  UNCOVERED, which is the check reporting the true state of the decomposition rather than a
  defect in this story.

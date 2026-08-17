---
id: STORY-0004
title: The postcondition loader: examiner material pinned, and no verdict before red and green
deps: []
labels: [chain]
sensitive_files: []
status: draft
adr: ADR-0001
decisions: [D3, D4]
group: A
---

# Problem / Context

Postconditions, their configuration, and their fixtures have no pinned resolution, and nothing refuses an undemonstrated postcondition. Both judged-tree violations D3 names are already measured in the design.

Grounding: `docs/adrs/ADR-0001-advancement-re-derived.md`, D3 and D4. Stub depth per the walkthrough's proximity rule—dep
edges and scope now, full spec when the work is imminent.

# Proposed approach

A loader resolving postconditions from a pinned out-of-tree location; refusal (could-not-run) of any postcondition lacking its red and green fixtures; the examiner-pinning test.

# Scope and non-goals

In scope:

- the loader, the pinned layout, the pinning test

Out of scope:

- the advance scripts themselves (STORY-0005)

# Acceptance criteria

Story-specific criteria—each dischargeable by a named check:

- [x] an undemonstrated postcondition's verdict reads could-not-run—verified by `the loader's known-bad fixture (fixtures absent)`, which is `harness/fixtures/loader_test.py`'s `missing-red-fixtures` and `missing-green-fixtures` cases: each removes one fixture directory and requires exit 2 naming both the postcondition and the limb that is absent. Three neighbouring cases carry the rest of D4—`red-passes` (the known-bad tree the postcondition does not fail: exit 1, detection power absent), `green-fails` (the known-good tree it does not pass: exit 1), and `demonstration-exit-2` (a limb outside the 0/1 contract: exit 2 naming the observed code)
- [x] a verdict does not change when only the judged tree's copies change—verified by `the examiner-pinning test named in ADR-0001's Falsification section`, which is `harness/fixtures/loader_test.py`'s `judged-tree-shadow` case: the loader runs with a judged git repository as its working directory while that repository holds a same-named, well-formed postcondition printing a different marker, and the pinned examiner must be the one that ran; the shadow is then changed again and the exit code must be identical. Its converse limb points `pinned_root` at the judged tree's own copy and requires exit 2, so the shadow cannot be reached by relocating it either

Anti-weakening contract—the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

- Risk: pinned-path layout diverges from the machine-hardening checklist—mitigation: contained to new files and the named check until wired.
- Rollback: revert the story's commits; every court named here fails closed on absence.

# Notes

- Allocated by the 2026-08-12 decision-coverage triage (docs/adrs/coverage-triage-proposal.md),
  split option: one `adr:` per story.
- Discharged 2026-08-12 on `feat/chain-loader`: `harness/chain/loader.py` (the chain runtime's
  first module) and its 20-case fixture `harness/fixtures/loader_test.py`, wired into
  `scripts/check.sh`, with `pinned_root` added to `.claude/chain/profile.toml`. The layout the
  loader defines is `<pinned_root>/postconditions/<name>/` holding `run`, an optional `config/`,
  and `fixtures/red/` plus `fixtures/green/`; `run` is invoked as `run <tree>` with its own pinned
  directory as the working directory and every `GIT_*` variable dropped from its environment, so a
  postcondition resolving anything relatively reaches pinned material and a `GIT_DIR` exported by
  a hook or a seam cannot redirect it onto the caller's repository. The judged-party prohibition is
  a filesystem walk for `.git` at and above the pinned root rather than a question put to git,
  because the environment the pinning defends against is the same environment that would answer it.
- The loader itself is NOT on the commit path and its fixture is, which mirrors how the story
  graph's checker was held back until its triage closed. `pinned_root` names
  `/var/lib/discipline-chain/`, the machine-hardening checklist of `docs/sdlc-chain-design.md` §4.3
  creates it, the checklist has not run on any machine here, and the loader VOIDs while it is
  absent—so wiring the loader today would block every commit rather than report a defect. It wires
  the day the root exists. Ownership and mode of that root the loader does not check, and says so:
  a root-ownership assertion would fail every machine today and would be edited out, so the
  property rests on the path being outside the agent's tree and on nothing else until the
  checklist runs.
- `scripts/profile-check.sh` is deliberately NOT extended. A profile with no `pinned_root` is a
  sequencer that must refuse to start, which is ADR-0003/D5's obligation and STORY-0011's work; the
  loader already VOIDs on the absence, so nothing is fail-open in the meantime, and requiring the
  key in the profile court would take that story's decision early and in the wrong file. The
  boundary is recorded beside the key in the profile.
- Red-first: the suite was observed against a stub loader that admitted everything it was asked
  for—17 of 20 cases failed. The three that passed passed for the wrong reason, and the stub is
  what shows it: they are the cases whose expected verdict is loadable, and an always-admits
  loader satisfies them, which is D4's own argument that an always-passing fence and a working one
  are indistinguishable from outside. Their discriminating power is against a loader that refuses
  well-formed material, and `judged-tree-shadow` is what makes one of them discriminate on which
  examiner ran.
- The anti-weakening contract holds by measurement rather than assertion: the fixture is a net add
  of 20 cases, the change introduces no suppression and no skip marker, and no existing assertion
  is touched. Three mutations were run with the mutant observed executing rather than merely
  reported killed—the working-tree walk neutered (killed by `pinned-root-in-worktree` and by
  `judged-tree-shadow`, whose converse limb then resolved the shadow and demonstrated it), the red
  requirement inverted to accept exit 0 (killed by `red-passes` and by all three loadable cases),
  and the both-fixtures requirement deleted (killed by `missing-red-fixtures` and
  `missing-green-fixtures`). The third mutation is why those two cases assert the state and not
  only the exit code: without the requirement the loader runs the postcondition against a
  directory that does not exist, the run exits 2, and could-not-run comes back carrying the
  postcondition's name—so exit 2 naming `demo` survives the mutation and exit 2 naming
  "'demo' has no red fixture" does not.
- Merge review returned FIX_NEEDED with five findings, all taken in a second commit and each
  reproduced before it was fixed. Two symlink shapes read LOADABLE with the judged tree's own
  examiner running: a `pinned_root` symlinked into a subdirectory of a judged repository, and a
  clean root whose `postconditions/` is a symlink into one. The first is the narrower hole the
  review reported—a symlink naming the repository's own root was already refused, because the
  first probe of the walk resolves through the link and meets `.git` immediately, and one shape
  being caught by accident is what let the other read clean. The remedy is to resolve the root
  before deciding and to require every resolved material path to sit under the resolved root.
- A `PermissionError` from an unreadable ancestor escaped as a traceback, and an uncaught Python
  exception exits 1, which is the code for a failed demonstration—ADR-0003/D2's inversion, a
  broken instrument read as a fact about the story. Measured firing at the `is_dir()` probe on the
  declared root rather than inside the path walk, so the guard is a net around every filesystem
  read on the resolution path rather than a wrapper on the loop where it was reported; a guard at
  the reported site would have left the measured shape open. Fixtures are now demonstrated against
  a copy rather than in place, because a postcondition that writes into the tree it judges was
  editing the evidence every later demonstration is judged by.
- Two of the review's prescriptions were not followed literally, and each departure is a case
  rather than an opinion. A walk from each material path would refuse a fixture tree that is
  itself a git repository, which is exactly the shape a postcondition over a tree's porcelain
  needs; `fixture-is-a-repo` pins that, and running the prescribed remedy as a mutation turns that
  case red while containment closes both measured escapes. And `.claude/chain/profile.toml`'s
  three spaced em dashes were not introduced by this story—they date from STORY-0003's commit,
  measured by diffing the block—but they are closed here anyway, since the file's style is the
  point rather than the authorship.
- The review's other value was a survivor it did not name. Adding the two symlink cases left
  `candidate.resolve()` on the root unpinned: the mutation dropping it kept the suite at 26 of 26,
  because containment refused the escape for the wrong reason. What that resolution actually buys
  is the LEGITIMATE symlinked root—a stable path pointing at a versioned release directory, and
  any machine whose temporary directory is itself a symlink—so `root-symlink-legitimate` was added
  and the mutation is killed. Nine mutations now run: the working-tree walk neutered, the red
  requirement inverted, the both-fixtures requirement dropped, the working directory set to the
  judged tree, the root resolution dropped, the containment check neutered, the fixture copy
  dropped, the OSError net removed, and the rejected alternative fix installed. All nine killed,
  27 cases.

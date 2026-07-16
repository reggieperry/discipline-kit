---
id: <ID>              # matches the filename stem — story files are stories/<ID>-<slug>.md
title: <one imperative line — "Add rate limiting to the request handler">
deps: []              # story ids this depends on, e.g. [0038, 0041]; empty list when independent
labels: []            # free-form tags, e.g. [refactor, gate, docs]
sensitive_files: []   # paths that need extra care — auth, migrations, shared-hot files, anything capital-touching
status: draft         # draft | ready | handed-off | closed
---

<!--
  A story is a work spec: the prose parent of the claim its acceptance criteria will pre-register.
  Fill in every section. Delete the guidance comments as you go; leave no <...> placeholder behind.
  Score the finished spec against the tightness rubric before you move status to `ready` — a story
  that names its files, its out-of-scope boundary, and atomic acceptance criteria costs the
  implementing agent far less exploration than one that gestures.
-->

# Problem / Context

<!--
  State the problem in prose: what is wrong or missing today, and why it is worth changing now.
  Then GROUND it against HEAD. Every claim you make about current behavior points at the real code
  it concerns with a file:line reference read from the working tree — not recalled from memory.
  Verify each reference before you write it (open the file, confirm the line); a stale path or a
  drifted line number sends the implementer to the wrong place and quietly widens the work.
-->

*What is the problem, and where does it live?* — one or two paragraphs.

Grounding against HEAD:

- `path/to/file.ext:120` — <what this line does today and why it is part of the problem>
- `path/to/other.ext:44–58` — <the behavior this range currently has>

# Proposed approach

<!--
  Describe the intended change concretely. Name the files and functions you expect to touch, so the
  agent reads them directly rather than discovering them. Point at a reference pattern to mirror —
  a sibling module, a prior change of the same shape — so conventions are inherited, not reinvented.
  This is a proposal, not a contract; the acceptance criteria below are the contract.
-->

*How should the problem be solved?* — the shape of the change, the files it touches, and a pattern to mirror.

# Scope and non-goals

<!--
  Draw the boundary. Name what this story explicitly does NOT touch, so scope cannot widen
  opportunistically mid-implementation. If the work was peeled off a larger unit, say what stayed
  behind and why. If a collaborator or consumer does not exist yet, name it and mark it out of scope.
-->

In scope:

- <the specific change this story delivers>

Out of scope:

- <what an implementer must not touch, even if adjacent and tempting>

# Acceptance criteria

<!--
  These criteria become the pre-registered claim the loop parks before any code is written, so each
  one must be atomic and verifiable: a named test, an observable assertion, a file shape, a command
  that passes. Vague criteria ("should work correctly") let the implementer invent what counts as
  done. Name the check that discharges each criterion; a criterion no check can recompute is a
  design error, and catching it here — before the work — is the point of writing the story first.
-->

Story-specific criteria — each dischargeable by a named check:

- [ ] <observable outcome> — verified by `<the exact command or test that shows it>`
- [ ] <observable outcome> — verified by `<the exact command or test that shows it>`

Anti-weakening contract — the change does not weaken the suite versus the merge-base. Confirm each before hand-off:

- [ ] The assertion count is not reduced versus the merge-base.
- [ ] No new suppressions are introduced versus the merge-base.
- [ ] No new skipped tests versus the merge-base.

# Risks and rollback

<!--
  Name what could go wrong and how the change comes back out. Give special attention to anything
  listed in `sensitive_files` — the extra care those paths need, and the blast radius if they break.
  State how to revert cleanly: a single commit to back out, a flag to flip, a migration to reverse.
-->

- Risk: <what could break, and how likely> — mitigation: <how it is contained>
- Rollback: <how the change is reverted if it does not hold>

# Notes

<!--
  Anything a reader needs but that did not fit above: open questions, links to prior discussion or
  a superseded story, the authoring order if part of this was adapted rather than written fresh, and
  a "memories consulted:" line naming any memory that materially shaped the spec. Keep it spare —
  this section is for what the other five could not carry, not a place to restate them.
-->

- <open question, reference, or authoring note>

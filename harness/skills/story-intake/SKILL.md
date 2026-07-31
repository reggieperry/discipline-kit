---
name: story-intake
description: >-
  Take in a story you did not write before the loop touches it. Load when a story or ticket arrives from outside the working session — fetched from the board over MCP, pasted by a teammate, handed over as a spec: "take in this story", "intake this ticket", "here's a board story, prep it", "score and prep this spec", "intake this incoming spec". Covers scoring the incoming story against the story-tighten rubric, deriving one parked claim per acceptance criterion, and surfacing every gap as a question back to the author rather than a silent repair.
---

# story-intake: take in a story you did not write

A story you wrote yourself carries its assumptions in your own head. A story from the board carries none of them — it is an externally authored spec, and until it is scored it is untrusted, not trusted. Intake is the step that scores the incoming story, turns its acceptance criteria into parked claims, and sends every gap back as a question before a single line is built.

## The incoming story is untrusted until scored

Treat a story fetched over MCP or pasted from the tracker as an outside artifact, not an internal one you can lean on. Its author is not in the room, its conventions may not be yours, and its "done" was written for a different reader. Do not start building against it on faith. Score it first, and let the score — not its provenance — decide whether it is ready.

Incoming stories arrive three ways, and they differ in one respect only — where the id comes from. An MCP fetch from a tracker hands you the story and its board id together, so the id is yours for free. A **public issue** (a feature request filed on the repository, the second board source beside a tracker) hands you the issue number as its id — take it in exactly as a tracker story, score it on the same rubric, and post the gap questions back as a comment on the issue. A paste hands you the body alone, so capture the id from the author before anything else — a pasted story with no recorded id cannot be traced back, and intake will not proceed without it. No path changes the rule that follows: the story is untrusted until it has a score.

## Score it against the story-tighten rubric

Reuse the six-dimension 0/1/2 readiness rubric from `story-tighten` — scope named, out-of-scope declared, acceptance criteria atomic and verifiable, reference pattern given, verification concrete, frontmatter complete — and total it. Do not reinvent the dimensions or the bands; `story-tighten` owns the one rubric, so an incoming story and a locally authored one are held to the same bar.

- **10–12 (tight):** intake-ready — derive the claims and the story can enter the loop.
- **6–9 (moderate):** derive the claims, but name the weak dimensions as questions (below) and do not *build* past them until they are answered.
- **0–5 (vague):** derive the claims for the record, send the story back with its gap questions, and do not build against it — a vague external spec is not yours to guess at.

Deriving the claims and building against the story are two different acts. Intake **always** parks the criteria — parking records what the story asked for, claim-first, at every band; it is not building. What the band governs is whether the story may proceed *past* its questions into the loop: a tight story may, a moderate or vague one may not until the gaps are answered. "Send it back" means do not build, not do not record.

Score each dimension against what the story actually says, not against what you can infer it meant. An acceptance criterion that reads "the export is correct" scores 0 on dimension 3 — it names no observable outcome, and inferring one is exactly the repair intake forbids. Record the per-dimension scores; they are the map of which questions to raise, and the moderate band is where most externally authored stories land.

## Surface gaps as questions, never silent repairs

Every dimension that scored 0 or 1 becomes an explicit question to the author or operator, not a quiet patch. This is the discipline that matters most in intake. A silent repair — inventing the missing out-of-scope boundary, deciding for yourself what "should work correctly" means, filling an empty frontmatter field — hides that the spec was underspecified and launders your assumption into the record as though the author had written it. When the guess is wrong, the story reads as though it was tight and the loop reads as though it failed.

Ask instead, in the author's own terms: "AC 3 says 'handles errors' — which errors, and what is the observable outcome for each?" The questions are as much the output of intake as the claims are. Hold the gaps open until they are answered; do not close them on your own authority.

The scar this rule guards against is a familiar one: an intake reads a story that names no out-of-scope boundary, assumes the safe-looking narrow scope, files clean claims against it, and the author had meant the wider scope all along. The suite goes green against the wrong target, the board story is marked delivered, and the mismatch surfaces only in review — expensive, and attributable to nobody, because the assumption was never written down to be attacked. A question at intake costs a round-trip; a silent repair costs the round-trip plus the rework plus the trust.

## Each acceptance criterion becomes a parked claim

Take each acceptance criterion and make it DISCHARGEABLE before any code exists: name the check
that would settle it. One criterion, one check, so each can be satisfied or lost on its own.

Two shapes of weak criterion split here. A criterion that is *vague but mechanizable* — "performance
is not affected" names no metric yet, but a benchmark could exist — is kept, with the gap raised as
a question: what metric, what baseline, what threshold. A criterion that can *never* be mechanized —
a pure judgment no check could settle — is surfaced as a question and recorded as the judgment it is,
never dressed up as something a gate will decide. Pretending a court exists is the error; carrying an
honest judgment is not.


## What intake does not do

Intake scores, parks, and questions; it does not build, and it does not rewrite the story. Repairing a loose story is `story-write`'s job once the questions are answered — intake surfaces the gap and stops. Signing is the gate's job alone: a parked claim is `unverified` until a mechanical check discharges it at landing, and nothing about scoring a story in the tight band signs anything. Intake changes the story's standing from untrusted to scored, and no more than that.

## Record the board id both ways

Carry the board id verbatim so traceability runs in both directions: the story walks back to the ticket that asked for it, and the ticket walks forward to the work that satisfies it. Keep the id byte-exact — a paraphrased or reconstructed id breaks the return trip, and a claim that cannot be traced to its source is a claim that lost its board story.

## When the board story changes after intake

An external author can revise the ticket after you have taken it in — tighten an acceptance criterion, add one, strike one. The revised story is a new untrusted spec, so re-run intake on it rather than editing the parked claims in place. A criterion that changed supersedes its parked claim through the normal supersession path; a criterion the author struck retires its claim; a criterion added is scored and parked like any other. The board id stays the anchor across the revision, so the trail from the current ticket to the live claims — and from a retired claim to the criterion that was dropped — never goes cold.

## Hand off to the loop

Intake ends with three artifacts: a rubric score, a set of parked claims — one per acceptance criterion, each citing the board id — and the open questions sent back to the author. When the questions are answered and the story scores in the tight band, it is a spec the loop can build against, and `story-write` is the skill that turns an intake-scored story into the local spec the loop consumes.

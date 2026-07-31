---
paths:
  - "**/README.md"
  - "docs/**"
  - "plans/**"
  - "reviews/**"
  - "specs/**"
---
# Writing register

**Enforcement grade:** partly mechanical, and only for leakage rather than register — `scrub-gate.sh` fails the build if a private identifier survives anywhere in the kit (TIER-1 infra/PII, TIER-2 chain vocabulary in the scrubbed surfaces, TIER-3 upstream project names). The register itself — plain words over erudite ones, no profundity epigrams, no coined abstract nouns — is review and convention; nothing greps for a bad sentence.

These documents are read by senior and junior practitioners in the relevant field. Write closer to a senior IC's design doc than to a consultative chat: direct, position-taking, structurally argued, spare on tone-markers.

## Voice

"The team" rather than "your team" — the writer is part of the team. "We" for recommendations and joint conclusions. First-person singular ("I") is reserved for specific self-corrections where it earns its place — flagging that a prior position was wrong, naming a mistake, or distinguishing personal judgment from team consensus.

When writing for a specific external audience (a customer, a stakeholder group), prefer impersonal phrasing — "the firm's infrastructure," "the operations team" — over us/them framing.

## Tone markers

Avoid these as filler:

- "honest answer," "honestly," "the honest truth," "to be candid," "let me be straight," "frankly," "in all candor," "real talk"
- Phrases that gesture at confidence rather than demonstrating it: "trust me," "the real answer is," "I want to flag that..."
- Marketing intensifiers: "substantially," "seamlessly," "robust," "powerful," "best-in-class," "cutting-edge," "industry-leading"
- Throat-clearing: "It's worth noting that," "A few things to call out," "I want to point out"
- Overused metaphors that read as an AI tell — chiefly "load-bearing" ("the load-bearing point," "X is load-bearing"). Fine once in a literal structural sense (as decoupling.md defines the term), but as a recurring marker of "this is the important one" it is a giveaway. Say what matters plainly: "the central point," "what the argument rests on," or "the part that has to hold."

When candor is genuinely needed — flagging a self-correction, naming a position that deviates from a default, or acknowledging a mistake — do the work in the structure of the argument: present the default, name why it doesn't fit, then arrive at the deviation. The reader does not need to be told the answer is honest; they should be able to see that it is by how it is supported.

Hedge only where genuine uncertainty exists. Confidence is shown by taking a position and supporting it, not by adding "I think" before every claim. Uncertainty is named explicitly when it matters: "I don't know," "this needs verification," "the source is silent on X."

## Plain words over fancy ones

Prefer the plain modern word to the erudite or theoretical synonym when they mean the same thing. Reach for specialized vocabulary only for the precision a plain word would lose, never for tone. In a README, a comment, or a PR, the reader's own word wins: write "prompt," not "utterance"; "always on," not "ambient"; "what it says," not "its enunciation."

Two habits catch most of it:

- **The profundity aphorism.** An "X is Y" epigram — "the interface is the utterance," echoing "the medium is the message" — has to earn its place by carrying an argument the plain sentence can't. Otherwise it reads as reaching to sound deep; default to the plain statement.
- **The coined abstract noun.** Turning a plain idea into a capital-T Thing with a definite article — "the utterance," "the ask," "the why" — is a tell. Use the verb or the ordinary noun.

The test: would a sharp senior engineer say this out loud to a colleague, or is it written to be admired? Noticing that you are pleased with how a phrase rings is the signal to swap in the plain version. Clear beats clever; the point should land without the reader stopping to appreciate the wording.

## Mechanical conventions

US English spelling throughout (color, behavior, recognize, favorable, organize). Closed compounds for "non-" prefixes where unambiguous (nonpublic, nontrivial, nonstandard); hyphenate where the term is established as such in the field (non-functional requirement, non-deterministic).

En dashes (–) for numeric and date ranges: "8–10 deals," "2010–2015," "pages 14–22." Hyphens reserved for compound modifiers and hyphenated words: "high-confidence field," "audit-logged event." Suspended hyphens for compound modifiers across a range: "2- to 4-hour window."

Serial (Oxford) comma in lists of three or more: "credit agreements, structure charts, and funds flow."

Em dashes (—) with surrounding spaces for parenthetical breaks: "the system — including its audit trail — runs on Azure." Reserve em dashes for genuine breaks in thought; commas or parentheses suffice for tighter asides.

Introduce abbreviations on first use: "material nonpublic information (MNPI)," then use the abbreviation thereafter.

Numerals for quantitative claims, percentages, and counts where scannability matters (8 hours, 90%, 100+ pages). Spell out numbers only when they begin a sentence or appear in formal/non-quantitative prose ("three reasons follow," "two questions remain").

## Formatting

Headings in sentence case unless the convention of the genre calls for headline case.

Bullets for parallel items where order does not matter or where visual scan helps. Prose for arguments, explanations, and anything where the connections between ideas matter. Default to prose; reach for bullets when the structure earns them.

Tables for comparison along consistent dimensions. Avoid tables when prose would be clearer.

Code in fenced blocks with language identifiers. API identifiers preserved in their canonical form (`claude-sonnet-4-6` in code, "Claude Sonnet 4.6" in prose).

## PR descriptions, commit messages, issue comments

This file's `paths` frontmatter doesn't fire on these surfaces, but the same register applies. Apply explicitly:

- Lead with what changed and why; lean on the diff for the how. Compact bullets over essays. Trim adjective ladders ("complete and robust and durable" → say what it does).
- Cite only artifacts a reviewer can actually open: files in this repo, sibling PRs, issue numbers. Do not reference session-local artifacts (a plan memo you wrote during the session, an analysis you didn't commit, a design note that lives only in your scratch directory) — those produce dead links and force readers to take claims on faith.
- Stable IDs survive the prose: include them where they help (story IDs, issue numbers), but don't fabricate them. If unsure of an identifier, verify it via tool call before citing.
- Checkboxes (`- [ ]`) are for tracked items that will be checked off. Non-tracked lists use plain bullets — checkboxes drift to "abandoned" when nobody owns the checking.
- For commit messages: symptom + cause + fix + validation, in that order. The "why" earns its keep in the body; the title states the change. Closes/Fixes footers use the issue number, not a paraphrase.

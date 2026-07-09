---
name: feedback-credibility-gestures
description: "Cut \"real\" and similar credibility-claim phrasings — gesture at trust instead of demonstrating it"
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

Don't write phrases that assert credibility instead of demonstrating it. "The references are real," "the project's structure is real," "each edge is a real dependency," "the honest answer is," "trust me," "this is genuinely useful" — all in the same family. They telegraph the opposite of what they intend. A reader who sees "the references are real" starts wondering why they had to be told.

**Why:** This pattern recurs because LLM training rewards reassurance, but it does the opposite of what's intended — it reads as defensive throat-clearing. It's also banned in [[reference-voicing-document]] under "phrases that gesture at confidence rather than demonstrating it."

**How to apply:** Before writing any sentence containing "real," "honest," "genuinely," "actually" as a credibility marker, delete the qualifier. If the claim was unsupported without it, the qualifier was hiding the weakness — strengthen the claim instead. The same goes for "trust me," "in fact," "to be clear," "I want to flag that," "I should mention" — these are all variants of the same anti-pattern.

When the urge to reassure surfaces, the right response is to make the argument itself carry the credibility — show the work, name the source, take the position. Adjectives don't earn trust; structure does.

Related: [[reference-voicing-document]], [[feedback-checkboxes-vs-bullets]] (also a register/restraint pattern).

---
paths:
  - "**/*.go"
  - "**/*.sh"
  - "**/*.py"
  - "**/*.scala"
  - "**/*.sc"
---

# Complexity and module design

The discipline of keeping a system understandable and cheap to change. Source: John Ousterhout, *A Philosophy of Software Design* (2nd ed). Complexity is the one thing to fight; every rule below is a move against it.

> See `craft-abstraction.md` for the specification-and-encapsulation theory underneath deep modules, `craft-refactoring.md` for removing complexity from existing code, `craft-documentation.md` for the comment and doc-comment discipline, and the active language overlay (`go-*.md`, the `python-*` and `scala-*` sets) for the language-specific expression of these rules.

## What complexity is

- **Treat complexity as anything structural that makes the system hard to understand or change** — not feature count, not lines of code. Judge a design by how hard the *next* change is.
- **Hunt its two causes: dependencies and obscurity.** A dependency is code that can't be understood or changed in isolation; obscurity is important information that isn't obvious. Every design move either reduces one or adds one.
- **Watch for the three symptoms: change amplification** (one decision forces edits in many places), **cognitive load** (how much a developer must hold in their head), and **unknown unknowns** (it isn't even clear what must change). Unknown unknowns are the worst — design so that the system is *obvious*.
- **Complexity is incremental — sweat the small stuff.** It accumulates from many small dependencies and obscurities, so adopt zero tolerance: a little added complexity now is a debt paid forever.

## Strategic, not tactical

- **Make a great design that also works, not working code that you'll clean up later.** Tactical programming (just ship the feature) is how systems rot; the cleanup never comes.
- **Invest continuously — roughly 10–20% of effort — in design.** Small, constant improvements; the payoff arrives in months, not years. Avoid the big up-front design (waterfall) and the never (tactical) alike.
- **When you modify existing code, leave the design as if it had been built with this change in mind from the start.** Resist the minimal local patch that buys a feature at the cost of a new special case.

## Deep modules

- **Make modules deep: a simple interface over a powerful implementation.** The interface is the cost a module imposes on the rest of the system; the functionality is the benefit. Maximize benefit, minimize interface.
- **Reject classitis — more, smaller classes is not better.** Many shallow modules each add interface and boilerplate; the system-level complexity is the sum of all those interfaces. Depth beats length: make functions deep first, short second, and never split a function into conjoined halves that can only be understood together.
- **It is more important that a module's interface be simple than that its implementation be simple** — most modules have more users than developers, so push the suffering onto the implementer.

## Information hiding

- **Make each module hide a design decision** — a data structure, an algorithm, a file format, a protocol — so that decision can change without touching anything else. Hiding information is what makes a module deep.
- **Treat information leakage as a top red flag: the same knowledge embedded in two modules.** It can leak through an interface or, worse, through a back door (two modules that both know a file format). When you see it, reorganize so the knowledge lives in exactly one place.
- **Avoid temporal decomposition** — structuring modules by the order operations run (read, then parse, then write) rather than by the knowledge each needs. It is the most common source of leakage; design around knowledge, not time.
- **Hide expected change behind an abstraction.** Think about what is likely to change and encapsulate it so the change stays local.

## Generality and special cases

- **Make modules somewhat general-purpose: functionality for today's need, interface general enough for more.** Over-specialization is the single greatest cause of complexity; a general interface is usually simpler, deeper, and smaller than the special-purpose one.
- **Eliminate special cases in code.** Design the normal path so it handles the edges with no extra `if` (an empty selection rather than a "no selection" flag). Fewer special cases means simpler, faster, more obvious code.
- **Push specialization to the top or bottom of the stack**, keeping the middle layers general — the way device drivers isolate device-specific code below a general interface.

## Layering, pulling down, and errors

- **Give each layer a different abstraction.** Adjacent layers with the same abstraction signal a problem. The sharpest symptom is the **pass-through method** (does nothing but call another with the same signature) and the **pass-through variable** (threaded through methods that don't use it — prefer a shared context object).
- **Pull complexity downward.** When you hit unavoidable complexity, handle it inside the module rather than exporting it as configuration parameters or exceptions for every caller to deal with.
- **Define errors out of existence.** The best exception handling is none — redefine the operation so the error case becomes normal (an `unset` that succeeds when the variable is already gone). Where you can't, mask the error low or aggregate handlers high. (Language-specific expression: the overlay's error rules.)

## Obviousness, names, and comments

- **Design it twice.** Sketch two genuinely different approaches for any significant interface before committing; the comparison teaches you the design.
- **Choose names that are precise and consistent.** A vague or overloaded name is a latent bug. If a name is hard to pick, the underlying thing probably lacks a clean design.
- **Comments are governed by `craft-documentation.md`** — describe what isn't obvious from the code (units, invariants, who-frees-what, rationale), never restate it; write the interface comment first, and treat a long or hard-to-write one as the canary for a shallow or muddled abstraction.

## Red flags (stop and redesign when you see one)

Shallow module · information leakage · temporal decomposition · overexposure (common feature forces awareness of rare ones) · pass-through method · repetition · special-general mixture · conjoined methods · comment repeats code · implementation detail in an interface comment · vague name · hard-to-pick name · hard-to-describe (the doc must be long to be complete) · nonobvious code.

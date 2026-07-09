---
name: feedback-aposd-module-design
description: "Seven rules from Ousterhout's *A Philosophy of Software Design* 2e — judge modules by depth (functionality / interface surface), kill pass-through methods, pull complexity downwards, build general-purpose interfaces, decompose by knowledge not by execution order, define errors out of existence, treat unwritable interface comments as a complexity sensor, push back on vague names, design every nontrivial module twice. Operational vocabulary for [[feedback-simplicity-principle]]."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

Ousterhout's *A Philosophy of Software Design* gives "as simple as possible but no simpler" ([[feedback-simplicity-principle]]) a measurable definition: **complexity = obscurity + dependencies**, weighted by edit frequency, manifesting as change amplification, cognitive load, and unknown unknowns. The rules below convert that frame into review-time checks for common codebase shapes (web/API services, orchestration spine, persistence layer).

**Why:** "keep it simple" alone doesn't give vocabulary for *judging* whether a particular module is simple enough. Ousterhout's red flags (Shallow Module, Pass-Through Method, Special-General Mixture, Hard to Describe, Hard to Pick Name) are the diagnostic surface that turns the principle into a checklist.

**How to apply:** at PR review time, walk the rules below against each new or substantially-changed module. Most relevant when adding a new router, a service-layer file, or any new class in the core domain layer.

---

## 1. Judge every module by its depth: `functionality_hidden / interface_surface`

**Rule.** A deep module exposes a small interface that hides substantial implementation. A shallow module's interface mirrors what it wraps. Shallow modules are net-negative — the interface cost without the encapsulation benefit. Small ≠ simple.

**Why.** Ch 4 "Modules Should Be Deep" + the "Shallow Module" red flag. *"Modules should be deep: their interfaces should be much simpler than their implementations."*

**Trigger.** Reviewing a new service-layer file; any time a class is added under the orchestration layer whose every method is one DB call; node/handler wrappers that just rename arguments and forward.

**How to apply.** Before merging, sketch the rectangle — how many public methods/attributes does the module expose, how much hidden state/logic does it cover? If the interface roughly equals the implementation (a service whose only methods are `get_x`, `update_x`, `delete_x` against one table), either inline into the caller or merge into a deeper neighbor. Don't reach for "a class per concern" by default.

---

## 2. Eliminate pass-through methods and pass-through variables

**Rule.** A method that just forwards args to another method with a near-identical signature is a sign two modules share a responsibility neither owns cleanly. A variable threaded through 3+ frames as a function argument is a pass-through variable — introduce a context object instead.

**Why.** Ch 7 "Different Layer, Different Abstraction" + "Pass-Through Method" / "Pass-Through Variable" red flags. They add interface surface without adding functionality and couple the layers together.

**Trigger.** The route → service → repository chain; node/handler wrappers that just call a helper; pass-through arguments like `correlation_id`, `actor_id` threaded through every function call.

**How to apply.** When you see `return other.same_method(*args)`, pick one: expose the lower layer directly, push real work into the wrapper, or merge the two layers. For pass-through variables threaded across 3+ frames, introduce a request-scoped dependency (a `RequestContext` model injected via dependency injection) rather than threading them via signatures or globals.

---

## 3. Pull complexity downwards — the module developer suffers so its users don't

**Rule.** Before adding a `Settings` field or constructor argument, ask: can I compute a sensible value from observed behavior, or pick a strong default? Only export a knob when the caller genuinely knows more than this module ever will.

**Why.** Ch 8 "Pull Complexity Downwards." *"Most modules have more users than developers, so it is better for the developers to suffer than the users."* Configuration parameters and "let the caller decide" exceptions are the chief offenders.

**Trigger.** Designing an external-service adapter signature, an orchestration claim/heartbeat API, any schema callers instantiate often, retry-policy decisions in a gateway wrapper. Tension to manage with [[feedback-pr-review-patterns]] Pattern 3 (config-over-constants).

**How to apply.** The two rules together: *export* a knob only when an operator will tune it at runtime ([[feedback-pr-review-patterns]] Pattern 3); *don't invent* the knob when a default would do (this rule). The deciding question: would a different value of this knob change observed behavior in production? If yes, export it. If "no, we just want it configurable for testing," default it strongly and override in tests via monkeypatch.

---

## 4. Build modules somewhat general-purpose — interface reflects the abstraction, not today's caller

**Rule.** Specialization in the interface (`backspace(cursor)` vs `delete(range)`) leaks the caller's vocabulary down and creates information leakage. Push specialization up to the application boundary or down into a driver, not into the middle layers.

**Why.** Ch 6 "General-Purpose Modules are Deeper." Ousterhout calls over-specialization "the single greatest cause of complexity." The "Special-General Mixture" red flag fires when one class mixes general mechanism with specialized handlers.

**Trigger.** Designing node/stage interfaces, an extractor protocol, a parser, anything one stage asks of a helper today that a different stage might ask of tomorrow.

**How to apply.** When sketching a new module, ask Ousterhout's three questions: what's the simplest interface that covers all my current needs; in how many situations will this method be used; is the API still easy to use for today's caller. If a method has one caller and its name encodes that caller's intent, refactor to a more primitive operation and move the intent up.

---

## 5. Don't decompose by execution order — decompose by knowledge

**Rule.** Modules named "loader," "parser," "writer," "validator" are red-flag verbs implying ordering. If two modules share knowledge about a format or schema, merge them or pull the shared knowledge into a third module both call.

**Why.** Ch 5 §5.3 "Temporal Decomposition" + the matching red flag. Order matters in the application but shouldn't matter at the module boundary unless the stages genuinely hide different information.

**Trigger.** Drawing an ingestion pipeline boundary — chunker / embedder / persister. Designing the orchestration spine vs the stage handlers. Splitting a processing stage into "fetch context" + "call out" + "validate" modules.

**How to apply.** The orchestration spine is the legitimate place for time-ordering (it owns the sequence). Stage modules should be organized by *what knowledge they encapsulate*, not *when they run*. If two stages need the same domain concept, the concept lives in a third module owned by neither.

---

## 6. Define errors out of existence — most exceptions are an abdication

**Rule.** Each `except` block answers "does the caller have a meaningful action?" If yes, raise a domain exception (not the SDK exception) and aggregate handling at the request boundary. If no, mask at a low level. If the failure means the process is unsound, crash.

**Why.** Ch 10 "Define Errors Out Of Existence." The four techniques in priority order: redefine the operation so the error case is the normal case (Tcl's `unset` succeeds on missing keys); mask the exception in a low-level module (TCP retransmits); aggregate handlers (one top-level catch); crash for unrecoverable failures.

**Trigger.** Designing an external-service adapter (retryable vs terminal failures), the persistence layer (idempotency vs raise), the framework exception handlers, anywhere current code is dotted with `try/except` around individual calls.

**How to apply.** Refines [[feedback-security-when-writing-code]] rule 1 — error-message sanitization is the *what*; this is the *whether*. In review, count the `try/except` blocks in a new module. More than 2-3 is a smell that the abstraction is leaking; consolidate.

---

## 7. Comments and names as design diagnostics

**Rule.** Write the interface docstring **before** the body. If the docstring is drifting past ~4 lines, or starts naming internal collaborators, or you can't pick a precise name for a variable, that's design feedback — refactor the design, not the comment.

**Why.** Ch 12-15, specifically Ch 15 §15.3 "Comments are a design tool" + Ch 14 §14.3 + the "Hard to Describe" and "Hard to Pick Name" red flags. Long conditional implementation-leaking docstrings diagnose shallow modules. Vague names (`data`, `result`, `info`, `status`, `manager` outside loops) diagnose vague concepts.

**How to apply.** When a docstring requires "this method is called by X after Y has set Z," the boundary is wrong — that's leaked implementation. When a name needs the class prefix to make sense (`File.fileBlock`), drop the prefix. When two variables of "the same kind" carry different invariants (logical block vs physical block, raw vs URL-decoded), encode the distinction in the name or in distinct types — pair with [[reference-type-system-for-invariants]] rule 2 (`NewType`).

---

## 8. Design every nontrivial module twice

**Rule.** When the work is more than a day, write a one-paragraph "alternative design" — even a deliberately bad one — and compare. The act of contrast surfaces what makes the chosen design good.

**Why.** Ch 11 "Design it Twice." The investment is small; the design-skill gain compounds. Ousterhout argues most engineers don't do this because it feels wasteful; the contrast is exactly what gives you signal that the first design wasn't obvious-by-accident.

**Trigger.** Choosing an orchestration claim model (advisory lock vs row CAS vs queue framework); choosing a workflow state shape; picking a core domain record schema.

**How to apply.** In the PR description or ADR for any non-trivial change, include a "Considered alternatives" section. One paragraph each, with pros and cons. Pairs with [[feedback-demo-with-prod-risk]] — design-it-twice is how you tell whether the simpler design has actually painted into a corner.

---

## What's not in scope

- Ousterhout is hostile to TDD (Ch 19.4) — we explicitly disagree, GOOS is stronger evidence for our context, see [[feedback-tdd-listening]].
- Strategic vs tactical programming (Ch 3) — already covered by [[feedback-demo-with-prod-risk]] and [[reference-coding-methodology]].
- Implementation inheritance is suspect — already in [[reference-design-abstraction-lsp]] and [[feedback-oo-style]].
- Performance / critical-path design — deferred per [[feedback-demo-with-prod-risk]] until a real hotspot appears.

## Related memory

- [[feedback-simplicity-principle]] — the founding principle this memory operationalizes
- [[feedback-demo-with-prod-risk]] — the posture; rule 8 (design-it-twice) is how you check whether "simple" has hit a wall
- [[feedback-oo-style]] / [[reference-design-abstraction-lsp]] — module-boundary patterns Ousterhout sharpens
- [[feedback-pr-review-patterns]] — Pattern 3 (config-over-constants) interacts with rule 3 here
- [[reference-type-system-for-invariants]] — rule 7 (names as diagnostic) pairs with NewType for naming distinct invariants
- [[reference-sources-to-consume]] — APoSD is the priority short read

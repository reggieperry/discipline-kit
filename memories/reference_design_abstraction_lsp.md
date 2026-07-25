---
name: design-abstraction-encapsulation-substitutability
description: "Core design principles from Liskov 1974 (Programming with Abstract Data Types) and Liskov 1988 (Data Abstraction and Hierarchy). Operations characterize a type; representation is private; substitutability is behavioral, not just signature-shaped. Reference for design decisions and review."
metadata: 
  node_type: memory
  type: reference
  volatility: durable
---

The two Liskov papers (Programming with Abstract Data Types, 1974; Data Abstraction and Hierarchy, 1987) ground the data-abstraction view of design. Keep these on hand as the foundation. The principles below are how to apply them.

## Abstraction is the key to good design

A data abstraction is defined by its **operations** — what callers can do with objects of the type. The **representation** is private to the cluster (or class) that implements the type; callers cannot and should not depend on it. Implementations may differ in algorithm and performance; any correct implementation is acceptable to callers as long as it meets the spec.

When designing:
- Lead with operations and the spec they implement; postpone representation.
- A class that exposes its representation (public mutable fields, leaky getters that return internal collections) is not a data abstraction — it is a record. Records are sometimes fine for results of distinct function invocations, but they are not modules to design behavior around.
- Two independent implementations of the same abstraction must be substitutable from the caller's perspective. If they aren't, the abstraction has leaked.

## Locality is what makes systems tractable

Abstraction plus specification plus encapsulation gives **local reasoning**: each module can be implemented, understood, and modified one at a time. The implementer needs the spec, not other implementers' code. A using module needs the spec of what it calls, not the called code. Modification stays within one module unless the spec itself changes.

This is the central reason for the rule that the rep is private. Once any other module reads the rep directly, you've lost locality — that module now has to be consulted (and possibly rewritten) when the rep changes.

## Liskov Substitution Principle — behavioral, not shaped

From Liskov 1988: *"If for each object o₁ of type S there is an object o₂ of type T such that for all programs P defined in terms of T, the behavior of P is unchanged when o₁ is substituted for o₂, then S is a subtype of T."*

In practice this means subtyping requires three things together:
1. **Operations of the right names and signatures.** Necessary but not sufficient.
2. **Operations that do the same thing.** Same semantics, same invariants, same pre/postconditions.
3. **Same behavior under composition.** A program written against the supertype must continue to work when given a subtype.

`set` is not a subtype of `list`, and `list` is not a subtype of `set` — even though both have add/remove operations, the semantics differ (deduplication, ordering). `stack` is not a subtype of `queue` — same operation names (`add_el`, `rem_el`), opposite removal discipline.

**Subclass vs subtype is the distinction that matters.** Subclass is a linguistic mechanism for code reuse; subtype is a semantic claim about substitutability. They are independent. Using inheritance for code reuse without intending substitutability is a recurring source of confusion — Liskov calls this out explicitly.

## When to use inheritance, when not to

From Liskov 1988:
- **Implementation hierarchy** (inherit to reuse code) — does not add anything you couldn't already do with data abstraction. Often violates encapsulation by giving the subclass insider access to the superclass's rep. Prefer composition / delegation.
- **Type hierarchy** (subtype relationships) — the genuinely useful case. Used for incremental refinement during design, related types (variants of a common idea), polymorphism, library organization.

GOOS reinforces this: *"We view classes for objects as an 'implementation detail' — a way of implementing types, not the types themselves. We discover object class hierarchies by factoring out common behavior, but prefer to refactor to delegation if possible."* See [[feedback_oo_style]].

## How to apply

When designing a new type:
- Write the operations and a one-line spec for each before writing the body.
- If a representation choice would force callers to know about it, the abstraction is wrong; revise.
- Default to composition; reach for inheritance only when subtype substitutability is the actual relationship.

When reviewing code:
- If a class's rep leaks into callers (via getters that return mutable collections, public fields, or shared references), the leak is the bug — fix that, not the symptom.
- If a subclass overrides a method to throw `NotImplementedError` or to weaken a postcondition, the subclass is not a subtype. The hierarchy is wrong.
- If a class's operations have the right names but the wrong semantics for the supertype's contract, the class shouldn't claim that supertype.

## Cross-references

- [[feedback_oo_style]] — peers, Tell-Don't-Ask, context independence (GOOS).
- [[feedback_tdd_listening]] — how testing surfaces abstraction quality.
- [[feedback_refactoring_smells]] — code smells that signal broken abstraction.
- Source: Liskov, Programming with Abstract Data Types (1974); Liskov, Data Abstraction and Hierarchy (1988).

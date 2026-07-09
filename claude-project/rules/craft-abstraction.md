---
paths:
  - "**/*.go"
  - "**/*.sh"
  - "**/*.py"
  - "**/*.scala"
  - "**/*.sc"
---

# Abstraction, specification, and substitutability

The theory of data abstraction that makes modules safe to build and change independently. Sources: Barbara Liskov & Stephen Zilles, *Programming with Abstract Data Types* (1974); Barbara Liskov, *Data Abstraction and Hierarchy* (1987, the origin of the substitution principle).

> See `craft-complexity.md` for deep modules and information hiding (the same idea from the design side), the language overlay (`go-types.md`, the `python-*` and `scala-*` sets) for encoding these abstractions in the type system, and `craft-domain-modeling.md` for value objects and intention-revealing interfaces.

## An abstraction is a specification, not an implementation

- **Define every abstraction by what it does, not how — a specification separate from its representation.** A data abstraction is a set of objects characterized completely by the operations on them; the representation ("rep") is hidden behind those operations.
- **Permit many implementations behind one specification.** An implementation is correct if it provides the behavior the specification describes; correct implementations may differ in algorithm and performance and remain freely substitutable. The specification says what is important; everything else is free to change.
- **Encapsulate the representation so no other module can depend on it.** Using code calls operations and never touches the rep. This is what lets a module be reimplemented without breaking its callers — the practical payoff of abstraction.

## Encapsulation buys local reasoning

- **Reason about one module at a time, against specifications.** With encapsulation you can implement, understand, or modify a module knowing only its own spec, the specs of the modules it calls, and nothing about its callers — because callers depend on the spec, not the code, and callees are summarized by their specs. Specifications are far smaller than implementations, so this is an enormous saving.
- **Encapsulate the decisions most likely to change** — storage layout, data structures, machine or platform differences — so a change to that decision stays inside one module. A good design organizes itself around expected modifications.
- **Prefer enforced encapsulation over manual discipline.** Encapsulation guaranteed by the language (or by a checked boundary) can be relied on without reading any code; encapsulation maintained only by convention degrades as the system is modified.

## Build abstractions incrementally

- **Discover abstractions as the design progresses, one decision at a time.** You will know only some of an abstraction's operations early; add operations as using code reveals the need. Build the program one decision at a time and delay each until you have the information to make it well.
- **Introduce a type to limit the spread of information.** When a representation detail threatens to leak across modules, wrap it in a new abstract type whose operations are the only access — confine the blast radius of a future change to one cluster.

## Subtyping and the substitution principle

- **Honor substitutability: a subtype's objects must be usable everywhere the supertype is expected, with the program's behavior unchanged.** A subtype must provide all the supertype's operations *and* the same behavior for them — matching names and signatures is not enough (a stack is not a subtype of a queue though both `add` and `remove`).
- **Distinguish a subtype (a semantic, behavioral relationship) from a subclass (a code-reuse mechanism).** Use the substitution test to decide subtyping; never assume that inheriting code makes one type a subtype of another.
- **Do not abuse inheritance to share an implementation.** Implementing one type using another as its representation achieves reuse without claiming a subtype relationship, and without the encapsulation violations that implementation inheritance invites. Keep "is-a-subtype-of" and "is-implemented-using" separate. (The language overlay expresses this with composition and small interfaces over any inheritance hierarchy.)

## Polymorphism by constraint

- **Let a polymorphic operation require only the operations it actually uses.** A sort needs its elements to be comparable, nothing more; state that constraint and accept any type that satisfies it rather than enumerating types. This is the grouping approach — depend on a small required interface, which the language overlay expresses as a consumer-defined interface.

---
paths:
  - "**/*.go"
  - "**/*.sh"
  - "**/*.py"
  - "**/*.scala"
  - "**/*.sc"
---

# Domain modeling

**Enforcement grade:** review and convention — ubiquitous language, entity-versus-value, aggregate boundaries, and where a bounded-context seam falls are all judgment. A repo can mechanize one seam with a vocabulary check over a package it wants kept domain-neutral.

Building code around a rigorous model of the problem domain. Source: Eric Evans, *Domain-Driven Design*. Calibrated for a modest domain (a handful of entities and value objects, a lifecycle or two, the rules that govern them, and the boundaries where work is handed off) — favor the tactical and supple-design rules, and use bounded contexts as a primary guide to module boundaries (below), not as enterprise-only machinery.

> See `craft-abstraction.md` for value objects as abstract data types, and the language overlay (`go-types.md` / `go-modules.md`, the `python-*` and `scala-*` sets) for encoding them and for packages as domain modules.

## Ubiquitous language and model-driven design

- **Build one shared vocabulary spanning speech, docs, and code; the model is the backbone of that language.** Make code names match domain terms exactly, and rename when a term shifts — a change in the language *is* a change to the model.
- **Let the model drive the design literally, so the mapping from model to code is obvious.** A model that doesn't guide implementation is worthless paper; whoever writes the code is modeling.
- **Push knowledge-rich behavior and rules into the model, not just data** — a domain model is not a database schema. Isolate domain logic in its own layer, free of transport, persistence, and orchestration.

## Tactical building blocks

- **Model anything with identity over time as an Entity** — define identity explicitly (an `ID` field), keep the type spare, and don't lean on language `==` or pointer identity for domain identity.
- **Model anything defined purely by its attributes as a Value Object — immutable and side-effect-free.** Make its attributes a conceptual whole and replace the whole rather than mutate a part. Value objects are the bulk of this domain; this is where suppleness pays off.
- **Express an operation that isn't naturally a thing as a Service** — stateless, verb-named, defined in domain terms, with domain objects for parameters and results. Forcing an action onto an entity distorts it; "Manager" objects are a smell.
- **Organize code into Modules named in the ubiquitous language; let the boundaries emerge from the model, not from technical tiers.** Modules are the chapters of the domain's story — group the classes you want the next reader to think about together, and seek low coupling as *concepts that can be reasoned about independently*, not a metric over imports. Refine the model until it partitions along high-level domain concepts; resist infrastructure-driven packaging (a tier per layer, data split from the behavior that operates on it) that fragments a conceptual object and robs cohesion. Let modules coevolve with the model rather than freezing the early guess. The outer boundary that contains these modules is the bounded context (below).
- **Cluster entities and values into Aggregates with one root and a consistency boundary; enforce invariants at every commit** — but only where a real invariant spans objects. Outside objects reference the root only. Keep cross-aggregate consistency eventual.
- **Use a Factory to encapsulate complex creation** (produce a whole aggregate atomically, invariants satisfied or fail loudly) — but prefer a plain validating constructor when construction is simple.
- **Provide a Repository only for aggregate roots that need global access; make it act like an in-memory collection that hides persistence**, and leave transaction control to the caller.

## Supple design

- **Name every type, method, and argument by its effect and purpose, never its mechanism** — an intention-revealing interface. If a client must read the internals to use it, encapsulation is lost.
- **Put as much logic as possible into side-effect-free functions** that return a result without changing state, and strictly **separate commands from queries** — commands change state and return no domain data; queries compute and change nothing. Side-effect-free functions compose safely.
- **State post-conditions and invariants as assertions** (encode them as tests where the language can't express them) — assertions describe state, so they're analyzable without tracing execution.
- **Factor intricate computation into standalone, dependency-free types understandable in isolation; prefer closure of operations** (a return type matching the argument type) where it fits. **Decompose along the domain's conceptual contours**, not by uniform grain — align module boundaries with the domain's real axes of change.

## Making implicit concepts explicit

- **When a constraint, process, or rule distorts its host object, promote it to a first-class object.** A rule buried in a guard clause can't be discussed or reused.
- **Express a rule that tests an object as a Specification** — a predicate-like value usable for validation, selection, and creation — but implement only the combinators (AND/OR/NOT) you actually use.

## Bounded contexts and the module boundary

- **A Bounded Context is the boundary within which one model — and every term in it — stays coherent and means exactly one thing.** It is the outermost and hardest modularity boundary: decide the context seams first, then partition inside each. A context boundary is wherever the model's meaning changes — an external system you don't control, a separate subsystem or team, a distinct physical model (code base, schema).
- **Draw the hard module boundary at the context seam and put explicit translation across it; only inside one context do you split into modules for cognitive load.** Model-driven design is context-bounded — work with one model within any single context, and don't force the whole system into one model.
- **Heed Evans's precision: bounded contexts are not modules.** Modules also organize elements *within* a context and don't by themselves signal a context change, and naive module-splitting can *hide* accidental fragmentation — the same concept duplicated, or one name meaning two different things (false cognates). When a module boundary is really a context boundary, it needs translation across it, not a shared import.
- **A system that integrates with models it doesn't own has a real context seam at each — identifying them is critical even at small scale.** An external platform, a separate data store, a different target system, the LLM's own output schema: make each a hard module boundary with an explicit translation type, rather than letting a foreign model leak in. Only the heavy *artifacts* (a formal context-map document, a full anticorruption layer) scale with the number of contexts. (Record your own system's seams and their translation types in the language overlay so the boundary stays visible.)
- **The real hazard here is the opposite of over-application: missing a context seam and fusing two models into one**, which produces exactly those duplicate concepts and false cognates. Scale the heavy strategic artifacts to the domain's size — but never skip drawing the boundary.

## Translating to the target language

The building blocks land differently per language — value objects as immutable constructed types, entities as types with an explicit identity field, repositories as a narrow interface over the store, services as stateless functions or focused modules, modules as packages or namespaces named in domain terms (never partitioned by technical layer or by pattern type, which Evans calls an error). The per-language overlay carries the concrete idiom (`go-types.md` / `go-modules.md` for Go; the `python-*` set for Python; the `scala-*` set for Scala). At this domain's scale the essential pieces are value objects + constructor validation, the repository interface over the store, intention-revealing names, command/query separation, and drawing boundaries along context seams; elaborate aggregates, factories beyond a validating constructor, the full specification algebra, and the heavy strategic artifacts scale to need.

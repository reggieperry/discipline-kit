---
name: object-oriented-style-peers-messages-context-independence
description: "How to structure objects per GOOS Ch 6-7. Communication over classification; peers via messages; dependencies in constructor; composite simpler than sum; context independence. Applies to Python and most OO languages, not just Java."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

GOOS's "opinionated view" of OO design (Ch 6-7) is the style I lean toward for non-trivial classes. The rules below are how I apply it.

**Why:** focusing on object communication rather than class hierarchy yields code that's easier to test, easier to change, and easier to reason about locally. A past PR review surfaced several specific anti-patterns these rules guard against ([[reference_python_pr_gotchas]]).

**How to apply:** when designing a class, name its peers and the messages it sends them before you choose its representation. When the class is awkward to construct or test, suspect a design problem in one of the categories below.

## Communication over classification

The behavior of an OO system is an emergent property of how its objects communicate. The class hierarchy is at best one dimension of the structure; the communication patterns between objects carry most of the meaning. *"The domain model is in these communication patterns."* (GOOS Ch 2.)

In practice: emphasize interfaces and roles over classes. An object's type is defined by the role it plays in messaging, not by what it inherits from. Treat class hierarchies as an implementation detail; prefer composition.

## Internals vs. peers

An object communicates with its *peers* through messages. Peers fall into three stereotypes:

| Stereotype | Lifetime | How initialized | Examples |
|---|---|---|---|
| **Dependencies** | Required for the object to function | Constructor argument; never optional | Database, registry, gateway client |
| **Notifications** | Listeners; fire-and-forget; the object doesn't care if anyone is listening | Default to null-object or empty list; settable later | Event listeners, progress reporters |
| **Adjustments** | Policy or strategy that tunes behavior | Default to a sensible value; settable later | Comparator, formatter, retry policy |

The shape that follows:
- Pass dependencies through the constructor; the object cannot exist without them.
- Default notifications to "no listeners"; expose `add_listener` / `subscribe` methods.
- Default adjustments to sensible behavior; expose setters.

*"There is no try"* (GOOS Ch 6, citing Yoda). Partially-constructed objects that get "configured" via setters after creation are brittle; new fields can be added and old client code still compiles while constructing invalid objects.

## Tell, Don't Ask (the Law of Demeter)

Send messages that say *what to do*; don't pull data out and decide outside. The anti-pattern is a chain of getters terminating in a setter — every step in the chain exposes structure and couples the caller to all the intermediate types. Replace with a single named operation on the object that knows.

```python
# Wrong — caller knows the chain
master.get_dockable_panel().get_customizer().get_save_item().set_enabled(False)

# Right — caller says what it wants
master.allow_saving_of_customizations()
```

The second form hides structure, names the intent, and concentrates the change radius.

## No And's, Or's, or But's

Single Responsibility Principle in plain language: you should be able to describe what an object does without using a conjunction. *"This object loads documents AND parses them"* is two objects. *"This object dispatches requests OR caches them"* is two objects. When the description needs an "and," split.

## Composite simpler than the sum of its parts

The API of a composite object should not be more complicated than that of any one of its components. A `MoneyEditor` containing an `AmountField` and a `CurrencyField` should expose `setValue(money)`, not `getAmountField()` and `getCurrencyField()`. If exposing the parts is necessary, the composite is a leaky wrapper — clients will do the work, and the composite earns nothing.

## Context independence

A system is easier to change if its objects are *context-independent* — they hold no built-in knowledge about the system they execute in. Whatever an object needs to know about its larger environment must be passed in (at construction, or as a method argument). The object decides locally based on what it has.

Operationalized: a class that uses terms from two different domains (the application domain and a transport domain, say) is probably violating context independence. The exception is a *bridging layer* whose stated purpose is translating between domains. Inside the application core, each class should speak one domain vocabulary.

## Encapsulation vs information hiding

The two terms are often conflated; they are not the same:

- **Encapsulation** controls how a change to one object can affect others, by ensuring all interaction goes through the API. The blast radius of a change is bounded.
- **Information hiding** conceals *how* the object does its work behind the abstraction of *what* it does, so callers can work at the level of intent.

You can have one without the other. A class with public mutable fields has poor encapsulation. A class with getters and setters for every field has reasonable encapsulation but poor information hiding (the rep is fully visible). Aim for both. Anti-patterns: returning mutable internal collections (encapsulation hole), letting clients query for state they're about to act on (information-hiding hole — Tell-Don't-Ask).

## Roles and class diagrams diverge

A single object can play multiple roles. In GOOS's game example: an Obstacle is `Visible` and `Physical`; a Script is `CollisionResolver` and `Animated` but not `Visible`. Static class hierarchies tend to capture one dimension; communication-driven design captures roles, which often crosscut classes.

**Practical move:** identify the *role* (interface/protocol) before locking in the class. Multiple unrelated classes can play the same role; one class can play multiple roles. Languages with structural typing (Go, TypeScript) or duck typing (Python) make this easier; languages with nominal typing (Java) need explicit interface declarations to make it visible.

## Apply judiciously to Python

GOOS uses Java. Python translation:
- "Pass dependencies in the constructor" → `__init__` arguments, type-hinted with the Protocol/ABC role they play.
- "Mock peers, not internals" → patch boundaries with `pytest`'s `monkeypatch` or `unittest.mock`; don't reach into the class's `_private` attributes.
- "Use interfaces" → `typing.Protocol` for structural roles, `abc.ABC` for nominal roles. Lean Protocol unless you need explicit registration.
- "Tell, Don't Ask" → applies identically; avoid getter-chain `__getattr__` magic that turns into Demeter violations.

## Cross-references

- [[reference_design_abstraction_lsp]] — Liskov foundation; subclass vs subtype.
- [[feedback_tdd_listening]] — how testing reveals design problems in this style.
- [[feedback_mock_discipline]] — what to mock; corollary of "peers vs internals."
- [[feedback_refactoring_smells]] — code smells that signal violations of these rules.
- Source: Growing Object-Oriented Software, Guided by Tests (Freeman & Pryce), Chapters 6-7.

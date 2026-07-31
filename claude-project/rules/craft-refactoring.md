---
paths:
  - "**/*.go"
  - "**/*.sh"
  - "**/*.py"
  - "**/*.scala"
  - "**/*.sc"
---

# Refactoring existing code

**Enforcement grade:** review and convention, with a mechanical prerequisite — the fast self-checking suite this file requires is real wherever the gate runs tests, so the safety net exists even though the discipline is not scanned. Nothing enforces one-hat-at-a-time, and no check detects a smell.

The disciplined way to change the structure of working code without changing what it does. Source: Martin Fowler, *Refactoring: Improving the Design of Existing Code* (2nd ed).

> See `craft-complexity.md` for what you are refactoring *toward* (deep modules, less leakage), `craft-tdd.md` for the test suite that makes refactoring safe, and the active language overlay (`go-*.md`, the `python-*` and `scala-*` sets) for the idioms several catalog entries map to.

## Discipline

- **Refactor only to make code easier to understand and cheaper to change — never to alter observable behavior.** "Observable" is user-visible behavior; call stacks, performance characteristics, and internal interfaces may move.
- **Wear one hat at a time: adding functionality, or refactoring — never both in the same step.** Adding function writes new code and new tests; refactoring restructures and changes no tests except to track a moved interface.
- **Take the smallest steps that compose, and run the tests after every one.** The code compiles and passes after each step; it never sits broken. If someone's code was "broken for days while refactoring," they weren't refactoring.
- **Commit after each green step so you can revert to the last good state.** When a test goes red and the cause isn't immediately obvious, revert and redo in smaller pieces rather than debugging forward.
- **Rename the moment a better name appears — naming is a first-class refactoring, not cosmetic.** Leave the code healthier than you found it; aim for better, not perfect.

## When to refactor

- **Rule of Three:** do it once, tolerate the second duplicate, refactor on the third.
- **Preparatory:** before adding a feature, "make the change easy (this may be hard), then make the easy change."
- **Comprehension:** when you have to think to understand code, move that understanding out of your head into the code (rename, extract) before proceeding.
- **Litter-pickup and opportunistic:** fix small messes you pass through; most refactoring is interwoven with feature work, not a scheduled phase.
- **Justify it economically, not morally** — faster to add features and fix bugs (the design-stamina hypothesis), never "clean code" for its own sake. Apply YAGNI: add a parameter or abstraction only when a real second case exists.
- **Don't refactor a stable API you needn't touch, and prefer rewriting code that's beyond repair.**

## Prerequisite: self-testing code

- **Never refactor without a fast, self-checking test suite** — it is the bug detector that makes small steps safe. If the code is untested legacy, find seams and add tests *first*; never refactor on a red bar. (The language overlay's testing rules.)

## Smell → refactoring

| Smell | Tell | Refactoring |
|---|---|---|
| Mysterious Name | you puzzle out a name | Rename (Change Function Declaration) |
| Duplicated Code | same structure 2+ places | Extract Function; Pull Up |
| Long Function | you want to comment a block | Extract Function; Replace Temp with Query; Decompose Conditional; Split Loop |
| Long Parameter List | many or derivable params | Preserve Whole Object; Introduce Parameter Object; Remove Flag Argument |
| Global / Mutable Data | state writable from anywhere; spooky action | Encapsulate Variable; Split Variable; Separate Query from Modifier |
| Divergent Change | one module changes for many reasons | Split Phase; Extract Class/Function |
| Shotgun Surgery | one change, many little edits | Move Function/Field to gather |
| Feature Envy | a function talks to another module's data | Move Function; Extract then move |
| Data Clumps | same items travel together | Extract Class; Introduce Parameter Object |
| Primitive Obsession | domain modeled as strings/ints | Replace Primitive with Object; Replace Type Code with Subclasses |
| Repeated Switches | same type-switch in many places | Replace Conditional with Polymorphism |
| Loops | loop obscures select/transform | Replace Loop with Pipeline |
| Speculative Generality | hooks only the tests use | Inline; Collapse Hierarchy; Remove Dead Code |
| Message Chains | `a.b().c().d()` | Hide Delegate; Extract+Move |
| Large Class | too many fields/methods | Extract Class/Superclass |
| Comments (as deodorant) | comment hides bad code | Extract Function; Rename; Introduce Assertion — keep *why* comments |

## Named refactorings to know

Extract / Inline Function · Extract / Inline Variable · Change Function Declaration (rename, change signature; use migration mechanics — extract, inline, rename — for many callers) · Encapsulate Variable · Introduce Parameter Object · Combine Functions into Class · Replace Temp with Query · Extract Class · Decompose Conditional · Replace Nested Conditional with Guard Clauses · Replace Conditional with Polymorphism · Separate Query from Modifier · Parameterize Function · Replace Magic Literal with a named constant.

## Translating to the target language

Several catalog entries assume class-based OO; the per-language overlay carries the translation. Where a language has no implementation inheritance, *Replace Conditional with Polymorphism* becomes small interfaces plus one concrete type per case; where error returns are idiomatic, *Replace Error Code with Exception* inverts (return errors, don't reach for panic or exceptions); guard clauses may be the default control-flow style rather than an occasional cleanup; and immutable result records may need no getters/setters. Apply the smell→refactoring catalog as written, and let the active language rules (`go-*.md`, the `python-*` and `scala-*` sets) specialize the mechanics.

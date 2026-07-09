---
name: refactoring-posture-and-code-smells
description: "When to refactor, how to refactor, and the smells that signal it. Distilled from Fowler Refactoring 2nd ed Ch 2-3 and GOOS Ch 20. Refactoring is opportunistic and economic, not aesthetic; smells are guides not rules."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

Refactoring is the discipline of restructuring code without changing observable behavior. Fowler's Refactoring is the catalog; this memo is the posture.

**Why:** the economic case is what matters, not aesthetics. Fowler: *"The point of refactoring isn't to show how sparkly a code base is — it is purely economic. We refactor because it makes us faster — faster to add features, faster to fix bugs."* When a review finds code that works but is hard to reason about, refactoring is the response to that, not adding comments.

**How to apply:** refactor opportunistically as you work; reach for a smell-driven refactoring when one of the patterns below fires; always have tests before you start.

## The two hats

When working on code, you're either *adding behavior* or *restructuring without changing behavior*. Wear one hat at a time. Make the distinction visible (separate commits, or at minimum mental discipline). Mixing them is how subtle bugs creep in: a refactor that "while I'm in here" also changes behavior is a behavior change disguised as a refactor.

## Kent Beck's two-step

*"For each desired change, make the change easy (warning: this may be hard), then make the easy change."* — Kent Beck.

The implication: when adding a feature is hard, *don't* push through. Stop, refactor the surrounding code so the feature becomes a small addition, then add the feature. Both parts of the work — the refactor and the feature — are smaller than the brute-force "just add the feature to messy code" alternative.

## When to refactor

- **Preparatory refactoring.** Before adding a feature, restructure the area so the feature becomes a small change. This is the highest-leverage form.
- **Comprehension refactoring.** While reading code to understand it, rename variables, extract methods, and simplify conditionals as the understanding develops. *"Refactoring moves the understanding from your head into the code itself"* (Fowler, channeling Ward Cunningham).
- **Litter-pickup refactoring.** When you notice something bad, leave it slightly better than you found it. Camp-site rule. Don't take a multi-hour detour, but small fixes pay back.

Most refactoring is opportunistic — it happens while you're doing something else. Planned refactoring (a dedicated effort) is appropriate when neglect has built up enough debt that surrounding work is being slowed, but it should be rare.

## When NOT to refactor

- Code that's a mess but you don't need to modify it. Treat it as an API; leave it alone.
- Code you're about to rewrite entirely. Don't pre-clean the rewrite target.
- Code with no tests when you can't safely add tests first. *"Working Effectively with Legacy Code"* (Feathers) is the guide for this case — get seams in place, then refactor.

## The Rule of Three

*"The first time you do something, you just do it. The second time, you wince at the duplication but do it anyway. The third time, you refactor."* — Don Roberts (via Fowler).

Premature extraction is its own cost. Two similar things might not be the same thing. The third occurrence is when you have enough evidence that the duplication is structural rather than coincidental.

## Tests are the precondition

*"Before you start refactoring, make sure you have a solid suite of tests."* Refactoring without tests is restructuring blind. Self-testing code is the bedrock — see [[feedback_test_discipline]].

If you can't safely add tests to the legacy code first, you're in a "find seams" territory. Use automated refactorings (IDE-supported) where you can — they're proven safe at the syntax level even without behavior tests.

## The mechanical discipline

Small steps. After each step, run the tests. Commit after each green refactor (locally, can squash before pushing). When a step fails, you know exactly which step caused it; revert it and try a different decomposition.

The temptation is to "do the whole thing at once" — resist. Multiple small refactorings compose into large structural changes safely; one large refactor risks getting stuck in the middle.

## The smells (and what they say)

Smells are heuristics — code that *might* indicate a design problem. They're not rules to mechanically apply; they're prompts to look closer.

| Smell | What it usually means | First-try refactoring |
|---|---|---|
| **Long Function** | Mixed levels of abstraction; hidden concepts | Extract Function |
| **Long Parameter List** | A concept is missing; the function does too much | Introduce Parameter Object; or split the function |
| **Duplicated Code** | A concept is repeated without a name | Extract Function; or pull up to common helper |
| **Mysterious Name** | A reader (or future-you) won't understand | Rename — *"Never be afraid to change names to improve clarity"* |
| **Divergent Change** | One class changes for many reasons | Split Class along the change-reason axis |
| **Shotgun Surgery** | One change requires edits in many classes | Move related behavior together; Introduce a coordinator |
| **Feature Envy** | A method uses another class's data more than its own | Move Function to the other class |
| **Data Clumps** | Same group of fields traveling together everywhere | Extract Class (or value object) |
| **Primitive Obsession** | Domain concepts represented as strings/ints | Replace Primitive with Object |
| **Repeated Switches** | Same type-test in many places | Replace Conditional with Polymorphism (or strategy) |
| **Mutable Data** | Many places mutate the same state | Encapsulate (Separate Query from Modifier); Replace with Value Object |
| **Loops** | (2nd ed addition) | Replace with Pipeline (filter/map/reduce) |
| **Lazy Element** | A function/class doing less than its keeping-around cost | Inline |
| **Speculative Generality** | Hooks for future flexibility that's not actually needed | Collapse Hierarchy; Remove Dead Code |
| **Temporary Field** | Field only meaningful in some states | Extract Class for the state, or Replace with Strategy |
| **Message Chains** | Train wrecks of `a.b().c().d()` | Hide Delegate; Tell-Don't-Ask |
| **Middle Man** | A class that just delegates to another | Remove Middle Man |
| **Insider Trading** | Classes whispering to each other across module boundaries | Move Function; Hide Delegate |
| **Large Class** | Too many fields, too many concerns | Extract Class; Extract Superclass |
| **Alternative Classes with Different Interfaces** | Same role, different vocabulary | Rename to match; or Extract Superclass |
| **Data Class** | A class that's just getters/setters | Move behavior into the class (Move Function); but: see Result Records exception |
| **Refused Bequest** | Subclass doesn't want what the parent provides | Replace Subclass with Delegate; or the smell is faint enough to ignore |
| **Comments** | Comments explaining what bad code is doing | Refactor so the comment becomes superfluous — *"When you feel the need to write a comment, first try to refactor the code so that any comment becomes superfluous"* |

The last one is widely misunderstood. Fowler does NOT say "don't write comments." He says: when you reach for a comment to explain what code does, suspect the code first. A comment that captures *why* (a constraint, a non-obvious decision, a workaround) is valuable. A comment that captures *what* (replicating what the code says in English) is usually a sign that the code should be clearer.

## Refactoring and YAGNI

Refactoring is what makes YAGNI ("You Aren't Gonna Need It") credible. Without refactoring, YAGNI is reckless — you build for today and you're stuck with it. With refactoring, YAGNI is the right call — build for today, refactor when tomorrow's actual needs arrive.

Don't add flexibility mechanisms (parameters, indirection layers, configuration knobs) speculatively. Add them when the second concrete need arrives; the Rule of Three says you'll know enough by then to design the right mechanism.

## Performance

Refactoring sometimes slows code locally. The strategy: write well-factored code first, then profile, then optimize the hotspots. *"Measure performance, don't speculate. You'll learn something, and nine times out of ten, it won't be that you were right."* (Fowler, citing Ron Jeffries.)

A well-factored codebase is easier to optimize, not harder — the hotspots are easier to find and smaller in scope. Premature optimization (the constant-attention approach) actually slows you down by spreading complexity through the codebase.

## Cross-references

- [[feedback_test_discipline]] — tests are the precondition for safe refactoring.
- [[feedback_tdd_listening]] — listening to tests surfaces the smells.
- [[feedback_oo_style]] — many smells are signs of OO-style violations.
- Source: Fowler, *Refactoring: Improving the Design of Existing Code* 2nd ed., Ch 2-3; Freeman & Pryce, *Growing Object-Oriented Software, Guided by Tests*, Ch 20.

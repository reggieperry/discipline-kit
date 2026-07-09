---
paths:
  - "**/*.scala"
  - "**/*.sc"
---

# Scala style and idioms

The base layer of Scala 3 discipline: naming, control flow, the braces-versus-indentation default, the `given`/`using` and `extension` basics, and the collection and `Option` idioms everything else builds on. Sources: the Scala 3 reference (docs.scala-lang.org/scala3/reference — Optional Braces, the `infix` modifier under Changed Features / Operators), the official Scala Style Guide (docs.scala-lang.org/style), *Programming in Scala* 5th ed (Odersky, Spoon, Venners, Sommers — Chapters 21 Givens and 22 Extension Methods), Li Haoyi's *Strategic Scala Style: Conciseness & Names*, and Wampler's *Seductions of Scala* for the central thesis that Scala's flexibility is its sharpest risk — the reason this rule exists is to spend that flexibility once, here, on one house standard rather than re-litigating it per file. Where the canon leaves a choice open, the choice is named with a house default and a reason.

> See `craft-complexity.md` for why one consistent vocabulary lowers cognitive load, `craft-documentation.md` for the language-neutral comment discipline the doc-comment mechanics here implement, `scala-types.md` for `enum`/opaque-type ADT modeling and `scala-concurrency.md` for the cats-effect `IO` boundary the pure core sits behind, and `scala-modules.md` for package layout and the one-effect-system rule.

## Formatting

- **Run `scalafmt` (`sbt scalafmtAll`) on every file; never hand-align.** The machine owns indentation, wrapping, and alignment, so the formatting debate does not exist. The repo config pins `maxColumn = 100`, `align.preset = none`, and the `RedundantBraces`/`RedundantParens`/`SortModifiers` rewrites — do not fight a rewrite by re-adding what it strips.
- **Let `scalafmt` settle the braces-versus-indentation question for a given construct; do not mix the two styles within one construct.** The Scala 3 reference is explicit that a well-indented program means the same with or without the optional braces — so the choice is a readability call, not a semantic one, and consistency is the whole value.

## Braces versus significant indentation

Scala 3 makes braces optional and treats indentation as significant. That freedom is exactly the kind of dialect-fork *Seductions of Scala* warns about, so the house picks one default and states when to deviate.

- **Default to braces in shared, reviewed code.** Significant indentation is fine for a tight local lambda body, but in code that others read and diff, explicit `{ }` and `( )` make the extent of a block obvious at a glance and survive a careless re-indent or a bad merge. A reusable library core and the pipeline stages are shared code.
- **Add an `end` marker only when the construct earns it.** The reference's own rule: an `end` marker makes sense when the construct contains blank lines, runs roughly fifteen to twenty lines or more, or ends heavily indented (four levels or more). Below that, an `end` marker is noise — drop it.
- **Reserve the `fewer-braces` colon-argument form (`xs.map: x =>`) for a single trailing block argument that genuinely reads better that way.** Do not reach for it to dodge a pair of parentheses; the dotted call with braces is the default.

```scala
// Default in shared code: braces, dot-notation, line-of-sight.
def total(orders: List[Order]): Money = {
  val amounts = orders.map(_.amount)
  amounts.reduceOption(_ combine _).getOrElse(Money.zero)
}

// Acceptable: a single trailing lambda where the colon form is clearly cleaner.
val scored = orders.map: order =>
  score(order)
```

## Naming

- **Upper camel case for types and objects, lower camel case for methods, values, variables, and parameters** — `class RetryPolicy`, `def scoreOne`, `val pendingCount`. The Scala Style Guide is explicit: underscores in identifiers are strongly discouraged, and `SCREAMING_SNAKE_CASE` is not used even for constants — a constant is just an upper-camel-case immutable member (`val MaxRetries = 3`).
- **Do not carry Java's `get`/`set` prefix.** Name an accessor for the property it returns (`def total`, not `def getTotal`); a boolean accessor with no mutator may take an `is` prefix (`def isEmpty`). A setter is the property name with `_=` appended.
- **Scale name length with usage density and scope, not with type complexity alone** (Li Haoyi's *Conciseness & Names*): a value used many times per line earns a short name; a name read once per few thousand lines earns a descriptive one; a wider-scoped or public name is longer because the reader lacks local context. A one-letter `c` for a fold accumulator is fine; an exported entry point is not.
- **Single uppercase letters for ordinary type parameters** (`A`, `K`, starting from `A`); a descriptive upper-camel-case name (not all-caps) when the parameter carries meaning — `Cache[K, V]`, `Repository[Id, A]`, `Validated[E, A]`. Keep the domain term identical across speech, docs, and code (`craft-complexity.md`); rename everywhere when the term shifts.
- **Give a dangerous-but-occasionally-needed operation a longer, deliberately clunkier name rather than a tempting short one or an operator** (`Unsafe.runSyncAndDiscard`, not a terse alias) so a caller chooses it consciously.

## Control flow

- **Prefer expressions to statements; let the last expression be the value.** `if`/`match` are expressions — assign their result, do not mutate a `var` across branches. Reserve `var` for a genuinely local, single-method accumulator and prefer a fold even there.
- **Handle the failure or empty case first and keep the success path at the left margin.** The line-of-sight discipline applies unchanged: a guard that returns or short-circuits early beats nesting the happy path inside `else`.
- **Use `match` for closed alternatives and make the compiler check exhaustiveness.** Match on an `enum`/sealed ADT (an order status, a parse result, a state) and let a missing case be a warning the build escalates — do not add a catch-all `case _` that silences it. (`scala-types.md`.)
- **Do not shadow an outer name in an inner block.** A rebind that reuses a name silently operates on the wrong value; pick a distinct name.

## `given` / `using` basics

Functional Scala leans on typeclasses — a combiner is a `Monoid`, an ordering is an `Order`, an accumulating validation is an `Applicative` — so the `given`/`using` mechanics are part of the base layer (*Programming in Scala* 5th ed, Ch. 21).

- **Pass a typeclass instance as a `using` parameter; never thread it by hand.** Write `def combineAll[A](xs: List[A])(using M: Monoid[A]): A`, not an explicit instance argument the caller must remember to supply.
- **Name a `given` for what it provides and the type it provides for** — `given monoidForMoney: Monoid[Money]` — not an anonymous instance, when it is referred to or imported by name. An anonymous `given` is fine only when nothing names it.
- **Place a typeclass instance in the companion object of the type or of the typeclass**, so it is found without an import (*Programming in Scala* Ch. 21 §5): the `Money` instances live in `object Money`, an instance that exists for a foreign type lives in the typeclass's companion. Reserve a separate `Ops`/`syntax` object — invited with an explicit `import` — for instances a user should opt into.
- **Import a `given` deliberately.** Bring instances into scope with the `given` selector (`import com.example.money.given`) rather than a wildcard that drags in unrelated names.

## Extension methods

- **Add syntax to a type you do not own with an `extension`, not an implicit class** (*Programming in Scala* 5th ed, Ch. 22). Group related operations in one collective `extension` block so sibling methods can call each other.
- **Put the extension where the compiler will find it without ceremony.** When the extension exists to make a typeclass pleasant to use, define it inside the typeclass trait itself — then it is in scope wherever a `using` instance of that typeclass is (Ch. 22 §5, "This is the best design"). When the extension is the goal and the user should opt in, put it in a singleton object they `import`.
- **Keep the receiver name on the `extension` clause meaningful** (`extension (lhs: A)`), and do not let an extension method silently shadow a real member — the compiler only rewrites a call that would otherwise be an error.

## Operators and `infix`

Scala's symbolic-method freedom is the part of the language most prone to producing a private dialect, so the house draws the line tight.

- **Define a method as alphanumeric and call it with a dot by default.** In Scala 3 an alphanumeric method may be used in dot-less infix position only if it is declared with the `infix` modifier — so reserve `infix` for the rare operation that genuinely reads as infix in the domain (`a combine b` on a `Monoid`), and let everything else be `obj.method(arg)`. The Style Guide's position is that infix notation for ordinary methods should generally be avoided.
- **A symbolic operator (`+`, `<+>`, `~`) is justified only where it is dense and standard** — a binary algebraic operator on a value type the reader already knows from the math (a semiring `+`/`*`, a lattice `meet`/`join` aliased to a conventional symbol). It is not justified for an operation used once per file; give that a name. This is Li Haoyi's density test applied to operators, which are just very short names.
- **Carry a `@targetName` on a symbolic operator** that gives it an alphanumeric encoding (the Scala 3 reference recommends this) — it makes stack traces and the bytecode signature readable and gives Java interop a name to call.

```scala
extension (lhs: Money)
  infix def combine(rhs: Money): Money = Money(lhs.cents + rhs.cents)

opaque type Score = Double
object Score:
  extension (s: Score)
    @targetName("plus") def +(t: Score): Score = (s: Double) + (t: Double)
```

## Collections and `Option`

- **Reach for the standard combinators — `map`, `flatMap`, `filter`, `fold`, `collect` — over a manual loop, and write a non-trivial chain as a `for` comprehension.** The combinator names the intent; the loop hides it.
- **Default to immutable collections** from `scala.collection.immutable`; introduce a mutable builder or `mutable` collection only as a contained local optimization, never in a type that crosses a module boundary.
- **Model absence with `Option`, never `null`.** Combine optional values with `map`/`flatMap`/`getOrElse` or a `for` comprehension; do not pattern-match `Some`/`None` when a combinator says it more plainly.
- **Never call `.get` on an `Option` or `.head` on a possibly-empty collection** — reach for `getOrElse`, `fold`, `headOption`, or a `match` that handles `None`, and prefer `collect` to a `map` that can fall through. (`scala-errors.md` owns why a partial accessor is a defect, not a style nit, and the WartRemover/Scalafix lints that mechanize it.)
- **Treat an empty collection and a missing value as ordinary cases, not errors.** Return an empty `List` rather than a sentinel, and test emptiness with `.isEmpty`. Errors that are genuinely failures belong in the effect and error types, not in a magic return value. (`scala-errors.md`, `scala-concurrency.md`.)

```scala
// Combinators and a for-comprehension over Option — not null, not .get, not a manual loop.
def latestStatus(events: List[Event]): Option[Status] =
  events.filter(_.isComplete).maxByOption(_.at).map(_.status)

val isOverdue: Option[Boolean] =
  for
    s <- latestStatus(events)
    d <- dueDates.get(s.orderId)
  yield s.settledAfter(d)
```

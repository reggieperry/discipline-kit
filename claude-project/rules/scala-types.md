---
paths:
  - "**/*.scala"
  - "**/*.sc"
---

# Scala domain modeling with the type system

**Enforcement grade:** partly mechanical, via the compiler more than the gate — `-Werror` with `-Wunused:all` and `-Wvalue-discard` makes an inexhaustive match and a dropped result fatal, and the gate's fail-closed compile precondition means a non-compiling tree blocks rather than reading as clean. The modeling discipline is review, carried by the suites.

Encode your domain's invariants in the type system so the compiler rejects an illegal value before it reaches the code that consumes it — a closed set of states, a branded identifier, a value object with two coherent fields, and a multi-field validation all carry their laws as types, not as runtime checks. Sources: the Scala 3 reference (enums, opaque type aliases, contextual abstractions / type classes), *Functional Programming in Scala* 2nd ed (ADTs, the `Either`-to-`Validated` derivation and error accumulation in chapter 4), *Scala with Cats* (the anatomy of a type class, type classes and variance), and *Programming in Scala* 5th ed (case classes and pattern matching). The substitutability discipline is from Liskov (`craft-abstraction.md`); the value-object and ubiquitous-language discipline is from Evans (`craft-domain-modeling.md`).

> See `craft-domain-modeling.md` for value objects, entities, and naming in the ubiquitous language; `craft-abstraction.md` for abstract data types and the substitution principle; `scala-style.md` for the brace and given-clarity defaults; and `scala-llm.md` for the structured-output type as the typed model boundary at the LLM call.

## The shape of the discipline: encode what's cheap, test the residue

"Make illegal states unrepresentable" is the aspiration, not the whole job. Under the Curry-Howard correspondence a type reads as a proposition and a value of that type as its proof, so the compiler discharges the invariants you manage to encode — though Scala's nontermination, casts, and exceptions mean a well-typed program *approximates* a proof rather than being one. Push each invariant into the type while it stays cheap and clear: an `enum`/ADT for a closed set of cases (below), an opaque type behind a validating smart constructor. Some invariants are too costly — or impossible — to state in Scala's type system, and that residue is where the work lives. Close it with tests (`scala-testing.md`): ScalaCheck properties and `discipline` `checkAll` prove the laws and rules a value must obey on valid input, and they pin how the smart constructor behaves when something tries to build an illegal value. The type carries what it cheaply can; property and law tests carry the rest, the negative space included.

- **An opaque type without a validating smart constructor is just obfuscation.** The payoff of wrapping a primitive is the *constructor* that rejects or normalizes bad input. If every `String` is a valid `UserId`, the opacity buys type-safety but not an invariant — pair the opaque type with the check, or do not open the scope at all.
- **Fail closed by default: reject the illegal input.** A validating constructor returns `Option`/`Either` (or maps the bad case to a safe bottom); it never throws and never admits the bad value. Normalize instead of reject only when the mapping is *total and lossless* — clamping a known-bounded number, trimming insignificant whitespace; when in doubt, reject (`scala-errors.md`).
- **Test both sides of every uncodified invariant.** Write the law or property on valid values *and* a test that the constructor refuses or normalizes the illegal ones. The negative space is half the contract; an untested constructor is an unproven invariant.
- **A type with no illegal state needs no constructor.** `Point(x, y)` is a plain `case class`: every pair of `Double`s is a legal point, so there is nothing to reject. Do not add ceremony where the type already makes all states legal — the goal is the invariant, not the wrapper.

**Worked example — `Weight`.** A weight is a magnitude with `Zero` the bottom (no weight) and a positive `Pos` above it. Scala will not cheaply make "a `Double` in `(0, 1]`" a type, and `Weight` also carries several derived instances (`Order`, a `CommutativeRig`, two bounded semilattices), so it is a *distinct* sealed type — `sealed trait Weight` with `case Zero` and `case Pos(magnitude: Double)` — **not** an `opaque type = Double`, which would send a derived `Order.by(_.magnitude)` back to the `Order[Double]` it defines and loop (the self-referential-instance trap below). Its only constructors are `bottom`, `top`, and a clamping `of` that is fail-closed: `if !(m > 0.0) then bottom` catches `NaN` and every non-positive input, and `m >= 1.0` clamps to the top. The tests then carry both halves — `checkAll` pins the `Order` and bounded-semilattice laws on generated valid weights, and `WeightSuite` pins that `of(NaN)`, `of(0.0)`, and `of(-1.0)` all collapse to the bottom. The invariant the type cannot state is enforced by the constructor and proven by the test, which is exactly what stops a forged or non-finite weight from passing a downstream guard.

## ADTs are enums; make illegal states unrepresentable

The central rule of this file: an invalid value should not type-check. A closed set of cases is an enum, and the compiler then checks every match for exhaustiveness — a missing case is a compile error, not a `MatchError` at run time.

- **Model every closed alternative as a Scala 3 `enum`, not a hand-rolled sealed trait plus case classes.** An enum is the house ADT form: it desugars to a sealed hierarchy, gives you `ordinal`, `values`, `valueOf`, and `fromOrdinal` for free, and reads as the domain vocabulary. Reach for a bare `sealed trait` only when a case needs its own members the enum syntax can't express; default to `enum`.

```scala
// An order's lifecycle as a closed ADT. No fifth state can exist.
enum Status:
  case Draft       // created, not yet submitted
  case Submitted   // awaiting a decision
  case Approved    // decided, accepted
  case Rejected    // decided, refused

// Exhaustive by construction: drop a case and the compiler flags every match.
def isTerminal(s: Status): Boolean = s match
  case Status.Approved | Status.Rejected => true
  case Status.Draft | Status.Submitted   => false
```

- **Parameterize an enum case only when the case genuinely carries data**, with an explicit `extends` clause for the shared field. Keep the data minimal and the invariant inside the type.

```scala
// A verdict is a closed set; one case carries the reason it fired.
enum Verdict(val passing: Boolean):
  case Clean               extends Verdict(true)
  case Flagged(reason: String) extends Verdict(false)
  case Abstain             extends Verdict(false)
```

- **Generic, variant enums replace the old `sealed trait T[+A]` ADT.** A keyed carrier `Record[K, A]` and a result type are parameterized enums. Declare variance on the type parameter (below) and let the compiler check it across every case.

## Variance: read the parameter's role, then annotate

A parameter that the type only *produces* is covariant (`+A`); one it only *consumes* is contravariant (`-A`); a type that does both — or that is mutable — is invariant. *Scala with Cats* is explicit that Cats keeps its type classes invariant for exactly this reason; a producer-only result type is the case where covariance pays off.

- **A result-shaped enum is covariant in its value and error parameters.** The `Validated` derivation in *Functional Programming in Scala* (ch. 4) lands on `enum Validated[+E, +A]` precisely because a `Validated` only ever yields its `E` or its `A` — it never accepts one as input. A result type in your own code follows that shape.

```scala
// Covariant in both: a Result[Nothing, A] substitutes anywhere a
// Result[E, A] is wanted, and an Invalid[E] flows up unchanged.
enum Result[+E, +A]:
  case Ok(value: A)
  case Invalid(errors: cats.data.NonEmptyChain[E])
```

- **A consumer abstraction is contravariant.** An `Encoder[-A]` that only reads an `A` to serialize it should be `-A`, so an `Encoder[Any]` substitutes where an `Encoder[Order]` is wanted.
- **Make a type invariant when in doubt, and always when it both reads and writes its parameter, holds it in a mutable cell, or is a type class.** Invariance is the safe default; widen to `+`/`-` only when you have shown the parameter appears in one position only. Do not annotate a type-class trait's parameter — keep `Semigroup[A]`, `Eq[A]`, and your own type-class instances invariant, as Cats does.

## Wrap primitives in opaque types, behind a smart constructor

A bare `String` or `Double` carries no domain meaning and lets a caller pass the wrong one. An opaque type is a distinct type at compile time that erases to its underlying representation at runtime — zero allocation, full checking. This is the Scala form of "make illegal states unrepresentable" at the scalar level.

- **Give every scalar with a domain meaning an opaque type, and make the only way to build it a validating constructor.** Keep the `opaque type` and its companion together so the alias is transparent only inside that scope; outside it, the underlying type is invisible and no caller can forge a value past the check.

```scala
object Ratios:
  // Distinct from a raw Double everywhere outside this scope; erases to Double.
  opaque type Ratio = Double

  object Ratio:
    /** The only constructor: a ratio is a fraction in [0, 1]. */
    def from(d: Double): Either[String, Ratio] =
      if d >= 0.0 && d <= 1.0 then Right(d)
      else Left(s"ratio out of range: $d")

  extension (r: Ratio)
    def value: Double = r
    def combineMin(other: Ratio): Ratio = math.min(r, other)
```

- **Add behavior through `extension` methods on the opaque type**, not by exposing the representation. The representation stays sealed inside the defining scope; callers see only the operations the domain allows.
- **Use opaque types for the identifiers and tags a pipeline routes** — `UserId`, `OrderId`, a `Source` tag — so a user id can't be passed where an order id is wanted. This is the value-object building block from `craft-domain-modeling.md` expressed in Scala.
- **Beware the self-referential-instance trap when an opaque type aliases the type you derive an instance from.** Inside the opaque type's own scope the alias and its underlying are the same type, so an instance built `by` the underlying — `Order.by(_.magnitude)` on `opaque type Weight = Double`, `Order.by(_.value)` on `opaque type Label = String` — resolves the required `Order[Double]`/`Order[String]` back to *its own given* and recurses forever (the compiler warns "Infinite loop in function body"; `-Werror` makes that fatal). Two escapes: build the instance so it never summons the underlying's (`Order.fromLessThan`, `Eq.from`), or — especially when the type will carry several derived instances — make it a *distinct* `enum`/sealed type rather than an opaque alias, where the underlying is genuinely a different type and `.by` is safe. The scalar `Weight` and the label `Label` take the distinct-type route for exactly this reason.

## Compound value objects: enforce the invariant, key the carrier

A value object with two coherent fields and a parameterized carrier are the everyday building blocks; model them so a malformed one cannot be constructed. Keep the fields separately named and the key in the type.

- **Model a value object whose constructor enforces its invariant**, and any two related fields as two named, typed fields — never a single untyped map. A `case class` with a `private` constructor plus a validating `apply` keeps the fields coherent.

```scala
final case class Money private (amount: BigDecimal, currency: Currency)
object Money:
  /** The only constructor: reject an amount too precise for its currency. */
  def of(amount: BigDecimal, currency: Currency): Either[String, Money] =
    if amount.scale <= currency.decimals then Right(new Money(amount, currency))
    else Left(s"amount $amount too precise for $currency")

// Two related fields as two named, typed fields — making the pair a conceptual
// whole and forbidding "the approver's id under the author's label".
final case class Attribution(createdBy: UserId, approvedBy: UserId)
```

- **Carry the subject key as a phantom-style type parameter `K`** so two records about different subjects don't unify, and the value type `A` as the payload. Let the case class hold the `Money` value and its `Attribution` together, and never expose a setter — "change" means construct a new `Record` (the immutable value-object rule).

## Accumulate errors across independent checks — use `Validated`, never `Either`

This is a correctness rule, not a style preference. `Either` is a monad and *short-circuits* at the first `Left`; a multi-field validation must surface *every* failing field at once, which is the applicative `Validated`. *Functional Programming in Scala* derives `Validated` from `Either[List[E], A]` for exactly this reason: the difference is entirely in how two failures combine (concatenated via a `Semigroup`, not dropped).

- **Use `cats.data.Validated` for independent-field validation**, and combine with the applicative `mapN`, which accumulates every failing field's error rather than dropping all but the first. Reserve `Either` for genuinely sequential, fail-fast steps where a later check depends on an earlier one's success. The house error container is `ValidatedNec[E, A]` — `Validated[NonEmptyChain[E], A]` — for the reason `scala-errors.md` sets out (constant-time accumulation, at-least-one-error in `Invalid`); use it here too rather than `ValidatedNel`.

```scala
import cats.data.ValidatedNec
import cats.syntax.all.*

def validateUser(
    name: ValidatedNec[FieldError, Name],
    email: ValidatedNec[FieldError, Email],
    age: ValidatedNec[FieldError, Age]
): ValidatedNec[FieldError, User] =
  // Applicative: every Invalid field contributes its FieldError; none is dropped.
  (name, email, age).mapN(User.apply)
```

- **Type the accumulated error as a domain `FieldError` enum, not `String`** — a closed set of failures the caller can match on mechanically and render precisely, rather than reparse from a message.
- **Keep the error collection non-empty.** An empty error list is an illegal `Invalid` state; the `NonEmptyChain` inside `ValidatedNec` makes that unrepresentable and removes the empty-case branch from every consumer.

## Behavior is a type class via `given`/`using`

An algebraic operation over a carrier — a merge, an ordering, a monoid's combine — is a type-class instance, defined as *Scala with Cats* describes: a trait parameterized over the carrier, with `given` instances summoned through `using`.

- **Define the operation as a trait with the type parameter, and provide a single `given` instance for the carrier.** Summon it with `using` (or a context bound `[A: Combine]`), and reach for `summon[Combine[A]]` only when you need the instance as a value.

```scala
trait Combine[A]:
  extension (x: A) def combine(y: A): A   // associative

given Combine[Weight] with
  extension (x: Weight)
    def combine(y: Weight): Weight = ???   // e.g. the join

def combineAll[A: Combine](xs: List[A]): A = ???  // context bound, no named param
```

- **Derive a `given` from other `given`s for compound carriers** — a `Combine` over `Record[K, A]` built from the underlying `Combine[A]` in scope — rather than hand-writing each. Conditional givens are the house mechanism for lifting an operation over a wrapper.
- **Keep your type classes pure and lawful, and keep them invariant.** A `given` instance is a fact about a type; the laws (associativity, identity, absorption where they apply) are the contract a substitute must honor, per the substitution principle in `craft-abstraction.md`. State the laws as ScalaCheck properties (see `scala-testing.md`) — the type cannot express them, so the property suite does.

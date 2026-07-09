---
paths:
  - "**/*.scala"
  - "**/*.sc"
---

# Scala errors in the types

Errors live in the return type, not in thrown exceptions. A pure core — your domain value types, the parsing and validation layer, the functions that transform them — is pure by design, so a failure is a value the type system forces the caller to confront rather than a control-flow jump the caller can forget. Sources: *Scala with Cats* (Welsh and Gurnell), chapters 9 (`MonadError`) and 11 (`Semigroupal`, `Applicative`, and `Validated`); *Functional Programming in Scala*, 2nd ed. (Chiusano and Bjarnason), chapter 4 (why exceptions break referential transparency, `Option`, `Either`, `Validated`); *Practical FP in Scala* (Volpe), chapter 1 (`MonadError`/`ApplicativeError`, typed errors versus `F[A]`); the cats and cats-effect documentation (`Validated`, `ApplicativeError`/`MonadError`); and the WartRemover and Scalafix `DisableSyntax` catalogs for the lints that mechanize these rules. The design principle behind several of these rules — define errors out of existence — comes from `craft-complexity.md`.

> See `craft-complexity.md` for defining errors away, `craft-domain-modeling.md` for modeling the failure cases as part of the domain, `scala-types.md` for the error ADTs and the pure-core/`IO`-shell split, `scala-concurrency.md` for the one-effect-system rule, and `scala-llm.md` for feeding validation errors back to the model.

## Errors are values, not thrown exceptions

- **Do not use exceptions for control flow.** A thrown exception is not referentially transparent — its meaning depends on the enclosing `try`, so the same expression takes on different values in different contexts and can no longer be reasoned about locally (FPiS §4.1). Model the failure in the return type instead.
- **Return `Either[E, A]` for a recoverable error a caller will branch on, `Validated[E, A]` when independent failures must be accumulated, and `Option[A]` only for a plain present/absent with no reason to report.** These are the three shapes; reach for the narrowest one the call site actually needs.
- **The pure core never throws and never blocks.** Your domain types and the functions over them stay total: a step that cannot produce a value returns a failure in its result type, which is what lets the calling code branch on the failure deliberately rather than lose it to a stack unwind.
- **`throw` belongs only at a hard boundary** — an unrecoverable invariant breach the program cannot continue past — and even there prefer to surface it as a value. Reserve genuine exceptions for programmer bugs, not domain outcomes.

## No null; `Option` for absence

- **Never introduce `null`, and never return it.** Use `Option[A]` to express absence in a value the type system can see. Lift a nullable value crossing the boundary from Java or a raw library with `Option(x)` at once, before it spreads.
- **Do not reach into a partial accessor.** `Option.get`, `Either.toOption.get`, `head` on a possibly-empty list, and a `Try.get` are the same bug as a `null` dereference moved one type over — they throw on the absent case the type was meant to capture. Pattern-match, `fold`, `getOrElse`, `map`/`flatMap`, or a `for`-comprehension instead. WartRemover's `Null`, `OptionPartial`, `EitherProjectionPartial`, and `TryPartial` warts and Scalafix `DisableSyntax.noNulls` exist to make these mechanical failures; treat a finding as a real defect, not noise.

## Error ADTs, not stringly-typed errors

- **Model the error channel as a sealed `enum` (a Scala 3 ADT), not a bare `String` or a loose `Throwable`.** A typed hierarchy lets a caller exhaustively match the failure modes it handles and lets the compiler flag the one it forgot when a new case is added (Volpe ch. 1) — exactly the safety a `String` error throws away.

```scala
enum ParseError:
  case EmptyInput
  case NotANumber(raw: String)
  case OutOfRange(value: Int, bound: Int)

def parsePort(raw: String): Either[ParseError, Int] =
  if raw.isEmpty then Left(ParseError.EmptyInput)
  else raw.toIntOption match
    case None                  => Left(ParseError.NotANumber(raw))
    case Some(n) if n > 65535  => Left(ParseError.OutOfRange(n, 65535))
    case Some(n)               => Right(n)
```

- **Name the type for the operation, not the layer** — `ParseError`, `RouteError`, `ValidationError` — and give each case the data a handler or a log line actually needs (the offending input, the violated bound). Do not encode that data back into an interpolated `String`; that forces every consumer to re-parse what you already had structured.
- **Keep error messages free of secrets and free of redundant context.** Render a human-readable message at the edge from the typed case, not by carrying a prebuilt sentence through the core.

## Fail-fast with `Either`, accumulate with `Validated`

- **`Either` is fail-fast; `Validated` accumulates — and the difference is structural, not stylistic.** `Either` is a monad, so `flatMap` (and therefore a `for`-comprehension) sequences and short-circuits on the first `Left`; the second failure is never inspected (*Scala with Cats* §11.3). `Validated` is an `Applicative` but deliberately *not* a `Monad`, so combining two `Invalid`s with `mapN` merges both errors instead of stopping (FPiS §4.4). Choose by whether the caller needs every reason or just the first.
- **Use `Either` when one failure makes the rest moot** — a step that depends on the previous one's output, where there is nothing to report past the first stop. Sequence it in a `for`-comprehension.

```scala
for
  port <- parsePort(rawPort)        // a later step needs `port`;
  conn <- connect(host, port)       // no point validating it if the port is bad
yield conn
```

- **Use `Validated` when failures are independent and the caller wants all of them at once** — validating the fields of an inbound request against a schema, where reporting only the first defect would force a slow one-at-a-time round-trip with the client. House default for the error container is `ValidatedNec[E, A]` — `Validated[NonEmptyChain[E], A]` — because `NonEmptyChain` accumulates in constant time and guarantees at least one error in the `Invalid` case; prefer it to `ValidatedNel`/`NonEmptyList`. Combine with `mapN`.

```scala
import cats.data.ValidatedNec
import cats.syntax.all.*

def validateUser(
    name: String,
    age: Int,
): ValidatedNec[FormError, User] =
  (validateName(name), validateAge(age))
    .mapN(User.apply)   // both checks run; Invalid carries every failure
```

- **Keep the two forms convertible at the boundary, and do not mix paradigms within one expression.** Run an accumulating phase in `Validated`, then `.toEither` to feed a fail-fast sequential phase (or `.toValidatedNec` the other way). Do not call `flatMap` on a `Validated` to fake sequencing — its lack of a `Monad` is the whole point; if you need sequencing, you are in `Either`.

## Effectful errors: `MonadError` over `IO`, not a second mechanism

- **Effects are cats-effect `IO`, and `IO` already is its error channel.** `IO` implements `MonadError[IO, Throwable]` (aliased `MonadThrow`), so an effectful failure is raised and handled through that one mechanism — `raiseError`, `handleErrorWith`/`handleError`, `attempt`, `adaptError`, `onError`, `rethrow` — not by throwing inside an `IO.delay` or returning a side `Future` (*Scala with Cats* §9.5; cats-effect docs). Do not introduce ZIO or `scala.concurrent.Future` alongside `IO`; mixing effect systems and error channels is banned across this set — see `scala-concurrency.md`.
- **Raise a domain failure with `raiseError`, recover with `handleErrorWith`.** Define the effectful error type as a sealed ADT extending `NoStackTrace` (an exception's stack trace is dead weight for a value you route deliberately):

```scala
import cats.MonadThrow
import cats.syntax.all.*
import scala.util.control.NoStackTrace

sealed trait LookupError extends NoStackTrace
object LookupError:
  case object NotFound extends LookupError

def load[F[_]: MonadThrow](id: UserId): F[User] =
  repo.find(id) match
    case Some(user) => user.pure[F]
    case None       => LookupError.NotFound.raiseError[F, User]
```

- **Code the happy path; let an unhandled domain error propagate to the one place that decides the response.** You do not have to handle every failure at every layer — an unrecovered `IO` error surfaces at the boundary that runs it. Handle only the cases whose recovery changes behavior, with `handleErrorWith` or `recoverWith` on the specific case (Volpe ch. 1).

## `raiseError` versus returning a value — pick by what the caller does

- **Return `Either[E, A]`/`Validated[E, A]`/`Option[A]` when the immediate caller will pattern-match the outcome and the failure is part of the normal result.** The type makes the failure visible at the call site; that is the default for the pure core.
- **Use `F[A]` with `raiseError` when the error type is a `Throwable`, the caller mostly cares about the happy path, and the failure should ride the effect's error channel to a distant handler.** Volpe's guidance is explicit: when `E <: Throwable`, `F[A]` over `MonadError` has better ergonomics than threading `F[Either[E, A]]` through `EitherT` everywhere — at the cost of losing the error type from the signature, a trade-off to make consciously, not by habit.
- **Do not stack `F[Either[E, A]]` as a reflex.** Reach for it only when the business logic genuinely branches on a *typed* error and you want the compiler to enforce exhaustiveness; otherwise it is monad-transformer overhead the call sites pay for in annotations.

## Handle once, and define errors out of existence

- **Handle each error exactly once.** Do not both log it and re-raise/return it — that produces duplicate, confusing log lines. Log where you actually handle the failure, or propagate it with context, not both.
- **Prefer redefining an operation so the error case becomes the normal case** over adding another failure return — an `ensureAbsent` that succeeds when the thing is already gone needs no error path at all. Where you cannot define the error away, handle it as low as you can (mask it) or aggregate many handlers into one high in the call path. Fewer failure sites means simpler, more reliable code, and a smaller error surface overall (`craft-complexity.md`).

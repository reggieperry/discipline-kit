---
paths:
  - "**/*.java"
---

# Java types

Encode your domain's invariants in Java's type system so the compiler rejects an illegal value before the code that consumes it runs — a closed set of cases, an immutable data carrier, a wrapped identifier, and a non-null-by-default reference each carry their laws as types, not as scattered runtime checks. Sources: *Effective Java* 3rd ed (Joshua Bloch — Item 17 "minimize mutability" and the `record` as its modern realization, Item 62 "avoid strings where other types are more appropriate"), the Java 21 language documentation for records, sealed classes and interfaces, and pattern matching for `switch`, and the JSpecify nullness specification (jspecify.org). The value-object and ubiquitous-language discipline is from Evans (`craft-domain-modeling.md`); the fight against needless complexity is from Ousterhout (`craft-complexity.md`). Floor: Java 21.

> See `java-errors.md` for closed-alternative failure handling and the exception-versus-result boundary; `java-style.md` for pattern matching and the `switch` defaults; `java-modules.md` for package boundaries and where `@NullMarked` is declared; `java-testing.md` for pinning the invariants the type cannot state; `craft-domain-modeling.md` for value objects, entities, and the ubiquitous language; and `craft-complexity.md` for keeping each module deep.

## The shape of the discipline: make illegal states unrepresentable

"Make illegal states unrepresentable" is the aspiration, not the whole job. Push each invariant into the type while it stays cheap and clear — a sealed interface for a closed set of cases, a record behind a validating canonical constructor. Some invariants are too costly to state in Java's type system, and that residue is where the work lives; close it with tests (`java-testing.md`) that pin the laws a value obeys on valid input and pin how the constructor behaves when something tries to build an illegal one.

- **A record without a validating constructor is just a tuple with names.** The payoff of wrapping data in a record is the compact canonical constructor that rejects or normalizes bad input. If every argument makes a valid value, the record still earns its place as a named type — but where an invariant exists, pair the record with the check or you have a carrier, not a contract.
- **Fail closed: reject the illegal input at construction.** The canonical constructor throws (`IllegalArgumentException` for a bad value, `NullPointerException` via `Objects.requireNonNull` for a missing one), or it normalizes when the mapping is total and lossless — clamping a bounded number, trimming insignificant whitespace. When in doubt, reject.
- **Test both sides of every uncodified invariant.** Write the property on valid values and a test that the constructor refuses or normalizes the illegal ones. The negative space is half the contract; an untested constructor is an unproven invariant.
- **A type with no illegal state needs no ceremony.** `record Point(int x, int y) {}` — every pair of `int`s is a legal point, so there is nothing to reject. Do not add a constructor where the type already makes all states legal.

## Sealed interfaces and records are the ADT; switch exhaustively

The central rule of this file: an invalid value should not type-check. A closed set of alternatives is a `sealed interface` permitting a fixed set of `record`s, matched with an exhaustive `switch` — the compiler flags a missing case as a compile error, not a `default` fall-through at run time.

- **Model a closed sum type as a `sealed interface` with a `permits` clause and one `record` per case.** The compiler knows the alternatives are closed, so a `switch` over the type needs no `default`; add a case and every non-exhaustive switch fails to compile — the same guarantee Scala's `enum` and Rust's `match` give.

```java
sealed interface Shape permits Circle, Rectangle {}
record Circle(double radius) implements Shape {}
record Rectangle(double width, double height) implements Shape {}

// Exhaustive by construction: no default. Add a Shape and this switch stops compiling.
static double area(Shape s) {
    return switch (s) {
        case Circle(double radius)          -> Math.PI * radius * radius;
        case Rectangle(double w, double h)  -> w * h;
    };
}
```

- **Destructure with a record pattern in the same `switch`** — `case Circle(double radius)` binds the component directly rather than calling the accessor, and pairs with the pattern-matching defaults in `java-style.md`.
- **Reach for an `enum` when the cases carry no data**, a `sealed interface` when each case carries its own fields; both give the compiler an exhaustive switch. Reserve a `sealed abstract class` for a shared base a record cannot express, and keep it immutable.

## JSpecify nullness: non-null by default, `@Nullable` the exception

This is Java's answer to Scala's "model absence with `Option`, never `null`." Under `@NullMarked` every unannotated reference type is non-null, so `null` becomes a deliberate, annotated choice a null-checker can enforce — the compiler and the checker do the work that scattered `!= null` guards did by hand.

- **Declare `@NullMarked` once at the package or module level**, in `package-info.java`, so non-null is the default across the whole unit and you annotate the exceptions, not the norm (`java-modules.md`).
- **Mark a genuinely-absent reference `@Nullable` and handle it at the boundary.** A `@Nullable` field or parameter forces the reader — and the checker — to account for absence exactly where it can occur, rather than everywhere.
- **Prefer `Optional<T>` for a return that may be absent; reserve `@Nullable` for fields and parameters.** Bloch cautions against `Optional` in fields and collections, so use `@Nullable` there — and never return `null` for an absent collection; return an empty one.

```java
@NullMarked
package com.example.credit;   // package-info.java: every reference below is non-null unless marked

import org.jspecify.annotations.Nullable;

record Borrower(String name, @Nullable String parentEntity) {}   // name required; parent optional
```

## Ban primitive obsession; validate in the canonical constructor

A bare `String`, `long`, or `BigDecimal` carries no domain meaning and lets a caller pass the wrong one — an account id where an order id is wanted, a raw amount with no currency. Item 62 is direct: avoid strings where a purpose-built type fits. Wrap it, and make the wrapper's canonical constructor the one gate every value passes.

- **Give every scalar with a domain meaning its own record wrapper.** `record OrderId(String value) {}` is distinct at compile time from `AccountId`, so the two cannot be transposed in a call. This is the value object of `craft-domain-modeling.md` expressed in Java, and it costs one line.
- **Validate in the compact canonical constructor so a constructed record is always valid.** The compact form runs before the fields are assigned; reject or normalize there, and no other code path can build an invalid instance.
- **Wrap identifiers, money amounts, quantities, and codes** — the categories where Item 62 calls a string the wrong type. Two related fields become two named, typed components, never a single untyped map or a delimited string.

```java
record Money(BigDecimal amount, Currency currency) {
    Money {                                            // compact canonical constructor
        Objects.requireNonNull(amount, "amount");
        Objects.requireNonNull(currency, "currency");
        if (amount.scale() > currency.getDefaultFractionDigits()) {
            throw new IllegalArgumentException("amount " + amount + " too precise for " + currency);
        }
    }
}
```

## Records are immutable — keep them that way

A record is shallowly immutable by construction: final components, no setters, structural `equals`/`hashCode`. Item 17 is to keep it that way through the components, so the value stays safe to share and safe to key a map on.

- **Defensively copy any mutable component in the canonical constructor.** `record Deal(List<Covenant> covenants) { Deal { covenants = List.copyOf(covenants); } }` — otherwise a caller holding the original list mutates the record's state behind its back (Item 50).
- **"Change" means construct a new value, never mutate.** There is no setter; a revised deal is a new `Deal`. This is the immutable value-object rule, and it is what lets `equals` stay stable for the object's lifetime.
- **Do not smuggle in a mutable static or a hidden field.** Two equal records must be interchangeable; a mutable field the accessors ignore breaks that contract and the `hashCode` that depends on it.

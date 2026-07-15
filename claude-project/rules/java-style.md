---
paths:
  - "**/*.java"
---

# Java style and idioms

The base layer of Java discipline: formatting, naming, control flow, and the modern-syntax defaults — records, sealed hierarchies, pattern matching, and switch expressions — a Java 21 codebase reaches for first. Sources: *Effective Java* 3rd ed (Bloch — Item 17 minimize mutability, Item 34 enums over int constants, Items 54–55 collections and `Optional`, Item 68 naming conventions), the google-java-format documentation (github.com/google/google-java-format), and the Java 21 Language Specification with the JEPs that landed the modern surface — records (JEP 395), sealed classes (JEP 409), pattern matching for `switch` (JEP 441), record patterns (JEP 440), switch expressions (JEP 361), and `var` local-variable type inference (JEP 286). The version floor is Java 21 LTS. The rule exists because Java gives more than one way to write nearly everything, and the house spends that choice once, here, on a single standard rather than re-litigating it per file — with a stated default wherever the canon leaves the call open.

> See `craft-complexity.md` for why one consistent vocabulary lowers cognitive load, `craft-documentation.md` for the language-neutral comment discipline the Javadoc mechanics here implement, `java-types.md` for record and sealed-hierarchy ADT modeling, `java-errors.md` for exceptions and `Optional` at the failure boundary, `java-concurrency.md` for the virtual-thread and structured-concurrency idioms, `java-modules.md` for package layout and the module system, and `java-testing.md`, `java-security.md`, and `java-llm.md` for the test, trust, and SDK boundaries.

## Formatting

- **Run google-java-format on every file; never hand-align.** The machine owns indentation, wrapping, and import order — 2-space block indentation, a 100-column limit, and sorted imports — so the formatting debate does not exist. Do not re-align a table of assignments or wrap a chain by hand; the formatter decides.
- **Formatting is a build gate, not a cleanup step: the build fails on unformatted code.** Wire google-java-format in check mode into the build (`--set-exit-if-changed` on the CLI, or the Spotless `spotlessCheck` task in Maven or Gradle) so an unformatted file fails CI rather than being silently reformatted later. The local fix you run before committing is the same tool with `--replace` (or `spotlessApply`).
- **Do not fight a formatter decision by reflowing around it.** If a line the formatter produces reads badly, the fix is a shorter expression or an extracted local, not a manual override the next format run will revert.

```java
// google-java-format: 2-space indent, 100-column wrap, sorted imports — the machine decides.
var total = orders.stream().map(Order::amount).reduce(Money.ZERO, Money::plus);
```

## Records and sealed hierarchies

Records and sealed types are the default shapes, not advanced options: a record is the honest spelling of an immutable data carrier, and a sealed hierarchy is the honest spelling of a closed set of alternatives.

- **Model an immutable data carrier as a `record`, not a hand-written class with fields, constructor, accessors, and `equals`/`hashCode`.** A record states intent in one line and generates the boilerplate correctly; add a compact constructor only to validate or normalize components.
- **Model a closed set of alternatives as a `sealed interface` (or sealed class) with an explicit `permits` list.** The compiler then knows the full set, which is what makes an exhaustive `switch` with no `default` possible downstream (see Control flow).
- **Keep a record shallowly immutable: no setter, no state-carrying non-component field.** If a component is a mutable collection, defensively copy it in the compact constructor and hand out an unmodifiable view.

```java
sealed interface Shape permits Circle, Rectangle {}
record Circle(double radius) implements Shape {}
record Rectangle(double width, double height) implements Shape {}
```

## Naming

- **Packages all-lowercase, types `UpperCamelCase`, methods and fields `lowerCamelCase`, constants `SCREAMING_SNAKE_CASE`, type parameters single uppercase letters** — `T`, `E`, `K`, `V`, `R` (*Effective Java* Item 68). Unlike Scala, a Java constant is genuinely screaming-snake (`static final int MAX_RETRIES = 3`); do not carry a Scala habit across.
- **JavaBeans `getX`/`setX` accessors are conventional in Java — keep them where a framework or convention expects them.** But a `record` accessor is just the component name — call `point.x()`, not `point.getX()`, and do not hand-write get-prefixed accessors onto a record.
- **Name for meaning; avoid abbreviation.** A descriptive `pendingCount` beats a cryptic `pc`; scale name length with scope, so a fold accumulator may be short while an exported method is spelled out. Keep the domain term identical across speech, docs, and code (`craft-complexity.md`).
- **Give a dangerous-but-occasionally-needed operation a longer, deliberately clunkier name** (`copyOfUnvalidated`, not a tempting short alias) so a caller reaches for it consciously.

## Control flow and expressions

- **Prefer the switch expression to the switch statement; let it yield a value with arrow labels.** Assign the result of a `switch` rather than mutating a variable across `case` blocks, and use `case ... -> ...` arrows, which do not fall through.
- **Make a `switch` over a sealed type exhaustive and drop the `default`.** With every permitted subtype covered the compiler proves exhaustiveness; a catch-all `default` only hides the compile error you want when a new subtype is added.
- **Deconstruct with record patterns and `instanceof` patterns instead of casting.** A `case Circle(double r)` binds the component directly — no cast, no separate accessor call. (Java 25 extends patterns to primitive types via JEP 507, still preview — do not depend on it under the Java 21 floor.)
- **Use `var` for a local whose initializer makes the type obvious; spell the type out where `var` would hide something the reader needs.** `var orders = new ArrayList<Order>()` is clear; `var result = compute()` that returns an unobvious type is not — name the type there.
- **Handle the empty or failure case first and keep the success path at the left margin.** A guard that returns early beats nesting the happy path inside `else`.

```java
String describe(Shape shape) {
  return switch (shape) {
    case Circle(double r) -> "circle r=" + r;
    case Rectangle(double w, double h) -> "rect " + w + "x" + h;
  };
}
```

## Immutability

- **Make every field `final` unless a concrete reason forbids it, and prefer immutable types** (*Effective Java* Item 17). Immutable objects are thread-safe by construction and cannot be observed in an inconsistent state; a record enforces this for its components.
- **Defensively copy a mutable component on the way in and, where it could escape, on the way out** (Item 50). Storing the caller's `List` directly lets them mutate your internals after construction.
- **Prefer the immutable factories to a mutable collection that escapes a boundary** — `List.of`, `Map.of`, `List.copyOf` return unmodifiable collections; use a builder or a `mutable` collection only as a contained local, never in a type that crosses a module seam.

```java
record Deal(String id, List<Covenant> covenants) {
  Deal {
    covenants = List.copyOf(covenants); // defensive, unmodifiable
  }
}
```

## Collections and Optional

- **Return an empty collection, never `null`** (*Effective Java* Item 54). An empty `List` is an ordinary case the caller iterates without a guard; a `null` is a landmine.
- **Model a possibly-absent return with `Optional`, judiciously** (Item 55): never for a collection, never as a field or method parameter, and never call `Optional.get()` without proof it is present. Combine with `map`, `flatMap`, `orElse`, and `orElseGet`.
- **Reach for the stream and collection combinators over a manual index loop — but stop where a stream only obscures a plain loop.** The combinator names the intent; a one-line `for` sometimes reads more plainly than a contorted stream.

```java
Optional<Status> latestStatus(List<Event> events) {
  return events.stream()
      .filter(Event::isComplete)
      .max(comparing(Event::at))
      .map(Event::status);
}
```

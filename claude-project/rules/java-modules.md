---
paths:
  - "**/*.java"
---

# Java modules

How to organize packages, draw the module boundary, and decide what is public. Sources of record: Joshua Bloch, *Effective Java* (3rd ed) — Item 15 (minimize the accessibility of classes and members), Item 16 (in public classes, use accessor methods, not public fields), and Chapter 4 on classes and interfaces; and the Java Platform Module System (JPMS, JEP 261) documentation. Floor: Java 21. One house rule governs the rest: **a package owns one feature and exposes as little as it can get away with.**

> See `java-types.md` for the value types and sealed hierarchies these packages pass, `java-concurrency.md` for the effect and threading seam at the boundary, `java-style.md` for naming and layout, `craft-abstraction.md` for the specification-and-encapsulation theory underneath a narrow public surface, and `craft-complexity.md` for deep modules and the dependency-versus-obscurity frame.

## Package by feature, not by layer

The default Java tutorial split — `controllers/`, `services/`, `repositories/` — organizes by technical role, so a single feature is smeared across three packages and no package can be read, tested, or moved as a unit. Organize by feature instead: a package holds one feature's model, its logic, and its boundary together.

- **Give each feature its own package holding its model, logic, and boundary.** `billing`, `pricing`, `scheduling` — each package is the whole feature, so understanding it means reading one directory and moving it means moving one directory. The package name is the domain concept, never `utils`, `common`, `helpers`, or a bare `core` grab-bag (`craft-domain-modeling.md`).
- **Do not split horizontally by technical role.** A `services/` package that collects every feature's service class maximizes change amplification: one feature's change touches three packages, and each package depends on all the others. Feature packages keep a change local.
- **Let the boundary class be the only door in.** Each feature package exposes one public entry type (a facade, a service interface); the model, the mappers, and the helpers behind it stay package-private so they can be reshaped without breaking callers (`craft-complexity.md`: deep modules, narrow interfaces).
- **Draw the package seam along the domain, not the framework.** A feature package is a bounded context — what changes together lives together. When two features start reaching into each other's internals, the seam is wrong; either they are one feature or the shared piece belongs in a third package they both depend on.

## Minimize accessibility: package-private by default

Bloch's Item 15 is the governing rule: make each class and member as inaccessible as the design allows. Package-private is the default access level in Java for a reason — reach past it only for the deliberate API surface.

- **Default every class and member to package-private; promote to `public` only for the intended API.** A type is `public` because callers in another package must name it, not because it happened to be written first. Package-private types can be merged, renamed, or deleted without a downstream break.
- **Never expose a public mutable field.** Item 16: a public class exposes state through accessor methods, not public fields, so the representation stays free to change. The only public field permitted is a genuine constant — `public static final` on an immutable value.
- **Prefer package-private over `protected`.** `protected` is part of the exported API and commits you to a subclassing contract most classes never wanted; use it only when an extension point is deliberate.

```java
package billing;

// The one public door: an interface callers depend on.
public interface Invoicer {
    Invoice issue(Order order);
}

// The implementation and its helpers are package-private — invisible outside billing.
final class LineItemInvoicer implements Invoicer {
    private final TaxTable taxes;          // no public field
    LineItemInvoicer(TaxTable taxes) { this.taxes = taxes; }

    @Override public Invoice issue(Order order) { /* ... */ }
}

// Constants are the one public-field exception.
final class Billing {
    public static final int MAX_LINE_ITEMS = 500;
    private Billing() {}
}
```

## Cap the public surface at about seven names

A boundary is a contract, and a contract the reader cannot hold in their head is doing too much. Carry the same cap the Scala module set uses.

- **Keep a package or module boundary under about seven public names.** Count the public types plus the public static entry points a caller must know. Past roughly seven, the package has more than one responsibility — split it along the seam that keeps each half cohesive.
- **Count names, not methods.** A single public interface with several methods is one name on the boundary; seven such interfaces is not. The cap is about how many independent things a caller must learn to use the package, which is the real cognitive load (`craft-complexity.md`).
- **Treat a growing surface as a design signal, not a nuisance.** When a package pushes past the cap, the fix is to extract a feature, not to relax the rule. A wide surface is change amplification waiting to happen.

## Depend on interfaces; keep the dependency direction acyclic

- **Depend on an interface, not a concrete implementation.** A caller names `Invoicer`, never `LineItemInvoicer`; the implementation is constructed once at the composition root and passed in. This is what lets an implementation be swapped or faked in a test without touching the caller (`craft-abstraction.md`: many implementations behind one specification).
- **Point every dependency arrow one way.** The domain model depends on nothing; features depend on the model; the wiring layer depends on the features. A cycle between two packages means the boundary is in the wrong place — merge them or extract the shared piece into a third package both depend on (`craft-complexity.md`).
- **Wire dependencies explicitly at a single composition root.** Construct the concrete implementations in one place — a `main` method or a small factory — and inject them through constructors. Keep field injection and service-locator lookups out; explicit constructor parameters make the dependency graph readable and testable.

## JPMS is optional: adopt module-info only when it earns its keep

The Java Platform Module System (JPMS) gives strong encapsulation — a package is invisible outside its module unless explicitly exported — and a declared dependency graph the compiler enforces. It is worth adopting for a published library or a large application where the boundary must be enforced across teams; many services run perfectly well on the classpath and gain little from it. This is a per-project call, not a mandate.

- **Package-by-feature and minimal visibility stand with or without JPMS.** The rules above are the primary discipline; a `module-info.java` hardens an already-clean boundary, it does not substitute for one.
- **If you adopt it, `exports` only the API packages and `requires` every dependency explicitly.** The exported set is the same small public surface as above, now enforced by the runtime; everything else — the implementation packages — stays unexported and genuinely unreachable.
- **Avoid automatic modules as a long-run state.** An automatic module (a plain jar on the module path) exports everything and reads everything, which discards the encapsulation JPMS exists to provide. Tolerate one only as a migration step toward a real `module-info.java` for that dependency.
- **Do not open a package unless reflection genuinely requires it.** `opens` grants deep reflective access and reopens the encapsulation `exports` was closing; reserve it for a serialization or injection framework that truly needs it, and scope it with `opens ... to` rather than opening the package to the world.

```java
module com.example.billing {
    requires com.example.model;   // explicit dependency
    exports billing;              // the API package only — implementations stay hidden
}
```

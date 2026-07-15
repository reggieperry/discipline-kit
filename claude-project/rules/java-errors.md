---
paths:
  - "**/*.java"
---

# Java errors

Java routes failure through exceptions, and using that channel well is the difference between a failure that names its cause and one that disappears into an empty catch. The stance is unchecked-by-default: reserve a checked exception for a condition a caller can plausibly recover from, and raise a runtime exception for a programming error that no caller should be catching. Sources: *Effective Java*, 3rd ed. (Bloch) — Items 69–77 on exceptions (using them only for exceptional conditions, checked versus unchecked, the standard types, translating to the right abstraction, failure-capture detail, failure atomicity, and never ignoring one), Item 9 on `try`-with-resources, and Item 55 on returning `Optional` judiciously — and the Java 21 language documentation, the floor for this set. The design principle behind several of these rules — define errors out of existence — comes from `craft-complexity.md`.

> See `java-types.md` for the domain value types and the null-free boundary, `java-concurrency.md` for exceptions crossing a thread or an executor, `java-style.md` for the guard-clause control flow, `java-testing.md` for asserting the thrown type and message, and `craft-complexity.md` for defining errors away.

## Checked for recoverable, runtime for programming errors

- **Reserve a checked exception for a condition the caller can plausibly recover from; raise a runtime exception for a programming error.** Bloch's line (Item 70): a checked exception forces the caller to confront a failure they might act on — a file that is not there, a connection that dropped — while a `RuntimeException` signals a precondition violation or a broken invariant no caller can sensibly handle. If the only thing a caller can do is propagate, the checked exception buys boilerplate and nothing else.
- **Do not checked-exception-spam.** Item 71: an API that throws a checked exception no caller can act on pushes a `try`/`catch` onto every call site for zero recovery. Prefer an unchecked exception, or restructure so the failure becomes a value the caller queries first — a state-testing method, or an `Optional` return.
- **Favor the standard exceptions (Item 72).** `IllegalArgumentException` for a bad argument value, `IllegalStateException` for a bad receiver state, `NullPointerException` for a forbidden null, `IndexOutOfBoundsException`, `UnsupportedOperationException`. Reusing them makes the API read like the platform; a bespoke `BadArgumentException` that means exactly `IllegalArgumentException` is noise a reader has to decode.

## Fail fast: precondition checks at the boundary

- **Validate arguments at the top of the method, before any work runs.** A guard clause that throws on bad input keeps the failure close to its cause and leaves the success path at the left margin — no arrow of nested `if`s. `Objects.requireNonNull(x, "x")` for a forbidden null, an explicit `if` for a range or emptiness check.

```java
public Order place(Customer customer, List<LineItem> items) {
    Objects.requireNonNull(customer, "customer");
    if (items.isEmpty()) {
        throw new IllegalArgumentException("items must be non-empty");
    }
    // success path stays at the left margin from here down
    return Order.of(customer, items);
}
```

- **Name the offending value in the check** — `requireNonNull`'s second argument names the parameter, and a range message states the bound and the value that missed it. A check that throws a bare `IllegalArgumentException` with no message diagnoses nothing.
- **Strive for failure atomicity (Item 76).** A method that throws should leave the receiver in the state it held before the call. Validate before you mutate, so a rejected argument never leaves a half-updated object behind.

## `try`-with-resources always, never a manual finally-close

- **Open every `AutoCloseable` in a `try`-with-resources; never close one in a hand-written `finally`.** Item 9: a manual `try`/`finally` gets suppression wrong — an exception thrown by `close()` masks the real exception from the body — and nested `finally` blocks get it wronger. `try`-with-resources closes in reverse order and attaches a close failure as a *suppressed* exception on the primary one, so both survive to the log.

```java
try (var in = Files.newInputStream(path);
     var out = Files.newOutputStream(dest)) {
    in.transferTo(out);
}   // both closed in reverse order; a close failure is suppressed, not lost
```

- **A manual finally-close is a defect even when it looks correct.** The version that closes and reports both failures is exactly what `try`-with-resources already is; hand-rolling it invites the masking bug the construct was built to remove.

## Never swallow an exception

- **An empty catch, or one that only logs and drops the failure, is a defect (Item 77).** Rethrow it, wrap it with context, or actually handle it — recover, retry, fall back to a documented default. A catch that does none of these loses the failure exactly where it was cheapest to see, and the bug resurfaces later with no trace of its origin.
- **If you genuinely must ignore one, say why.** Name the caught variable `ignored` and leave a comment stating the reason the failure is safe to drop. This is rare; treat every empty catch as a defect until a comment justifies it.
- **Handle each error exactly once.** Do not both log an exception and rethrow it — that produces duplicate, confusing log lines. Log where you actually handle the failure, or propagate it with added context, not both.

## `Optional` as a return type only

- **Return `Optional<T>` to signal a possibly-absent result; never make it a field, a parameter, or a collection element (Item 55).** An `Optional` return states at the type level that a value may be absent and forces the caller to confront the empty case instead of tripping over a null later. A field of type `Optional` bloats the object and reintroduces the null it was meant to banish (the field reference itself can be null); an `Optional` parameter pushes the wrapping onto every caller; and an `Optional<T>` inside a collection is strictly worse than an absent key or an empty collection.
- **Never return a null `Optional`, and never call `get()` unguarded.** Return `Optional.empty()`, and consume with `map`, `filter`, `orElse`, `orElseThrow`, or `ifPresent` — not an `isPresent()`/`get()` pair, which is the null check you were escaping moved one type over. Use `OptionalInt`/`OptionalLong`/`OptionalDouble` for a primitive rather than boxing.

```java
public Optional<Account> findByEmail(String email) {
    return repository.lookup(email);   // Optional.empty() when absent, never null
}

String owner = findByEmail(email)
    .map(Account::owner)
    .orElseThrow(() -> new AccountLookupException("no account for " + email));
```

## Throw at the right abstraction, with context

- **Translate a low-level exception to one that fits your abstraction, chaining the cause (Item 73).** Catch a `SQLException` at the repository boundary and throw a domain exception whose cause is the original, so the stack trace keeps the root while the type reads at the caller's level. Use the `Throwable(String, Throwable)` constructor; never discard the cause.

```java
try {
    return jdbc.queryForObject(sql, mapper, id);
} catch (DataAccessException cause) {
    throw new AccountLookupException("no account for id " + id, cause);
}
```

- **Put failure-capture information in the message (Item 75).** Name the offending value and the bound it violated — "index 7 not in [0, 5)" beats "index out of bounds" — so a log line diagnoses without a debugger. Never leak a secret, a token, or a credential path into an exception message.
- **Never `catch (Exception)` — or `Throwable` — where a specific type is meant.** A blanket catch swallows the `RuntimeException` that signals a bug you would want to fail loudly, alongside the checked one you meant to handle. Catch the narrowest type, and use a multi-catch (`catch (IOException | TimeoutException e)`) when two specific types share one handler.
- **Prefer redefining an operation so the error case becomes the normal case** over adding another failure mode — an `ensureAbsent` that succeeds when the thing is already gone needs no exception at all. Where you cannot define the error away, handle it as low as you can or aggregate many handlers into one high in the call path; fewer failure sites means simpler, more reliable code (`craft-complexity.md`).

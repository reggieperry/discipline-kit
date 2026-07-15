---
paths:
  - "**/*.java"
---

# Java concurrency

Threading, shared state, and task composition for code that does real I/O — network calls, database round-trips, file reads — on a Java 21 platform floor. Java 21 changes the default: virtual threads make a blocking call cheap, so a thread no longer has to be rationed against a scarce pool, and the design pressure shifts from "reuse threads" to "don't share mutable state." Sources: Brian Goetz, Tim Peierls, Joshua Bloch, Joseph Bowbeer, David Holmes, and Doug Lea, *Java Concurrency in Practice* (the shared-state, safe-publication, and building-blocks chapters); JEP 444, *Virtual Threads* (final in Java 21); JEP 453, *Structured Concurrency* (preview in Java 21); and the `java.util.concurrent` package documentation, including the value-based-class synchronization warning.

> See `java-types.md` for the immutable-record and sealed-type modeling that keeps shared state read-only, `java-errors.md` for exception and `InterruptedException` handling across task boundaries, `java-style.md` for naming and the try-with-resources convention, `java-testing.md` for exercising concurrent code deterministically, and `craft-complexity.md` for keeping concurrency policy out of the domain logic so the logic stays unit-testable.

## Virtual threads are the default for blocking I/O

- **Run each blocking task on its own virtual thread.** For I/O-bound work, `Executors.newVirtualThreadPerTaskExecutor()` or `Thread.ofVirtual().start(...)` is the default. A virtual thread is cheap to create and to block, so the thread-per-task model that was once wasteful is now correct — you get one thread per in-flight request and the runtime multiplexes them onto a handful of carrier threads.
- **Do not pool virtual threads.** Pooling exists to amortize the cost of a scarce resource, and virtual threads are neither scarce nor costly. Create one per task and let it end. A fixed `ThreadPoolExecutor` of virtual threads reintroduces the queueing limit the model removes.
- **Do not cache a virtual thread in a `ThreadLocal`.** With potentially millions of short-lived threads, a per-thread cache no longer amortizes anything — it becomes a per-task allocation that defeats the point and can retain memory. Pass state as parameters instead.

```java
// One virtual thread per task; the executor is an AutoCloseable that joins on close.
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    List<Future<Score>> futures = requests.stream()
        .map(req -> executor.submit(() -> scorer.callBlocking(req)))
        .toList();
    for (var f : futures) results.add(f.get());
}
```

## Structured concurrency for fan-out/fan-in

- **Compose concurrent subtasks with `StructuredTaskScope`, not bare `submit` you then juggle by hand.** A scope binds the subtasks' lifetimes to a syntactic block: fork the children, join once, and the scope guarantees none outlives the block — on success, on failure, or on cancellation. `ShutdownOnFailure` cancels the siblings the moment one subtask throws, which is the fan-out/fan-in idiom for "call three services, fail fast if any fails."
- **At the Java 21 floor `StructuredTaskScope` is a preview API** (JEP 453), and it has kept evolving through further preview rounds in later releases (its API shifted between previews) — so confirm the exact GA version and shape for your JDK, and until it is final in your target release gate it behind `--enable-preview` deliberately: an explicit, reviewed compiler and runtime flag, never an accidental one.

```java
// --enable-preview at Java 21. Fork independent calls, fail fast, propagate cleanly.
try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
    Subtask<Terms>   terms   = scope.fork(() -> loadTerms(dealId));
    Subtask<Ratings> ratings = scope.fork(() -> loadRatings(dealId));
    scope.join().throwIfFailed();          // wait for both; rethrow the first failure
    return new Deal(terms.get(), ratings.get());
}
```

## Immutability first

- **The safest shared state is no shared mutable state.** Prefer immutable `record` types and `final` fields for anything two threads can see; an object that cannot change needs no lock, no `volatile`, and no reasoning about visibility. This pairs with `java-types.md`'s immutable-record modeling — make the data immutable at the type level and most concurrency problems never arise.
- **Publish safely when you must share.** A mutable object handed to another thread has to be published through a safe channel — a `final` field, a `volatile` field, an `AtomicReference`, or a concurrent collection — or the reader may see a partially constructed value. Do not rely on a plain field write being visible across threads.
- **Confine mutable state to one thread when you can.** State that never leaves the thread that owns it needs no synchronization at all; a virtual-thread-per-task design makes per-task confinement the natural shape.

## Never synchronize on a value-based class

- **Do not `synchronized` on a boxed primitive, a `String`, an `Optional`, or any value-based class.** Their identity is not guaranteed — two equal values may or may not be the same instance — so a lock taken on one is not a lock any other holder will respect, and the JLS and `java.util.concurrent` docs warn the behavior is unspecified. Lock on a dedicated `private final Object lock = new Object();` or, preferably, a `java.util.concurrent.locks.Lock`.

```java
// Wrong: identity of a boxed Long or an interned String is not guaranteed.
synchronized (accountId) { ... }          // accountId is a Long — undefined behavior

// Right: a dedicated lock object with a stable identity.
private final Object lock = new Object();
synchronized (lock) { ... }
```

## Prefer the java.util.concurrent primitives over hand-rolled locking

- **Reach for the building blocks before `synchronized`.** A `ConcurrentHashMap`, an `AtomicLong`, a `ReentrantLock`, a `CountDownLatch`, or a `BlockingQueue` expresses intent, is tested, and composes; a hand-rolled `synchronized`/`wait`/`notify` protocol is the last resort, not the reach. Per *Java Concurrency in Practice*, favor the standard concurrent collections and synchronizers over building your own.
- **Do not spawn a raw `new Thread(...)` for task work.** Submit to an executor so the scheduling policy is one decision in one place; a bare thread you `start` and forget is unowned and unmonitored.
- **If you must use a low-level monitor, guard the wait correctly.** A `wait` always sits in a `while` loop that re-checks the condition — never an `if` — because of spurious wakeups; but prefer a `Condition` on an explicit `Lock`, or a higher-level synchronizer, over writing that loop at all.

## Don't pin or block a carrier thread

- **Guard against blocking a platform carrier thread.** A virtual thread unmounts from its carrier at a blocking point so the carrier stays free — unless the blocking happens inside a `synchronized` block or a native call, which *pins* the virtual thread to its carrier and blocks the platform thread underneath it. Enough pinned threads and the carrier pool starves.
- **Replace `synchronized` around a blocking call with a `ReentrantLock`.** A `Lock` lets the virtual thread unmount while it waits, so the guarded blocking call no longer pins. Where a hot path holds a monitor across I/O, migrate it to an explicit lock and document why.

```java
// Pins the virtual thread across the I/O: the monitor is held while blocking.
synchronized (this) { return db.query(sql); }   // avoid — pins the carrier

// A ReentrantLock lets the virtual thread unmount while the query blocks.
private final ReentrantLock lock = new ReentrantLock();
lock.lock();
try { return db.query(sql); } finally { lock.unlock(); }
```

- **Document any residual pinning risk at the call site.** If a third-party library holds a monitor across a blocking call and you cannot avoid it, note it where the code lives so the next reader knows the carrier can stall there.

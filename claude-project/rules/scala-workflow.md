---
paths:
  - "**/*.scala"
  - "**/*.sc"
  - "build.sbt"
---

# Scala build loop and when to stop

How to drive the compiler while working, and the conditions under which to stop and ask rather than
keep trying. Everything else in the `scala-*` set is about what the code should *be*; this one is
about how to get there without burning the session on cold JVM starts and error cascades. Sources:
the sbt server and thin-client documentation (`sbt --client`, sbt 1.4+), the Scala 3 reporting
behaviour under `-explain`, and a measurement taken on a reference Scala 3 repository (below).

> See `craft-tdd.md` for the red-green cadence this loop serves — the loop is how you get to a fast
> red bar, not a substitute for having one; `scala-testing.md` for what to write once it compiles;
> and `craft-complexity.md` for design-it-twice, which is what the stop conditions below buy time for.

## Compile with the thin client, not a cold JVM

A bare `sbt` invocation pays a full JVM and build-load cost every time. The thin client talks to a
persistent server and the difference is not marginal.

**Measured** (sbt 1.12, a mid-sized multi-module build, `Test/compile`, no source change):

| | |
|---|--:|
| `sbt --client`, server cold (starts one) | 8.3 s |
| `sbt --client`, server warm | **0.42 s** |
| `sbt -batch Test/compile` | 12–14 s |
| `sbt -batch check` (full gate) | 37–48 s |

So the inner loop is:

```bash
sbt --client -error "Test/compile" 2>&1 | head -60
```

- **`Test/compile`, not `compile`** — it compiles both source sets, so a broken test source is caught
  in the same pass rather than surfacing later as a failed gate.
- **Always bound the output.** Pipe through `head`. Do not read a full sbt log looking for the problem.
- **If the client reports no server**, run `sbt --client shutdown` once and retry rather than falling
  back to a bare `sbt` — a stale server socket is the usual cause.
- **Never run the full suite to find out whether something compiles.** That is the 48-second command
  answering a question the 0.4-second one answers.

Run the full check task when you are *finished* — it is the gate, and the commit path runs it anyway.
It is not an inner-loop command.

## Read the first error, not the last

Scala 3 reports cascades. A single genuine error commonly produces several downstream ones that
vanish when it is fixed, so the last error in the log is usually the least informative thing in it.

- **Fix the first error, then recompile.** Do not triage the whole list.
- With `-explain` on (`scala-modules.md` puts it in the shared `scalacOptions`), the first error
  carries its own reasoning — read that before forming a theory.
- An exhaustivity error (`E029`) or an unused-symbol error (`E198`) is usually telling you something
  true about the design, not obstructing you. `-Werror` makes both fatal on purpose.

## Formatting is the gate's job, not the loop's

- **Do not hand-adjust formatting.** `scalafmt` owns it (`scala-style.md`).
- **Do not run `scalafmtAll` speculatively** in the inner loop either. Run it when `sbt check` reports
  a formatting failure, which is the only time it is needed — the check is what decides.

## Stop and ask rather than guess

Stop when any of these is true. Each is a case where continuing produces confident-looking work built
on a decision that was not yours to make.

- **The task needs a dependency or version that is not already in the build.** Do not add one
  unprompted; `scala-modules.md` treats the dependency surface as a reviewed decision.
- **Two reasonable designs differ in public API shape.** That is a `design-it-twice` moment and the
  choice belongs to whoever owns the interface.
- **A fix would require changing a signature you did not write**, or one that other code depends on.
- **The same compile error survives three fix attempts.** Report the error and what you tried. Three
  failures means the model of the problem is wrong, and a fourth attempt is guessing with better
  syntax. This is the cheapest anti-thrash rule available and the easiest to ignore.

Stopping is not failure to deliver. Delivering something that compiles by accident is worse than
saying which decision is blocked.

## Provenance

The compile-loop and stop-condition material here is adapted from an external Scala 3 conventions
template. Four of that template's positions were **deliberately not taken**, because they contradict
settled rules in this set: it prefers significant indentation over braces (`scala-style.md` defaults
to braces in shared code), forbids opaque types and variance annotations (`scala-types.md` is built
on both), says not to write tests unless asked (`craft-tdd.md` makes a failing test first the golden
rule), and offers ZIO as a stack option (`scala-modules.md` commits to one effect system). The measurements above were taken
for this rule, not quoted from the template.

---
paths:
  - "**/*.go"
  - "**/*.sh"
  - "**/*.py"
  - "**/*.scala"
  - "**/*.sc"
  - "scripts/**"
---

# Measuring, and why an instrument reads clean when it is not looking

**Enforcement grade:** review and convention, entirely — and this is the file where that matters most. No check notices a metric bounded by its own workload, a filtered failure signal, a wait loop with no deadline, or a statistic whose assumptions were never tested against a known-healthy series. Every rule here was paid for by a defect a green build did not catch.

Load this when writing or reading a benchmark, soak harness, metric, health check, wait
loop or CI gate, or when interpreting a number a run produced. Otherwise skip it.

Every rule here was paid for by a real defect, and each shares a shape: **the instrument
reported success while not actually watching.** Green, zero, flat, silent and "all checks
passed" each have two meanings — *nothing is wrong*, and *nothing is being looked at* —
and they are indistinguishable from outside unless you build in the difference.

> See `craft-tdd.md` for the red bar as evidence rather than ceremony. That rule makes a
> test prove it can fail; this one makes a measurement prove it can.

## Prove the instrument can fail, before believing that it passed

- **Run it once with its subject removed** — a no-op implementation, a disconnected
  source, an empty workload — and record that reading beside the live one. If they match,
  you measured nothing. A memory oracle that kept full event histories grew 4.4 → 13.2 MB
  against a null subject, and the growth was nearly billed to the code under test.
- **Calibrate with an effect shaped like the fault you are hunting.** A memory gauge ran
  an hour and produced byte-identical readings with a standard deviation of exactly zero:
  the value only updates after a garbage collection, and with no traffic none ever ran.
  Adding churn was the obvious fix and it *also* read byte-identical — collections now
  ran, but discarded payloads are never promoted, so the number had nothing to vary by.
  Churn is not retention. Hold a known constant set live, above the collector's occupancy
  trigger, and require the gauge to move by the amount you held.
- **A measured zero deserves more scrutiny than a measured problem.** The zero above would
  have been *used*: a noise floor of zero justifies declaring any deviation, of any size,
  to be within tolerance.
- **Emit an explicit VOID state, distinct from a pass.** When a harness can tell it did not
  observe anything — nothing collected, the reading never moved, no sample cleared the
  filter — it must say so rather than print the flattering number.
- **Make it fail on purpose, and again after every change to the instrument or its
  workload.** Reintroducing a fixed defect and requiring the check to catch it is the
  cheapest form. When a mutant SURVIVES, check first whether every test supplies the
  setting explicitly — if so, nothing pins the *default*, and the default is what ships.
  Add one check that constructs the thing with no configuration at all. Then either write
  the check that kills it or drop the defence; never leave it claiming cover it lacks.
- **A metric bounded by its own workload cannot detect growth.** Three health metrics once
  read steady because their maximum was set by the traffic driving them. Ask of every
  metric: what value would this take if the fault were present and large?
- **A ceiling is a claim about two systems.** Perturbing downward proves the instrument
  notices damage; it proves nothing about headroom. Before reporting a limit, scale the
  driver until the measured number stops rising — a load generator's single-thread
  ~500 MB/s was reported as the runtime's ceiling until the drivers were parallelised, and
  the real figure was fourteen times higher.

## Do not filter away the signal you are about to need

- **Filter the view, never the record**: `cmd 2>&1 | tee run.log | tail -20`. A build tool
  printed `Error compiling project` and **exited 0** while its output went through
  `grep`/`tail`, so a tree did not build for an entire workstream while every suite printed
  a green summary. Both halves were needed: a tool lying in its exit code, and a filter
  removing the line telling the truth.
- **Check exit status AND content; trust neither alone.**
- **Prove the artifact you measured is the one you just built** — compare a hash, not just
  the build's exit code. A compile that silently did not run leaves every downstream number
  scoring the previous build, so a lying build step invalidates the results taken behind
  it, not merely the build.
- **Wait on the thing, not on a proxy for it.** A loop using `pgrep -f "<pattern>"` matched
  its own command line, which contains the pattern. Another polled for a marker that the
  `tail -N` writing the log had already removed. Prefer the completion signal the runtime
  gives you.
- **Every wait loop carries a deadline, exits non-zero on expiry, and prints the condition
  it was waiting for.** A loop whose only exit is success runs until someone notices. Both
  failures above cost half an hour of wall clock for that reason alone, independently of
  why their condition was unreachable — and the next unreachable condition will be a third
  pattern neither bullet names.

## Two samples are not a pattern

- **Do not infer a mechanism from a repeated value.** A count came out as exactly 5 on two
  runs and was written up as proof of a fixed set of five specific events rather than a
  rare race. Later runs gave 4, 0 and 0.
- **Vary candidate causes independently before attributing.** An overhead was reported as
  scaling with one input, from runs in which *two* inputs differed. Measured properly —
  holding each fixed in turn — that input made no difference at all, byte for byte. If the
  numbers came from runs that differed in more than one way, you have a story, not a
  finding.
- **Prefer a magnitude check to a significance test.** A signal that survives every
  statistical test is still not a leak if it works out to a hundredth of a byte per event.
  Convert the effect into the units of the mechanism you are accusing; mechanisms do not
  retain fractions of a byte.

## Check what a statistic reads on a known-healthy series

Three failed in turn on one series, for **three different reasons** — which matters,
because the repair for one does nothing for another:

- **Rising fraction** (what share of steps increased): an asymmetric sawtooth rises in more
  than half its samples *by construction*, so ≥ 0.5 is the null, not a signal. No
  aggregation repairs this; the statistic is simply wrong for the shape.
- **First-versus-last**: two endpoints, one observation each. It reported +5.76 MB/h where
  a fit over the same data gave −3.75.
- **A slope with a confidence interval**: compute the residual lag-1 autocorrelation before
  reporting any interval, and print it beside the interval. Here it measured **+0.94**
  where the test assumes near zero, so the interval was far too narrow. Fitting over block
  means averages the oscillation away and gives the same point estimate with an honest
  one.

**The signature of a broken interval is sub-windows that contradict each other.** One
series fitted "+0.065, excludes zero" while its own halves fitted +0.641 and −0.512, each
also "excluding zero". When splitting the data flips the sign with confidence, the model is
wrong, not the world.

## Measure the noise floor before pre-registering any bound

- **A bound below the instrument's own noise is unfalsifiable.** Establish the floor first,
  under conditions where the instrument actually moves, then register bounds above it.
- **Register before the run, and shrink rather than widen.** A bound written after seeing
  the data is not a bound. If the floor exceeds the effect being hunted, say so and reduce
  the claim — do not relax the threshold until the result passes.
- **Distinguish the single-reading floor from the aggregate one.** Noise on one sample and
  the precision of a fit over thousands of samples are different numbers; using the first
  to reject the second wastes a run that would have worked.
- **Report the limit of what a run establishes, not just its verdict.** "No growth
  demonstrated; this run excludes growth above X" is honest. "No growth" is not, and the
  difference is the part a reader needs.

## Suspect your own harness first

When a measurement surprises you, the instrument is the most likely defect. A timing check
bracketed the harness's own sleep and reported a constant whatever the code did. Write down
what the harness must never do — allocate per sample beyond a known bound, bound a metric
by its own workload, use a statistic whose assumptions are unchecked, filter its own tool
output — and keep that list where the harness lives, because a list nobody can find is a
list nobody applies.

## A requirement that cannot fail is the same defect as a gauge that cannot move

The instruments above watch code. This one watches the *checklist* — and a checklist is written by
the same person, in the same sitting, as the tests it is supposed to audit, so it inherits their
blind spots rather than correcting them.

- **A row naming a family discharges the whole family on one mapping.** "Bilattice laws" was one row
  in a conformance registry, mapped to two suites, counted as covered — while it stood for roughly
  fifty distinct laws, of which four De Morgan identities and one closure property were tested
  nowhere. Nothing could notice: the row was already green. Require a row to state its proposition
  **in words**, and treat a plural family noun with no count as a bucket that must be decomposed. The
  distinguishing question is not whether the statement is plural — it is whether the family's **size
  is pinned**, because a counted family cannot silently shrink and an uncounted one can.
- **Assert the MEMBERS, not the count.** A count survives a reordering, and for a priority-ordered
  vocabulary the order *is* the semantics — a rejection enum whose declaration order fixes which
  reason is reported first will answer the wrong reason after a swap that a cardinality assertion
  waves through. Assert the member list against a literal, and you pin names, order and size at once.
  Measured: on a corpus of 26 closed sets, a reorder was the only mutation that both compiled and
  discriminated, and it was killed by the list assertion and invisible to a count.
- **Deletion is usually the compiler's job, not the test's.** Removing a referenced member fails at
  every use site before any test runs, which is why deletion mutations are a poor way to validate
  this kind of assertion. What the test buys is the case the compiler cannot see: a rename, a
  reorder, or the removal of a member nothing referenced — which is exactly the "shipped but unread"
  symbol that started this.
- **The shape of the set decides what can pin it.** Where the language gives a members list, assert
  it. Where it does not — a sum type with parameterised cases often has none — the only mechanism
  left is exhaustive matching with no wildcard, and that guards *addition* while saying nothing about
  deletion. Say which of the two you have rather than recording the set as covered.
- **An opaque row id hides collectivity.** `LAWTABLE/row1` is unreadable, so no reviewer can see what
  it absorbs. If a row cannot be stated, its coverage cannot be judged.
- **Beware the check that reads the plausible signal instead of the real one.** A first cut flagged
  any statement containing " and ", and over-fired five times in seven: a biconditional with a
  conjunctive right-hand side is one obligation, not two. Run a new check against the existing corpus
  before wiring it in, and count the false positives — a check that cries wolf is one somebody
  eventually edits to shut up. A second worked example, measured the same way: "every closed set must
  have its size pinned" fires on 16 of 26 with 13 of those noise — 81%, the same class as a query
  already demoted for it — while the narrower "every set **whose own doc declares a count** must have
  it pinned" fires on 3 and all 3 are real. Same idea, two orders of magnitude apart in usefulness,
  and only measurement tells them apart.
- **Instruments have this failure in both directions.** One reads propositions and is blind to a type
  that was never written; another reads a promise list and is blind to a promise made only in a
  comment. Neither silence means nothing is wrong. Ask of any completeness instrument: what class of
  omission is invisible to it by construction, and print that count on every run.

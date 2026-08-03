---
paths:
  - "**/*.go"
  - "**/*.py"
  - "**/*.scala"
  - "**/*.sc"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.java"
  - "**/*.sh"
---

# Logging

**Enforcement grade:** review and convention. No check anywhere reads a log statement. The security rules' ban on logging a secret is the one adjacent mechanical neighbour, and only partly: a repo running gitleaks catches a committed credential, never one written to a log at runtime. Levels, structure, correlation, cardinality, and what a log line is *for* are read by a person or by nobody.

What a running program says while it runs. Sources: the OWASP Logging Cheat Sheet; the Twelve-Factor App, factor XI (a log is an event stream the process does not route or manage); the Google SRE book on monitoring signals; *Observability Engineering* (Majors, Fong-Jones, Miranda) for structured wide events over free text; and CWE-117 (log injection) and CWE-532 (information exposure through log files).

**This file does not restate the output discipline the kit already carries.** Those rules are about what an *instrument* says about itself, and they hold unchanged:

- **print the denominator** — `craft-measurement.md`, and `shell-errors.md` for the shell form
- **a query returning nothing must say what it looked at** — the self-audit's second property
- **the three-valued exit vocabulary**, and diagnostics to stderr — `shell-errors.md`
- **never log a secret; sanitize an untrusted string before logging it** — the `*-security.md` set

What follows is the other half: a long-running program's output, where nobody is reading an exit code.

> See `craft-measurement.md` for why silence has two meanings, `craft-documentation.md` for the comment discipline a log message is not a substitute for, the `*-errors.md` set for the error channel a log line must not replace, and the `*-security.md` set for the injection and disclosure classes named here.

## A library returns; a service logs

- **A pure library should log nothing, and needing to is a design signal.** Every diagnostic a total function could emit is already available as a return value, with more information than a line of text and no chance of drifting from what happened. A typed rejection that distinguishes *stale input* from *unauthorized* sends the caller to different remedies; "request refused" sends them to neither.
- **The boundary is where effects begin.** A module that cannot perform I/O cannot log, and that constraint is worth keeping rather than working around — reach for a logging dependency in a pure core and the answer is almost always a richer return type.
- **Render the log line FROM the typed value, not beside it.** A message hand-written at the call site drifts from the case it describes the moment a new case is added; one derived from the value by an exhaustive mapping cannot, because the compiler names the gap.
- **Where a system already emits a committed record — an audit entry, a receipt, a digest-bearing artifact — that is the observability story and a parallel log is a second version of the same fact.** Log that the record was produced and how to find it; do not restate its contents.

## Levels mean something, or they mean nothing

- **Fix what each level is FOR, in one sentence, and hold it.** The common split: `error` — a human must act, and the action is stated; `warn` — the system recovered but the condition should not persist; `info` — a state change an operator would want in the timeline; `debug` — the developer's trace, off in production.
- **`error` for something the program handled and continued past is the fastest way to make errors unreadable.** Once the error stream is mostly noise, the real one is invisible, which is a worse position than not logging at all.
- **Do not log and also return the same failure.** Handle it once. Both, and every failure appears twice from different layers with different wording, and a reader cannot tell one event from two.
- **`debug` is not a dumping ground.** A `debug` line nobody has read in a year is a comment that costs runtime.

## Structured fields, not interpolated prose

- **Emit fields, not sentences.** `event=grounding.failed slot=… reason=timeout attempt=2` can be filtered, counted, and grouped; `"Grounding failed for the thing after retrying"` can only be read. Interpolating a value into a message destroys the one property that makes a log queryable.
- **One wide event beats several narrow ones.** Prefer a single line per unit of work carrying everything known about it to five lines that a reader must reassemble in the right order — especially under concurrency, where they will not be adjacent.
- **Name events from a closed vocabulary and keep it stable.** A message string that gets reworded breaks every filter built on it; an event name is an interface and changing it is a breaking change.
- **Log the units.** A number with no unit in the field name is a number somebody will misread — `wait_ms`, not `wait`.

## Correlation, or you have no trail

- **Carry one id through the whole unit of work and put it on every line.** Without it, concurrent requests interleave into a transcript nobody can separate, and the more traffic the system takes the less its logs are worth.
- **Propagate the id across every boundary the work crosses** — a queue, a subprocess, an outbound call, a thread hand-off. The place a correlation id is most often dropped is exactly where it becomes most valuable.
- **Where work moves between threads or actors, log the hand-off on both sides.** A failure observed by a supervisor is the only account of what happened, because the failing unit returned nothing to anyone.

## What never goes in a log

- **No secrets.** Not a key, a token, a session id, or a password — including inside a URL, an exception message, or a serialized request object. This is where a credential most often escapes a system that handles them carefully everywhere else, because a log is not usually treated as an output.
- **No payload.** Log identifiers, digests, sizes and counts; not the document, the extracted value, or the record contents. A system handling confidential material has a rule about where that material may be written, and a log file is somewhere nobody applied it.
- **No personal data beyond what the log is for**, and where that is unavoidable, decide the retention before writing it. A log is a data store that outlives the request and gets copied into places the original never went (CWE-532).
- **Sanitize anything untrusted before it becomes a line.** A newline or a control character in model output, user input, or a subprocess's stdout forges a log entry (CWE-117). Strip or escape at the logging seam.
- **Redact before assembling, never after.** A line built with the secret in it has already been written by the time a filter would see it.
- **Trace output prints expanded arguments, so it prints secrets.** Enabling a shell's `set -x` or a framework's request tracing around a call that carries a credential writes it out; disable across that call and restore in a way that survives the failure path.

## Volume and cardinality

- **Log per unit of work, not per loop iteration.** A line inside a hot loop is a performance defect and a readability one, and it will be the line that fills the disk during the incident it was supposed to explain.
- **Rate-limit or sample anything that can fire unboundedly.** A retry loop logging every attempt turns one failing dependency into an outage of the logging system.
- **Unbounded-cardinality fields belong in a field, never in the event name.** An event name per user id is not a vocabulary, and it will break whatever indexes it.
- **Decide what happens when the sink is unavailable.** Logging that blocks makes the log a dependency of the work; logging that silently drops means an absent line proves nothing. Pick deliberately and write down which.

## Silence has two meanings here too

`craft-measurement.md`'s central point applies directly to a log, and the failure is easier because nobody checks an exit code:

- **An absent line is not evidence the event did not happen.** It is equally evidence that the level was off, the sink was down, the filter dropped it, or nobody wrote the statement. Before concluding from a quiet log, establish that the line would have appeared.
- **Prove a log path can fire, the same way a test must be able to fail.** A branch whose only observable is a log statement nobody has ever seen is unexercised code, and the error paths — the ones that matter most — are exactly the ones never taken in development.
- **State the retention and the filter beside any conclusion drawn from logs.** "No errors in the last week" and "no errors in the last week that survived a seven-day retention and a level filter set to warn" are different claims.

---
paths:
  - "**/*.java"
---

# Java LLM integration

The boundary where a model's response enters a Java service — the one place this boundary's reliability is earned, and the seam an otherwise well-typed domain shares with an untrusted outside world. Sources: general LLM-integration engineering practice, and the official Java SDK documentation of the relevant providers (the Anthropic and OpenAI Java SDKs) — their structured-output features, client construction, and auth patterns. The floor is Java 21 (records, sealed types, and pattern matching for `switch`). This file is a skeleton: it states each stance at the section level, and its body is marked for fleshing when a real Java LLM project exists to ground the specifics against a resolved SDK version.

> See `java-security.md` for the response as untrusted, network-class input, `java-types.md` for the parsed record as the typed contract, `java-errors.md` for surfacing a parse or validation failure as a value rather than a swallowed exception, and `java-testing.md` for exercising the boundary against malformed and adversarial outputs.

## The SDK-call trust boundary

- **An LLM response is untrusted input.** Treat the model's output the way you treat a network payload — validated and constrained at the boundary before it enters the domain, never trusted because it arrived through your own SDK call. Pairs with `java-security.md`.
- **The SDK response type appears only at the seam.** Convert the provider's response object into a domain type immediately, so the SDK's shape and its nullability do not leak into the core; the domain never imports the provider package.

<!-- flesh out when the project exists -->

## Schema-validated outputs

- **Prefer structured outputs constrained to a schema.** Constrain generation with the SDK's structured-output feature and parse into a record — never scrape a value out of free-form text. Pairs with `java-types.md`.
- **Re-validate the parsed record before the code trusts it.** The schema constrains generation, not a misbehaving model; layer the closed-set, numeric-range, and collection-size checks the wire schema cannot carry as a total validation over the record, returning a result rather than throwing.
- **A parse or validation failure is handled, not swallowed.** Surface it as a typed value the caller must decide on — a failure is a first-class outcome of the call, not an exception to be logged and ignored. Pairs with `java-errors.md`.

```java
// The parsed carrier is a record — the schema and the typed contract in one place.
// Keep it at the boundary; convert to the domain type before the core sees it.
public record VerdictDto(String decision, List<String> reasons, int severity) {}

// Total: a malformed output becomes a typed failure, never an exception.
sealed interface Parsed permits Parsed.Ok, Parsed.Invalid {
    record Ok(Verdict verdict) implements Parsed {}
    record Invalid(String reason) implements Parsed {}
}

static Parsed validate(VerdictDto dto) {
    if (!Set.of("pass", "block").contains(dto.decision()))
        return new Parsed.Invalid("decision not in {pass, block}: " + dto.decision());
    if (dto.severity() < 0 || dto.severity() > 5)
        return new Parsed.Invalid("severity out of range 0..5: " + dto.severity());
    return new Parsed.Ok(Verdict.from(dto));
}
```

<!-- flesh out when the project exists -->

## Prompts as versioned artifacts

- **Prompts live in version control as named, reviewed resources.** A prompt is a specification, not a string literal scattered across call sites; keep each one as a classpath resource keyed by name so a prompt change is a reviewable diff.
- **Load prompts by name and version at the boundary.** The call site references a prompt by its identifier and pins the version it was reviewed against, so a run records which prompt produced its output and two runs stay comparable.

<!-- flesh out when the project exists -->

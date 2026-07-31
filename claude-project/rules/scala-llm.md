---
paths:
  - "**/*[Ll]lm*.scala"
  - "**/*[Ss]chema*.scala"
---

# Scala LLM boundary (structured output)

**Enforcement grade:** review and convention — nothing scans a model boundary. The keep-the-SDK-off-the-core half is enforceable structurally, by a build-level dependency boundary rather than a scanner.

The typed contract between your Scala code and the model — the single place this boundary's reliability is bought, and the only place an otherwise-pure core touches the outside world. Sources: the model provider's Java SDK, reached over JVM interop (most providers ship no native Scala SDK); the provider's structured-outputs documentation (the `outputConfig` equivalent and the JSON-schema limitations); and cats-effect `IO` for the effect boundary. The model is reached through the provider's official Java SDK; the model id is configured per call site. Pin the dated model id for reproducibility, and confirm the exact SDK `Model` enum against the resolved artifact at first wiring.

> See `scala-types.md` for the output as a typed contract (the case class the schema is derived from), `scala-concurrency.md` for wrapping the blocking SDK call in `IO` and putting a timeout on it, `scala-errors.md` for surfacing validation failures as typed values rather than thrown exceptions, `scala-modules.md` for keeping the SDK off the pure core's dependency surface, and `craft-abstraction.md` for the schema as a specification the call is written against.

> **Verify SDK specifics against the version resolved by `sbt`.** The Java SDK evolves and the JVM-interop surface is verbose; treat the method names below as a guide and confirm them against the resolved artifact (`sbt "show dependencyTree"`, the Javadoc, or the SDK README) before relying on them — do not compose interop calls from memory. `outputConfig(Class[T])`, a `StructuredMessage[T]` result, and a `fromEnv()` client factory are the shapes this rule turns on; the rest of the builder surface shifts between releases.

## The schema is the contract, and it is language-independent

- **The structured-output schema — not the Scala type, not the Java class — is what this rests on.** The guardrail lives at the JSON schema the model is constrained to, which is independent of Scala, Java, or any host language. Define one type as the single source of truth for each LLM output and derive the wire schema and the parsed result from it, so they cannot drift.
- **One bounded call, one typed result.** A focused call site makes a narrow, structured, validated call — no open-ended agent loop, no unbounded tool surface. The leverage over an open-ended agent is exactly this narrowing; keep the prompt and rubric fed whole (do not pre-digest them) and keep the schema as the thin typed boundary.
- **Feed the schema from a Java class the SDK can reflect.** A JVM structured-output SDK derives the JSON schema from a class passed to `outputConfig(Class[T])` and returns a `StructuredMessage[T]`. Scala 3 `case class`es work as that carrier, but reflection-based SDKs (Jackson) want a **top-level** class (not a nested or local one) with fields the reflector maps cleanly. Treat that class as a boundary adapter, converted to a domain type immediately; the pure core never imports it.

```scala
// The carrier IS the schema and the contract. A top-level class the Java SDK can reflect.
// Keep it at the boundary; convert to the domain Verdict before it reaches the pure core.
final case class VerdictDto(
    decision: String,        // constrained to a closed set — validate after parse
    reasons: java.util.List[String],
    severity: Int
)
```

## Bound everything, then validate again at the boundary

- **The schema constrains generation; it does not constrain a misbehaving model.** Constrain the wire schema where the SDK allows it — `enum` / `const` on closed sets, required vs optional fields, `additionalProperties: false` (the SDK adds this to every derived schema). But the structured-output schema commonly does **not** enforce string-length, item-count, or numeric range: `minLength`/`maxLength`, `minItems` beyond 0/1, and `minimum`/`maximum`/`multipleOf` are stripped from the wire schema and are not enforced by the model. Recursive schemas and complex enum members are often unsupported — keep the carrier flat.
- **Re-validate every parsed output against a total Scala check before your code trusts it.** Layer the bounds the schema cannot carry — closed-set membership, list size, numeric range, cross-field rules — as a pure validating function from the boundary DTO to the domain type. This is the deterministic replica of the constraints JSON Schema dropped, and it is where reproducibility is bought: the same output must always validate to the same domain value. Return the result as `Either` / `Validated`, never by throwing.

```scala
import cats.data.ValidatedNec
import cats.syntax.all.*

enum Decision:
  case Pass, Block

// Total: a malformed model output becomes an accumulated error, not an exception.
def validate(dto: VerdictDto): ValidatedNec[String, Verdict] =
  val decision = dto.decision match
    case "pass"  => Decision.Pass.validNec
    case "block" => Decision.Block.validNec
    case other   => s"decision not in {pass, block}: $other".invalidNec
  val reasons =
    val rs = dto.reasons.asScala.toList
    if rs.nonEmpty && rs.sizeIs <= 10 then rs.validNec
    else s"reasons must hold 1..10 items, got ${rs.size}".invalidNec
  val severity =
    if (0 to 5).contains(dto.severity) then dto.severity.validNec
    else s"severity out of range 0..5: ${dto.severity}".invalidNec
  (decision, reasons, severity).mapN(Verdict.apply)
```

## Calling the model — a thin Scala facade over the Java SDK

- **Wrap the call in one `LlmCall` facade and keep the SDK behind it.** The Java SDK's builder surface (a params builder, `StructuredMessage[T]`, `java.util.List`, `CompletableFuture`) is Java-shaped and stays at the boundary. Expose one Scala-idiomatic method that takes the prompt and the carrier class and returns `IO[Either[CallError, A]]`; every call site calls that, never the SDK directly. (`scala-modules.md` — the SDK is a boundary dependency, not a pure-core dependency.)
- **Construct one client, share it, and run the blocking call on a blocking pool.** The provider's `fromEnv()` factory builds a client with its own connection and thread pools — build it once at the edge, not per call. The synchronous `client.messages().create(params)` blocks; lift it with `IO.blocking(...)` (or the SDK's `async()` client adapted to `IO`) so it doesn't starve the cats-effect compute pool. (`scala-concurrency.md`.)
- **Put a timeout on every call and set retries explicitly.** The per-call latency and cost budget belong to the caller, not the SDK default. Bound the `IO` with `.timeout(d)` and configure the client's `maxRetries` and request `timeout` through the builder rather than relying on the multi-minute default. A call that can hang has no place in a bounded pipeline.

```scala
import cats.effect.IO
import scala.concurrent.duration.*
import scala.jdk.CollectionConverters.*
// ProviderClient / MessageParams below come from the provider's Java SDK (JVM interop).

final class LlmCall(client: ProviderClient, modelId: String):
  // One bounded, structured, validated call. A is the domain type; Dto is its boundary carrier.
  def structured[Dto, A](
      prompt: String,
      carrier: Class[Dto],
      validate: Dto => Either[String, A],
      timeout: FiniteDuration = 60.seconds
  ): IO[Either[String, A]] =
    val params = MessageParams.builder
      .model(modelId)             // configured per call site; pin the dated id for reproducibility
      .maxTokens(1024L)
      .outputConfig(carrier)      // the wire schema is derived here — confirm the name against the resolved SDK
      .addUserMessage(prompt)
      .build()
    IO.blocking(client.messages().create(params))
      .timeout(timeout)
      .map(parseCarrier[Dto])     // pull the typed value out of StructuredMessage[Dto]
      .map(_.flatMap(validate))   // then the total Scala re-validation
      .handleError(t => Left(s"llm call failed: ${t.getMessage}"))
```

## Determinism and reproducibility

- **Pin the model id and every sampling lever the SDK exposes; record them alongside the output.** A silently floating model id or token budget makes two runs incomparable. Set the model id explicitly (pin the dated id), hold `maxTokens` and any temperature or effort setting fixed, and write the resolved values next to each result so a run is reproducible from its own record. The API does not promise bit-identical output even at fixed settings — determinism here means *fixed, recorded inputs and a mechanical check downstream*, not a deterministic model.
- **Keep any check you need to be trustworthy mechanical.** Where a result must be reproducible, compute it in code over the structured output rather than asking a model to grade a model — an `LlmCall` belongs at a boundary, never as the arbiter of its own pipeline's result.

## Auth and prompt safety

- **Use API-key auth for programmatic calls, and keep the key in the environment.** Configure the client from the environment (a `fromEnv()` factory typically reads a provider key variable) or an explicit `apiKey` builder setter, not an interactive OAuth/subscription token path. Keep the key in the environment, never in source, a test fixture, or a committed config. (`scala-security.md`.)
- **Never interpolate untrusted content into the system prompt.** Retrieved documents, user input, and any upstream stage's output are untrusted data — they go in a user-role message, never spliced into the system prompt or the rubric. The system prompt and rubric are fixed, trusted, and fed verbatim; mixing data into them both poisons the cache prefix and opens a prompt-injection seam. (`scala-security.md`.)

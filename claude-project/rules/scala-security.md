---
paths:
  - "**/*.scala"
  - "**/*.sc"
---

# Scala security

This is a general Scala/JVM-security rule. It bites hardest on the kind of JVM service that runs untrusted-input-shaped data through a long pipeline — it reads a corpus and config off the filesystem, shells out to external tools (`git`, a linter, the sbt toolchain), parses untrusted JSON/stdout from those tools, persists to a SQL store, and makes bounded LLM calls whose output is by definition untrusted. So secrets handling, JVM deserialization (the sharpest class on this platform), command and SQL injection, JVM transitive-dependency hygiene, unsafe reflection, and safe temp files are what this rests on. Sources, all primary: the OWASP Cheat Sheet Series (Deserialization, Injection Prevention, Secrets Management, Password Storage), the OWASP Dependency-Check project and its `sbt-dependency-check` plugin, the Scala 3 reference and the `scala.sys.process` stdlib docs, the cats-effect `Resource`/`Sync` docs for safe acquisition and release, the SnakeYAML / Jackson advisories for CVE-2022-1471-class deserialization, the `java.security` / `java.nio.file` JDK docs (`SecureRandom`, `MessageDigest.isEqual`, `Files.createTempFile`, `ProcessBuilder`), the WartRemover built-in-warts catalog and the Scalafix `DisableSyntax`/`Disable` rules, the LLM provider SDK docs for reading the key from the environment (a `fromEnv`-style constructor), and the CISA/MITRE 2024 CWE Top 25.

> See `scala-llm.md` for the bounded structured-output schema as the typed model boundary — this rule is the input side of it (treat model output as untrusted, validate at the schema, feed back sanitized secret-free errors); `scala-types.md` for encoding invariants with enums, opaque types, and refinements so bad input can't construct a bad value; `scala-errors.md` for never swallowing a failure into a silent `Try`/`Either` and never leaking a secret into an error message; `scala-concurrency.md` for the cats-effect `Resource` and the timeout on every external call (CWE-400); `scala-modules.md` for the one-effect-system house rule and for pinning and vulnerability-scanning the JVM dependency tree; `scala-testing.md` for property-testing the parsing boundary with ScalaCheck; and the craft core — `craft-domain-modeling.md` for the domain model staying pure so the trust boundary is a single typed seam, and `craft-complexity.md` for keeping that seam narrow.

## Run the security toolchain in the build

- **Run `sbt dependencyCheck` (OWASP `sbt-dependency-check`) and fail on findings.** It runs OWASP Dependency-Check across the project, its aggregates, and the full transitive tree, matching against the NVD, and reports known CVEs. This is the JVM analog of `govulncheck` / `pip-audit`. The central JVM risk is transitive: a single direct dependency in `build.sbt` resolves to dozens of nested artifacts, and the vulnerability is almost always in a transitive node, not the one you named. Treat a new finding the way a strict lint gate treats a new lint finding — a regression to fix, not to suppress. Dependency-Check needs an NVD API key for timely updates (9.0+), and the first run downloads the full feed. (`scala-modules.md`.)
- **Run WartRemover and Scalafix `DisableSyntax`, and fail on a new finding.** The security- and safety-relevant warts — `Null`, `AsInstanceOf`, `IsInstanceOf`, `JavaSerializable`, `JavaConversions`, `OptionPartial`/`TryPartial`/`EitherProjectionPartial`, `Var`, `Throw` — are the static guardrail; `DisableSyntax` bans `null`, `asInstanceOf`, `var`, and `throw` syntactically. A differential lint gate blocks new WartRemover/Scalafix findings and new suppressions versus the merge-base; do not add a `@SuppressWarnings` or a `// scalafix:off` to clear a security finding.
- **Compile with `-Wunused:all` and `-Wvalue-discard` (set them in `build.sbt`), and never widen the warning baseline.** A discarded `IO[A]` or a discarded validation result is a dropped check; `-Wvalue-discard` surfaces it. Keep `-Xfatal-warnings` in CI so a new warning fails the build rather than scrolling past.
- **Keep the JDK and the dependency set current, but review before bumping.** Point releases of the JVM and of the JSON/HTTP/SQL libraries carry security fixes; an unreviewed bump can also pull in a compromised artifact (the supply-chain risk runs both ways). Pin exact versions in `build.sbt` and resolve from a trusted repository. (`scala-modules.md`.)

## Secrets — the LLM provider API key (CWE-798, hardcoded credentials, in the 2024 CWE Top 25)

- **Load the provider API key from the environment, never from source.** Construct the client with a `fromEnv()`-style constructor that reads the key from the process environment; do not pass a literal to `.apiKey(...)` and do not commit a key in any form. A hardcoded credential is CWE-798. In tests, inject a fake through the `LlmCall` facade — never a real key, even a throwaway.

```scala
import cats.effect.{IO, Resource}

// Read at the edge, acquire as a Resource, keep the key off every other surface.
val clientResource: Resource[IO, LlmClient] =
  Resource.fromAutoCloseable(IO.blocking(LlmClient.fromEnv()))
//                                        ^ fromEnv reads the key from the environment; no literal anywhere
```

- **Never log, print, or serialize a secret.** Keep the key out of `toString`, structured logs, exception messages, and any persisted store. A `case class` derives a `toString` that prints every field, so a secret must never be a field of a logged or persisted case class — wrap it in a dedicated type whose `toString` is redacted, or keep it out of the data model entirely and read it only at the call site.

```scala
opaque type ApiKey = String
object ApiKey:
  def fromEnv: Option[ApiKey] = sys.env.get("LLM_API_KEY")
  extension (k: ApiKey) def value: String = k
  // No given Show[ApiKey]; an opaque String won't be auto-derived, and there is no
  // case-class toString to leak it. The raw value is reachable only via .value, at the sink.
```

- **Keep secrets out of the build and the repo.** No key in `build.sbt`, `application.conf`, a checked-in `.env`, or a test resource. If a config layer is used, source secret values from the environment (Typesafe Config `${?LLM_API_KEY}` env substitution), not from a committed literal, and pair the repo with a pre-commit secret scanner. (OWASP Secrets Management Cheat Sheet.)

## JVM deserialization — the sharpest class on this platform (CWE-502, #16 in the 2024 CWE Top 25)

- **Never deserialize untrusted data with Java native serialization.** `ObjectInputStream.readObject` on attacker-influenced bytes is the canonical JVM RCE: the cast happens after deserialization, so it cannot prevent the attack, and the classpath supplies gadget chains that execute during construction (OWASP Deserialization Cheat Sheet). The safe architecture is to not accept serialized JVM objects from any untrusted source at all. The WartRemover `JavaSerializable` wart and avoiding `extends Serializable` on domain types keep this surface closed; prefer a data format (JSON) with an explicit, typed decoder for anything that crosses a trust boundary.
- **Parse untrusted YAML only with a SafeConstructor-based loader.** SnakeYAML before 2.0 instantiates any class named by a `!!` type tag via the default `Constructor`, which is CVE-2022-1471 — YAML-driven RCE through gadget chains. Use SnakeYAML ≥ 2.0 (its `Constructor` now extends `SafeConstructor`) or pass `SafeConstructor` explicitly, which restricts construction to primitives, strings, lists, and maps. The same caution applies to Jackson with default typing enabled (`enableDefaultTyping`/`@JsonTypeInfo` over an open type hierarchy is the polymorphic-deserialization gadget vector) — keep default typing off and deserialize into closed, sealed types.
- **Decode untrusted JSON into a closed, typed schema and bound the read.** The untrusted inputs — model output and external-tool stdout — cross the boundary as JSON; decode them into a sealed ADT / case-class schema (a circe/jsoniter decoder over an `enum` or `sealed trait`, not a raw `Json` cursor ranged over dynamically), reject unknown shapes rather than absorbing them, and cap the input size before decoding so a giant payload can't exhaust memory (CWE-400). The schema is the parse boundary. (`scala-types.md`, `scala-llm.md`.)
- **Parse untrusted XML, if any, with the secure-processing features on.** Disable DTDs (`disallow-doctype-decl`) and external entities on any `DocumentBuilderFactory`/`SAXParserFactory`/`XMLInputFactory` to close XXE and the billion-laughs entity-expansion DoS (CWE-611, CWE-776; OWASP XXE Prevention Cheat Sheet). A JSON-first system's cleanest stance is: no XML parser on the untrusted path.

## Command execution — the pipeline shells out to git and the toolchain (CWE-78, OS command injection)

- **Build a subprocess from a `Seq`, never a single command `String`, and never through a shell.** `scala.sys.process` constructs a `ProcessBuilder` from a `String` by splitting on spaces with no escaping, or from a `Seq[String]` where the first element is the program and the rest are arguments passed verbatim to the child as data. The `Seq` form goes straight to Java's `ProcessBuilder` with no shell interpreter, so metacharacters in an argument are inert. The `String` form, and any `Seq("sh", "-c", userString)`, reintroduce injection — don't.

```scala
import scala.sys.process.*

// SAFE — program fixed, each argument a separate Seq element, no shell.
val out: String = Seq("git", "rev-parse", "HEAD").!!

// UNSAFE — never do either of these with anything attacker-influenced.
// (s"git log $ref").!!                 // String form: splits on spaces, no escaping
// Seq("sh", "-c", s"git log $ref").!!  // re-introduces the shell and its metacharacters
```

- **Keep the program name a fixed constant; validate any argument that came from outside.** The executable must be a literal or a vetted allowlist entry, never user- or model-controlled (CWE-426, untrusted search path). For an argument that is an external value used as a flag, validate it and terminate option parsing with `--` so a value like `--upload-pack=...` can't be read as an option (CWE-88, argument injection). Never feed model output into an argument list without validating it against the typed schema first.
- **Wrap every subprocess in a cats-effect `Resource` with a timeout, on the blocking pool.** Run it via `IO.blocking`/`Sync[F].blocking` so it doesn't starve the compute pool, give it a `.timeout(...)` so a hung `git`/`sbt` can't wedge the pipeline (CWE-400), and acquire/release it as a `Resource` so the process is destroyed on cancellation or error. (`scala-concurrency.md`.)
- **Never use `eval`-shaped dynamic execution on untrusted input.** No `scala.tools.nsc` / Scripting-engine compile-and-run, no `javax.script` (Nashorn/GraalJS) evaluation of attacker- or model-derived strings — both run arbitrary code (CWE-94, #11 in the 2024 CWE Top 25). For dynamic dispatch use an explicit `Map`/`enum` allowlist, not reflective name-to-code resolution.

## SQL injection and the persisted store (CWE-89, #3 in the 2024 CWE Top 25)

- **Build SQL with bound parameters, never string interpolation.** Build every query with `?`/named placeholders bound through the driver (Doobie's `sql"... ${x}"` interpolator parameterizes — it does not concatenate; a raw JDBC `PreparedStatement` with `setX` does the same), so statement and values travel separately. A hand-built `s"... WHERE id = '$id'"` or a `Statement.executeQuery(concatenated)` is the named injection anti-pattern. The same holds across drivers and wire-compatible stores — the SQL-injection class is identical.
- **Validate the identifier domain rather than interpolating it.** Placeholders bind values, not table or column names; when a query shape genuinely varies by identifier, select it from a fixed allowlist (an `enum` of known columns) rather than interpolating an external string into the SQL text.

## Reflection and dynamic class loading (CWE-470, unsafe reflection)

- **Don't resolve a class or method by an externally-derived name.** `Class.forName(name)` / `getDeclaredMethod(...).invoke(...)` driven by attacker- or model-controlled input is unsafe reflection (CWE-470) and a sibling of the deserialization gadget problem — it lets input choose what code runs. Scala makes this easy to avoid: model the closed set of choices as a `sealed trait`/`enum` and pattern-match, so the compiler enumerates the cases and no string ever names a type.
- **Avoid `asInstanceOf` and reflective casts across the trust boundary.** A cast doesn't validate; it asserts. Decode into the typed schema and let the decoder reject bad shapes (the WartRemover `AsInstanceOf`/`IsInstanceOf` warts enforce this), rather than reading a `Json`/`Any` and casting it into the domain. `craft-domain-modeling.md`: make the illegal state unrepresentable so there's nothing to cast.

## Filesystem and temp files (CWE-22 path traversal #5; CWE-377 insecure temp file)

- **Confine an externally-supplied filename under a base directory before opening it.** Input and config paths are configured; if any path component comes from outside, resolve it and verify it stays under the intended base — `base.resolve(name).normalize().startsWith(base)` on `java.nio.file.Path` — and reject absolute paths and `..` escapes before opening (CWE-22, #5 in the 2024 CWE Top 25; OWASP). Prefer a generated name over a caller-supplied one.
- **Create temp files atomically with `Files.createTempFile`/`createTempDirectory`, never a hand-built `/tmp` path.** A predictable temp path is a TOCTOU symlink-swap race (CWE-377): another process can win between the name choice and the open. The JDK helpers pick an unpredictable name and create in one step; on POSIX, request owner-only permissions via `PosixFilePermissions.asFileAttribute(...)` (`rwx------`) at creation, and acquire the temp file as a cats-effect `Resource` so it is deleted on release. Avoid `File.createTempFile` followed by a separate open, and never `new File("/tmp/fixed-name")`.

```scala
import java.nio.file.{Files, Path}
import java.nio.file.attribute.PosixFilePermissions
import cats.effect.{IO, Resource}

val ownerOnly = PosixFilePermissions.asFileAttribute(
  PosixFilePermissions.fromString("rw-------")
)
def tempFile(prefix: String): Resource[IO, Path] =
  Resource.make(IO.blocking(Files.createTempFile(prefix, ".tmp", ownerOnly)))(
    p => IO.blocking(Files.deleteIfExists(p)).void
  )
```

- **Set least-privilege permissions on anything secret-bearing.** Owner-only (`rw-------` for files, `rwx------` for dirs) on a file that holds a secret, a token, or a credential; never world- or group-writable, never `0777`-equivalent (CWE-276).

## Cryptography and constant-time comparison

- **Use `java.security.SecureRandom` for any token, salt, nonce, or unpredictable identifier — never `scala.util.Random`/`java.util.Random`.** The general PRNGs are deterministic and predictable from observed output (CWE-330/CWE-338); `SecureRandom` is the JVM CSPRNG. Note that a *deterministic-seeding* requirement (a seeded corpus, a reproducible run for tests) is a separate axis from cryptographic randomness: a reproducible seed for reproducibility is fine and intended; it is just never the source for a security value.
- **Compare secrets, MACs, and digests with `java.security.MessageDigest.isEqual`, never `==` or `sameElements`.** `MessageDigest.isEqual` runs to the end regardless of the first differing byte, closing the timing side channel that `==`/structural array equality open by short-circuiting (CWE-208). This applies to any place code checks an API-key echo, a signature, or a token.
- **Use SHA-256 or stronger for any security hash; don't use MD5, SHA-1, DES, or RC4.** MD5/SHA-1 are broken for collision resistance (CWE-327/CWE-328); for symmetric encryption use an authenticated mode (AES-GCM) with a fresh per-message nonce, never ECB and never a reused IV. For password storage — not always a current need, but the rule is general — use a salted, memory-hard KDF (Argon2id first; OWASP Password Storage Cheat Sheet), never a fast general-purpose hash (CWE-916).

## The trust boundary — model output and tool stdout are untrusted input

- **Treat every `LlmCall` result and every external-process stdout as untrusted, validated at a typed boundary before any sink.** This is the input side of the structured-output schema `scala-llm.md` describes at the output side. Decode into the closed schema, reject what doesn't fit, bound the size, and only then let the value reach a subprocess argument, a SQL parameter, a file path, or a log line — never interpolate it raw into any of those (OWASP LLM02, Insecure Output Handling; CWE-20). Feed sanitized, secret-free errors back into the loop, never the raw exception or a value that might carry the key (`scala-errors.md`). The domain core stays pure precisely so this boundary is one explicit, testable seam rather than scattered across the pipeline (`craft-domain-modeling.md`).
- **Sanitize an untrusted string before logging it.** A newline or control character in model output or tool stdout can forge a log line (CWE-117, log injection); strip or escape control characters at the logging seam, and never log the unvalidated payload verbatim.

---
paths:
  - "**/*.java"
---

# Java security

This is a general Java/JVM-security rule for a service that runs untrusted-input-shaped data through its layers — it accepts bytes over the wire, parses XML and JSON from callers and upstream systems, reads files and config off the filesystem, persists to a SQL store, and holds provider credentials. The order below leads with the JVM's own sharpest teeth — native deserialization and XXE, the two classes where a single mistake is remote code execution — and then the OWASP core of path traversal, injection, and secrets. The floor is Java 21: `var`, records, sealed types, pattern matching, and the JEP 415 `ObjectInputFilter` are all assumed. Sources, all primary and public: the OWASP Top 10 and the OWASP Cheat Sheet Series (Deserialization, XXE Prevention, SQL Injection Prevention), *Effective Java* 3rd ed. Items 85–88 on serialization, the SpotBugs/FindSecBugs published bug-pattern catalog, and the JDK API docs for `java.io.ObjectInputFilter`, `javax.xml.parsers`, `java.nio.file.Path`, and `java.sql.PreparedStatement`.

> See `java-errors.md` for never swallowing a failure into a silent catch and never leaking a secret into an exception message or stack trace; `java-types.md` for encoding invariants with records, sealed types, and enums so untrusted input can't construct a bad value; `java-modules.md` for pinning and vulnerability-scanning the transitive dependency tree — the JVM's sharpest supply-chain surface; and `java-concurrency.md` for bounding every external call with a timeout (CWE-400) and releasing subprocess and stream resources deterministically with try-with-resources.

## Native deserialization of untrusted input is banned (CWE-502, deserialization of untrusted data)

- **Never call `ObjectInputStream.readObject` on attacker-controlled bytes.** This is the canonical JVM RCE: the cast to the expected type happens *after* the object graph is reconstructed, so it cannot prevent the attack, and the classpath supplies gadget chains that execute during construction (`readObject`/`readResolve`/`finalize`) before your code ever runs. *Effective Java* Item 85 is unambiguous — prefer alternatives to Java serialization entirely. The safe architecture accepts no serialized JVM objects across a trust boundary; use a data format like JSON with an explicit, typed schema and reject unknown shapes. FindSecBugs flags this as `OBJECT_DESERIALIZATION`.
- **If native deserialization is genuinely unavoidable, install a strict allow-list `ObjectInputFilter`.** A filter that names the exact classes permitted and rejects everything else (Items 86–88; JEP 290/415) closes the gadget surface. Allow-list by class or package and terminate with `!*`; set depth, ref, and byte caps so a hostile graph can't exhaust memory.

```java
// Reject-by-default: allow only the model package plus java.base, cap the graph, deny the rest.
var filter = ObjectInputFilter.Config.createFilter(
    "maxbytes=16384;maxdepth=5;com.example.model.*;java.base/*;!*");
try (var in = new ObjectInputStream(source)) {
    in.setObjectInputFilter(filter);   // must be set before the first readObject
    var value = (Order) in.readObject();
}
```

## XXE-hardened XML factories (CWE-611 external entity, CWE-776 entity expansion)

- **Disable DTDs and external entities on every XML factory before you parse.** An unhardened `DocumentBuilderFactory`, `SAXParserFactory`, or `XMLInputFactory` resolves external entities — that is XXE (file read, SSRF) — and expands nested internal entities into the billion-laughs DoS. The primary defense per the OWASP XXE Prevention Cheat Sheet is a single feature: disable the doctype declaration. FindSecBugs flags the unhardened forms as `XXE_DOCUMENT`, `XXE_SAXPARSER`, and `XXE_XMLSTREAMREADER`.

```java
var dbf = DocumentBuilderFactory.newInstance();
dbf.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true); // primary defense
dbf.setFeature("http://xml.org/sax/features/external-general-entities", false);
dbf.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
dbf.setXIncludeAware(false);
dbf.setExpandEntityReferences(false);
// StAX takes the analog: xif.setProperty(XMLInputFactory.SUPPORT_DTD, false);
//   and xif.setProperty("javax.xml.stream.isSupportingExternalEntities", false);
```

- **Hardening is per-factory, not global — set it every time.** There is no JVM-wide switch; a factory constructed anywhere in the codebase without these features is exploitable. Wrap factory construction in one shared helper and route all XML parsing through it so the hardening cannot be forgotten. A JSON-first system's cleanest stance is no XML parser on the untrusted path at all.

## Path traversal — confine an external filename under its base (CWE-22, in the OWASP Top 10)

- **Canonicalize the resolved path and verify it stays under the intended root before opening it.** A filename component that came from outside — a request parameter, an upload name, an archive entry — can carry `..` or an absolute path to escape the base directory (CWE-22; FindSecBugs `PT_RELATIVE_PATH_TRAVERSAL`). Resolve against a canonical base, `normalize()`, and reject anything that does not `startsWith` the base. Prefer a generated name over a caller-supplied one.

```java
Path base = Path.of("/srv/deals").toRealPath();     // canonical base, symlinks resolved
Path resolved = base.resolve(userSupplied).normalize();
if (!resolved.startsWith(base)) {
    throw new SecurityException("path escapes base directory: " + userSupplied);
}
// For an existing target, resolved.toRealPath().startsWith(base) also defeats symlink escapes.
```

## Parameterized SQL only (CWE-89, SQL injection, in the OWASP Top 10)

- **Build every query with a `PreparedStatement` and bound parameters, never string concatenation.** A placeholder sends the statement and its values on separate channels, so a value can never be reparsed as SQL — this is the OWASP SQL Injection Prevention Cheat Sheet's primary defense. A concatenated `"... WHERE id = '" + id + "'"` or a `Statement.executeQuery` over interpolated text is the named anti-pattern (FindSecBugs `SQL_INJECTION_JDBC`). The rule is identical across JDBC, JPA/HQL, and Spring `JdbcTemplate`.

```java
String sql = "SELECT balance FROM accounts WHERE id = ? AND owner = ?";
try (PreparedStatement ps = conn.prepareStatement(sql)) {
    ps.setLong(1, accountId);
    ps.setString(2, owner);          // statement and values travel on separate channels
    try (ResultSet rs = ps.executeQuery()) { /* ... */ }
}
```

- **Validate identifiers against an allowlist — placeholders bind values, not table or column names.** When a query shape genuinely varies by identifier, select it from a fixed `enum` of known columns rather than interpolating an external string into the SQL text.

## Secrets hygiene (CWE-798, hardcoded credentials)

- **Read credentials from the environment or a secret store, never from source.** A literal key, password, or token in a `.java` file, a checked-in `.properties`/`.yml`, or a test resource is CWE-798 (FindSecBugs `HARD_CODE_PASSWORD`, `HARD_CODE_KEY`). Read at the edge, fail fast if absent, and pass the value no further than the client that needs it.

```java
String key = System.getenv("PROVIDER_API_KEY");
if (key == null || key.isBlank()) {
    throw new IllegalStateException("PROVIDER_API_KEY is not set");
}
```

- **Keep secrets out of logs, `toString`, and serialized forms.** A `record` derives a `toString` that prints every component, so a secret must never be a component of a logged or persisted record — wrap it in a dedicated type with a redacted `toString`, or keep it out of the data model and read it only at the call site. Never log a request or config object that carries a credential, and strip control characters from any untrusted string before logging it (CWE-117, log injection).

## Spring Boot

When the build declares `spring-boot-starter` — otherwise skip this section. The gate scanners stay framework-neutral; this subsection applies only when the dependency manifest pulls Spring Boot in.

- **Do not expose the Actuator wholesale.** `management.endpoints.web.exposure.include=*` publishes `env`, `heapdump`, `threaddump`, and `mappings` — a configuration- and memory-disclosure surface. Expose only what a probe needs and keep the rest off the web tier.

```properties
management.endpoints.web.exposure.include=health,info
management.endpoint.health.show-details=never
```

- **Do not blanket-disable CSRF on a browser-facing app.** `http.csrf(csrf -> csrf.disable())` removes the cross-site-request-forgery defense for any session-cookie-authenticated UI (FindSecBugs `SPRING_CSRF_PROTECTION_DISABLED`). Disable CSRF only for a stateless, token-authenticated API that carries no ambient session credential, and say so explicitly.
- **Enforce authorization at the service layer with method security.** Enable `@EnableMethodSecurity` and annotate service methods with `@PreAuthorize` so an authorization check sits on the business operation itself, not only on a URL pattern that a new controller route can bypass.

```java
@Service
public class LoanService {
    @PreAuthorize("hasRole('ANALYST')")   // checked at the operation, not just the route
    public Decision approve(long dealId) { /* ... */ }
}
```

---
paths:
  - "**/*.ts"
  - "**/*.tsx"
---

# TypeScript security

This is a general TypeScript/JavaScript-security rule spanning the two runtimes TS ships to — the browser and Node. It bites hardest on the shapes most TS code takes: a single-page app that renders untrusted content into the DOM, reads URL params and `postMessage` and `localStorage`, and ships a bundle to every visitor; and a Node service that shells out, queries a database, makes outbound and LLM calls, and reads request bodies. So the client-side secret boundary, XSS and the DOM sinks, untrusted-input validation, dynamic code execution, prototype pollution, dependency supply chain, and the server-side injection classes are what this rests on. The one idea under all of it: nothing you send to the browser is secret, and everything that crosses a trust boundary is untrusted until a schema says otherwise. Sources, all primary: the OWASP Top 10 and the XSS / DOM-based XSS / DOM Clobbering cheat sheets, the React docs on `dangerouslySetInnerHTML` and JSX escaping, the Vite env-and-mode docs (the `VITE_` inlining rule), the MDN docs on `Content-Security-Policy`, `structuredClone`, `Object.create(null)`, and `rel="noopener"`, the npm CLI docs (`npm audit`, `npm ci`, `npm audit signatures`), the `typescript-eslint` and `eslint-plugin-react` rule catalogs, DOMPurify (`cure53/DOMPurify`), the Zod docs (`safeParse`), the Node `crypto`/`child_process`/`fs`/`path` docs, and the CISA/MITRE 2024 CWE Top 25 — corroborated by the Snyk and Semgrep JavaScript cheat sheets.

> See `ts-llm.md` for the bounded structured-output schema as the typed model boundary — this rule is the input side of it (treat model output as untrusted, validate at the schema, feed back sanitized secret-free errors); `ts-types.md` for encoding invariants with branded types and discriminated unions so a raw value can't reach the domain unvalidated (`strict` and `noUncheckedIndexedAccess` on in `tsconfig.json`); `ts-react.md` for the component-level rendering rules the XSS section leans on; `ts-errors.md` for never swallowing a rejected promise and never leaking a secret into an error message or a client response; `ts-concurrency.md` for the `AbortSignal` timeout on every external call (CWE-400); `ts-modules.md` for pinning and auditing the dependency tree; `ts-testing.md` for property-testing the parsing boundary; and the craft core — `craft-domain-modeling.md` for a single typed translation seam at each trust boundary (never letting a foreign model leak in), and `craft-complexity.md` for keeping that seam narrow.

## Run the security toolchain in the gate

- **Run `npm audit --omit=dev --audit-level=high` and fail on findings.** It scans the installed tree against the npm advisory database and reports known vulnerabilities; `--omit=dev` scopes the gate to what actually ships (a prototype-pollution advisory in a test-only formatter is real but not a production exposure, so keep it off the release gate and on a separate dev sweep). Treat a new production finding the way a strict lint gate treats a new lint finding — a regression to fix or a reviewed, time-boxed exception, not a permanent ignore. (`ts-modules.md`.)
- **Install from the lockfile with `npm ci` in CI, never `npm install`.** `npm ci` treats `package-lock.json` as a strict contract and fails if `package.json` and the lock disagree, so every build resolves to exactly the versions you reviewed — the precondition for knowing whether a malicious release was ever pulled. `npm install` can silently rewrite the lock.
- **Verify registry signatures with `npm audit signatures`.** It checks the packages in the lockfile against the registry's signatures and (where present) sigstore provenance attestations, catching a tampered or account-hijacked release that a version-based advisory scan misses. Run it in the same gate as the audit.
- **Lint with `typescript-eslint` (type-checked) and the React plugin, and fail on a new finding.** The security-relevant rules are the static guardrail: `@typescript-eslint/no-implied-eval` (the type-aware superset of core `no-implied-eval` — `new Function`, `setTimeout`/`setInterval` with a string body), core `no-eval`, `react/no-danger` (flags every `dangerouslySetInnerHTML`), `react/jsx-no-script-url` (`javascript:` URLs), and `react/jsx-no-target-blank`. Don't add an `// eslint-disable-next-line` to clear a security finding; fix it or record a reviewed exception.
- **Keep `tsconfig.json` strict.** `"strict": true` plus `"noUncheckedIndexedAccess": true` turn a whole class of "it was `undefined` and I indexed into it" bugs into compile errors. The type system is a security control only when it's on; a codebase riddled with `any` and `as` casts has opted out of it (`ts-types.md`).

## Nothing in a client bundle is secret (CWE-798, hardcoded credentials, in the 2024 CWE Top 25)

The single most expensive browser mistake is treating the client as a place a secret can live. It cannot.

- **No API key, token, session secret, or credential ships to the browser — they belong on a server.** Everything in a client bundle is readable: the user can open devtools, read the minified source, and inspect every network call. A third-party API that needs a secret key is called from your own backend endpoint, which holds the key server-side and proxies the request; the browser talks only to your server. There is no obfuscation, no "it's minified," no environment trick that changes this — a key in the bundle is a leaked key (OWASP A02, Cryptographic Failures; CWE-798).

```ts
// UNSAFE — the key is inlined into the JS every visitor downloads.
const res = await fetch("https://api.example.com/charge", {
  headers: { authorization: `Bearer ${import.meta.env.VITE_STRIPE_SECRET_KEY}` },
});

// SAFE — the browser calls your own origin; the secret stays on the server.
const res = await fetch("/api/charge", { method: "POST", body: JSON.stringify(order) });
```

- **Vite inlines every `VITE_`-prefixed env var into the bundle at build time — so a secret named `VITE_*` is a leaked secret.** The Vite env docs are explicit: variables prefixed with `VITE_` are exposed in client source after bundling, and "`VITE_*` variables should _not_ contain sensitive information such as API keys." An unprefixed var (`DB_PASSWORD`) is `undefined` in client code by design. The prefix is configurable via `envPrefix`, which only moves the boundary — it doesn't create a private channel. The publishable/anon keys some SDKs hand out (a Stripe publishable key, a Supabase anon key) are designed to be public and are fine in `VITE_`; a secret/service key never is. Know which one you're holding before you prefix it.
- **Same rule under every bundler and framework.** Create React App's `REACT_APP_` prefix, Next.js's `NEXT_PUBLIC_`, and webpack `DefinePlugin` substitutions all inline the value into client code identically — the prefix is a "this will be public" marker, not a protection. A Next.js value without `NEXT_PUBLIC_` stays server-only; one with it is in the bundle.
- **Keep secrets out of the repo and out of source.** No key in a committed `.env`, in a config module, or as a literal. Load server secrets from the environment (`process.env`) at the call site, gitignore every `.env*` that holds a real value (commit a `.env.example` with blank placeholders), and pair the repo with a pre-commit secret scanner. A secret that reached a public bundle or a git history is compromised — rotate it, don't patch it.

## Trust boundaries and input validation (CWE-20 — the boundary that governs the rest)

- **Validate everything crossing a trust boundary against a runtime schema before it reaches the domain — TypeScript types are erased at runtime and check nothing about actual data.** A type annotation on a `fetch` result, a request body, or `JSON.parse` output is a compile-time assertion the runtime never enforces; the value can be any shape at all. Parse it with Zod (or an equivalent runtime validator) at every untrusted edge — network responses and request bodies, URL/query params, route params, `postMessage` payloads, `localStorage`/`sessionStorage` reads, cookies, and file contents — so a malformed or hostile value is rejected at the seam rather than flowing inward as a lie about its type. This is the input side of the boundary `ts-llm.md` applies at the structured-output schema (`craft-domain-modeling.md`: one explicit translation type per seam).

```ts
import { z } from "zod";

const Order = z.object({
  id: z.string().uuid(),
  amountCents: z.number().int().nonnegative(),
  currency: z.enum(["USD", "EUR", "GBP"]),
});
type Order = z.infer<typeof Order>;

// SAFE — `parsed` is either a typed Order or a handled error; the raw JSON never reaches the domain.
const parsed = Order.safeParse(await res.json());
if (!parsed.success) return badRequest(parsed.error);
process(parsed.data);
```

- **Default to `safeParse`, not `parse`, at an untrusted boundary.** `parse` throws a `ZodError` on bad input, which turns hostile data into an exception you must remember to catch; `safeParse` returns a discriminated `{ success, data | error }` result the compiler forces you to branch on. Reserve `parse` for internal data you already trust (`ts-errors.md` for the throw-vs-return policy). Reject unknown fields (`.strict()`) where an extra key signals a mismatched or malicious payload rather than silently absorbing it.
- **Never trust `postMessage` data, and always check `event.origin`.** A message handler receives events from any window that has a handle to yours; validate `event.origin` against an allowlist before reading `event.data`, then schema-parse the data. When you send, pass an explicit `targetOrigin` — never `"*"` for anything sensitive, since that broadcasts the payload to whatever origin currently occupies the target frame.
- **Bound the size of any untrusted read before parsing** — a request body, an uploaded file, a pasted blob. An unbounded `JSON.parse` of a giant payload is a memory-exhaustion DoS (CWE-400); cap the body size at the server (the framework's body-limit option) and reject oversized input before decoding.

## XSS — the browser's default-loaded gun (CWE-79, #1 in the 2024 CWE Top 25)

- **Let React (or your framework) auto-escape — that is the protection, and interpolating a string in JSX is safe by construction.** `<div>{userInput}</div>` renders the value as text: React escapes it, so `<img onerror=...>` becomes inert characters, not an element. The same holds for Angular interpolation and Vue's `{{ }}` mustaches. This default is the whole defense; the vulnerabilities below are all ways of stepping around it.
- **`dangerouslySetInnerHTML` is the escape hatch that reintroduces XSS — sanitize with DOMPurify, or don't use it.** The React docs are blunt: "Unless the markup is coming from a completely trusted source, it is trivial to introduce an XSS vulnerability this way." If you must render HTML (rendered Markdown, a rich-text field), run it through DOMPurify first — it works from a secure default and strips scripts, event handlers, and `javascript:` URLs. Never feed model output, a URL param, or any user text to the raw `__html` key.

```tsx
import DOMPurify from "dompurify";

// SAFE — sanitized to an HTML-only profile before it reaches the DOM.
function Article({ html }: { html: string }): JSX.Element {
  const clean = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
  return <div dangerouslySetInnerHTML={{ __html: clean }} />;
}
```

- **Treat `href`/`src` as an injection sink — a `javascript:` URL runs code.** A user-controlled link target like `href={userUrl}` lets `javascript:alert(1)` execute on click (`eslint-plugin-react`'s `jsx-no-script-url` flags the static case; the dynamic case needs a runtime guard). Allowlist the scheme before rendering — permit `https:`, `http:`, `mailto:`, and relative URLs; reject everything else. Parse with the `URL` constructor rather than string-matching.

```ts
export function safeHref(raw: string): string {
  try {
    const url = new URL(raw, window.location.origin);
    return ["http:", "https:", "mailto:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#"; // not a parseable URL — don't render it as a link target
  }
}
```

- **For a `target="_blank"` link to an untrusted origin, keep `rel="noopener"`.** Without it the opened page gets a live `window.opener` handle and can navigate your tab to a phishing clone (reverse tabnabbing, CWE-1022). Modern browsers (Chrome/Edge 88+, Firefox 79+, Safari 12.2+) imply `noopener` for `target="_blank"`, so this is defense for older engines and for explicitness — set it anyway; the React plugin's `jsx-no-target-blank` enforces it. Add `noreferrer` when you also want to withhold the `Referer` header.
- **Reach for the raw DOM sinks — `element.innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` — only with sanitized input.** These are the framework-independent version of the same hole (the OWASP DOM-XSS cheat sheet's sink list). Prefer `textContent` when you're inserting text; it never parses HTML. If you build DOM imperatively, `createElement` + `textContent` is injection-free.

## No dynamic code execution (CWE-94, code injection, #11 in the 2024 CWE Top 25)

- **Never `eval`, `new Function`, or a string-bodied `setTimeout`/`setInterval` on any value derived from untrusted input.** All of them compile and run arbitrary code with your page's or process's privileges (`no-eval`, `@typescript-eslint/no-implied-eval`). There is essentially never a legitimate reason to build code from a string at runtime in application code; for dynamic dispatch use an explicit lookup object or a `Map` keyed by a validated enum, not a name resolved into a callable.

```ts
// UNSAFE — attacker controls what runs.
const result = new Function("return " + userExpr)();

// SAFE — a closed, typed table of allowed operations.
const ops = { add, subtract, multiply } as const;
const op = ops[parsed.operation]; // parsed.operation is a validated key of `ops`
```

- **Don't route strings through `setTimeout(str)`, template compilers with `eval`-based backends, or `vm`/`Function` sandboxes fed untrusted code.** A "sandbox" built from `Function` or Node's `vm` is not a security boundary — untrusted code escapes it. If you genuinely must run untrusted code, that is a separate-process/isolate/WASM problem, not a `vm` call.

## Prototype pollution (CWE-1321)

- **Never deep-merge, `Object.assign`, or path-set untrusted keys into an object without blocking `__proto__`, `constructor`, and `prototype`.** A JS-specific class: assigning to `obj["__proto__"]["isAdmin"]` from attacker-controlled JSON mutates `Object.prototype`, so every object in the process gains the property — a foothold for auth bypass and, on the server, RCE via a polluted `constructor`. It reaches you through recursive merge helpers, query-string parsers, and `lodash.set`-style path assignment fed user input.
- **Parse untrusted JSON into a Zod schema (which reads only declared keys), and use a null-prototype map for arbitrary-key lookups.** `Object.create(null)` and `new Map()` have no prototype chain to poison, so `__proto__` becomes an ordinary key with no special meaning. `JSON.parse` itself is safe — the danger is what you do with the result — so validate the shape rather than merging it blindly.

```ts
// SAFE — a bag with no prototype; "__proto__" is just a string key here.
const lookup: Record<string, string> = Object.create(null);
for (const [k, v] of Object.entries(parsed.pairs)) lookup[k] = v;
```

- **Freeze known-shape config objects and prefer `structuredClone` over hand-rolled deep-copy.** `Object.freeze` on a config singleton blocks post-parse tampering; `structuredClone` is the built-in deep copy and avoids the merge-based pollution path that custom recursive copiers reintroduce.

## Content Security Policy — the second line when escaping fails

- **Serve a `Content-Security-Policy` header so an injected script has nothing to execute.** CSP is the defense-in-depth layer under output escaping: even if XSS slips through, a strict policy blocks inline scripts and unlisted origins from running (OWASP; MDN CSP). Set it as a response header from the server, not only a `<meta>` tag (the header is stricter and covers more directives). Start from `default-src 'self'` and widen deliberately per resource type.
- **Avoid `'unsafe-inline'` and `'unsafe-eval'` in `script-src` — they defeat most of CSP's value.** Prefer a nonce- or hash-based policy for the inline scripts you genuinely need (`script-src 'self' 'nonce-<random>'`), generating a fresh nonce per response. `'unsafe-eval'` re-permits the `eval`/`Function` family the section above bans. Add `object-src 'none'`, `base-uri 'self'` (closing a `<base>`-tag injection that rewrites every relative URL), and `frame-ancestors 'none'` (clickjacking, the modern replacement for `X-Frame-Options`).
- **Set the transport and isolation headers alongside it.** `Strict-Transport-Security` (HSTS) to force HTTPS, `X-Content-Type-Options: nosniff` to stop MIME-sniffing a response into an executable type, and a `Referrer-Policy`. A helmet-style middleware sets a sane default bundle; review each directive rather than accepting the defaults blind.

## Safe serialization and the wire (CWE-502)

- **`JSON.parse`/`JSON.stringify` are the only serialization you should need for untrusted data.** JSON deserialization is not itself a code-execution vector the way a language-native object format is — the risk is downstream (prototype pollution above, or trusting the shape), so validate with a schema and you're done. Avoid `eval`-based JSON parsing and any library that revives class instances or functions from untrusted input (that is the JS analog of the CWE-502 deserialization-gadget class).
- **When stringifying an object that might hold a secret, strip it explicitly.** `JSON.stringify` serializes every enumerable own property, so a token accidentally living on a logged or persisted object leaks. Keep secrets out of the domain objects you serialize, or pass a `replacer` that drops them; don't rely on a field being "obviously internal."

## The Node backend — never trust the client (server-side classes)

The browser rules above assume a server behind them. On that server, every value from a request is attacker-controlled.

- **Build SQL with parameterized queries, never string interpolation (CWE-89, #3 in the 2024 CWE Top 25).** Pass values as bound parameters (`$1`/`?` placeholders, or a query builder / ORM that parameterizes) so statement and data travel separately; a template-literal query with an interpolated value is the named injection anti-pattern. A tagged-template SQL client that parameterizes (`sql\`... where id = ${id}\``) is safe because the tag binds the value — a plain string built with `+` or `${}` is not.

```ts
// UNSAFE — interpolated into the statement text.
db.query(`SELECT * FROM users WHERE email = '${email}'`);

// SAFE — the driver binds `email` as a parameter, separate from the SQL.
db.query("SELECT * FROM users WHERE email = $1", [email]);
```

- **Confine an externally-supplied filename under a base directory before opening it (CWE-22, path traversal, #5 in the 2024 CWE Top 25).** Resolve the path and verify it stays under the intended root before any `fs` call — reject absolute paths and `..` escapes. Prefer a server-generated name (a UUID) over a client-supplied one for anything written to disk.

```ts
import path from "node:path";

export function resolveUnder(base: string, name: string): string {
  const full = path.resolve(base, name);
  const root = path.resolve(base);
  if (full !== root && !full.startsWith(root + path.sep)) {
    throw new Error("path escapes base directory");
  }
  return full;
}
```

- **Validate against SSRF before any outbound request built from untrusted input (CWE-918).** Don't accept a full URL from a caller and fetch it — allowlist the permitted host, then resolve the hostname and confirm the resolved IP is not loopback, private (`10/8`, `172.16/12`, `192.168/16`), link-local, or the cloud metadata address (`169.254.169.254`), checking the resolved IP rather than the hostname to close the DNS-rebinding window. Disable redirect-following (or re-validate each hop) so a redirect can't bounce past the check, and don't return the raw upstream response or error to the caller.
- **Shell out with the argument-array form, never a shell string (CWE-78, OS command injection, #7 in the 2024 CWE Top 25).** Use `execFile`/`spawn` with the program fixed and arguments as separate array elements — they pass to the child as data with no shell to interpret metacharacters. `exec`/`execSync` and any `spawn("sh", ["-c", userString])` route through a shell and reintroduce injection; don't build a command string from input. Keep the program name a constant, put an `AbortSignal` timeout on every subprocess (`ts-concurrency.md`), and never feed model output into an argument without schema-validating it first.

```ts
import { execFile } from "node:child_process";
// SAFE — fixed program, ref as a discrete argument, no shell.
execFile("git", ["log", "-1", "--format=%H", "--", ref], (err, stdout) => { /* ... */ });
```

- **Sanitize an untrusted string before logging it, and never log a secret or a full request body.** A newline or control character in user input can forge a log line (CWE-117, log injection); strip control characters at the logging seam. Keep tokens, keys, and passwords out of logs and out of any error returned to the client (`ts-errors.md`), and return a generic message with a correlation id rather than the raw exception.

## Cryptography and secrets on the server (CWE-330, CWE-208)

- **Generate tokens, salts, nonces, and session ids with `crypto.randomBytes`/`crypto.randomUUID` (Node) or `crypto.getRandomValues` (Web) — never `Math.random`.** `Math.random` is a non-cryptographic PRNG, predictable from observed output (CWE-330/CWE-338); the `crypto` APIs are the CSPRNG. `crypto.randomUUID()` is available in both runtimes for an id.
- **Compare secrets, tokens, and MACs with `crypto.timingSafeEqual`, never `===`.** `===` on strings short-circuits at the first differing character, leaking length and prefix through timing (CWE-208, observable timing discrepancy). `timingSafeEqual` runs in length-independent time; feed it equal-length `Buffer`s (hash both sides first if lengths can differ).
- **Store passwords only with a salted, memory-hard KDF — Argon2id first, then scrypt or bcrypt.** `argon2` (or Node's built-in `crypto.scrypt`, or `bcrypt` with the 72-byte input limit in mind) — a fast general-purpose hash, even SHA-256, is far too fast to resist offline cracking (CWE-916; OWASP Password Storage Cheat Sheet). Never MD5 or SHA-1 for a security purpose (CWE-327/328); use SHA-256+ for integrity hashing and an authenticated cipher (AES-GCM) with a fresh 12-byte nonce per message for symmetric encryption.
- **When verifying a JWT, pass an explicit `algorithms` allowlist and never disable verification.** Hard-code the expected algorithm rather than trusting the token's own `alg` header, and don't mix symmetric and asymmetric families — this blocks the `alg: none` downgrade and the RS256→HS256 key-confusion attack (CWE-347). Load the signing secret from the environment, never a literal.

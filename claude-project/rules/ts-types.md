---
paths:
  - "**/*.ts"
  - "**/*.tsx"
---

# TypeScript domain modeling with the type system

Encode a value's invariants in the type system so `tsc` rejects the illegal state before it reaches a caller — a discriminated union for a closed set of cases, a branded scalar behind a validating constructor, `readonly` for a value that must not mutate, and a runtime schema at the boundary the compiler cannot see. Sources: the TypeScript Handbook (Narrowing, Unions and Intersection Types, Generics, and the TSConfig reference), *Effective TypeScript* (Vanderkam), *Programming TypeScript* (Cherny), the release notes for `satisfies` (4.9) and `const` type parameters (5.0), and the zod documentation for the runtime-schema boundary. The substitutability discipline is from Liskov (`craft-abstraction.md`); the value-object and ubiquitous-language discipline is from Evans (`craft-domain-modeling.md`).

> See `craft-domain-modeling.md` for value objects, entities, and naming in the ubiquitous language; `craft-abstraction.md` for abstract data types and the substitution principle; `ts-errors.md` for the `Result`/discriminated-error convention and why thrown errors stay `unknown`; `ts-testing.md` for testing the residue the type can't state; and `ts-security.md` and `ts-llm.md` for the zod schema as the typed boundary at an untrusted input or a model response.

## The shape of the discipline: encode what's cheap, test the residue

"Make illegal states unrepresentable" is the aspiration, not the whole job. TypeScript's type system is structural and — critically — *erased*: it exists only at compile time and vanishes at runtime, so a type is a claim about values the compiler checks under closed-world assumptions it does not always own. Push each invariant into the type while it stays cheap and clear: a discriminated union for a closed set of cases (below), a branded type behind a validating constructor for a constrained scalar, `readonly` for immutability. Some invariants are too costly to state, and some — anything about a value that entered the program from outside — the compiler *cannot* state, because it never saw that value's provenance. That residue is where the work lives. Close the compile-time part with tests (`ts-testing.md`) and the runtime part with a schema (below): the type carries what it cheaply can, a zod parse carries the boundary the type is blind to, and property and unit tests pin the negative space — what the constructor does when handed an illegal value.

- **A branded type without a validating constructor is just a label.** The payoff of branding a primitive is the *constructor* that rejects or normalizes bad input. If every `number` can be cast to a `Money`, the brand buys nominal type-safety but not an invariant — pair the brand with the check, and make the cast reachable only inside that constructor.
- **Fail closed by default: reject the illegal input.** A validating constructor returns `T | undefined` or a `Result<T, E>` (`ts-errors.md`); it does not throw for an expected-invalid input, and it never returns the bad value branded. Normalize instead of reject only when the mapping is total and lossless — clamping a known-bounded number, trimming insignificant whitespace; when in doubt, reject.
- **Test both sides of every uncodified invariant.** Write the property on valid values *and* a test that the constructor refuses or normalizes the illegal ones. The negative space is half the contract; an untested constructor is an unproven invariant.
- **A type with no illegal state needs no constructor.** A `{ readonly x: number; readonly y: number }` point has no invalid inhabitant — every pair is a legal point. Do not add ceremony where the type already makes all states legal; the goal is the invariant, not the wrapper.

**Worked example — `Money`.** A money amount is a nonnegative integer count of minor units (cents), never a `float` and never negative. TypeScript will not cheaply make "a nonnegative integer" a type, so `Money` is a branded `number` whose only constructor is fail-closed: `Number.isInteger` rejects a fractional or `NaN` input, `< 0` rejects a negative, and only past both guards does the single sanctioned `as Money` run. The brand keeps a raw `number` from being passed where a `Money` is wanted, and keeps a `Money` from being multiplied by another `Money` without going through the domain operation. The tests then carry both halves — a property that any valid cent count round-trips through `money(n).value`, and unit tests that `money(1.5)`, `money(-1)`, and `money(NaN)` each return `undefined`. The invariant the type cannot state is enforced by the constructor and proven by the test, which is what stops a forged or fractional amount from reaching a total.

## Turn on strict, then turn on the flags strict leaves off

`strict: true` is the floor, not the ceiling. It enables `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `noImplicitAny`, `noImplicitThis`, `alwaysStrict`, and `useUnknownInCatchVariables`. Four sharp flags sit *outside* `strict` and must be set explicitly — the house default enables all four, because each closes a class of runtime bug the base strict set still admits.

```jsonc
// tsconfig.json — the house floor
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,    // arr[i] is T | undefined, not T
    "exactOptionalPropertyTypes": true,  // `x?: T` ≠ `x: T | undefined`
    "noImplicitOverride": true,          // an override must say `override`
    "useUnknownInCatchVariables": true   // in `strict`; keep it if strict is relaxed
  }
}
```

- **`noUncheckedIndexedAccess` is the one people most want to skip and most need.** Without it, `xs[i]` and `record[key]` are typed `T` while the value at runtime may be `undefined`, so the type lies at exactly the access that segfaults. With it on, an index read is `T | undefined` and the compiler forces the check. Keep it on; narrow at the read.
- **`exactOptionalPropertyTypes` distinguishes "absent" from "present and `undefined`."** With it on, `{ mode?: "a" | "b" }` forbids `{ mode: undefined }` — you must omit the key. This catches a real bug class around object spread and `Object.assign`, where a stray `undefined` overwrites a default.
- **Do not use `// @ts-ignore`; use `// @ts-expect-error` with a reason** — `expect-error` itself errors if the line below it stops being an error, so a stale suppression fails the build instead of rotting. Treat every suppression as a tracked, temporary debt (`ts-errors.md`).

## Ban `any`; take `unknown` at the boundary, then narrow

`any` is not a type — it is an escape hatch that switches the checker off for every value it touches and every value derived from it, silently. A value whose type is genuinely not known at compile time is `unknown`, the type-safe top: you can hold it, but you cannot *use* it until you narrow it. This is the single highest-leverage rule in the file.

- **Forbid `any` with `@typescript-eslint/no-explicit-any`, and type an unknown input as `unknown`.** With `any`, `payload.user.name` type-checks and throws at runtime; with `unknown`, it errors and forces a narrowing or a schema parse first. Where a third-party type leaks `any`, quarantine it at the module edge — parse or assert it into a known type immediately, so the `any` never spreads.

```ts
// The parse boundary: unknown in, a domain type out, narrowing in between.
function readPort(raw: unknown): number | undefined {
  if (typeof raw !== "string") return undefined;
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 && n < 65536 ? n : undefined;
}
```

- **`useUnknownInCatchVariables` makes a caught error `unknown`, which is correct** — anything can be thrown in JavaScript, so a `catch` binding is genuinely of unknown type. Narrow it (`err instanceof Error`) before reading `.message`; do not annotate it back to `any` (`ts-errors.md`).

## Model a closed set as a discriminated union, with an exhaustive `switch`

The central rule of this file: an invalid combination of state should not type-check. A closed set of variants is a discriminated union — an object union sharing a literal `kind` (or `type`, `tag`) field — and a `switch` over that field, whose `default` funnels into a `never`, becomes a compile-time exhaustiveness check. Add a variant and forget a branch, and the build breaks.

```ts
type Shape =
  | { readonly kind: "circle"; readonly radius: number }
  | { readonly kind: "rect"; readonly w: number; readonly h: number };

function assertNever(x: never): never {
  throw new Error(`unreachable variant: ${JSON.stringify(x)}`);
}

function area(s: Shape): number {
  switch (s.kind) {
    case "circle":
      return Math.PI * s.radius ** 2;
    case "rect":
      return s.w * s.h; // s narrowed to the rect member here
    default:
      return assertNever(s); // a new unhandled variant makes `s` not `never` → error
  }
}
```

- **Every closed variant type carries a literal discriminant; never reconstruct the variant from optional fields.** `{ radius?: number; w?: number; h?: number }` admits the illegal all-present and all-absent states and forces a defensive check at every read. The discriminated union makes those states unrepresentable and narrows each branch to exactly its own fields.
- **Back the exhaustive `switch` with the `@typescript-eslint/switch-exhaustiveness-check` rule.** The `never` default catches the gap at the call site; the lint rule catches it project-wide and does not depend on a hand-written default being present. Use both.
- **Prefer a discriminated union over an `enum`.** A `const`-assertion union (`as const` below) gives the same closed set with no runtime code emitted, no `enum` reverse-mapping footgun, and structural rather than nominal members. Reach for a TypeScript `enum` only when you need a named runtime object to iterate; default to the union.

## `as const` and literal types freeze a value into its narrowest type

By default TypeScript widens a literal to its base type — `"draft"` becomes `string`, `3` becomes `number`. An `as const` assertion says "this is exactly these values, deeply readonly," which is how a literal array becomes the source of truth for a union type.

```ts
const STATUSES = ["draft", "sent", "paid"] as const;
type Status = (typeof STATUSES)[number]; // "draft" | "sent" | "paid"

// One list drives the type, the runtime array, and any iteration — no drift.
function isStatus(s: string): s is Status {
  return (STATUSES as readonly string[]).includes(s);
}
```

- **Derive the type from the `as const` value with `typeof` and indexed access, so the union and the runtime list cannot drift apart.** Maintaining a hand-written `type Status = "draft" | "sent" | "paid"` *and* a separate array is two things to keep in sync; derive one from the other.

## Brand a domain scalar; make the cast reachable only in its constructor

A bare `string` or `number` carries no domain meaning and lets a caller pass the wrong one — a `UserId` where an `OrderId` is wanted, both `string`. TypeScript is structural, so two aliases of `string` are interchangeable; a *brand* — an intersection with a unique, uninhabited tag — makes them nominally distinct at compile time and erases to the bare primitive at runtime. This is the TypeScript form of a validating smart constructor.

```ts
declare const brand: unique symbol;
type Brand<T, B extends string> = T & { readonly [brand]: B };

type Money = Brand<number, "Money">;

/** The only constructor: nonnegative integer minor units, else fail closed. */
function money(cents: number): Money | undefined {
  if (!Number.isInteger(cents) || cents < 0) return undefined;
  return cents as Money; // the single sanctioned `as`, gated behind the checks
}

const total = (a: Money, b: Money): Money => (a + b) as Money;
```

- **Brand every scalar with a domain meaning and a constraint** — ids, an email, a nonnegative quantity, a bounded ratio — and keep the constructor and the `Brand` alias in one module so the cast is reachable nowhere else. This is the value-object building block from `craft-domain-modeling.md` expressed in TypeScript.
- **The one place an `as` assertion is correct is inside the validating constructor, after the guard.** Everywhere else, an assertion that produces a branded value forges the invariant. Keep the brand and its `as` colocated and unexported.
- **A brand is compile-time only; it does not survive `JSON.parse`.** A value that crossed a serialization boundary is `unknown` and must be re-validated, not re-cast — that is the schema's job (below), not the brand's.

## Generics: constrain to the smallest interface, and no wider (least power)

A type parameter that appears in only one position, constrained to exactly what the code uses, is a precise, reusable signature. A type parameter reached for reflexively — or left unconstrained where the body needs structure — buys nothing and loses inference.

```ts
// Constrain to the operation actually used; accept anything that satisfies it.
function maxBy<T, K extends number | string>(xs: readonly T[], key: (x: T) => K): T | undefined {
  let best: T | undefined;
  let bestK: K | undefined;
  for (const x of xs) {
    const k = key(x);
    if (bestK === undefined || k > bestK) [best, bestK] = [x, k];
  }
  return best;
}
```

- **State the constraint as the smallest shape the body relies on** (`extends { id: string }`, `extends readonly unknown[]`), rather than leaving a parameter unconstrained and then reaching for `any` inside. This is polymorphism by constraint from `craft-abstraction.md`.
- **Do not add a type parameter that is used exactly once and never relates two positions** — it is a `any` in disguise and defeats inference. A parameter earns its place by *linking* an input type to an output type or to another input.
- **Reach for `const` type parameters (`<const T>`) when you need a literal argument inferred narrowly** without forcing the caller to write `as const` at every call. Prefer the widest inference that is still correct; narrow deliberately.

## `type` vs `interface`: default to `type`

Both describe object shapes and are largely interchangeable for that case. The guides split — *Programming TypeScript* leans `interface` for object types; *Effective TypeScript* treats it as case-by-case. The house default is **`type`**, for consistency and range: a `type` alias also expresses unions, intersections, mapped and conditional types, tuples, and branded primitives, so one keyword covers the whole domain vocabulary and there is no rule to remember about which shapes get which keyword.

- **Use `type` by default; reach for `interface` in two cases.** First, a public API surface that third parties are meant to *extend* via declaration merging (rare in application code, common in a library's ambient types). Second, when profiling shows a hot type-checking path — the compiler caches `interface` relationships more aggressively than large intersection-heavy `type` aliases. Absent one of those, prefer `type`.
- **Declaration merging is a feature of `interface`, and usually a hazard in application code** — two same-named interfaces silently combine. That surprise is a reason to keep application models as `type` aliases, which cannot merge.

## Avoid `as` assertions and the non-null `!`; narrow instead

A type assertion (`x as T`) and the non-null operator (`x!`) both *tell* the compiler something it could not verify, trading a compile error now for a runtime error later. Prefer a check the compiler can *see*: control-flow narrowing, a user-defined type predicate, or a schema parse.

- **Replace `x!` with an explicit guard.** `noUncheckedIndexedAccess` makes `xs[0]` be `T | undefined` for a reason; `xs[0]!` throws that safety away. Narrow with `if (first === undefined) return …` and let the compiler carry the non-`undefined` type forward. Ban the operator with `@typescript-eslint/no-non-null-assertion`.
- **Write a user-defined type predicate for a reusable narrowing** the control-flow analysis can't infer on its own — and know it is an unchecked promise: the compiler trusts the boolean, so the predicate's body must actually establish the type.

```ts
interface User { readonly id: string; readonly email: string }

function isUser(x: unknown): x is User {
  return (
    typeof x === "object" && x !== null &&
    "id" in x && typeof (x as { id: unknown }).id === "string" &&
    "email" in x && typeof (x as { email: unknown }).email === "string"
  );
}
```

- **Reserve `as` for the two honest cases**: inside a validating constructor after its guard (the brand above), and the `as const` assertion, which only narrows and never widens or lies. A cast that *widens* a type toward `unknown` is safe; a cast that *narrows* toward a more specific type is the dangerous one — that is what the predicate or the schema is for. For anything at a runtime boundary, do not hand-write the predicate at all — use zod (below), which generates the check and the type from one schema.

## `satisfies` checks a value against a type without widening it

`as` forces a value to a type and can hide a mismatch; a bare annotation checks the value but *widens* it to the annotation, losing the literal precision. `satisfies` (TypeScript 4.9) does both right — it verifies the value conforms and keeps the value's own narrow inferred type.

```ts
type Config = Record<string, { readonly url: string; readonly retries: number }>;

const endpoints = {
  auth: { url: "/auth", retries: 3 },
  data: { url: "/data", retries: 1 },
} satisfies Config;

endpoints.auth.retries; // still `number`, and `endpoints`' keys stay known — not widened to Config
```

- **Use `satisfies` to validate a literal against a contract while preserving its exact keys and value types.** With `: Config` the keys widen to `string` and you lose autocomplete on `endpoints.auth`; with `as Config` a typo in a field is silently accepted. `satisfies` catches the typo and keeps the precision.

## `readonly` and `Readonly<T>` for immutability the type enforces

A value object is defined by its attributes and replaced rather than mutated (`craft-domain-modeling.md`). Encode that with `readonly` fields and `readonly T[]` / `ReadonlyArray<T>` parameters, so a mutation is a compile error rather than a convention.

```ts
interface Order {
  readonly id: OrderId;
  readonly lines: readonly OrderLine[]; // no push/splice; construct a new array to "change"
}

// Accept the least-privileged type: a function that only reads should take readonly.
function subtotal(lines: readonly OrderLine[]): Money { /* ... */ }
```

- **Mark value-object fields `readonly`, take `readonly T[]` in any parameter you only read, and reach for `Readonly<T>` to derive an immutable view of an existing shape.** `readonly` is shallow, so nest it (`readonly OrderLine[]` whose elements are themselves `readonly`) or use a deep-readonly utility where the whole graph must be frozen. This is compile-time only — combine with `Object.freeze` at a trust boundary if a runtime guarantee is needed.

## zod at the untrusted boundary — where the compiler cannot reach

Types are erased, so at every input the program did not itself construct — an HTTP body, a config file, `JSON.parse`, `localStorage`, a model response — the type is a claim about data the compiler never saw. A `x as ApiUser` there is a lie the runtime discovers. Define the shape once as a zod schema, and derive the static type *from* the schema so the two cannot drift.

```ts
import { z } from "zod";

const User = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  age: z.number().int().nonnegative(),
});
type User = z.infer<typeof User>; // the type is generated from the schema

function loadUser(raw: unknown): User | undefined {
  const parsed = User.safeParse(raw); // no throw; a tagged result
  return parsed.success ? parsed.data : undefined; // fail closed on invalid input
}
```

- **Parse, don't assert, at every boundary.** `safeParse` returns `{ success: true; data } | { success: false; error }` — narrow it and fail closed, rather than `parse` throwing into a `catch` (reserve `parse` for a startup config where a throw *is* the correct fail-fast). Past a successful parse, the value is `User` and the rest of the program is honest.
- **Derive the type with `z.infer<typeof Schema>`; do not hand-write a parallel `interface`.** One schema is the single source of truth for the runtime check and the static type; a separately maintained type is a second thing to keep in sync and the exact drift the boundary exists to prevent. This is the typed model boundary `ts-llm.md` builds the structured-output contract on and the input contract `ts-security.md` requires.
- **Combine the schema with a brand for a validated scalar**: `z.string().uuid().transform((s) => s as UserId)` produces a `UserId` only past the runtime check, uniting the boundary parse and the nominal brand in one place.

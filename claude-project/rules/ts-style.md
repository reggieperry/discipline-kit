---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.mts"
  - "**/*.cts"
---

# TypeScript style and idioms

The base layer of TypeScript and JavaScript discipline: formatting, naming, the binding and immutability defaults, the ESM module idioms, and the operator and collection idioms everything else builds on. Sources: the TypeScript Handbook (typescriptlang.org/docs/handbook), Dan Vanderkam's *Effective TypeScript*, the Google TypeScript Style Guide (google.github.io/styleguide/tsguide.html), the Airbnb JavaScript Style Guide, the typescript-eslint recommended and stylistic configs (typescript-eslint.io/rules), Prettier, and MDN. The reason this rule exists is that JavaScript gives many ways to write the same thing — `var`/`let`/`const`, four ways to compare, function declarations versus arrows, default versus named exports — and TypeScript adds more; the flexibility is the sharpest risk, so the house spends it once, here, on one standard rather than re-litigating it per file. Where the major guides disagree, the disagreement is named with a house default and a reason.

> See `craft-complexity.md` for why precise, consistent names lower cognitive load, `craft-documentation.md` for the language-neutral comment discipline the TSDoc mechanics here implement, `ts-types.md` for `type`-versus-`interface`, discriminated unions, and the strict-`tsconfig` settings referenced here, `ts-errors.md` for the `Error`/`Result` and exhaustiveness idioms, `ts-testing.md` for the test conventions, and `ts-modules.md` for package layout and the ESM boundary. `ts-react.md` and `ts-security.md` carry the framework and injection specifics.

## Formatting

- **Run Prettier on every file; never hand-format.** The machine owns indentation, wrapping, quotes, and semicolons, so the style debate does not exist — a Prettier config plus a CI check ends it. Wire `eslint-config-prettier` in so ESLint stops reporting anything Prettier already fixes; leave the layout rules to Prettier and keep ESLint for correctness.
- **Semicolons on.** *Disagreement:* StandardJS omits them and relies on automatic semicolon insertion; Google, Airbnb, and the Prettier default (`semi: true`) keep them. Default: keep semicolons — ASI has genuine footguns (a line starting `(` or `[` after a return-less statement), and an explicit terminator removes the class of bug entirely.
- **Single quotes, two-space indent, trailing commas.** *Disagreement:* Prettier defaults to double quotes (`singleQuote: false`); Google and Airbnb use single. Default: single quotes with `singleQuote: true`, falling back to double only to avoid escaping. Set `trailingComma: 'all'` (the Prettier 3 default) so an added last element is a one-line diff, not two.

## Naming

- **`camelCase` for variables, functions, methods, and parameters; `PascalCase` for types, interfaces, classes, enums, and enum members; `UPPER_SNAKE_CASE` only for a true module-level constant of a primitive.** A `const` that holds an object or is computed is still `camelCase` — the casing marks *deep immutability and primitiveness*, not merely the `const` keyword.
- **Do not encode the type in the name** — no Hungarian notation, no `strName`, no `arrUsers`, no `IUser` interface prefix (Google and typescript-eslint both reject the `I` prefix). The type annotation already carries the type; a name that repeats it drifts when the type changes. Name for the role: `users`, not `userArray`; `open`, not `bIsOpen`.
- **Scale name length with scope** — a one-letter `i` in a short loop or `e` for a caught error is fine; a name used far from its declaration or across a module boundary earns a descriptive name. Keep the domain term identical across speech, docs, and code (`craft-complexity.md`, `craft-domain-modeling.md`); rename everywhere when the term shifts.
- **Mechanize casing with `@typescript-eslint/naming-convention`** rather than reviewing it by eye — one rule pins the whole scheme (variable/function `camelCase`, type-like `PascalCase`, the `UPPER_CASE` exception) so it never becomes a review comment.

```ts
// Casing marks the kind of thing. UPPER_SNAKE only for a primitive constant.
const MAX_RETRIES = 3;
const defaultConfig = { retries: MAX_RETRIES }; // an object const stays camelCase

type Money = { readonly amountMinor: number; readonly currency: string };
interface User { readonly id: string; readonly name: string } // no `IUser`
```

## Variables and bindings

- **`const` by default, `let` only when a binding genuinely must be reassigned, and `var` never.** `var` is function-scoped and hoisted, which reintroduces exactly the aliasing and temporal-dead-zone confusion block scoping removed; the core `no-var` and `prefer-const` rules make this mechanical. Reach for `let` only for a counter or an accumulator that cannot be expressed as a `const` bound to an expression.
- **Prefer an expression that produces the value over a `let` mutated across branches.** A `const` assigned from a ternary or an immediately-invoked arrow beats declaring `let x` and writing `x` in each `if` arm — the value is defined in one place and cannot be left unset.
- **Do not reassign or mutate a parameter.** Treat parameters as inputs; derive a new local instead (the core `no-param-reassign` rule, `props: true` to also forbid mutating a passed object's fields). A mutated argument is a side channel the caller cannot see. (`ts-types.md` for `readonly` parameter types.)

```ts
// A const from an expression, not a reassigned let.
const tier = amount > 10_000 ? 'enterprise' : amount > 1_000 ? 'pro' : 'free';

// Derive, never mutate the parameter.
function withTax(order: Order): Order {
  return { ...order, total: order.subtotal * 1.08 };
}
```

## Functions — arrow versus declaration

- **Use a `function` declaration for a named top-level or exported function; use an arrow for a callback, a closure, or anything short and inline.** *Disagreement:* Airbnb leans arrow-first even at module scope; Google and the TypeScript Handbook use named `function` declarations for standalone functions and arrows for callbacks. Default: named `function` for a standalone unit — it hoists (so call-before-definition and mutual recursion read naturally), and it names itself in a stack trace — and arrow for the passed-in case.
- **Reach for an arrow whenever `this` must stay lexical** — a callback inside a method, an event handler on a class field. An arrow has no own `this`, so it closes over the enclosing one instead of silently rebinding it. This is the decisive reason to prefer arrows for callbacks, not concision alone.
- **Keep an arrow body an expression when it is one; add braces and an explicit `return` when the body has statements.** Do not write a braced arrow that only returns, and do not chain a multi-line expression body that a reader must parse for the implicit return.
- **Never bind an arrow to a name where a declaration would do** the same job with a better trace and hoisting — reserve the named-arrow-constant form for the genuinely higher-order case (a curried factory, a memoized closure).

```ts
// Named declaration for the standalone function; arrow for the callback.
function totalOwed(orders: readonly Order[]): number {
  return orders
    .filter((o) => !o.paid)
    .reduce((sum, o) => sum + o.total, 0);
}
```

## Modules — ESM import and export

- **Write ES modules — `import`/`export`, never CommonJS `require`/`module.exports`** in new code, and set the `tsconfig` `module`/`moduleResolution` to a modern ESM target (`ts-modules.md`). ESM is statically analyzable, so it tree-shakes and the toolchain can check an import resolves.
- **Prefer named exports over a default export.** *Disagreement:* Airbnb prefers a default export for a single-export module; Google bans default exports outright. Default: named exports — a default export has no canonical name, so every importer may rename it, which defeats grep, breaks safe automated rename, and hides typos (`import foo from './bar'` never errors on a missing symbol). Export the symbol under its real name and import it by that name.
- **Group and order imports: external packages, then internal absolute paths, then relative — with the type-only imports marked.** Let an import-sort rule own the ordering so it is never a review comment. Use `import type { User } from './user'` (and `export type`) for a type-only import so the emit strips it and there is no accidental runtime dependency or side-effect load.
- **Import a namespace only for a module that is genuinely a namespace** (`import * as path from 'node:path'`); otherwise name the specific bindings you use so the surface is visible and tree-shakeable. Never re-export a barrel `index.ts` that pulls the whole subtree in solely to shorten an import path — it defeats tree-shaking and invites import cycles.

```ts
import { readFile } from 'node:fs/promises'; // external / builtin first

import { formatMoney } from '@app/money'; // internal absolute

import type { Order } from './order'; // type-only, stripped at emit
import { priceOrder } from './pricing'; // relative last

export { priceOrder }; // named, not default
```

## Strings and template literals

- **Use a template literal for any interpolation or multiline string; never build a string with `+`.** `` `${user.name} owes ${formatMoney(total)}` `` reads in order and cannot drop a space or coerce a number the wrong way; the core `prefer-template` rule enforces it. Reserve `+` for genuine numeric addition.
- **Do not nest a heavy expression inside a `${}`** — compute it into a named `const` first. A template's value is that it reads as text with holes; a hole containing a ternary and a method chain defeats that.
- **Keep quote style uniform** (Prettier settles it) and prefer a plain string literal over a single-placeholder template — `` `error` `` gains nothing over `'error'`.

## Optional chaining and nullish coalescing

- **Reach a possibly-absent member with `?.` and supply a fallback with `??`.** `user?.address?.city ?? 'unknown'` short-circuits to `undefined` on the first absent link and then substitutes the default; the typescript-eslint `prefer-optional-chain` and `prefer-nullish-coalescing` rules flag the hand-rolled `&&`/`||` equivalents.
- **Default with `??`, not `||`, whenever `0`, `''`, or `false` is a valid value.** `||` coalesces on any falsy value, so `count || 10` turns a real `0` into `10` — a classic defect. Use `??` so only `null` and `undefined` trigger the fallback; reserve `||` for a genuine boolean-or.
- **`?.` reports absence, it does not create presence** — `a?.b.c` still throws if `b` is present but `c`'s access is on `undefined` further down, and `arr?.[0]` guards `arr`, not the element. Chain the `?.` at each link that can actually be absent, and no further. (`ts-types.md` for modeling absence in the type — `T | undefined` and `noUncheckedIndexedAccess` — so the compiler tells you where a `?.` is required.)
- **Do not paper over a type error with `?.` or `!`.** A `?.` on a value the type says is always present is dead code that misleads the reader; the non-null assertion `!` silently overrides the checker and is banned by default (`@typescript-eslint/no-non-null-assertion`) — narrow with a guard instead, so the compiler proves presence rather than being told to assume it.

```ts
// ?. for the absent link, ?? for the default — 0 and '' survive.
const city = user?.address?.city ?? 'unknown';
const retries = config.retries ?? 3; // a configured 0 is honored, not overwritten
```

## Immutability

- **Declare a field, parameter, or array `readonly` unless it is genuinely mutated in place.** `readonly` is a compile-time guarantee at zero runtime cost; make the mutable case the marked exception. A value object — `Money`, a coordinate, a config — is `readonly` throughout and replaced whole rather than edited in part (`craft-domain-modeling.md`).
- **Freeze a literal you mean to be constant with `as const`.** `as const` narrows to the literal type and makes the whole structure deeply `readonly`, which is what turns a lookup table or a discriminant list into a source of truth the compiler enforces — and it is how you derive a union type from an array of literals (`ts-types.md`).
- **Produce a new value instead of mutating; use spread and the non-mutating array methods.** `{ ...order, paid: true }` and `[...items, next]` beat assigning a field or `push`; `toSorted`/`toReversed`/`with` beat their mutating `sort`/`reverse`/`splice` siblings when you must not disturb the input. `map`/`filter` already return fresh arrays.
- **Prefer `prefer-readonly` for private class fields never reassigned after the constructor** so the checker proves the intent. Runtime `Object.freeze` is a defense against a specific mutation bug at a trust boundary, not the default — the type-level `readonly` is the everyday tool.

```ts
// A value object: readonly throughout, replaced whole.
type Money = { readonly amountMinor: number; readonly currency: 'USD' | 'EUR' };

const CURRENCIES = ['USD', 'EUR'] as const; // deeply readonly, literal-typed
type Currency = (typeof CURRENCIES)[number]; // 'USD' | 'EUR'

const paid = { ...order, paid: true }; // new value, input untouched
```

## Collections and combinators

- **Reach for `map`, `filter`, `reduce`, `flatMap`, `find`, and `some`/`every` over a manual `for` loop.** The combinator names the intent and returns a fresh value; the loop hides the intent behind an index and a mutable accumulator. Chain them for a pipeline, and break a long chain across lines so each stage reads on its own.
- **Use `reduce` only where a fold is the clearest expression** — an accumulation into a single value or a keyed object. When a `reduce` grows a nontrivial body, or when the result is another array, a `map`/`filter` pair or a small loop is plainer; do not force everything through `reduce`.
- **Prefer a `for...of` loop over `for...in` or a C-style index loop** when you do need an imperative loop — for a genuine side effect, an early `break`, or an `await` in sequence. `for...in` iterates enumerable keys including inherited ones and is a common bug; reserve the index form for when the index itself is the point.
- **Use `Map` and `Set` for keyed and membership collections, not a plain object as a poor man's map.** An object keyed by arbitrary strings collides with prototype keys and loses insertion order semantics; `Map` states the intent, keys on any type, and has a real `size`. Reserve the object literal for a fixed-shape record.

```ts
// A combinator pipeline reads as a sequence of transforms.
const activeEmails = users
  .filter((u) => u.active)
  .map((u) => u.email)
  .filter((e): e is string => e !== undefined);

// for...of for the side-effecting, sequential, awaited case.
for (const order of pending) {
  await settle(order);
}
```

## Equality and truthiness

- **Compare with `===` and `!==`, never `==`/`!=`.** Loose equality applies a table of coercions (`'' == 0`, `null == undefined`, `[] == false`) that almost no one has memorized correctly; the core `eqeqeq` rule bans it. The one deliberate exception some guides allow — `x == null` to catch both `null` and `undefined` — is unnecessary here because `x == null` is better written `x === null || x === undefined`, or the absence is modeled in the type and narrowed.
- **Guard on an explicit predicate, not on truthiness, whenever `0`, `''`, `NaN`, or `false` is a legitimate value.** `if (count)` is a bug when `0` is valid; write `if (count > 0)` or `if (count !== undefined)`. `if (list.length)` is likewise sharper as `if (list.length > 0)`. Reserve bare truthiness for a value whose type is exactly `boolean`.
- **Test presence explicitly.** For a `T | null | undefined`, narrow with `if (value !== undefined)` or `value != null`-free equivalents, or use optional chaining and `??`; do not lean on `if (value)` to mean "present," which also rejects a valid falsy value. Turn on `@typescript-eslint/no-unnecessary-condition` so the checker flags both a condition that is always truthy and one that is always falsy — usually the sign of a mismodeled type.
- **Prefer a `switch` over a discriminant with `switch-exhaustiveness-check`, or an exhaustive `if`/`else` with a `never` guard, so a new union member is a compile error rather than a silent fall-through.** (`ts-errors.md` owns the `assertNever` pattern and why an unhandled case is a defect, not a style nit.)

```ts
// === always; explicit predicate over truthiness for a numeric zero.
if (order.total > 0 && order.currency === 'USD') {
  charge(order);
}

// Presence tested explicitly, not by truthiness of a possibly-empty string.
const label = order.note !== undefined ? order.note : 'no note';
```

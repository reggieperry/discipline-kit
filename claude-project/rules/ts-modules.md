---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "package.json"
  - "tsconfig.json"
---

# TypeScript project and dependency structure

How to organize modules, draw boundaries between them, and configure the resolver and the package manifest so imports mean one thing. Sources of record: the TypeScript Handbook on Modules and Module Resolution (typescriptlang.org/docs/handbook/modules), the Node.js ESM and Packages documentation (nodejs.org/api/esm.html, /api/packages.html), the Vite guide on `resolve.alias` and env (vite.dev/config/shared-options), the package.json `exports` field reference, and typescript-eslint (`consistent-type-imports`) plus `eslint-plugin-import` (`no-cycle`). One house rule governs the rest: **this is an ES-modules codebase — every package sets `"type": "module"`, and there is no CommonJS in first-party source.**

> See `ts-types.md` for the branded value types and discriminated unions these modules pass across their seams, `ts-style.md` for import ordering and naming, `ts-errors.md` for the error types that cross a boundary, `ts-react.md` for feature-folder layout in a component tree, `craft-complexity.md` for deep cohesive modules and the dependency-versus-obscurity frame, and `craft-domain-modeling.md` for drawing module boundaries along bounded-context seams.

## ESM everywhere: `"type": "module"`

The one thing this set rests on is a single module system. TypeScript's sharpest practical hazard is not a thin corpus — it is a *split* one: CommonJS against ESM, `require` against `import`, three live `moduleResolution` modes, and a decade of blog posts describing a `tsconfig` that no longer resolves the way it did. Types catch a type error; they do not catch "configured the resolver for the wrong host." Every rule here collapses that fragmentation to one coherent shape the model can pattern-match against.

- **Set `"type": "module"` in every `package.json` and write `import`/`export`, never `require`/`module.exports`.** A `.ts` file is an ES module. The only CommonJS in the tree is a third-party dependency the runtime interops with, never first-party source.
- **Do not mix `require()` into module code.** When a dependency ships CommonJS only, import it with a default or namespace import and let ESM interop handle the bridge (`import pkg from "legacy-cjs"`), wrapped once at the seam. Never thread a raw `require` through the app.
- **Prefer top-level `await` and static `import` over dynamic `import()` for wiring**; reserve `import()` for a genuine code-split boundary or an optional dependency loaded on demand.

```ts
// House default — an ES module with named exports.
import { parseMoney } from "./money.js";
export function totalOrder(order: Order): Money { /* … */ }

// Banned — CommonJS in first-party source.
// const { parseMoney } = require("./money");
// module.exports = { totalOrder };
```

## Named exports over default

- **Default to named exports; avoid `export default`.** A named export has one spelling every call site and every editor rename shares, so a symbol is greppable and refactor-safe across the tree. A default export is renamed freely at each import, which fragments the name the way orphan instances fragment an interface — the same value acquires three spellings and a typo-import silently binds to nothing.
- **Reserve `export default` for the boundaries a host framework demands it** — a Vite/Node config module, a React lazy-loaded route where the tooling expects a default, a page module under a file-based router. Those are host contracts, not a style choice; everywhere else, name the export.
- **One primary concept per module, exported by name.** If a module needs a default to feel natural, it is usually doing two jobs — split it (`craft-complexity.md`: a deep module has a small, named surface).
- **Turn the rule on in lint** — `import/no-default-export` scoped to `src`, with an override that permits defaults in the framework-owned files above, so the exception is declared rather than assumed.

```ts
// Good — named, greppable, rename-safe.
export function priceQuote(order: Order): Money { /* … */ }
export type Quote = { total: Money; expires: Date };

// Avoid — the importer picks the name, so it drifts.
// export default function (order: Order) { /* … */ }
```

## Module resolution: NodeNext for Node, Bundler for Vite

Where you point `moduleResolution` is a correctness decision tied to who resolves the imports at runtime, not a preference. The two modern modes disagree on exactly one thing that shows up in every relative import — the file extension — so pick by host and be consistent.

- **A Node service, a CLI, or a published library uses `"module": "nodenext"` with `"moduleResolution": "nodenext"`, and every relative import carries an explicit `.js` extension.** Node's ESM resolver does not search extensions, so the specifier must name the emitted file — which is `.js` even though the source is `.ts`. This reads wrong the first time and is correct: you are importing the compiled artifact.
- **A Vite (or other bundler) app uses `"moduleResolution": "bundler"` and omits extensions on relative imports.** `bundler` mode honors package.json `exports` like `nodenext` but never requires an extension, because the bundler — not Node — resolves the graph. Pair it with `"module": "esnext"` (or `"preserve"`) since Vite emits the final module format.
- **Do not carry `.js` extensions into a `bundler`-mode app or drop them from a `nodenext` one.** The mismatch either fails to resolve or emits specifiers the host can't load. One mode per package; state it once in the base `tsconfig` and let packages inherit.
- **Turn on `"verbatimModuleSyntax": true`.** It forces `import type` on type-only imports and forbids an ambiguous import that depends on `esModuleInterop`, so what you write is what gets emitted — no elided-import surprises at the CJS/ESM boundary.

```jsonc
// tsconfig.json — a Node service (extensions required in source).
{ "compilerOptions": { "module": "nodenext", "moduleResolution": "nodenext", "verbatimModuleSyntax": true } }
// import { parseMoney } from "./money.js";   // names the emitted file

// tsconfig.json — a Vite app (the bundler resolves; no extensions).
{ "compilerOptions": { "module": "esnext", "moduleResolution": "bundler", "verbatimModuleSyntax": true } }
// import { parseMoney } from "./money";
```

## Type-only imports at the seam

- **Import types with `import type` (or an inline `type` specifier), and let a value and a type from one module split into two statements.** A type-only import is erased at emit, so it never creates a runtime edge — which keeps a purely-type dependency out of the cycle detector and out of the bundle.
- **Enforce it with `@typescript-eslint/consistent-type-imports`** rather than by hand; the fixer rewrites a mixed import into a `type`-qualified one. This is what makes `verbatimModuleSyntax` painless — the lint keeps the annotations honest.

```ts
import { priceQuote } from "./pricing.js";   // value edge — real at runtime
import type { Quote } from "./pricing.js";    // type edge — erased at emit
```

## Module boundaries: import through the public surface, never into internals

- **A feature imports another feature only through its entry module — never a deep path into its internals.** `import { priceQuote } from "@/pricing"` is a contract; `import { roundHalfEven } from "@/pricing/internal/round.js"` reaches past the interface and welds the caller to a private decision (`craft-complexity.md`: information leakage is the top red flag — the same knowledge embedded in two modules).
- **Draw the hardest boundaries along bounded-context seams first, then partition within** (`craft-domain-modeling.md`). Where your code meets a model it does not own — a third-party SDK, an HTTP payload, the LLM's output schema — put a module boundary with an explicit translation type at it (a parsed domain value, a validated DTO), rather than letting the foreign shape leak across every call site.
- **Enforce the boundary mechanically with `no-restricted-imports` `patterns`**, blocking cross-feature deep paths so the rule is a build failure, not a code-review hope.

```jsonc
// eslint — a feature may be imported by its entry, never by an internal path.
"no-restricted-imports": ["error", { "patterns": [
  { "group": ["@/*/internal/*", "@/*/*"], "message": "Import a feature through its index, not its internals." }
]}]
```

## Barrel files: index as the contract, not a re-export of everything

A barrel is an `index.ts` that re-exports a directory. It is the right tool for one job — publishing a module's public surface — and the wrong tool the moment it re-exports the whole subtree.

- **Give each module one `index.ts` that names its public exports explicitly; that file *is* the module's contract.** Everything not re-exported there is internal and reshapeable without breaking a caller (`craft-complexity.md`: a small, stable interface over substantial internals).
- **Do not build a root barrel that re-exports every feature.** A whole-app barrel is the classic cause of import cycles — feature A's index pulls feature B's index which transitively pulls A — and it defeats tree-shaking, because importing one symbol drags the module-init side effects of the entire graph into the bundle.
- **Never let two modules import each other through their barrels.** A cycle means a boundary is in the wrong place — extract the shared type into a third module both depend on (`craft-domain-modeling.md`), rather than papering the loop with a lazy import.
- **Detect cycles in CI with `import/no-cycle`.** It ignores `import type` edges (correctly — those are erased), so it flags only the runtime loops that actually bite. A green run is the evidence that the dependency arrows stay one-directional.

```ts
// pricing/index.ts — the contract: three names, nothing else escapes.
export { priceQuote } from "./quote.js";
export type { Quote } from "./quote.js";
export { PricingError } from "./errors.js";
// round.ts, table.ts, and the rest stay internal.
```

## Path aliases: one source of truth in tsconfig, mirrored to the resolver

- **Define aliases once in `tsconfig.json` `compilerOptions.paths`, keyed off `baseUrl` (or the alias root), and let the runtime resolver mirror them.** A `@/` root that maps to `src` keeps imports stable under a file move and reads as an absolute address rather than a `../../../` climb.
- **`tsc` only type-checks these — the runtime resolver must be told the same mapping.** Under Vite, either the `vite-tsconfig-paths` plugin (which reads `compilerOptions.paths` directly, so there is a single source of truth) or an explicit `resolve.alias` entry. Under Node, a loader or the package's own `imports` map. Never rely on `paths` alone; TypeScript does not rewrite specifiers at emit, so an unmapped runtime crashes at import.
- **Prefer package-relative `imports` subpaths (`#internal/*`) for a published library**, since they are a Node-native manifest feature the runtime honors without a build step; reserve `tsconfig` `paths` for app code a bundler owns.

```jsonc
// tsconfig.json
{ "compilerOptions": { "baseUrl": ".", "paths": { "@/*": ["src/*"] } } }
```

```ts
// vite.config.ts — mirror the alias so the runtime resolves it too.
import tsconfigPaths from "vite-tsconfig-paths";
export default { plugins: [tsconfigPaths()] };
// or, explicitly:  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } }
```

## package.json: `exports` is the public boundary, `types` comes first

For a published package the manifest *is* the module boundary — a consumer can import only what `exports` lets through, so treat it the way you treat an `index.ts`.

- **Declare the public surface in `exports`; drop `main`/`module` in favor of it.** `exports` both advertises the entry points and *encapsulates* the rest — a subpath not listed is unreachable from outside, which is how you keep a deep-import from welding a consumer to an internal file.
- **Put the `types` condition first in every conditional block.** Conditions are matched top-to-bottom and the first hit wins, so a `types` entry after `import`/`require` is shadowed and the consumer gets no declarations. Point it at the `.d.ts` that matches the resolution mode.
- **Publish ESM-only unless a real CommonJS consumer forces dual output.** A dual package doubles the build and invites the "types don't match the runtime format" trap; ship one format, set `"type": "module"`, and add a `require` condition only when a concrete CJS consumer appears.
- **Set `"sideEffects": false`** (or list the few files that have them) so a bundler can tree-shake the package — the manifest-level complement to avoiding whole-tree barrels.

```jsonc
{
  "type": "module",
  "sideEffects": false,
  "exports": {
    ".":         { "types": "./dist/index.d.ts", "import": "./dist/index.js" },
    "./pricing": { "types": "./dist/pricing/index.d.ts", "import": "./dist/pricing/index.js" }
  }
}
```

## Dependencies: pin, audit, minimize, one direction

- **Pin dependencies and keep the lockfile honest.** Commit the lockfile, install with `--frozen-lockfile` in CI, and pin an SDK to a version known compatible with the toolchain rather than floating a range (this matters most for the model SDK and its schema-generation peer — see `ts-llm.md`).
- **Audit and minimize.** Run the package manager's audit in CI, prefer the platform primitive over a micro-dependency, and treat a new transitive tree as a cost. Every dependency is code you can't change in isolation (`craft-complexity.md`).
- **Keep dependency arrows one-directional.** Domain modules depend inward toward shared value types, never sideways into a peer feature's internals; a cycle — caught by `import/no-cycle` — means a boundary is misdrawn, so extract the shared piece rather than close the loop.
- **Draw the pure-versus-effectful seam structurally.** Keep the domain-logic modules free of I/O imports (no `fs`, no `fetch`, no SDK) so they stay unit-testable and the effects live at the app edges — the module graph makes the purity rule enforceable rather than aspirational (`craft-domain-modeling.md`).

## Name modules after the domain, never `utils`

- **Name a module after the domain concept it owns** — `pricing`, `billing`, `inventory`, `scheduling` — never `utils`, `common`, `helpers`, `shared`, or `lib` as a grab-bag. The import site reads `pricing.priceQuote`, so the module name is part of every call that uses it; a name with no cohesive responsibility becomes a dumping ground and its imports tell the reader nothing.
- **Keep modules deep and cohesive — a small public surface over substantial internals — not many shallow files each re-exporting one function** (`craft-complexity.md`: reject classitis). A folder of one-function modules multiplies interface for no benefit.
- **When a genuinely generic helper exists, name it for what it does** — `formatMoney`, `parseIsoDate` — and home it in the domain module that owns the concept, not in a catch-all. A truly cross-cutting primitive earns its own named module (`money`, `dates`), never `utils`.

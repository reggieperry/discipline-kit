---
paths:
  - "**/*.tsx"
  - "**/*.jsx"
---

# React and Vite discipline

The framework layer for a React application built with Vite: function components, the Rules of Hooks, how props and state are typed, the derive-don't-store principle, what an effect is actually for, and the Vite dev-server and build seams. Sources: the current React docs (react.dev — Rules of Hooks, You Might Not Need an Effect, Passing Props to a Component, Rendering Lists, Keeping Components Pure, and the React 19 / React Compiler notes), the Vite guide (vite.dev — Server Options, Env Variables and Modes, Building for Production), and the lint stack that mechanizes all of it: `typescript-eslint`, `eslint-plugin-react-hooks`, and `eslint-plugin-jsx-a11y`. Where the guidance leaves a choice open, the choice is named with a house default and a reason. A recurring theme below is derive-don't-store — a component's rendered output is a pure function of its props and state, so state that merely mirrors other state is a defect, not an optimization; several rules below are that principle applied.

> See `ts-types.md` for the discriminated-union and `as const` modeling the prop types here lean on, `ts-errors.md` for the error and loading states an async view must render (never a thrown render), `ts-testing.md` for testing a component through its rendered output rather than its internals, and `ts-security.md` for why a `VITE_`-prefixed variable is public. `craft-complexity.md` supplies the deep-module and single-vocabulary rationale, `craft-abstraction.md` the specification-over-representation split a component's props express, and `craft-domain-modeling.md` the value objects a well-typed component renders.

## Formatting and the lint stack

- **Run Prettier on every file; never hand-align JSX.** The machine owns wrapping and indentation, so the formatting debate does not exist. Lint the semantics separately with `typescript-eslint` (type-aware rules), `eslint-plugin-react-hooks`, and `eslint-plugin-jsx-a11y` — three checkers doing three different jobs, none of which Prettier does.
- **Turn the two hook rules on and treat them as build-breaking.** `react-hooks/rules-of-hooks` is an `error`; keep `react-hooks/exhaustive-deps` at least a `warn` and fix every warning rather than suppressing it (the flat-config preset is `reactHooks.configs.flat.recommended`). These two catch the defects that survive `tsc` — a hook called conditionally, an effect that reads a stale value — because the type system cannot see them.
- **Extend `jsx-a11y`'s recommended flat config (`jsxA11y.flatConfigs.recommended`).** Accessibility findings are correctness findings; do not carry a growing list of `eslint-disable-next-line jsx-a11y/*` — each one is an interaction a real user cannot complete. (`ts-testing.md` owns why a suppression is a debt the differential gate tracks.)

## Function components only

- **Write every component as a function that returns JSX; never a class component.** Class components are legacy — hooks are the whole state-and-lifecycle model now, and mixing the two idioms fragments the codebase the way `craft-complexity.md` warns against. A component is a plain function whose name is upper camel case (`DealPanel`, not `dealPanel`) so JSX can tell it from an HTML tag.
- **Keep a component a pure function of its props and state during render.** Rendering computes JSX and touches nothing else — no mutation of a prop, no write to a module-level variable, no network call, no DOM poke. React may call render more than once and discard the result; a render with a side effect corrupts under that. Side effects belong in an event handler or, for external synchronization, an effect (below). This is the Keeping Components Pure rule, and it is the same "single source of truth, no side state" principle stated at the component grain.

```tsx
// A component is a pure view of its inputs — compute, return, mutate nothing.
function OrderTotal({ order }: { order: Order }): React.ReactElement {
  const total = order.lines.reduce((sum, line) => sum.add(line.amount), Money.zero);
  return <span>{total.format()}</span>;
}
```

## The Rules of Hooks

Hooks are the state model, and they carry two non-negotiable rules the `react-hooks` plugin enforces — get either wrong and state silently attaches to the wrong render.

- **Call hooks only at the top level of a component or another hook — never inside a condition, a loop, a nested function, a `try`/`catch`, or after an early `return`.** React identifies a hook by its call order, so a conditional call desynchronizes every hook after it. When a value is conditional, put the condition inside the hook, not the hook inside the condition.
- **Call hooks only from a React function component or a custom hook — never from a plain function, an event handler, or a class.** A function that calls a hook *is* a custom hook and its name must start with `use` (`useDealStatus`), which is how the linter and the reader both know it obeys these rules.
- **Give an effect a complete dependency array and let `exhaustive-deps` police it.** Every reactive value the effect body reads — prop, state, or a value derived from them — goes in the array. Do not trim the array to control when the effect runs; that ships a closure over a stale value. If the effect runs too often, the fix is to remove the dependency at its source (memoize the function, move a constant out of the component), not to lie to the linter.

```tsx
// Hook at the top level, unconditionally; the condition lives inside.
function DealStatus({ dealId }: { dealId: DealId }): React.ReactElement {
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    if (dealId === null) return;          // condition inside the hook
    const sub = subscribe(dealId, setStatus);
    return () => sub.unsubscribe();       // cleanup — see the effects section
  }, [dealId]);                           // complete deps; exhaustive-deps verified

  return <StatusBadge status={status} />;
}
```

## Typing props and state

- **Type props as a named interface or type alias; do not annotate the component with `React.FC`.** The house default is a plain typed parameter, not `React.FC<Props>`. `React.FC` buys nothing now that it no longer implies `children`, it makes generic components awkward, and it obscures the return type — a component is just a function `(props: Props) => React.ReactElement`, so type it as one. Name the props type after the component (`DealPanelProps`) when it is exported or reused, and inline it for a one-off leaf.
- **Type `children` explicitly as `React.ReactNode` when a component accepts them.** Because the implicit-children era is over, a wrapper must declare `children: React.ReactNode` in its props — the widest correct type, admitting elements, strings, numbers, fragments, and `null`. Reach for `React.ReactElement` only when you genuinely require a single element.
- **Model mutually exclusive prop shapes as a discriminated union, not a bag of optional booleans.** A component that is either a link or a button, or a panel that is loading, loaded, or errored, gets one union with a discriminant tag so the impossible combination cannot be constructed and the body `switch`es exhaustively. This is `craft-domain-modeling.md`'s make-illegal-states-unrepresentable applied to the prop boundary; `ts-types.md` owns the union mechanics.

```tsx
// Discriminated union: the three states are exclusive by construction.
type PanelProps =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; deal: Deal };

function DealPanel(props: PanelProps): React.ReactElement {
  switch (props.kind) {
    case "loading": return <Spinner />;
    case "error":   return <Alert>{props.message}</Alert>;
    case "ready":   return <DealBody deal={props.deal} />;
  }
}
```

## Derive, don't store

The core state discipline, and the component-grain form of the single-source-of-truth principle: state that mirrors other state is a second copy that will drift.

- **Compute derived data during render; do not hold it in state.** If a value can be calculated from props or existing state, calculate it inline every render — a filtered list, a total, a validity flag, a formatted string. Copying it into `useState` creates two sources of truth and an update path that will eventually forget to run — the source of a whole class of stale-UI bugs.
- **Do not use an effect to keep one piece of state in sync with another.** Setting state inside an effect to mirror a prop is the most common misuse — it renders once with the stale value, then again after the effect, and it is a derivation wearing an effect's clothes. Delete the state and the effect; compute the value in render.
- **Reach for `useMemo` only to skip an expensive recomputation, never for correctness.** `useMemo` is a performance cache with the same value the plain computation would produce; the code must be correct with the memo removed. Measure before adding one — most derived values are cheap enough that the plain expression is clearer and the memo is noise (`craft-complexity.md`'s zero-tolerance for gratuitous complexity).

```tsx
// Derived state is computed in render, not stored and synced.
function Roster({ users, query }: { users: User[]; query: string }): React.ReactElement {
  // No useState + useEffect mirror — just derive.
  const visible = users.filter((u) => u.name.includes(query));
  return <ul>{visible.map((u) => <li key={u.id}>{u.name}</li>)}</ul>;
}
```

## What an effect is for

- **Use an effect to synchronize with an external system, and for nothing else.** A subscription, a manually managed DOM node, a non-React widget, an analytics ping tied to appearance — things that live outside React and must be set up and torn down. An effect is not a place to transform data for rendering (derive it), and it is not a place to respond to a user action (that is the event handler that caused the action). The test from the React docs: if the code is not synchronizing with an external system, it probably should not be an effect.
- **Return the cleanup, and make setup plus cleanup a symmetric pair.** Whatever the effect establishes — a subscription, a timer, a listener — the returned function tears down, so a re-run or unmount leaves nothing behind. An effect that subscribes without unsubscribing leaks; the pair is the whole contract.
- **Fetch through a hook that handles race conditions, not a bare effect that `setState`s.** A hand-rolled fetch effect races on fast prop changes — an older response resolving after a newer one and overwriting it. Guard with an ignore flag in cleanup, or use a data-fetching library; either way keep the loading and error states first-class (`ts-errors.md`), never a render that throws or a spinner that never clears.

```tsx
// External synchronization with a symmetric teardown; fetch guarded against races.
useEffect(() => {
  let active = true;
  fetchDeal(dealId).then((deal) => {
    if (active) setDeal(deal);   // stale response from a prior dealId is ignored
  });
  return () => { active = false; };
}, [dealId]);
```

## Keys on lists

- **Give every element in a rendered list a stable key drawn from the data's identity, never the array index.** The key tells React which item is which across renders; a domain identifier (`user.id`, `order.ref`) is stable under insertion, deletion, and reordering. An index key is a lie the moment the list changes — React reuses the wrong element's state, so a checkbox or an input value attaches to the wrong row.
- **Use the index only for a list that is static, never reordered, and has no per-item state** — and prefer a real key even then. If the data has no natural identifier, mint one when the item is created and carry it, rather than reaching for the index at render time.

```tsx
{orders.map((order) => <OrderRow key={order.ref} order={order} />)}
// not key={index} — an index key corrupts row state on reorder or deletion.
```

## Controlled versus uncontrolled inputs

- **Default to a controlled input: React state is the value, and `onChange` writes it back.** One source of truth for the field, the same principle again — the state drives the input and nothing else does. This is the default because it is the only form that composes with validation, derived enablement, and the pure-view discipline.
- **Pick uncontrolled — a `defaultValue` plus a `ref` read on submit — only for a genuinely fire-and-forget field** where React never needs the value mid-edit. Do not mix the two on one input: an input with both `value` and `defaultValue`, or `value` without `onChange`, is a bug the console will warn about and the field will behave erratically.

```tsx
// Controlled: state is the single source of truth for the field.
const [name, setName] = useState("");
return <input value={name} onChange={(e) => setName(e.target.value)} />;
```

## Memoization and the React Compiler

- **Do not reach for `useMemo`, `useCallback`, or `React.memo` preemptively — add one only against a measured render cost.** Each wrapper adds a dependency array to keep correct and reading cost to every future maintainer, for a speed-up that is usually imperceptible. The bar is a profiled slow render or a referentially-unstable value breaking a memoized child's bailout — not a hunch.
- **Write the code the compiler can optimize, and let it.** The React Compiler auto-memoizes components and hooks that follow the Rules of Hooks, which is the direction the ecosystem is moving — so the manual `useMemo`/`useCallback` sprinkling becomes redundant, and the payoff for obeying the hook rules and keeping render pure goes up. The house default is to keep render pure and lean, add memoization only where a profile demands it, and let the compiler handle the rest rather than hand-caching everything now.

## Composition over prop-drilling

- **Prefer composition — pass a rendered element as a prop or as `children` — before threading a value through intermediate components that do not use it.** A value passed down three layers only to reach the fourth is `craft-complexity.md`'s pass-through variable in JSX; often the fix is to render the leaf where the data already lives and pass it in as `children`, so the middle layers never see it.
- **Reserve Context for genuinely cross-cutting values — theme, the current user, a locale — and reach for it sparingly.** Context solves prop-drilling but couples every consumer to the provider and re-renders the subtree on change, so it is the wrong tool for state that only two nearby components share (lift that to their common parent) and the wrong tool for frequently-changing values (it makes the whole subtree a dependency). One provider per truly global concern, not a context per feature.
- **Keep component composition shallow and deep in the `craft-complexity.md` sense — a simple prop interface over a capable body.** A component with fifteen boolean props is a shallow module; split it by the discriminated-union shapes it actually renders, or compose it from smaller pieces the caller assembles.

## Accessibility

- **Use the semantic element for the job before adding a role.** A `<button>` for an action, an `<a href>` for navigation, `<nav>`/`<main>`/`<header>` for landmarks, a real `<label>` bound to its control. A `<div onClick>` is not a button — it is unreachable by keyboard and invisible to a screen reader — and `jsx-a11y` will flag it. Native semantics carry focus, keyboard behavior, and role for free; reaching for `role="button"` on a `div` means re-implementing all of that by hand and usually getting it wrong.
- **Give every form control an associated label and every meaningful image alt text.** `label-has-associated-control` wants a `<label htmlFor>` or a wrapped control; `alt-text` wants an `alt` on `<img>` (empty `alt=""` for a purely decorative one, which is a deliberate signal, not a missing attribute). A placeholder is not a label.
- **Keep interactive elements reachable and operable by keyboard.** If a non-standard element must be interactive, it needs a `role`, a `tabIndex={0}`, and key handlers — which is the argument for using the native element instead. Do not remove focus outlines without replacing them with a visible focus style.

```tsx
// Semantic element + bound label — reachable, announced, no role needed.
<label htmlFor="amount">Loan amount</label>
<input id="amount" name="amount" value={amount} onChange={onAmount} />
<button type="submit">Submit</button>
```

## Vite: dev server, environment, and build

- **Set `server.host` to `true` when the dev server must be reachable off the loopback** — a remote or headless machine, another device on the network. The default binds to localhost only; `host: true` (equivalently `'0.0.0.0'`) listens on all addresses. Scope that to the environments that need it rather than committing it as the unconditional default.
- **Treat every `VITE_`-prefixed variable as public — it is inlined into the client bundle at build time.** Only variables beginning with `VITE_` are exposed to client code through `import.meta.env`, and the exposure is the point: the value ships in the shipped JavaScript for anyone to read. Never put an API key, a token, or any secret in one; a secret belongs behind a server call. (`ts-security.md` owns the secret-handling boundary.)
- **Read build-time facts from `import.meta.env`, not `process.env`.** `import.meta.env.MODE`, `.PROD`, and `.DEV` are statically replaced at build time, so a `if (import.meta.env.DEV)` block tree-shakes out of the production bundle entirely. Access custom values as `import.meta.env.VITE_API_URL`, typed by augmenting `ImportMetaEnv` so `tsc` checks them.
- **Trust HMR in development and do not design around it, but verify behavior against the production build before shipping.** Hot module replacement preserves state across edits and is a development-only convenience; the optimized `vite build` output (minified, tree-shaken, code-split) is what runs in production, and a `vite preview` pass catches the class of bug that only appears once dev-only code is stripped and modules are bundled for real.

```tsx
// Typed access to a public build-time variable; DEV-only code tree-shakes away.
const apiUrl: string = import.meta.env.VITE_API_URL;
if (import.meta.env.DEV) {
  console.debug("dev build against", apiUrl);
}
```

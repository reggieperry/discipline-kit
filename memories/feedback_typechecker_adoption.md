---
name: feedback-typechecker-adoption
description: "Concrete playbook for adopting mypy on a Python service. Four rules from Robust Python (Viafore) — strict flags from day one, ABC-not-concrete on parameter types, UserDict over dict subclassing, MonkeyType `Union[X,Y]` as a smell. Pairs with the runtime defenses in [[feedback-pr-review-patterns]] to add a write-time defense layer."
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

A Python service may already run ruff plus a static linter and review subagents but no static typechecker. Adding mypy is a defense-in-depth move: most write-time errors that reviewers surface would have been caught by a strict typechecker before any reviewer saw them. The rules below are the adoption playbook, sourced from *Robust Python* (Viafore) Chs 5-7.

**Why:** runtime defenses (Pydantic `max_length`, input validation, error sanitization) run at request time. A typechecker runs at write time and catches a different bug class — wrong-shape calls, unparametrized generics that bleed `Any`, stale `# type: ignore` from a fix that landed and got reverted, accidental shadowing.

**How to apply:** when adding mypy to the workspace (a separate decision; not retroactive), use the rules below as the initial config + idioms. Adopt incrementally — per-module strictness rollout is fine.

---

## 1. Ship strict flags on day one

**Rule.** When mypy enters the workspace, the initial `mypy.ini` (or `pyproject.toml` `[tool.mypy]`) carries `strict_optional = True`, `no_implicit_optional = True`, `warn_unused_ignores = True`, and `disallow_any_generics = True`. Allow per-module relaxation for `tests/` and integration/adapter modules.

**Why.** Ch 6 "Configuring Mypy" — default mypy is too lenient to be useful. These four flags catch the bug classes that hurt most: None mishandling (the silent `if x:` that misses `0` and `""`), `Any`-bleed through unparametrized generics, stale ignores that survived a fix being reverted.

**Trigger.** First-time mypy adoption. Not retroactive on the current codebase, but every new file enforced.

**How to apply.** Ship the config in the repo, not in a Makefile flag (it has to survive a fresh checkout). Run `dmypy run` for fast feedback. Add a CI gate that fails the build on a mypy error in application code. Allow `tests/` to be opt-in strict (test code legitimately needs `MagicMock` shapes that defy annotation). Mirrors the [[feedback-pr-review-patterns]] Pattern 3 frame: config that operators may want to tune lives in checked-in config, not in a flag.

---

## 2. Annotate iterable parameters as `collections.abc.Iterable`, not concrete `list`

**Rule.** Default parameter types to the loosest ABC that supports the operations used inside. `Iterable[X]` for `for x in xs`; `Sequence[X]` for `xs[0]` or `len(xs)`; `Mapping[K,V]` for `m[k]` or `m.get(k)`. Return types stay concrete.

**Why.** Ch 5 — `def f(xs: list[X])` rejects tuples, generators, sets, and SQLAlchemy 2.0's `ScalarResult`. The function rarely needs `list`; it needs iteration. `Iterable` documents the contract honestly and accepts the SQLAlchemy result type without a `list(...)` materialization.

**Trigger.** Every helper that loops over a query result, a batch, or a stage handler's input. Signatures often say `list[X]` even when only iteration is needed. SQLAlchemy 2.0's `select(...).all()` returns a list, but `.scalars()` returns a `ScalarResult` — passing the latter into a `list[X]` annotation requires a redundant materialization.

**How to apply.** Default to `Iterable[X]` for "just iterate"; `Sequence[X]` for indexing/length; concrete `list[X]` only for "I will mutate this list inside the function and return it." Returns stay concrete because callers benefit from knowing the shape. Pairs with rule 6 in [[reference-type-system-for-invariants]] (bounded TypeVars).

---

## 3. Subclass `collections.UserDict` / `UserList`, not built-in `dict` / `list`

**Rule.** When defining a dict-like or list-like with overridden behavior, subclass `collections.UserDict` (or `collections.UserList`, `collections.UserString`) instead of `dict` / `list` / `str`.

**Why.** Ch 5 "Modifying Existing Types" — overriding `__getitem__` on a built-in `dict` subclass does **not** fire from `.get()`, `.update()`, or comprehensions, because CPython inlines those paths for speed. Override on `UserDict` and the subclass's hook actually runs everywhere. The book frames this as a Law-of-Least-Surprise violation; in practice, it's a silent-failure landmine.

**Trigger.** Rare in most codebases, but it surfaces for an alias-aware vocabulary dict, a case-insensitive header dict, a sanitizing string wrapper, or anything where "subclass dict and override `__getitem__`" looks like the natural shape.

**How to apply.**
```python
from collections import UserDict

class AliasAwareDict(UserDict):
    def __getitem__(self, key):
        return self.data[self._canonicalize(key)]
```
Performance caveat goes in the docstring: `UserDict` has one level of indirection through `self.data`. Don't use for hot-loop code where the dict is read thousands of times per second.

---

## 4. Treat MonkeyType-generated `Union[X, Y]` as a code smell, not an annotation

**Rule.** When using MonkeyType or pytype to retrofit annotations on legacy code, audit every generated `Union[X, Y]` before accepting it. A Union in a generated stub usually means the function received different types in different runtime paths — a likely latent bug, not a deliberate polymorphism.

**Why.** Ch 7 "MonkeyType" — Viafore explicitly calls this a smell. Generated Unions encode "the runtime tracer saw both shapes," which is almost always an unintentional consequence of a refactor that left two call sites passing incompatible arguments. The fix is to refactor one of the call sites, not to accept the Union.

**Trigger.** Retrofitting annotations on legacy modules, POC code, or any module that was untyped when it was written. Also any time you accept a generated stub from a tool.

**How to apply.** Before accepting a generated stub, grep the call sites of every `Union[X, Y]` function. Either replace with a single type (refactor callers to converge) or document why both shapes are intentional with a docstring named-invariant ([[feedback-pr-review-patterns]] Pattern 6 style). Don't accept the Union by default.

---

## Adoption sequence (not a rule, but the order to follow)

1. Add `mypy.ini` with the four strict flags above, restricted to application code. Tests opt-in.
2. Run `dmypy run` and absorb the existing errors. Fix the trivial cases; add narrow `# type: ignore[reason]` for the genuinely-hard cases with a comment naming the follow-up.
3. Add the CI gate. Failing the build on a mypy error in application code enforces the floor.
4. Add the [[reference-type-system-for-invariants]] tools (Literal, NewType, Final, TypedDict, Optional discipline, bounded TypeVar) one PR at a time as new code lands.
5. Revisit the `# type: ignore` list quarterly; `warn_unused_ignores` will surface any that became unnecessary after refactor.

---

## Related memory

- [[reference-type-system-for-invariants]] — the type-tool half (companion memory)
- [[reference-local-quality-stack]] — existing quality stack mypy joins
- [[reference-python-pr-gotchas]] — Pydantic v2 + SQLAlchemy 2.0 idiom errors mypy would catch
- [[feedback-pr-review-patterns]] — Pattern 3 (config-over-constants) applies to mypy config too

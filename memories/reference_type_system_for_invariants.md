---
name: reference-type-system-for-invariants
description: "Python type-system tools as a structural complement to runtime validation. Six rules from Robust Python (Viafore) on encoding invariants in types — Literal, NewType, Final, TypedDict, Optional with present-vs-absent discipline, bounded TypeVar. Pairs with Pydantic v2 runtime defense to give defense-in-depth at zero runtime cost."
metadata: 
  node_type: memory
  type: reference
  volatility: durable
---

The Python type system encodes invariants the typechecker enforces at write time, complementing the runtime validation we already get from Pydantic v2 and the boundary checks from [[feedback-pr-review-patterns]] Pattern 1. The rules below come from *Robust Python* (Viafore, ER2 2022), Chs 1-7 (type system). Each pairs with one of our existing boundaries.

**Why this exists:** runtime defenses are well covered (Pydantic field constraints, max_length on LLM strings, id validation). What is easy to leave unnamed is the set of type-time defenses that ride alongside them. Adding both layers is "defense in depth at zero runtime cost" — the typechecker rejects a wrong call before the runtime ever sees it.

**How to apply:** when designing a new function or schema, pick the loosest of these tools that captures the invariant you care about. Don't retrofit; new code only unless a specific bug shows up.

---

## 1. `Literal` for fixed small value sets

**Rule.** Use `Literal["high", "medium", "low"]` (or similar) for any field whose value comes from a closed enumerable set, instead of `str` with `Field(pattern=...)`.

**Why.** Ch 4 "Literal Types" — the typechecker rejects typos at write time; Pydantic v2 enforces the same set at validate time. A `str + pattern` regex catches only the runtime cases; `Literal` catches the call-site cases too.

**Trigger.** Pydantic schema fields with closed sets — `confidence: Literal["high","medium","low","not_found"]`, `source: Literal["agent","analyst"]`, `match_type: Literal["explicit","inferred","not_found"]`, currencies, ISO codes, status enums where the set is small and stable. A `Literal` defined once and reused is right; the pattern is often correct in one spot but not propagated.

**How to apply.** Replace `Field(..., pattern=r"^(...)$")` with `Literal[...]`. Define the literal once at module level (`StatusFlag = Literal["multi_root", "circular_reference", ...]`) and import it at every use site. When the closed set is large or unstable, use an `Enum` instead.

---

## 2. `NewType` for "blessed-function-only" subtypes

**Rule.** When a value must pass a checkpoint before it's safe to use downstream, define a `NewType` and make the validator the only function that produces it.

**Why.** Ch 4 "NewType" — the conversion is one-way at type-check time, so any function taking the subtype proves at the type level that the checkpoint ran upstream. Zero runtime cost.

**Trigger.** Exactly the [[feedback-pr-review-patterns]] Pattern 1 surfaces — LLM-returned ids that need to be looked up in a table before being persisted into a referencing table; entity UUIDs from extraction that need confirmation; user-submitted IDs from a UI before they hit the DB.

**How to apply.**
```python
from typing import NewType
from uuid import UUID

ValidatedChunkID = NewType("ValidatedChunkID", UUID)

def resolve_chunk_id(session, raw_id: UUID) -> ValidatedChunkID | None:
    """The only function in the codebase that produces a ValidatedChunkID."""
    row = session.execute(text("SELECT id FROM document_chunks WHERE id = :id"), {"id": raw_id}).first()
    return ValidatedChunkID(raw_id) if row else None

def persist_ownership_chain(..., chunk_id: ValidatedChunkID) -> None:
    """Caller must have passed `raw_id` through resolve_chunk_id."""
```
Persistence functions take the subtype, never the raw type. The typechecker now refuses dangling-FK writes structurally instead of relying on convention.

---

## 3. `Final` for module-level invariants

**Rule.** Annotate module-level constants that other modules rely on as `Final`. The constraint matters more when the value sets a contract (an invariant, an external URL, a model name).

**Why.** Ch 4 "Final Types" — `Final` doesn't make the object immutable, it stops rebinding. An accidental `+=` or reassignment from another module fails typechecking instead of silently corrupting the contract.

**Trigger.** Ordered invariant chains like the one documented in [[feedback-pr-review-patterns]] Pattern 3 — `RECLAIM_THRESHOLD_SECONDS > REQUEST_TIMEOUT_SECONDS > HEARTBEAT_INTERVAL_SECONDS`. Default model names, vendor URLs, schema version strings, MAX_RETRY_ATTEMPTS — anything where a future contributor rebinding the constant in their own module would silently break a contract.

**How to apply.**
```python
from typing import Final

HEARTBEAT_INTERVAL_SECONDS: Final = 30
RECLAIM_THRESHOLD_SECONDS: Final = 240
```
In settings classes, prefer `Final` on the class attributes that drive invariants. Combine with a settings invariant comment naming the relationship.

---

## 4. `TypedDict` for heterogeneous boundary dicts

**Rule.** For any dict crossing a boundary (LLM JSON output, vendor API response, YAML/TOML config), define a `TypedDict` mirror of the schema. Don't use `dict[str, Any]` and let the call sites guess.

**Why.** Ch 5 "TypedDict" — encodes the keys and their value types so the typechecker shows callers exactly what's available. No runtime cost (it's still a plain dict at runtime). Pairs with the Pydantic-at-boundary pattern: TypedDict at parse time (zero cost), Pydantic at validate time (adds `max_length`, `max_items` defense).

**Trigger.** Anywhere we parse a structured JSON-schema model output before converting to a Pydantic model; any vendor API response we shape into our own model; a tool-use response. Going straight to Pydantic works; adding TypedDict as the intermediate parse type makes the schema contract a typed surface.

**How to apply.**
```python
from typing import TypedDict, NotRequired

class FieldExtractionRaw(TypedDict):
    value: str | None
    confidence: Literal["high", "medium", "low", "not_found"]
    candidates: NotRequired[list[dict]]

def parse_extraction_response(raw: str) -> FieldExtractionRaw:
    return json.loads(raw)  # TypedDict at parse boundary

def to_pydantic(t: FieldExtractionRaw) -> FieldExtractionResult:
    return FieldExtractionResult.model_validate(t)  # runtime defense
```
Use `NotRequired[X]` for optional keys; `Required[X]` is the default in 3.11+.

---

## 5. `Optional[X]` means present-or-absent; don't conflate `[]` with error

**Rule.** Return `Optional[list[X]]` when the absence is a distinct state from the empty result. `None` = errored / degraded / not-applicable; `[]` = ran successfully, produced nothing.

**Why.** Ch 4 "Optional Type" — collapsing two states into one (empty list) makes the caller guess. Optional makes the distinction load-bearing in the type signature; the typechecker forces an explicit None check at the call site, and the codebase reads more honestly.

**Trigger.** Handlers that today return `list[Entity]` and use `[]` for both "the model returned zero entities" and "the retrieval connection dropped"; a vector retriever that returns `[]` on low-similarity miss vs on connection drop. These are different stories for a downstream consumer.

**How to apply.** In any function that can either succeed-with-empty or fail-degraded, the signature is `Optional[list[X]]`. `None` carries the "stage errored, see logs / status field" semantics; `[]` carries "the model said zero, this is a legitimate outcome." Pairs with [[feedback-claims-need-tests]] — a test for each branch flowing to the right surface (None → "stage errored," `[]` → "stage produced zero entities").

---

## 6. Bound every TypeVar

**Rule.** When introducing a `TypeVar` in a pipeline, generic helper, or callback, bind it (`T = TypeVar("T", bound=BaseModel)`). Unbounded TypeVars collapse to `Any` under `--disallow-any-generics`.

**Why.** Ch 5 "Generics" + Ch 6 "Catching Dynamic Behavior" — the value of generic typing is the typechecker propagating constraints through a pipeline. An unbounded `T` accepts anything, so a typo at one end typechecks because Any is Any-compatible. Binding to `BaseModel`, a `Protocol`, or a concrete base re-engages the typechecker.

**Trigger.** Graph/pipeline state types where one node returns `T` and the next consumes it; retry-wrapper generics around chat-client calls; a generic row shape threaded through a persistence helper. Anywhere the same generic flows through more than one named function.

**How to apply.**
```python
from typing import TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

async def with_retries(call: Callable[..., Awaitable[T]], ...) -> T:
    ...
```
Pair with `--disallow-any-generics` in mypy config so missing parametrization is an error, not a silent escape hatch. See [[feedback-typechecker-adoption]] for the broader mypy config.

---

## Related memory

- [[feedback-pr-review-patterns]] — runtime defenses these type-time rules complement
- [[feedback-security-when-writing-code]] — Pydantic boundary discipline; the `max_length` / `max_items` runtime layer
- [[reference-python-pr-gotchas]] — Pydantic v2 + SQLAlchemy 2.0 idiom errors caught after the fact
- [[feedback-typechecker-adoption]] — companion memory on adopting mypy strictness flags
- [[feedback-claims-need-tests]] — required for rule 5 (Optional present-vs-absent has to be tested)

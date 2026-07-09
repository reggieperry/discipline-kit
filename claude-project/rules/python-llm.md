---
paths:
  - "**/*llm*.py"
  - "**/*agent*.py"
  - "**/agents/**/*.py"
  - "**/llm.py"
---

# Python LLM boundary (structured output)

The typed contract between Python code and the model — where reliability is bought. Sources: Pydantic v2 (fields, strict mode) and your model SDK's structured-outputs docs. The model is reached through its official Python SDK; the model id is configured per call.

> See `python-types.md` for the typed contract, `python-concurrency.md` for the timeout on every model call, `python-errors.md` for surfacing validation failures, and `craft-abstraction.md` for the schema as a specification.

> **Verify SDK specifics against the version pinned in `pyproject.toml`.** The SDK evolves; treat the API names below as a guide and confirm them against the pinned source before relying on them — don't compose SDK calls from memory. The method and field names below (`messages.parse()`, `output_format`, `parsed_output`, `stop_reason`) follow one SDK's structured-output API; the shape generalizes, but the exact names differ across providers.

## The model is the contract

- **Define one Pydantic v2 `BaseModel` as the single typed contract per LLM call, and pass it as the SDK's structured-output format argument (e.g. `output_format=` to a parse-style call)** — the SDK derives the JSON schema, requests constrained output, and returns a typed parsed result.
- **Constrain string fields with `Field(min_length=..., max_length=..., pattern=...)` and numerics with `gt`/`ge`/`lt`/`le`/`multiple_of`** (v2 names). Express reusable constrained types as `Annotated[str, Field(max_length=N)]`.
- **Turn on strict validation at the boundary with `model_config = ConfigDict(strict=True)`** (or `Field(strict=True)`) to block silent lax coercion like `"123" → 123`.

## Validate at the boundary, retry bounded

- **Read the parsed result and treat `None` as a hard failure** (the SDK returns `None` when the wire JSON can't instantiate your model), falling back to the raw text for diagnostics. Bound every collection field and cap `max_tokens` generously — the wire schema *drops* `minimum`/`maximum`/length constraints into field descriptions, so your real defense against unbounded or out-of-range output is the **post-parse Pydantic validation plus the token cap**, not the model honoring the wire schema.
- **Run a bounded validate-and-retry loop on `ValidationError` / a `None` parsed result** (e.g. ≤2 retries) — feed the field-level `ValidationError` detail back to the model (causal-first, un-summarized), and stop at the bound rather than burning tokens on an open loop.
- **Handle the non-schema terminal states explicitly:** a refusal stop reason (a 200 that won't match the schema) and a truncation stop reason such as `max_tokens` (retry with a higher `max_tokens`). Both return success-shaped responses that fail validation.

## Calling the model

- **Put an `asyncio.timeout` on every model call** and set the SDK request timeout and max-retries explicitly rather than relying on defaults (`python-concurrency.md`).
- **For the tool-use structured path, set `strict: true` on the tool definition with `additionalProperties: false` and explicit `required`.** Respect the schema limits (a bounded number of strict tools and params per request, no recursive schemas, a compile timeout) — exceeding them fails the request.
- **One call, one typed result — no open-ended agent loop in a focused, single-purpose call.** The leverage over a general open-ended agent is exactly this bounded, structured, validated call; keep the prompt and rubric fed whole, and keep the Pydantic model as the narrow typed boundary.

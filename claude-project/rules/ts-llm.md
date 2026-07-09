---
paths:
  - "**/*llm*.ts"
  - "**/*agent*.ts"
  - "**/*schema*.ts"
---

# TypeScript LLM boundary (structured output)

The typed contract between a Node/TypeScript service and the model — the single place a model call's reliability is bought, and the boundary where an otherwise-untrusted output becomes a value the rest of the program may hold. This is the server-side boundary: a key is read from the environment on a server or agent process, never shipped to a browser (`ts-security.md`). Sources: the Anthropic TypeScript SDK (`@anthropic-ai/sdk`) and its `helpers/zod` structured-output surface; the OpenAI Node SDK (`openai`) and `openai/helpers/zod`; the Messages API and OpenAI structured-output / tool-use documentation; zod (v3 and v4, the schema and validator); and the OWASP LLM Top 10 (LLM01 prompt injection, LLM02 insecure output handling). The model id is configured per call site and pinned to a dated snapshot; a cheaper tier is the sensible default for high-volume extraction, since it both costs less and tends to surface a larger error signal for the schema and re-validation to catch.

> See `ts-types.md` for the parsed output as a typed contract (the `z.infer` type the domain code consumes) and branded value types, `ts-errors.md` for surfacing a validation or transport failure as a typed result rather than a thrown exception, `ts-security.md` for keeping the key out of the client bundle and treating model output as untrusted, `ts-react.md` for never rendering that output through `dangerouslySetInnerHTML`, `ts-testing.md` for fuzzing the parse boundary, and `craft-abstraction.md` for the schema as a specification the call is written against and `craft-domain-modeling.md` for the model's output schema as a real context seam with an explicit translation type.

> **Verify SDK specifics against the version pinned in `package.json`.** Both SDKs move quickly and the helper surface is newer than the core client. Treat the method and helper names below — `client.messages.parse`, `zodOutputFormat`, `output_config`, `parsed_output`, `client.chat.completions.parse`, `zodResponseFormat`, `message.parsed`, `message.refusal` — as a guide keyed to a recent release, and confirm each against the pinned package's `helpers.md` and type definitions before relying on it. Do not compose SDK calls from memory.

## The zod schema is the contract, and it is language-independent

- **Define one zod schema as the single source of truth for each model output, and derive both the wire schema and the parsed result from it.** The guardrail lives at the JSON schema the model is constrained to, which is independent of TypeScript — a wire-level typed contract is the point, not the host language it is expressed in. The SDK's zod helper turns one schema into both the request's `response_format` / `output_config` and the parse of the reply, so the request contract and the result type cannot drift. **House default:** one zod object schema per call, fed through the SDK helper; never hand-maintain a parallel JSON schema alongside it — a second hand-written artifact is exactly the drift the single source of truth exists to prevent.
- **Describe every field.** A field's `.describe(...)` is the model's instruction for that field; an undescribed field invites garbage. Keep the schema flat — object of scalars and short arrays — and closed sets as `z.enum([...])`, since a nested or recursive schema is where the structured-output backends most often reject or silently degrade.
- **Infer the domain type from the schema, and treat the schema as a boundary adapter.** The `z.infer` type is the contract the domain code consumes; convert it to intention-revealing domain types (branded ids, `Money`, an `Order` value object — `ts-types.md`) at the boundary so the raw wire shape never spreads inward.

```typescript
import { z } from 'zod';

// The zod schema IS the contract and the single source of truth.
// The request format and the parsed result both derive from it, so they cannot drift.
export const ReviewVerdict = z.object({
  decision: z.enum(['pass', 'block']).describe('Review outcome'),
  reasons: z.array(z.string().min(1)).min(1).max(10).describe('One reason per finding'),
  severity: z.number().int().min(0).max(5).describe('0 = clean, 5 = severe'),
});

export type ReviewVerdict = z.infer<typeof ReviewVerdict>;
```

## Structured output over tool-use for a single typed result

- **Use the structured-output / parse path for a pure typed result, and reserve tool-use for genuine action selection.** Anthropic's `client.messages.parse` with `output_config: { format: zodOutputFormat(Schema) }` returns a validated `parsed_output`; OpenAI's `client.chat.completions.parse` with `response_format: zodResponseFormat(Schema, name)` returns `message.parsed` (the newer Responses API exposes the equivalent `client.responses.parse` with `zodTextFormat` — confirm against the pinned version). Tool-use (an `input_schema` the model fills, forced with `tool_choice`) is the older way to coerce a shape and the right tool only when the model must *choose among actions* or run an agent loop — Anthropic's `betaZodTool` + `client.beta.messages.toolRunner` is that path. **House default:** the parse helper for extraction; tool-use only for action selection, because the parse path both derives the wire schema and re-runs zod for you, whereas a hand-built tool `input_schema` returns an unchecked `input` you must validate yourself.
- **One bounded call, one typed result — no open-ended agent loop, no unbounded tool surface in a focused call site.** The leverage of a structured call over an open-ended agent is exactly this narrowing. Keep the system prompt and rubric fed whole (do not pre-digest them) and keep the schema as the thin typed boundary.

## Bound everything, then re-validate at the boundary

- **The schema constrains generation; it does not constrain a misbehaving model.** The structured-output backends carry a *subset* of JSON Schema onto the wire: closed sets (`enum`), required vs optional, and `additionalProperties: false` hold, but numeric `.min()`/`.max()`, array `.min()`/`.max()`, string length bounds, and cross-field `.refine(...)` rules are generally dropped and are not enforced by the model. So an unbounded `z.array(...)` can come back arbitrarily large, and an out-of-range number can come back out of range.
- **Re-run the zod schema over the parsed output before the domain trusts it, and return a typed result rather than throwing.** The parse helpers already validate against the schema and hand you a typed value — but re-validating with `safeParse` at the seam into domain code is the enforcement for every constraint the wire schema dropped, and it is mandatory on the tool-use path, where the SDK returns an unchecked `input`. **House default:** `safeParse` at the boundary, mapped to a typed result (`ts-errors.md`); never let a `ZodError` throw across the seam, and never trust a raw `input` from a tool call without a `safeParse`.

```typescript
import { z } from 'zod';

export type CallError =
  | { readonly kind: 'transport'; readonly message: string }
  | { readonly kind: 'refusal'; readonly message: string }
  | { readonly kind: 'invalid'; readonly issues: readonly z.ZodIssue[] };

export type CallResult<T> =
  | { readonly ok: true; readonly value: T; readonly modelId: string }
  | { readonly ok: false; readonly error: CallError };

// Total: a malformed model output becomes a typed error, not an exception.
export function validate<T>(schema: z.ZodType<T>, raw: unknown, modelId: string): CallResult<T> {
  const parsed = schema.safeParse(raw);
  return parsed.success
    ? { ok: true, value: parsed.data, modelId }
    : { ok: false, error: { kind: 'invalid', issues: parsed.error.issues } };
}
```

## Calling the model — one facade over each SDK

- **Wrap the call in one `LlmCall` interface and keep each SDK behind an adapter.** The provider is chosen by configuration; every call site depends on the interface, never on `@anthropic-ai/sdk` or `openai` directly. This is the context seam of `craft-domain-modeling.md` — the model's output is a foreign model, translated at exactly one boundary. **House default:** the SDK is imported only inside its adapter module; a direct `client.messages.create` anywhere else is a boundary leak.
- **Construct the client once and share it.** `new Anthropic({ apiKey: process.env['ANTHROPIC_API_KEY'] })` and `new OpenAI({ apiKey: process.env['OPENAI_API_KEY'] })` each own connection pooling — build one at the edge, not per call.
- **Put an explicit timeout on every call and keep retries bounded.** Both clients default to a 10-minute request timeout and 2 automatic retries; the 10-minute default has no place in a request path. Set a short per-request `timeout` and an explicit `maxRetries` through the request options rather than relying on the default. **House default:** a per-request `timeout` in the tens of seconds; keep the SDK's bounded retry, never an unbounded manual loop. A bounded validate-and-retry — feed the located `ZodError` issues back and stop at a small cap (≤ 2) — is the only retry that touches the schema.

```typescript
import Anthropic from '@anthropic-ai/sdk';
import { zodOutputFormat } from '@anthropic-ai/sdk/helpers/zod';
import { z } from 'zod';

export interface LlmCall {
  structured<T>(schema: z.ZodType<T>, name: string, system: string, input: string): Promise<CallResult<T>>;
}

const MODEL_ID = 'claude-haiku-4-5-20251001'; // pinned dated snapshot, recorded per record

export function anthropicCall(client: Anthropic): LlmCall {
  return {
    async structured(schema, _name, system, input) {
      try {
        const message = await client.messages.parse(
          {
            model: MODEL_ID,
            max_tokens: 1024,
            system, // trusted, fixed — never spliced with untrusted content
            messages: [{ role: 'user', content: input }], // untrusted data rides here
            output_config: { format: zodOutputFormat(schema) },
          },
          { timeout: 60_000, maxRetries: 2 },
        );
        return validate(schema, message.parsed_output, MODEL_ID); // re-validate at the seam
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return { ok: false, error: { kind: 'transport', message } };
      }
    },
  };
}
```

- **Handle the non-schema terminal states explicitly.** A refusal and a truncation both return success-shaped responses that fail validation. OpenAI surfaces a refusal as `message.refusal` (a non-null string) and truncation as `finish_reason === 'length'`; branch on the refusal before reading `parsed`, and treat a length cutoff as a retry with a higher token cap, not a parse error.

```typescript
import OpenAI from 'openai';
import { zodResponseFormat } from 'openai/helpers/zod';

const OPENAI_MODEL_ID = 'gpt-4o-2024-08-06'; // structured outputs need this snapshot or later

export function openAiCall(client: OpenAI): LlmCall {
  return {
    async structured(schema, name, system, input) {
      const completion = await client.chat.completions.parse(
        {
          model: OPENAI_MODEL_ID,
          messages: [
            { role: 'system', content: system },
            { role: 'user', content: input },
          ],
          response_format: zodResponseFormat(schema, name),
        },
        { timeout: 60_000, maxRetries: 2 },
      );
      const message = completion.choices[0]?.message;
      if (message?.refusal != null) {
        return { ok: false, error: { kind: 'refusal', message: message.refusal } };
      }
      return validate(schema, message?.parsed, OPENAI_MODEL_ID);
    },
  };
}
```

## Determinism and reproducibility — record the model id

- **Pin the dated model snapshot and every sampling lever, and write them into the record.** A silently floating model id, token budget, or temperature makes two runs incomparable. Set the model to a dated snapshot (`claude-haiku-4-5-20251001`, `gpt-4o-2024-08-06`), hold `max_tokens` and `temperature` fixed, pass OpenAI's `seed` where it applies (best-effort, paired with `system_fingerprint`), and store the resolved values alongside each output so a result is reproducible from its own row. **House default:** the model id is a pinned constant per adapter, recorded on every `CallResult`, never read from an unpinned alias. The API does not promise bit-identical output even at fixed settings — determinism here means *fixed, recorded inputs and a mechanical check*, not a deterministic model.
- **Never put an LLM judge on a mechanical or headline decision.** If a decision must be deterministic, it is computed over the structured record, not delegated to a model — a generator is not a trustworthy judge of its own class of output. An `LlmCall` belongs in an extraction node, never in the grader.

## Treat model output as untrusted input

- **Model output is untrusted input; validate at the schema, then never let it reach a sink unescaped.** After `safeParse` a value is well-typed, not trustworthy. Never interpolate it into a shell command, a SQL string, a file path, `eval`/`new Function`, or a template — this is OWASP LLM02, insecure output handling (`ts-security.md`). Build SQL with parameterized queries, shell commands with an argument array (`execFile`, never a shell string), and file paths confined under a resolved base directory.
- **Never render model output as raw HTML.** In React, JSX auto-escapes text nodes, so rendering a validated string as a child is safe; `dangerouslySetInnerHTML` with model output is a stored-XSS sink and is banned (`ts-react.md`). Bound the decode too — cap the token budget and reject an oversized field — so a runaway output cannot exhaust the process.

## Auth and prompt safety

- **API key from the environment, on the server only — never in source and never in the client bundle.** Read `process.env['ANTHROPIC_API_KEY']` / `process.env['OPENAI_API_KEY']` at construction; do not hardcode a key, commit one to a fixture, or bake one into a config. A key handed to a bundler is shipped to every browser: a Vite `import.meta.env.VITE_*` value is inlined into the client build, so an SDK key must never carry that prefix. Both SDKs disable browser use by default (`dangerouslyAllowBrowser`) for exactly this reason — keep the call server-side and proxy the browser through your own endpoint (`ts-security.md`).
- **Never interpolate untrusted content into the system prompt.** The document text, an upstream node's output, and any user-supplied string are untrusted data — they belong in a user-role message, never spliced into the system prompt or the rubric. The system prompt and rubric are fixed, trusted, and fed verbatim; mixing data into them opens the prompt-injection seam (OWASP LLM01) and, where the SDK caches a stable system prefix, poisons that cache. Keep the trusted instruction and the untrusted data in separate message roles, as the facade above does.

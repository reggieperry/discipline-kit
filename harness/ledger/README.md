# The dev-ledger and gate harness

A repo-visible record of **claims about this repo's own development**, and a mechanical gate at commit that discharges them. The evidence half of a trust kernel: a model reporting "done" creates an *unverified* claim; only a mechanical check turns it into a *signed* one. Installed by the kit's `install-harness.sh`.

If this repo keeps another ledger for its own domain, this one is **distinct** — same idea (graded claims), disjoint subject (development, not the domain), separate store. Do not fold one into the other.

## Layout

- `ledger/claims.jsonl` — append-only, one JSON object per line. The live board.
- `ledger/trace/` — retired entries (one `<id>.jsonl` per retirement). Off the live board, still on the record.
- `ledger/audit.py` — the mechanical checks over the ledger (supplied verbatim; do not edit).
- `ledger/append` — the ONE schema-validating writer. Assigns id + timestamp. `echo '{...}' | ledger/append`.
- `ledger/retire <id> <reason> <refuting-id>` — the ONE sanctioned removal: move a claim to `trace/`.
- `ledger/librarian` — reports contested claims and retires superseded ones.
- `ledger/board.sh` — read-only views over the board: `open` (unverified claims), `graveyard` (refuted/contested, with pointers), `checks` (verifier histogram), `stale [days]`, `find <keyword>` (any status, live + trace), `next-id`, plus `--selftest` against `ledger/fixtures/board-fixture.jsonl`. The board reads; humans and the gate write, so it has no write subcommands.
- `ledger/gate.py` — the commit-path gate (forgery guard, check-discharge, audit), called by the git hooks. Byte-identical across repos; per-repo behavior comes from `ledger/languages` + `ledger/check.sh`, never from editing the gate.
- `ledger/check.sh` (optional) — the repo's mechanical check. If absent, the gate auto-detects a single toolchain (`sbt check` / `uv run pytest`); if neither, it runs the forgery guard + audit only.
- `ledger/languages` (optional) — the extensions of the languages that build the system, one per line (`#` comments). A staged file in one of them fires the check. If absent, the gate unions the toolchains it auto-detects from the build markers at the repo root.

## The ledger-* skills

`install-harness.sh` also drops six `ledger-*` skills into `.claude/skills/`, so the next Claude Code instance loads the right ledger procedure at the right moment: **ledger-board** (read before writing), **ledger-write** (the entry discipline), **ledger-preregister** (claim before building), **ledger-discharge** (cite before re-checking, and how signing works), **ledger-retire** (supersession and the librarian, safely), and **ledger-verify** (the auditor's stance). Each carries the exact commands, the guardrails, and the scar that taught the rule. Wiring `sh ledger/board.sh --selftest` into `ledger/check.sh` (see `harness/templates/check.sh.example`) makes the board views part of what `repo-check` proves.

The skills teach the instances; `ledger/operators-manual.md` (installed alongside) teaches the operator — the three board commands, the two trigger phrases, the three rituals, and the five operator-only verbs (authorize, place the bets, sign off, set the ceilings, release the gates).

## Which languages fire the check

The gate must fire for **every language that builds the system**, and `ledger/check.sh` must in turn check **every** one of them — firing for a language you don't check lets that language weaken unseen (a fail-open). A repo built from one language needs neither file: the gate auto-detects the toolchain and its extensions. A repo built from several — or whose build markers are nested or sit beside vendored code in another language — declares them explicitly:

- `ledger/languages` lists the extensions that fire the check (e.g. `.scala .sc .sbt` + `.ts .tsx`).
- `ledger/check.sh` runs the check for all of them (e.g. `sbt check` **and** the frontend's `npm run check`).

Worked example (the claim-algebra-lab): a Scala backend (`build.sbt` at root) plus a TypeScript frontend (`reasoning-society/frontend`, markers nested). Auto-detection would find only Scala and let TS changes through green; `ledger/languages` + a two-part `ledger/check.sh` close that. `LEDGER_CODE_EXTS` overrides the set for tests only.

## Schema and status semantics

One object per line: `id, ts, sha, subject, claim, source, kind, about, check, status, discharged_by, supersedes, trace_reason`.

- `kind` — `assertion` (a claim), `testimony` (review output, never signs), `refutation` (a defect, `about` a claim).
- `status` — `unverified` (asserted, no check ran — the honest "I don't know"); `signed` (a mechanical check discharged it, `discharged_by` mandatory); `refuted` (a check failed it, stays on the record); `retired` (superseded or defeated, moved to `trace/`).
- **Entries are immutable.** A transition is a NEW appended entry whose `supersedes` names its predecessor; the current status of a claim is the head of its supersedes chain. Only `unverified` may be superseded in place (`unverified → signed | refuted | unverified`); a `signed` or `refuted` claim is never rewritten — it is defeated by a refutation and then retired.
- **Only a mechanical check signs.** `discharged_by.check` must be a real check with a run reference — never a generative source (`none`, `pr-review`, `deep-reason`, `workflow-verify`, a model). The audit enforces this; the gate is the sole writer of `signed`.

## The immutability discipline for retirement

The audit holds every line ever **committed** to `claims.jsonl` byte-identical now, in live or trace. Because retirement rewrites the moved entry (adds `trace_reason` + `retired_by`), **retire a claim in the same commit that supersedes or defeats it** — not as a later edit to a long-committed line.

## The demotion rule (generative review testifies, never signs)

Two generative confirmers share their blind spots — correlated confirmation is not verification. So **review output — pr-review, deep-reason, and dynamic-workflow verification passes — is `testimony`; only mechanical checks sign.** The structural enforcement is the schema (nothing reaches `signed` without a mechanical `discharged_by`); the prose rule is one line in the repo's CLAUDE.md. A reviewer that finds a defect appends `refutation`.

## The librarian rule (retired claims leave the live board)

When a refutation defeats a claim (a standing refutation, no surviving support), the defeated entry moves to `ledger/trace/` with `trace_reason` pointing at the refuting id. The live file never carries a claim whose defeat is on the record. `ledger/librarian` does this for superseded claims and reports contested ones. Recovery is allowed — a traced entry can return via a new entry that cites it — but the traced original is immutable.

## Rollback

`git checkout pre-harness-baseline` restores the pre-harness tree (the installer tags it). Removal is: delete `ledger/`, revert the hook wiring (`.githooks/pre-commit` gate block, `.githooks/post-commit`), revert the CLAUDE.md demotion section. Accumulated ledger contents should be archived, not destroyed.

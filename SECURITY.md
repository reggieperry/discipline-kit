# Security policy and threat model

The discipline kit is a **development-discipline aid**, not a security boundary. It makes "done" claims mechanically checkable (the dev-ledger + commit-path gate) and blocks test-weakening versus a merge-base (the differential gate). Stating its trust boundaries plainly is itself part of the discipline — a signing-adjacent tool that does not say what its signature means invites over-trust.

## What a signature means

A `signed` ledger entry means: **a named mechanical check ran and passed** (the gate is the sole writer of `signed`; the pre-commit forgery guard blocks any `signed` line it did not itself mint). It does **not** mean the underlying work is correct — only that the cited check discharged it. Correctness beyond the check rests on whatever the claim names (a second-language recount, an adversarial review, a hand-verified oracle). Read a signature no wider than the check it cites.

## Trust model — single-user mode (what this release ships)

The shipped mode trusts the **local machine and the local git repository**. Within that boundary the gate defends against:

- an automated instance (or a careless commit) **forging a `signed` entry** — the forgery guard rejects any signed line whose hash it did not record;
- **silently weakening the test suite or the ledger** versus the merge-base — the differential gate and the audit's immutability check flag it;
- **editing a committed ledger line** — the append-only immutability check flags any historically-committed line not present verbatim in the live board or the trace.

It does **not** defend against a party who controls the local machine. A local operator can bypass the hooks (`git commit --no-verify`), rewrite history, or edit `ledger/.hook-signed`. In single-user mode that party is *you*; the gate keeps an automated collaborator and your own future carelessness honest, not a hostile local admin.

## Team / multi-writer mode — NOT in this release

The design for multi-writer use relocates signing authority **server-side** (a protected-branch CI job as the sole minting path, provenance-verifiable discharge references, an optional HMAC signing key in CI secrets). **That mode is deferred along with the sharded ledger layout and is not shipped here.** Do not rely on any server-side signing, provenance, or fork-PR guarantee in this release — the shipped kit is single-user by default, with the sharded layout as the concurrency foundation only. When team mode ships, this section will state its guarantees and their boundaries.

## What the kit does NOT defend against (any mode)

- A **hostile repository administrator** — anyone who can rewrite history, disable branch protection, or force-push can defeat the record. The gate raises the cost of dishonesty and makes it auditable; it does not make it impossible against admin rights.
- A **compromised CI runner or a malicious dependency** — the checks are only as trustworthy as the environment that runs them.
- **Secrets in the repo** — the kit ships a gitleaks-style pre-commit backstop as a convention, not a guarantee; treat any committed secret as compromised.

## Reporting a vulnerability

Report a security issue privately via a GitHub security advisory on this repository ("Security" → "Report a vulnerability"), not a public issue. Please include a minimal reproduction and the affected files.

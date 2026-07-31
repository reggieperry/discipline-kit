# Security policy and threat model

The discipline kit is a **development-discipline aid**, not a security boundary. It runs a repo's mechanical check on the commit path and blocks test-weakening versus a merge-base (the differential gate). Stating its trust boundaries plainly is itself part of the discipline — a signing-adjacent tool that does not say what its signature means invites over-trust.

## What a signature means

A green commit means: **the repo's mechanical check ran and passed**. It does NOT mean the underlying work is correct — only that the check found nothing. Correctness beyond the check rests on whatever else was done (a second-language recount, an adversarial review, a hand-verified oracle). Read a green run no wider than the check it ran.

(The dev-ledger and its signature model were removed on 2026-07-30. Its own record showed that every signature it ever minted cited one check — the repo's mechanical check — so the signature carried no information the check did not already return.)

## Trust model — single-user mode (what this release ships)

The shipped mode trusts the **local machine and the local git repository**. Within that boundary the gate defends against:

- an automated instance (or a careless commit) **forging a `signed` entry** — the forgery guard rejects any signed line whose hash it did not record;
- **silently weakening the test suite** versus the merge-base — the differential gate flags it;

It does **not** defend against a party who controls the local machine. A local operator can bypass the hooks (`git commit --no-verify`) or rewrite history. In single-user mode that party is *you*; the commit-path check keeps an automated collaborator and your own future carelessness honest, not a hostile local admin. The cheapest automated bypass is closed by name: `git commit --no-verify` / `-n` sit on the settings deny-list.

## Team / multi-writer mode — NOT in this release

Multi-writer use is not addressed by this kit. There is no server-side authority, no provenance verification, and no fork-PR guarantee. The shipped kit is single-user by default.

## What the kit does NOT defend against (any mode)

- A **hostile repository administrator** — anyone who can rewrite history, disable branch protection, or force-push can defeat the record. The gate raises the cost of dishonesty and makes it auditable; it does not make it impossible against admin rights.
- A **compromised CI runner or a malicious dependency** — the checks are only as trustworthy as the environment that runs them.
- **Secrets in the repo** — the kit ships a gitleaks-style pre-commit backstop as a convention, not a guarantee; treat any committed secret as compromised.

## Reporting a vulnerability

Report a security issue **privately** via a GitHub security advisory on this repository ("Security" → "Report a vulnerability"), **never as a public issue** — a public issue discloses the vulnerability to everyone before it is fixed. Please include a minimal reproduction and the affected files. Enable the platform's private vulnerability reporting on the repository (Settings → Security → Private vulnerability reporting); an adopter that opens to outside contributions should do the same. It is the one inbound channel the issue templates deliberately do not cover, because a bug report is a public refutation and a vulnerability must not be.

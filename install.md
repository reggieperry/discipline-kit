# Installing the harness

The dev-ledger and its commit-path gate install into a **git repository**, not a machine. This is the one-time ceremony; after it, the discipline is ambient (the injected `CLAUDE.md` section and the auto-loaded `ledger-*` skills carry it).

Read `README.md` (what the kit is) and `SECURITY.md` (the trust model) before you install.

## Prerequisites

- A git repository (run `git init` first if the target is not one yet).
- `python3` and `git` on `PATH`. No other runtime is required by the ledger tooling itself.
- Optional, for the differential gate's language scanners: the repo's own toolchain (`uv` for Python, `sbt` for Scala, `mvn`/`gradle` for Java).

## Install

From the kit directory, install into the target repo:

```
./install-harness.sh --dir /path/to/your/repo
```

Or run it from inside the target repo with no `--dir`. The installer is **idempotent** — a re-run against an already-installed tree copies only what is absent, so it is a no-op rather than a second layer. It:

- tags the current commit `pre-harness-baseline` for one-move rollback;
- drops `ledger/` (the `append` writer, `audit.py`, `gate.py`, `librarian`, `retire`, `board.sh`, `red-proof`, the fixtures, the README, and the operators-manual);
- copies the six `ledger-*` skills into `.claude/skills/`;
- wires `.githooks/pre-commit` to the gate, installs `.githooks/post-commit`, and points `core.hooksPath` at `.githooks`;
- writes a `ledger/VERSION` stamp so staleness is detectable;
- bootstraps `ledger/claims.jsonl` with a genesis line and a single `unverified` claim parked under the `harness-verify` check.

**Tier.** The kit ships the **single-user (private, local) tier** — the only shipped mode. Your ledger is local; the gate keeps an automated collaborator and your own future carelessness honest, not a hostile local admin. Shared/team mode (server-side signing, provenance-verifiable discharge) is a named roadmap, deferred; `SECURITY.md` states the boundary plainly. There is no tier flag to set.

## Verify

```
./harness-verify.sh
```

This is the installer acting as its own first customer. It proves three things before it will sign the installed claim:

1. `ledger/audit.py` exits 0 on the live ledger (the structural invariants hold);
2. **hook-is-a-hook** — a forged `signed` commit on a scratch branch is **blocked** (a signature with no check behind it is a forgery, and a gate that lets one through is not a gate);
3. the ledger-tooling fixtures pass (retirement immutability, `red-proof`, the precedence and coverage courts).

Only with all three green does it sign the installed claim and record its line-hash for the forgery guard; the scratch probe is discarded and the ledger restored verbatim. Show the full output — the forgery-probe result and the `VERSION` stamp are the receipt that the front door works.

**After install, most users should run the Tour** (the operators-manual's Options section) to arm the repo deliberately and record the choices as a configuration claim. See `harness/ledger/operators-manual.md` and, for the narrative, `docs/week-with-the-kit.md`.

## Upgrade

When the kit is newer:

```
./install-harness.sh --dir /path/to/your/repo --upgrade
```

`--upgrade` overwrites the kit-owned verbatim files (the tooling, the skills, the fixtures) and re-stamps `ledger/VERSION`, but never touches the repo-owned `check.sh`, `languages`, `claims.jsonl`, or `trace/`. Re-run `harness-verify.sh` after.

## Rollback

`git checkout pre-harness-baseline` restores the pre-harness tree. To remove the harness: delete `ledger/`, revert the hook wiring, and revert the `CLAUDE.md` section. Archive accumulated ledger contents rather than destroying them.

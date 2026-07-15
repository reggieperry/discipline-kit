## Dev-ledger and gate harness

A claim ledger over this repo's own development, gated at commit (`ledger/`, docs in `ledger/README.md`). If this repo keeps another ledger for its own domain, this one is distinct — same idea, disjoint subject, separate store.

- **A "done" report is an unverified claim, never a signed one.** Nothing acquires a signature except through a mechanical check run by the commit-path gate; the gate is the sole writer of `signed`. Append assertions via `ledger/append` (`check: "none"` when no check exists) — assertions only, never a signature.
- **Review output — pr-review, deep-reason, and dynamic-workflow verification passes — is testimony in the dev-ledger; only mechanical checks sign.** A reviewer that finds a defect appends a `refutation`.
- **Retired claims leave the live board** (`ledger/librarian`): a defeated or superseded claim moves to `ledger/trace/` with a pointer, verbatim-move plus a sidecar record — immutability-safe to retire in any later commit.

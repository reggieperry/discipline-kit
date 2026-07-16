# Contributing

External contributions are welcome, and they are welcome as *testimony*. A contributor's work lands testimony-grade — evidence toward a claim, never the claim's verdict. The maintainer wraps it in the claim, and the gate signs after merge. No contributor is asked to run the full development loop.

## Inbound is claim-algebra traffic

Every inbound artifact is a move in the same algebra the kit runs internally. A bug report is an attempted refutation — it asserts that some believed or signed claim is false, or reveals one that was never filed. A feature request is an externally authored story — an acceptance criterion the maintainer may adopt and file. A pull request is a testimony-grade contribution — evidence toward a claim, not its disposition. In every case you contribute the claim, and ideally the check that would dispose it, not the verdict. The maintainer holds the record and wraps your contribution in the claim; the gate signs after merge.

## Signatures come only from the gate

A signature in this repo means exactly one thing: a named mechanical check ran and passed, minted by this repo's own commit-path gate. A contributor never adds a `"status":"signed"` ledger line — and never needs to. You send the claim; the maintainer's gate signs it after merge.

The `inbound-guard` workflow enforces this on the way in. A fork PR that adds a signed ledger line is rejected with:

> signatures are minted only by this repo's gate; contribute the claim, not the verdict.

Dissent, by contrast, lands freely. A refutation or a piece of testimony needs no sign-off, because neither becomes institutional belief on its own. Review output is testimony too — a maintainer's approval of your PR is evidence, not a signature, and it signs nothing by itself. Only a signature is gated, and only the gate mints it, on the merge commit that carries your change.

## Contributing a change

Open a pull request against the default branch. You are not asked to install the harness or run the full loop — that discipline is the maintainer's, and carrying it is never a condition of contributing. Write the change, say what it does, and open the PR.

If you run a harnessed repo yourself, you can make your contribution mechanically disposable by including a `kit-interchange: v1` block in the PR body:

```
kit-interchange: v1
claim: <the claim your change discharges, verbatim>
disposing-check: <a command that turns red on the defect, green on the fix>
red: <the red line you observed before the fix>
```

The block names the claim your change discharges, the disposing check as a runnable command, and the red line you observed. It lets the maintainer re-run your check under `ledger/interchange.py --verify` and dispose the contribution mechanically — DISCHARGEABLE if the check passes, RECEIPT-FAILED if it does not. The block authenticates nothing and proves no identity; it makes your contribution dischargeable. It is a courtesy that speeds review, not a requirement — a PR without one is reviewed the same way, by hand.

A foreign PR is reviewed as the testimony-grade contribution it is, through the `adversarial-review` skill's `foreign-pr` mode. That review produces a receipts-per-finding artifact — quoted evidence, a repro, and a disposing check on every line — rather than a ledger write, because the maintainer does not hold the record for your slice until it merges.

## Bugs and feature requests

File both through the issue templates. A bug report names the claim it refutes — or the one it reveals as missing — and gives the version receipt (from `ledger/VERSION`), the exact failing command, and what you would accept as done. A feature request states the behavior you want and the same acceptance line: what, concretely, would close it. The acceptance line is not ceremony — it is the story's criterion, the thing a future claim is checked against.

## Security

Do not file a vulnerability as a public issue. Report it privately through a GitHub security advisory on this repository — "Security" → "Report a vulnerability" — with a minimal reproduction and the affected files. Read `SECURITY.md` first: it states the trust model and what a signature does and does not mean, and a report framed in those terms is faster to act on.

## Tier — single-user by default

The kit ships single-user and private by default. In that tier the gate keeps an automated collaborator and your own future carelessness honest, not outside contributors, and there are no fork PRs for the inbound guard to screen. This file applies when a repo built on the kit opens to outside contributions; until then it is inert. The full trust model, and the boundaries it does not cross, are in `SECURITY.md`.

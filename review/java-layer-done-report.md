# v1.3.0 — the Java layer — done report

Built under the self-installed loop (the first loop-built kit release). Accurate at commit-and-ledger granularity, best-effort below.

## Shas

**Wave one (mechanism, on `main`):**
- `627651e` slice 0 — self-install the dev-ledger harness (kit dogfoods its own loop)
- `c1b3fb7` slice 1 claim-first (clm-0006, ledger-only) → `fbc45a9` green (clm-0009 **signed**) → `fc67252` red-proof receipt (clm-0010)
- `25593e7` slice 2 claim-first (clm-0011) → `487a314` green (clm-0014 **signed**) → `a00fb13` `--upgrade` sync + red-proof receipt (clm-0015)
- `f3de0da` slice 3 claim-first (clm-0018) → `a419541` templates + pr-review docs (clm-0019, check:none)
- `e820ae7` slice 4 — live sample gate run testimony (clm-0020)

**Wave two (judgment, branch `java-rules-v1.3.0`):**
- `92bb5a6` the eight `java-*` rule drafts
- `6425c98` parent assertion (clm-0021) + eight testimony entries (clm-0022…clm-0029)
- `79001a1` README rule table (50 rules) + CHANGELOG v1.3.0
- `605f0cc` dogfooding finding (clm-0030)

## Observed-red disclosures (the pasted red lines)

**Slice 1 — JavaToolchain** (16 fixtures, red against the pre-JavaToolchain gate):
```
AttributeError: module 'sdlc_gate' has no attribute 'JavaToolchain'. Did you mean: 'ScalaToolchain'?
sdlc-gate: unknown --toolchain 'java'
```
`red-proof: 1 new test path(s) failed against base c1b3fb74 (red confirmed)` → clm-0010 about clm-0009.

**Slice 2 — gate.py plumbing** (red against the no-Java-marker gate):
```
AssertionError: pom.xml must check_command() to mvn verify, got None
```
`red-proof: 1 new test path(s) failed against base 25593e74 (red confirmed)` → clm-0015 about clm-0014.

## Sample gate run (synthetic Maven repo, real git baseline→diff)

```
baseline: toolchain=java assert_total=3 suppressions_total=0
gate exit: 1  (blocked)   verdict: fail   toolchain: java
  BLOCK B / new_suppressions        -> SuppressWarnings[unchecked]
  BLOCK D.scalacheck / weakened_property_params -> tries 1000 -> 10
```
Both a suppression and a jqwik `tries` fall caught end to end.

## CI-equivalent green

`ledger/check.sh` green throughout — 22/22 (scrub-gate, board selftest, five ledger fixtures incl. `java_plumbing_test`, 36 `test_sdlc_gate.py` tests, validate_note). Actual GitHub CI runs on push.

## Season-bet counters (with a finding)

`ledger/audit.py --report`: **red-proof coverage 1/3 test-bearing slices; 3 `tdd-precedence` warns.** These are largely ARTIFACTS, not discipline failures (clm-0030):
- The three-link discharge chain (park-nonrunnable → repo-check → gate-sign) the preregister/discharge skills teach produces a repo-check *middle* link that lands with code; `warn_tdd_precedence` reads it as a late-precedence warn on clm-0007/clm-0012 — but the ORIGINAL parked claims clm-0006/clm-0011 WERE ledger-only and preceded their code. (clm-0003's warn is legitimate: slice zero was one infra commit.)
- Coverage undercounts because the receipts are filed `about` the signed 3rd-link claim, which doesn't match the `(parked, repo-check)` pair the counter walks. Both detector slices DO carry receipts (clm-0010, clm-0015).
- Recommendation for the operator: fix the checks to walk the supersedes-chain to its first ledger-only ancestor and accept a receipt anywhere on it, OR teach the two-link pattern (park directly under `repo-check`).

## Known residues (reported, per the STOP)

- **SpotBugs** (bytecode) is implemented fail-closed but not wired into default Check A — a source-snapshot differential can't compile bytecode, so default-path wiring would fail-open; its findings path awaits a compiled pilot.
- The jqwik param block reuses the shared helper and is labeled **`D.scalacheck`** even for Java (data correct, label scala-flavored) — renaming touches the shared engine helper, so reported not forced.
- The Scala side has the same latent `forAllNoShrink`-appearing fail-open the Java side closes by always-emitting the key; flagged, not fixed (out of the Java brief's scope).

## Wave-two PR (for the gavel)

The eight `java-*` rules are TESTIMONY (clm-0022…clm-0029) until the operator's review signs them into doctrine. The instance does not merge wave two. **PR is prepared on `java-rules-v1.3.0` but not yet pushed** — push-only-on-command. On the go, the PR description will carry the eight testimony ids and the post-gavel re-read line (whichever instance continues after the merge reads the eight `java-*` rules before their first use).

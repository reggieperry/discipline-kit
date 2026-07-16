---
name: Bug report
about: Report a defect in the discipline kit — evidence at the front door
title: ''
labels: bug
---

<!--
  A bug report is an attempted refutation of a claim: the harness asserts a behavior, and you have
  evidence it does not hold. Bring the evidence, not the prose — every field below is a receipt a
  maintainer reruns. Fill each one verbatim, and delete these comments as you go.
-->

## Version receipt

The `ledger/VERSION` of your checkout (`cat ledger/VERSION`, e.g. `v1.4.1`):

```
<paste the contents of ledger/VERSION>
```

## Verification output

The verbatim output of the check that failed. For an install- or gate-level defect run
`./harness-verify.sh`; for the kit's own acceptance suite run `bash ledger/check.sh`. Paste the
whole output — do not summarize, and do not trim the failing lines.

```
<paste the verbatim output of ./harness-verify.sh or bash ledger/check.sh>
```

## Failing command

The exact command that reproduces the defect, copied verbatim — for example `./harness-verify.sh`,
`bash ledger/check.sh`, or `bash install-harness.sh --dir <target-repo>`:

```
<the exact command>
```

## Expected vs. actual

- **Expected:** <what the kit should have done>
- **Actual:** <what it did instead>

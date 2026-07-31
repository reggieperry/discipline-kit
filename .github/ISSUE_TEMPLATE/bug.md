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

The `the version` of your checkout (`cat the version`, e.g. `v1.4.1`):

```
<paste the contents of the version>
```

## Verification output

The verbatim output of the check that failed. For an install- or gate-level defect run
whole output — do not summarize, and do not trim the failing lines.

```
```

## Failing command

The exact command that reproduces the defect, copied verbatim — for example `./harness-verify.sh`,

```
<the exact command>
```

## Expected vs. actual

- **Expected:** <what the kit should have done>
- **Actual:** <what it did instead>

---
name: Bug report
about: Report a defect against an installed harness — evidence at the front door
title: ''
labels: bug
---

<!--
  A bug report is an attempted refutation of a claim: the harness asserts a behavior, and you have
  evidence it does not hold. Bring the evidence, not the prose — every field below is a receipt the
  maintainer can rerun. Fill each one verbatim, and delete these guidance comments as you go.
-->

## Version receipt

The `the version` of the repo where the harness is installed:

```
<paste the contents of the version>
```

## Verification output

The verbatim output of `harness-verify.sh`, or of the specific check that failed. Paste it whole —
do not summarize, and do not trim the failing lines.

```
<paste the verbatim output>
```

## Failing command

The exact command that reproduces the defect, copied verbatim so the maintainer can rerun it:

```
<the exact command>
```

## Expected vs. actual

- **Expected:** <what the harness should have done>
- **Actual:** <what it did instead>

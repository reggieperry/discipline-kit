# Contributing

External contributions are welcome.

## Contributing a change

Open a pull request against the default branch. Say what the change does and why. If it fixes a
defect, include the smallest reproduction you can — a command and its output beats a description.

The kit's own check runs in CI and on the commit path (`scripts/check.sh`): the scrub gate, the
rule-grade check and its fixture, the differential-gate unit tests, and the algebra-note validator.
Run it locally before opening a PR if you can; a green run is the bar.

## Review

Review output is **evidence, not a verdict**. An approving review means a reader looked and found
nothing; it does not mean the change is correct, and it never substitutes for a check. Where a
change alters behaviour, say what check would catch a regression — and if none exists, say that
plainly rather than implying one does.

## Bugs and feature requests

File both through the issue templates. A bug report gives the version, the exact failing command,
and what you would accept as fixed. A feature request states the behaviour you want and the same
acceptance line: what, concretely, would close it. That line is not ceremony — it is what a future
check is written against.

## Security

Do not file a vulnerability as a public issue. Report it privately through a GitHub security
advisory on this repository, with a minimal reproduction and the affected files. Read `SECURITY.md`
first: it states the trust model and what this kit does and does not guarantee.

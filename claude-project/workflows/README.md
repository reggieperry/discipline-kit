# Shipped workflows

Workflows the kit ships for an installed repo, alongside the rules in `../rules/`. Like the rules,
they are **not** auto-installed — copy the ones a repo wants into its `.claude/workflows/`.

## `rule-review.js`

Reviews a change against the repo's **own** declared rules rather than against general good
practice, and targets attention by the enforcement grade each rule states about itself:

- **review and convention** — no check exists, so a reader is the only instrument these will ever
  get. One agent per rule.
- **partly mechanical** — the build refuses part of it. The agent is pointed at the remainder and
  told to say which part it treated as already covered.
- **mechanically enforced** — skipped, and *reported as skipped*, because a reviewer re-deriving
  what the compiler already refuses spends attention on something that has an owner.

It needs two things a workflow script cannot gather for itself, since a workflow has no filesystem:

```bash
python3 harness/rules_manifest.py            # the rules, their globs, their grades
git diff --name-only <base>...HEAD           # the changed files
```

The main loop passes both as `args`; the script does the glob matching, which is the part that
should be deterministic rather than delegated.

Its result carries `examinedNothing` and `skippedAsMechanical` for the reason every instrument here
carries a denominator: a rule that matched no file and a rule deliberately skipped are both
absences, and an absence nobody prints reads exactly like a check that passed.

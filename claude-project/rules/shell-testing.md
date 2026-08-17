---
paths:
  - "**/*.sh"
  - "**/*.bash"
  - "**/.githooks/*"
  - "**/*.bats"
---

# Shell testing

**Enforcement grade:** review and convention, entirely. `scripts/check.sh` runs `shellcheck`, which reads a script's syntax and never runs it, so nothing here is mechanical: the kit ships no shell test suite and `check.sh` invokes no shell test runner, which means a script whose failure branch has never been taken passes every check the kit applies. Read this as the discipline to follow by hand, and treat "wire a bats suite into `check.sh`" as work that would move this grade.

Shell scripts in this kit are instruments — they decide whether a commit lands. An instrument that has only ever been observed passing is the exact defect `craft-measurement.md` is about, and it is more likely in shell than anywhere else, because a script's failure branches are the ones that never run during development. Sources: the bats-core documentation (`@test`, `run`, `$status`, `$output`, `setup`/`teardown`, `bats_load_library`); the GNU Bash Reference Manual for the exit-status semantics being asserted; and the kit's own Python fixture suites (`harness/fixtures/*_test.py`), which are the shape to copy where a script's logic has already moved into Python.

> See `craft-measurement.md` for why an instrument must be shown to fail before it is believed, `craft-tdd.md` for the red-first cadence and the mutate-the-shipped-code beat, `shell-errors.md` for the three-valued exit vocabulary these tests assert, and `shell-style.md` for the length at which a script should become Python instead.

## Test the failure paths, because nothing else will

- **Every exit code the script can return needs a test that produces it.** A script documenting `0` pass, `1` fail, `2` could-not-run has three tests at minimum. The `2` case is the one that is never exercised by hand, and it is the one whose absence turns "nothing was examined" into a green commit.
- **Assert the status and the output, not one or the other.** A check that exits 1 with an empty message is as unusable as one that prints a diagnostic and exits 0. bats gives you both from one `run`.
- **Prove the check can fail before believing that it passed.** Feed it an input that must be rejected and confirm it is. A gate written and observed only on clean input has never demonstrated it does anything.

```bash
#!/usr/bin/env bats

@test "blocks when the gate script is missing" {
  cd "$BATS_TEST_TMPDIR"
  run bash "$KIT/.githooks/pre-commit"
  [ "$status" -eq 1 ]
  [[ "$output" == *"no check ran"* ]]
}

@test "passes on a clean tree and names the denominator" {
  run bash "$KIT/scripts/check.sh"
  [ "$status" -eq 0 ]
}
```

## Keep each test hermetic

- **Run in `$BATS_TEST_TMPDIR`, which bats creates fresh per test and removes afterward.** A test that writes into the repository leaves state for the next test and turns a failure into an ordering puzzle.
- **Never let a test touch the developer's real environment** — no writes outside the temp directory, no `git config --global`, no network. A test that mutates a shared resource passes alone and fails in a suite, which reads as flakiness and gets the test deleted.
- **Set up the fixture explicitly in `setup()` rather than depending on what a previous test left.** Two tests that must run in order are one test with a misleading name.
- **Where a script shells out to a tool you do not own, put a fake earlier on `PATH`** rather than mocking inside the script. That keeps the seam at the boundary and lets the test drive the tool's exit code, which is the thing under test.

## Assert on observable behavior

- **Assert on exit status, stdout, stderr, and the files the script created or removed.** These are its whole contract. Do not assert on an internal variable by sourcing the script — that couples the test to the implementation and, worse, runs the script's top level in the test's own shell.
- **Match output with a substring or a pattern, not a full-text equality.** Pinning the exact wording makes every message improvement a test failure, which trains people to update assertions without reading them.
- **A test that cannot fail is worse than no test.** `run cmd; [ "$status" -eq 0 ]` on a script that always exits 0 asserts nothing. Ask of each assertion what input would break it, and if there is none, delete or strengthen it.

## When the logic outgrows shell, move it and test it there

- **A script that needs branching logic, a data structure, or real error handling should be Python, and then it gets a real test suite.** The kit's own instruments went this way: `scope_check.py`, `comment_shape.py`, and `rule_grades.py` each carry a fixture suite in `harness/fixtures/`, and each of those suites exists because the logic was worth testing and shell would have made testing it painful.
- **What stays in shell is orchestration** — resolve paths, invoke tools in order, propagate status. That is testable with a handful of bats cases and does not want more.
- **Keep the shell wrapper thin enough that its own tests are about wiring**: does it find the tool, does it pass the arguments through, does it propagate a non-zero status, does it block when a precondition is missing.

## Anti-weakening

Treat any of these against the merge base as weakening, and do not introduce them:

- A bats test deleted, renamed to something the runner does not collect, or its body commented out.
- `skip` added to a test with no reason, or a `skip` whose stated condition is now permanently true.
- An assertion on `$status` removed, or loosened from a specific code to `[ "$status" -ne 0 ]` where the script distinguishes 1 from 2 — that erases exactly the could-not-run signal.
- An output assertion replaced with a wildcard that any output satisfies.
- A `shellcheck` finding cleared with a `# shellcheck disable=SCxxxx` that carries no reason. A disable comment needs the code, the reason, and the scope; a bare directive at the top of a file disables it everywhere below.

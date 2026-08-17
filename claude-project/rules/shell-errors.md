---
paths:
  - "**/*.sh"
  - "**/*.bash"
  - "**/.githooks/*"
---

# Shell errors and exit status

**Enforcement grade:** partly mechanical **where the repo has wired the scanner**, and the mechanical part is the smaller half. In the kit, `harness/shellcheck_all.sh` runs on the commit path and catches two of the traps below — reading `$?` instead of branching on the command (SC2181) and `local x=$(cmd)` masking a failure (SC2155) — both as build failures; a consuming repo installs this file without that wiring, so confirm it before relying on either. Nothing anywhere checks that `set -euo pipefail` is present, that a `trap` cleans up, that an exit code means what the script's own header says it means, or that a failure signal survives the pipe it was filtered through. The three-valued exit vocabulary below is convention held by review alone.

Shell has one error channel — the exit status of the last command — and a set of options that decide how aggressively the shell reads it. Most shell defects are not wrong logic; they are a failure that was reported and then discarded on the way out. Sources: the GNU Bash Reference Manual (`set`, `trap`, pipelines and exit status, `$?` and `PIPESTATUS`); the ShellCheck wiki for the two codes above, captured from the installed tool; and the defects recorded in `craft-measurement.md`, every one of which was a shell defect.

> See `shell-style.md` for the strict-mode header these rules depend on, `craft-measurement.md` for the worked failures — the filtered compile error, the wait loops with no deadline — and `shell-testing.md` for proving that a script's failure path actually fails.

## What `set -e` does not cover

`set -e` is necessary and it is not sufficient. Knowing where it stops is most of this rule.

- **`set -e` does not fire inside a condition.** A command in an `if`, a `while`, on the left of `&&` or `||`, or negated with `!` has its status consumed by the construct. That is correct and it is why `if ! cmd; then` is the right way to branch — but it also means a helper function called in a condition runs with `-e` effectively disabled for its whole body.
- **`set -e` does not fire on a pipeline's non-final stage without `pipefail`.** `cmd | tee log` exits with `tee`'s status. Set `-o pipefail` in the header, and where you need per-stage detail read `"${PIPESTATUS[@]}"` immediately — it is overwritten by the next command, including the one you use to test it.
- **`set -e` does not fire on a command whose status you assign.** `out=$(cmd)` propagates, but `local out=$(cmd)` does not, because `local` is the command that ran. Split the declaration (SC2155).
- **`set -u` does not protect an array subscript or a nested expansion.** `"${arr[$i]}"` with `i` unset under `-u` is an error, but `${arr[@]:-}` quietly defaults an entire array to empty, which is rarely what the author meant.

## Branch on the command, not on `$?`

- **Write `if ! cmd; then` rather than `cmd; if [[ $? -ne 0 ]]; then`.** `$?` is the status of the immediately preceding command, so any statement inserted between the two — a `echo`, a `local`, a later-added log line — silently changes what is being tested. ShellCheck reports this as SC2181.
- **Capture the status explicitly when you genuinely need it after other work.** `cmd; rc=$?` on the same logical step, before anything else runs, then branch on `"$rc"`.
- **Never read an exit code through a pipe.** `cmd | tail -5; echo $?` reports `tail`'s status, not `cmd`'s. Redirect to a file, capture the status, then filter the file:

```bash
# Filter the VIEW, never the record — and capture the status before any pipe.
cmd > run.log 2>&1; rc=$?
tail -20 run.log
if (( rc != 0 )); then
  echo "✖ cmd failed (exit $rc); full output in run.log" >&2
  exit 1
fi
```

## Check status and content; trust neither alone

- **A tool that exits 0 can still have failed.** This is recorded rather than hypothetical: a build tool printed `Error compiling project` and exited 0, and because its output ran through `grep`, the line saying so was removed. The check must read both.
- **A tool that exits non-zero can still have done the work.** `grep` exits 1 on no match, `diff` exits 1 on a difference. Neither is a failure, and `set -e` will treat both as one — guard them with `|| true` **and a comment saying which status you are absorbing**, never a bare `|| true` that swallows a real error too.

```bash
# grep exits 1 on "no match", which here is the expected case, not a failure.
if grep -q 'TODO' "$file"; then found=1; else found=0; fi
```

## An absent check is not a passing check

- **Distinguish three outcomes, not two, and give the third its own exit code.** The kit's own instruments use `0` pass, `1` fail, `2` **could not run** — no rules directory, no story on the base ref, nothing matched the pattern. A script that returns 0 when it examined nothing reports the same green as one that examined everything and found nothing wrong, and those are different facts.
- **Print the denominator on a passing run.** "0 findings across 41 files" and "0 findings" are the same exit code; only the first tells the reader the instrument was looking.
- **Fail closed when a precondition is missing.** The kit's `pre-commit` blocks when `scripts/check.sh` is absent rather than treating a missing gate as a clear one, and says why in the message. Copy that shape: a missing tool, an unreadable config, or an unresolvable ref exits non-zero.

```bash
if [[ ! -f scripts/check.sh ]]; then
  echo "✖ scripts/check.sh not found — commit blocked (no check ran)." >&2
  exit 1
fi
```

## Cleanup belongs in a trap

- **Register a `trap … EXIT` for anything that must be released**, and register it immediately after acquiring the thing. `EXIT` runs on a normal exit, on a `set -e` abort, and on an explicit `exit`; add `INT TERM` when the script can be interrupted mid-work and the resource is shared.
- **Make the handler idempotent and quiet.** It runs on the error path, where a second failure inside cleanup replaces the message the operator needed with one about the cleanup.
- **Create temp files with `mktemp`, and delete them in the trap** — never a fixed `/tmp/name` (`shell-security.md` covers why the fixed path is also a vulnerability).

```bash
tmp=$(mktemp) || exit 1
trap 'rm -f "$tmp"' EXIT
```

## Error messages

- **Send every diagnostic to stderr** with `>&2`. A message on stdout is captured by `$( )` at the call site and becomes part of the value.
- **Name the command, the exit status, and the remedy.** "failed" tells the operator nothing they did not already know from the exit code; "✖ sbt check failed (exit 1) — see /tmp/check.log" tells them where to look next.
- **Do not log a failure and then also return it.** Handle it once — either the caller decides, or you do.
- **Keep secrets out of the message and out of `set -x`.** Tracing prints every expanded argument, so a script that enables `-x` around a call carrying a token writes that token to the log (`shell-security.md`).

## Waiting

- **Every wait loop carries a deadline, exits non-zero on expiry, and prints the condition it was waiting for.** A loop whose only exit is success runs until someone notices; this cost half an hour of wall clock twice in this codebase's history, independently of why each condition was unreachable.
- **Wait on the process, not on a proxy for it.** `wait "$pid"` gives you the child's real status. `pgrep -f "<pattern>"` matches the watching script's own command line, because that command line contains the pattern — a measured failure, not a theoretical one.

```bash
deadline=$(( SECONDS + 60 ))
until [[ -S "$sock" ]]; do
  if (( SECONDS > deadline )); then
    echo "✖ timed out after 60s waiting for socket $sock" >&2
    exit 1
  fi
  sleep 1
done
```

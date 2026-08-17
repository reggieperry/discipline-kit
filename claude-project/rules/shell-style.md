---
paths:
  - "**/*.sh"
  - "**/*.bash"
  - "**/.githooks/*"
---

# Shell style and idioms

**Enforcement grade:** partly mechanical **where the repo has wired the scanner** — in the kit itself, `scripts/check.sh` runs `harness/shellcheck_all.sh` on the commit path and fails on any finding, so the quoting rules (SC2086, SC2046), the `cd` guard (SC2164), the `local`-masking trap (SC2155), the `printf` format rule (SC2059), and unused or unassigned variables (SC2034, SC2154) are build failures there. **In a consuming repo this file installs and that wiring does not**, so check before relying on it: if `shellcheck_all.sh` is not in your gate, read the whole page as review and convention. **And what shellcheck does not check is the most important rule here** — it was run against a script carrying no `set -euo pipefail` at all and reported nothing. The strict-mode header, naming, function shape, and the sourcing discipline are review and convention in every repo.

The base layer for shell: the strict-mode header, quoting, test syntax, functions, and sourcing. Shell is the language this kit is written in — `scripts/check.sh`, `scrub-gate.sh`, `install.sh`, and every installed repo's `.githooks/pre-commit` — so a defect here lands in the instrument rather than the subject. Sources: the GNU Bash Reference Manual (parameter expansion, `set` builtin options, `[[` conditional construct); the Google Shell Style Guide; the ShellCheck wiki, one page per SC code, with the codes above captured from the installed tool rather than recalled; and POSIX.1 Shell & Utilities for what is and is not portable.

> See `shell-errors.md` for exit status as the error channel and why `set -e` covers less than it appears to, `shell-security.md` for injection and temp files, `shell-testing.md` for proving a script can fail, `craft-measurement.md` for the filtered-failure-signal and wait-loop defects that are all shell defects, and `craft-documentation.md` for the comment discipline.

## Every script opens the same way

- **Start with `#!/usr/bin/env bash` and `set -euo pipefail`, on the first two lines.** `-e` exits on an unchecked non-zero command, `-u` makes an unset variable an error instead of an empty string, and `-o pipefail` makes a pipeline carry the failure of any stage rather than only the last. Without `pipefail`, `build | tee log` reports the exit status of `tee` — which is the mechanism behind the defect in `craft-measurement.md` where a compile failure printed green for a whole workstream.
- **Nothing mechanical will remind you.** ShellCheck does not require the header; a script missing all three options is clean by its lights. This is the one rule on the page where a reader is the only instrument.
- **`#!/usr/bin/env bash`, not `#!/bin/bash`.** The former finds bash on a PATH that may not be `/bin` (macOS with a Homebrew bash, a Nix profile). Use `#!/bin/sh` only when the script is genuinely POSIX and you have checked it with `shellcheck -s sh`.
- **When `-e` is deliberately off for a section, say why in a comment.** The kit's own `pre-commit` runs `set -uo pipefail` without `-e` because it needs to inspect the check's exit status and print its own message; that is a reason, and it is written down.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
```

## Quoting

- **Quote every expansion.** `"$var"`, `"${arr[@]}"`, `"$(cmd)"`. An unquoted expansion is subject to word splitting and pathname expansion, so a path containing a space becomes two arguments and a value containing `*` becomes a directory listing. This is the most common shell bug and ShellCheck catches it (SC2086 for a variable, SC2046 for a command substitution).
- **`"${arr[@]}"` is the only correct way to expand an array.** `"${arr[*]}"` joins with the first character of `IFS` into one word, and a bare `${arr[@]}` word-splits each element. The difference matters exactly when an element contains a space, which is when you would not notice.
- **Use `${var:?message}` to require a variable and `${var:-default}` to default it.** Under `set -u` a plain `$var` on an unset name aborts with the shell's own message, which names the variable but not what the caller should have done. `"${1:?usage: install.sh <dir>}"` says both.
- **Prefer `$(cmd)` to backticks.** Backticks nest badly and their escaping rules differ from the rest of the language; `$( )` nests directly.

## Tests and arithmetic

- **Use `[[ … ]]` for tests in bash, not `[ … ]`.** `[[` is a shell keyword rather than a command, so it does not word-split its operands — `[[ $unset_var == x ]]` is safe where `[ $unset_var == x ]` is a syntax error. It also gives you `=~`, `&&`, and `||` inside the brackets. Use `[ … ]` only in a genuinely POSIX `#!/bin/sh` script.
- **Use `(( … ))` for arithmetic and `$(( … ))` for arithmetic expansion.** `[[ $n -gt 3 ]]` works; `(( n > 3 ))` reads as arithmetic and does not need `$`.
- **Compare strings with `==` inside `[[`, and quote the left side but not a pattern on the right.** `[[ "$file" == *.sh ]]` matches a glob; `[[ "$file" == "*.sh" ]]` compares to a literal. Quoting the right side turns a pattern match into an equality test, silently.

## Functions and scope

- **Declare a function as `name() { … }` with no `function` keyword**, and give it a lower-snake-case name. The `function` keyword is a bashism that buys nothing.
- **Declare every function-local variable `local`.** A variable assigned without `local` inside a function is global, so two functions using `i` as a loop counter corrupt each other, and the corruption is invisible until the second one is called from inside the first.
- **Split `local` from a command substitution: `local x; x=$(cmd)`.** `local x=$(cmd)` makes `local` the command whose exit status the shell sees, so the substitution's failure is masked and `set -e` does not fire. ShellCheck catches this as SC2155 and it is worth knowing rather than deferring to the tool, because the same trap applies to `export`, `readonly`, and `declare`.
- **Return a value by printing it, and reserve the return status for success or failure.** A function that prints its result composes with `$( )`; a function that sets a global to communicate does not compose at all.

## Sourcing

- **Source with an explicit path and quote it: `source "$LIB_DIR/util.sh"`.** ShellCheck reports SC1091 when it cannot follow a non-constant source, which is a note rather than a defect — but it also means everything in that file is unchecked, so a sourced library needs its own shellcheck run.
- **A sourced file defines and does not act.** A library that runs work at source time makes every consumer pay for it and makes the file impossible to test in isolation. Put the work in functions and let the caller call them.
- **Resolve the script's own directory from `${BASH_SOURCE[0]}`, not `$0`.** `$0` is the invoking script when the file is sourced rather than executed, so `dirname "$0"` silently resolves against the wrong file.

## Naming and layout

- **Lower snake case for variables and functions, upper snake case for exported environment variables and for constants** — `readonly MAX_RETRIES=3`. Do not shout a local.
- **`readonly` anything that must not be reassigned**, and declare it once near the top. A constant reassigned halfway down a 300-line script is a bug nothing will catch.
- **Do not parse `ls`.** Its output is formatted for a terminal, it mangles names containing newlines, and it gives no way to distinguish an empty directory from a failure. Use a glob (`for f in ./*.sh`) or `find … -print0` with `read -d ''`.
- **Keep a script under a few hundred lines, and when it wants a data structure, stop.** Associative arrays, nested state, and anything needing real error handling are the signal to move to Python. Shell is a process-orchestration language; the kit's own harness is Python for exactly this reason.

## Comments

- **The comment discipline is `craft-documentation.md` and applies unchanged.** A header comment saying what the script is for and what a green run means earns its place; a comment restating the line below it does not. Interior comments are a smell unless the shell is genuinely forcing something unusual — and shell does force it occasionally, which is why `IFS=` before a `read` deserves a note and `cd "$(dirname "$0")"` does not.

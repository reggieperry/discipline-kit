---
paths:
  - "**/*.sh"
  - "**/*.bash"
  - "**/.githooks/*"
---

# Shell security

**Enforcement grade:** partly mechanical **where the repo has wired the scanner**, and the gap is specific enough to name. In the kit, `harness/shellcheck_all.sh` runs on the commit path and catches the quoting failures that are the main injection vector — an unquoted variable (SC2086) and an unquoted command substitution (SC2046) — both as build failures; a consuming repo installs this file without that wiring, so confirm it before relying on either. Regardless of wiring, shellcheck was measured against a script containing `eval "$1"` and **reported nothing**, so the sharpest construct on this page has no instrument anywhere. Temp-file creation, secrets in argv or under `set -x`, `PATH` handling, and the pipe-to-shell install pattern are review and convention.

Shell's defining hazard is that a string becomes a command. Every expansion is a splice into a command line, so untrusted data reaching an unquoted position is not a bug class adjacent to injection — it is injection. Sources: the GNU Bash Reference Manual (word splitting, `IFS`, `eval`, `set -x`); the ShellCheck wiki for the two codes above, captured from the installed tool; the OWASP Command Injection and Secrets Management cheat sheets; and the `mktemp(1)` and `umask(1)` manual pages.

> See `shell-style.md` for the quoting rules this rule depends on, `shell-errors.md` for failing closed and for traps that clean up, and the per-language security rules (`python-security.md`, `go-security.md`) for the same classes where a script shells out to a program written in one of them.

## Never let data become a command

- **`eval` is the construct to remove, not to secure.** There is no quoting discipline that makes `eval "$user_input"` safe, and no linter here reports it. Where you reach for `eval` to select behavior by name, use a `case` over a closed set instead — the set is then visible, reviewable, and cannot be extended by input.
- **Do not build a command as a string and run it.** `cmd="rm -rf $dir"; $cmd` re-splits on whitespace and expands globs in `$dir`. Put the command in an array and expand it quoted: `cmd=(rm -rf -- "$dir"); "${cmd[@]}"`.
- **Terminate option parsing with `--` before any argument that came from outside.** A filename of `--exclude=/` is read as a flag by most tools; `rm -rf -- "$dir"` is not.
- **Validate an external value against an allowlist before it reaches a command line**, and prefer a pattern that states what is allowed over one that lists what is forbidden.

```bash
# Closed set, visible in the source, not extendable by input.
case "$mode" in
  build|test|check) run_"$mode" ;;
  *) echo "✖ unknown mode: $mode" >&2; exit 2 ;;
esac
```

- **`IFS` is global and changing it changes how every later expansion splits.** Set it for exactly one command (`IFS=, read -ra parts <<<"$line"`) rather than assigning it and leaving it changed for the rest of the script.

## Temp files

- **Create every temp file and directory with `mktemp`, and delete it in a trap.** A fixed path like `/tmp/build-$$` is predictable, so another process on the machine can create it first as a symlink pointing somewhere else and win the race between the name being chosen and the file being opened. `mktemp` picks an unpredictable name and creates the file in one step.
- **`mktemp -d` for a working directory**, and quote every use of it — a temp path under a home directory can contain a space.
- **Set the umask before writing anything secret**, or create the file and `chmod 600` it before the first write. `mktemp` creates with mode 600 already; a redirect you open yourself does not.

```bash
work=$(mktemp -d) || exit 1
trap 'rm -rf "$work"' EXIT
```

- **Never `rm -rf "$dir"` where `$dir` could be empty.** Under `set -u` an unset variable aborts, which is the protection — but a variable set to the empty string does not, and `rm -rf "$prefix"/` with an empty prefix is `rm -rf /`. Guard with `${dir:?refusing to delete an unset path}`.

## Secrets

- **Never pass a secret as a command-line argument.** Every process's argv is readable from `/proc/<pid>/cmdline` by any process of the same user, and it lands in the shell history and in any `ps` output an operator pastes into a ticket. Pass secrets in the environment or on stdin.
- **Read a secret from a file or the environment at the point of use, and do not echo it.** `export ANTHROPIC_API_KEY` from a `0600` file outside the repository is the pattern this machine uses; a key in the script, in a committed config, or in a test fixture is a defect regardless of the repository's visibility.
- **`set -x` prints every expanded argument, so it prints secrets.** If a script traces, disable it around the call that carries the credential (`set +x` … `set -x`) and remember that the restore is what leaks if the call fails in between — under `set -e`, put the restore in a trap.
- **Redact before logging, not after.** A log line assembled with the secret in it has already been written by the time a filter sees it.

## Fetching and executing

- **Do not pipe a downloaded script into a shell.** `curl … | bash` executes bytes nobody has read, over a connection whose failure mid-stream leaves a truncated script that runs anyway — a partial download of a script whose last line is `rm -rf "$dir"` can execute a prefix that means something different. Download to a file, check it, then run it.
- **Pin what you fetch.** A URL that resolves to "latest" is a supply-chain dependency with no version; pin a tag or a digest and verify a checksum where the publisher offers one.
- **Set `PATH` explicitly at the top of any script that runs privileged or from cron.** A script that calls `git` resolves it against the invoker's `PATH`, which the invoker controls.

## Filesystem boundaries

- **Confine an externally-supplied path under a base directory before opening it.** Resolve it and check that it still starts with the base — a value containing `..` escapes an otherwise reasonable-looking join, and an absolute path ignores the base entirely.
- **Quote every path and terminate every loop over filenames safely.** `for f in $(find …)` splits on whitespace and breaks on any filename containing a space. Use `find … -print0` with `while IFS= read -r -d '' f`, or a glob, which does not split at all.

```bash
while IFS= read -r -d '' f; do
  process "$f"
done < <(find "$root" -name '*.sh' -print0)
```

- **Prefer a glob to `find` when the pattern is simple**, and handle the no-match case: a glob that matches nothing expands to itself unless `shopt -s nullglob` is set, so a loop body can receive the literal `*.sh` as a filename.

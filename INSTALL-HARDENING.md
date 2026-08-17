# INSTALL-HARDENING.md—the containment the machine supplies

This is the deliverable ADR-0005/D5 specifies: the hardening the chain cannot ship as code,
applied by the operator or the machine's admin, each step carrying the measurement that says
whether it took. Read ADR-0005 first. Its honest ceiling governs this file: in-process fencing is
friction, not containment, and on an unhardened host a phase runs as the operator with
passwordless root and a reachable push credential, so the trust boundary is not the dedicated
clone but the human act at the trunk. These steps are what make a blast-radius bound true, and
until they hold the chain is attended-only.

Every step names its measurement because a hardening step asserted but not measured is the
instrument reading clean because nothing looked. Where a measurement is a false-confidence trap
here, the step says so and names the test that actually exercises the mechanism.

## The reference-host baseline, measured 2026-08-15

Before any step, this is what the measurements read. Every one is the pre-hardening state, and
every step below moves one of them:

| Condition | Measured state today | The step that moves it |
|---|---|---|
| The phase's identity | the operator's own uid, in group `sudo` | 1. Dedicated run-user |
| Passwordless sudo for that identity | `sudo -n true` exits 0 (`NOPASSWD: ALL`) | 1. Dedicated run-user |
| The push credential | reachable via `gh auth token` (secret-service keyring) | 2. Credential isolation |
| Pinned examiner ownership | owner-writable by the phase (settings.json `0664`) | 3. Examiner ownership |
| Managed settings tier | `/etc/claude-code/managed-settings.json` absent | 4. Managed settings |
| The `bash -c` sandbox | `bwrap` fails `uid map: Permission denied` | 5. Bubblewrap sandbox |
| The gate that checks all of the above | does not exist | 6. Unattended-start gate |

None holds today, so unattended operation is refused (ADR-0005/D2) and the honest posture is a
human authoring the briefs and watching the run.

The steps are ordered by value. Step 1 and Step 2 together close the direct-to-trunk path the
ADR's draft-attack gate found—a phase pushing to the real trunk with the ambient credential —
and are the highest-value work even before unattended operation is contemplated. Steps 3 through 5
are the deeper tiers; Step 6 is the fail-closed gate that verifies all of them and is the
precondition ADR-0005/D2 gates unattended operation behind.

Placeholders used throughout: `RUN_USER` is the dedicated account (suggested `chainrunner`);
`ROOT` is the pinned root from `profile.toml` (`/var/lib/discipline-chain`); `OPERATOR` is the
operator's login and `~OPERATOR` their home. Substitute them in every pasteable block before
running it—an unsubstituted `RUN_USER` makes `sudo -u RUN_USER` error "unknown user", which
most measurements catch fail-closed but which is noise you do not want to debug mid-apply. The
measurement blocks use bash features (`< <(…)` process substitution, `$(( 8#$mode … ))` base
notation); run them under bash, not dash or an interactive zsh, or the octal read is wrong.

## Step 1—a dedicated unprivileged run-user

**What it buys.** The phase stops running as the operator. A separate system account with no
passwordless sudo and no privileged group cannot escalate to root, cannot rewrite the managed
settings of Step 4, and—because file permissions are per-uid—cannot read the operator's
`0600` secrets. This is the account Step 4's managed tier needs removed-sudo to trust, and the
identity Steps 2, 3, and 6 are all defined against.

**Evidence:** DOCUMENTED (man pages) and VERIFIED on this host using the existing `nobody`
account as a stand-in (creating the real account mutates the host and is the operator's to run).

**Apply**, as the operator (who holds the sudo to create it):

```
sudo useradd --system --create-home --home-dir /home/RUN_USER \
     --shell /usr/sbin/nologin RUN_USER
sudo passwd --lock RUN_USER
# Do NOT pass -G to add any group, and do NOT create any /etc/sudoers.d entry for RUN_USER.
# A user absent from sudoers and from every privileged group is granted nothing: absence is the denial.

# The chain needs a working area RUN_USER owns; the operator home is unreadable to it (see the trap).
sudo install -d -o RUN_USER -g RUN_USER -m 0755 /srv/chain
```

The sequencer, still running as the operator, invokes each phase as the run-user with an
environment allowlist—`env_reset` strips everything, so the API key is re-injected explicitly
and nothing else rides along:

```
sudo -u RUN_USER env -i \
     HOME=/home/RUN_USER PATH=/usr/bin:/bin:/opt/claude/bin \
     ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
     claude -p "<phase prompt>" --output-format stream-json --verbose ...
```

Two things about that invocation. The `claude` binary must be on the allowlisted `PATH` and
readable by the run-user: a per-user install under the operator's `0750` home is unreachable, so
install it system-wide or give the run-user its own copy and name its directory in `PATH` (shown
as `/opt/claude/bin`). And the invocation contract changes once Steps 4 and 5 land: the current
`--dangerously-skip-permissions` flag the invocation layer uses is blocked when launched via
`sudo` on Linux and is disabled outright by Step 4's `disableBypassPermissionsMode`, so under the
hardened posture the phase relies on the sandbox and the managed allow-rules instead of the skip
flag. Plan that change into the sequencer with the hardening; the flag and the hardened posture
cannot both hold.

**The measurement.** Three checks, and their polarities differ—do not conflate them:

```
# (A) DEFINITIVE no-sudo—read the MESSAGE, this command exits 0 regardless:
sudo -l -U RUN_USER            # expect: "User RUN_USER is not allowed to run sudo on <host>."
# (B) no passwordless sudo—read $?, not the text:
sudo -u RUN_USER sudo -n true; echo "exit=$?"   # expect nonzero
# (C) no privileged group:
id RUN_USER                    # expect only RUN_USER's own group, no sudo/adm/admin
# (D) the env boundary—the key is present, no push token rides along:
sudo -u RUN_USER env -i HOME=/home/RUN_USER ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
     env | grep -E 'ANTHROPIC_API_KEY|GH_TOKEN|GITHUB_TOKEN'   # expect only ANTHROPIC_API_KEY
```

**Traps.**

- Check (B) alone is a false-confidence instrument: `sudo -n true` failing proves only *no
  passwordless* sudo—a user with a password in sudoers prints the identical "a password is
  required" and exits 1. The definitive proof of no sudo at all is check (A), whose message you
  read rather than its exit. Opposite polarities on two adjacent checks; the gate of Step 6 must
  get both right.
- Bare `sudo -u RUN_USER claude` strips `ANTHROPIC_API_KEY` (that is `env_reset` doing its job),
  so the phase finds no key and fails. Re-inject it—and prefer the `env -i` allowlist over
  `--preserve-env`, so a future `GH_TOKEN` in the operator environment can never ride through.
- The isolation that hides the operator's secrets also hides the operator's files: a home at
  `0750` is untraversable by a foreign uid, so the run-user cannot reach a clone or worktree under
  `~OPERATOR`. Put the chain's clone and pinned root where the run-user can read them (`/srv/chain`,
  `/var/lib/discipline-chain`), never under the operator home.

## Step 2—the run-user reaches no publish credential

**What it buys.** This is the step that closes the direct-to-trunk path. On an unhardened host a
phase reads the operator's git push credential and runs `git push` to the real public trunk, no
human act, independent of terminal posture (ADR-0005/D4). Running phases as the Step-1 run-user
closes the operator's credential by uid, but the run-user must also hold none of its own and
inherit none in its environment.

**Evidence:** MIXED—VERIFIED for the host's credential facts; the cross-uid negative is
DOCUMENTED (a foreign uid cannot read a `0600` owner-only file with no ACL, confirmed by
`getfacl`/`getcap`).

**The correction that matters.** The obvious measurement—stat the token file—is wrong here,
and reads clean vacuously. On this host the gh config file carries no token (it is a short
non-secret file); the actual credential lives in the secret-service keyring and is retrieved
through `gh auth token` and `git credential fill`. Statting a file that is not the secret passes
while telling you nothing. The measurement must exercise the resolution path as the run-user.

**Apply**, as the operator:

```
# The Step-1 run-user already holds no credential by default. Make it explicit and keep it so:
sudo -u RUN_USER bash -lc 'rm -f ~/.git-credentials ~/.netrc; rm -rf ~/.config/gh'
# NEVER run `gh auth login` or `git config --global credential.helper` as RUN_USER.
# The sequencer must scrub the publish-credential environment before spawning a phase—these are
# NOT covered by ADR-0005/D6's CLAUDE_* scrub and must be added to it:
#   GH_TOKEN GITHUB_TOKEN GH_ENTERPRISE_TOKEN GITHUB_ENTERPRISE_TOKEN GH_CONFIG_DIR GIT_ASKPASS SSH_AUTH_SOCK
```

**The measurement**—run as the run-user, in the environment the sequencer will hand the phase,
and exercise the credential resolution rather than statting a file:

```
sudo -u RUN_USER bash -s <<'PROBE'
set -u; rc=0
sudo -n true 2>/dev/null && { echo "REACH: passwordless sudo"; rc=1; }
[ -n "$(gh auth token 2>/dev/null)" ] && { echo "REACH: gh resolves a token"; rc=1; }
printf 'protocol=https\nhost=github.com\n\n' | git credential fill 2>/dev/null | grep -q password= \
    && { echo "REACH: git credential fill returns a secret"; rc=1; }
[ -n "${GH_TOKEN:-}${GITHUB_TOKEN:-}" ] && { echo "REACH: token in environment"; rc=1; }
exit $rc
PROBE
echo "exit=$?"   # expect 0 with no REACH line
```

**Traps.**

- Statting the token file is the vacuous check above; do not ship it as the measurement.
- A zero-remote clone is not credential isolation. Removing `origin` bounds only default-remote
  resolution; a phase holding a live credential names the push URL explicitly. The zero-remote
  clone is friction (it removes the lazy path); the credential unreachability is the containment.
- An ssh agent socket (`SSH_AUTH_SOCK`) forwarded into the environment is a push credential too;
  the scrub list above includes it.

## Step 3—the pinned examiner material is root-owned and read-only to the run-user

**What it buys.** A phase is graded by the postconditions, the fence settings, and the phase
briefs under the pinned root. If the phase can write them, it grades itself. Making the examiner
material root-owned and unwritable by the run-user—while the per-run directories stay run-user
owned—means a phase reads its graders but cannot rewrite them.

**Evidence:** DOCUMENTED. The loader checks only that `run` is executable
(`loader.py:258`, `os.access(run, X_OK)`); it never reads ownership or mode, as its own docstring
states (`loader.py:74-85`), so this property is enforced by Step 6's gate, not by the loader.

**Apply**, as root:

```
ROOT=/var/lib/discipline-chain
# (0) The pinned root ITSELF must be root-owned, or the split is defeated: replacing a child entry
#     needs write on the PARENT dir, so a run-user-owned ROOT lets a phase
#     `mv postconditions postconditions.bak && mkdir postconditions` and plant a fresh writable grader.
chown root:root "$ROOT"; chmod 0755 "$ROOT"
# (1) Examiner material -> root-owned; dirs and existing-executables keep +x, data files drop to 0644.
#     Capital-X sets execute only on directories and already-executable files, so `run` stays runnable
#     while .md/.json/.txt/fixtures land 0644. A flat `chmod 0644` on files strips +x off `run` and the
#     loader then refuses it (could-not-run).
for d in settings briefs postconditions phases rules sequencer; do
  chown -R root:root "$ROOT/$d"; chmod -R u=rwX,go=rX "$ROOT/$d"
done
# (2) Per-run writable dirs stay owned by the run-user.
for d in worktrees streams records; do
  chown RUN_USER:RUN_USER "$ROOT/$d"; chmod 0755 "$ROOT/$d"
done
```

**The measurement**—stat the tree, and prove the write boundary as the run-user (the ground
truth that catches an ACL an octal-mode check would miss):

```
ROOT=/var/lib/discipline-chain; fail=0
[ "$(stat -c %U "$ROOT")" = root ] || { echo "ROOT not root-owned"; fail=1; }
for base in settings briefs postconditions phases rules sequencer; do
  while IFS='|' read -r owner mode path; do
    [ "$owner" = root ] || { echo "OWNER $path -> $owner"; fail=1; }
    [ $(( 8#$mode & 022 )) -eq 0 ] || { echo "WRITE $path is group/other-writable"; fail=1; }
  done < <(find "$ROOT/$base" -printf '%u|%m|%p\n')
done
# ground truth: the run-user must READ but not WRITE the examiner:
sudo -u RUN_USER test -r "$ROOT/settings/settings.json" || { echo "run-user cannot read examiner"; fail=1; }
sudo -u RUN_USER sh -c "echo x >> $ROOT/settings/settings.json" 2>/dev/null && { echo "run-user CAN WRITE examiner"; fail=1; }
echo "fail=$fail"   # expect 0
```

**Trap.** The parent-dir rename defeat (command 0) is the one most likely skipped: root-owning the
children while the root stays run-user-owned buys nothing. Assert the root itself.

## Step 4—the managed-settings tier, once passwordless sudo is gone

**What it buys.** `/etc/claude-code/managed-settings.json` is the highest-precedence settings
scope; no other scope, including command-line arguments, overrides a managed permission rule. It
can disable the bypass mode the invocation layer uses. But it is a trust root only if the phase
cannot rewrite it—which on a host with passwordless sudo it can (`sudo -n tee`), so Step 1's
removed-sudo is the precondition.

**Evidence:** DOCUMENTED against the official Claude Code docs (verified by fetch), with two
corrections to the design doc's binary-string reading: the keys sit under `permissions`, and one
key is not enough.

**Apply**, as root, precondition first:

```
# PRECONDITION: passwordless sudo must be gone, or a phase rewrites this file. Remove it FIRST.
sudo grep -rl NOPASSWD /etc/sudoers /etc/sudoers.d      # locate the granting drop-in
sudo visudo -f /etc/sudoers.d/<drop-in>                 # delete/replace the NOPASSWD line
sudo -n true 2>/dev/null && echo "ABORT: still passwordless—not a trust root" || echo "ok"

sudo install -d -o root -g root -m 0755 /etc/claude-code
sudo install -o root -g root -m 0644 /dev/stdin /etc/claude-code/managed-settings.json <<'JSON'
{
  "permissions": {
    "disableBypassPermissionsMode": "disable",
    "disableAutoMode": "disable"
  },
  "allowManagedPermissionRulesOnly": true
}
JSON
```

**The measurement:**

```
stat -c '%U %G %a %n' /etc/claude-code/managed-settings.json   # expect: root root 644 ...
# run AS THE OPERATOR, never as root—root's sudo -n always exits 0 and reads a false FAIL:
sudo -n true 2>/dev/null && echo "FAIL: NOPASSWD present" || echo "PASS: sudo needs a password"
python3 - <<'PY'
import json; d=json.load(open('/etc/claude-code/managed-settings.json'))
assert d['permissions']['disableBypassPermissionsMode']=='disable'
assert d['permissions']['disableAutoMode']=='disable'
assert d['allowManagedPermissionRulesOnly'] is True
print('keys OK')
PY
```

**Traps.**

- Two doors, not one. Disabling only bypass leaves `auto` mode—a second prompt-elimination path
 —open; `disableAutoMode` closes it. The design doc's single-key form is incomplete.
- Namespacing: both `disable*` keys go under `permissions`; a top-level placement is silently
  ignored. `allowManagedPermissionRulesOnly` is top-level and governs allow/ask/deny rules, not
  modes, so it does not substitute for the mode-disable keys.
- This is a denylist over another program's config across releases. Re-verify the key names on a
  harness version bump (ADR-0004/D5's re-probe).

## Step 5—the bubblewrap sandbox

**What it buys.** The sandbox is the only surveyed mechanism that reaches inside `bash -c` and
`python -c`, because it is a kernel mount-and-user namespace rather than a string match. It is the
tier that bounds what a phase reads and where it writes within its own authority—the half Step 1
does not cover (ADR-0005/D2, corrected: run-identity plus the sandbox, together). On Ubuntu 24.04
an unprivileged process may create a user namespace only under an AppArmor profile carrying the
`userns,` rule, which is why `bwrap` fails here today.

**Evidence:** MIXED. The AppArmor profile is DOCUMENTED and VERIFIED (byte-identical to both
Ubuntu's canonical profile and Claude Code's own sandboxing docs). The Claude Code sandbox
settings keys the design doc read from binary strings are corrected below; the flat names are
silently ignored.

**Apply**, as root—path A is surgical and keeps the system-wide restriction intact:

```
# PATH A (recommended): grant only bwrap the userns capability via an AppArmor profile.
sudo tee /etc/apparmor.d/bwrap >/dev/null <<'PROFILE'
abi <abi/4.0>,
include <tunables/global>
profile bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
  include if exists <local/bwrap>
}
PROFILE
sudo systemctl reload apparmor
# PATH B (blunter, system-wide—relaxes the restriction for every unprivileged app):
#   echo 'kernel.apparmor_restrict_unprivileged_userns=0' | sudo tee /etc/sysctl.d/99-bwrap.conf
#   sudo sysctl --system

# Then enable the sandbox, hard-failing rather than silently falling back (see the trap):
#   in the pinned/managed settings: {"sandbox": {"enabled": true, "failIfUnavailable": true}}
```

**The measurement:**

```
bwrap --unshare-user --ro-bind / / /bin/true; echo "exit=$?"   # expect exit 0 (today: uid-map denied, exit 1)
# Behavioral oracle—prove Claude USES it, not merely that bwrap can start. In a sandboxed session:
#   touch "$HOME/outside-cwd" && echo WROTE || echo BLOCKED     # a working sandbox prints BLOCKED
```

**Traps.**

- Fail-open by default: if bwrap cannot start, Claude Code warns and runs UNSANDBOXED. A green,
  error-free session does not prove the sandbox enforced anything—the silent-can-mean-not-looking
  pattern. The write-probe returning BLOCKED is the proof; `sandbox.failIfUnavailable: true` turns
  a broken sandbox into a hard stop.
- The flat keys from the binary strings (`sandboxEnabled`, `sandboxDenyPaths`,
  `areUnsandboxedCommandsForbiddenByPolicy`) are not settings keys and do nothing; use the nested
  `sandbox.enabled`, `sandbox.filesystem.denyRead`/`denyWrite`, and the managed
  `sandbox.allowUnsandboxedCommands: false`. All were grepped from a 2.1.224 binary and are not the
  public contract—re-verify on a version bump.

## Step 6—the unattended-start gate

**What it is.** ADR-0005/D2's fail-closed court: a check the sequencer runs before an unattended
run and refuses to start unless every condition above holds. It is not built; this is its spec, so
that "verified" has a single mechanical meaning and the unattended-run envelope story can build it.
Its absence is why unattended operation is refused today.

**Evidence:** PROPOSED (unbuilt). It is the gate that runs the other steps' measurements.

**The spec.** It runs as the run-user (a gate run as root or the operator makes `sudo -n true`
pass and every ownership probe meaningless—a catastrophic false pass, so it asserts `id -u`
matches the declared run-user first). It checks all six conditions every run; any failure exits 2
naming the failed condition, and an unmeasurable condition (a missing tool, an unreadable path, a
git error) also exits 2, never a skip. A partial gate is worse than none, so it never
short-circuits.

The conditions, each with its exit-2-on-failure probe:

1. `sudo -n true` fails for the run-user, and `sudo -l -U` reports no sudo (both polarities, Step 1).
2. every pinned examiner path is root-owned and not run-user-writable, proven by a write attempt
   as the run-user, not only by octal mode (Step 3).
3. the run-user resolves no push credential—`gh auth token` empty, `git credential fill` returns
   no secret, no token and no forwarded ssh-agent socket (`SSH_AUTH_SOCK`) in the environment
   (Step 2's real test, not a file stat).
4. the per-run directories are run-user owned (Step 3).
5. a `bwrap --unshare-user` probe succeeds AND the pinned or managed settings carry
   `sandbox.enabled: true` and `sandbox.failIfUnavailable: true` (Step 5). The bwrap probe alone
   is insufficient and would reproduce Step 5's own trap: Claude Code fails open, so a host where
   bwrap can start but the sandbox is not enabled runs the phase unsandboxed while a gate checking
   only the probe reports the tier in place. The settings assertion is what closes it.
6. the clone's remotes match the declared expectation (`--expect-remotes`).

These six omit Step 4's managed-settings tier deliberately, matching ADR-0005/D2's falsifier: a
clear gate means unattended operation may begin, not that every step in this file is applied.
Step 4 is a defense-in-depth tier the operator verifies with its own measurement, not a condition
the start gate reads.

It follows the kit's three-valued court convention (exit 0 clear, 2 could-not-run) and is testable
the way `profile-check.sh` is: point it at a throwaway pinned root with one planted hole per
condition and confirm each hole alone yields exit 2 naming exactly that condition.

**What running it would look like**, once the layout and the gate exist:

```
sudo -u RUN_USER env -i PATH=/usr/bin:/bin ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  /var/lib/discipline-chain/sequencer/unattended-start-gate.sh \
    --run-user RUN_USER --pinned-root /var/lib/discipline-chain \
    --clone /srv/chain/kit --expect-remotes none; echo "exit=$?"
# hardened host: "unattended-start: clear—6/6 conditions hold", exit 0
# reference host today: stderr enumerating conditions 1-5 failing, exit 2
```

## What this file does not buy

Applying every step makes unattended operation *permissible* under ADR-0005/D2; it does not make
the human trunk act unnecessary. The friction layers stay friction, the forged-ref residue stays
consumed not closed (ADR-0005/D3), and a green run is never a reason to skip the diff read
(ADR-0005/D4). What the steps change is the blast radius behind that human act—from the
operator's whole account and the public trunk, to the run-user's own writable set—which is the
difference between a boundary and its absence.

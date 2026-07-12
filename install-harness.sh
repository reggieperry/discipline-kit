#!/usr/bin/env bash
#
# install-harness.sh — install the dev-ledger + commit-path gate harness into a repo.
#
# The evidence half of the trust kernel: a claim ledger over the repo's own development,
# a mechanical gate at commit, the demotion of generative review to testimony, and the
# librarian over live claims. Additive (a ledger/ dir, hook wiring, one CLAUDE.md
# section, a baseline tag). IDEMPOTENT — re-running against an installed repo is a no-op.
# Scope: the pieces named below and nothing more.
#
#   ./install-harness.sh [--dir <repo>] [--verify]
#
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
H="$KIT/harness"
TARGET="."
VERIFY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) TARGET="$2"; shift 2 ;;
    --verify) VERIFY=1; shift ;;
    *) echo "usage: install-harness.sh [--dir <repo>] [--verify]" >&2; exit 2 ;;
  esac
done

cd "$TARGET"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "✖ not a git repo: $TARGET" >&2; exit 1; }
TARGET="$(pwd)"
echo "Installing dev-ledger harness into $TARGET"

# 1. ledger helpers — copy only what is ABSENT, so a re-run (or a repo with a
# customized gate) is a true no-op and nothing is clobbered.
mkdir -p ledger/trace ledger/fixtures
for f in audit.py append retire gate.py librarian board.sh README.md; do
  [ -f "ledger/$f" ] || cp "$H/ledger/$f" "ledger/$f"
done
[ -f ledger/fixtures/board-fixture.jsonl ] || cp "$H/ledger/fixtures/board-fixture.jsonl" ledger/fixtures/
chmod +x ledger/append ledger/retire ledger/gate.py ledger/librarian ledger/audit.py ledger/board.sh
[ -f ledger/trace/.gitkeep ] || touch ledger/trace/.gitkeep
echo "  ledger/ helpers + board + README in place"

# 1b. the ledger-discipline skills — teach the next instance to use the ledger correctly
# (read before writing, cite before re-checking, claim before building). Additive; absent-only.
mkdir -p .claude/skills
for s in ledger-board ledger-write ledger-preregister ledger-discharge ledger-retire ledger-verify; do
  [ -d ".claude/skills/$s" ] || cp -R "$H/skills/$s" ".claude/skills/$s"
done
echo "  ledger-* skills in .claude/skills/"

# 2. bootstrap the ledger — only if absent (installer-as-first-customer)
if [ ! -f ledger/claims.jsonl ]; then
  if git tag pre-harness-baseline -m "State before dev-ledger/gate harness." 2>/dev/null; then
    BASE="$(git rev-parse --short pre-harness-baseline^{commit})"
  else
    BASE="$(git rev-parse --short HEAD 2>/dev/null || echo root)"
  fi
  python3 - "$BASE" <<'PY'
import json, sys, datetime
base = sys.argv[1]
ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
e = {"id": "clm-0000", "ts": ts, "sha": None, "subject": "dev-ledger/gate harness",
     "claim": ("Harness installed by the kit install-harness.sh — ledger/ (claims.jsonl, trace/, "
       "append+retire+librarian, audit.py verbatim, gate.py), the pre/post-commit gate, and the "
       "CLAUDE.md demotion line. Baseline tag pre-harness-baseline (%s) for one-move rollback. "
       "Mechanical checks govern from this commit forward." % base),
     "source": "claude-code", "kind": "assertion", "about": None, "check": "none",
     "status": "unverified", "discharged_by": None, "supersedes": None, "trace_reason": None}
open("ledger/claims.jsonl", "w").write(json.dumps(e, separators=(",", ":")) + "\n")
PY
  # the working claim the verify step will discharge (installer-as-first-customer)
  echo '{"claim":"harness installed per brief and passes its own acceptance","subject":"install","source":"claude-code","kind":"assertion","status":"unverified","check":"harness-verify"}' \
    | python3 ledger/append >/dev/null
  echo "  bootstrapped ledger (clm-0000 + the installed claim)"
else
  echo "  ledger/claims.jsonl exists — left as-is (idempotent)"
fi

# 3. hooks
mkdir -p .githooks
[ -f .githooks/pre-commit ] || printf '#!/usr/bin/env bash\nset -uo pipefail\n' > .githooks/pre-commit
if ! grep -q "dev-ledger gate" .githooks/pre-commit; then
  cat "$H/templates/pre-commit-gate.snippet" >> .githooks/pre-commit
  echo "  pre-commit gate wired"
else
  echo "  pre-commit gate already wired"
fi
if [ ! -f .githooks/post-commit ]; then
  cp "$H/templates/post-commit" .githooks/post-commit
  echo "  post-commit installed"
fi
chmod +x .githooks/pre-commit .githooks/post-commit
if [ "$(git config core.hooksPath || true)" != ".githooks" ]; then
  git config core.hooksPath .githooks
  echo "  core.hooksPath -> .githooks"
fi

# 4. gitignore
if ! grep -q "ledger/.hook-signed" .gitignore 2>/dev/null; then
  cat "$H/templates/gitignore.snippet" >> .gitignore
  echo "  gitignore entries added"
fi

# 5. CLAUDE.md demotion section
if [ -f CLAUDE.md ]; then
  if ! grep -q "Dev-ledger and gate harness" CLAUDE.md; then
    printf '\n' >> CLAUDE.md
    cat "$H/templates/CLAUDE-harness-section.md" >> CLAUDE.md
    echo "  CLAUDE.md demotion section added"
  else
    echo "  CLAUDE.md demotion section already present"
  fi
else
  echo "  (no CLAUDE.md — add harness/templates/CLAUDE-harness-section.md by hand)"
fi

echo "Done."
if [ "$VERIFY" = 1 ]; then
  echo "--- verify ---"
  exec "$KIT/harness-verify.sh"
fi

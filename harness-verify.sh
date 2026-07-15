#!/usr/bin/env bash
#
# harness-verify.sh — mechanically verify an installed dev-ledger harness.
# Run from the target repo root. Checks the acceptance that must hold on every install:
#   1. ledger/audit.py exits 0 on the live ledger (the structural invariants hold).
#   2. hook-is-a-hook: a forged `signed` commit on a scratch branch is BLOCKED.
# On success it signs the "installed" claim, discharged by this verify run
# (installer-as-first-customer). Exit 0 iff verified.
#
set -uo pipefail
[ -f ledger/audit.py ] || { echo "✖ no ledger/ here — run from a repo with the harness installed" >&2; exit 2; }
fail=0

echo "verify 1/3: ledger/audit.py exits 0 on the live ledger"
if python3 ledger/audit.py --root . >/dev/null; then
  echo "  PASS"
else
  echo "  FAIL"; python3 ledger/audit.py --root . 2>&1 | tail -8; fail=1
fi

echo "verify 2/3: hook-is-a-hook — a forged signed commit is blocked"
ORIG="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
BR="harness-verify-$$"
BAK="$(mktemp)"; cp ledger/claims.jsonl "$BAK"   # file-level restore (claims.jsonl may be uncommitted)
if git checkout -q -b "$BR" 2>/dev/null; then
  echo '{"id":"clm-forgery-probe","ts":"2000-01-01T00:00:00Z","claim":"forged","source":"hook","kind":"assertion","status":"signed","discharged_by":{"check":"repo-check","run":"fake"}}' >> ledger/claims.jsonl
  git add ledger/claims.jsonl 2>/dev/null
  if git commit -q -m "forgery probe (must block)" >/dev/null 2>&1; then
    echo "  FAIL — the forged signed commit was NOT blocked"; fail=1
    git reset -q --hard "HEAD~1" >/dev/null 2>&1
  else
    echo "  PASS — blocked"
  fi
  git reset -q >/dev/null 2>&1
  git checkout -q "$ORIG" 2>/dev/null
  git branch -D "$BR" >/dev/null 2>&1
else
  echo "  SKIP — could not create a scratch branch"; fail=1
fi
cp "$BAK" ledger/claims.jsonl; rm -f "$BAK"   # restore the pre-probe ledger verbatim

echo "verify 3/3: ledger tooling fixtures (retire immutability-safe; red-proof rejects tautologies; tdd-precedence + coverage)"
for fx in retire_immutable_test red_proof_test tdd_precedence_test; do
  if [ -f "ledger/fixtures/$fx.py" ]; then
    if python3 "ledger/fixtures/$fx.py" >/dev/null 2>&1; then
      echo "  PASS  $fx"
    else
      echo "  FAIL  $fx"; python3 "ledger/fixtures/$fx.py" 2>&1 | tail -6; fail=1
    fi
  else
    echo "  SKIP  $fx — not installed"
  fi
done

if [ "$fail" != 0 ]; then echo "HARNESS VERIFICATION FAILED"; exit 1; fi

# installer-as-first-customer: sign the pending "installed" claim, discharged by this verify.
python3 - <<'PY'
import json, hashlib, subprocess, datetime
from pathlib import Path
LED = Path("ledger/claims.jsonl"); HS = Path("ledger/.hook-signed")
entries = [json.loads(l) for l in LED.read_text().splitlines() if l.strip()]
superseded = {e.get("supersedes") for e in entries if e.get("supersedes")}
installed = None
for e in entries:
    if (e.get("kind") == "assertion" and e.get("status") == "unverified"
            and e.get("check") == "harness-verify" and e.get("id") not in superseded):
        installed = e["id"]
if installed:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ent = {"claim": "harness installed per brief and passes its own acceptance", "subject": "install",
           "source": "hook", "kind": "assertion", "status": "signed", "check": "harness-verify",
           "supersedes": installed,
           "discharged_by": {"check": "harness-verify", "run": "harness-verify", "ts": ts}}
    p = subprocess.run(["python3", "ledger/append"], input=json.dumps(ent),
                       capture_output=True, text=True)
    if p.returncode == 0:
        last = LED.read_text().splitlines()[-1]
        with HS.open("a") as f:
            f.write(hashlib.sha256(last.encode()).hexdigest() + "\n")
        print(f"  signed the installed claim ({installed} -> {p.stdout.strip()}), discharged by harness-verify")
    else:
        print("  (could not sign the installed claim:", p.stderr.strip(), ")")
else:
    print("  (no pending installed claim — already signed, or a re-verify)")
PY

python3 ledger/audit.py --root . >/dev/null && echo "  post-sign audit exit 0" || { echo "  post-sign audit FAILED"; exit 1; }
echo "HARNESS VERIFIED"

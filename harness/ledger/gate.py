#!/usr/bin/env python3
"""ledger/gate.py — the commit-path gate. Called by the git hooks, not by hand.

  --pre-commit   (from .githooks/pre-commit, after gitleaks)
    1. FORGERY GUARD: any `signed` line newly staged into ledger/claims.jsonl that
       the gate did not itself write (its line-hash not in ledger/.hook-signed)
       blocks the commit. The gate is the sole writer of signatures.
    2. CHECK-DISCHARGE: if a staged file is in one of the repo's build languages (see
       `code_exts`) or a pending unverified claim names a runnable check, run the
       mechanical check — which must cover every one of those languages. On FAILURE, append a
       `refuted` entry (parent sha + patch-id, since pre-commit has no commit sha)
       and BLOCK — approving review testimony never signs. On PASS, queue the claims
       for the post-commit signer.
    3. AUDIT: run ledger/audit.py; block on any hard violation.

  --post-commit  (from .githooks/post-commit)
    Write the queued `signed` entries now that the commit sha exists, and record each
    one's line-hash in ledger/.hook-signed so the forgery guard admits it next commit.

The mechanical check is auto-detected (see `check_command`): a repo-provided
`ledger/check.sh`, else an sbt/uv toolchain default, else none (forgery guard + audit
only). LEDGER_CHECK_CMD overrides it (test-only knob — a bypass is exactly what the
harness forbids in real use).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "ledger" / "claims.jsonl"
HOOKSIGNED = ROOT / "ledger" / ".hook-signed"
PENDING = ROOT / "ledger" / ".pending-sign"
APPEND = ROOT / "ledger" / "append"
AUDIT = ROOT / "ledger" / "audit.py"
CHECK_NAME = "repo-check"
STANDARD_CLAIM = "the repo's mechanical check passes"
RUNNABLE = {"repo-check", "scala-check", "scala-suite", "typecheck"}
CODE_EXTS = (".scala", ".sc", ".sbt", ".py", ".go", ".ts", ".tsx", ".js", ".rs", ".java", ".kt")


def check_command() -> list[str] | None:
    """The repo's mechanical check, auto-detected. LEDGER_CHECK_CMD overrides (test
    knob). A repo-provided `ledger/check.sh` wins next (the recommended way to pin the
    exact check). Otherwise a toolchain default; None means no check is wired, so the
    gate runs the forgery guard + audit only."""
    env = os.environ.get("LEDGER_CHECK_CMD")
    if env is not None:
        return env.split()
    if (ROOT / "ledger" / "check.sh").exists():
        return ["bash", "ledger/check.sh"]
    if (ROOT / "build.sbt").exists():
        return ["sbt", "-batch", "-Dsbt.color=false", "check"]
    if (ROOT / "pyproject.toml").exists():
        return ["uv", "run", "pytest", "-q"]
    return None


def code_exts() -> tuple[str, ...]:
    """Extensions whose staged change should fire the check — every language that builds
    the SYSTEM in this repo. A repo may build from several (the lab is Scala + a
    TypeScript frontend); the gate must fire for all of them, and `ledger/check.sh` must
    in turn check all of them — else a change in an unchecked language slips through
    green (a fail-open). Vendored or tooling sources in a language the system is not
    built in (a Go reference copy, the ledger's own Python) are deliberately excluded.

    Resolution: `LEDGER_CODE_EXTS` override (test knob) → a per-repo `ledger/languages`
    declaration (authoritative: one extension per line, `#` comments; the robust choice
    when build markers are nested or vendored) → a union auto-detected from the build
    markers at the repo root → a broad fallback (any source — fail-closed)."""
    def norm(toks) -> tuple[str, ...]:
        return tuple(dict.fromkeys(t if t.startswith(".") else "." + t for t in toks))
    env = os.environ.get("LEDGER_CODE_EXTS")
    if env:
        return norm(env.replace(",", " ").split())
    decl = ROOT / "ledger" / "languages"
    if decl.exists():
        toks = [t for line in decl.read_text().splitlines() for t in line.split("#", 1)[0].split()]
        if toks:
            return norm(toks)
    detected: list[str] = []
    if (ROOT / "build.sbt").exists():
        detected += [".scala", ".sc", ".sbt"]
    if (ROOT / "tsconfig.json").exists() or (ROOT / "package.json").exists():
        detected += [".ts", ".tsx"]
    if (ROOT / "go.mod").exists():
        detected += [".go"]
    if (ROOT / "pyproject.toml").exists() or (ROOT / "setup.py").exists():
        detected += [".py"]
    if (ROOT / "Cargo.toml").exists():
        detected += [".rs"]
    return norm(detected) if detected else CODE_EXTS


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def clean_env() -> dict:
    """Strip the GIT_* vars git sets for a hook (GIT_INDEX_FILE=.git/index, GIT_DIR, …)
    before running the check. The check may itself run git — a project whose tests do
    `git worktree add` / `git commit` in scratch repos — and inheriting the hook's
    transient index both FAILS those tests and can CORRUPT the main repo (worktree and
    commit ops land on the wrong index). The check must see the normal repo."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def line_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def append_entry(e: dict) -> tuple[int, str]:
    """Append through the schema-validating ledger/append helper."""
    p = subprocess.run([sys.executable, str(APPEND)], cwd=ROOT,
                       input=json.dumps(e), capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr)
    return p.returncode, p.stdout.strip()


def staged_added_ledger_lines() -> list[str]:
    r = sh(["git", "diff", "--cached", "--unified=0", "--", "ledger/claims.jsonl"])
    return [l[1:] for l in r.stdout.splitlines() if l.startswith("+") and not l.startswith("+++")]


def staged_code() -> list[str]:
    r = sh(["git", "diff", "--cached", "--name-only"])
    return [f for f in r.stdout.split() if f.endswith(code_exts())]


def hook_hashes() -> set[str]:
    return set(HOOKSIGNED.read_text().split()) if HOOKSIGNED.exists() else set()


def pending_runnable() -> list[dict]:
    out = []
    if LEDGER.exists():
        for l in LEDGER.read_text().splitlines():
            if not l.strip():
                continue
            try:
                e = json.loads(l)
            except Exception:
                continue
            if (e.get("kind") == "assertion" and e.get("status") == "unverified"
                    and e.get("check") in RUNNABLE):
                out.append(e)
    return out


def run_ref() -> tuple[str, str]:
    parent = sh(["git", "rev-parse", "--short", "HEAD"]).stdout.strip() or "root"
    patch = ""
    diff = sh(["git", "diff", "--cached"]).stdout
    if diff:
        pp = subprocess.run(["git", "patch-id", "--stable"], input=diff,
                            capture_output=True, text=True)
        toks = pp.stdout.split()
        patch = toks[0][:12] if toks else ""
    return parent, patch


def pre_commit() -> int:
    # 1. forgery guard
    hs = hook_hashes()
    for l in staged_added_ledger_lines():
        try:
            e = json.loads(l)
        except Exception:
            continue
        if e.get("status") == "signed" and line_hash(l) not in hs:
            sys.stderr.write("✖ dev-ledger: a `signed` entry is staged that the gate did not write "
                             "— forged signature, commit blocked.\n")
            sys.stderr.write(f"   {e.get('id', '?')}: {(e.get('claim') or '')[:80]}\n")
            return 1

    # 2. check-discharge
    code = staged_code()
    pend = pending_runnable()
    cmd = check_command()
    if (code or pend) and cmd:
        parent, patch = run_ref()
        ref = f"{CHECK_NAME}@{parent}+{patch}"
        sys.stderr.write(f"dev-ledger gate: running `{' '.join(cmd)}` "
                         f"({'code staged' if code else 'pending claims'})…\n")
        r = sh(cmd, env=clean_env())
        if r.returncode != 0:
            append_entry({
                "claim": STANDARD_CLAIM, "subject": "verification-surface", "source": "hook",
                "kind": "assertion", "status": "refuted", "check": CHECK_NAME,
                "sha": f"{parent}+{patch}",
                "discharged_by": {"check": CHECK_NAME, "run": ref, "ts": now()},
            })
            sys.stderr.write("✖ dev-ledger: mechanical check FAILED — commit blocked, refuted "
                             "entry recorded. Approving review testimony does not sign.\n")
            return 1
        PENDING.write_text(json.dumps({
            "run": ref, "check": CHECK_NAME, "claim": STANDARD_CLAIM,
            "subject": "verification-surface",
            "pending": [{"id": e["id"], "claim": e["claim"], "subject": e.get("subject"),
                         "check": e["check"]} for e in pend],
        }) + "\n")

    # 3. audit
    a = sh([sys.executable, str(AUDIT), "--root", "."])
    if a.returncode != 0:
        sys.stderr.write("✖ dev-ledger: audit.py found a hard violation — commit blocked.\n")
        sys.stderr.write(a.stdout[-1000:])
        return 1
    return 0


def _sign(claim: str, subject, check: str, ref: str, sha: str, supersedes=None) -> None:
    e = {"claim": claim, "subject": subject, "source": "hook", "kind": "assertion",
         "status": "signed", "sha": sha, "check": check,
         "discharged_by": {"check": check, "run": ref, "ts": now()}}
    if supersedes:
        e["supersedes"] = supersedes
    rc, _ = append_entry(e)
    if rc == 0:
        last = LEDGER.read_text().splitlines()[-1]
        with HOOKSIGNED.open("a", encoding="utf-8") as f:
            f.write(line_hash(last) + "\n")


def post_commit() -> int:
    if not PENDING.exists():
        return 0
    try:
        q = json.loads(PENDING.read_text())
    except Exception:
        PENDING.unlink()
        return 0
    sha = sh(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    _sign(q["claim"], q["subject"], q["check"], q["run"], sha)
    for p in q.get("pending", []):
        _sign(p["claim"], p.get("subject"), q["check"], q["run"], sha, supersedes=p["id"])
    PENDING.unlink()
    return 0


def main() -> int:
    if "--pre-commit" in sys.argv:
        return pre_commit()
    if "--post-commit" in sys.argv:
        return post_commit()
    sys.stderr.write("usage: ledger/gate.py --pre-commit | --post-commit\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())

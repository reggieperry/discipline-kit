#!/usr/bin/env python3
"""Red-first fixture for `install.sh --refresh-rules` and `scripts/tag-consumption-check.sh`.

ADR-0002/D7: downstream consumption pins tags, never `main`. Before this story the refresh
path copied `claude-project/rules/*.md` from whatever tree the checkout held and scraped a
version out of the checkout's `CHANGELOG.md`, resolving no tag at all — so a bad merge on
`main` reached consumers on their next routine refresh, before any backstop could act. The
installer cases drive the real `install.sh` (copied into scratch kit repositories, since it
derives its kit root from its own location) and assert the refreshed content is the TAG's,
not HEAD's. The court cases drive D7's check, whose known-bad plant is the pre-fix refresh
region verbatim: the patterns are grounded in a defect that actually shipped, not a guessed
one.

  THE INSTALLER
  refresh-resolves-latest-tag-0  HEAD differs from every tag       -> 0, the newest release
                                                                      tag's content, its name
                                                                      reported, the CHANGELOG
                                                                      decoy version absent
  refresh-explicit-tag-0         --tag names an older release      -> 0, that tag's content
  refresh-unknown-tag-1          --tag names no tag                -> 1, named, nothing copied
  bare-tree-refusal-1            a kit tree with no .git           -> 1, named, nothing copied
  no-tags-refusal-1              a kit repo with no release tag    -> 1, named, nothing copied
  no-rules-dir-1                 a consumer with no .claude/rules  -> 1 (the refusal that
                                                                      predates this story)
  tag-without-refresh-2          --tag outside --refresh-rules     -> 2, usage

  THE D7 COURT
  court-clean-real-0             the real repository               -> 0, denominators printed
  court-clean-plant-0            a tag-resolving refresh region    -> 0
  court-pre-fix-1                the pre-fix region verbatim       -> 1, all three of its
                                                                      defects named (checkout
                                                                      copy, CHANGELOG scrape,
                                                                      no tag resolution)
  court-main-rev-1               `g archive main`                  -> 1, non-tag rev
  court-head-rev-1               `git archive HEAD`                -> 1, non-tag rev
  court-empty-corpus-2           no install.sh at the root         -> 2, VOID, never a pass
  court-region-missing-2         install.sh with no refresh path   -> 2, VOID, never a pass

`refresh-resolves-latest-tag-0` plants v0.9.0 and v0.10.0 with different rule bodies, so it
also pins VERSION sort: a lexical sort resolves v0.9.0 and fails the case. `court-pre-fix-1`
asserts one marker per pattern, so neutering any single pattern in the court is caught here
even while the other two still drive the exit code to 1. The two VOID cases exist because a
court that scanned nothing must not read as a court that found nothing: an absent corpus and
a refresh region the extractor cannot find are could-not-run, never clean.

Run: python3 harness/fixtures/install_test.py   (exit 0 = pass).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "install.sh"
COURT = REPO / "scripts" / "tag-consumption-check.sh"

RULE_REL = Path("claude-project/rules/kit-rule.md")
V9_BODY = "rule body shipped in v0.9.0\n"
V10_BODY = "rule body shipped in v0.10.0\n"
HEAD_BODY = "rule body only HEAD holds, never tagged\n"
STALE_BODY = "stale rule body from an earlier refresh\n"
LOCAL_BODY = "authored by the consumer, not the kit's to overwrite\n"

COURT_PASS = "tag-consumption-check: clean"
COURT_VOID = "tag-consumption-check: VOID"
COURT_FAIL = "tag-consumption-check: FAIL"


def clean_env() -> dict[str, str]:
    """The environment with git's own variables dropped.

    A `pre-commit` hook exports `GIT_DIR` and `GIT_INDEX_FILE`, and a subprocess inherits
    them, so a fixture that builds a throwaway repository writes into the REAL one instead.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> str:
    """Git confined to the scratch repository, with signing off.

    An operator config carrying `tag.gpgsign = true` turns a bare `git tag` into a signed
    annotated tag, which prompts for a message and a key; a fixture must not depend on the
    operator's signing setup, so both signing switches are pinned off per invocation.
    """
    done = subprocess.run(
        ["git", "-c", "tag.gpgsign=false", "-c", "commit.gpgsign=false",
         "-C", str(repo), *args],
        capture_output=True, text=True, check=True, env=clean_env(),
    )
    return done.stdout.strip()


def kit_tree(td: Path, *, repo: bool = True, tags: bool = True) -> Path:
    """A kit-shaped tree carrying the real installer.

    `repo=False` leaves no `.git` (the tarball-download shape); `tags=False` leaves a
    repository whose release tags were never fetched. With both true the tree carries two
    release tags whose rule bodies differ from each other and from HEAD's, plus a CHANGELOG
    claiming a version no tag names — the decoy the pre-fix scrape would have reported.
    """
    kit = td / "kit"
    (kit / RULE_REL).parent.mkdir(parents=True)
    shutil.copy(INSTALLER, kit / "install.sh")
    (kit / RULE_REL).write_text(V9_BODY)
    if not repo:
        return kit
    git(kit, "init", "-q", "-b", "main", ".")
    git(kit, "config", "user.email", "fixture@example.invalid")
    git(kit, "config", "user.name", "fixture")
    git(kit, "add", "-A")
    git(kit, "commit", "-qm", "v0.9.0 tree")
    if tags:
        git(kit, "tag", "v0.9.0")
        (kit / RULE_REL).write_text(V10_BODY)
        git(kit, "add", "-A")
        git(kit, "commit", "-qm", "v0.10.0 tree")
        git(kit, "tag", "v0.10.0")
    (kit / RULE_REL).write_text(HEAD_BODY)
    (kit / "CHANGELOG.md").write_text("# Changelog\n\n## v9.9.9 (never tagged)\n")
    git(kit, "add", "-A")
    git(kit, "commit", "-qm", "untagged head")
    return kit


def consumer_tree(td: Path) -> Path:
    consumer = td / "consumer"
    rules = consumer / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "kit-rule.md").write_text(STALE_BODY)
    (rules / "local-rule.md").write_text(LOCAL_BODY)
    return consumer


def run_installer(kit: Path, consumer: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(kit / "install.sh"), "--refresh-rules", "--dir", str(consumer), *extra],
        capture_output=True, text=True, env=clean_env(),
    )


def run_court(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(COURT), str(root)], capture_output=True, text=True, env=clean_env(),
    )


class Failure(Exception):
    pass


def expect(cond: bool, why: str) -> None:
    if not cond:
        raise Failure(why)


def unchanged(consumer: Path) -> None:
    expect(
        (consumer / ".claude" / "rules" / "kit-rule.md").read_text() == STALE_BODY,
        "a refused refresh must copy nothing, but the consumer's rule changed",
    )


def case(name: str, body) -> bool:
    try:
        with tempfile.TemporaryDirectory() as td:
            body(Path(td))
        print(f"  ok   {name}")
        return True
    except Failure as e:
        print(f"  FAIL {name}: {e}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  FAIL {name}: fixture git call failed: {e.stderr.strip()[:300]}")
        return False


def refresh_resolves_latest_tag(td: Path) -> None:
    kit, consumer = kit_tree(td), consumer_tree(td)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:300]}")
    refreshed = (consumer / ".claude" / "rules" / "kit-rule.md").read_text()
    expect(
        refreshed == V10_BODY,
        f"want the newest release tag's rule body, got {refreshed!r} "
        "(HEAD's body means no tag was resolved; v0.9.0's means a lexical sort)",
    )
    expect("v0.10.0" in said, f"the resolved tag must be reported, got: {said.strip()[:300]}")
    expect("v9.9.9" not in said, "the CHANGELOG decoy version leaked into the report")
    expect(
        (consumer / ".claude" / "rules" / "local-rule.md").read_text() == LOCAL_BODY,
        "a consumer-authored rule under another name must be untouched",
    )


def refresh_explicit_tag(td: Path) -> None:
    kit, consumer = kit_tree(td), consumer_tree(td)
    got = run_installer(kit, consumer, "--tag", "v0.9.0")
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:300]}")
    refreshed = (consumer / ".claude" / "rules" / "kit-rule.md").read_text()
    expect(refreshed == V9_BODY, f"want v0.9.0's rule body, got {refreshed!r}")
    expect("v0.9.0" in said, f"the pinned tag must be reported, got: {said.strip()[:300]}")


def refresh_unknown_tag(td: Path) -> None:
    kit, consumer = kit_tree(td), consumer_tree(td)
    got = run_installer(kit, consumer, "--tag", "v3.0.0")
    said = got.stdout + got.stderr
    expect(got.returncode == 1, f"want exit 1, got {got.returncode}: {said.strip()[:300]}")
    expect("v3.0.0" in said, f"the missing tag must be named, got: {said.strip()[:300]}")
    unchanged(consumer)


def bare_tree_refusal(td: Path) -> None:
    kit, consumer = kit_tree(td, repo=False), consumer_tree(td)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 1, f"want exit 1, got {got.returncode}: {said.strip()[:300]}")
    expect(
        "not a git checkout" in said,
        f"the bare tree must be refused by name, got: {said.strip()[:300]}",
    )
    unchanged(consumer)


def no_tags_refusal(td: Path) -> None:
    kit, consumer = kit_tree(td, tags=False), consumer_tree(td)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 1, f"want exit 1, got {got.returncode}: {said.strip()[:300]}")
    expect(
        "no release tag" in said,
        f"the missing tags must be refused by name, got: {said.strip()[:300]}",
    )
    unchanged(consumer)


def no_rules_dir(td: Path) -> None:
    kit = kit_tree(td)
    consumer = td / "consumer"
    consumer.mkdir()
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 1, f"want exit 1, got {got.returncode}: {said.strip()[:300]}")
    expect("no .claude/rules" in said, f"want the standing refusal, got: {said.strip()[:300]}")


def tag_without_refresh(td: Path) -> None:
    kit = kit_tree(td)
    got = subprocess.run(
        ["bash", str(kit / "install.sh"), "--tag", "v0.9.0"],
        capture_output=True, text=True, env=clean_env(),
    )
    expect(got.returncode == 2, f"want usage exit 2, got {got.returncode}")


# The pre-fix refresh region, captured VERBATIM from install.sh before this story's fix (only
# the surrounding argument parsing is reduced to what the court reads). This is the known-bad
# corpus the court's patterns are grounded in: a copy sourced from the checkout's working
# tree, a version scraped from the checkout's CHANGELOG, and no tag resolved anywhere.
PRE_FIX_INSTALLER = r"""#!/usr/bin/env bash
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REFRESH_RULES=1
TARGET="."
if [ "$REFRESH_RULES" = 1 ]; then
  cd "$TARGET"
  if [ ! -d .claude/rules ]; then
    echo "no .claude/rules in $(pwd)" >&2
    exit 1
  fi
  cp "$KIT"/claude-project/rules/*.md .claude/rules/
  ver="$(grep -m1 -oE 'v[0-9]+\.[0-9]+\.[0-9]+' "$KIT/CHANGELOG.md" 2>/dev/null || echo v0.0.0)"
  echo "refreshed .claude/rules/ in $(pwd) from discipline-kit $ver"
  exit 0
fi
"""


def rev_swapped_installer(rev: str) -> str:
    """The fixed refresh shape with the archived rev swappable.

    With `"$tag"` it is the clean control; with `main` or `HEAD` it is D7's named falsifier —
    a consumer path whose mechanics look right but whose rev is not a tag.
    """
    return r"""#!/usr/bin/env bash
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REFRESH_RULES=1
TARGET="."
g() { git -C "$KIT" "$@"; }
if [ "$REFRESH_RULES" = 1 ]; then
  cd "$TARGET"
  tag="$(g tag --list 'v[0-9]*' --sort=-version:refname | head -n 1)"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  g archive REV claude-project/rules | tar -x -C "$tmp"
  cp "$tmp"/claude-project/rules/*.md .claude/rules/
  exit 0
fi
""".replace("REV", rev)


def plant(td: Path, installer_body: str | None) -> Path:
    root = td / "planted"
    root.mkdir()
    if installer_body is not None:
        (root / "install.sh").write_text(installer_body)
    return root


def court_case(name: str, want: int, markers: tuple[str, ...], root_of) -> bool:
    def body(td: Path) -> None:
        got = run_court(root_of(td))
        said = got.stdout + got.stderr
        expect(
            got.returncode == want,
            f"want exit {want}, got {got.returncode}: {said.strip()[:400]}",
        )
        for marker in markers:
            expect(marker in said, f"want '{marker}' named, got: {said.strip()[:400]}")

    return case(name, body)


def main() -> int:
    if not INSTALLER.is_file():
        print(f"install_test: installer not found at {INSTALLER}", file=sys.stderr)
        return 2
    if not COURT.is_file():
        print(f"install_test: court not found at {COURT}", file=sys.stderr)
        return 2
    results = [
        case("refresh-resolves-latest-tag-0", refresh_resolves_latest_tag),
        case("refresh-explicit-tag-0", refresh_explicit_tag),
        case("refresh-unknown-tag-1", refresh_unknown_tag),
        case("bare-tree-refusal-1", bare_tree_refusal),
        case("no-tags-refusal-1", no_tags_refusal),
        case("no-rules-dir-1", no_rules_dir),
        case("tag-without-refresh-2", tag_without_refresh),
        court_case("court-clean-real-0", 0, (COURT_PASS, "consumer script"), lambda td: REPO),
        court_case(
            "court-clean-plant-0", 0, (COURT_PASS,),
            lambda td: plant(td, rev_swapped_installer('"$tag"')),
        ),
        court_case(
            "court-pre-fix-1", 1,
            (COURT_FAIL, "checkout tree", "CHANGELOG", "no tag resolution"),
            lambda td: plant(td, PRE_FIX_INSTALLER),
        ),
        court_case(
            "court-main-rev-1", 1, (COURT_FAIL, "non-tag rev"),
            lambda td: plant(td, rev_swapped_installer("main")),
        ),
        court_case(
            "court-head-rev-1", 1, (COURT_FAIL, "non-tag rev"),
            lambda td: plant(td, rev_swapped_installer("HEAD")),
        ),
        court_case("court-empty-corpus-2", 2, (COURT_VOID,), lambda td: plant(td, None)),
        court_case(
            "court-region-missing-2", 2, (COURT_VOID,),
            lambda td: plant(td, "#!/usr/bin/env bash\nset -euo pipefail\necho install only\n"),
        ),
    ]
    failed = results.count(False)
    print(f"install_test: {len(results) - failed}/{len(results)} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

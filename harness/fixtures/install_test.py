#!/usr/bin/env python3
"""Red-first fixture for `install.sh --refresh-rules` and `scripts/tag-consumption-check.sh`.

ADR-0002/D7: downstream consumption pins tags, never `main`. Before this story the refresh
path copied `claude-project/rules/*.md` from whatever tree the checkout held and scraped a
version out of the checkout's `CHANGELOG.md`, resolving no tag at all — so a bad merge on
`main` reached consumers on their next routine refresh, before any backstop could act. The
installer cases drive the real `install.sh` (copied into scratch kit repositories, since it
derives its kit root from its own location) and assert the refreshed content is the TAG's,
not HEAD's. The court cases drive D7's check, whose known-bad plant is the pre-fix refresh
region (pattern-bearing lines verbatim): the patterns are grounded in a defect that actually
shipped, not a guessed one.

  THE INSTALLER
  refresh-resolves-latest-tag-0  HEAD differs from every tag       -> 0, the newest release
                                                                      tag's content, its name
                                                                      reported, the CHANGELOG
                                                                      decoy version absent
  refresh-prerelease-not-latest-0  v2.0.0-rc1 and v2.0.0 both     -> 0, the final release's
                                   tagged                            content, never the rc's
  refresh-explicit-tag-0         --tag names an older release      -> 0, that tag's content
  refresh-unknown-tag-1          --tag names no tag                -> 1, named, nothing copied
  bare-tree-refusal-1            a kit tree with no .git           -> 1, named, nothing copied
  no-tags-refusal-1              a kit repo with no release tag    -> 1, named, nothing copied
  no-rules-in-tag-1              the resolved tag's tree holds no  -> 1, named, nothing copied
                                 claude-project/rules/*.md
  no-rules-dir-1                 a consumer with no .claude/rules  -> 1 (the refusal that
                                                                      predates this story)
  tag-without-refresh-2          --tag outside --refresh-rules     -> 2, usage
  dir-without-refresh-2          --dir outside --refresh-rules     -> 2, usage, and nothing
                                                                      written into the home
                                                                      directory
  user-stamp-working-tree-0      the no-argument install mode      -> 0, discipline/KIT-VERSION
                                                                      naming the kit path, the
                                                                      commit, the describe, the
                                                                      time, and saying WORKING
                                                                      TREE rather than a tag
  user-stamp-no-git-0            the same mode on a tarball tree   -> 0, a stamp that says the
                                                                      checkout carries no git
  rules-stamp-names-tag-0        a refresh                         -> 0, .claude/rules/.kit-version
                                                                      naming the resolved tag, its
                                                                      commit, the time; a dotfile
                                                                      no *.md glob picks up
  version-flag-0                 --version                         -> 0, path, commit, describe,
                                                                      newest tag, the flag list,
                                                                      the fetch caveat; no file
                                                                      created, nothing copied
  version-flag-no-tags-0         --version, tags never fetched     -> 0, the commit still named
                                                                      and the absent tag said
  guides-refresh-from-tag-0      a consumer that has a guides dir  -> 0, the TAG's guide body,
                                                                      both counts in the line
  guides-missing-reported-0      a consumer with no guides dir     -> 0, reported and NOT created
  local-edit-preserved-0         a kit rule the consumer edited    -> 0, copied aside to
                                                                      <name>.md.local-<stamp>
                                                                      and listed
  untouched-copy-not-preserved-0 a kit rule matching a tag's blob  -> 0, overwritten with NO
                                                                      backup (negative control)
  obsolete-rule-reported-0       a kit-named rule the tag dropped  -> 0, named, NOT deleted, and
                                                                      a consumer-authored name
                                                                      not mistaken for one
  working-tree-install-not-blamed-0  rules installed from the kit's -> 0, copied aside and reported
                                     WORKING TREE, edited by nobody    as matching no release, never
                                                                       asserted to be an edit
  abort-mid-copy-stamp-honest-1  a copy dies partway through       -> not 0, and the stamp says
                                                                      partial rather than naming
                                                                      the new tag as clean
  backup-never-clobbered-0       a backup name already taken       -> 0, the earlier preserved
                                                                      file survives untouched
  guide-local-edit-preserved-0   a kit guide the consumer edited    -> 0, copied aside and listed
  untouched-guide-not-preserved-0  a guide matching a tag's blob    -> 0, overwritten with NO
                                                                      backup (negative control)
  user-stamp-disposition-0       a home that already has CLAUDE.md -> 0, the stamp records
                                                                      kept-existing per piece,
                                                                      never a bare new commit
  version-with-refresh-2         --version with --refresh-rules     -> 2, refused, nothing copied
  missing-dir-refusal-1          --dir names no directory           -> 1, named, no raw cd error
  flag-without-value-2           --dir or --tag with no value       -> 2, named, not an unbound
                                                                      variable
  portable-shell-0               install.sh's own source            -> 0, no bash-4-only
                                                                      construct, and the floor
                                                                      it needs is named in it
  stale-tag-set-not-blamed-0     a consumer file matching a tag     -> 0, copied aside, but
                                 this checkout never fetched           reported against the tags
                                                                       READ, with their count
                                                                       and the fetch that would
                                                                       extend them
  unclassifiable-file-refused-1  a present file this run can        -> 1, named, nothing
                                 neither address nor read              copied, never git's raw
                                                                       fatal
  symlinked-rule-not-written-through-0  a rule symlinked to a file  -> 0, that file untouched,
                                        outside the repository         the link replaced by a
                                                                       real file, and said
  shipped-name-with-space-refused-1  the tag ships a name carrying  -> 1, named, nothing
                                     whitespace                        copied
  user-install-abort-stamp-honest-1  the user-level install dies    -> not 0, and its stamp
                                     partway                           says partial, with the
                                                                       pieces it reached
  version-with-dir-2             --version with --dir, '.' and any  -> 2, refused alike
                                 other directory

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
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "install.sh"
COURT = REPO / "scripts" / "tag-consumption-check.sh"

RULE_REL = Path("claude-project/rules/kit-rule.md")
V9_BODY = "rule body shipped in v0.9.0\n"
V10_BODY = "rule body shipped in v0.10.0\n"
RC_BODY = "rule body shipped in v2.0.0-rc1, a pre-release\n"
V2_BODY = "rule body shipped in v2.0.0, the final release\n"
HEAD_BODY = "rule body only HEAD holds, never tagged\n"
STALE_BODY = "stale rule body from an earlier refresh\n"
LOCAL_BODY = "authored by the consumer, not the kit's to overwrite\n"
EDITED_BODY = "a kit rule body the consumer edited in place\n"

# The guides ride the same release tag as the rules, so they need the same three bodies: one
# per tag and one only the working tree holds, which is what tells a tag refresh apart from a
# working-tree copy.
GUIDE_REL = Path("claude-project/sdlc-discipline/guides/kit-guide.md")
V9_GUIDE = "guide body shipped in v0.9.0\n"
V10_GUIDE = "guide body shipped in v0.10.0\n"
HEAD_GUIDE = "guide body only HEAD holds, never tagged\n"
STALE_GUIDE = "stale guide body from an earlier refresh\n"
EDITED_GUIDE = "a kit guide body the consumer edited in place\n"

# The body behind a rule that is a symlink out of the repository, and the newer skill body the
# user-level abort case installs. Both are sentinels: the point of each case is that these exact
# bytes are where the run left them.
SHARED_OUTSIDE = "a shared file outside the repository, not this refresh's to write\n"
NEW_SKILL_BODY = "a deep-reason SKILL.md body newer than the last install's\n"

# The name a second refresh in the same second would reuse. Backups are named from a per-RUN
# timestamp with one-second resolution, so the collision is real rather than theoretical.
SENTINEL_BACKUP = "a preserved copy an earlier refresh wrote\n"

# A rule v0.9.0 shipped and v0.10.0 dropped: the corpus for the obsolete-rule report, and the
# reason the kit trees carry two rule names rather than one.
RETIRED_REL = Path("claude-project/rules/retired-rule.md")
RETIRED_BODY = "a rule v0.9.0 shipped and v0.10.0 no longer does\n"

# The three rules the abort case needs, in the order the copy loop's glob walks them: two land
# before the poisoned third.
THREE_RULES = ("a-rule.md", "kit-rule.md", "zz-rule.md")

# The files the no-argument install mode copies by exact path. Stubs: nothing under test reads
# their contents, but every one must exist or the mode dies at its first cp.
USER_PAYLOAD = (
    "claude-user/skills/deep-reason/SKILL.md",
    "claude-user/skills/pr-review/SKILL.md",
    "claude-user/CLAUDE.md",
    "claude-user/settings.json",
    "reference/deep-reasoning-agent.md",
    "reference/sdlc-gate.py",
    "reference/review-checklist.md",
    "reference/voicing-document.md",
)

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


def kit_tree(td: Path, *, repo: bool = True, tags: bool = True,
             prerelease: bool = False, full: bool = False) -> Path:
    """A kit-shaped tree carrying the real installer.

    `repo=False` leaves no `.git` (the tarball-download shape); `tags=False` leaves a
    repository whose release tags were never fetched. With both true the tree carries two
    release tags whose rule bodies differ from each other and from HEAD's, plus a CHANGELOG
    claiming a version no tag names — the decoy the pre-fix scrape would have reported.
    `prerelease=True` adds v2.0.0-rc1 and v2.0.0 with distinct bodies: without a
    versionsort.suffix pin the rc tag sorts ABOVE its final release, so the pair
    discriminates the sort a plain refresh uses. `full=True` also plants the user-level
    payload, without which the no-argument install mode dies at its first cp and cannot be
    exercised at all. Every tree carries a guide beside the rule, and a `retired-rule.md`
    that v0.9.0 ships and v0.10.0 drops.
    """
    kit = td / "kit"
    (kit / RULE_REL).parent.mkdir(parents=True)
    (kit / GUIDE_REL).parent.mkdir(parents=True)
    shutil.copy(INSTALLER, kit / "install.sh")
    (kit / RULE_REL).write_text(V9_BODY)
    (kit / RETIRED_REL).write_text(RETIRED_BODY)
    (kit / GUIDE_REL).write_text(V9_GUIDE)
    if full:
        for rel in USER_PAYLOAD:
            f = kit / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("{}\n" if rel.endswith(".json") else f"stub for {rel}\n")
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
        (kit / GUIDE_REL).write_text(V10_GUIDE)
        (kit / RETIRED_REL).unlink()
        git(kit, "add", "-A")
        git(kit, "commit", "-qm", "v0.10.0 tree")
        git(kit, "tag", "v0.10.0")
    if tags and prerelease:
        (kit / RULE_REL).write_text(RC_BODY)
        git(kit, "add", "-A")
        git(kit, "commit", "-qm", "v2.0.0-rc1 tree")
        git(kit, "tag", "v2.0.0-rc1")
        (kit / RULE_REL).write_text(V2_BODY)
        git(kit, "add", "-A")
        git(kit, "commit", "-qm", "v2.0.0 tree")
        git(kit, "tag", "v2.0.0")
    (kit / RULE_REL).write_text(HEAD_BODY)
    (kit / GUIDE_REL).write_text(HEAD_GUIDE)
    (kit / "CHANGELOG.md").write_text("# Changelog\n\n## v9.9.9 (never tagged)\n")
    git(kit, "add", "-A")
    git(kit, "commit", "-qm", "untagged head")
    return kit


def three_rule_kit(td: Path) -> Path:
    """A kit shipping three rules, so a copy loop can die with some copies already done.

    `kit_tree` ships one rule, and a loop that dies on its only file proves nothing about a
    stamp written after the last copy: the measured defect is new bodies on disk UNDER a stamp
    naming the old tag, which needs at least one copy to succeed first.
    """
    kit = td / "kit"
    (kit / "claude-project" / "rules").mkdir(parents=True)
    shutil.copy(INSTALLER, kit / "install.sh")
    for release in ("v0.9.0", "v0.10.0"):
        for n in THREE_RULES:
            (kit / "claude-project" / "rules" / n).write_text(f"{n} body {release}\n")
        if release == "v0.9.0":
            git(kit, "init", "-q", "-b", "main", ".")
            git(kit, "config", "user.email", "fixture@example.invalid")
            git(kit, "config", "user.name", "fixture")
        git(kit, "add", "-A")
        git(kit, "commit", "-qm", f"{release} tree")
        git(kit, "tag", release)
    return kit


def consumer_tree(td: Path) -> Path:
    consumer = td / "consumer"
    rules = consumer / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "kit-rule.md").write_text(STALE_BODY)
    (rules / "local-rule.md").write_text(LOCAL_BODY)
    return consumer


def consumer_with_guides(td: Path) -> Path:
    """A consumer that took the guides at install time, as the per-project lines instruct."""
    consumer = consumer_tree(td)
    guides = consumer / ".claude" / "sdlc-discipline" / "guides"
    guides.mkdir(parents=True)
    (guides / "kit-guide.md").write_text(STALE_GUIDE)
    return consumer


def run_install(kit: Path, home: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """The no-argument install mode, pinned to a scratch install directory.

    BOTH variables are set, and the second is the point: CLAUDE_HOME is what the installer
    reads, and HOME is set to the same scratch directory so that a fixture is never one
    dropped or renamed variable away from writing into the operator's real ~/.claude. An
    earlier run of an installer without CLAUDE_HOME set did exactly that damage.
    """
    env = clean_env()
    env["CLAUDE_HOME"] = str(home)
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(kit / "install.sh"), *extra],
        capture_output=True, text=True, env=env,
    )


def stamp_fields(body: str) -> dict[str, str]:
    """A stamp's `key: value` lines, comments dropped.

    The header explains the vocabulary the fields use, so a substring test over the whole file
    answers "the word appears" rather than "this piece says it" - which is a different
    question, and the one worth asserting.
    """
    out: dict[str, str] = {}
    for line in body.splitlines():
        if line.startswith("#") or ": " not in line:
            continue
        key, value = line.split(": ", 1)
        out[key] = value
    return out


def expect_currency_instructions(body: str, what: str, compare_key: str) -> None:
    """A stamp's header promises the reader a way to answer "am I current"; keep that promise.

    Both stamps tell the reader to run the kit's own `install.sh --version` and compare a
    named field. That instruction is only followable if the stamp records WHERE the kit is and
    records the field it names, so this asserts the header's promise against the stamp's own
    body rather than trusting the prose.
    """
    expect("--version" in body, f"{what} does not name install.sh --version: {body!r}")
    expect(
        re.search(r"^kit_path: \S", body, re.M) is not None,
        f"{what} tells the reader to run the kit's install.sh --version but records no "
        f"kit_path to run it from: {body!r}",
    )
    expect(
        re.search(rf"^{compare_key}: \S", body, re.M) is not None,
        f"{what} names {compare_key} as the field to compare but does not record it: {body!r}",
    )


def stamp_text(path: Path, what: str) -> str:
    """Read a stamp, or fail the case by name rather than raising out of it."""
    if not path.is_file():
        raise Failure(f"no {what} written at {path}")
    return path.read_text()


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


def refresh_prerelease_not_latest(td: Path) -> None:
    kit, consumer = kit_tree(td, prerelease=True), consumer_tree(td)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:300]}")
    refreshed = (consumer / ".claude" / "rules" / "kit-rule.md").read_text()
    expect(
        refreshed == V2_BODY,
        f"want the final release's rule body, got {refreshed!r} "
        "(the rc body means the pre-release outranked its release in the sort)",
    )
    expect(
        "v2.0.0-rc1" not in said,
        f"the pre-release tag must not be the one reported, got: {said.strip()[:300]}",
    )
    expect("v2.0.0" in said, f"the resolved tag must be reported, got: {said.strip()[:300]}")


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


def no_rules_in_tag(td: Path) -> None:
    """The resolved tag's tree carries claude-project/rules with no markdown in it.

    The verdict was already fail-closed (the copy had nothing to expand and died), but the
    voice was cp's raw `cannot stat` rather than a refusal naming the tag — this case pins
    the named message alongside the untouched consumer.
    """
    kit = td / "kit"
    rules = kit / "claude-project" / "rules"
    rules.mkdir(parents=True)
    shutil.copy(INSTALLER, kit / "install.sh")
    (rules / "notes.txt").write_text("no markdown rules in this tree\n")
    git(kit, "init", "-q", "-b", "main", ".")
    git(kit, "config", "user.email", "fixture@example.invalid")
    git(kit, "config", "user.name", "fixture")
    git(kit, "add", "-A")
    git(kit, "commit", "-qm", "rules dir without markdown")
    git(kit, "tag", "v0.1.0")
    consumer = consumer_tree(td)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 1, f"want exit 1, got {got.returncode}: {said.strip()[:300]}")
    expect(
        "carries no rules" in said,
        f"the empty tag must be refused by name, got: {said.strip()[:300]}",
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


def user_stamp_records_working_tree(td: Path) -> None:
    """The user-level pieces come from the WORKING TREE, and the stamp must say so.

    Nothing the installer placed recorded a version at all, so a session could not tell a
    current install from a year-old one. The stamp must not claim a release tag either: this
    mode copies whatever the checkout holds, tag or no tag.
    """
    kit = kit_tree(td, full=True)
    home = td / "home"
    got = run_install(kit, home)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    body = stamp_text(home / "discipline" / "KIT-VERSION", "user-level stamp")
    commit = git(kit, "log", "-1", "--format=%H")
    described = git(kit, "describe", "--tags", "--always", "--dirty")
    for want in (str(kit), commit, described):
        expect(want in body, f"the stamp omits {want!r}: {body!r}")
    expect(
        "working tree" in body.lower(),
        f"the stamp must say these pieces come from the checkout's working tree: {body!r}",
    )
    expect(
        re.search(r"20\d\d-\d\d-\d\d", body) is not None,
        f"the stamp carries no install time: {body!r}",
    )
    expect(
        commit in said and described in said,
        f"the run must print the stamp's key facts, got: {said.strip()[:400]}",
    )
    expect_currency_instructions(body, "the user-level stamp", "kit_commit")
    expect(
        "nearest ancestor" in body,
        "the stamp must say what git describe is (the nearest ancestor tag plus a distance), "
        f"so its tag is not read as the release these files are: {body!r}",
    )


def user_stamp_without_git(td: Path) -> None:
    """A kit unpacked from a tarball still installs, and the stamp says why it names no commit.

    The stamp reads git four ways; under `set -e` any one of them failing would abort an
    install that has already copied half its files.
    """
    kit = kit_tree(td, repo=False, full=True)
    home = td / "home"
    got = run_install(kit, home)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    body = stamp_text(home / "discipline" / "KIT-VERSION", "user-level stamp")
    expect(
        "not a git checkout" in body,
        f"the stamp must say the checkout carries no git metadata: {body!r}",
    )


def rules_stamp_names_tag(td: Path) -> None:
    kit, consumer = kit_tree(td), consumer_tree(td)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    rules = consumer / ".claude" / "rules"
    stampfile = rules / ".kit-version"
    body = stamp_text(stampfile, "rules stamp")
    expect("v0.10.0" in body, f"the stamp does not name the resolved tag: {body!r}")
    tag_commit = git(kit, "rev-list", "-n", "1", "v0.10.0")
    expect(tag_commit in body, f"the stamp omits the tag's commit {tag_commit}: {body!r}")
    expect(
        re.search(r"20\d\d-\d\d-\d\d", body) is not None,
        f"the stamp carries no refresh time: {body!r}",
    )
    expect(
        stampfile.name.startswith(".") and not stampfile.name.endswith(".md"),
        f"the stamp must be a dotfile with no .md suffix, got {stampfile.name!r}",
    )
    expect(
        not [q for q in rules.glob("*.md") if q.name.startswith(".kit-version")],
        "the stamp must not be reachable by the *.md glob a rule loader uses",
    )
    expect(
        "state: complete" in body,
        f"a finished refresh must stamp itself complete, so a partial one is tellable: {body!r}",
    )
    expect_currency_instructions(body, "the rules stamp", "tag")


def version_flag_reports_and_writes_nothing(td: Path) -> None:
    kit = kit_tree(td, full=True)
    home = td / "home"
    before = git(kit, "status", "--porcelain")
    got = run_install(kit, home, "--version")
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    commit = git(kit, "log", "-1", "--format=%H")
    described = git(kit, "describe", "--tags", "--always", "--dirty")
    for want in (str(kit), commit, described, "v0.10.0",
                 "--refresh-rules", "--dir", "--tag", "--version"):
        expect(want in said, f"--version omits {want!r}, got: {said.strip()[:600]}")
    expect(
        "fetch" in said,
        f"--version must say that tags arrive by fetch, so a stale checkout reads as "
        f"current: {said.strip()[:600]}",
    )
    expect(
        not home.exists(),
        "--version must create no file, but it created the install dir",
    )
    # The claim is "creates no file, copies nothing", not "touches no byte on disk":
    # `git describe --dirty` refreshes the checkout's git index, as any status-like read does.
    # Measured: the index file's bytes change. What must not change is the tracked content.
    expect(
        git(kit, "status", "--porcelain") == before,
        "--version modified the kit checkout",
    )


def version_flag_without_tags(td: Path) -> None:
    """The checkout the audit found: cloned or pulled in a way that fetched no tags."""
    kit = kit_tree(td, tags=False, full=True)
    home = td / "home"
    got = run_install(kit, home, "--version")
    said = got.stdout + got.stderr
    expect(
        got.returncode == 0,
        f"want exit 0 in a checkout with no tags, got {got.returncode}: {said.strip()[:400]}",
    )
    expect("no release tag" in said, f"the absent tag must be said, got: {said.strip()[:600]}")
    commit = git(kit, "log", "-1", "--format=%H")
    expect(commit in said, f"the commit must still be named, got: {said.strip()[:600]}")
    expect(
        not home.exists(),
        "--version must create no file, but it created the install dir",
    )


def guides_refresh_from_tag(td: Path) -> None:
    kit = kit_tree(td)
    consumer = consumer_with_guides(td)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    guide = consumer / ".claude" / "sdlc-discipline" / "guides" / "kit-guide.md"
    body = stamp_text(guide, "refreshed guide")
    expect(
        body == V10_GUIDE,
        f"want the tag's guide body, got {body!r} (HEAD's body means the working tree was "
        "copied; the stale body means the guides never moved)",
    )
    expect(
        "1 rule file" in said and "1 guide file" in said,
        f"the success line must count what moved, each separately, got: {said.strip()[:400]}",
    )
    saved = sorted(q.name for q in guide.parent.glob("kit-guide.md.local-*"))
    expect(
        len(saved) == 1,
        f"the guide here matches no release, so it must be copied aside like a rule, found "
        f"{saved}",
    )


def guides_missing_is_reported(td: Path) -> None:
    kit, consumer = kit_tree(td), consumer_tree(td)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    expect(
        "sdlc-discipline/guides" in said,
        f"a consumer with no guides directory must be told it was skipped, got: "
        f"{said.strip()[:400]}",
    )
    expect(
        not (consumer / ".claude" / "sdlc-discipline").exists(),
        "a missing guides directory must be reported, never created silently",
    )
    expect(
        (consumer / ".claude" / "rules" / "kit-rule.md").read_text() == V10_BODY,
        "the rules must still refresh when the guides are skipped",
    )


def local_edit_preserved(td: Path) -> None:
    kit = kit_tree(td)
    consumer = consumer_tree(td)
    rules = consumer / ".claude" / "rules"
    (rules / "kit-rule.md").write_text(EDITED_BODY)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    saved = sorted(rules.glob("kit-rule.md.local-*"))
    expect(
        len(saved) == 1,
        f"the consumer's edit must be copied aside before the overwrite, found "
        f"{[q.name for q in saved]}",
    )
    expect(
        saved[0].read_text() == EDITED_BODY,
        "the preserved copy does not hold what the consumer wrote",
    )
    expect(
        (rules / "kit-rule.md").read_text() == V10_BODY,
        "the tag's rule must still land after the backup",
    )
    expect(saved[0].name in said, f"what was preserved must be listed, got: {said.strip()[:400]}")
    # install.sh states the backup must not end in .md so no rule loader picks it up. Stated in
    # a comment and asserted nowhere, that is a promise, not a property.
    expect(
        not saved[0].name.endswith(".md"),
        f"a backup must not end in .md, or the rule loader's *.md glob picks it up: "
        f"{saved[0].name}",
    )
    expect(
        "locally modified" not in said,
        "the report must not assert a cause the code has not established: a file matching no "
        f"release may be an edit OR a working-tree install. Got: {said.strip()[:400]}",
    )
    expect(
        "match no release tag" in said,
        "the report must say what is actually true of the file: that it matches no release TAG "
        f"this checkout holds, which is the set the test read. Got: {said.strip()[:400]}",
    )


def untouched_copy_not_preserved(td: Path) -> None:
    """A negative control, green before this story and after it.

    Its body is v0.9.0's blob exactly, so a content test classifies it as a copy the kit
    shipped and overwriting it loses nothing. Without this case, a script that backed up
    EVERY rule would pass local-edit-preserved-0 while filling the directory with junk.
    """
    kit = kit_tree(td)
    consumer = consumer_tree(td)
    rules = consumer / ".claude" / "rules"
    (rules / "kit-rule.md").write_text(V9_BODY)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    saved = sorted(q.name for q in rules.glob("*.local-*"))
    expect(not saved, f"an untouched kit copy must not be backed up, but found {saved}")
    expect(
        (rules / "kit-rule.md").read_text() == V10_BODY,
        "the tag's rule must land over an untouched copy",
    )


def obsolete_rule_reported_not_deleted(td: Path) -> None:
    kit = kit_tree(td)
    consumer = consumer_tree(td)
    rules = consumer / ".claude" / "rules"
    (rules / "retired-rule.md").write_text(RETIRED_BODY)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    expect(
        "retired-rule.md" in said,
        f"a kit-named rule the resolved tag no longer ships must be reported, got: "
        f"{said.strip()[:400]}",
    )
    expect(
        (rules / "retired-rule.md").read_text() == RETIRED_BODY,
        "the obsolete rule must be reported, never deleted",
    )
    expect(
        "local-rule.md" not in said,
        "a consumer-authored name the kit never shipped must not be reported as obsolete",
    )


def working_tree_install_not_blamed(td: Path) -> None:
    """A consumer who edited nothing, whose rules came from the kit's WORKING TREE.

    The kit's own per-project setup says to copy `claude-project/rules/*.md` out of the
    checkout, so those files match a release only if the checkout sat exactly on one. The
    classifier reads content and can therefore see only "this matches no release" - it cannot
    see WHO wrote it. Measured before this case: the run reported the kit's own install as
    "locally modified rule(s)", a cause the code never established.
    """
    kit, consumer = kit_tree(td), consumer_tree(td)
    rules = consumer / ".claude" / "rules"
    (rules / "kit-rule.md").write_text(HEAD_BODY)  # the working tree's body, never tagged
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:300]}")
    expect(
        len(list(rules.glob("kit-rule.md.local-*"))) == 1,
        "the safe direction is still to keep a copy, whatever wrote the file",
    )
    expect(
        "locally modified" not in said,
        f"the run must not call the kit's own install an edit, got: {said.strip()[:600]}",
    )
    expect(
        "working tree" in said.lower(),
        f"the run must name the other explanation for a file matching no release, got: "
        f"{said.strip()[:600]}",
    )
    expect(
        "cannot tell" in said.lower(),
        f"the run must say it cannot tell the two apart, got: {said.strip()[:600]}",
    )
    expect(
        ".kit-version" in said,
        "with no prior stamp the run must say so, since the stamp is what would have told "
        f"the two apart: {said.strip()[:600]}",
    )


def abort_mid_copy_stamp_honest(td: Path) -> None:
    """A refresh that dies partway must not leave a stamp naming a tag as cleanly installed.

    The abort is a DIRECTORY where the last rule's file belongs: the backup step copies the
    destination before overwriting it, and `cp` without `-r` refuses a directory, for any user
    and on every platform, so the case depends on neither file modes nor a non-root run. It was
    a dangling symlink until the refresh started replacing symlinked destinations rather than
    writing through them, which made that plant succeed. Measured before this case: two of three
    rules carried the new tag's body while the stamp still read the previous tag.

    THE ASSERTIONS ARE THE EXIT TRAP'S OWN OUTPUT. The stamp is written twice on this path,
    `in-progress` before the first copy and `partial` by the trap, and the earlier version of
    this case accepted either word: deleting the trap left the suite green (measured, mutant
    `no-exit-trap`: exit 1, stamp `state: in-progress, rules_copied: 0`, 36/36 passing). The
    state and the counts together are what only the trap can have written, since the pre-copy
    write happens when nothing has been copied.
    """
    kit = three_rule_kit(td)
    consumer = td / "consumer"
    rules = consumer / ".claude" / "rules"
    rules.mkdir(parents=True)
    for n in ("a-rule.md", "kit-rule.md"):
        (rules / n).write_text(f"{n} body v0.9.0\n")
    (rules / "zz-rule.md").mkdir()
    (rules / ".kit-version").write_text("state: complete\ntag: v0.9.0\ntag_commit: dead\n")
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode != 0, f"a refresh that could not copy must not exit 0: {said[:300]}")
    expect(
        (rules / "a-rule.md").read_text().endswith("v0.10.0\n"),
        "the case is only meaningful if a copy landed before the abort",
    )
    body = stamp_text(rules / ".kit-version", "rules stamp")
    fields = stamp_fields(body)
    expect(
        fields.get("state") == "partial",
        f"the stamp must carry the exit trap's own state, not the pre-copy write's: {body!r}",
    )
    expect(
        fields.get("rules_copied") == "2",
        "the stamp must carry the counts as they stood when the run died, which the pre-copy "
        f"write cannot produce (it runs at 0 copied): {body!r}",
    )
    expect(
        fields.get("guides_copied") == "0" and fields.get("files_copied_aside") == "0",
        f"the stamp's other counts must be the ones this run reached: {body!r}",
    )
    expect("v0.10.0" in body, f"the stamp must name the tag being installed: {body!r}")


def backup_never_clobbered(td: Path) -> None:
    """A backup must never overwrite another backup.

    The backup name carries a per-RUN timestamp with one-second resolution, so two refreshes
    in the same second reused one name and the second copy destroyed the first preserved file.
    Rather than race two runs, this plants the names a run in this second (or the next few)
    would choose, and asserts every planted file survives with its content.
    """
    kit, consumer = kit_tree(td), consumer_tree(td)
    rules = consumer / ".claude" / "rules"
    (rules / "kit-rule.md").write_text(EDITED_BODY)
    now = time.time()
    planted = {}
    for k in range(6):  # this second and the next five, so a slow run still collides
        name = "kit-rule.md.local-" + time.strftime("%Y%m%d-%H%M%S", time.localtime(now + k))
        text = f"{SENTINEL_BACKUP}{name}\n"
        (rules / name).write_text(text)
        planted[name] = text
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:300]}")
    for name, text in planted.items():
        here = rules / name
        expect(here.is_file(), f"a planted backup vanished: {name}")
        expect(
            here.read_text() == text,
            f"a refresh overwrote an earlier preserved copy at {name}: "
            f"{here.read_text()!r}",
        )
    kept = [q for q in rules.glob("kit-rule.md.local-*") if q.name not in planted]
    expect(
        len(kept) == 1 and kept[0].read_text() == EDITED_BODY,
        f"this run's own backup must land under a free name, found "
        f"{[q.name for q in kept]}",
    )
    expect(
        not kept[0].name.endswith(".md"),
        f"a numbered backup must still not end in .md: {kept[0].name}",
    )


def guide_local_edit_preserved(td: Path) -> None:
    """Guides are refreshed wholesale too, so they need the same protection rules get."""
    kit = kit_tree(td)
    consumer = consumer_with_guides(td)
    guides = consumer / ".claude" / "sdlc-discipline" / "guides"
    (guides / "kit-guide.md").write_text(EDITED_GUIDE)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    saved = sorted(guides.glob("kit-guide.md.local-*"))
    expect(
        len(saved) == 1,
        f"the consumer's guide edit must be copied aside before the overwrite, found "
        f"{[q.name for q in saved]}",
    )
    expect(
        saved[0].read_text() == EDITED_GUIDE,
        "the preserved guide does not hold what the consumer wrote",
    )
    expect(
        (guides / "kit-guide.md").read_text() == V10_GUIDE,
        "the tag's guide must still land after the backup",
    )
    expect(
        saved[0].name in said,
        f"what was preserved must be listed, got: {said.strip()[:400]}",
    )


def untouched_guide_not_preserved(td: Path) -> None:
    """A negative control for the guides half: a shipped copy is overwritten with no backup."""
    kit = kit_tree(td)
    consumer = consumer_with_guides(td)
    guides = consumer / ".claude" / "sdlc-discipline" / "guides"
    (guides / "kit-guide.md").write_text(V9_GUIDE)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    saved = sorted(q.name for q in guides.glob("*.local-*"))
    expect(not saved, f"an untouched kit guide must not be backed up, but found {saved}")
    expect(
        (guides / "kit-guide.md").read_text() == V10_GUIDE,
        "the tag's guide must land over an untouched copy",
    )


def user_stamp_records_disposition(td: Path) -> None:
    """The stamp must not read current for a file the run deliberately did not write.

    CLAUDE.md and settings.json are never clobbered, so after an upgrade they hold the
    PREVIOUS release's text while the stamp records the new commit. A reader comparing
    kit_commit gets "current" for a machine that is half old.
    """
    kit = kit_tree(td, full=True)
    fresh = td / "fresh-home"
    got = run_install(kit, fresh)
    expect(got.returncode == 0, f"fresh install failed: {(got.stdout + got.stderr)[:400]}")
    fields = stamp_fields(stamp_text(fresh / "discipline" / "KIT-VERSION", "user-level stamp"))
    for piece in ("CLAUDE.md", "settings.json"):
        expect(piece in fields, f"the stamp records no disposition for {piece}: {fields}")
        expect(
            fields[piece].startswith("installed"),
            f"a fresh install wrote {piece}, so its disposition must say installed: {fields}",
        )

    held = td / "held-home"
    held.mkdir()
    (held / "CLAUDE.md").write_text("the previous release's user CLAUDE.md\n")
    (held / "settings.json").write_text('{"from": "the previous release"}\n')
    got = run_install(kit, held)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    body = stamp_text(held / "discipline" / "KIT-VERSION", "user-level stamp")
    fields = stamp_fields(body)
    for piece in ("CLAUDE.md", "settings.json"):
        expect(piece in fields, f"the stamp records no disposition for {piece}: {fields}")
        expect(
            fields[piece].startswith("kept-existing"),
            f"{piece} was left alone holding the previous release's text, so the stamp must "
            f"say kept-existing rather than let kit_commit stand for it: {fields}",
        )
    expect(
        (held / "CLAUDE.md").read_text().startswith("the previous release"),
        "the guarded files must still not be overwritten",
    )
    backups = sorted(q.name for q in held.glob("CLAUDE.md.bak-*"))
    expect(len(backups) == 1, f"want one CLAUDE.md backup, found {backups}")
    expect(
        backups[0] in fields["CLAUDE.md"],
        f"the stamp must name where the kept file was copied to: {fields['CLAUDE.md']!r}",
    )


def version_with_refresh_refused(td: Path) -> None:
    """--version asks a question; --refresh-rules acts. Together they used to exit 0 having
    printed a version and refreshed nothing, which reads as a successful refresh in a log."""
    kit, consumer = kit_tree(td, full=True), consumer_tree(td)
    got = subprocess.run(
        ["bash", str(kit / "install.sh"), "--version", "--refresh-rules",
         "--dir", str(consumer)],
        capture_output=True, text=True, env=clean_env(),
    )
    said = got.stdout + got.stderr
    expect(got.returncode == 2, f"want usage exit 2, got {got.returncode}: {said[:400]}")
    expect(
        "--version" in said and "--refresh-rules" in said,
        f"the refusal must name the combination it refuses, got: {said.strip()[:400]}",
    )
    unchanged(consumer)


def missing_dir_refusal(td: Path) -> None:
    """--dir naming no directory died on the shell's own `cd:` line, which names a line
    number rather than the mistake."""
    kit = kit_tree(td)
    absent = td / "no-such-repo"
    got = subprocess.run(
        ["bash", str(kit / "install.sh"), "--refresh-rules", "--dir", str(absent)],
        capture_output=True, text=True, env=clean_env(),
    )
    said = got.stdout + got.stderr
    expect(got.returncode == 1, f"want exit 1, got {got.returncode}: {said.strip()[:300]}")
    expect(str(absent) in said, f"the refusal must name the directory: {said.strip()[:300]}")
    expect(
        "no such directory" in said.lower(),
        f"want a named refusal, got: {said.strip()[:300]}",
    )
    expect(
        "cd:" not in said,
        f"the raw shell error must not be the whole message: {said.strip()[:300]}",
    )


def flag_without_value(td: Path) -> None:
    """A flag with no value died on `$2: unbound variable` under set -u."""
    kit = kit_tree(td)
    for flag in ("--dir", "--tag"):
        got = subprocess.run(
            ["bash", str(kit / "install.sh"), "--refresh-rules", flag],
            capture_output=True, text=True, env=clean_env(),
        )
        said = got.stdout + got.stderr
        expect(
            got.returncode == 2,
            f"{flag} with no value: want usage exit 2, got {got.returncode}: "
            f"{said.strip()[:300]}",
        )
        expect(
            "needs a value" in said and flag in said,
            f"{flag} with no value must be named, got: {said.strip()[:300]}",
        )
        expect(
            "unbound variable" not in said,
            f"{flag} with no value still dies on the shell's own error: {said.strip()[:300]}",
        )


def portable_shell(td: Path) -> None:
    """The installer is the one script whose job is landing on someone else's machine.

    Associative arrays and mapfile are bash 4.0; macOS ships bash 3.2. This asserts the
    constructs are absent and that the floor the script needs is named IN the script, because
    a floor stated in a comment and enforced nowhere is the failure this kit is built against.
    No bash 3.2 exists on this machine to run against, so this is a construct check, not a
    measurement on that shell, and it says so rather than implying more.

    EXECUTED LINES ONLY. The comment that explains why the constructs are gone has to name
    them, and a comment naming a construct must not read as the construct being present -
    the same reason `scripts/tag-consumption-check.sh` judges executed lines.
    """
    body = "\n".join(
        ln for ln in INSTALLER.read_text().splitlines() if not ln.lstrip().startswith("#")
    )
    for construct in ("declare -A", "mapfile", "readarray"):
        expect(
            construct not in body,
            f"install.sh uses {construct!r}, which needs bash 4.0; macOS ships bash 3.2",
        )
    expect(
        "BASH_VERSINFO" in body and "3.2" in body,
        "install.sh must name the bash version it needs and check it, so an older shell "
        "fails with a sentence rather than a syntax error",
    )


def dir_without_refresh(td: Path) -> None:
    """`--dir <repo>` without `--refresh-rules` installed into the HOME directory, exit 0.

    `--tag` outside `--refresh-rules` has been refused since v2.0.0; `--dir` was the one left,
    and the README's Upgrade prompt teaches the `--dir` form, so one dropped word turned a
    repository refresh into a home-directory install that logs as success. Measured before this
    case: exit 0, nine files into the home directory, none into the named repository.
    """
    kit = kit_tree(td, full=True)
    consumer = consumer_tree(td)
    home = td / "home"
    got = run_install(kit, home, "--dir", str(consumer))
    said = got.stdout + got.stderr
    expect(got.returncode == 2, f"want usage exit 2, got {got.returncode}: {said.strip()[:400]}")
    expect(
        "--dir" in said and "--refresh-rules" in said,
        f"the refusal must name the flag and the mode it belongs to, got: {said.strip()[:400]}",
    )
    expect(
        not home.exists(),
        "a refused run must install nothing, but it wrote the user-level install directory",
    )
    unchanged(consumer)


def version_with_dir_refused(td: Path) -> None:
    """`--version --dir .` exited 0 while `--version --dir <elsewhere>` exited 2.

    The guard compared the target to its default rather than tracking whether the flag was
    given, so one rule had two answers. THE SAME REFUSAL, not merely the same exit code, is what
    this asserts: with the guard comparing values again, `--version --dir .` still exits 2, but
    it exits through the flag-needs-refresh-rules guard and says something else entirely, so an
    exit-code-only case leaves that mutation alive (measured).
    """
    kit = kit_tree(td, full=True)
    home = td / "home"
    for where in (".", str(td)):
        got = run_install(kit, home, "--version", "--dir", where)
        said = got.stdout + got.stderr
        expect(
            got.returncode == 2,
            f"--version --dir {where}: want exit 2, got {got.returncode}: {said.strip()[:300]}",
        )
        expect(
            "cannot be combined" in said,
            f"--version --dir {where}: want the refusal --version gives every other flag, got: "
            f"{said.strip()[:300]}",
        )
        expect("--dir" in said, f"the refusal must name --dir, got: {said.strip()[:300]}")
        expect(not home.exists(), "a refused run must install nothing")


def stale_tag_set_not_blamed(td: Path) -> None:
    """The report may claim only what the run read: the tags THIS CHECKOUT has.

    The classifier tests a file's bytes against the `v*` tags the kit checkout holds, and tags
    arrive by fetch, so "matches no release the kit ever shipped" asserted more than the test
    performed. Here the consumer's rule is v0.10.0's blob exactly and the kit clone was never
    told about v0.10.0: the file matches a release the kit really published. The backup is still
    the safe direction, but the run must name the tag set it read, the fetch that would extend
    it, and the stale set as a third cause beside the edit and the working-tree install.
    """
    kit, consumer = kit_tree(td), consumer_tree(td)
    git(kit, "tag", "-d", "v0.10.0")  # published upstream, never fetched here
    rules = consumer / ".claude" / "rules"
    (rules / "kit-rule.md").write_text(V10_BODY)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    expect(
        len(list(rules.glob("kit-rule.md.local-*"))) == 1,
        "keeping a copy is still the safe direction for a file this run cannot place",
    )
    expect(
        "ever shipped" not in said,
        "the run reads the tags this checkout has, so it must not claim to know every release "
        f"the kit ever shipped. Got: {said.strip()[:700]}",
    )
    expect(
        "1 release tag(s)" in said,
        "the run must say how many release tags it read, since that count IS the claim it is "
        f"entitled to make. Got: {said.strip()[:700]}",
    )
    expect(
        "fetch --tags" in said,
        f"the run must point at the fetch that would extend that set, got: {said.strip()[:700]}",
    )
    expect(
        "working tree" in said.lower() and "cannot tell" in said.lower(),
        f"the other two causes must still be named, got: {said.strip()[:700]}",
    )


def unclassifiable_file_refused(td: Path) -> None:
    """A file the classifier can neither address nor read stops the run, by name.

    The classification comment promised that anything unreadable or unhashable fell to the
    copy-aside side. No such fallback existed: the batched `git hash-object --stdin-paths` died
    on the first such file and the run ended in git's own fatal (measured: exit 128, "could not
    open ... Permission denied", nothing copied and no backup). The promise was also not
    keepable, since a file this script cannot read it cannot copy aside either, so the sentence
    is gone and each case is refused by name instead.

    The newline half runs everywhere: `--stdin-paths` reads one path per line, so a name
    carrying a newline addresses a file that does not exist whatever the file modes are, and it
    exercises the same refusal branch as the permission half. The permission half is skipped for
    root alone, which can read a mode-000 file, and the case still measures the branch through
    the half that always runs.
    """
    kit = kit_tree(td)
    consumer = consumer_tree(td)
    rules = consumer / ".claude" / "rules"
    odd = rules / "two\nlines.md"
    odd.write_text("a consumer file whose name carries a newline\n")
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 1, f"want exit 1, got {got.returncode}: {said.strip()[:300]}")
    expect(
        "cannot classify" in said and "newline" in said,
        f"the refusal must name the file and why it cannot be classified: {said.strip()[:300]}",
    )
    expect("fatal:" not in said, f"the run must not end in git's raw error: {said.strip()[:300]}")
    unchanged(consumer)
    odd.unlink()
    if os.geteuid() == 0:
        return
    (rules / "kit-rule.md").chmod(0o000)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    (rules / "kit-rule.md").chmod(0o644)
    expect(got.returncode == 1, f"want exit 1, got {got.returncode}: {said.strip()[:300]}")
    expect(
        "cannot read" in said and "kit-rule.md" in said,
        f"the refusal must name the file it could not read: {said.strip()[:300]}",
    )
    expect("fatal:" not in said, f"the run must not end in git's raw error: {said.strip()[:300]}")
    expect(
        not list(rules.glob("*.local-*")),
        "a refused run must copy nothing aside, since a file it cannot read it cannot back up",
    )
    unchanged(consumer)


def symlinked_rule_not_written_through(td: Path) -> None:
    """A rule that is a symlink out of the repository must not carry the tag's body out with it.

    `cp` follows a symlink, so the refresh wrote the release's rule body onto a file outside the
    repository it was pointed at, left the link in place to do it again, and said nothing.
    Measured before this case: the outside file held v0.10.0's body afterwards.
    """
    kit = kit_tree(td)
    consumer = consumer_tree(td)
    rules = consumer / ".claude" / "rules"
    outside = td / "outside"
    outside.mkdir()
    shared = outside / "kit-rule.md"
    shared.write_text(SHARED_OUTSIDE)
    (rules / "kit-rule.md").unlink()
    (rules / "kit-rule.md").symlink_to(shared)
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 0, f"want exit 0, got {got.returncode}: {said.strip()[:400]}")
    expect(
        shared.read_text() == SHARED_OUTSIDE,
        "the refresh wrote through the link, so the tag's body landed outside the repository it "
        f"was pointed at: {shared.read_text()!r}",
    )
    expect(
        not (rules / "kit-rule.md").is_symlink(),
        "the link must be replaced by a real file, or the next refresh writes outside again",
    )
    expect(
        (rules / "kit-rule.md").read_text() == V10_BODY,
        "the tag's rule must land inside the repository",
    )
    saved = sorted(rules.glob("kit-rule.md.local-*"))
    expect(
        len(saved) == 1 and saved[0].read_text() == SHARED_OUTSIDE,
        f"what the link pointed at must be preserved first, found "
        f"{[q.name for q in saved]}",
    )
    expect(
        "symlink" in said,
        f"replacing a link is a change to the repository's shape, so the run must say it "
        f"happened: {said.strip()[:400]}",
    )


def shipped_name_with_space_refused(td: Path) -> None:
    """A shipped name carrying whitespace can never match its own blob.

    The lookup files are whitespace-delimited, one key and one blob per line, so such a rule is
    classified as matching no release on every run and copied aside forever. Measured before
    this case, on a kit shipping "my rule.md" and a byte-identical consumer: three refreshes,
    three backups, each run reporting the file as matching no release. The kit ships no such
    name today; this refuses the day it does, rather than growing a consumer's directory.
    """
    kit = td / "kit"
    (kit / "claude-project" / "rules").mkdir(parents=True)
    shutil.copy(INSTALLER, kit / "install.sh")
    shipped = "a rule whose shipped name carries a space\n"
    (kit / "claude-project" / "rules" / "my rule.md").write_text(shipped)
    git(kit, "init", "-q", "-b", "main", ".")
    git(kit, "config", "user.email", "fixture@example.invalid")
    git(kit, "config", "user.name", "fixture")
    git(kit, "add", "-A")
    git(kit, "commit", "-qm", "v1.0.0 tree")
    git(kit, "tag", "v1.0.0")
    consumer = td / "consumer"
    rules = consumer / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "my rule.md").write_text(shipped)  # byte-identical to the tag's blob
    got = run_installer(kit, consumer)
    said = got.stdout + got.stderr
    expect(got.returncode == 1, f"want exit 1, got {got.returncode}: {said.strip()[:400]}")
    expect(
        "my rule.md" in said and "whitespace" in said,
        f"the refusal must name the shipped file and why: {said.strip()[:400]}",
    )
    expect(
        not list(rules.glob("*.local-*")),
        "a byte-identical file must not be copied aside, least of all by a refused run",
    )


def user_install_abort_stamp_honest(td: Path) -> None:
    """The user-level stamp must not read as a clean install over a half-copied one.

    This is the rules stamp's defect in the other stamp: the stamp was written after every copy,
    so a run that died partway left new skill bodies on disk under the PREVIOUS commit's stamp,
    with nothing in the file to say the run had not finished (measured: the deep-reason skill
    holding the new body, the stamp naming the older commit, no state field at all).

    The abort is a reference file removed from the kit tree, so the fourth `cp` cannot stat its
    source. As in the refresh case the assertions are the EXIT TRAP'S OWN OUTPUT: `state:
    partial` is a word the pre-copy write cannot produce, and the dispositions say which pieces
    this run reached.
    """
    kit = kit_tree(td, full=True)
    home = td / "home"
    got = run_install(kit, home)
    expect(got.returncode == 0, f"the first install failed: {(got.stdout + got.stderr)[:400]}")
    first = stamp_fields(stamp_text(home / "discipline" / "KIT-VERSION", "user-level stamp"))
    expect(
        first.get("state") == "complete",
        f"an install that finished must stamp itself complete: {first}",
    )
    older_commit = first.get("kit_commit", "")
    (kit / "claude-user" / "skills" / "deep-reason" / "SKILL.md").write_text(NEW_SKILL_BODY)
    git(kit, "add", "-A")
    git(kit, "commit", "-qm", "a newer kit")
    (kit / "reference" / "voicing-document.md").unlink()
    got = run_install(kit, home)
    said = got.stdout + got.stderr
    expect(got.returncode != 0, f"an install that could not copy must not exit 0: {said[:400]}")
    expect(
        (home / "skills" / "deep-reason" / "SKILL.md").read_text() == NEW_SKILL_BODY,
        "the case is only meaningful if a new body landed before the abort",
    )
    body = stamp_text(home / "discipline" / "KIT-VERSION", "user-level stamp")
    fields = stamp_fields(body)
    expect(
        fields.get("state") == "partial",
        f"the stamp must carry the exit trap's own state, not the pre-copy write's: {body!r}",
    )
    expect(
        fields.get("kit_commit", "") != older_commit,
        "the stamp must name the commit this run was placing, not the one before it: "
        f"{fields.get('kit_commit')!r}",
    )
    expect(
        fields.get("skills", "").startswith("installed"),
        f"the piece that landed before the abort must say so: {fields}",
    )
    expect(
        not fields.get("reference", "").startswith("installed"),
        f"the piece the run never finished must not read as installed: {fields}",
    )
    for state in ("in-progress", "partial", "complete"):
        expect(
            state in body,
            f"the stamp's header must name all three states, missing {state!r}: {body!r}",
        )


# The pre-fix refresh region — its pattern-bearing lines captured verbatim (the surrounding
# argument parsing is reduced to what the court reads, and the refusal echo is shortened).
# This is the known-bad corpus the court's patterns are grounded in: a copy sourced from the
# checkout's working tree, a version scraped from the checkout's CHANGELOG, and no tag
# resolved anywhere.
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
        case("refresh-prerelease-not-latest-0", refresh_prerelease_not_latest),
        case("refresh-explicit-tag-0", refresh_explicit_tag),
        case("refresh-unknown-tag-1", refresh_unknown_tag),
        case("bare-tree-refusal-1", bare_tree_refusal),
        case("no-tags-refusal-1", no_tags_refusal),
        case("no-rules-in-tag-1", no_rules_in_tag),
        case("no-rules-dir-1", no_rules_dir),
        case("tag-without-refresh-2", tag_without_refresh),
        case("dir-without-refresh-2", dir_without_refresh),
        case("user-stamp-working-tree-0", user_stamp_records_working_tree),
        case("user-stamp-no-git-0", user_stamp_without_git),
        case("rules-stamp-names-tag-0", rules_stamp_names_tag),
        case("version-flag-0", version_flag_reports_and_writes_nothing),
        case("version-flag-no-tags-0", version_flag_without_tags),
        case("guides-refresh-from-tag-0", guides_refresh_from_tag),
        case("guides-missing-reported-0", guides_missing_is_reported),
        case("local-edit-preserved-0", local_edit_preserved),
        case("untouched-copy-not-preserved-0", untouched_copy_not_preserved),
        case("obsolete-rule-reported-0", obsolete_rule_reported_not_deleted),
        case("working-tree-install-not-blamed-0", working_tree_install_not_blamed),
        case("abort-mid-copy-stamp-honest-1", abort_mid_copy_stamp_honest),
        case("backup-never-clobbered-0", backup_never_clobbered),
        case("guide-local-edit-preserved-0", guide_local_edit_preserved),
        case("untouched-guide-not-preserved-0", untouched_guide_not_preserved),
        case("user-stamp-disposition-0", user_stamp_records_disposition),
        case("version-with-refresh-2", version_with_refresh_refused),
        case("version-with-dir-2", version_with_dir_refused),
        case("missing-dir-refusal-1", missing_dir_refusal),
        case("flag-without-value-2", flag_without_value),
        case("portable-shell-0", portable_shell),
        case("stale-tag-set-not-blamed-0", stale_tag_set_not_blamed),
        case("unclassifiable-file-refused-1", unclassifiable_file_refused),
        case("symlinked-rule-not-written-through-0", symlinked_rule_not_written_through),
        case("shipped-name-with-space-refused-1", shipped_name_with_space_refused),
        case("user-install-abort-stamp-honest-1", user_install_abort_stamp_honest),
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

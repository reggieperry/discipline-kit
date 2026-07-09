---
name: Permission grants must be narrow, never broad-allowlist interpreters or runners
description: When adding to .claude/settings.json permissions allowlist, prefer specific patterns over wildcards; never allowlist Bash(python3 *), Bash(uv run *), Bash(npx *), or any interpreter/runner with arbitrary args
type: feedback
volatility: durable
---
When proposing additions to `.claude/settings.json` `permissions.allow`, default to the narrowest pattern that still covers the observed need.

**Why:** The user pushed back when an early proposal added `Bash(npx *)` and asked to narrow it to `Bash(npx --yes markdownlint*)` — the only npx invocation actually used. Same principle held throughout: `Bash(uv run scripts/*)` instead of `Bash(uv run *)`. The fewer-permission-prompts skill spec explicitly forbids broad runner allowlists ("Never allowlist a pattern that grants arbitrary code execution... Interpreters: python/python3, node, bun, deno, ... Package runners: npx, bunx, uvx, uv run, etc."). The user agreed with this rule and applies it consistently.

**How to apply:**
- Before adding any `Bash(<runner> *)` entry, check whether `<runner>` is an interpreter or package runner. If yes, narrow to specific scripts/packages.
- For commands like `python3 -c '...'`, do not propose `Bash(python3 *)` — it's arbitrary code execution. Suggest using auto-allowed alternatives (`jq` for JSON, `uuidgen` for IDs) when possible, or accept that prompts are the right friction.
- Prefer the `Bash(foo *)` style with space-before-asterisk per the fewer-permission-prompts skill convention. Existing entries in a repo may use both `Bash(foo*)` (no space) and `Bash(foo:*)` (colon syntax) — those work but are inconsistent; don't add new ones in those styles unless extending an existing entry.
- Auto-allowed commands per Claude Code's built-ins (grep, ls, cat, head, tail, wc, find, jq, all read-only git/gh subcommands, etc.) need no allowlist entry at all. The user knows this; don't bloat the list with redundant entries.
- The deny list (e.g. `Bash(rm -rf*)`, `Bash(git push --force*)`, `Bash(git push -f*)`, and `Write` guards on sensitive files) is intentional and important. Don't propose changes to it without strong justification.

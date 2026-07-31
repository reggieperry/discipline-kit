# Stories

This directory holds the repository's work stories — the prose specs whose acceptance criteria become the loop's pre-registered claims. Each story is one file, `stories/<ID>-<slug>.md`; the template is `harness/templates/story-template.md`.

A story earns a file when its "done" is contestable and it outlives one sitting. Write it with `story-write`, score it with `story-tighten` before it turns `ready`, and — when it arrives from outside — take it in with `story-intake` (which scores it). A story's acceptance criteria carry the anti-weakening contract verbatim (assertion count not reduced, no new suppressions, no new skipped tests versus the merge-base) and are settled before any code.

The frontmatter is portable — `id`, `title`, `deps`, `labels`, `sensitive_files`, `status` (`draft` | `ready` | `handed-off` | `closed`) — and carries no tracker-specific fields, so a story travels to any board without rewriting.

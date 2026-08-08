# Stories

This directory holds the repository's work stories — the prose specs whose acceptance criteria become the loop's pre-registered claims. Each story is one file, `stories/<ID>-<slug>.md`; the template is `harness/templates/story-template.md`.

A story earns a file when its "done" is contestable and it outlives one sitting. Write it with `story-write`, score it with `story-tighten` before it turns `ready`, and — when it arrives from outside — take it in with `story-intake` (which scores it). A story's acceptance criteria carry the anti-weakening contract verbatim (assertion count not reduced, no new suppressions, no new skipped tests versus the merge-base) and are settled before any code.

The frontmatter is portable — `id`, `title`, `deps`, `labels`, `sensitive_files`, `status` (`draft` | `ready` | `handed-off` | `closed`) — and carries no tracker-specific fields, so a story travels to any board without rewriting.

Five further keys are optional and make a story a node in the chain's graph rather than a standalone spec: `adr`, `decisions`, `group`, `milestone`, `cites`. A story that carries none of them is a plain kit story. A story that carries them is read by `harness/chain_graph.py`, which parses every file here and checks the graph six ways: parse errors (the key list is closed, so an unknown key is fatal), dangling `deps` ids, cycles, unresolvable `adr:`/`decisions:` references, the ADR-0000 orphan ratio, and reverse coverage of every non-superseded Decision. Each check prints its denominator, and the exit codes are the kit's canonical three: 0 clean, 1 findings, 2 could-not-run. Run it on demand: it is not on the commit path while this repository's ADRs still hold uncovered Decisions, though its fixture is, so the checker stays guarded meanwhile.

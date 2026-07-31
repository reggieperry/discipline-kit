## Commit-path check

A mechanical check runs on the commit path, so a green commit means a machine ran the suite rather
than that the author said so.

- **A "done" report is not evidence.** Nothing is settled by an assertion that it works; it is
  settled by a check that would have failed if it did not. When you report something done, name the
  check that establishes it — and if none exists, say so plainly rather than implying one does.
- **Review output is evidence, not a verdict.** A reviewer finding nothing means a reader looked and
  found nothing. It never substitutes for a check, and correlated approval is worth little.
- **The check covers every language that builds the system.** A check that fires for one language
  while another goes unexamined lets that language weaken unseen.

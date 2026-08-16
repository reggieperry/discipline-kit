# ADR-0007 acceptance gate: the deep-reason record

Passes per `harness/skills/adr-write/SKILL.md`. Acceptance is the operator's; the gate below informs
that read and substitutes for nothing. The specific substrate is named only in a private companion
analysis held outside this repo; the adversary read that note for the concrete mechanics, and this
record stays substrate-agnostic to hold the infra-scrub line.

## Pass 1 (pre-draft attack on the drafted record), 2026-08-16: ACCEPT the reuse decision, five defects folded in

A fresh-context adversary attacked the reuse-over-build decision with access to the private
companion analysis (the substrate's actual gate mechanics, with source citations) plus ADR-0006 and
the inherited ADR-0001/0002/0005. Its charge was to find the case where reuse fails and building
in-house would have held, and to catch anything mis-stated.

**Verdict: the reuse decision is sound as recorded.** Its load-bearing premise—D4's re-derived-verdict
invariant survives on the substrate because the substrate's verification check is controller-run, not
the worker's self-report—is directly supported by the companion analysis's reading of the substrate's
mechanics. No attack found a phase where the substrate structurally forces self-report, so the reuse
does not fail at the one thing the chain exists for. The three-valued verdict is expressible (out of
band, because the substrate's gate is binary by default), the economics falsifier is honestly named
as non-mechanical and deferred, and build-in-house was fairly weighed, not dismissed.

The one reachable failure the adversary named is the one the record already courts: a substrate
upgrade silently regresses a permissive-default guard (self-report advance, the tool fence, or
park-versus-retry), reintroducing the confidently-wrong-at-signature hole, where build-in-house would
have held because it owns the seam. That is not fatal—it is closable—and defect 4 closes it by making
the gate-seam test standing rather than one-time.

Five defects found; the first four folded into the record before the pack is built, the fifth owed
with the pack:

- **Defect 1—ADR-0006's status header was stale.** ADR-0007 declared ADR-0006 Rejected, but
  ADR-0006 still read Proposed. Fixed: ADR-0006's Status line and cross-reference now read Rejected by
  ADR-0007, its record retained per supersede-never-delete. (Confirmed "Rejected" is correct for a
  never-accepted proposal, not "Superseded," which the house rule ties to overturning a governing
  decision.)
- **Defect 2—the forged-completion residue was not carried onto the substrate.** D4 re-asserted the
  happy-path invariant but not ADR-0001/D5's residue: a worker with a shell can write the substrate's
  work-and-dependency state and the git state the re-derivation reads, the same hole as a forged phase
  ref, bounded by OS-and-runtime isolation (ADR-0005), not by the fence. Fixed: a Consequence names
  the residue as consumed-not-closed with the same bound the chain gives the forged phase ref.
- **Defect 3—the terminal act could become an agent act, breaking ADR-0002/D5.** The companion
  analysis's own sketch put the terminal push in the step body, which is worker-run and fires before
  the merge conjuncts. Fixed: D4 now folds the terminal act into the never-self-report seam—the branch
  push or PR-open is controller-run, a side effect of the merge gate's pass, never a worker's step
  body.
- **Defect 4—the gate-seam conformance test was framed one-time, but the substrate churns.** A
  permissive-default regression on any substrate upgrade is silent. Fixed: the D1/D2 and D4 falsifiers
  now name the gate-seam test as a STANDING gate re-run on every substrate version bump, not a
  one-time acceptance.
- **Defect 5 (lower, owed with the pack)—the vendored-copy drift has no named court.** The pack's
  cross-repo copy of the discipline loses the same-repo commit-path checks that keep the chain's
  internal copy-not-share honest. Fixed in the record: a Consequence names a drift court (the vendored
  logic matches the chain's pinned SHA, checked on the pack's own commit path) as owed with the pack.

Attacks that did not land, recorded so the tested surface is visible: D4 unachievable
(structurally-forced self-report)—did not land, the check is controller-run and native; three-valued
verdict inexpressible—did not land, concrete encodings exist and the park semantics match the chain's
own; economics falsifier dishonest—did not land, it is explicitly non-mechanical and deferred;
ADR-0006 mis-dispositioned—did not land as a reasoning error (only the stale header, defect 1);
build-in-house dismissed too quickly—did not land, its strongest argument is named and the real trust
boundary (human merge plus OS isolation) is unchanged by reuse; misread of ADR-0001/0005—did not land.

One framing correction the adversary flagged against the operator's attack prompt, not the ADR: a
"the substrate is a fork ~1300 commits ahead" figure is not supported by the companion analysis (which
pins one commit and says only that line numbers drift) and does not appear in ADR-0007, which says
"actively-changing." The churn tension is real and disclosed; the specific figure is not load-bearing
and was kept out of the record.

The record lands Accepted on the operator's direction to decline ADR-0006 and record the reuse fork,
with this pass as the admitting testimony. Acceptance is the operator's read; this gate is an
adversary's absence report, bounded as such, and signs nothing.

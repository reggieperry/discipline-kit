# Report & claim disclosure conventions

Drop this beside a repo's reports so the conventions install with the harness instead of being
rediscovered per project. Four conventions, each one sentence of discipline; they make a report's
guarantees legible to every future reader.

1. **Semantics line.** Every verify-family claim (any discharge, any signature) states in one clause
   what its signature actually certifies — reproducibility of a receipt, agreement between two legs,
   a mechanical check passing — and points at the leg that would carry *correctness* beyond that. A
   signature's meaning is bounded by the weakest provenance in its chain; say so.

2. **Authorship note.** A report discloses the true authoring order in one sentence — what was
   written fresh, what was adapted from an existing template, what a prior session or another author
   produced — rather than presenting an outcome as if it were sole fresh work.

3. **Reliability boundary.** Any retrospective account states the granularity at which it is
   *evidence* versus *memory* — commit-anchored and re-readable versus recalled — and flags any
   context-compaction seam across which recall is unverified testimony about the past, not knowledge.

4. **Process paragraph.** Per slice, one short paragraph answers four questions, with the reliability
   boundary applied (definitive statements only for direct-recall work): (a) for each test suite
   touched, was it written *before*, *alongside*, or *after* the code it exercises; (b) which new
   tests were **observed red**, and by what route — for any test-bearing slice, either a pasted
   `red-proof` receipt line or a declared allocation ("build-then-verify; dual-leg discharge cited"),
   where a **detector-class** slice (a gate, check, tamper proof, fail-closed property, or
   discriminating mechanism) may take only the first branch — never-red is not an option for a
   detector; (c) any assertion or golden **adjusted after seeing actual output**, with the
   justification (the green-by-weakening disclosure — adjusting a wrong expectation is legitimate;
   saying so is the price); (d) the refactor pass — done, naming its catalog moves or giving a real
   justification, or skipped with the reason, and confirming any `refactor:` commit is separate from
   the functional change. Four sentences
   suffice — "I ran it and the tests passed" describes an outcome, not the process the reader asked
   about. The `red-proof` check (harness/ledger/red-proof) is the mechanical court for (b).

   Optionally, add a **"memories consulted:"** line when a memory materially shaped the slice, naming
   the ones it drew on. This is the recall numerator a memory layer otherwise never has — the cheap
   signal (one sentence per slice) that tells the weekly prune which memories earn their keep and which
   are dead weight. Name only memories that changed a decision, not every one glanced at.

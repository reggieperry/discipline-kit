# Dual-implementation review checklist (the primitives-diff pass)

For any computation implemented in two languages so the legs verify each other.
The logic is rarely where legs diverge; the primitives are. Walk this list against
BOTH implementations side by side — it is a fifteen-minute pass and it targets the
seam a single author of both legs cannot see by reading.

## Text primitives
- Line splitting: enumerate each language's terminator set; pin the intended set at
  the byte level in the operationalization note; one shared exotic-separator fixture.
- Whitespace: which \s dialect (ASCII vs Unicode); tokenization on split().
- Regex: dialect differences for any shared pattern (anchors, \b, unicode classes).
- Encoding: bytes vs str seams; normalization if any input is user/agent text.

## Numeric primitives
- Rounding mode: name it per language (HALF_UP vs banker's); pin or tolerate — declared.
- Float formatting in receipts: byte-identical only if format + mode pinned both sides;
  otherwise stated tolerance with epsilon.
- Integer division/modulo sign; overflow behavior if any counter can be large.

## Stochastic components
- Shared explicit PRNG (e.g. splitmix64) implemented by hand in both legs; never a
  language default Random. Pin the seed and a cross-language output vector fixture.

## Ordering and structure
- Sort stability and comparator ties; map/dict iteration order where it can leak
  into receipts.

## Fixtures and goldens
- One shared edge fixture both legs must reproduce identically.
- Goldens obtained empirically from the leg where behavior is primitive-dependent
  (write the fixture, run it, let it state the golden) — and provenance-labeled
  (see memories/feedback_golden_provenance.md).

## Receipt policy
- Comparability declared per receipt class before comparing: integer receipts
  byte-identical; float receipts pinned-mode or tolerance; the policy quoted in the
  discharge claim's semantics line.

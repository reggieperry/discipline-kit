---
name: reference_data_system_design
description: "DDIA Ch 1-6 (Kleppmann) — the data-system half (storage/columnar, encoding/schema-evolution, partitioning); complements the Ch 7-9 transaction memories"
metadata: 
  node_type: memory
  type: reference
  volatility: durable
---

Distilled from Kleppmann, *Designing Data-Intensive Applications*, Ch 3/4/6 read from source. This is the **data-system half**; the transaction half (Ch 7-9) lives in [[feedback_concurrency_invariant_design]], [[feedback_postgres_concurrency_operational]], [[feedback_aggregates_and_optimistic_concurrency]].

**Storage engines (Ch 3).** Two schools: log-structured (LSM-trees — append-only, turn random writes into sequential writes; SSTable/Bitcask/Cassandra/Lucene family) vs update-in-place (B-trees — fixed pages overwritten). OLTP (row-oriented, indexed key lookups, seek-bound) vs OLAP (column-oriented, full scans, bandwidth-bound).

**Column-oriented storage (Ch 3, p95-103).** Store all values of each column together (column-per-file), not each row together — a query reads only the columns it needs. **Parquet is exactly this** (columnar, document-model, Dremel-based). Compresses well (bitmap + run-length encoding) because a column's values repeat. **Sort order is decisive:** the *first* sort key compresses best (long runs) and enables efficient range scans — so for time-series a date/timestamp first sort key lets a query scan only the relevant range. You can't update-in-place compressed columns (inserting a row rewrites every column file) → writes go through an LSM-style buffer + bulk merge, or whole-file rewrite.

**Encoding + schema evolution (Ch 4, p111-137).** Preserve two compatibilities at once: *backward* (new code reads old data) and *forward* (old code reads new data). "**Data outlives code**" — persisted/cached data written under an old schema must stay readable. Avro: reader's and writer's schemas need only be *compatible*, resolved by field **name** (not position/tag); a field in the writer but not the reader is ignored; a field the reader expects but the writer lacks is filled from the reader's **default**. Rule: **you may only add or remove a field that has a default value** — adding a no-default field breaks backward compat, removing one breaks forward compat; renaming is backward- but not forward-compatible (reader aliases). Protobuf/Thrift: field **tags** are essential — never change or reuse a tag; new fields get a new tag and must be optional/defaulted. Changing a field's type risks truncation/precision loss.

**Partitioning (Ch 6, p199-211).** Spread data + load evenly; **skew and hot spots** defeat it. Range partitioning makes range scans easy BUT a monotonic first key (e.g. a timestamp) sends all writes to the current partition ("today") → hot spot; fix by prefixing with another key (e.g. `(sensor, time)`). Hash partitioning distributes uniformly but loses range scans. Compound key = hash the first part, sort the rest (e.g. `(user_id, timestamp)`) — even distribution + in-partition range scans. Small-vs-large partition tradeoff: too many small partitions = management overhead; too few large = expensive rebalancing/recovery. Don't rebalance with hash-mod-N (changing N moves almost everything); use many-fixed-partitions or dynamic split/merge.

**Application notes.** A Parquet bar cache keyed one file per `(entity, partition_key)` is an entity-keyed partitioning scheme that *correctly avoids* the date-first hot-spot (many entities spread the writes) — keep it. Watch the **small-file problem** (many entities × partitions × refreshes → many small Parquet files → read amplification). Stable per-column dtypes + an explicit date sort key drive both scan speed and compression. Arrow IPC across a process-pool boundary, plus a cached Parquet schema, are schema boundaries under the add-field-with-default / never-reorder-or-retype / read-side-version-guard rules. For a vector store: bound collection growth; an embedding-model change is a schema migration (re-embed, don't mix versions).

**Lower relevance (Ch 1/2/5 — from knowledge, not re-read this pass):** Ch 1 reliability/scalability/maintainability + *evolvability* (the umbrella over schema evolution); Ch 2 data models (settled once chosen); Ch 5 replication (revisit at multi-host deployment).

Related: [[feedback_concurrency_invariant_design]], [[feedback_postgres_concurrency_operational]], [[feedback_aggregates_and_optimistic_concurrency]], [[reference_sources_to_consume]].

# Consistency model

SyncMesh is an educational operation replication lab. Its tests and simulator
check specific invariants; they are not a formal proof for every possible
execution or a production guarantee.

## State rules

- Each operation has an origin sequence, base vector, and hybrid logical clock.
- A peer operation is applied only when its next origin sequence and every
  cross-origin dependency in its base vector are present. Missing dependencies
  stay in `pending_ops` until they arrive.
- Each mutable item field is a max-register ordered by
  `(physical_ms, logical, origin_node_id, operation_id)`. This total order makes
  field projection independent of delivery order. Different fields have
  independent registers. Concurrent values for the same field are retained in
  an open conflict row; a reviewed resolution is a new normal operation.
- Stock is a PN-counter: each origin has monotonically increasing positive and
  negative components. The visible stock is the sum of positive minus negative
  components. Negative stock is allowed and returned with `oversold: true`.
- Deletes are permanent remove-wins tombstones. A concurrent or later create or
  field edit does not resurrect a deleted ID; this release has no restore op.
- Duplicate operation IDs are ignored. Atomic batches prevent partial writes
  when one operation in a batch is invalid.

## Compaction and bootstrap

`POST /admin/compact` only removes log entries at or below the minimum vector
reported by every configured peer. If a peer has not reported a vector, the
compactor waits. The materialized tables and `node_state.node_vector` retain the
state and compacted prefix. A peer behind that prefix receives an authenticated
state snapshot before normal log exchange resumes. Snapshot application merges
registers, PN-counter components, and tombstones by their deterministic rules.

Operation history older than a compacted prefix is no longer available for
causal-graph inspection. Keep backups of the SQLite files if historical audit
records matter.

## Evidence and limits

`uv run python -m syncmesh.simulation.run --reproduce` generates 1,000 seeded
operation schedules and a gossip/topology comparison. The current generated
report records whether those schedules converge. Randomized testing can find
counterexamples; it cannot establish a formal CRDT proof, test real networks,
or guarantee behavior beyond the modeled message schedules.

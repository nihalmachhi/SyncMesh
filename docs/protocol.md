# Replication protocol

## Operations

Each immutable operation is identified by `origin_node_id:origin_seq` and
contains an entity ID, discriminated payload, base vector, UTC timestamp, and
hybrid logical clock. Pydantic validates the operation kind and payload before
any database write. An entire exchange page is applied in one SQLite
transaction.

## Exchange

1. A peer reads the receiver's vector and compacted prefix.
2. If one side is behind the other's compacted prefix, it exchanges a validated
   materialized snapshot first.
3. Peers compare per-origin hash ranges and request bounded pages of up to 500
   missing operations according to version vectors.
4. Operations are deduplicated and buffered until both origin sequence and
   causal context are ready.
5. The materialized fields, PN-counter, and permanent tombstones update in the
   same transaction as the operation log.

Peer HTTP calls reuse one async client per loop, run concurrently across peers,
and use bounded exponential retry delays with jitter. Sync outcomes are written
to `sync_log` and reflected in `/stats` and Prometheus `/metrics`.

## Digests and snapshots

`GET /sync/digest` returns SHA-256 values for fixed-size ranges by operation
origin. Digests expose divergence compactly and complement the authoritative
version vector. When a peer is behind a compacted prefix, `/sync/snapshot`
transfers the materialized entities, their registers and counters, tombstones,
conflict records, and current vector. Snapshots merge by the same deterministic
register and counter rules.

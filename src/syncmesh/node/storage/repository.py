"""Transactional repository composed from log, entity, and conflict storage."""

import json
import sqlite3
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from syncmesh.domain.apply import EntityState, apply_operation
from syncmesh.node.storage import conflicts, entities, oplog
from syncmesh.node.storage.db import Database
from syncmesh.protocol.digest import range_digests
from syncmesh.protocol.hlc import HLC, HybridLogicalClock
from syncmesh.protocol.messages import NodeSnapshot, Operation, OpType, SnapshotEntity
from syncmesh.protocol.version_vector import merge


class ReceiveOutcome(StrEnum):
    """Result of handling a peer operation."""

    APPLIED = "applied"
    BUFFERED = "buffered"
    DUPLICATE = "duplicate"


def _register_key(register: dict) -> tuple[int, int, str, str]:
    """Return the stable HLC/node/operation ordering used by register snapshots."""
    hlc = register["hlc"]
    return (
        int(hlc["physical_ms"]),
        int(hlc["logical"]),
        str(register["origin_node_id"]),
        str(register["operation_id"]),
    )


class Repository:
    """Coordinate one node's immutable operation log and entity projection."""

    def __init__(self, db: Database, node_id: str) -> None:
        self.db = db
        self.node_id = node_id
        with self.db.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO node_state(node_id) VALUES (?)", (node_id,))
            saved_hlcs = [
                HLC(**json.loads(row[0]))
                for row in connection.execute("SELECT hlc FROM change_log WHERE hlc<>''").fetchall()
            ]
        self.clock = HybridLogicalClock(max(saved_hlcs, default=HLC(0, 0)))

    def vector(self, connection: sqlite3.Connection) -> dict[str, int]:
        """Return the log vector plus any causally stable compacted prefix."""
        row = connection.execute(
            "SELECT node_vector FROM node_state WHERE node_id=?", (self.node_id,)
        ).fetchone()
        baseline = json.loads(row[0]) if row else {}
        return merge(baseline, oplog.vector(connection))

    def create(self, fields: dict, quantity: int = 0, entity_id: str | None = None) -> str:
        """Create an inventory entity and return its ID."""
        entity_id = entity_id or uuid4().hex
        self.local(entity_id, OpType.CREATE, {"fields": fields, "quantity": quantity})
        return entity_id

    def set_fields(self, entity_id: str, fields: dict) -> Operation:
        """Write an operation updating inventory fields."""
        return self.local(entity_id, OpType.SET_FIELD, {"fields": fields})

    def adjust(self, entity_id: str, delta: int) -> Operation:
        """Write a signed stock delta operation."""
        return self.local(entity_id, OpType.ADJUST_QUANTITY, {"delta": delta})

    def delete(self, entity_id: str) -> Operation:
        """Write an entity tombstone operation."""
        return self.local(entity_id, OpType.DELETE, {})

    def local(self, entity_id: str, kind: OpType, payload: dict) -> Operation:
        """Create and atomically apply the next local operation."""
        with self.db.connect() as connection:
            state = connection.execute(
                "SELECT local_seq FROM node_state WHERE node_id=?", (self.node_id,)
            ).fetchone()
            sequence = int(state[0]) + 1
            now = datetime.now(UTC)
            operation = Operation(
                operation_id=f"{self.node_id}:{sequence}",
                origin_node_id=self.node_id,
                origin_seq=sequence,
                entity_id=entity_id,
                op_type=kind,
                payload=payload,
                base_vector=self.vector(connection),
                hlc=self.clock.tick(),
                wall_clock=now,
            )
            self._apply(connection, operation)
            connection.execute(
                "UPDATE node_state SET local_seq=? WHERE node_id=?",
                (sequence, self.node_id),
            )
        return operation

    def receive(self, operation: Operation) -> bool:
        """Apply the operation if ready; return whether it was applied immediately."""
        return self.receive_detailed(operation) is ReceiveOutcome.APPLIED

    def receive_detailed(self, operation: Operation) -> ReceiveOutcome:
        """Apply, buffer, or identify a duplicate in one transaction."""
        return self.receive_batch([operation])[0]

    def receive_batch(self, operations: list[Operation]) -> list[ReceiveOutcome]:
        """Validate and apply a whole peer batch atomically, then drain ready gaps."""
        outcomes: list[ReceiveOutcome] = []
        with self.db.connect() as connection:
            for operation in operations:
                if operation.origin_node_id == self.node_id:
                    raise ValueError("peer operation claims the local node identity")
                found = connection.execute(
                    "SELECT 1 FROM change_log WHERE operation_id=?", (operation.operation_id,)
                ).fetchone()
                pending = connection.execute(
                    "SELECT operation_id FROM pending_ops WHERE origin_node_id=? AND origin_seq=?",
                    (operation.origin_node_id, operation.origin_seq),
                ).fetchone()
                if found or pending:
                    if pending and pending[0] != operation.operation_id:
                        raise ValueError(
                            "origin sequence already has a different pending operation"
                        )
                    outcomes.append(ReceiveOutcome.DUPLICATE)
                    continue
                have = self.vector(connection).get(operation.origin_node_id, 0)
                if operation.origin_seq <= have:
                    outcomes.append(ReceiveOutcome.DUPLICATE)
                    continue
                connection.execute(
                    "INSERT INTO pending_ops(operation_id, origin_node_id, origin_seq, "
                    "raw_operation) "
                    "VALUES(?,?,?,?)",
                    (
                        operation.operation_id,
                        operation.origin_node_id,
                        operation.origin_seq,
                        operation.model_dump_json(),
                    ),
                )
                outcomes.append(ReceiveOutcome.BUFFERED)

            self._drain_pending(connection)
            for index, operation in enumerate(operations):
                applied = connection.execute(
                    "SELECT 1 FROM change_log WHERE operation_id=?", (operation.operation_id,)
                ).fetchone()
                if applied and outcomes[index] is ReceiveOutcome.BUFFERED:
                    outcomes[index] = ReceiveOutcome.APPLIED
        return outcomes

    def _drain_pending(self, connection: sqlite3.Connection) -> None:
        """Repeatedly apply pending operations whose dot and context are available."""
        while True:
            vector = self.vector(connection)
            rows = connection.execute(
                "SELECT raw_operation FROM pending_ops ORDER BY origin_node_id, origin_seq"
            ).fetchall()
            ready: Operation | None = None
            for row in rows:
                candidate = Operation.model_validate_json(row[0])
                next_sequence = vector.get(candidate.origin_node_id, 0) + 1
                context_ready = all(
                    vector.get(origin, 0) >= sequence
                    for origin, sequence in candidate.base_vector.items()
                )
                if candidate.origin_seq == next_sequence and context_ready:
                    ready = candidate
                    break
            if ready is None:
                return
            connection.execute(
                "DELETE FROM pending_ops WHERE operation_id=?", (ready.operation_id,)
            )
            self.clock.observe(ready.hlc)
            self._apply(connection, ready)

    def _apply(self, connection: sqlite3.Connection, operation: Operation) -> int:
        """Persist an operation and its convergent field-register projection."""
        now = datetime.now(UTC)
        received_at = now.isoformat()
        oplog.append(connection, operation, received_at)
        conflicts_added = conflicts.record_concurrent_pairs(connection, operation, received_at)

        state = entities.get(connection, operation.entity_id)
        next_state, _ = apply_operation(state, operation)
        next_state = EntityState(
            fields=next_state.fields,
            quantity=next_state.quantity,
            is_deleted=next_state.is_deleted,
            entity_vector=merge(
                state.entity_vector or {},
                operation.base_vector,
                {operation.origin_node_id: operation.origin_seq},
            ),
            field_registers=next_state.field_registers,
            pn_counter=next_state.pn_counter,
            tombstone=next_state.tombstone,
        )
        entities.save(
            connection,
            operation.entity_id,
            next_state,
            now,
        )
        if operation.origin_node_id != self.node_id:
            self.clock.observe(operation.hlc)
        return conflicts_added

    def items(self) -> list[dict]:
        """Return visible inventory items."""
        with self.db.connect() as connection:
            return entities.list_items(connection)

    def get_item(self, entity_id: str) -> dict | None:
        """Return one visible inventory item without loading the collection."""
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT entity_id, fields, quantity FROM entities "
                "WHERE entity_id=? AND is_deleted=0",
                (entity_id,),
            ).fetchone()
        if row is None:
            return None
        fields = json.loads(row["fields"])
        stock = int(row["quantity"])
        return {"id": row["entity_id"], **fields, "stock": stock, "oversold": stock < 0}

    def conflicts(self) -> list[dict]:
        """Return recorded conflict rows."""
        with self.db.connect() as connection:
            return conflicts.list_all(connection)

    def resolve_conflict(self, conflict_id: str, fields: dict) -> Operation:
        """Resolve selected fields by appending a normal causally later operation."""
        with self.db.connect() as connection:
            conflict = conflicts.get(connection, conflict_id)
        if conflict is None:
            raise KeyError("Conflict not found")
        if conflict["status"] != "OPEN":
            raise ValueError("Conflict is already resolved")
        allowed = set(conflict["field"].split(","))
        if not fields or not set(fields).issubset(allowed):
            raise ValueError("resolution fields must be a nonempty subset of the conflict fields")
        operation = self.set_fields(conflict["entity_id"], fields)
        with self.db.connect() as connection:
            conflicts.mark_resolved(connection, conflict_id, operation.operation_id)
        return operation

    def stats(self) -> dict:
        """Return log, pending, conflict, vector, and sync summaries."""
        with self.db.connect() as connection:
            peer_lag = [
                {"peer_id": row["peer_id"], "duration_ms": row["duration_ms"]}
                for row in connection.execute(
                    "SELECT peer_id, duration_ms FROM sync_log "
                    "WHERE (peer_id, started_at) IN ("
                    "SELECT peer_id, MAX(started_at) FROM sync_log GROUP BY peer_id)"
                ).fetchall()
            ]
            return {
                "operations": connection.execute("SELECT COUNT(*) FROM change_log").fetchone()[0],
                "pending": connection.execute("SELECT COUNT(*) FROM pending_ops").fetchone()[0],
                "conflicts": connection.execute(
                    "SELECT COUNT(*) FROM conflicts WHERE status='OPEN'"
                ).fetchone()[0],
                "vector": self.vector(connection),
                "peer_lag": peer_lag,
            }

    def since(self, version: dict[str, int], limit: int = 500) -> list[Operation]:
        """Return one bounded page of operations absent from a peer's vector."""
        with self.db.connect() as connection:
            return oplog.since(connection, version, limit)

    def recent_operations(self, limit: int = 300) -> list[Operation]:
        """Return a bounded recent log page for graph diagnostics."""
        with self.db.connect() as connection:
            return oplog.recent(connection, limit)

    def operation_digest(self, range_size: int = 128) -> dict:
        """Return compact content hashes for the bounded current operation log."""
        with self.db.connect() as connection:
            operations = oplog.recent(connection, 100_000)
        return range_digests(operations, range_size)

    def compacted_vector(self) -> dict[str, int]:
        """Return the stable prefix already summarized by the materialized snapshot."""
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT node_vector FROM node_state WHERE node_id=?", (self.node_id,)
            ).fetchone()
            return json.loads(row[0]) if row else {}

    def record_peer_vector(self, peer_id: str, peer_vector: dict[str, int]) -> None:
        """Record the operation prefix a peer reports having received."""
        with self.db.connect() as connection:
            connection.execute(
                "INSERT INTO peer_vectors(peer_id, vector, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(peer_id) DO UPDATE SET vector=excluded.vector, "
                "updated_at=excluded.updated_at",
                (peer_id, json.dumps(peer_vector, sort_keys=True), datetime.now(UTC).isoformat()),
            )

    def compact(self, peer_ids: tuple[str, ...]) -> dict:
        """Delete log entries acknowledged by every configured peer."""
        if not peer_ids:
            raise ValueError("compaction requires at least one configured peer")
        with self.db.connect() as connection:
            rows = {
                row["peer_id"]: json.loads(row["vector"])
                for row in connection.execute("SELECT peer_id, vector FROM peer_vectors").fetchall()
            }
            if any(peer_id not in rows for peer_id in peer_ids):
                return {
                    "removed": 0,
                    "stable_vector": {},
                    "waiting_for": [p for p in peer_ids if p not in rows],
                }
            current = self.vector(connection)
            stable = {
                origin: min(
                    peer_vectors.get(origin, 0) for peer_vectors in (rows[p] for p in peer_ids)
                )
                for origin in current
            }
            previous = json.loads(
                connection.execute(
                    "SELECT node_vector FROM node_state WHERE node_id=?", (self.node_id,)
                ).fetchone()[0]
            )
            baseline = merge(previous, stable)
            removed = 0
            for origin, sequence in stable.items():
                cursor = connection.execute(
                    "DELETE FROM change_log WHERE origin_node_id=? AND origin_seq<=?",
                    (origin, sequence),
                )
                removed += cursor.rowcount
            connection.execute(
                "UPDATE node_state SET node_vector=? WHERE node_id=?",
                (json.dumps(baseline, sort_keys=True), self.node_id),
            )
        return {"removed": removed, "stable_vector": baseline, "waiting_for": []}

    def export_snapshot(self) -> NodeSnapshot:
        """Export materialized state and the vector a stale peer can bootstrap from."""
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT entity_id FROM entities ORDER BY entity_id"
            ).fetchall()
            snapshot_entities = {}
            for row in rows:
                state = entities.get(connection, row["entity_id"])
                snapshot_entities[row["entity_id"]] = SnapshotEntity(
                    fields=state.fields,
                    quantity=state.quantity,
                    is_deleted=state.is_deleted,
                    entity_vector=state.entity_vector or {},
                    field_registers=state.field_registers,
                    pn_counter=state.pn_counter,
                    tombstone=state.tombstone,
                )
            return NodeSnapshot(
                node_id=self.node_id,
                vector=self.vector(connection),
                entities=snapshot_entities,
                conflicts=conflicts.list_all(connection),
            )

    def apply_snapshot(self, snapshot: NodeSnapshot) -> None:
        """Merge an authenticated peer snapshot into the local materialized state."""
        if snapshot.node_id == self.node_id:
            raise ValueError("snapshot cannot claim the local node identity")
        with self.db.connect() as connection:
            for entity_id, incoming in snapshot.entities.items():
                current = entities.get(connection, entity_id)
                registers = dict(current.field_registers)
                for field_name, candidate in incoming.field_registers.items():
                    present = registers.get(field_name)
                    if present is None or _register_key(candidate) > _register_key(present):
                        registers[field_name] = candidate
                counter = {node: dict(parts) for node, parts in current.pn_counter.items()}
                for node, parts in incoming.pn_counter.items():
                    existing = counter.setdefault(node, {"positive": 0, "negative": 0})
                    for component in ("positive", "negative"):
                        existing[component] = max(existing[component], parts[component])
                tombstone = current.tombstone
                if incoming.tombstone and (
                    tombstone is None
                    or _register_key(incoming.tombstone) > _register_key(tombstone)
                ):
                    tombstone = incoming.tombstone
                merged_fields = {name: register["value"] for name, register in registers.items()}
                quantity = sum(parts["positive"] - parts["negative"] for parts in counter.values())
                merged_state = EntityState(
                    fields=merged_fields,
                    quantity=quantity,
                    is_deleted=current.is_deleted or incoming.is_deleted or tombstone is not None,
                    entity_vector=merge(current.entity_vector or {}, incoming.entity_vector),
                    field_registers=registers,
                    pn_counter=counter,
                    tombstone=tombstone,
                )
                entities.save(connection, entity_id, merged_state, datetime.now(UTC))
            for conflict in snapshot.conflicts:
                connection.execute(
                    "INSERT OR IGNORE INTO conflicts(conflict_id, entity_id, field, operation_ids, "
                    "policy, status, resolution, detected_at) VALUES(?,?,?,?,?,?,?,?)",
                    tuple(
                        conflict[key]
                        for key in (
                            "conflict_id",
                            "entity_id",
                            "field",
                            "operation_ids",
                            "policy",
                            "status",
                            "resolution",
                            "detected_at",
                        )
                    ),
                )
            state = connection.execute(
                "SELECT node_vector, local_seq FROM node_state WHERE node_id=?", (self.node_id,)
            ).fetchone()
            baseline = merge(json.loads(state["node_vector"]), snapshot.vector)
            connection.execute(
                "UPDATE node_state SET node_vector=?, local_seq=? WHERE node_id=?",
                (
                    json.dumps(baseline, sort_keys=True),
                    max(state["local_seq"], baseline.get(self.node_id, 0)),
                    self.node_id,
                ),
            )

    def record_sync(
        self,
        peer_id: str,
        started_at: datetime,
        duration_ms: float,
        ops_sent: int,
        ops_received: int,
        duplicates_ignored: int,
        conflicts_found: int,
    ) -> None:
        """Write one peer exchange summary to the sync history table."""
        with self.db.connect() as connection:
            connection.execute(
                "INSERT INTO sync_log(sync_id, peer_id, started_at, duration_ms, ops_sent, "
                "ops_received, duplicates_ignored, conflicts_found) VALUES(?,?,?,?,?,?,?,?)",
                (
                    uuid4().hex,
                    peer_id,
                    started_at.isoformat(),
                    duration_ms,
                    ops_sent,
                    ops_received,
                    duplicates_ignored,
                    conflicts_found,
                ),
            )

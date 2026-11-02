"""Transactional repository composed from log, entity, and conflict storage."""

import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from syncmesh.domain.apply import EntityState, apply_operation
from syncmesh.node.storage import conflicts, entities, oplog
from syncmesh.node.storage.db import Database
from syncmesh.protocol.messages import Operation, OpType
from syncmesh.protocol.version_vector import CausalOrder, compare, merge


class Repository:
    """Coordinate one node's immutable operation log and entity projection."""

    def __init__(self, db: Database, node_id: str) -> None:
        self.db = db
        self.node_id = node_id
        with self.db.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO node_state(node_id) VALUES (?)", (node_id,)
            )

    @staticmethod
    def vector(connection: sqlite3.Connection) -> dict[str, int]:
        """Return the local operation-log vector."""
        return oplog.vector(connection)

    def create(self, fields: dict, quantity: int = 0, entity_id: str | None = None) -> str:
        """Create an inventory entity and return its ID."""
        entity_id = entity_id or uuid4().hex
        self.local(entity_id, OpType.CREATE, {"fields": fields, "quantity": quantity})
        return entity_id

    def set_fields(self, entity_id: str, fields: dict) -> None:
        """Write an operation updating inventory fields."""
        self.local(entity_id, OpType.SET_FIELD, {"fields": fields})

    def adjust(self, entity_id: str, delta: int) -> None:
        """Write a signed stock delta operation."""
        self.local(entity_id, OpType.ADJUST_QUANTITY, {"delta": delta})

    def delete(self, entity_id: str) -> None:
        """Write an entity tombstone operation."""
        self.local(entity_id, OpType.DELETE, {})

    def local(self, entity_id: str, kind: OpType, payload: dict) -> Operation:
        """Create and atomically apply the next local operation."""
        with self.db.connect() as connection:
            state = connection.execute(
                "SELECT local_seq FROM node_state WHERE node_id=?", (self.node_id,)
            ).fetchone()
            sequence = int(state[0]) + 1
            operation = Operation(
                operation_id=f"{self.node_id}:{sequence}",
                origin_node_id=self.node_id,
                origin_seq=sequence,
                entity_id=entity_id,
                op_type=kind,
                payload=payload,
                base_vector=self.vector(connection),
                wall_clock=datetime.now(UTC),
            )
            self._apply(connection, operation)
            connection.execute(
                "UPDATE node_state SET local_seq=? WHERE node_id=?",
                (sequence, self.node_id),
            )
        return operation

    def receive(self, operation: Operation) -> bool:
        """Apply the next origin sequence or buffer it until its gap is filled."""
        with self.db.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM change_log WHERE operation_id=?", (operation.operation_id,)
            ).fetchone():
                return False
            have = oplog.sequence(connection, operation.origin_node_id)
            if operation.origin_seq > have + 1:
                connection.execute(
                    "INSERT OR IGNORE INTO pending_ops VALUES(?,?,?,?)",
                    (
                        operation.operation_id,
                        operation.origin_node_id,
                        operation.origin_seq,
                        operation.model_dump_json(),
                    ),
                )
                return False
            if operation.origin_seq <= have:
                return False
            self._apply(connection, operation)
            while True:
                next_sequence = oplog.sequence(connection, operation.origin_node_id) + 1
                next_row = connection.execute(
                    "SELECT raw_operation FROM pending_ops "
                    "WHERE origin_node_id=? AND origin_seq=?",
                    (operation.origin_node_id, next_sequence),
                ).fetchone()
                if next_row is None:
                    break
                queued = Operation.model_validate_json(next_row[0])
                connection.execute(
                    "DELETE FROM pending_ops WHERE operation_id=?", (queued.operation_id,)
                )
                self._apply(connection, queued)
        return True

    def _apply(self, connection: sqlite3.Connection, operation: Operation) -> None:
        """Persist the operation and its current materialized transition."""
        now = datetime.now(UTC)
        received_at = now.isoformat()
        oplog.append(connection, operation, received_at)

        state = entities.get(connection, operation.entity_id)
        relation: CausalOrder | None = None
        previous_key: tuple[str, str, str] | None = None
        if operation.op_type is OpType.SET_FIELD:
            relation = compare(operation.base_vector, state.entity_vector or {})
            previous_key = conflicts.latest_field_edit(connection, operation.entity_id)

        next_state, has_conflict = apply_operation(state, operation, relation, previous_key)
        next_state = EntityState(
            fields=next_state.fields,
            quantity=next_state.quantity,
            is_deleted=next_state.is_deleted,
            entity_vector=merge(
                state.entity_vector or {},
                operation.base_vector,
                {operation.origin_node_id: operation.origin_seq},
            ),
        )
        if has_conflict and previous_key is not None:
            conflicts.record_losing_edit(connection, operation, previous_key, received_at)
        entities.save(
            connection,
            operation.entity_id,
            next_state,
            now,
            operation.operation_id if next_state.is_deleted else None,
        )

    def items(self) -> list[dict]:
        """Return visible inventory items."""
        with self.db.connect() as connection:
            return entities.list_items(connection)

    def conflicts(self) -> list[dict]:
        """Return recorded conflict rows."""
        with self.db.connect() as connection:
            return conflicts.list_all(connection)

    def stats(self) -> dict:
        """Return log, pending, conflict, and version-vector summaries."""
        with self.db.connect() as connection:
            return {
                "operations": connection.execute(
                    "SELECT COUNT(*) FROM change_log"
                ).fetchone()[0],
                "pending": connection.execute(
                    "SELECT COUNT(*) FROM pending_ops"
                ).fetchone()[0],
                "conflicts": connection.execute(
                    "SELECT COUNT(*) FROM conflicts WHERE status='OPEN'"
                ).fetchone()[0],
                "vector": self.vector(connection),
            }

    def since(self, version: dict[str, int]) -> list[Operation]:
        """Return operations absent from a peer's version vector."""
        with self.db.connect() as connection:
            return oplog.since(connection, version)

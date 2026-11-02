"""Deterministic conflict detection and review state in SQLite."""

import hashlib
import json
import sqlite3
from typing import Any

from syncmesh.node.storage import oplog
from syncmesh.protocol.messages import Operation, OpType
from syncmesh.protocol.version_vector import CausalOrder, compare, merge


def record_concurrent_pairs(
    connection: sqlite3.Connection, operation: Operation, detected_at: str
) -> int:
    """Record symmetric open conflict rows for every concurrent overlapping edit."""
    if operation.op_type not in (OpType.CREATE, OpType.SET_FIELD):
        return 0
    current_fields = operation.payload["fields"]
    rows = connection.execute(
        "SELECT * FROM change_log WHERE entity_id=? AND operation_id<>? "
        "AND op_type IN ('create','set_field') ORDER BY operation_id",
        (operation.entity_id, operation.operation_id),
    ).fetchall()
    added = 0
    for row in rows:
        previous = oplog.operation_from_row(row)
        overlap = sorted(set(current_fields) & set(previous.payload["fields"]))
        if (
            not overlap
            or compare(_event_vector(operation), _event_vector(previous))
            is not CausalOrder.CONCURRENT
        ):
            continue
        winner, loser = sorted((operation, previous), key=_operation_key, reverse=True)
        conflict_id = _conflict_id(operation.operation_id, previous.operation_id)
        resolution = {
            "winner": winner.operation_id,
            "loser": loser.operation_id,
            "winner_value": {name: winner.payload["fields"][name] for name in overlap},
            "loser_value": {name: loser.payload["fields"][name] for name in overlap},
        }
        cursor = connection.execute(
            "INSERT OR IGNORE INTO conflicts(conflict_id, entity_id, field, operation_ids, "
            "policy, status, resolution, detected_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                conflict_id,
                operation.entity_id,
                ",".join(overlap),
                json.dumps(sorted((operation.operation_id, previous.operation_id))),
                "hlc_per_field",
                "OPEN",
                json.dumps(resolution, sort_keys=True),
                detected_at,
            ),
        )
        added += cursor.rowcount
    return added


def _event_vector(operation: Operation) -> dict[str, int]:
    """Return the causal context including this operation's own dot."""
    return merge(operation.base_vector, {operation.origin_node_id: operation.origin_seq})


def _operation_key(operation: Operation) -> tuple[int, int, str, str]:
    """Stable winner ordering for operations in the same causal antichain."""
    return (
        operation.hlc.physical_ms,
        operation.hlc.logical,
        operation.origin_node_id,
        operation.operation_id,
    )


def _conflict_id(left: str, right: str) -> str:
    """Derive a replica-independent identifier from an unordered operation pair."""
    pair = "\0".join(sorted((left, right))).encode()
    return hashlib.sha256(pair).hexdigest()


def list_all(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return conflict rows, newest first."""
    return [
        dict(row) for row in connection.execute("SELECT * FROM conflicts ORDER BY detected_at DESC")
    ]


def get(connection: sqlite3.Connection, conflict_id: str) -> dict[str, Any] | None:
    """Load one conflict row by its stable ID."""
    row = connection.execute(
        "SELECT * FROM conflicts WHERE conflict_id=?", (conflict_id,)
    ).fetchone()
    return dict(row) if row else None


def mark_resolved(connection: sqlite3.Connection, conflict_id: str, operation_id: str) -> bool:
    """Mark an open conflict reviewed and retain its resolution operation ID."""
    row = get(connection, conflict_id)
    if row is None or row["status"] != "OPEN":
        return False
    resolution = json.loads(row["resolution"] or "{}")
    resolution["resolution_operation_id"] = operation_id
    connection.execute(
        "UPDATE conflicts SET status='RESOLVED', resolution=? WHERE conflict_id=?",
        (json.dumps(resolution, sort_keys=True), conflict_id),
    )
    return True

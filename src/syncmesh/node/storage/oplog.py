"""SQLite operation-log reads and writes."""

import json
import sqlite3

from syncmesh.protocol.messages import Operation


def vector(connection: sqlite3.Connection) -> dict[str, int]:
    """Return the highest stored sequence for each operation origin."""
    return {
        row["origin_node_id"]: row["origin_seq"]
        for row in connection.execute(
            "SELECT origin_node_id, MAX(origin_seq) AS origin_seq "
            "FROM change_log GROUP BY origin_node_id"
        )
    }


def sequence(connection: sqlite3.Connection, origin: str) -> int:
    """Return the highest stored sequence for one origin."""
    return int(
        connection.execute(
            "SELECT COALESCE(MAX(origin_seq),0) FROM change_log WHERE origin_node_id=?",
            (origin,),
        ).fetchone()[0]
    )


def append(connection: sqlite3.Connection, operation: Operation, received_at: str) -> None:
    """Append an immutable operation to the local log."""
    connection.execute(
        "INSERT INTO change_log(operation_id, origin_node_id, origin_seq, entity_id, "
        "op_type, payload, base_vector, wall_clock, received_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            operation.operation_id,
            operation.origin_node_id,
            operation.origin_seq,
            operation.entity_id,
            operation.op_type.value,
            json.dumps(operation.payload, sort_keys=True),
            json.dumps(operation.base_vector, sort_keys=True),
            operation.wall_clock.isoformat(),
            received_at,
        ),
    )


def since(connection: sqlite3.Connection, version: dict[str, int]) -> list[Operation]:
    """Read operations after the supplied version vector."""
    rows = connection.execute("SELECT * FROM change_log ORDER BY origin_node_id,origin_seq")
    return [
        Operation(
            operation_id=row["operation_id"],
            origin_node_id=row["origin_node_id"],
            origin_seq=row["origin_seq"],
            entity_id=row["entity_id"],
            op_type=row["op_type"],
            payload=json.loads(row["payload"]),
            base_vector=json.loads(row["base_vector"]),
            wall_clock=row["wall_clock"],
        )
        for row in rows
        if row["origin_seq"] > version.get(row["origin_node_id"], 0)
    ]

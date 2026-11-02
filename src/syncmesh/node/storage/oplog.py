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
        "op_type, payload, base_vector, wall_clock, hlc, received_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            operation.operation_id,
            operation.origin_node_id,
            operation.origin_seq,
            operation.entity_id,
            operation.op_type.value,
            json.dumps(operation.payload, sort_keys=True),
            json.dumps(operation.base_vector, sort_keys=True),
            operation.wall_clock.isoformat(),
            json.dumps(
                {"physical_ms": operation.hlc.physical_ms, "logical": operation.hlc.logical},
                sort_keys=True,
            ),
            received_at,
        ),
    )


def since(
    connection: sqlite3.Connection, version: dict[str, int], limit: int = 500
) -> list[Operation]:
    """Read operations after the supplied version vector."""
    if not 1 <= limit <= 500:
        raise ValueError("operation page limit must be between 1 and 500")
    origins = connection.execute(
        "SELECT DISTINCT origin_node_id FROM change_log ORDER BY origin_node_id"
    ).fetchall()
    operations: list[Operation] = []
    remaining = limit
    for origin_row in origins:
        if remaining <= 0:
            break
        origin = origin_row["origin_node_id"]
        rows = connection.execute(
            "SELECT * FROM change_log WHERE origin_node_id=? AND origin_seq>? "
            "ORDER BY origin_seq LIMIT ?",
            (origin, version.get(origin, 0), remaining),
        ).fetchall()
        operations.extend(operation_from_row(row) for row in rows)
        remaining -= len(rows)
    return operations


def operation_from_row(row: sqlite3.Row) -> Operation:
    """Rebuild an operation, including compatibility with pre-HLC log rows."""
    values = {
        "operation_id": row["operation_id"],
        "origin_node_id": row["origin_node_id"],
        "origin_seq": row["origin_seq"],
        "entity_id": row["entity_id"],
        "op_type": row["op_type"],
        "payload": json.loads(row["payload"]),
        "base_vector": json.loads(row["base_vector"]),
        "wall_clock": row["wall_clock"],
    }
    if "hlc" in row.keys() and row["hlc"]:  # noqa: SIM118 - sqlite3.Row needs key membership.
        values["hlc"] = json.loads(row["hlc"])
    return Operation(**values)

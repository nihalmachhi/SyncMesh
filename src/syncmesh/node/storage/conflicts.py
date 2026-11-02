"""SQLite conflict record helpers."""

import json
import sqlite3

from syncmesh.protocol.messages import Operation


def latest_field_edit(
    connection: sqlite3.Connection, entity_id: str
) -> tuple[str, str, str] | None:
    """Return the last locally applied create or field edit ordering key."""
    row = connection.execute(
        "SELECT wall_clock, origin_node_id, operation_id FROM change_log "
        "WHERE entity_id=? AND op_type IN ('create','set_field') "
        "ORDER BY local_id DESC LIMIT 1",
        (entity_id,),
    ).fetchone()
    return (row[0], row[1], row[2]) if row else None


def record_losing_edit(
    connection: sqlite3.Connection,
    operation: Operation,
    previous_key: tuple[str, str, str],
    detected_at: str,
) -> None:
    """Record the conflict in the same way as the original repository path."""
    connection.execute(
        "INSERT OR IGNORE INTO conflicts VALUES(?,?,?,?,?,?,?,?)",
        (
            f"{operation.entity_id}:{operation.operation_id}",
            operation.entity_id,
            ",".join(operation.payload["fields"]),
            ",".join((previous_key[2], operation.operation_id)),
            "deterministic_lww",
            "RESOLVED",
            json.dumps({"winner": previous_key[2]}),
            detected_at,
        ),
    )


def list_all(connection: sqlite3.Connection) -> list[dict]:
    """Return conflict rows, newest first."""
    return [
        dict(row)
        for row in connection.execute("SELECT * FROM conflicts ORDER BY detected_at DESC")
    ]

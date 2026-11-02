"""SQLite projection for replicated inventory entities."""

import json
import sqlite3
from datetime import datetime

from syncmesh.domain.apply import EntityState


def get(connection: sqlite3.Connection, entity_id: str) -> EntityState:
    """Load an entity projection or return its empty initial state."""
    row = connection.execute("SELECT * FROM entities WHERE entity_id=?", (entity_id,)).fetchone()
    if row is None:
        return EntityState(fields={})
    return EntityState(
        fields=json.loads(row["fields"]),
        quantity=int(row["quantity"]),
        is_deleted=bool(row["is_deleted"]),
        entity_vector=json.loads(row["entity_vector"]),
    )


def save(
    connection: sqlite3.Connection,
    entity_id: str,
    state: EntityState,
    updated_at: datetime,
    deleted_operation_id: str | None,
) -> None:
    """Persist the materialized entity state."""
    entity_vector = state.entity_vector or {}
    deleted = state.is_deleted
    connection.execute(
        "INSERT INTO entities(entity_id, fields, quantity, is_deleted, entity_vector, "
        "deleted_vector, deleted_operation_id, updated_at) VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(entity_id) DO UPDATE SET fields=excluded.fields, "
        "quantity=excluded.quantity, is_deleted=excluded.is_deleted, "
        "entity_vector=excluded.entity_vector, deleted_vector=excluded.deleted_vector, "
        "deleted_operation_id=excluded.deleted_operation_id, updated_at=excluded.updated_at",
        (
            entity_id,
            json.dumps(state.fields, sort_keys=True),
            state.quantity,
            int(deleted),
            json.dumps(entity_vector, sort_keys=True),
            json.dumps(entity_vector) if deleted else None,
            deleted_operation_id if deleted else None,
            updated_at.isoformat(),
        ),
    )


def list_items(connection: sqlite3.Connection) -> list[dict]:
    """Return non-deleted entities in stable ID order."""
    rows = connection.execute(
        "SELECT * FROM entities WHERE is_deleted=0 ORDER BY entity_id"
    ).fetchall()
    return [
        {"id": row["entity_id"], **json.loads(row["fields"]), "stock": row["quantity"]}
        for row in rows
    ]

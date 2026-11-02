"""SQLite projection for replicated inventory entities."""

import json
import sqlite3
from datetime import UTC, datetime

from syncmesh.domain.apply import EntityState


def get(connection: sqlite3.Connection, entity_id: str) -> EntityState:
    """Load an entity projection or return its empty initial state."""
    row = connection.execute("SELECT * FROM entities WHERE entity_id=?", (entity_id,)).fetchone()
    if row is None:
        return EntityState(fields={})
    fields = json.loads(row["fields"])
    field_registers = json.loads(row["field_registers"])
    pn_counter = json.loads(row["pn_counter"])
    if not pn_counter and int(row["quantity"]):
        legacy_quantity = int(row["quantity"])
        pn_counter = {
            "legacy": {
                "positive": max(0, legacy_quantity),
                "negative": max(0, -legacy_quantity),
            }
        }
    deleted_vector = json.loads(row["deleted_vector"] or "{}")
    tombstone = json.loads(row["tombstone"]) if row["tombstone"] else None
    if row["is_deleted"]:
        deleted_operation_id = row["deleted_operation_id"] or "legacy:delete"
        tombstone_operation = connection.execute(
            "SELECT origin_node_id, hlc, wall_clock FROM change_log WHERE operation_id=?",
            (deleted_operation_id,),
        ).fetchone()
        tombstone_hlc = {"physical_ms": 0, "logical": 0}
        origin_node_id = deleted_operation_id.split(":", 1)[0]
        if tombstone_operation is not None:
            origin_node_id = tombstone_operation["origin_node_id"]
            if tombstone_operation["hlc"]:
                tombstone_hlc = json.loads(tombstone_operation["hlc"])
            else:
                deleted_at = datetime.fromisoformat(tombstone_operation["wall_clock"]).astimezone(
                    UTC
                )
                tombstone_hlc["physical_ms"] = int(deleted_at.timestamp() * 1000)
        tombstone = tombstone or {
            "vector": deleted_vector,
            "operation_id": deleted_operation_id,
            "origin_node_id": origin_node_id,
            "hlc": tombstone_hlc,
        }
    if not field_registers and fields:
        legacy_timestamp = datetime.fromisoformat(row["updated_at"]).astimezone(UTC)
        legacy_hlc = {"physical_ms": int(legacy_timestamp.timestamp() * 1000), "logical": 0}
        legacy_vector = json.loads(row["entity_vector"])
        field_registers = {
            name: {
                "value": value,
                "vector": legacy_vector,
                "hlc": legacy_hlc,
                "origin_node_id": "legacy",
                "operation_id": f"legacy:{entity_id}",
            }
            for name, value in fields.items()
        }
    return EntityState(
        fields=fields,
        quantity=int(row["quantity"]),
        is_deleted=bool(row["is_deleted"]),
        entity_vector=json.loads(row["entity_vector"]),
        field_registers=field_registers,
        pn_counter=pn_counter,
        tombstone=tombstone,
    )


def save(
    connection: sqlite3.Connection,
    entity_id: str,
    state: EntityState,
    updated_at: datetime,
) -> None:
    """Persist the materialized entity state."""
    entity_vector = state.entity_vector or {}
    deleted = state.is_deleted
    connection.execute(
        "INSERT INTO entities(entity_id, fields, field_registers, quantity, is_deleted, "
        "entity_vector, deleted_vector, deleted_operation_id, pn_counter, tombstone, updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(entity_id) DO UPDATE SET fields=excluded.fields, "
        "field_registers=excluded.field_registers, "
        "quantity=excluded.quantity, is_deleted=excluded.is_deleted, "
        "entity_vector=excluded.entity_vector, deleted_vector=excluded.deleted_vector, "
        "deleted_operation_id=excluded.deleted_operation_id, "
        "pn_counter=excluded.pn_counter, tombstone=excluded.tombstone, "
        "updated_at=excluded.updated_at",
        (
            entity_id,
            json.dumps(state.fields, sort_keys=True),
            json.dumps(state.field_registers, sort_keys=True),
            state.quantity,
            int(deleted),
            json.dumps(entity_vector, sort_keys=True),
            json.dumps(state.tombstone["vector"], sort_keys=True)
            if deleted and state.tombstone
            else None,
            state.tombstone["operation_id"] if deleted and state.tombstone else None,
            json.dumps(state.pn_counter, sort_keys=True),
            json.dumps(state.tombstone, sort_keys=True) if state.tombstone else None,
            updated_at.isoformat(),
        ),
    )


def list_items(connection: sqlite3.Connection) -> list[dict]:
    """Return non-deleted entities in stable ID order."""
    rows = connection.execute(
        "SELECT * FROM entities WHERE is_deleted=0 ORDER BY entity_id"
    ).fetchall()
    items = []
    for row in rows:
        stock = int(row["quantity"])
        items.append(
            {
                "id": row["entity_id"],
                **json.loads(row["fields"]),
                "stock": stock,
                "oversold": stock < 0,
            }
        )
    return items

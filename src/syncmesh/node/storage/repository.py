from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from syncmesh.protocol.messages import Operation, OpType
from syncmesh.protocol.version_vector import CausalOrder, compare, merge


class Repository:
    def __init__(self, db, node_id: str):
        self.db = db
        self.node_id = node_id
        with self.db.connect() as con:
            con.execute("INSERT OR IGNORE INTO node_state(node_id) VALUES (?)", (node_id,))

    @staticmethod
    def vector(con: sqlite3.Connection) -> dict[str, int]:
        return {
            r["origin_node_id"]: r["origin_seq"]
            for r in con.execute(
                "SELECT origin_node_id, MAX(origin_seq) AS origin_seq "
                "FROM change_log GROUP BY origin_node_id"
            )
        }

    def create(self, fields: dict, quantity: int = 0, entity_id: str | None = None) -> str:
        entity_id = entity_id or uuid4().hex
        self.local(entity_id, OpType.CREATE, {"fields": fields, "quantity": quantity})
        return entity_id

    def set_fields(self, entity_id: str, fields: dict) -> None:
        self.local(entity_id, OpType.SET_FIELD, {"fields": fields})

    def adjust(self, entity_id: str, delta: int) -> None:
        self.local(entity_id, OpType.ADJUST_QUANTITY, {"delta": delta})

    def delete(self, entity_id: str) -> None:
        self.local(entity_id, OpType.DELETE, {})

    def local(self, entity_id: str, kind: OpType, payload: dict) -> Operation:
        with self.db.connect() as con:
            state = con.execute(
                "SELECT local_seq FROM node_state WHERE node_id=?", (self.node_id,)
            ).fetchone()
            seq = int(state[0]) + 1
            vector = self.vector(con)
            op = Operation(
                operation_id=f"{self.node_id}:{seq}",
                origin_node_id=self.node_id,
                origin_seq=seq,
                entity_id=entity_id,
                op_type=kind,
                payload=payload,
                base_vector=vector,
                wall_clock=datetime.now(UTC),
            )
            self._apply(con, op)
            con.execute("UPDATE node_state SET local_seq=? WHERE node_id=?", (seq, self.node_id))
        return op

    def receive(self, op: Operation) -> bool:
        with self.db.connect() as con:
            if con.execute(
                "SELECT 1 FROM change_log WHERE operation_id=?", (op.operation_id,)
            ).fetchone():
                return False
            have = int(
                con.execute(
                    "SELECT COALESCE(MAX(origin_seq),0) FROM change_log WHERE origin_node_id=?",
                    (op.origin_node_id,),
                ).fetchone()[0]
            )
            if op.origin_seq > have + 1:
                con.execute(
                    "INSERT OR IGNORE INTO pending_ops VALUES(?,?,?,?)",
                    (op.operation_id, op.origin_node_id, op.origin_seq, op.model_dump_json()),
                )
                return False
            if op.origin_seq <= have:
                return False
            self._apply(con, op)
            while True:
                next_row = con.execute(
                    "SELECT raw_operation FROM pending_ops WHERE origin_node_id=? AND origin_seq=?",
                    (op.origin_node_id, self._seq(con, op.origin_node_id) + 1),
                ).fetchone()
                if not next_row:
                    break
                queued = Operation.model_validate_json(next_row[0])
                con.execute("DELETE FROM pending_ops WHERE operation_id=?", (queued.operation_id,))
                self._apply(con, queued)
        return True

    @staticmethod
    def _seq(con, origin):
        return int(
            con.execute(
                "SELECT COALESCE(MAX(origin_seq),0) FROM change_log WHERE origin_node_id=?",
                (origin,),
            ).fetchone()[0]
        )

    def _apply(self, con, op: Operation) -> None:
        now = datetime.now(UTC).isoformat()
        con.execute(
            "INSERT INTO change_log(operation_id, origin_node_id, origin_seq, entity_id, "
            "op_type, payload, base_vector, wall_clock, received_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                op.operation_id,
                op.origin_node_id,
                op.origin_seq,
                op.entity_id,
                op.op_type.value,
                json.dumps(op.payload, sort_keys=True),
                json.dumps(op.base_vector, sort_keys=True),
                op.wall_clock.isoformat(),
                now,
            ),
        )
        row = con.execute("SELECT * FROM entities WHERE entity_id=?", (op.entity_id,)).fetchone()
        fields = json.loads(row["fields"]) if row else {}
        qty = int(row["quantity"]) if row else 0
        deleted = bool(row["is_deleted"]) if row else False
        ev = json.loads(row["entity_vector"]) if row else {}
        if op.op_type is OpType.CREATE:
            fields.update(op.payload["fields"])
            qty += int(op.payload.get("quantity", 0))
            deleted = False
        elif op.op_type is OpType.SET_FIELD:
            relation = compare(op.base_vector, ev)
            incoming = (op.wall_clock.isoformat(), op.origin_node_id, op.operation_id)
            old = con.execute(
                "SELECT wall_clock, origin_node_id, operation_id FROM change_log "
                "WHERE entity_id=? AND op_type IN ('create','set_field') "
                "ORDER BY local_id DESC LIMIT 1",
                (op.entity_id,),
            ).fetchone()
            old_key = (old[0], old[1], old[2]) if old else ("", "", "")
            if (
                relation is CausalOrder.AFTER
                or relation is CausalOrder.EQUAL
                or (relation is CausalOrder.CONCURRENT and incoming > old_key)
            ):
                fields.update(op.payload["fields"])
            elif relation is CausalOrder.CONCURRENT:
                cid = f"{op.entity_id}:{op.operation_id}"
                con.execute(
                    "INSERT OR IGNORE INTO conflicts VALUES(?,?,?,?,?,?,?,?)",
                    (
                        cid,
                        op.entity_id,
                        ",".join(op.payload["fields"]),
                        json.dumps([old[2], op.operation_id]),
                        "deterministic_lww",
                        "RESOLVED",
                        json.dumps({"winner": old[2]}),
                        now,
                    ),
                )
        elif op.op_type is OpType.ADJUST_QUANTITY:
            qty += int(op.payload["delta"])
        elif op.op_type is OpType.DELETE:
            deleted = True
        ev = merge(ev, op.base_vector, {op.origin_node_id: op.origin_seq})
        con.execute(
            "INSERT INTO entities(entity_id, fields, quantity, is_deleted, entity_vector, "
            "deleted_vector, deleted_operation_id, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(entity_id) DO UPDATE SET "
            "fields=excluded.fields, quantity=excluded.quantity, "
            "is_deleted=excluded.is_deleted, entity_vector=excluded.entity_vector, "
            "deleted_vector=excluded.deleted_vector, "
            "deleted_operation_id=excluded.deleted_operation_id, updated_at=excluded.updated_at",
            (
                op.entity_id,
                json.dumps(fields, sort_keys=True),
                qty,
                int(deleted),
                json.dumps(ev, sort_keys=True),
                json.dumps(ev) if deleted else None,
                op.operation_id if deleted else None,
                now,
            ),
        )

    def items(self):
        with self.db.connect() as con:
            rows = con.execute(
                "SELECT * FROM entities WHERE is_deleted=0 ORDER BY entity_id"
            ).fetchall()
        return [
            {"id": r["entity_id"], **json.loads(r["fields"]), "stock": r["quantity"]} for r in rows
        ]

    def conflicts(self):
        with self.db.connect() as con:
            rows = con.execute("SELECT * FROM conflicts ORDER BY detected_at DESC").fetchall()
        return [dict(r) for r in rows]

    def stats(self):
        with self.db.connect() as con:
            return {
                "operations": con.execute("SELECT COUNT(*) FROM change_log").fetchone()[0],
                "pending": con.execute("SELECT COUNT(*) FROM pending_ops").fetchone()[0],
                "conflicts": con.execute(
                    "SELECT COUNT(*) FROM conflicts WHERE status='OPEN'"
                ).fetchone()[0],
                "vector": self.vector(con),
            }

    def since(self, vector):
        with self.db.connect() as con:
            rows = con.execute(
                "SELECT * FROM change_log ORDER BY origin_node_id,origin_seq"
            ).fetchall()
        return [
            Operation(
                operation_id=r["operation_id"],
                origin_node_id=r["origin_node_id"],
                origin_seq=r["origin_seq"],
                entity_id=r["entity_id"],
                op_type=r["op_type"],
                payload=json.loads(r["payload"]),
                base_vector=json.loads(r["base_vector"]),
                wall_clock=r["wall_clock"],
            )
            for r in rows
            if r["origin_seq"] > vector.get(r["origin_node_id"], 0)
        ]

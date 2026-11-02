"""Pure inventory transition function used by the SQLite write path."""

from dataclasses import dataclass
from typing import Any

from syncmesh.protocol.messages import Operation, OpType
from syncmesh.protocol.version_vector import CausalOrder


@dataclass(frozen=True)
class EntityState:
    """An inventory projection plus its causal vector."""

    fields: dict[str, Any]
    quantity: int = 0
    is_deleted: bool = False
    entity_vector: dict[str, int] | None = None


def apply_operation(
    state: EntityState,
    operation: Operation,
    relation: CausalOrder | None = None,
    previous_key: tuple[str, str, str] | None = None,
) -> tuple[EntityState, bool]:
    """Apply one operation without I/O; return the new state and conflict flag."""
    fields = dict(state.fields)
    quantity = state.quantity
    is_deleted = state.is_deleted
    conflict = False

    if operation.op_type is OpType.CREATE:
        fields.update(operation.payload["fields"])
        quantity += int(operation.payload.get("quantity", 0))
        is_deleted = False
    elif operation.op_type is OpType.SET_FIELD:
        order = relation or CausalOrder.EQUAL
        incoming_key = (
            operation.wall_clock.isoformat(),
            operation.origin_node_id,
            operation.operation_id,
        )
        last_key = previous_key or ("", "", "")
        if (
            order in (CausalOrder.AFTER, CausalOrder.EQUAL)
            or (order is CausalOrder.CONCURRENT and incoming_key > last_key)
        ):
            fields.update(operation.payload["fields"])
        elif order is CausalOrder.CONCURRENT:
            conflict = True
    elif operation.op_type is OpType.ADJUST_QUANTITY:
        quantity += int(operation.payload["delta"])
    elif operation.op_type is OpType.DELETE:
        is_deleted = True

    return (
        EntityState(
            fields=fields,
            quantity=quantity,
            is_deleted=is_deleted,
            entity_vector=dict(state.entity_vector or {}),
        ),
        conflict,
    )

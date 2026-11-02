"""Pure inventory transition function used by the SQLite write path."""

from dataclasses import dataclass, field
from typing import Any

from syncmesh.protocol.messages import Operation, OpType
from syncmesh.protocol.version_vector import CausalOrder, compare, merge


@dataclass(frozen=True)
class EntityState:
    """An inventory projection plus its causal vector."""

    fields: dict[str, Any]
    quantity: int = 0
    is_deleted: bool = False
    entity_vector: dict[str, int] | None = None
    field_registers: dict[str, dict[str, Any]] = field(default_factory=dict)


def apply_operation(
    state: EntityState,
    operation: Operation,
    relation: CausalOrder | None = None,
    previous_key: tuple[str, str, str] | None = None,
) -> tuple[EntityState, list[tuple[str, dict[str, Any], dict[str, Any]]]]:
    """Apply one operation without I/O using a register for each edited field."""
    fields = dict(state.fields)
    registers = {key: dict(value) for key, value in state.field_registers.items()}
    quantity = state.quantity
    is_deleted = state.is_deleted
    conflicts: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    if operation.op_type is OpType.CREATE:
        quantity += int(operation.payload.get("quantity", 0))
        is_deleted = False
    elif operation.op_type is OpType.ADJUST_QUANTITY:
        quantity += int(operation.payload["delta"])
    elif operation.op_type is OpType.DELETE:
        is_deleted = True

    if operation.op_type in (OpType.CREATE, OpType.SET_FIELD):
        operation_vector = merge(
            operation.base_vector, {operation.origin_node_id: operation.origin_seq}
        )
        incoming_key = (
            operation.hlc.physical_ms,
            operation.hlc.logical,
            operation.origin_node_id,
            operation.operation_id,
        )
        for field_name, value in operation.payload["fields"].items():
            incoming = {
                "value": value,
                "vector": operation_vector,
                "hlc": {
                    "physical_ms": operation.hlc.physical_ms,
                    "logical": operation.hlc.logical,
                },
                "origin_node_id": operation.origin_node_id,
                "operation_id": operation.operation_id,
            }
            current = registers.get(field_name)
            should_apply = current is None
            if current is not None:
                order = compare(operation_vector, current["vector"])
                current_hlc = current["hlc"]
                current_key = (
                    current_hlc["physical_ms"],
                    current_hlc["logical"],
                    current["origin_node_id"],
                    current["operation_id"],
                )
                if order in (CausalOrder.AFTER, CausalOrder.EQUAL):
                    should_apply = True
                elif order is CausalOrder.CONCURRENT:
                    conflicts.append((field_name, current, incoming))
                    should_apply = incoming_key > current_key
            if should_apply:
                registers[field_name] = incoming
                fields[field_name] = value

    return (
        EntityState(
            fields=fields,
            quantity=quantity,
            is_deleted=is_deleted,
            entity_vector=dict(state.entity_vector or {}),
            field_registers=registers,
        ),
        conflicts,
    )

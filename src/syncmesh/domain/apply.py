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
    pn_counter: dict[str, dict[str, int]] = field(default_factory=dict)
    tombstone: dict[str, Any] | None = None


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
    counter = {node: dict(values) for node, values in state.pn_counter.items()}
    tombstone = dict(state.tombstone) if state.tombstone else None
    is_deleted = tombstone is not None or state.is_deleted
    conflicts: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    if operation.op_type is OpType.CREATE:
        _add_to_counter(
            counter, operation.origin_node_id, int(operation.payload.get("quantity", 0))
        )
    elif operation.op_type is OpType.ADJUST_QUANTITY:
        _add_to_counter(counter, operation.origin_node_id, int(operation.payload["delta"]))
    elif operation.op_type is OpType.DELETE:
        incoming_tombstone = {
            "vector": merge(
                operation.base_vector, {operation.origin_node_id: operation.origin_seq}
            ),
            "operation_id": operation.operation_id,
            "origin_node_id": operation.origin_node_id,
            "hlc": {
                "physical_ms": operation.hlc.physical_ms,
                "logical": operation.hlc.logical,
            },
        }
        if tombstone is None or _tombstone_key(incoming_tombstone) > _tombstone_key(tombstone):
            tombstone = incoming_tombstone
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
                if order is CausalOrder.CONCURRENT:
                    conflicts.append((field_name, current, incoming))
                # The register is a max-register over the complete timestamp key.
                # Causal descendants can be concurrent with a different writer and
                # may have a lower clock; replacing the winner by arrival/causality
                # would lose the actual maximum and break convergence.
                should_apply = incoming_key > current_key
            if should_apply:
                registers[field_name] = incoming
                fields[field_name] = value

    quantity = sum(parts["positive"] - parts["negative"] for parts in counter.values())
    return (
        EntityState(
            fields=fields,
            quantity=quantity,
            is_deleted=is_deleted,
            entity_vector=dict(state.entity_vector or {}),
            field_registers=registers,
            pn_counter=counter,
            tombstone=tombstone,
        ),
        conflicts,
    )


def _add_to_counter(counter: dict[str, dict[str, int]], node_id: str, delta: int) -> None:
    """Accumulate a positive or negative per-node component."""
    parts = counter.setdefault(node_id, {"positive": 0, "negative": 0})
    component = "positive" if delta >= 0 else "negative"
    parts[component] += abs(delta)


def _tombstone_key(tombstone: dict[str, Any]) -> tuple[int, int, str, str]:
    """Order concurrent deletion markers deterministically."""
    hlc = tombstone["hlc"]
    return (
        hlc["physical_ms"],
        hlc["logical"],
        tombstone["origin_node_id"],
        tombstone["operation_id"],
    )

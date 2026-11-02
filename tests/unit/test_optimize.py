"""Operation byte-budget selection and causal-prefix guarantees."""

from datetime import UTC, datetime

from syncmesh.protocol.hlc import HLC
from syncmesh.protocol.messages import Operation, OpType
from syncmesh.protocol.optimize import encoded_size, select_operations


def event(origin: str, sequence: int, kind: OpType, base: dict[str, int]) -> Operation:
    """Make one operation with a deterministic approximate payload size."""
    payload = (
        {"fields": {"name": "A long descriptive catalog item name"}}
        if kind is OpType.SET_FIELD
        else {"delta": 1}
        if kind is OpType.ADJUST_QUANTITY
        else {"fields": {"name": "Tea"}, "quantity": 1}
        if kind is OpType.CREATE
        else {}
    )
    return Operation(
        operation_id=f"{origin}:{sequence}",
        origin_node_id=origin,
        origin_seq=sequence,
        entity_id="item",
        op_type=kind,
        payload=payload,
        base_vector=base,
        hlc=HLC(1000 + sequence, 0),
        wall_clock=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_selection_respects_causal_prefix_and_byte_limit():
    """A later same-origin operation cannot jump a missing predecessor."""
    operations = [
        event("a", 1, OpType.CREATE, {}),
        event("a", 2, OpType.SET_FIELD, {"a": 1}),
        event("b", 1, OpType.DELETE, {"a": 1}),
    ]

    selected = select_operations(operations, {}, byte_budget=10_000)

    assert {operation.operation_id for operation in selected} == {"a:1", "a:2", "b:1"}
    assert select_operations(operations, {}, byte_budget=1) == [operations[0]]


def test_value_per_byte_prioritizes_deletes_while_preserving_progress():
    """High-value operations can go first without losing origin sequencing."""
    operations = [
        event("a", 1, OpType.SET_FIELD, {}),
        event("a", 2, OpType.DELETE, {"a": 1}),
        event("b", 1, OpType.ADJUST_QUANTITY, {}),
    ]
    budget = encoded_size(operations[0]) + encoded_size(operations[2]) + 2

    fifo = select_operations(operations, {}, budget, "fifo")
    prioritized = select_operations(operations, {}, budget, "value_per_byte")

    assert fifo[0].operation_id == "a:1"
    assert prioritized[0].operation_id == "b:1"
    selected_ids = {operation.operation_id for operation in prioritized}
    assert "a:2" not in selected_ids or "a:1" in selected_ids

"""Causal-prefix operation selection under a peer exchange byte budget."""

from syncmesh.protocol.messages import Operation, OpType

_PRIORITY = {
    OpType.DELETE: 4.0,
    OpType.CREATE: 3.0,
    OpType.ADJUST_QUANTITY: 2.0,
    OpType.SET_FIELD: 1.0,
}


def encoded_size(operation: Operation) -> int:
    """Estimate its JSON wire size in UTF-8 bytes."""
    return len(operation.model_dump_json().encode("utf-8"))


def select_operations(
    operations: list[Operation],
    peer_vector: dict[str, int],
    byte_budget: int,
    strategy: str = "value_per_byte",
) -> list[Operation]:
    """Select a causal prefix fitting a byte budget using FIFO or greedy priority."""
    if byte_budget < 1:
        raise ValueError("byte budget must be positive")
    if strategy not in {"fifo", "value_per_byte"}:
        raise ValueError("strategy must be 'fifo' or 'value_per_byte'")
    ordered = sorted(operations, key=lambda op: (op.origin_node_id, op.origin_seq))
    selected: list[Operation] = []
    selected_by_origin: dict[str, int] = {}
    selected_ids: set[str] = set()
    used_bytes = 0
    remaining = ordered[:]
    while remaining:
        ready = [
            operation
            for operation in remaining
            if operation.origin_seq
            == peer_vector.get(operation.origin_node_id, 0)
            + selected_by_origin.get(operation.origin_node_id, 0)
            + 1
            and all(
                sequence <= peer_vector.get(origin, 0) + selected_by_origin.get(origin, 0)
                for origin, sequence in operation.base_vector.items()
            )
        ]
        if not ready:
            break
        if strategy == "fifo":
            candidate = ready[0]
        else:
            candidate = max(
                ready,
                key=lambda operation: (
                    _PRIORITY[operation.op_type] / max(1, encoded_size(operation)),
                    operation.operation_id,
                ),
            )
        size = encoded_size(candidate)
        if used_bytes + size > byte_budget:
            fitting = [
                operation
                for operation in ready
                if used_bytes + encoded_size(operation) <= byte_budget
            ]
            if not fitting:
                if selected:
                    break
                # Permit one oversized operation to prevent permanent starvation.
                candidate = ready[0]
                size = encoded_size(candidate)
            else:
                candidate = (
                    fitting[0]
                    if strategy == "fifo"
                    else max(
                        fitting,
                        key=lambda operation: (
                            _PRIORITY[operation.op_type] / max(1, encoded_size(operation)),
                            operation.operation_id,
                        ),
                    )
                )
                size = encoded_size(candidate)
        selected.append(candidate)
        selected_ids.add(candidate.operation_id)
        selected_by_origin[candidate.origin_node_id] = (
            selected_by_origin.get(candidate.origin_node_id, 0) + 1
        )
        used_bytes += size
        remaining = [
            operation for operation in remaining if operation.operation_id not in selected_ids
        ]
    return selected


def compare_selection(operations: list[Operation], byte_budget: int) -> dict:
    """Compare causal FIFO and value-per-byte page contents on fixed operations."""
    fifo = select_operations(operations, {}, byte_budget, "fifo")
    prioritized = select_operations(operations, {}, byte_budget, "value_per_byte")
    return {
        "synthetic_operations": len(operations),
        "byte_budget": byte_budget,
        "fifo": {
            "selected": len(fifo),
            "estimated_bytes": sum(encoded_size(operation) for operation in fifo),
        },
        "value_per_byte": {
            "selected": len(prioritized),
            "estimated_bytes": sum(encoded_size(operation) for operation in prioritized),
            "operation_ids": [operation.operation_id for operation in prioritized],
        },
        "synthetic": True,
    }

"""Reproducible concurrent edit schedules over independent replicas."""

from datetime import UTC, datetime
from typing import Any

from syncmesh.domain.apply import EntityState, apply_operation
from syncmesh.protocol.hlc import HybridLogicalClock
from syncmesh.protocol.messages import Operation, OpType
from syncmesh.simulation.prng import Mulberry32


def run_schedule(seed: int, nodes: int = 3, operations_per_node: int = 4) -> dict:
    """Replay one seeded concurrent write schedule and report convergence."""
    random = Mulberry32(seed)
    operation_set: list[Operation] = []
    clock_values: dict[str, int] = {}
    clocks: dict[str, HybridLogicalClock] = {}
    fields = ("name", "category", "price")
    for node_index in range(nodes):
        origin = f"node-{node_index}"
        for sequence in range(1, operations_per_node + 1):
            is_create = node_index == 0 and sequence == 1
            is_adjustment = not is_create and random.random() < 0.25
            if is_adjustment:
                op_type = OpType.ADJUST_QUANTITY
                payload: dict[str, Any] = {"delta": random.randrange(9) - 4}
            else:
                field_name = fields[random.randrange(len(fields))]
                value = (
                    f"item-{random.randrange(20)}"
                    if field_name != "price"
                    else random.randrange(10_000) / 100
                )
                op_type = OpType.CREATE if is_create else OpType.SET_FIELD
                payload = (
                    {
                        "fields": {"name": "base item", "category": "General", "price": 1.0},
                        "quantity": 10,
                    }
                    if is_create
                    else {"fields": {field_name: value}}
                )
            base_vector = {origin: sequence - 1} if sequence > 1 else {}
            if node_index > 0:
                base_vector["node-0"] = 1
            physical_ms = 1_800_000_000_000 + random.randrange(500)
            clock_values[origin] = physical_ms
            if origin not in clocks:

                def clock_reader(node: str = origin) -> int:
                    return clock_values[node]

                clocks[origin] = HybridLogicalClock(clock_ms=clock_reader)
            operation_set.append(
                Operation(
                    operation_id=f"{origin}:{sequence}",
                    origin_node_id=origin,
                    origin_seq=sequence,
                    entity_id="simulated-item",
                    op_type=op_type,
                    payload=payload,
                    base_vector=base_vector,
                    hlc=clocks[origin].tick(),
                    wall_clock=datetime.fromtimestamp(physical_ms / 1000, UTC),
                )
            )

    order = list(range(len(operation_set)))
    for index in range(len(order) - 1, 0, -1):
        swap_index = random.randrange(index + 1)
        order[index], order[swap_index] = order[swap_index], order[index]
    deliveries = [operation_set[index] for index in order]
    if deliveries:
        deliveries.insert(random.randrange(len(deliveries) + 1), deliveries[0])

    state = _deliver_with_causal_buffer(deliveries)
    replicas = [_replay(operation_set, random) for _ in range(3)]
    converged = all(replica.fields == state.fields for replica in replicas)
    converged = converged and all(replica.quantity == state.quantity for replica in replicas)
    result = {
        "seed": seed,
        "operations": len(operation_set),
        "duplicate_deliveries": len(deliveries) - len(operation_set),
        "converged": converged,
        "state": state.fields,
        "stock": state.quantity,
    }
    if not converged:
        result["replica_fields"] = [replica.fields for replica in replicas]
        result["field_registers"] = [replica.field_registers for replica in [state, *replicas]]
        result["price_operations"] = [
            operation.model_dump(mode="json")
            for operation in operation_set
            if "price" in operation.payload.get("fields", {})
        ]
    return result


def _replay(operations: list[Operation], random: Mulberry32) -> EntityState:
    """Apply the same operation set in another independently shuffled order."""
    indexes = list(range(len(operations)))
    for index in range(len(indexes) - 1, 0, -1):
        other = random.randrange(index + 1)
        indexes[index], indexes[other] = indexes[other], indexes[index]
    deliveries = [operations[index] for index in indexes]
    if deliveries:
        deliveries.insert(random.randrange(len(deliveries) + 1), deliveries[0])
    return _deliver_with_causal_buffer(deliveries)


def _deliver_with_causal_buffer(deliveries: list[Operation]) -> EntityState:
    """Apply each operation once and wait until its vector context is available."""
    state = EntityState(fields={})
    vector: dict[str, int] = {}
    pending: dict[str, Operation] = {}
    applied: set[str] = set()
    for operation in deliveries:
        if operation.operation_id not in applied:
            pending.setdefault(operation.operation_id, operation)
        while True:
            ready = sorted(
                (
                    candidate
                    for candidate in pending.values()
                    if candidate.origin_seq == vector.get(candidate.origin_node_id, 0) + 1
                    and all(
                        vector.get(origin, 0) >= sequence
                        for origin, sequence in candidate.base_vector.items()
                    )
                ),
                key=lambda candidate: (candidate.origin_node_id, candidate.origin_seq),
            )
            if not ready:
                break
            current = ready[0]
            state, _ = apply_operation(state, current)
            vector[current.origin_node_id] = current.origin_seq
            applied.add(current.operation_id)
            pending.pop(current.operation_id)
    if pending:
        raise ValueError("simulated schedule ended before causal dependencies arrived")
    return state


def run_simulation(seed: int = 1, schedules: int = 1000) -> dict:
    """Run a deterministic suite and count schedules that satisfy invariants."""
    if schedules < 1:
        raise ValueError("schedules must be at least one")
    outcomes = [run_schedule(seed + offset) for offset in range(schedules)]
    failures = [outcome["seed"] for outcome in outcomes if not outcome["converged"]]
    return {
        "seed": seed,
        "schedules_run": schedules,
        "converged": schedules - len(failures),
        "failed_seeds": failures,
        "all_converged": not failures,
    }

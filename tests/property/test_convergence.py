"""Randomized convergence checks for concurrent field-register updates."""

from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from syncmesh.domain.apply import EntityState, apply_operation
from syncmesh.protocol.messages import Operation, OpType


@given(
    st.lists(
        st.tuples(
            st.sampled_from(("node-b", "node-c", "node-d", "node-e")),
            st.sampled_from(("name", "category", "price")),
            st.integers(min_value=0, max_value=50),
            st.integers(min_value=1, max_value=20),
        ),
        min_size=1,
        max_size=4,
        unique_by=lambda value: value[0],
    )
)
@settings(max_examples=60, deadline=None)
def test_concurrent_register_updates_converge_with_permutations_and_duplicates(changes):
    """Concurrent field updates converge for any delivery order and duplication."""
    create = Operation(
        operation_id="node-a:1",
        origin_node_id="node-a",
        origin_seq=1,
        entity_id="property-item",
        op_type=OpType.CREATE,
        payload={"fields": {"name": "base", "category": "base", "price": 0}},
        base_vector={},
        wall_clock=datetime(2026, 1, 1, tzinfo=UTC),
    )
    operations = [
        Operation(
            operation_id=f"{origin}:1",
            origin_node_id=origin,
            origin_seq=1,
            entity_id="property-item",
            op_type=OpType.SET_FIELD,
            payload={"fields": {field: value}},
            base_vector={"node-a": 1},
            wall_clock=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(milliseconds=tick),
        )
        for origin, field, value, tick in changes
    ]

    states = []
    delivery_orders = [operations, list(reversed(operations))]
    for order in delivery_orders:
        state = EntityState(fields={})
        state, _ = apply_operation(state, create)
        for operation in order + order[:1]:
            state, _ = apply_operation(state, operation)
        states.append(state)

    assert states[0].fields == states[1].fields
    assert states[0].field_registers == states[1].field_registers

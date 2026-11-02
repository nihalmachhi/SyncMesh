"""Content hash range stability and divergence detection."""

from datetime import UTC, datetime

from syncmesh.protocol.digest import differing_ranges, range_digests
from syncmesh.protocol.hlc import HLC
from syncmesh.protocol.messages import Operation, OpType


def make_operation(sequence: int, value: str) -> Operation:
    """Build an operation with a deterministic content value."""
    return Operation(
        operation_id=f"node-a:{sequence}",
        origin_node_id="node-a",
        origin_seq=sequence,
        entity_id="item",
        op_type=OpType.SET_FIELD,
        payload={"fields": {"name": value}},
        base_vector={"node-a": sequence - 1} if sequence > 1 else {},
        hlc=HLC(1000 + sequence, 0),
        wall_clock=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_digest_identifies_missing_and_different_operation_ranges():
    """Same ranges compare equal; changed or missing ranges are reported."""
    source = range_digests([make_operation(1, "rice"), make_operation(2, "beans")], 1)
    same = range_digests([make_operation(1, "rice"), make_operation(2, "beans")], 1)
    changed = range_digests([make_operation(1, "rice"), make_operation(2, "corn")], 1)

    assert differing_ranges(source, same) == []
    assert differing_ranges(source, changed) == [{"origin": "node-a", "start": 2}]
    assert differing_ranges(source, {"node-a": source["node-a"][:1]}) == [
        {"origin": "node-a", "start": 2}
    ]

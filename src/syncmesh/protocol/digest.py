"""Content digests for bounded per-origin operation-log ranges."""

import hashlib
import json
from collections import defaultdict

from syncmesh.protocol.messages import Operation


def range_digests(operations: list[Operation], range_size: int = 128) -> dict[str, list[dict]]:
    """Hash fixed-size ranges within each origin's immutable sequence."""
    if range_size < 1:
        raise ValueError("range_size must be positive")
    grouped: dict[str, list[Operation]] = defaultdict(list)
    for operation in operations:
        grouped[operation.origin_node_id].append(operation)
    result: dict[str, list[dict]] = {}
    for origin, events in sorted(grouped.items()):
        events.sort(key=lambda operation: operation.origin_seq)
        ranges = []
        for offset in range(0, len(events), range_size):
            chunk = events[offset : offset + range_size]
            serialized = [json.loads(operation.model_dump_json()) for operation in chunk]
            digest = hashlib.sha256(
                json.dumps(serialized, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            ranges.append(
                {
                    "start": chunk[0].origin_seq,
                    "end": chunk[-1].origin_seq,
                    "count": len(chunk),
                    "sha256": digest,
                }
            )
        result[origin] = ranges
    return result


def differing_ranges(left: dict[str, list[dict]], right: dict[str, list[dict]]) -> list[dict]:
    """List ranges whose digest differs or is absent on either side."""
    differences = []
    for origin in sorted(set(left) | set(right)):
        left_by_start = {int(item["start"]): item for item in left.get(origin, [])}
        right_by_start = {int(item["start"]): item for item in right.get(origin, [])}
        for start in sorted(set(left_by_start) | set(right_by_start)):
            a, b = left_by_start.get(start), right_by_start.get(start)
            if a is None or b is None or a["sha256"] != b["sha256"] or a["end"] != b["end"]:
                differences.append({"origin": origin, "start": start})
    return differences

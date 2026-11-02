"""Causal directed acyclic graph summaries built from operation contexts."""

from collections import defaultdict, deque

from syncmesh.protocol.messages import Operation


def build_causal_graph(operations: list[Operation], max_nodes: int = 300) -> dict:
    """Summarize operation causality, frontier, chain length, and antichain width."""
    selected = sorted(operations, key=lambda op: (op.origin_node_id, op.origin_seq))[-max_nodes:]
    by_dot = {(op.origin_node_id, op.origin_seq): op.operation_id for op in selected}
    ids = [op.operation_id for op in selected]
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming_count = dict.fromkeys(ids, 0)
    edges: set[tuple[str, str]] = set()
    for operation in selected:
        for origin, sequence in operation.base_vector.items():
            parent = by_dot.get((origin, sequence))
            if parent and parent != operation.operation_id:
                edges.add((parent, operation.operation_id))
    for parent, child in edges:
        outgoing[parent].add(child)
        incoming_count[child] += 1

    ready = deque(sorted(node for node, count in incoming_count.items() if count == 0))
    topological: list[str] = []
    depth: dict[str, int] = dict.fromkeys(ids, 1)
    while ready:
        current = ready.popleft()
        topological.append(current)
        for child in sorted(outgoing[current]):
            depth[child] = max(depth[child], depth[current] + 1)
            incoming_count[child] -= 1
            if incoming_count[child] == 0:
                ready.append(child)
    if len(topological) != len(ids):
        raise ValueError("operation contexts contain a causal cycle")

    reachability = _transitive_successors(ids, outgoing)
    width = _poset_width(ids, reachability)
    return {
        "nodes": [
            {
                "id": operation.operation_id,
                "origin": operation.origin_node_id,
                "sequence": operation.origin_seq,
                "entity": operation.entity_id,
                "type": operation.op_type.value,
            }
            for operation in selected
        ],
        "edges": [{"from": parent, "to": child} for parent, child in sorted(edges)],
        "topological_order": topological,
        "frontier": sorted(node for node in ids if not outgoing[node]),
        "antichain_width": width,
        "longest_chain": max(depth.values(), default=0),
        "truncated": len(operations) > max_nodes,
        "operation_count": len(selected),
    }


def _transitive_successors(nodes: list[str], outgoing: dict[str, set[str]]) -> dict[str, set[str]]:
    """Return reachable successors for each operation node."""
    result: dict[str, set[str]] = {}
    for node in nodes:
        seen: set[str] = set()
        pending = list(outgoing[node])
        while pending:
            child = pending.pop()
            if child not in seen:
                seen.add(child)
                pending.extend(outgoing[child])
        result[node] = seen
    return result


def _poset_width(nodes: list[str], successors: dict[str, set[str]]) -> int:
    """Compute maximum antichain size using Dilworth's bipartite matching form."""
    matches: dict[str, str] = {}

    def augment(left: str, visited: set[str]) -> bool:
        for right in sorted(successors[left]):
            if right in visited:
                continue
            visited.add(right)
            if right not in matches or augment(matches[right], visited):
                matches[right] = left
                return True
        return False

    matching = sum(augment(node, set()) for node in nodes)
    return len(nodes) - matching

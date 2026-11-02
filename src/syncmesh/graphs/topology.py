"""Peer topology construction and network partition detection."""


def connected_components(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Return deterministically ordered connected components of an undirected graph."""
    neighbors: dict[str, set[str]] = {node: set() for node in nodes}
    for left, right in edges:
        if left in neighbors and right in neighbors:
            neighbors[left].add(right)
            neighbors[right].add(left)
    components: list[list[str]] = []
    remaining = set(nodes)
    while remaining:
        start = min(remaining)
        component = {start}
        frontier = [start]
        remaining.remove(start)
        while frontier:
            current = frontier.pop()
            for neighbor in neighbors[current] & remaining:
                component.add(neighbor)
                remaining.remove(neighbor)
                frontier.append(neighbor)
        components.append(sorted(component))
    return components


def topology_from_peers(peers: dict[str, list[str]], offline: set[str] | None = None) -> dict:
    """Build a display-ready graph and connected components after failures."""
    offline = offline or set()
    nodes = sorted(set(peers) | {peer for values in peers.values() for peer in values})
    edges = sorted(
        {
            tuple(sorted((node, peer)))
            for node, values in peers.items()
            for peer in values
            if node != peer
        }
    )
    active = [node for node in nodes if node not in offline]
    active_edges = [(a, b) for a, b in edges if a in active and b in active]
    return {
        "nodes": [{"id": node, "online": node not in offline} for node in nodes],
        "edges": [{"from": a, "to": b, "online": (a, b) in active_edges} for a, b in edges],
        "components": connected_components(active, active_edges),
    }

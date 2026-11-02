"""Seeded gossip experiments over common peer network shapes."""

from syncmesh.graphs.topology import connected_components
from syncmesh.simulation.prng import Mulberry32

TOPOLOGIES = ("ring", "star", "erdos_renyi", "small_world")
STRATEGIES = ("random", "round_robin", "push_pull")


def make_topology(kind: str, node_count: int, seed: int) -> list[tuple[int, int]]:
    """Generate an undirected graph for the selected reproducible topology."""
    if node_count < 2:
        raise ValueError("at least two nodes are required")
    if kind not in TOPOLOGIES:
        raise ValueError(f"unknown topology: {kind}")
    rng = Mulberry32(seed)
    edges: set[tuple[int, int]] = set()
    if kind == "ring":
        edges.update(_edge(node, (node + 1) % node_count) for node in range(node_count))
    elif kind == "star":
        edges.update((0, node) for node in range(1, node_count))
    elif kind == "erdos_renyi":
        probability = min(1.0, 2.0 / (node_count - 1))
        for left in range(node_count):
            for right in range(left + 1, node_count):
                if rng.random() < probability:
                    edges.add((left, right))
        # Keep the experiment connected to measure propagation rounds reliably.
        edges.update(_edge(node, node + 1) for node in range(node_count - 1))
    else:
        for node in range(node_count):
            for offset in (1, 2):
                edges.add(_edge(node, (node + offset) % node_count))
        for left, right in list(edges):
            if rng.random() < 0.15:
                edges.remove((left, right))
                replacement = rng.randrange(node_count)
                if replacement != left:
                    edges.add(_edge(left, replacement))
    return sorted(edges)


def simulate_gossip(
    kind: str,
    strategy: str,
    seed: int,
    node_count: int = 12,
    fan_out: int = 2,
    max_rounds: int = 500,
) -> dict:
    """Measure rounds and approximate payload IDs needed to spread all knowledge."""
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    edges = make_topology(kind, node_count, seed)
    components = connected_components(
        [str(index) for index in range(node_count)],
        [(str(left), str(right)) for left, right in edges],
    )
    neighbors: dict[int, set[int]] = {node: set() for node in range(node_count)}
    for left, right in edges:
        neighbors[left].add(right)
        neighbors[right].add(left)
    knowledge = [{node} for node in range(node_count)]
    rng = Mulberry32(seed ^ 0xA5A5A5A5)
    bytes_sent = 0
    for round_number in range(1, max_rounds + 1):
        if all(len(items) == node_count for items in knowledge):
            return _report(kind, strategy, seed, round_number - 1, bytes_sent, components)
        contacts: set[tuple[int, int]] = set()
        for node in range(node_count):
            candidates = sorted(neighbors[node])
            if strategy == "push_pull":
                selected = candidates
            elif strategy == "round_robin":
                selected = [candidates[(round_number - 1) % len(candidates)]] if candidates else []
            else:
                pool = list(candidates)
                selected = []
                for _ in range(min(fan_out, len(pool))):
                    selected.append(pool.pop(rng.randrange(len(pool))))
            contacts.update(_edge(node, peer) for peer in selected)
        before = [set(items) for items in knowledge]
        for left, right in contacts:
            bytes_sent += len(before[left] ^ before[right]) * 8
            union = before[left] | before[right]
            knowledge[left].update(union)
            knowledge[right].update(union)
    return _report(kind, strategy, seed, max_rounds, bytes_sent, components, converged=False)


def run_gossip_suite(seed: int = 7, node_count: int = 12) -> list[dict]:
    """Compare every named graph and peer-selection strategy once."""
    return [
        simulate_gossip(kind, strategy, seed, node_count)
        for kind in TOPOLOGIES
        for strategy in STRATEGIES
    ]


def _edge(left: int, right: int) -> tuple[int, int]:
    """Normalize an undirected integer edge."""
    return min(left, right), max(left, right)


def _report(
    kind: str,
    strategy: str,
    seed: int,
    rounds: int,
    bytes_sent: int,
    components: list[list[str]],
    converged: bool = True,
) -> dict:
    """Build a fully labelled simulation result."""
    return {
        "topology": kind,
        "strategy": strategy,
        "seed": seed,
        "rounds_to_converge": rounds if converged else None,
        "approx_bytes_sent": bytes_sent,
        "components": components,
        "converged": converged,
        "synthetic": True,
    }

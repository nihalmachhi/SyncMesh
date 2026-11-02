"""Causal and topology graph invariants."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from syncmesh.core.settings import Settings
from syncmesh.graphs.causal import build_causal_graph
from syncmesh.graphs.gossip_sim import make_topology, run_gossip_suite
from syncmesh.graphs.topology import topology_from_peers
from syncmesh.node.api import create_app
from syncmesh.protocol.hlc import HLC
from syncmesh.protocol.messages import Operation, OpType


def operation(origin: str, sequence: int, base: dict[str, int]) -> Operation:
    """Build a simple immutable operation for graph tests."""
    return Operation(
        operation_id=f"{origin}:{sequence}",
        origin_node_id=origin,
        origin_seq=sequence,
        entity_id="item",
        op_type=OpType.SET_FIELD,
        payload={"fields": {"name": origin}},
        base_vector=base,
        hlc=HLC(1000 + sequence, 0),
        wall_clock=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_causal_graph_reports_chain_frontier_and_concurrency():
    """Concurrent siblings are frontier nodes and contribute to antichain width."""
    operations = [
        operation("a", 1, {}),
        operation("b", 1, {"a": 1}),
        operation("c", 1, {"a": 1}),
        operation("b", 2, {"a": 1, "b": 1}),
    ]

    graph = build_causal_graph(operations)

    assert graph["operation_count"] == 4
    assert graph["longest_chain"] == 3
    assert graph["antichain_width"] == 2
    assert graph["frontier"] == ["b:2", "c:1"]
    assert not graph["truncated"]


def test_topology_finds_partitions_and_isolated_nodes():
    """Offline nodes disappear from active connected components."""
    topology = topology_from_peers({"a": ["b"], "b": ["a", "c"], "c": ["b"], "d": []}, {"b"})

    assert topology["components"] == [["a"], ["c"], ["d"]]


def test_supported_gossip_topologies_and_strategies_are_seeded():
    """The graph experiment covers all planned shapes and fan-out policies."""
    results = run_gossip_suite(seed=12, node_count=8)

    assert len(results) == 12
    assert all(result["synthetic"] for result in results)
    assert all(result["converged"] for result in results)
    assert make_topology("ring", 8, 12) == make_topology("ring", 8, 12)


def test_debug_graph_endpoints_require_auth_and_return_graphs(tmp_path):
    """Authenticated diagnostics expose operation causality and peer components."""
    app = create_app(
        Settings(
            node_id="graph-api",
            db_path=str(tmp_path / "graph-api.sqlite"),
            peers="",
            sync_interval_seconds=30,
            admin_token="graph-admin-secret",
        )
    )
    with TestClient(app) as client:
        assert client.get("/debug/causal-graph").status_code == 401
        assert client.post("/items", json={"name": "Rice", "quantity": 4}).status_code == 201
        headers = {"Authorization": "Bearer graph-admin-secret"}
        causal = client.get("/debug/causal-graph", headers=headers)
        topology = client.get("/debug/topology", headers=headers)

    assert causal.status_code == 200
    assert causal.json()["operation_count"] == 1
    assert topology.status_code == 200
    assert topology.json()["components"] == [["graph-api"]]

"""Regression cases for the independently reviewed SyncMesh defects."""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from itertools import permutations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from syncmesh.core.settings import Settings
from syncmesh.node.api import create_app
from syncmesh.node.storage.db import Database
from syncmesh.node.storage.repository import Repository
from syncmesh.protocol.messages import ExchangeRequest, Operation, OpType

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_repo(tmp_path, name: str) -> Repository:
    """Create an isolated replica database for a regression schedule."""
    database = Database(str(tmp_path / f"{name}.sqlite"))
    database.initialize()
    return Repository(database, name)


def make_operation(
    origin: str,
    sequence: int,
    entity_id: str,
    kind: OpType,
    payload: dict,
    base_vector: dict[str, int],
    tick: int = 0,
) -> Operation:
    """Build a stable operation with an identity derived from origin and sequence."""
    return Operation(
        operation_id=f"{origin}:{sequence}",
        origin_node_id=origin,
        origin_seq=sequence,
        entity_id=entity_id,
        op_type=kind,
        payload=payload,
        base_vector=base_vector,
        wall_clock=BASE_TIME + timedelta(milliseconds=tick),
    )


def test_concurrent_field_edits_converge_across_delivery_orders(tmp_path):
    """Concurrent independent fields must survive every delivery permutation."""
    entity_id = "item-1"
    create = make_operation(
        "a", 1, entity_id, OpType.CREATE, {"fields": {"name": "Rice", "price": 1}}, {}
    )
    changes = [
        make_operation(
            "b", 1, entity_id, OpType.SET_FIELD, {"fields": {"name": "Brown Rice"}}, {"a": 1}, 1
        ),
        make_operation("c", 1, entity_id, OpType.SET_FIELD, {"fields": {"price": 2}}, {"a": 1}, 2),
        make_operation(
            "d", 1, entity_id, OpType.SET_FIELD, {"fields": {"category": "Grain"}}, {"a": 1}, 3
        ),
    ]

    for schedule, order in enumerate(permutations(changes)):
        repository = make_repo(tmp_path, f"permutation-{schedule}")
        assert repository.receive(create)
        for change in order:
            repository.receive(change)
        item = repository.items()[0]
        assert (item["name"], item["price"], item["category"]) == (
            "Brown Rice",
            2,
            "Grain",
        )


def test_concurrent_same_field_uses_deterministic_winner(tmp_path):
    """The maximum HLC/node/op key wins regardless of arrival order."""
    entity_id = "item-2"
    create = make_operation("a", 1, entity_id, OpType.CREATE, {"fields": {"name": "Rice"}}, {})
    changes = [
        make_operation(
            "b", 1, entity_id, OpType.SET_FIELD, {"fields": {"name": "Red"}}, {"a": 1}, 1
        ),
        make_operation(
            "c", 1, entity_id, OpType.SET_FIELD, {"fields": {"name": "Brown"}}, {"a": 1}, 3
        ),
        make_operation(
            "d", 1, entity_id, OpType.SET_FIELD, {"fields": {"name": "White"}}, {"a": 1}, 2
        ),
    ]
    expected = "Brown"

    for schedule, order in enumerate(permutations(changes)):
        repository = make_repo(tmp_path, f"same-field-{schedule}")
        repository.receive(create)
        for change in order:
            repository.receive(change)
        assert repository.items()[0]["name"] == expected


def test_causal_descendant_does_not_overwrite_a_larger_concurrent_hlc(tmp_path):
    """A later local edit remains a max-register, even beside a concurrent writer."""
    create = make_operation(
        "a", 1, "item-descendant", OpType.CREATE, {"fields": {"name": "Rice"}}, {}
    )
    first = make_operation(
        "b", 1, "item-descendant", OpType.SET_FIELD, {"fields": {"name": "Brown"}}, {"a": 1}, 10
    )
    other = make_operation(
        "c", 1, "item-descendant", OpType.SET_FIELD, {"fields": {"name": "White"}}, {"a": 1}, 20
    )
    descendant = make_operation(
        "b",
        2,
        "item-descendant",
        OpType.SET_FIELD,
        {"fields": {"name": "Red"}},
        {"a": 1, "b": 1},
        15,
    )

    for index, order in enumerate(((first, other, descendant), (other, first, descendant))):
        repository = make_repo(tmp_path, f"descendant-{index}")
        repository.receive(create)
        for operation in order:
            repository.receive(operation)
        assert repository.items()[0]["name"] == "White"


def test_conflict_pair_is_stored_open_with_both_values_in_either_order(tmp_path):
    """Replicas store the same open record for a concurrent winning/losing pair."""
    create = make_operation(
        "a", 1, "item-conflict", OpType.CREATE, {"fields": {"name": "Rice"}}, {}
    )
    edits = [
        make_operation(
            "b", 1, "item-conflict", OpType.SET_FIELD, {"fields": {"name": "Red"}}, {"a": 1}, 1
        ),
        make_operation(
            "c", 1, "item-conflict", OpType.SET_FIELD, {"fields": {"name": "Brown"}}, {"a": 1}, 2
        ),
    ]
    snapshots = []

    for schedule, order in enumerate((edits, list(reversed(edits)))):
        repository = make_repo(tmp_path, f"conflict-{schedule}")
        repository.receive(create)
        for operation in order:
            repository.receive(operation)
        snapshots.append(repository.conflicts())

    assert len(snapshots[0]) == len(snapshots[1]) == 1
    assert snapshots[0][0]["conflict_id"] == snapshots[1][0]["conflict_id"]
    for conflict in (snapshots[0][0], snapshots[1][0]):
        assert conflict["status"] == "OPEN"
        resolution = json.loads(conflict["resolution"])
        assert resolution["winner_value"]["name"] in {"Red", "Brown"}
        assert resolution["loser_value"]["name"] in {"Red", "Brown"}
        assert resolution["winner_value"]["name"] != resolution["loser_value"]["name"]


def test_main_factory_boots_three_independent_nodes(tmp_path, monkeypatch):
    """The documented ASGI factory can start all three isolated lab nodes."""
    from syncmesh.node.main import create_app

    for node_id in ("node-a", "node-b", "node-c"):
        monkeypatch.setenv("SYNCMESH_NODE_ID", node_id)
        monkeypatch.setenv("SYNCMESH_DB_PATH", str(tmp_path / f"{node_id}.sqlite"))
        monkeypatch.setenv("SYNCMESH_PEERS", "")
        monkeypatch.setenv("SYNCMESH_SYNC_INTERVAL_SECONDS", "30")
        with TestClient(create_app()) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok", "node_id": node_id}


def test_causal_operation_waits_for_cross_origin_dependency(tmp_path):
    """An operation depending on a missing origin sequence stays buffered."""
    repository = make_repo(tmp_path, "causal")
    create = make_operation("a", 1, "item-3", OpType.CREATE, {"fields": {"name": "Rice"}}, {})
    edit = make_operation(
        "b", 1, "item-3", OpType.SET_FIELD, {"fields": {"name": "Brown Rice"}}, {"a": 1}
    )

    assert not repository.receive(edit)
    assert repository.items() == []
    assert repository.stats()["pending"] == 1
    assert repository.receive(create)
    assert repository.items()[0]["name"] == "Brown Rice"
    assert repository.stats()["pending"] == 0


def test_pn_counter_merges_independent_positive_and_negative_deltas(tmp_path):
    """Per-origin positive and negative components sum identically across order."""
    create = make_operation(
        "a", 1, "item-counter", OpType.CREATE, {"fields": {"name": "Rice"}, "quantity": 10}, {}
    )
    add = make_operation("b", 1, "item-counter", OpType.ADJUST_QUANTITY, {"delta": 5}, {"a": 1})
    subtract = make_operation(
        "c", 1, "item-counter", OpType.ADJUST_QUANTITY, {"delta": -3}, {"a": 1}
    )
    for name, changes in (("counter-left", (add, subtract)), ("counter-right", (subtract, add))):
        repository = make_repo(tmp_path, name)
        assert repository.receive(create)
        for operation in changes:
            assert repository.receive(operation)
        assert repository.items()[0]["stock"] == 12


def test_tombstone_wins_over_a_concurrent_create_and_survives_restart(tmp_path):
    """Concurrent creation cannot resurrect a deleted identity on a replica."""
    deleted = make_operation("b", 1, "item-tombstone", OpType.DELETE, {}, {"a": 1}, 5)
    created = make_operation(
        "a", 1, "item-tombstone", OpType.CREATE, {"fields": {"name": "Rice"}}, {}, 1
    )
    repository = make_repo(tmp_path, "tombstone")

    assert not repository.receive(deleted)
    assert repository.receive(created)
    assert repository.items() == []
    repository.set_fields("item-tombstone", {"name": "Renamed"})
    assert repository.items() == []

    reopened = Repository(repository.db, "tombstone")
    assert reopened.items() == []
    with repository.db.connect() as connection:
        row = connection.execute(
            "SELECT deleted_vector, deleted_operation_id FROM entities WHERE entity_id=?",
            ("item-tombstone",),
        ).fetchone()
    assert json.loads(row["deleted_vector"]) == {"a": 1, "b": 1}
    assert row["deleted_operation_id"] == "b:1"


def test_receive_rejects_operation_claiming_local_origin(tmp_path):
    """A peer cannot consume the local node's next operation identity."""
    repository = make_repo(tmp_path, "self-origin")
    forged = make_operation(
        "self-origin", 1, "item-4", OpType.CREATE, {"fields": {"name": "Forged"}}, {}
    )

    with pytest.raises(ValueError, match="local node"):
        repository.receive(forged)


def test_operation_identity_and_payload_are_validated():
    """Malformed identity and operation-specific payloads are rejected at parsing."""
    with pytest.raises(ValidationError):
        Operation.model_validate(
            make_operation(
                "a", 1, "item-5", OpType.CREATE, {"fields": {"name": "Rice"}}, {}
            ).model_dump(mode="json")
            | {"operation_id": "not-a:1"}
        )

    with pytest.raises(ValidationError):
        Operation.model_validate(
            make_operation("b", 1, "item-5", OpType.SET_FIELD, {}, {}).model_dump(mode="json")
        )


def test_exchange_batch_is_validated_before_any_operation_is_applied(tmp_path):
    """A malformed operation rejects the entire request before storage changes."""
    app = create_app(
        Settings(
            node_id="atomic-api",
            db_path=str(tmp_path / "atomic.sqlite"),
            peers="",
            sync_interval_seconds=30,
        )
    )
    valid = make_operation(
        "remote", 1, "item-6", OpType.CREATE, {"fields": {"name": "Rice"}}, {}
    ).model_dump(mode="json")
    invalid = make_operation(
        "remote", 2, "item-6", OpType.SET_FIELD, {"fields": {"name": "Brown"}}, {"remote": 1}
    )
    invalid_dict = invalid.model_dump(mode="json")
    invalid_dict["payload"] = {}
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/sync/exchange",
            json={
                "sender_node_id": "remote",
                "sender_vector": {},
                "operations": [valid, invalid_dict],
            },
        )
        assert response.status_code == 422
        assert client.get("/stats").json()["operations"] == 0


def test_exchange_page_is_capped_at_500_operations(tmp_path):
    """The wire request rejects batches larger than one bounded page."""
    operation = make_operation("a", 1, "item-7", OpType.CREATE, {"fields": {"name": "Rice"}}, {})

    with pytest.raises(ValidationError):
        ExchangeRequest(sender_node_id="a", sender_vector={}, operations=[operation] * 501)


def test_since_supports_bounded_pages(tmp_path):
    """The operation log can return a bounded page and continue from its vector."""
    repository = make_repo(tmp_path, "pagination")
    entity_id = repository.create({"name": "Rice"})
    for _ in range(1_000):
        repository.adjust(entity_id, 1)

    first = repository.since({}, limit=500)
    assert len(first) == 500
    next_vector = {first[-1].origin_node_id: first[-1].origin_seq}
    second = repository.since(next_vector, limit=500)
    assert len(second) == 500


def test_patch_rejects_protected_item_fields(tmp_path):
    """PATCH cannot overwrite the item ID or stock projection."""
    app = create_app(
        Settings(
            node_id="patch-api",
            db_path=str(tmp_path / "patch.sqlite"),
            peers="",
            sync_interval_seconds=30,
        )
    )
    with TestClient(app) as client:
        item = client.post("/items", json={"name": "Rice", "quantity": 5}).json()
        response = client.patch(f"/items/{item['id']}", json={"fields": {"id": "bad", "stock": 99}})
        assert response.status_code == 422
        assert client.get("/items").json()["items"][0]["id"] == item["id"]


def test_admin_routes_require_bearer_token(tmp_path, monkeypatch):
    """The administrative connectivity switch is unavailable without its token."""
    monkeypatch.setenv("SYNCMESH_ADMIN_TOKEN", "test-admin-token")
    app = create_app(
        Settings(
            node_id="auth-admin",
            db_path=str(tmp_path / "auth-admin.sqlite"),
            peers="",
            sync_interval_seconds=30,
        )
    )
    with TestClient(app) as client:
        assert client.post("/admin/connectivity", json={"online": False}).status_code == 401
        response = client.post(
            "/admin/connectivity",
            json={"online": False},
            headers={"Authorization": "Bearer test-admin-token"},
        )
        assert response.status_code == 200


def test_authenticated_write_routes_are_rate_limited(tmp_path):
    """Repeated protected writes exceed the configured per-client quota."""
    app = create_app(
        Settings(
            node_id="rate-limited",
            db_path=str(tmp_path / "rate-limited.sqlite"),
            peers="",
            sync_interval_seconds=30,
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
        )
    )
    with TestClient(app) as client:
        assert client.post("/admin/connectivity", json={"online": False}).status_code == 200
        limited = client.post("/admin/connectivity", json={"online": True})
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers


def test_metrics_endpoint_exports_replication_gauges(tmp_path):
    """Prometheus scraping includes operation, pending, and conflict gauges."""
    app = create_app(
        Settings(
            node_id="metrics-node",
            db_path=str(tmp_path / "metrics.sqlite"),
            peers="",
            sync_interval_seconds=30,
        )
    )
    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "syncmesh_operations 0.0" in response.text
        assert "syncmesh_pending_operations 0.0" in response.text


def test_peer_exchange_requires_valid_timestamped_hmac(tmp_path, monkeypatch):
    """The peer exchange endpoint verifies an HMAC over its exact request body."""
    secret = "test-peer-secret"
    monkeypatch.setenv("SYNCMESH_PEER_SECRET", secret)
    app = create_app(
        Settings(
            node_id="auth-peer",
            db_path=str(tmp_path / "auth-peer.sqlite"),
            peers="",
            sync_interval_seconds=30,
        )
    )
    body = json.dumps(
        {"sender_node_id": "peer", "sender_vector": {}, "operations": []},
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    with TestClient(app) as client:
        assert (
            client.post(
                "/sync/exchange", content=body, headers={"Content-Type": "application/json"}
            ).status_code
            == 401
        )
        response = client.post(
            "/sync/exchange",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-SyncMesh-Timestamp": timestamp,
                "X-SyncMesh-Signature": signature,
            },
        )
        assert response.status_code == 200

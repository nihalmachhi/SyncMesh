"""Stable-prefix compaction and stale-node snapshot bootstrap."""

from syncmesh.node.storage.db import Database
from syncmesh.node.storage.repository import Repository


def repository(tmp_path, node_id: str) -> Repository:
    """Make a fresh node for compaction checks."""
    database = Database(str(tmp_path / f"{node_id}.sqlite"))
    database.initialize()
    return Repository(database, node_id)


def test_compaction_waits_for_every_peer_and_snapshot_restores_state(tmp_path):
    """Compaction preserves the vector while a snapshot bootstraps stale peers."""
    source = repository(tmp_path, "source")
    item_id = source.create({"name": "Rice", "category": "Grain", "price": 4.25}, 8)
    source.adjust(item_id, -2)
    source.set_fields(item_id, {"name": "Brown Rice"})

    waiting = source.compact(("peer-a", "peer-b"))
    assert waiting["removed"] == 0
    assert waiting["waiting_for"] == ["peer-a", "peer-b"]

    vector = source.stats()["vector"]
    source.record_peer_vector("peer-a", vector)
    source.record_peer_vector("peer-b", vector)
    compacted = source.compact(("peer-a", "peer-b"))

    assert compacted["removed"] == 3
    assert source.stats()["vector"] == vector
    assert source.since({}) == []
    assert source.items()[0]["stock"] == 6

    stale = repository(tmp_path, "stale")
    stale.apply_snapshot(source.export_snapshot())
    assert stale.stats()["vector"] == vector
    assert stale.items() == source.items()
    assert stale.since({}) == []

from syncmesh.node.storage.db import Database
from syncmesh.node.storage.repository import Repository
from syncmesh.protocol.messages import OpType


def make_repo(tmp_path, name):
    db = Database(str(tmp_path / f"{name}.sqlite"))
    db.initialize()
    return Repository(db, name)


def test_stock_delta_and_duplicate_delivery(tmp_path):
    a = make_repo(tmp_path, "a")
    b = make_repo(tmp_path, "b")
    item_id = a.create({"name": "Rice"}, 10)
    op = a.local(item_id, OpType.ADJUST_QUANTITY, {"delta": 5})
    assert b.receive(a.since({})[0])
    assert b.receive(op)
    assert not b.receive(op)
    assert b.items()[0]["stock"] == 15


def test_version_vector_relation():
    from syncmesh.protocol.version_vector import CausalOrder, compare

    assert compare({"a": 2}, {"a": 1, "b": 1}) is CausalOrder.CONCURRENT

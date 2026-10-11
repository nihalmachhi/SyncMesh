from fastapi.testclient import TestClient

from syncmesh.common.settings import Settings
from syncmesh.node.api import create_app


def test_item_api_persists_local_inventory(tmp_path):
    app = create_app(
        Settings(
            node_id="api-test",
            db_path=str(tmp_path / "api.sqlite"),
            peers="",
            sync_interval_seconds=30,
        )
    )
    with TestClient(app) as client:
        created = client.post(
            "/items",
            json={"name": "Coffee", "category": "Drinks", "price": 4.5, "quantity": 12},
        )
        assert created.status_code == 201
        item = created.json()
        assert item["stock"] == 12
        assert client.get("/items").json()["items"] == [item]
        changed = client.post(f"/items/{item['id']}/quantity", json={"delta": -2})
        assert changed.json()["stock"] == 10

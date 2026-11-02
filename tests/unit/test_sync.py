"""End-to-end HTTP synchronization tests between in-process nodes."""

import httpx
import pytest

from syncmesh.core.settings import Settings
from syncmesh.node.api import create_app
from syncmesh.node.services.sync import Synchronizer
from syncmesh.node.storage.db import Database
from syncmesh.node.storage.repository import Repository


def build_repository(tmp_path, node_id: str) -> Repository:
    """Create an isolated node database for sync tests."""
    database = Database(str(tmp_path / f"{node_id}.sqlite"))
    database.initialize()
    return Repository(database, node_id)


@pytest.mark.asyncio
async def test_sync_paginates_more_than_one_wire_page(tmp_path):
    """A peer receives every operation across bounded round trips."""
    source = build_repository(tmp_path, "source")
    target_settings = Settings(
        node_id="target",
        db_path=str(tmp_path / "target-api.sqlite"),
        peers="",
        sync_interval_seconds=30,
    )
    target_app = create_app(target_settings)
    item_id = source.create({"name": "Rice"}, quantity=10)
    for _ in range(510):
        source.adjust(item_id, 1)

    def build_client(**kwargs: object) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=target_app)
        return httpx.AsyncClient(transport=transport, base_url="http://target", **kwargs)

    syncer = Synchronizer(source, ("http://target",), 1, client_factory=build_client)
    async with build_client() as client:
        result = await syncer.exchange(client)

    target_repository = target_app.state.repository
    assert result["sent"] == 511
    assert target_repository.stats()["operations"] == 511
    assert target_repository.items()[0]["stock"] == 520
    assert syncer.peer_status["http://target"]["online"] is True


@pytest.mark.asyncio
async def test_sync_failure_is_logged_and_backed_off(tmp_path):
    """An unavailable peer yields an observable error and bounded retry time."""
    source = build_repository(tmp_path, "source-fail")

    async def fail_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    def build_client(**kwargs: object) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(fail_request), base_url="http://peer", **kwargs
        )

    syncer = Synchronizer(source, ("http://peer",), 1, client_factory=build_client)
    result = await syncer.exchange()

    assert result == {"sent": 0, "received": 0, "duplicates": 0, "buffered": 0}
    assert syncer.peer_status["http://peer"]["online"] is False
    assert "503" in str(syncer.peer_status["http://peer"]["last_error"])
    assert syncer._retry_at["http://peer"] > 0

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from time import perf_counter

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from syncmesh.common.settings import Settings
from syncmesh.node.services.sync import Synchronizer
from syncmesh.node.storage.db import Database
from syncmesh.node.storage.repository import Repository
from syncmesh.protocol.messages import ExchangeRequest, ExchangeResponse


class ItemInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = "General"
    price: float = Field(default=0, ge=0)
    quantity: int = 0


class FieldUpdate(BaseModel):
    fields: dict


class QuantityChange(BaseModel):
    delta: int


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    db = Database(config.db_path)
    db.initialize()
    repo = Repository(db, config.node_id)
    syncer = Synchronizer(repo, config.peer_urls(), config.sync_interval_seconds)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(syncer.run())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="SyncMesh Node", version="1.0.0", lifespan=lifespan)
    app.state.repository = repo
    app.state.synchronizer = syncer
    app.add_middleware(
        CORSMiddleware, allow_origins=config.origins(), allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "node_id": config.node_id}

    @app.get("/items")
    def items():
        return {"items": repo.items()}

    @app.post("/items", status_code=201)
    def create_item(body: ItemInput):
        item_id = repo.create(
            {"name": body.name, "category": body.category, "price": body.price}, body.quantity
        )
        return next(item for item in repo.items() if item["id"] == item_id)

    @app.patch("/items/{item_id}")
    def update_item(item_id: str, body: FieldUpdate):
        if not any(x["id"] == item_id for x in repo.items()):
            raise HTTPException(404, "Item not found")
        repo.set_fields(item_id, body.fields)
        return next(x for x in repo.items() if x["id"] == item_id)

    @app.post("/items/{item_id}/quantity")
    def adjust(item_id: str, body: QuantityChange):
        if not any(x["id"] == item_id for x in repo.items()):
            raise HTTPException(404, "Item not found")
        repo.adjust(item_id, body.delta)
        return next(x for x in repo.items() if x["id"] == item_id)

    @app.delete("/items/{item_id}", status_code=204)
    def delete_item(item_id: str):
        if not any(x["id"] == item_id for x in repo.items()):
            raise HTTPException(404, "Item not found")
        repo.delete(item_id)

    @app.get("/sync/vector")
    def vector():
        return {"node_id": config.node_id, "vector": repo.stats()["vector"]}

    @app.post("/sync/exchange", response_model=ExchangeResponse)
    def exchange(body: ExchangeRequest):
        started = perf_counter()
        old = len(repo.conflicts())
        applied = sum(repo.receive(op) for op in body.operations)
        outgoing = repo.since(body.sender_vector)
        stats = repo.stats()
        return ExchangeResponse(
            receiver_node_id=config.node_id,
            receiver_vector=stats["vector"],
            operations=outgoing,
            duplicates_ignored=len(body.operations) - applied,
            conflicts_found=max(0, len(repo.conflicts()) - old),
            duration_ms=(perf_counter() - started) * 1000,
        )

    @app.get("/stats")
    def stats():
        return {"node_id": config.node_id, **repo.stats(), "online": syncer.online}

    @app.get("/conflicts")
    def conflicts():
        return {"conflicts": repo.conflicts()}

    @app.post("/admin/connectivity")
    def connectivity(body: dict):
        syncer.online = bool(body.get("online", True))
        return {"online": syncer.online}

    @app.post("/admin/sync")
    async def manual_sync():
        return await syncer.exchange()

    @app.websocket("/events")
    async def events(socket: WebSocket):
        await socket.accept()
        try:
            while True:
                await socket.send_json({"node_id": config.node_id, **repo.stats()})
                await asyncio.sleep(2)
        except WebSocketDisconnect:
            return

    return app

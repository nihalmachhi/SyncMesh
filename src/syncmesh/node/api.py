"""FastAPI application factory for a SyncMesh node."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from syncmesh.core.security import require_admin
from syncmesh.core.settings import Settings
from syncmesh.node.routers import admin, events, items, sync
from syncmesh.node.services.sync import Synchronizer
from syncmesh.node.storage.db import Database
from syncmesh.node.storage.repository import Repository


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a node application with its private store and peer synchronizer."""
    config = settings or Settings()
    database = Database(config.db_path)
    database.initialize()
    repository = Repository(database, config.node_id)
    peer_secret = config.peer_secret.get_secret_value() if config.peer_secret else None
    synchronizer = Synchronizer(
        repository,
        config.peer_urls(),
        config.sync_interval_seconds,
        peer_secret=peer_secret,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(synchronizer.run())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="SyncMesh Node", version="1.0.0", lifespan=lifespan)
    app.state.repository = repository
    app.state.synchronizer = synchronizer
    app.state.settings = config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """Report the identity and liveness of this node."""
        return {"status": "ok", "node_id": config.node_id}

    @app.get("/stats", tags=["admin"])
    def stats() -> dict:
        """Return local replication statistics."""
        return {
            "node_id": config.node_id,
            **repository.stats(),
            "online": synchronizer.online,
            "peers": synchronizer.peer_status,
        }

    @app.get("/conflicts", tags=["admin"], dependencies=[Depends(require_admin)])
    def conflicts() -> dict:
        """List conflict records currently stored by this node."""
        return {"conflicts": repository.conflicts()}

    app.include_router(items.router)
    app.include_router(sync.router)
    app.include_router(admin.router)
    app.include_router(events.router)
    return app

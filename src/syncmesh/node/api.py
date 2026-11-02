"""FastAPI application factory for a SyncMesh node."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from syncmesh.core.metrics import NodeMetrics
from syncmesh.core.rate_limit import FixedWindowRateLimiter, enforce_rate_limit
from syncmesh.core.security import require_admin
from syncmesh.core.settings import Settings
from syncmesh.graphs.causal import build_causal_graph
from syncmesh.graphs.topology import topology_from_peers
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
        byte_budget=config.sync_byte_budget,
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
    app.state.rate_limiter = FixedWindowRateLimiter(
        config.rate_limit_requests, config.rate_limit_window_seconds
    )
    metrics = NodeMetrics.create()
    app.state.metrics = metrics
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

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint():
        """Expose low-cardinality Prometheus node and peer gauges."""
        values = repository.stats()
        metrics.operations.set(values["operations"])
        metrics.pending.set(values["pending"])
        metrics.open_conflicts.set(values["conflicts"])
        for peer in synchronizer.peer_status:
            status = synchronizer.peer_status[peer]
            lag = status.get("lag", 0)
            duration = status.get("duration_ms", 0)
            metrics.peer_lag.labels(peer).set(float(lag) if isinstance(lag, (int, float)) else 0)
            metrics.sync_duration.labels(peer).set(
                float(duration) if isinstance(duration, (int, float)) else 0
            )
        return metrics.render()

    @app.get(
        "/conflicts",
        tags=["admin"],
        dependencies=[Depends(require_admin), Depends(enforce_rate_limit)],
    )
    def conflicts() -> dict:
        """List conflict records currently stored by this node."""
        return {"conflicts": repository.conflicts()}

    @app.post(
        "/admin/compact",
        tags=["admin"],
        dependencies=[Depends(require_admin), Depends(enforce_rate_limit)],
    )
    def compact_log() -> dict:
        """Compact only operation prefixes acknowledged by every configured peer."""
        peer_ids = tuple(urlsplit(url).hostname or url for url in config.peer_urls())
        try:
            return repository.compact(peer_ids)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get(
        "/debug/causal-graph",
        tags=["debug"],
        dependencies=[Depends(require_admin), Depends(enforce_rate_limit)],
    )
    def causal_graph() -> dict:
        """Return a bounded causal graph for the most recent 300 operations."""
        return build_causal_graph(repository.recent_operations(300))

    @app.get(
        "/debug/topology",
        tags=["debug"],
        dependencies=[Depends(require_admin), Depends(enforce_rate_limit)],
    )
    def peer_topology() -> dict:
        """Return configured peers and their currently observed status."""
        peer_urls = config.peer_urls()
        peers = {
            config.node_id: [urlsplit(url).hostname or url for url in peer_urls],
            **{urlsplit(url).hostname or url: [config.node_id] for url in peer_urls},
        }
        offline = {
            urlsplit(url).hostname or url
            for url, status in synchronizer.peer_status.items()
            if not status.get("online")
        }
        return topology_from_peers(peers, offline)

    app.include_router(items.router)
    app.include_router(sync.router)
    app.include_router(admin.router)
    app.include_router(events.router)
    return app

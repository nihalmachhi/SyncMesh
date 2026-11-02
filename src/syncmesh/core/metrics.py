"""Prometheus collectors for node replication health."""

from dataclasses import dataclass

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest
from starlette.responses import Response


@dataclass(frozen=True)
class NodeMetrics:
    """Collectors scoped to one in-process ASGI node."""

    registry: CollectorRegistry
    operations: Gauge
    pending: Gauge
    open_conflicts: Gauge
    peer_lag: Gauge
    sync_duration: Gauge

    @classmethod
    def create(cls) -> "NodeMetrics":
        """Create an isolated collector registry for an app instance."""
        registry = CollectorRegistry()
        return cls(
            registry,
            Gauge("syncmesh_operations", "Applied operations", registry=registry),
            Gauge("syncmesh_pending_operations", "Causally buffered operations", registry=registry),
            Gauge("syncmesh_open_conflicts", "Open field conflicts", registry=registry),
            Gauge(
                "syncmesh_peer_lag_operations",
                "Operations pending per peer",
                ("peer",),
                registry=registry,
            ),
            Gauge(
                "syncmesh_peer_sync_duration_ms",
                "Last sync duration per peer",
                ("peer",),
                registry=registry,
            ),
        )

    def render(self) -> Response:
        """Encode the latest collector values for Prometheus scraping."""
        return Response(generate_latest(self.registry), media_type=CONTENT_TYPE_LATEST)

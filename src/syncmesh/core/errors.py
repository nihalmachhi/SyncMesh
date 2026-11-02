"""Expected application-level errors."""


class SyncMeshError(Exception):
    """Base error for the synchronization engine."""


class ItemNotFoundError(SyncMeshError):
    """Requested item does not exist."""


class InvalidOperationError(SyncMeshError):
    """Operation violates an invariant."""


class PeerUnavailableError(SyncMeshError):
    """A peer is not reachable."""

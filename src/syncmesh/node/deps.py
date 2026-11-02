"""Request-scoped accessors for services owned by the application."""

from fastapi import Request

from syncmesh.node.services.sync import Synchronizer
from syncmesh.node.storage.repository import Repository


def get_repository(request: Request) -> Repository:
    """Return the repository attached to the running application."""
    return request.app.state.repository


def get_synchronizer(request: Request) -> Synchronizer:
    """Return the synchronizer attached to the running application."""
    return request.app.state.synchronizer

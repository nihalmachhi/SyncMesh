"""Request-scoped accessors for services owned by the application."""

from fastapi import Request

from syncmesh.core.settings import Settings
from syncmesh.node.services.sync import Synchronizer
from syncmesh.node.storage.repository import Repository


def get_repository(request: Request) -> Repository:
    """Return the repository attached to the running application."""
    return request.app.state.repository


def get_synchronizer(request: Request) -> Synchronizer:
    """Return the synchronizer attached to the running application."""
    return request.app.state.synchronizer


def get_settings(request: Request) -> Settings:
    """Return the validated settings attached to the running application."""
    return request.app.state.settings

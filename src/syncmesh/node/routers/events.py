"""WebSocket stream for node status updates."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from syncmesh.node.deps import get_repository
from syncmesh.node.storage.repository import Repository

router = APIRouter(tags=["events"])


@router.websocket("/events")
async def stream_events(
    socket: WebSocket, repository: Annotated[Repository, Depends(get_repository)]
) -> None:
    """Send a fresh node status snapshot every two seconds."""
    await socket.accept()
    try:
        while True:
            await socket.send_json({"node_id": repository.node_id, **repository.stats()})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return

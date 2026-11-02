"""Local administrative controls."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from syncmesh.node.deps import get_synchronizer
from syncmesh.node.services.sync import Synchronizer

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/connectivity")
def set_connectivity(
    body: dict[str, Any], synchronizer: Annotated[Synchronizer, Depends(get_synchronizer)]
) -> dict[str, bool]:
    """Toggle this lab node's outbound peer sync loop."""
    synchronizer.online = bool(body.get("online", True))
    return {"online": synchronizer.online}


@router.post("/sync")
async def sync_now(
    synchronizer: Annotated[Synchronizer, Depends(get_synchronizer)],
) -> dict[str, int]:
    """Request one immediate peer exchange cycle."""
    return await synchronizer.exchange()

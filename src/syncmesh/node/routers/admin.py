"""Local administrative controls."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from syncmesh.core.security import require_admin
from syncmesh.node.deps import get_repository, get_synchronizer
from syncmesh.node.schemas import ConflictResolution, ConnectivityInput
from syncmesh.node.services.sync import Synchronizer
from syncmesh.node.storage.repository import Repository

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/admin/connectivity")
def set_connectivity(
    body: ConnectivityInput, synchronizer: Annotated[Synchronizer, Depends(get_synchronizer)]
) -> dict[str, bool]:
    """Toggle this lab node's outbound peer sync loop."""
    synchronizer.online = body.online
    return {"online": synchronizer.online}


@router.post("/admin/sync")
async def sync_now(
    synchronizer: Annotated[Synchronizer, Depends(get_synchronizer)],
) -> dict[str, int]:
    """Request one immediate peer exchange cycle."""
    return await synchronizer.exchange()


@router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(
    conflict_id: str,
    body: ConflictResolution,
    repository: Annotated[Repository, Depends(get_repository)],
) -> dict[str, str]:
    """Record the selected conflict values as an ordinary field operation."""
    try:
        operation = repository.resolve_conflict(conflict_id, body.fields)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"conflict_id": conflict_id, "resolution_operation_id": operation.operation_id}

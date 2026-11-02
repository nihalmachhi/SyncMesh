"""Version-vector and operation-exchange endpoints."""

from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from syncmesh.core.security import require_peer
from syncmesh.node.deps import get_repository
from syncmesh.node.storage.repository import ReceiveOutcome, Repository
from syncmesh.protocol.messages import ExchangeRequest, ExchangeResponse

router = APIRouter(tags=["sync"], dependencies=[Depends(require_peer)])


@router.get("/sync/vector")
def version_vector(repository: Annotated[Repository, Depends(get_repository)]) -> dict:
    """Return this replica's contiguous operation vector."""
    return {"node_id": repository.node_id, "vector": repository.stats()["vector"]}


@router.post("/sync/exchange", response_model=ExchangeResponse)
def exchange(
    body: ExchangeRequest, repository: Annotated[Repository, Depends(get_repository)]
) -> ExchangeResponse:
    """Apply received operations and return operations missing at the sender."""
    started = perf_counter()
    old_conflicts = len(repository.conflicts())
    try:
        outcomes = repository.receive_batch(body.operations)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    outgoing = repository.since(body.sender_vector, limit=500)
    stats = repository.stats()
    return ExchangeResponse(
        receiver_node_id=repository.node_id,
        receiver_vector=stats["vector"],
        operations=outgoing,
        duplicates_ignored=sum(outcome is ReceiveOutcome.DUPLICATE for outcome in outcomes),
        buffered=sum(outcome is ReceiveOutcome.BUFFERED for outcome in outcomes),
        conflicts_found=max(0, len(repository.conflicts()) - old_conflicts),
        duration_ms=(perf_counter() - started) * 1000,
    )

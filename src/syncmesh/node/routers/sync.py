"""Version-vector and operation-exchange endpoints."""

from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends

from syncmesh.node.deps import get_repository
from syncmesh.node.storage.repository import Repository
from syncmesh.protocol.messages import ExchangeRequest, ExchangeResponse

router = APIRouter(tags=["sync"])


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
    applied = sum(repository.receive(operation) for operation in body.operations)
    outgoing = repository.since(body.sender_vector)
    stats = repository.stats()
    return ExchangeResponse(
        receiver_node_id=repository.node_id,
        receiver_vector=stats["vector"],
        operations=outgoing,
        duplicates_ignored=len(body.operations) - applied,
        conflicts_found=max(0, len(repository.conflicts()) - old_conflicts),
        duration_ms=(perf_counter() - started) * 1000,
    )

"""Inventory item HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from syncmesh.node.deps import get_repository
from syncmesh.node.schemas import FieldUpdate, ItemInput, QuantityChange
from syncmesh.node.storage.repository import Repository

router = APIRouter(tags=["items"])


@router.get("/items")
def list_items(repository: Annotated[Repository, Depends(get_repository)]) -> dict:
    """List visible inventory items."""
    return {"items": repository.items()}


@router.post("/items", status_code=201)
def create_item(
    body: ItemInput, repository: Annotated[Repository, Depends(get_repository)]
) -> dict:
    """Create an inventory item and return its current representation."""
    item_id = repository.create(
        {"name": body.name, "category": body.category, "price": body.price}, body.quantity
    )
    return next(item for item in repository.items() if item["id"] == item_id)


@router.patch("/items/{item_id}")
def update_item(
    item_id: str, body: FieldUpdate, repository: Annotated[Repository, Depends(get_repository)]
) -> dict:
    """Update fields on an existing item."""
    if not any(item["id"] == item_id for item in repository.items()):
        raise HTTPException(404, "Item not found")
    repository.set_fields(item_id, body.fields)
    return next(item for item in repository.items() if item["id"] == item_id)


@router.post("/items/{item_id}/quantity")
def adjust_quantity(
    item_id: str,
    body: QuantityChange,
    repository: Annotated[Repository, Depends(get_repository)],
) -> dict:
    """Apply a signed stock adjustment."""
    if not any(item["id"] == item_id for item in repository.items()):
        raise HTTPException(404, "Item not found")
    repository.adjust(item_id, body.delta)
    return next(item for item in repository.items() if item["id"] == item_id)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(
    item_id: str, repository: Annotated[Repository, Depends(get_repository)]
) -> None:
    """Delete an item by writing its tombstone operation."""
    if not any(item["id"] == item_id for item in repository.items()):
        raise HTTPException(404, "Item not found")
    repository.delete(item_id)

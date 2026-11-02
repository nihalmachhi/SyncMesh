"""Validated request and response models for node routes."""

from pydantic import BaseModel, Field


class ItemInput(BaseModel):
    """Inventory item creation payload."""

    name: str = Field(min_length=1, max_length=120)
    category: str = "General"
    price: float = Field(default=0, ge=0)
    quantity: int = 0


class FieldUpdate(BaseModel):
    """Fields to update on an existing item."""

    fields: dict


class QuantityChange(BaseModel):
    """Signed stock adjustment payload."""

    delta: int

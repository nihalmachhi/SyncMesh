"""Validated request and response models for node routes."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ItemInput(BaseModel):
    """Inventory item creation payload."""

    name: str = Field(min_length=1, max_length=120)
    category: str = "General"
    price: float = Field(default=0, ge=0, allow_inf_nan=False)
    quantity: int = 0

    @field_validator("name", "category")
    @classmethod
    def strip_text(cls, value: str) -> str:
        """Reject values that become empty after trimming whitespace."""
        value = value.strip()
        if not value:
            raise ValueError("text fields cannot be blank")
        return value


class FieldUpdate(BaseModel):
    """Fields to update on an existing item."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[str, Any] = Field(min_length=1)

    @field_validator("fields")
    @classmethod
    def validate_item_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Allow only supported mutable fields with their expected types."""
        allowed = {"name", "category", "price"}
        if not set(value).issubset(allowed):
            raise ValueError("only name, category, and price can be changed")
        for key in ("name", "category"):
            if key in value and (not isinstance(value[key], str) or not value[key].strip()):
                raise ValueError(f"{key} must be a nonempty string")
            if key in value:
                value[key] = value[key].strip()
        if "price" in value and (
            not isinstance(value["price"], (int, float))
            or isinstance(value["price"], bool)
            or value["price"] < 0
        ):
            raise ValueError("price must be a non-negative number")
        return value


class QuantityChange(BaseModel):
    """Signed stock adjustment payload."""

    delta: int


class ConnectivityInput(BaseModel):
    """Connectivity toggle payload."""

    online: bool


class ConflictResolution(BaseModel):
    """Field values selected when reviewing a conflict."""

    fields: dict[str, Any] = Field(min_length=1)

    @model_validator(mode="after")
    def require_fields(self) -> "ConflictResolution":
        """Keep the resolution payload nonempty and explicit."""
        if not self.fields:
            raise ValueError("at least one field value is required")
        return self

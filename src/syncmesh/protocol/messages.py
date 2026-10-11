"""Immutable, validated operation exchange messages."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpType(StrEnum):
    """Supported immutable operation kinds."""

    CREATE = "create"
    SET_FIELD = "set_field"
    DELETE = "delete"
    ADJUST_QUANTITY = "adjust_quantity"


class Operation(BaseModel):
    """One identified mutation with causal context."""

    model_config = ConfigDict(frozen=True)

    operation_id: str
    origin_node_id: str
    origin_seq: int = Field(ge=1)
    entity_id: str
    op_type: OpType
    payload: dict[str, Any]
    base_vector: dict[str, int]
    wall_clock: datetime

    @field_validator("wall_clock")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        """Normalize operation timestamps to UTC."""
        if value.tzinfo is None:
            raise ValueError("wall_clock must be timezone-aware")
        return value.astimezone(UTC)


class ExchangeRequest(BaseModel):
    """Sender vector and operations for an idempotent round trip."""

    sender_node_id: str
    sender_vector: dict[str, int]
    operations: list[Operation] = Field(max_length=1000)


class ExchangeResponse(BaseModel):
    """Receiver state and operations missing from the sender."""

    receiver_node_id: str
    receiver_vector: dict[str, int]
    operations: list[Operation]
    duplicates_ignored: int
    conflicts_found: int
    duration_ms: float

"""Validated operation payloads and bounded peer exchange messages."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from syncmesh.protocol.hlc import HLC


class OpType(StrEnum):
    """Supported immutable operation kinds."""

    CREATE = "create"
    SET_FIELD = "set_field"
    DELETE = "delete"
    ADJUST_QUANTITY = "adjust_quantity"


class CreatePayload(BaseModel):
    """Fields and initial stock for a new entity."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["create"]
    fields: dict[str, Any] = Field(min_length=1)
    quantity: int = 0


class SetFieldPayload(BaseModel):
    """A nonempty set of item fields to update."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["set_field"]
    fields: dict[str, Any] = Field(min_length=1)


class DeletePayload(BaseModel):
    """An empty delete marker."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["delete"]


class AdjustQuantityPayload(BaseModel):
    """A signed additive stock change."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["adjust_quantity"]
    delta: int


OperationPayload = Annotated[
    CreatePayload | SetFieldPayload | DeletePayload | AdjustQuantityPayload,
    Field(discriminator="kind"),
]
_PAYLOAD_ADAPTER = TypeAdapter(OperationPayload)


class Operation(BaseModel):
    """One identified mutation with validated, operation-specific data."""

    model_config = ConfigDict(frozen=True)

    operation_id: str
    origin_node_id: str = Field(min_length=1, max_length=120)
    origin_seq: int = Field(ge=1)
    entity_id: str = Field(min_length=1, max_length=200)
    op_type: OpType
    payload: dict[str, Any]
    base_vector: dict[str, int]
    hlc: HLC = Field(default_factory=lambda: HLC(0, 0))
    wall_clock: datetime

    @model_validator(mode="before")
    @classmethod
    def validate_discriminated_payload(cls, value: Any) -> Any:
        """Validate payload shape using the operation kind as its discriminator."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        kind = data.get("op_type")
        if kind is None:
            return data
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("operation payload must be an object")
        discriminator = str(kind)
        if "kind" in payload and payload["kind"] != discriminator:
            raise ValueError("payload kind must match op_type")
        parsed = _PAYLOAD_ADAPTER.validate_python({**payload, "kind": discriminator})
        data["payload"] = parsed.model_dump(exclude={"kind"})
        return data

    @model_validator(mode="before")
    @classmethod
    def supply_legacy_hlc(cls, value: Any) -> Any:
        """Read older wall-clock-only operations while upgrading existing logs."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        wall_clock = data.get("wall_clock")
        if wall_clock is None:
            timestamp = data.get("hlc")
            if isinstance(timestamp, dict):
                wall_clock = datetime.fromtimestamp(timestamp["physical_ms"] / 1000, UTC)
            else:
                wall_clock = datetime.now(UTC)
            data["wall_clock"] = wall_clock
        if data.get("hlc") is None:
            parsed_wall = wall_clock
            if isinstance(parsed_wall, str):
                parsed_wall = datetime.fromisoformat(parsed_wall.replace("Z", "+00:00"))
            if isinstance(parsed_wall, datetime):
                if parsed_wall.tzinfo is None:
                    raise ValueError("wall_clock must be timezone-aware")
                physical_ms = int(parsed_wall.timestamp() * 1000)
                data["hlc"] = {"physical_ms": physical_ms, "logical": 0}
        return data

    @model_validator(mode="after")
    def validate_identity_and_vector(self) -> "Operation":
        """Enforce deterministic IDs and non-negative causal-vector components."""
        expected = f"{self.origin_node_id}:{self.origin_seq}"
        if self.operation_id != expected:
            raise ValueError(f"operation_id must equal {expected!r}")
        if any(sequence < 0 for sequence in self.base_vector.values()):
            raise ValueError("base_vector sequence numbers must be non-negative")
        return self

    @model_validator(mode="after")
    def normalize_wall_clock(self) -> "Operation":
        """Normalize a supplied wall-clock timestamp to UTC."""
        if self.wall_clock.tzinfo is None:
            raise ValueError("wall_clock must be timezone-aware")
        object.__setattr__(self, "wall_clock", self.wall_clock.astimezone(UTC))
        return self


class ExchangeRequest(BaseModel):
    """One bounded page of missing operations from a peer."""

    sender_node_id: str = Field(min_length=1, max_length=120)
    sender_vector: dict[str, int]
    operations: list[Operation] = Field(max_length=500)


class ExchangeResponse(BaseModel):
    """One bounded response page and peer exchange counters."""

    receiver_node_id: str
    receiver_vector: dict[str, int]
    operations: list[Operation] = Field(max_length=500)
    duplicates_ignored: int
    buffered: int = 0
    conflicts_found: int
    duration_ms: float

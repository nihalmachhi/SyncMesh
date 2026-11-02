"""Generate site parity fixtures from SyncMesh's actual Python merge code."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from syncmesh.domain.apply import EntityState, apply_operation  # noqa: E402
from syncmesh.protocol.hlc import HLC  # noqa: E402
from syncmesh.protocol.messages import Operation, OpType  # noqa: E402
from syncmesh.simulation.prng import Mulberry32  # noqa: E402
from syncmesh.simulation.run import reproduce  # noqa: E402


def fixture_operation(
    origin: str,
    sequence: int,
    operation_type: OpType,
    payload: dict[str, Any],
    base_vector: dict[str, int],
    clock_ms: int,
) -> Operation:
    """Construct a validated operation for the cross-language fixture."""
    return Operation(
        operation_id=f"{origin}:{sequence}",
        origin_node_id=origin,
        origin_seq=sequence,
        entity_id="offline-rice",
        op_type=operation_type,
        payload=payload,
        base_vector=base_vector,
        hlc=HLC(clock_ms, sequence),
        wall_clock=datetime.fromtimestamp(clock_ms / 1000, UTC),
    )


def build_fixture() -> dict[str, Any]:
    """Run fixed concurrent writes through the Python domain transition."""
    operations = [
        fixture_operation(
            "node-a", 1, OpType.CREATE,
            {"fields": {"name": "Rice", "category": "Grains", "price": 4.5}, "quantity": 10},
            {}, 1_800_000_000_000,
        ),
        fixture_operation(
            "node-b", 1, OpType.SET_FIELD, {"fields": {"name": "Brown rice"}},
            {"node-a": 1}, 1_800_000_000_100,
        ),
        fixture_operation(
            "node-c", 1, OpType.SET_FIELD, {"fields": {"name": "Whole grain rice"}},
            {"node-a": 1}, 1_800_000_000_200,
        ),
        fixture_operation(
            "node-b", 2, OpType.ADJUST_QUANTITY, {"delta": 5},
            {"node-a": 1, "node-b": 1}, 1_800_000_000_300,
        ),
        fixture_operation(
            "node-c", 2, OpType.ADJUST_QUANTITY, {"delta": -2},
            {"node-a": 1, "node-c": 1}, 1_800_000_000_250,
        ),
    ]
    state = EntityState(fields={})
    for operation in operations:
        state, _ = apply_operation(state, operation)
    rng = Mulberry32(42)
    random_values = [rng.random() for _ in range(8)]
    return {
        "operations": [operation.model_dump(mode="json") for operation in operations],
        "expected": {
            "fields": state.fields,
            "quantity": state.quantity,
            "deleted": state.is_deleted,
            "field_registers": state.field_registers,
            "pn_counter": state.pn_counter,
        },
        "seeded_random": {
            "seed": 42,
            "mulberry32_first_8": random_values,
        },
        "tolerance": 0,
        "source": "src/syncmesh/domain/apply.py",
    }


def main() -> None:
    """Write the Python-derived simulator parity fixture and current reports."""
    fixture_dir = ROOT / "site" / "src" / "features" / "simulator" / "__fixtures__"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "merge.json").write_text(
        json.dumps(build_fixture(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = reproduce()
    schedules = report["convergence"]["converged"]
    print(
        f"Updated {fixture_dir / 'merge.json'} and generated site results "
        f"({schedules} schedules)."
    )


if __name__ == "__main__":
    main()

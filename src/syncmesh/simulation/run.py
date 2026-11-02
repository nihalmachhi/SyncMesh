"""Command-line entry points for deterministic reports and seed replay."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from syncmesh.graphs.gossip_sim import run_gossip_suite
from syncmesh.nlp.dedupe import evaluate_dedupe
from syncmesh.protocol.hlc import HLC
from syncmesh.protocol.messages import Operation, OpType
from syncmesh.protocol.optimize import compare_selection
from syncmesh.simulation.cluster import run_schedule, run_simulation

ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = ROOT / "reports" / "reproduce.json"
SITE_REPORT_PATH = ROOT / "site" / "src" / "data" / "results.generated.json"


def reproduce() -> dict[str, Any]:
    """Regenerate deterministic reports consumed by docs and the project site."""
    convergence = run_simulation(seed=2026, schedules=1000)
    gossip = run_gossip_suite(seed=42)
    duplicate = evaluate_dedupe()
    optimization = compare_selection(_sample_operations(), byte_budget=1800)
    report: dict[str, Any] = {
        "generated_by": "uv run python -m syncmesh.simulation.run --reproduce",
        "synthetic": True,
        "convergence": convergence,
        "gossip": gossip,
        "duplicate_detection": duplicate,
        "bandwidth_selection": optimization,
        "honest_reading": (
            "Generated schedule and synthetic catalogue results measure algorithm behavior, "
            "not production performance or correctness for every possible execution."
        ),
    }
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(payload, encoding="utf-8")
    if SITE_REPORT_PATH.parent.exists():
        SITE_REPORT_PATH.write_text(
            json.dumps(_site_results(report), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def _site_results(report: dict[str, Any]) -> dict[str, Any]:
    """Select simple generated metrics for the static page."""
    return {
        "synthetic": True,
        "convergence": report["convergence"],
        "duplicate_detection": report["duplicate_detection"],
        "bandwidth_selection": report["bandwidth_selection"],
        "gossip": report["gossip"],
    }


def _sample_operations() -> list[Operation]:
    """Build a fixed synthetic batch with mixed operation values and payload sizes."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    operations = [
        Operation(
            operation_id="node-a:1",
            origin_node_id="node-a",
            origin_seq=1,
            entity_id="sample-item",
            op_type=OpType.CREATE,
            payload={
                "fields": {"name": "Sample rice", "category": "Grains", "price": 4.5},
                "quantity": 10,
            },
            base_vector={},
            hlc=HLC(1_800_000_000_000, 0),
            wall_clock=now,
        )
    ]
    for index in range(1, 18):
        origin = f"node-{index % 3}"
        sequence = index // 3 + 1
        op_type = (OpType.SET_FIELD, OpType.ADJUST_QUANTITY, OpType.DELETE)[index % 3]
        payload = (
            {"fields": {"name": f"Updated sample item {index}"}}
            if op_type is OpType.SET_FIELD
            else {"delta": index - 8}
            if op_type is OpType.ADJUST_QUANTITY
            else {}
        )
        operations.append(
            Operation(
                operation_id=f"{origin}:{sequence}",
                origin_node_id=origin,
                origin_seq=sequence,
                entity_id=f"sample-item-{index}",
                op_type=op_type,
                payload=payload,
                base_vector={},
                hlc=HLC(1_800_000_000_000 + index, index),
                wall_clock=now + timedelta(milliseconds=index),
            )
        )
    return operations


def main() -> None:
    """Run either a single failing-seed replay or the full report generator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reproduce", action="store_true")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--schedules", type=int, default=1000)
    args = parser.parse_args()
    result = (
        reproduce()
        if args.reproduce
        else run_schedule(args.seed)
        if args.schedules == 1
        else run_simulation(args.seed, args.schedules)
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

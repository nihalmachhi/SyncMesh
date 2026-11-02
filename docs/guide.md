# SyncMesh learning guide

SyncMesh is an educational offline-first inventory replication lab. Each node writes to its own SQLite database and exchanges immutable operations with its peers when they are reachable. The current prototype demonstrates per-origin sequence numbers, version vectors, additive stock changes, and deterministic field conflict handling; it does not yet promise strong consistency or production-grade convergence.

## Start the lab

Requirements: Docker Desktop with its engine running.

```sh
docker compose up --build
```

Open the dashboard at <http://localhost:5173>. The node APIs are available on ports 8001, 8002, and 8003. Stop the lab with `docker compose down`; remove demo databases only with `docker compose down -v`.

## Follow a change

1. The dashboard sends an inventory request to one node.
2. The node appends an operation and updates its local SQLite view in a transaction.
3. The synchronizer compares peer version vectors and exchanges missing operations.
4. A replica ignores duplicate operation IDs and buffers gaps in an origin's sequence.
5. Field changes use causal context plus a deterministic tie-break; stock changes apply signed deltas.

The API and storage implementation live under `src/syncmesh/node/`; wire message and vector-clock types live under `src/syncmesh/protocol/`. The dashboard is in `dashboard/`. Keep the demo bound to a trusted network: this prototype does not yet authenticate peers or administrators.

## Development

Install development dependencies with `uv sync --extra dev`, then run `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy src`.

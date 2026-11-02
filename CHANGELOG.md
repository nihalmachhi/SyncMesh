# Changelog

Notable changes to SyncMesh are recorded here.

## Unreleased

### Decisions

- Baseline before phase 0: `uv run pytest -q` passed 3 tests after installing the declared `dev` extra. The first invocation could not find `pytest` because the virtual environment had not been synced.
- The checkout had no `frontend/` or `docs/` directory, although Compose and the README referenced both. The dashboard was restored from repository history and renamed to `dashboard/`; a current Markdown guide replaces the missing guide reference.
- The unused PDF generator was removed rather than adding an undeclared ReportLab dependency. No generated PDF was tracked.

### Changed

- Begin phase 0 repository cleanup: conventional `dashboard/`, `core/`, and node router layout; normalized editor and line-ending settings.
- Added causal operation buffering, per-field HLC registers, atomic peer batches, bounded indexed log pages, symmetric open conflicts, and ordinary-operation conflict resolution.
- Added timestamped peer HMAC and constant-time admin bearer checks, peer retry backoff/logging, paginated exchanges, sync history, and per-peer health status.
- Added SQLite `user_version` migration v1, container factory entry point, non-root image and healthcheck, MIT license, security policy, CI, Dependabot, and existing project icon favicon.
- Added regression, migration, HTTP sync pagination, HLC, and randomized convergence tests; coverage is gated at 85%.
- Extended merge state with per-origin PN-counter components and permanent remove-wins tombstones; added stable-prefix compaction and snapshot bootstrap for stale peers.
- Added per-origin hash-range digests, byte-budgeted causal operation selection, adaptive sync intervals, write rate limits, Prometheus gauges, causal/topology debug APIs, and deterministic gossip experiments.
- Added optional offline text duplicate/category suggestions and local QR, EAN-13, content-addressed blob, and photo dHash utilities.
- Rebuilt the local dashboard with bearer-token input, pause/resume controls, partition replay, conflict review, and causal/topology SVGs.
- Added consistency, protocol, architecture, threat-model, and evaluation documentation.

### Decisions

- Network UI sync and conflict review require the configured admin bearer token outside development. The dashboard UI will expose a credential entry flow when the authenticated controls are integrated in Phase 2.
- Docker Compose defaults to development mode for the local lab. Production deployments fail closed when admin or peer secrets are missing.
- Compaction waits for a vector report from every configured peer and only drops the shared stable prefix. A materialized snapshot supports peers returning after compaction.
- The optional text threshold is selected on the calibration subset of a ten-example generated synthetic set; held-out metrics are too small to estimate real catalog quality.

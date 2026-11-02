# Changelog

Notable changes to SyncMesh are recorded here.

## Unreleased

### Decisions

- Baseline before phase 0: `uv run pytest -q` passed 3 tests after installing the declared `dev` extra. The first invocation could not find `pytest` because the virtual environment had not been synced.
- The checkout had no `frontend/` or `docs/` directory, although Compose and the README referenced both. The dashboard was restored from repository history and renamed to `dashboard/`; a current Markdown guide replaces the missing guide reference.
- The unused PDF generator was removed rather than adding an undeclared ReportLab dependency. No generated PDF was tracked.

### Changed

- Begin phase 0 repository cleanup: conventional `dashboard/`, `core/`, and node router layout; normalized editor and line-ending settings.

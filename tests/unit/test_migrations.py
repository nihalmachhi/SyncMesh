"""Compatibility tests for upgrading existing SQLite node databases."""

import sqlite3

from syncmesh.node.storage.migrations import migrate


def test_migration_adds_register_and_hlc_columns_to_legacy_schema(tmp_path):
    """Legacy databases gain the two Phase 1 columns and a schema version."""
    database = tmp_path / "legacy.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE entities(entity_id TEXT PRIMARY KEY, fields TEXT)")
        connection.execute("CREATE TABLE change_log(operation_id TEXT PRIMARY KEY)")
        connection.row_factory = sqlite3.Row
        migrate(connection)

        entity_columns = {row["name"] for row in connection.execute("PRAGMA table_info(entities)")}
        log_columns = {row["name"] for row in connection.execute("PRAGMA table_info(change_log)")}
        assert {"field_registers"} <= entity_columns
        assert {"hlc"} <= log_columns
        assert {"pn_counter"} <= entity_columns
        assert {"tombstone"} <= entity_columns
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4

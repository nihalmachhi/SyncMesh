"""Versioned SQLite schema upgrades for existing SyncMesh node databases."""

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply additive migrations and update SQLite's schema version."""
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version < 1:
        _add_column(connection, "entities", "field_registers", "TEXT NOT NULL DEFAULT '{}'")
        _add_column(connection, "change_log", "hlc", "TEXT NOT NULL DEFAULT ''")
        connection.execute("PRAGMA user_version = 1")
        version = 1
    if version < 2:
        _add_column(connection, "entities", "pn_counter", "TEXT NOT NULL DEFAULT '{}'")
        connection.execute("PRAGMA user_version = 2")
        version = 2
    if version < 3:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS peer_vectors("
            "peer_id TEXT PRIMARY KEY, vector TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.execute("PRAGMA user_version = 3")
        version = 3
    if version < 4:
        _add_column(connection, "entities", "tombstone", "TEXT")
        connection.execute("PRAGMA user_version = 4")


def _add_column(connection: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    """Add a column only when the legacy table does not have it yet."""
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

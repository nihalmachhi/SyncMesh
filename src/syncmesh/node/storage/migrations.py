"""Versioned SQLite schema upgrades for existing SyncMesh node databases."""

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply additive migrations and update SQLite's schema version."""
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version < 1:
        _add_column(connection, "entities", "field_registers", "TEXT NOT NULL DEFAULT '{}'")
        _add_column(connection, "change_log", "hlc", "TEXT NOT NULL DEFAULT ''")
        connection.execute("PRAGMA user_version = 1")


def _add_column(connection: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    """Add a column only when the legacy table does not have it yet."""
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

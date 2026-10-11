"""SQLite file lifecycle for one node."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    """Own a single node's private SQLite file."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        """Create the database directory and apply schema."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self.connect() as connection:
            connection.executescript(schema)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Open a transaction with foreign keys and WAL enabled."""
        connection = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

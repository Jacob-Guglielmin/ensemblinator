import sqlite3
import threading
from pathlib import Path
from typing import Protocol


class ConnectionProvider(Protocol):
    def _connection(self) -> sqlite3.Connection: ...


class _WithDBConnection:
    def __init__(self, state_directory: Path):
        self._db_path = state_directory / "ensemblinator-db.sqlite3"
        self._local = threading.local()

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=15)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def close(self):
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()

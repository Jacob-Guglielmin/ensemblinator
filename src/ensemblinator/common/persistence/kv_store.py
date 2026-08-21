import sqlite3
from pathlib import Path

def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.execute("CREATE TABLE IF NOT EXISTS kv (job_id TEXT, key TEXT, value TEXT, PRIMARY KEY (job_id, key))")
    return conn

def kv_get(db_path: Path, job_id: str, key: str) -> str | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM kv WHERE job_id=? AND key=?", (job_id, key)).fetchone()
        return row[0] if row else None

def kv_set(db_path: Path, job_id: str, key: str, value: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO kv VALUES (?, ?, ?)", (job_id, key, value))

def kv_delete(db_path: Path, job_id: str, key: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM kv WHERE job_id=? AND key=?", (job_id, key))

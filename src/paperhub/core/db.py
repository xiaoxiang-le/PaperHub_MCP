import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS paper(
 id TEXT PRIMARY KEY, file_path TEXT NOT NULL UNIQUE, file_hash TEXT NOT NULL,
 file_type TEXT NOT NULL, file_mtime INTEGER NOT NULL, file_size INTEGER NOT NULL,
 status TEXT NOT NULL, fail_reason TEXT, title TEXT, abstract TEXT,
 document TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_paper_hash ON paper(file_hash);
CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts USING fts5(paper_id UNINDEXED, title, abstract, keywords);
CREATE TABLE IF NOT EXISTS object(kind TEXT, id TEXT, data TEXT NOT NULL,
 PRIMARY KEY(kind, id));
CREATE TABLE IF NOT EXISTS translate_chunk(task_id TEXT, idx INTEGER, source_hash TEXT,
 target_text TEXT NOT NULL, PRIMARY KEY(task_id,idx));
CREATE TABLE IF NOT EXISTS confirmation(token_hash TEXT PRIMARY KEY, action TEXT,
 payload_hash TEXT, expires REAL);
"""


class Database:
    """Short serialized transactions; no cursor survives its connection."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            connection = sqlite3.connect(self.path, timeout=30)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                with connection:
                    yield connection
            finally:
                connection.close()

    def put(self, kind: str, item_id: str, data: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO object VALUES(?,?,?)",
                (kind, item_id, json.dumps(data, ensure_ascii=False)),
            )

    def get(self, kind: str, item_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT data FROM object WHERE kind=? AND id=?", (kind, item_id)
            ).fetchone()
            return json.loads(row["data"]) if row else None

    def list(self, kind: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [
                json.loads(r["data"])
                for r in conn.execute(
                    "SELECT data FROM object WHERE kind=? ORDER BY rowid", (kind,)
                )
            ]

    def delete(self, kind: str, item_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM object WHERE kind=? AND id=?", (kind, item_id))

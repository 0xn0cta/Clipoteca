from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTIVE_STATUSES = ("queued", "downloading", "paused", "failed")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "Clipoteca"


class Database:
    """Small SQLite store for resumable queue state and local preferences."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else app_data_dir() / "clipoteca.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()
        self._recover_interrupted_items()

    def _create_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    is_playlist INTEGER NOT NULL,
                    destination TEXT NOT NULL,
                    output_format TEXT NOT NULL,
                    quality TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                    source_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    duration REAL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                    total_bytes INTEGER,
                    speed REAL,
                    eta REAL,
                    output_path TEXT,
                    error TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS items_status_idx ON items(status);
                CREATE INDEX IF NOT EXISTS items_batch_idx ON items(batch_id);
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def _recover_interrupted_items(self) -> None:
        # Never silently start work after a crash. The user can resume these items.
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE items SET status='paused', updated_at=? WHERE status='downloading'",
                (utc_now(),),
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def set_preference(self, key: str, value: Any) -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO preferences(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, encoded),
            )

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._connection.execute(
                "SELECT value FROM preferences WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row["value"]) if row else default

    def get_preferences(self) -> dict[str, Any]:
        with self._lock:
            rows = self._connection.execute("SELECT key, value FROM preferences").fetchall()
        return {row["key"]: json.loads(row["value"]) for row in rows}

    def create_batch(self, batch: dict[str, Any], items: list[dict[str, Any]]) -> None:
        now = utc_now()
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO batches(id, source_url, title, is_playlist, destination, "
                "output_format, quality, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    batch["id"],
                    batch["source_url"],
                    batch["title"],
                    int(batch["is_playlist"]),
                    batch["destination"],
                    batch["output_format"],
                    str(batch["quality"]),
                    now,
                ),
            )
            self._connection.executemany(
                "INSERT INTO items(id, batch_id, source_id, source_url, title, duration, "
                "status, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?)",
                [
                    (
                        item["id"],
                        batch["id"],
                        item["source_id"],
                        item["source_url"],
                        item["title"],
                        item.get("duration"),
                        now,
                    )
                    for item in items
                ],
            )

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT items.*, batches.source_url AS batch_source_url, "
                "batches.title AS batch_title, batches.destination, "
                "batches.output_format, batches.quality, batches.is_playlist "
                "FROM items JOIN batches ON batches.id=items.batch_id WHERE items.id=?",
                (item_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_item(self, item_id: str, **values: Any) -> None:
        allowed = {
            "status", "progress", "downloaded_bytes", "total_bytes", "speed", "eta",
            "output_path", "error", "attempts",
        }
        updates = {key: value for key, value in values.items() if key in allowed}
        if not updates:
            return
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key}=?" for key in updates)
        with self._lock, self._connection:
            self._connection.execute(
                f"UPDATE items SET {assignments} WHERE id=?",
                (*updates.values(), item_id),
            )

    def batch_items(self, batch_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM items WHERE batch_id=? ORDER BY rowid", (batch_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_cancelled(self, item_id: str) -> None:
        self.update_item(item_id, status="cancelled", error=None)

    def items_with_status(self, statuses: tuple[str, ...]) -> list[dict[str, Any]]:
        if not statuses:
            return []
        placeholders = ",".join("?" for _ in statuses)
        with self._lock:
            rows = self._connection.execute(
                "SELECT items.*, batches.title AS batch_title, batches.source_url AS batch_source_url, "
                "batches.is_playlist, batches.destination, batches.output_format, batches.quality, "
                "batches.created_at AS batch_created_at "
                "FROM items JOIN batches ON batches.id=items.batch_id "
                f"WHERE items.status IN ({placeholders}) ORDER BY batches.created_at DESC, items.rowid",
                statuses,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_queue_state(self) -> dict[str, Any]:
        return {
            "queue": self.items_with_status(ACTIVE_STATUSES),
            "history": self.items_with_status(("completed",)),
            "counts": {
                "active": len(self.items_with_status(ACTIVE_STATUSES)),
                "completed": len(self.items_with_status(("completed",))),
            },
            "preferences": self.get_preferences(),
        }

    def clear_history(self) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute("DELETE FROM items WHERE status='completed'")
            self._connection.execute(
                "DELETE FROM batches WHERE NOT EXISTS "
                "(SELECT 1 FROM items WHERE items.batch_id=batches.id)"
            )
        return cursor.rowcount

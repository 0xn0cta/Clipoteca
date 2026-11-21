from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ACTIVE_STATUSES = ("queued", "downloading", "paused", "failed")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_seconds(started_at: str | None, ended_at: str) -> float:
    if not started_at:
        return 0.0
    try:
        return max(
            0.0,
            (datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)).total_seconds(),
        )
    except ValueError:
        return 0.0


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
                    download_phase TEXT,
                    download_steps TEXT,
                    output_path TEXT,
                    error TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    download_attempt_started_at TEXT,
                    download_elapsed_seconds REAL NOT NULL DEFAULT 0,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS items_status_idx ON items(status);
                CREATE INDEX IF NOT EXISTS items_batch_idx ON items(batch_id);
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS worker_actions (
                    item_id TEXT PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
                    action TEXT NOT NULL
                );
                """
            )
            columns = {
                row["name"] for row in self._connection.execute("PRAGMA table_info(items)")
            }
            migrations = {
                "download_attempt_started_at": "TEXT",
                "download_elapsed_seconds": "REAL NOT NULL DEFAULT 0",
                "completed_at": "TEXT",
                "download_phase": "TEXT",
                "download_steps": "TEXT",
            }
            for name, declaration in migrations.items():
                if name not in columns:
                    self._connection.execute(
                        f"ALTER TABLE items ADD COLUMN {name} {declaration}"
                    )
            self._connection.execute(
                "UPDATE items SET completed_at=updated_at "
                "WHERE status='completed' AND completed_at IS NULL"
            )

    def recover_interrupted_items(self) -> None:
        """Mark orphaned downloads paused after the caller owns the worker lock."""
        with self._lock, self._connection:
            now = utc_now()
            rows = self._connection.execute(
                "SELECT id, download_attempt_started_at, download_elapsed_seconds "
                "FROM items WHERE status='downloading'"
            ).fetchall()
            for row in rows:
                elapsed = float(row["download_elapsed_seconds"] or 0)
                elapsed += _elapsed_seconds(row["download_attempt_started_at"], now)
                self._connection.execute(
                    "UPDATE items SET status='paused', download_elapsed_seconds=?, "
                    "download_attempt_started_at=NULL, updated_at=? "
                    "WHERE id=? AND status='downloading'",
                    (elapsed, now, row["id"]),
                )
            self._connection.execute(
                "DELETE FROM worker_actions WHERE item_id IN "
                "(SELECT id FROM items WHERE status='paused')"
            )

    def claim_queued_item(self, item_id: str) -> bool:
        with self._lock, self._connection:
            now = utc_now()
            cursor = self._connection.execute(
                "UPDATE items SET status='downloading', error=NULL, download_phase='preparing', "
                "total_bytes=NULL, speed=NULL, eta=NULL, "
                "download_attempt_started_at=?, updated_at=? WHERE id=? AND status='queued'",
                (now, now, item_id),
            )
            return cursor.rowcount == 1

    @contextmanager
    def block_download_claims(self) -> Iterator[None]:
        """Keep another connection from claiming a task during partial cleanup."""
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            yield

    def set_worker_action(self, item_id: str, action: str) -> str | None:
        """Apply the action to a waiting item or signal its active worker."""
        if action not in {"pause", "cancel"}:
            raise ValueError("Acción de worker no válida.")
        target_status = "cancelled" if action == "cancel" else "paused"
        with self._lock, self._connection:
            # Start the write transaction before inspecting the running state.
            cursor = self._connection.execute(
                "UPDATE items SET status=?, updated_at=?, "
                "error=CASE WHEN ?='cancel' THEN NULL ELSE error END "
                "WHERE id=? AND (status='queued' OR (status='paused' AND ?='cancel'))",
                (target_status, utc_now(), action, item_id, action),
            )
            if cursor.rowcount:
                self._connection.execute("DELETE FROM worker_actions WHERE item_id=?", (item_id,))
                return target_status
            cursor = self._connection.execute(
                "INSERT INTO worker_actions(item_id, action) "
                "SELECT id, ? FROM items WHERE id=? AND status='downloading' "
                "ON CONFLICT(item_id) DO UPDATE SET action=excluded.action "
                "WHERE worker_actions.action<>'cancel' OR excluded.action='cancel'",
                (action, item_id),
            )
            return "downloading" if cursor.rowcount else None

    def get_worker_action(self, item_id: str) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT action FROM worker_actions WHERE item_id=?", (item_id,)
            ).fetchone()
        return str(row["action"]) if row else None

    def clear_worker_action(self, item_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM worker_actions WHERE item_id=?", (item_id,))

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
            "output_path", "error", "attempts", "download_phase", "download_steps",
        }
        updates = {key: value for key, value in values.items() if key in allowed}
        if not updates:
            return
        with self._lock, self._connection:
            current = self._connection.execute(
                "SELECT status, download_attempt_started_at, download_elapsed_seconds, completed_at "
                "FROM items WHERE id=?",
                (item_id,),
            ).fetchone()
            if not current:
                return

            now = utc_now()
            next_status = updates.get("status")
            if next_status == "downloading":
                if current["status"] != "downloading" or not current["download_attempt_started_at"]:
                    updates["download_attempt_started_at"] = now
            elif next_status is not None and current["status"] == "downloading":
                elapsed = float(current["download_elapsed_seconds"] or 0)
                elapsed += _elapsed_seconds(current["download_attempt_started_at"], now)
                updates["download_elapsed_seconds"] = elapsed
                updates["download_attempt_started_at"] = None

            if next_status == "completed" and not current["completed_at"]:
                updates["completed_at"] = now
            updates["updated_at"] = now
            assignments = ", ".join(f"{key}=?" for key in updates)
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

from __future__ import annotations

import tempfile
import time
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from threading import Event

from clipoteca.engine import UserFacingError
from clipoteca.manager import DownloadManager
from clipoteca.storage import Database


class ManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database = Database(self.root / "clipoteca.sqlite3")
        self.manager = None

    def tearDown(self) -> None:
        if self.manager:
            self.manager.shutdown(pause_active=False)
        self.database.close()
        self.temp_dir.cleanup()

    def wait_for(self, predicate, timeout: float = 3) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.025)
        return False

    def make_analysis(self) -> dict:
        return {
            "source_url": "https://example.org/list",
            "title": "Example list",
            "is_playlist": True,
            "items": [{
                "id": "analysis-item-1",
                "source_id": "item-1",
                "source_url": "https://example.org/item-1",
                "title": "Item 1",
                "duration": 12,
                "available": True,
            }],
        }

    def test_downloaded_items_move_to_history_and_clear_does_not_touch_files(self) -> None:
        complete = Event()

        def fake_downloader(**kwargs):
            kwargs["progress"]({"progress": 0.5, "downloaded_bytes": 5, "total_bytes": 10})
            complete.set()
            return {"paths": ["C:/Downloads/item.mp4"], "duplicate": False}

        manager = DownloadManager(self.database, downloader=fake_downloader, autostart=False)
        self.manager = manager
        manager.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto", str(self.root / "downloads"))
        self.assertTrue(self.wait_for(lambda: bool(self.database.items_with_status(("queued",)))))
        manager.start()
        self.assertTrue(complete.wait(2))
        self.assertTrue(self.wait_for(lambda: bool(self.database.items_with_status(("completed",)))))
        state = manager.get_state()
        self.assertEqual(len(state["queue"]), 0)
        self.assertEqual(len(state["history"]), 1)
        self.assertEqual(manager.clear_history(), 1)
        self.assertEqual(self.database.items_with_status(("completed",)), [])
        manager.shutdown(pause_active=False)

    def test_non_retryable_failure_stays_in_queue(self) -> None:
        def failing_downloader(**_kwargs):
            raise UserFacingError("Este sitio no es compatible.")

        manager = DownloadManager(self.database, downloader=failing_downloader, autostart=False)
        self.manager = manager
        manager.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto", str(self.root / "downloads"))
        manager.start()
        self.assertTrue(self.wait_for(lambda: bool(self.database.items_with_status(("failed",)))))
        state = manager.get_state()
        self.assertEqual(state["queue"][0]["status"], "failed")
        self.assertEqual(state["history"], [])
        manager.shutdown(pause_active=False)

    def test_transient_failure_is_retried_three_times(self) -> None:
        calls = 0

        def retrying_downloader(**_kwargs):
            nonlocal calls
            calls += 1
            if calls < 4:
                raise UserFacingError("No se pudo conectar.", retryable=True)
            return {"paths": ["item.mp4"], "duplicate": False}

        manager = DownloadManager(self.database, downloader=retrying_downloader, autostart=False)
        self.manager = manager
        manager._wait_or_stop = lambda _item_id, _seconds: True
        manager.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto", str(self.root / "downloads"))
        self.assertTrue(self.wait_for(lambda: bool(self.database.items_with_status(("completed",)))))
        self.assertEqual(calls, 4)
        self.assertEqual(self.database.items_with_status(("failed",)), [])

    def test_cancel_removes_only_the_partial_file(self) -> None:
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager
        destination = self.root / "downloads"
        destination.mkdir()
        partial = destination / "Item 1 [item-1].mp4.part"
        completed = destination / "Item 1 [item-1].mp4"
        partial.write_bytes(b"partial")
        completed.write_bytes(b"complete")
        manager._remove_partials({
            "destination": str(destination),
            "is_playlist": False,
            "batch_title": "Example list",
            "title": "Item 1",
            "source_id": "item-1",
        })
        self.assertFalse(partial.exists())
        self.assertTrue(completed.exists())

    def test_unfinished_downloads_are_recovered_as_paused(self) -> None:
        batch = {
            "id": "batch-1", "source_url": "https://example.org", "title": "Batch",
            "is_playlist": False, "destination": str(self.root), "output_format": "video", "quality": "auto",
        }
        item = {"id": "item-1", "source_id": "source-1", "source_url": "https://example.org/item", "title": "Item"}
        self.database.create_batch(batch, [item])
        self.database.update_item("item-1", status="downloading")
        self.database.close()
        self.database = Database(self.root / "clipoteca.sqlite3")
        recovered = self.database.get_item("item-1")
        self.assertEqual(recovered["status"], "paused")

    def test_history_keeps_openable_output_paths(self) -> None:
        batch = {
            "id": "batch-history", "source_url": "https://example.org", "title": "Batch",
            "is_playlist": False, "destination": str(self.root), "output_format": "both", "quality": "auto",
        }
        item = {"id": "history-item", "source_id": "source-1", "source_url": "https://example.org/item", "title": "Item"}
        self.database.create_batch(batch, [item])
        paths = [str(self.root / "item.mp4"), str(self.root / "item.mp3")]
        self.database.update_item("history-item", status="completed", output_path=json.dumps(paths))
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager
        self.assertEqual(manager.get_history_path("history-item", 1), Path(paths[1]))
        self.assertEqual(manager.get_state()["history"][0]["output_paths"], paths)


if __name__ == "__main__":
    unittest.main()

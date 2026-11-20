from __future__ import annotations

import tempfile
import time
import unittest
import json
from pathlib import Path
from threading import Event
from unittest.mock import patch

from clipoteca.api import DesktopApi


class DesktopApiTests(unittest.TestCase):
    def test_analysis_can_be_queued_through_the_desktop_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = DesktopApi(database_path=Path(directory) / "db.sqlite3")
            finished = Event()

            def fake_downloader(**_kwargs):
                finished.set()
                return {"paths": [str(Path(directory) / "saved.mp4")], "duplicate": False}

            api.manager.downloader = fake_downloader
            analysis = {
                "title": "Sample",
                "source_url": "https://example.org/list",
                "is_playlist": False,
                "items": [{
                    "id": "item-one",
                    "source_id": "one",
                    "source_url": "https://example.org/one",
                    "title": "Video one",
                    "duration": 10,
                    "available": True,
                }],
            }
            try:
                with patch("clipoteca.api.analyze_url", return_value=analysis):
                    analyzed = api.analyze_url("https://example.org/list")
                self.assertTrue(analyzed["ok"])
                queued = api.enqueue_batch(
                    analyzed["analysis_id"], ["item-one"], "video", "auto", str(Path(directory) / "downloads")
                )
                self.assertTrue(queued["ok"])
                self.assertTrue(finished.wait(2))
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    if api.get_queue_state()["history"]:
                        break
                    time.sleep(0.02)
                state = api.get_queue_state()
                self.assertEqual(len(state["history"]), 1)
                self.assertEqual(state["history"][0]["title"], "Video one")
            finally:
                api.shutdown()

    def test_history_file_opens_with_the_windows_association(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = DesktopApi(database_path=Path(directory) / "db.sqlite3")
            media_file = Path(directory) / "finished.mp4"
            media_file.write_bytes(b"media")
            batch = {
                "id": "open-batch", "source_url": "https://example.org", "title": "Batch",
                "is_playlist": False, "destination": directory, "output_format": "video", "quality": "auto",
            }
            item = {
                "id": "open-item", "source_id": "source", "source_url": "https://example.org/item",
                "title": "Finished item",
            }
            api.database.create_batch(batch, [item])
            api.database.update_item("open-item", status="completed", output_path=json.dumps([str(media_file)]))
            try:
                with patch("clipoteca.api.os.startfile", create=True) as start_file:
                    result = api.open_history_file("open-item")
                self.assertTrue(result["ok"])
                start_file.assert_called_once_with(str(media_file))
            finally:
                api.shutdown()


if __name__ == "__main__":
    unittest.main()

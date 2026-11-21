from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import json
import sqlite3
import unittest
from unittest.mock import patch
from pathlib import Path
from threading import Event, Lock, current_thread

from clipoteca.engine import DownloadInterrupted, UserFacingError, safe_filename
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
            "source_url": "https://www.youtube.com/playlist?list=sample",
            "title": "Example list",
            "is_playlist": True,
            "items": [{
                "id": "analysis-item-1",
                "source_id": "item-1",
                "source_url": "https://www.youtube.com/watch?v=item-1",
                "title": "Item 1",
                "duration": 12,
                "available": True,
            }],
        }

    def create_timing_item(self) -> None:
        self.database.create_batch(
            {
                "id": "timing-batch",
                "source_url": "https://www.youtube.com/watch?v=abcdefghijk",
                "title": "Timing batch",
                "is_playlist": False,
                "destination": str(self.root),
                "output_format": "video",
                "quality": "auto",
            },
            [{
                "id": "timing-item",
                "source_id": "abcdefghijk",
                "source_url": "https://www.youtube.com/watch?v=abcdefghijk",
                "title": "Timing item",
                "duration": 45,
            }],
        )

    def test_download_time_accumulates_across_pause_and_resume(self) -> None:
        self.create_timing_item()
        timestamps = [
            "2025-04-01T12:00:00+00:00",
            "2025-04-01T12:00:10+00:00",
            "2025-04-01T12:01:00+00:00",
            "2025-04-01T12:01:25+00:00",
        ]

        with patch("clipoteca.storage.utc_now", side_effect=timestamps):
            self.database.update_item("timing-item", status="downloading")
            self.database.update_item("timing-item", status="paused")
            self.database.update_item("timing-item", status="downloading")
            self.database.update_item("timing-item", status="completed")

        item = self.database.get_item("timing-item")
        self.assertEqual(item["download_elapsed_seconds"], 35)
        self.assertEqual(item["completed_at"], timestamps[-1])
        self.assertIsNone(item["download_attempt_started_at"])

    def test_recovery_records_elapsed_download_time_before_pausing(self) -> None:
        self.create_timing_item()
        started_at = "2025-04-01T12:00:00+00:00"
        recovered_at = "2025-04-01T12:00:12+00:00"

        with patch("clipoteca.storage.utc_now", return_value=started_at):
            self.database.update_item("timing-item", status="downloading")
        with patch("clipoteca.storage.utc_now", return_value=recovered_at):
            self.database.recover_interrupted_items()

        item = self.database.get_item("timing-item")
        self.assertEqual(item["status"], "paused")
        self.assertEqual(item["download_elapsed_seconds"], 12)
        self.assertIsNone(item["download_attempt_started_at"])

    def test_existing_database_migrates_history_timestamps(self) -> None:
        path = self.root / "legacy.sqlite3"
        connection = sqlite3.connect(path)
        connection.executescript(
            """
            CREATE TABLE batches (
                id TEXT PRIMARY KEY, source_url TEXT NOT NULL, title TEXT NOT NULL,
                is_playlist INTEGER NOT NULL, destination TEXT NOT NULL,
                output_format TEXT NOT NULL, quality TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE items (
                id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, source_id TEXT NOT NULL,
                source_url TEXT NOT NULL, title TEXT NOT NULL, duration REAL,
                status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
                downloaded_bytes INTEGER NOT NULL DEFAULT 0, total_bytes INTEGER,
                speed REAL, eta REAL, output_path TEXT, error TEXT,
                attempts INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
            );
            INSERT INTO batches VALUES (
                'legacy-batch', 'https://www.youtube.com/watch?v=abcdefghijk',
                'Legacy', 0, 'C:/Downloads', 'video', 'auto',
                '2025-04-01T11:00:00+00:00'
            );
            INSERT INTO items (
                id, batch_id, source_id, source_url, title, duration, status, updated_at
            ) VALUES (
                'legacy-item', 'legacy-batch', 'abcdefghijk',
                'https://www.youtube.com/watch?v=abcdefghijk', 'Legacy item', 30,
                'completed', '2025-04-01T12:00:00+00:00'
            );
            """
        )
        connection.close()

        migrated = Database(path)
        try:
            item = migrated.get_item("legacy-item")
            self.assertEqual(item["completed_at"], "2025-04-01T12:00:00+00:00")
            self.assertEqual(item["download_elapsed_seconds"], 0)
            self.assertIsNone(item["download_attempt_started_at"])
        finally:
            migrated.close()

    def test_downloaded_items_move_to_history_and_clear_does_not_touch_files(self) -> None:
        complete = Event()

        def fake_downloader(**kwargs):
            kwargs["progress"]({"progress": 0.5, "downloaded_bytes": 5, "total_bytes": 10})
            complete.set()
            return {"paths": ["C:/Downloads/item.mp4"], "duplicate": False}

        manager = DownloadManager(self.database, downloader=fake_downloader, autostart=False)
        self.manager = manager
        manager.set_preferences({
            "destination": str(self.root / "downloads"),
            "concurrency_mode": "manual",
            "manual_concurrency": 1,
        })
        manager.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto")
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
        manager.set_preferences({
            "destination": str(self.root / "downloads"),
            "concurrency_mode": "manual",
            "manual_concurrency": 1,
        })
        manager.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto")
        manager.start()
        self.assertTrue(self.wait_for(lambda: bool(self.database.items_with_status(("failed",)))))
        state = manager.get_state()
        self.assertEqual(state["queue"][0]["status"], "failed")
        self.assertEqual(state["history"], [])
        manager.shutdown(pause_active=False)

    def test_batch_notification_summarizes_outcomes_once(self) -> None:
        batch = {
            "id": "batch-notification", "source_url": "https://www.youtube.com/playlist?list=sample",
            "title": "Lista de prueba", "is_playlist": True, "destination": str(self.root),
            "output_format": "video", "quality": "auto",
        }
        items = [
            {"id": key, "source_id": key, "source_url": f"https://youtu.be/{key}", "title": key}
            for key in ("new", "existing", "failure")
        ]
        self.database.create_batch(batch, items)
        notices = []
        manager = DownloadManager(
            self.database, notifier=lambda title, text: notices.append((title, text)), autostart=False,
        )
        self.manager = manager
        self.database.update_item("new", status="completed")
        self.database.update_item("existing", status="completed", error="Ya existía; no se sobrescribió.")
        manager._notify_batch_if_finished(batch["id"], batch["title"])
        self.assertEqual(notices, [])

        self.database.update_item("failure", status="failed", error="Fallo de prueba")
        manager._notify_batch_if_finished(batch["id"], batch["title"])
        manager._notify_batch_if_finished(batch["id"], batch["title"])
        self.assertEqual(notices, [
            ("Lote terminado con fallos", "Lista de prueba\n1 nuevos · 1 ya existentes · 1 por reintentar"),
        ])

    def test_transient_failure_is_retried_three_times(self) -> None:
        calls = 0
        retry_states = []

        def retrying_downloader(**kwargs):
            nonlocal calls
            calls += 1
            if calls < 4:
                kwargs["progress"]({"phase": "video", "total_bytes": 10, "eta": 2, "speed": 5})
                raise UserFacingError("No se pudo conectar.", retryable=True)
            return {"paths": ["item.mp4"], "duplicate": False}

        def observe_backoff(item_id, delay):
            state = self.database.get_item(item_id)
            retry_states.append((delay, state["download_phase"], state["eta"], state["speed"]))
            return True

        manager = DownloadManager(self.database, downloader=retrying_downloader, autostart=False)
        self.manager = manager
        manager.set_preferences({
            "destination": str(self.root / "downloads"),
            "concurrency_mode": "manual",
            "manual_concurrency": 1,
        })
        manager._wait_or_stop = observe_backoff
        manager.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto")
        self.assertTrue(self.wait_for(lambda: bool(self.database.items_with_status(("completed",)))))
        self.assertEqual(calls, 4)
        self.assertEqual(retry_states, [(delay, "retrying", None, None) for delay in (1, 2, 4)])
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
            "id": "batch-1", "source_url": "https://www.youtube.com/watch?v=batch", "title": "Batch",
            "is_playlist": False, "destination": str(self.root), "output_format": "video", "quality": "auto",
        }
        item = {"id": "item-1", "source_id": "source-1", "source_url": "https://www.youtube.com/watch?v=item", "title": "Item"}
        self.database.create_batch(batch, [item])
        self.database.update_item("item-1", status="downloading")
        self.database.close()
        self.database = Database(self.root / "clipoteca.sqlite3")
        self.assertEqual(self.database.get_item("item-1")["status"], "downloading")
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager
        manager.start()
        self.assertTrue(self.wait_for(lambda: self.database.get_item("item-1")["status"] == "paused"))
        recovered = self.database.get_item("item-1")
        self.assertEqual(recovered["status"], "paused")

    def test_worker_actions_are_shared_by_database_connections(self) -> None:
        batch = {
            "id": "batch-action", "source_url": "https://www.youtube.com/watch?v=batch", "title": "Batch",
            "is_playlist": False, "destination": str(self.root), "output_format": "video", "quality": "auto",
        }
        item = {"id": "item-action", "source_id": "source-1", "source_url": "https://www.youtube.com/watch?v=item", "title": "Item"}
        self.database.create_batch(batch, [item])
        self.database.update_item("item-action", status="downloading")
        other_database = Database(self.root / "clipoteca.sqlite3")
        try:
            manager = DownloadManager(self.database, autostart=False)
            self.manager = manager
            other_database.set_worker_action("item-action", "pause")
            self.assertEqual(manager._get_action("item-action"), "pause")
            other_database.set_worker_action("item-action", "cancel")
            other_database.set_worker_action("item-action", "pause")
            self.assertEqual(manager._get_action("item-action"), "cancel")
        finally:
            other_database.close()

    def test_second_manager_cannot_duplicate_worker_and_can_cancel_it(self) -> None:
        started = Event()
        owner_calls: list[str] = []
        second_calls: list[str] = []

        def owner_downloader(**kwargs):
            owner_calls.append("owner")
            started.set()
            while True:
                action = kwargs["should_stop"]()
                if action:
                    raise DownloadInterrupted(action)
                kwargs["progress"]({"progress": 0.1, "downloaded_bytes": 1})
                time.sleep(0.01)

        def second_downloader(**_kwargs):
            second_calls.append("second")
            return {"paths": ["unused.mp4"], "duplicate": False}

        manager = DownloadManager(self.database, downloader=owner_downloader, autostart=False)
        self.manager = manager
        manager.set_preferences({
            "destination": str(self.root / "downloads"),
            "concurrency_mode": "manual",
            "manual_concurrency": 1,
        })
        manager.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto")
        self.assertTrue(started.wait(2))

        other_database = Database(self.root / "clipoteca.sqlite3")
        other_manager = DownloadManager(other_database, downloader=second_downloader, autostart=False)
        try:
            other_manager.start()
            self.assertTrue(self.wait_for(lambda: manager.owns_worker))
            time.sleep(0.3)
            self.assertEqual(owner_calls, ["owner"])
            self.assertEqual(second_calls, [])

            item_id = self.database.items_with_status(("downloading",))[0]["id"]
            set_action_from_other_process = (
                "import sys; from clipoteca.storage import Database; "
                "db=Database(sys.argv[1]); "
                "db.set_worker_action(sys.argv[2], sys.argv[3]); db.close()"
            )
            subprocess.run([
                sys.executable, "-c", set_action_from_other_process,
                str(self.database.path), item_id, "pause",
            ], check=True, capture_output=True, text=True)
            self.assertTrue(
                self.wait_for(lambda: self.database.get_item(item_id)["status"] == "paused")
            )

            other_manager.resume_all()
            self.assertTrue(self.wait_for(lambda: len(owner_calls) == 2))
            self.assertTrue(
                self.wait_for(lambda: self.database.get_item(item_id)["status"] == "downloading")
            )
            subprocess.run([
                sys.executable, "-c", set_action_from_other_process,
                str(self.database.path), item_id, "cancel",
            ], check=True, capture_output=True, text=True)
            self.assertTrue(
                self.wait_for(
                    lambda: self.database.get_item(item_id)["status"] == "cancelled"
                )
            )
        finally:
            other_manager.shutdown(pause_active=False)
            other_database.close()

    def test_non_owner_manager_can_enqueue_for_the_worker_owner(self) -> None:
        owner_downloaded = Event()
        second_calls: list[str] = []

        def owner_downloader(**_kwargs):
            owner_downloaded.set()
            return {"paths": [str(self.root / "owner.mp4")], "duplicate": False}

        def second_downloader(**_kwargs):
            second_calls.append("duplicate")
            return {"paths": [str(self.root / "duplicate.mp4")], "duplicate": False}

        owner = DownloadManager(self.database, downloader=owner_downloader, autostart=False)
        self.manager = owner
        owner.set_preferences({
            "destination": str(self.root / "downloads"),
            "concurrency_mode": "manual",
            "manual_concurrency": 1,
        })
        owner.start()
        self.assertTrue(self.wait_for(lambda: owner.owns_worker))

        other_database = Database(self.root / "clipoteca.sqlite3")
        other_manager = DownloadManager(other_database, downloader=second_downloader, autostart=False)
        try:
            other_manager.start()
            queued = other_manager.enqueue(
                self.make_analysis(),
                ["analysis-item-1"],
                "video",
                "auto",
            )
            self.assertEqual(queued["queued"], 1)
            self.assertTrue(owner_downloaded.wait(2))
            self.assertTrue(self.wait_for(lambda: bool(self.database.items_with_status(("completed",)))))
            self.assertEqual(second_calls, [])
        finally:
            other_manager.shutdown(pause_active=False)
            other_database.close()

    def test_cancelled_item_is_not_claimed_after_worker_reads_it(self) -> None:
        queued_read = Event()
        allow_claim = Event()
        downloader_called = Event()

        def downloader(**_kwargs):
            downloader_called.set()
            return {"paths": [], "duplicate": False}

        owner = DownloadManager(self.database, downloader=downloader, autostart=False)
        self.manager = owner
        owner.set_preferences({
            "destination": str(self.root / "downloads"),
            "concurrency_mode": "manual",
            "manual_concurrency": 1,
        })
        batch = owner.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto", start_worker=False)
        item_id = self.database.batch_items(batch["batch_id"])[0]["id"]
        get_item = self.database.get_item

        def delayed_get_item(requested_id):
            item = get_item(requested_id)
            if current_thread().name.startswith("clipoteca-download-"):
                queued_read.set()
                allow_claim.wait(5)
            return item

        other_database = Database(self.database.path)
        try:
            controller = DownloadManager(other_database, autostart=False)
            with patch.object(self.database, "get_item", side_effect=delayed_get_item):
                try:
                    owner.start()
                    self.assertTrue(queued_read.wait(2))
                    controller.cancel_item(item_id)
                    self.assertEqual(other_database.get_item(item_id)["status"], "cancelled")
                finally:
                    allow_claim.set()
                    owner.shutdown(pause_active=False)
            self.assertFalse(downloader_called.is_set())
            self.assertEqual(get_item(item_id)["status"], "cancelled")
        finally:
            other_database.close()

    def test_cancel_signals_worker_if_it_claimed_item_during_request(self) -> None:
        started = Event()
        inspect_signal = Event()

        def downloader(**kwargs):
            started.set()
            inspect_signal.wait(5)
            if action := kwargs["should_stop"]():
                raise DownloadInterrupted(action)
            return {"paths": [], "duplicate": False}

        owner = DownloadManager(self.database, downloader=downloader, autostart=False)
        self.manager = owner
        owner.set_preferences({
            "destination": str(self.root / "downloads"),
            "concurrency_mode": "manual",
            "manual_concurrency": 1,
        })
        batch = owner.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto", start_worker=False)
        item_id = self.database.batch_items(batch["batch_id"])[0]["id"]
        other_database = Database(self.database.path)
        try:
            controller = DownloadManager(other_database, autostart=False)
            queued_item = other_database.get_item(item_id)
            owner.start()
            self.assertTrue(started.wait(2))
            with patch.object(other_database, "get_item", return_value=queued_item):
                controller.cancel_item(item_id)
            self.assertEqual(other_database.get_worker_action(item_id), "cancel")
            self.assertEqual(other_database.get_item(item_id)["status"], "downloading")
            inspect_signal.set()
            self.assertTrue(self.wait_for(lambda: self.database.get_item(item_id)["status"] == "cancelled"))
        finally:
            inspect_signal.set()
            other_database.close()

    def test_shutdown_keeps_worker_lock_until_active_download_exits(self) -> None:
        started = Event()
        finish_download = Event()

        def downloader(**_kwargs):
            started.set()
            finish_download.wait(10)
            return {"paths": [], "duplicate": False}

        owner = DownloadManager(self.database, downloader=downloader, autostart=False)
        self.manager = owner
        owner.set_preferences({
            "destination": str(self.root / "downloads"),
            "concurrency_mode": "manual",
            "manual_concurrency": 1,
        })
        batch = owner.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto")
        item_id = self.database.batch_items(batch["batch_id"])[0]["id"]
        probe_lock = [
            sys.executable, "-c",
            "import sys; from clipoteca.worker_lock import WorkerLock; "
            "lock = WorkerLock(sys.argv[1]); print(lock.acquire()); lock.release()",
            str(self.database.path.with_suffix(".sqlite3.worker.lock")),
        ]
        try:
            self.assertTrue(started.wait(2))
            owner.shutdown(pause_active=False, timeout=0.05)
            result = subprocess.run(probe_lock, check=True, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.stdout.strip(), "False")
            self.assertEqual(self.database.get_item(item_id)["status"], "downloading")
        finally:
            finish_download.set()
            owner.shutdown(pause_active=False)
        result = subprocess.run(probe_lock, check=True, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.stdout.strip(), "True")
        self.assertEqual(self.database.get_item(item_id)["status"], "completed")

    def test_cancel_all_keeps_failed_items_available_for_retry(self) -> None:
        batch = {
            "id": "batch-failed", "source_url": "https://www.youtube.com/watch?v=batch", "title": "Batch",
            "is_playlist": False, "destination": str(self.root), "output_format": "video", "quality": "auto",
        }
        item = {"id": "item-failed", "source_id": "source-1", "source_url": "https://www.youtube.com/watch?v=item", "title": "Item"}
        self.database.create_batch(batch, [item])
        self.database.update_item("item-failed", status="failed", error="Fallo terminal")
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager

        manager.cancel_all(wait=False)

        self.assertEqual(self.database.get_item("item-failed")["status"], "failed")

    def test_cancelling_queued_duplicate_preserves_active_partial_from_another_manager(self) -> None:
        partial_ready = Event()
        finish_download = Event()
        destination = self.root / "downloads"
        partial = destination / "Example list" / "Item 1 [item-1].mp4.part"

        def downloader(**kwargs):
            self.assertEqual(kwargs["destination"], partial.parent)
            partial.parent.mkdir(parents=True, exist_ok=True)
            partial.write_bytes(b"incomplete media")
            partial_ready.set()
            if not finish_download.wait(10):
                raise RuntimeError("No se liberó la descarga simulada")
            output = partial.with_suffix("")
            partial.replace(output)
            return {"paths": [str(output)], "duplicate": False}

        owner = DownloadManager(self.database, downloader=downloader, autostart=False)
        self.manager = owner
        owner.set_preferences({
            "destination": str(destination),
            "concurrency_mode": "manual",
            "manual_concurrency": 2,
        })
        other_database = Database(self.database.path)
        try:
            controller = DownloadManager(other_database, autostart=False)
            original = owner.enqueue(self.make_analysis(), ["analysis-item-1"], "video", "auto")
            self.assertTrue(partial_ready.wait(3))
            duplicate = controller.enqueue(
                self.make_analysis(), ["analysis-item-1"], "video", "auto", start_worker=False,
            )
            duplicate_id = other_database.batch_items(duplicate["batch_id"])[0]["id"]
            controller.cancel_item(duplicate_id)
            original_id = self.database.batch_items(original["batch_id"])[0]["id"]

            self.assertEqual(other_database.get_item(duplicate_id)["status"], "cancelled")
            self.assertEqual(self.database.get_item(original_id)["status"], "downloading")
            self.assertEqual(partial.read_bytes(), b"incomplete media")
            finish_download.set()
            self.assertTrue(self.wait_for(lambda: self.database.get_item(original_id)["status"] == "completed"))
            self.assertEqual(partial.with_suffix("").read_bytes(), b"incomplete media")
        finally:
            finish_download.set()
            owner.shutdown(pause_active=False)
            other_database.close()

    def test_jobs_with_same_output_target_are_serialized(self) -> None:
        state_lock = Lock()
        release_first = Event()
        first_started = Event()
        distinct_started = Event()
        active_by_target: dict[str, int] = {}
        max_same_target_active = 0
        max_total_active = 0

        def fake_downloader(**kwargs):
            nonlocal max_same_target_active, max_total_active
            destination = Path(kwargs["destination"])
            source_id = kwargs["source_id"]
            target = destination / (
                f"{safe_filename(kwargs['title'])} [{safe_filename(source_id, 48)}].mp4"
            )
            target_key = str(target).casefold()
            if target.exists():
                return {"paths": [str(target)], "duplicate": True}

            with state_lock:
                active_by_target[target_key] = active_by_target.get(target_key, 0) + 1
                max_same_target_active = max(
                    max_same_target_active,
                    active_by_target[target_key],
                )
                max_total_active = max(max_total_active, sum(active_by_target.values()))
            if source_id == "item-1" and not first_started.is_set():
                first_started.set()
                release_first.wait(3)
            elif source_id == "item-2":
                distinct_started.set()

            destination.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"media")
            with state_lock:
                active_by_target[target_key] -= 1
            return {"paths": [str(target)], "duplicate": False}

        manager = DownloadManager(self.database, downloader=fake_downloader, autostart=False)
        self.manager = manager
        manager.set_preferences({
            "destination": str(self.root / "downloads"),
            "concurrency_mode": "manual",
            "manual_concurrency": 2,
        })
        duplicate_analysis = self.make_analysis()
        distinct_analysis = self.make_analysis()
        distinct_analysis["items"] = [{
            "id": "analysis-item-2",
            "source_id": "item-2",
            "source_url": "https://www.youtube.com/watch?v=item-2",
            "title": "Item 2",
            "duration": 12,
            "available": True,
        }]

        try:
            manager.enqueue(duplicate_analysis, ["analysis-item-1"], "video", "auto")
            self.assertTrue(first_started.wait(2))
            manager.enqueue(duplicate_analysis, ["analysis-item-1"], "video", "auto")
            manager.enqueue(distinct_analysis, ["analysis-item-2"], "video", "auto")
            self.assertTrue(distinct_started.wait(2))
            time.sleep(0.3)
            self.assertEqual(max_same_target_active, 1)
            self.assertEqual(max_total_active, 2)
        finally:
            release_first.set()

        self.assertTrue(
            self.wait_for(lambda: len(self.database.items_with_status(("completed",))) == 3)
        )

    def test_history_keeps_openable_output_paths(self) -> None:
        batch = {
            "id": "batch-history", "source_url": "https://www.youtube.com/watch?v=batch", "title": "Batch",
            "is_playlist": False, "destination": str(self.root), "output_format": "both", "quality": "auto",
        }
        item = {"id": "history-item", "source_id": "source-1", "source_url": "https://www.youtube.com/watch?v=item", "title": "Item"}
        self.database.create_batch(batch, [item])
        paths = [str(self.root / "item.mp4"), str(self.root / "item.mp3")]
        self.database.update_item("history-item", status="completed", output_path=json.dumps(paths))
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager
        self.assertEqual(manager.get_history_path("history-item", 1), Path(paths[1]))
        self.assertEqual(manager.get_state()["history"][0]["output_paths"], paths)

    def test_first_run_requires_a_concurrency_choice_without_an_app_default(self) -> None:
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager
        self.assertNotIn("concurrency_mode", manager.get_state()["preferences"])
        with self.assertRaisesRegex(ValueError, "modo de concurrencia"):
            manager.enqueue(
                self.make_analysis(),
                ["analysis-item-1"],
                "video",
                "auto",
            )

    def test_theme_mode_defaults_to_system_and_is_validated(self) -> None:
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager
        self.assertEqual(manager.get_state()["preferences"]["theme_mode"], "system")

        preferences = manager.set_preferences({"theme_mode": "dark"})
        self.assertEqual(preferences["theme_mode"], "dark")

        with self.assertRaisesRegex(ValueError, "Modo de tema"):
            manager.set_preferences({"theme_mode": "sepia"})

    def test_manual_concurrency_has_no_application_imposed_ceiling(self) -> None:
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager
        preferences = manager.set_preferences({
            "concurrency_mode": "manual",
            "manual_concurrency": 250,
        })
        self.assertEqual(preferences["manual_concurrency"], 250)

    def test_legacy_implicit_concurrency_is_cleared_for_first_run_prompt(self) -> None:
        self.database.set_preference("concurrency_mode", "auto")
        self.database.set_preference("manual_concurrency", 1)
        self.database.set_preference("auto_concurrency_cap", 5)
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager
        preferences = manager.get_state()["preferences"]
        self.assertIsNone(preferences["concurrency_mode"])
        self.assertIsNone(preferences["manual_concurrency"])
        self.assertIsNone(preferences["auto_concurrency_cap"])

    def test_first_run_concurrency_choice_is_remembered(self) -> None:
        manager = DownloadManager(self.database, autostart=False)
        self.manager = manager
        manager.set_preferences({"concurrency_mode": "manual", "manual_concurrency": 12})
        manager.shutdown(pause_active=False)

        reopened = DownloadManager(self.database, autostart=False)
        self.manager = reopened
        preferences = reopened.get_state()["preferences"]
        self.assertEqual(preferences["concurrency_mode"], "manual")
        self.assertEqual(preferences["manual_concurrency"], 12)


if __name__ == "__main__":
    unittest.main()

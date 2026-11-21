from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from clipoteca.cli import EXIT_OPERATION_FAILED, EXIT_USAGE, main


class CliContractTests(unittest.TestCase):
    def test_help_lists_the_automation_commands_without_loading_webview(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import clipoteca.cli; "
                "assert 'webview' not in sys.modules; "
                "raise SystemExit(clipoteca.cli.main(['--help']))",
            ],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("download", result.stdout)
        self.assertIn("history", result.stdout)
        self.assertNotIn("webview", result.stderr)

    def test_version_is_available_without_desktop_dependencies(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = main(["--version"])

        self.assertEqual(result, 0)
        self.assertIn("clipoteca-cli dev", stdout.getvalue())

    def test_json_usage_error_has_stable_envelope_and_exit_code(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main(["--json", "download"])

        self.assertEqual(result, EXIT_USAGE)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "USAGE_ERROR")

    def test_cli_rejects_unsupported_hosts_before_dispatch(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main(["--json", "analyze", "https://example.com/video"])

        self.assertEqual(result, EXIT_USAGE)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "USAGE_ERROR")
        self.assertIn("YouTube, Instagram y Reddit", payload["error"]["message"])

    def test_json_option_is_accepted_after_a_nested_command(self) -> None:
        queue_state = {"queue": [], "history": [], "counts": {"active": 0, "completed": 0}}
        database = Mock()
        manager = Mock()
        manager.get_state.return_value = queue_state
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["queue", "list", "--json"])

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["command"], "queue list")
        self.assertEqual(payload["data"], queue_state)

    def test_download_enqueues_single_video_without_starting_a_worker_by_default(self) -> None:
        url = "https://www.youtube.com/watch?v=sample"
        analysis = {
            "title": "Video propio",
            "source_url": url,
            "is_playlist": False,
            "items": [{
                "id": "item-1",
                "source_id": "source-1",
                "source_url": url,
                "title": "Video",
                "available": True,
            }],
        }
        database = Mock()
        database.get_preference.return_value = "C:/Users/Test/Downloads/Clipoteca"
        manager = Mock()
        manager.enqueue.return_value = {"batch_id": "batch-1", "queued": 1}
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            patch("clipoteca.engine.analyze_url", return_value=analysis),
            contextlib.redirect_stdout(stdout),
        ):
            result = main([
                "download", url, "--destination", "C:/Users/Test/Downloads/Clipoteca", "--json",
            ])

        self.assertEqual(result, 0)
        manager.set_preferences.assert_called_once_with({
            "destination": "C:/Users/Test/Downloads/Clipoteca",
        })
        manager.enqueue.assert_called_once_with(
            analysis,
            ["item-1"],
            "video",
            "auto",
            start_worker=False,
        )
        manager.shutdown.assert_called_once_with(pause_active=False)
        database.close.assert_called_once_with()
        self.assertEqual(json.loads(stdout.getvalue())["data"]["batch_id"], "batch-1")

    def test_download_selects_requested_playlist_item(self) -> None:
        url = "https://www.youtube.com/playlist?list=sample"
        analysis = {
            "title": "Playlist propia",
            "source_url": url,
            "is_playlist": True,
            "items": [
                {
                    "id": "item-1",
                    "source_id": "source-1",
                    "source_url": "https://www.youtube.com/watch?v=one",
                    "title": "Primero",
                    "available": True,
                    "index": 1,
                },
                {
                    "id": "item-2",
                    "source_id": "source-2",
                    "source_url": "https://www.youtube.com/watch?v=two",
                    "title": "Segundo",
                    "available": True,
                    "index": 2,
                },
            ],
        }
        database = Mock()
        database.get_preference.return_value = "C:/Users/Test/Downloads/Clipoteca"
        manager = Mock()
        manager.enqueue.return_value = {"batch_id": "batch-1", "queued": 1}
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            patch("clipoteca.engine.analyze_url", return_value=analysis),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main([
                "download", url, "--item", "item-2", "--format", "audio",
                "--quality", "480", "--json",
            ])

        self.assertEqual(result, 0)
        manager.enqueue.assert_called_once_with(
            analysis,
            ["item-2"],
            "audio",
            "480",
            start_worker=False,
        )

    def test_download_rejects_invalid_destination_before_enqueue(self) -> None:
        url = "https://www.youtube.com/watch?v=sample"
        analysis = {
            "title": "Video propio",
            "source_url": url,
            "is_playlist": False,
            "items": [{
                "id": "item-1",
                "source_id": "source-1",
                "source_url": url,
                "title": "Video",
                "available": True,
            }],
        }
        database = Mock()
        manager = Mock()
        manager.set_preferences.side_effect = ValueError("La carpeta de destino debe ser absoluta.")
        stderr = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            patch("clipoteca.engine.analyze_url", return_value=analysis),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["--json", "download", url, "--destination", "relative/path"])

        self.assertEqual(result, EXIT_USAGE)
        manager.enqueue.assert_not_called()
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "INVALID_DESTINATION")

    def test_playlist_download_requires_explicit_selection(self) -> None:
        url = "https://www.youtube.com/playlist?list=sample"
        analysis = {
            "title": "Playlist propia",
            "source_url": url,
            "is_playlist": True,
            "items": [{
                "id": "item-1",
                "source_id": "source-1",
                "source_url": "https://www.youtube.com/watch?v=sample",
                "title": "Video",
                "available": True,
            }],
        }
        database = Mock()
        manager = Mock()
        stderr = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            patch("clipoteca.engine.analyze_url", return_value=analysis),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["--json", "download", url])

        self.assertEqual(result, EXIT_USAGE)
        manager.enqueue.assert_not_called()
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "SELECTION_REQUIRED")
        manager.shutdown.assert_called_once_with(pause_active=False)
        database.close.assert_called_once_with()

    def test_download_wait_returns_json_summary_for_completed_batch(self) -> None:
        url = "https://www.youtube.com/playlist?list=sample"
        analysis = {
            "title": "Playlist propia",
            "source_url": url,
            "is_playlist": True,
            "items": [{
                "id": "item-1",
                "source_id": "source-1",
                "source_url": "https://www.youtube.com/watch?v=sample",
                "title": "Video",
                "available": True,
            }],
        }
        database = Mock()
        database.batch_items.return_value = [{
            "id": "task-1",
            "title": "Video",
            "status": "completed",
            "progress": 1.0,
            "total_bytes": 100,
            "output_path": '["C:/Downloads/video.mp4"]',
            "error": None,
        }]
        manager = Mock()
        manager.enqueue.return_value = {"batch_id": "batch-1", "queued": 1}
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            patch("clipoteca.engine.analyze_url", return_value=analysis),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["download", url, "--all", "--wait", "--json"])

        self.assertEqual(result, 0)
        manager.enqueue.assert_called_once_with(
            analysis,
            ["item-1"],
            "video",
            "auto",
            start_worker=True,
        )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["data"]["counts"], {"completed": 1})
        self.assertEqual(payload["data"]["items"][0]["output_paths"], ["C:/Downloads/video.mp4"])
        progress_event = json.loads(stderr.getvalue().splitlines()[0])
        self.assertEqual(progress_event["event"], "progress")

    def test_download_wait_returns_failure_summary_and_nonzero_exit(self) -> None:
        url = "https://www.youtube.com/watch?v=sample"
        analysis = {
            "title": "Video propio",
            "source_url": url,
            "is_playlist": False,
            "items": [{
                "id": "item-1",
                "source_id": "source-1",
                "source_url": url,
                "title": "Video",
                "available": True,
            }],
        }
        database = Mock()
        database.batch_items.return_value = [{
            "id": "task-1",
            "title": "Video",
            "status": "failed",
            "progress": 0.0,
            "total_bytes": None,
            "output_path": None,
            "error": "Falta FFmpeg.",
        }, {
            "id": "task-2",
            "title": "Otro video",
            "status": "cancelled",
            "progress": 0.0,
            "total_bytes": None,
            "output_path": None,
            "error": None,
        }]
        manager = Mock()
        manager.enqueue.return_value = {"batch_id": "batch-1", "queued": 1}
        stderr = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            patch("clipoteca.engine.analyze_url", return_value=analysis),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["--json", "download", url, "--wait"])

        self.assertEqual(result, EXIT_OPERATION_FAILED)
        error_payload = json.loads(stderr.getvalue().splitlines()[-1])
        self.assertEqual(error_payload["error"]["code"], "DOWNLOAD_FAILED")
        self.assertEqual(error_payload["data"]["counts"], {"cancelled": 1, "failed": 1})
        self.assertIsNone(error_payload["data"]["items"][0]["progress"])

    def test_ctrl_c_during_headless_download_pauses_the_batch(self) -> None:
        url = "https://www.youtube.com/watch?v=sample"
        analysis = {
            "title": "Video propio",
            "source_url": url,
            "is_playlist": False,
            "items": [{
                "id": "item-1",
                "source_id": "source-1",
                "source_url": url,
                "title": "Video",
                "available": True,
            }],
        }
        database = Mock()
        database.batch_items.side_effect = KeyboardInterrupt
        manager = Mock()
        manager.enqueue.return_value = {"batch_id": "batch-1", "queued": 1}
        stderr = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            patch("clipoteca.engine.analyze_url", return_value=analysis),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["--json", "download", url, "--wait"])

        self.assertEqual(result, 130)
        manager.pause_all.assert_called_once_with(wait=True)
        manager.shutdown.assert_called_once_with(pause_active=False)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "INTERRUPTED")

    def test_queue_list_and_pause_use_shared_local_state(self) -> None:
        database = Mock()
        manager = Mock()
        queue_state = {"queue": [], "history": [], "counts": {"active": 0, "completed": 0}}
        manager.get_state.return_value = queue_state
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["queue", "list", "--json"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["data"], queue_state)

        manager = Mock()
        manager.get_state.return_value = queue_state
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main(["queue", "pause", "--wait", "--json"])

        self.assertEqual(result, 0)
        manager.pause_all.assert_called_once_with(wait=True)

    def test_cancel_all_requires_yes(self) -> None:
        database = Mock()
        manager = Mock()
        stderr = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["--json", "queue", "cancel", "--all"])

        self.assertEqual(result, EXIT_USAGE)
        manager.cancel_all.assert_not_called()
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "USAGE_ERROR")

    def test_cancel_all_confirms_and_returns_cancelled_count(self) -> None:
        database = Mock()
        manager = Mock()
        database.items_with_status.return_value = [{"id": "item-1"}]
        database.get_item.return_value = {"status": "cancelled"}
        manager.get_state.return_value = {"queue": []}
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["queue", "cancel", "--all", "--yes", "--json"])

        self.assertEqual(result, 0)
        manager.cancel_all.assert_called_once_with(wait=False)
        self.assertEqual(json.loads(stdout.getvalue())["data"]["cancelled"], 1)

    def test_queue_retry_can_enqueue_without_waiting(self) -> None:
        database = Mock()
        manager = Mock()
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["queue", "retry", "item-1", "--json"])

        self.assertEqual(result, 0)
        manager.retry_item.assert_called_once_with("item-1", start_worker=False)
        self.assertEqual(json.loads(stdout.getvalue())["data"]["status"], "queued")

    def test_queue_cancel_item_sends_request(self) -> None:
        database = Mock()
        database.get_item.side_effect = [
            {"id": "item-1", "status": "downloading"},
            {"id": "item-1", "status": "downloading"},
        ]
        manager = Mock()
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["queue", "cancel", "item-1", "--json"])

        self.assertEqual(result, 0)
        manager.cancel_item.assert_called_once_with("item-1")
        self.assertTrue(json.loads(stdout.getvalue())["data"]["cancel_requested"])

    def test_queue_cancel_queued_item_reports_cancelled(self) -> None:
        database = Mock()
        database.get_item.side_effect = [
            {"id": "item-1", "status": "queued"},
            {"id": "item-1", "status": "cancelled"},
        ]
        manager = Mock()
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["queue", "cancel", "item-1", "--json"])

        self.assertEqual(result, 0)
        manager.cancel_item.assert_called_once_with("item-1")
        self.assertEqual(json.loads(stdout.getvalue())["data"]["status"], "cancelled")

    def test_queue_cancel_wait_reports_the_outcome_of_cancellation(self) -> None:
        for status, expected_exit in (("cancelled", 0), ("completed", EXIT_OPERATION_FAILED)):
            with self.subTest(status=status):
                database = Mock()
                item = {
                    "id": "item-1",
                    "batch_id": "batch-1",
                    "title": "Video",
                    "status": "downloading",
                }
                database.get_item.side_effect = [item, item, {**item, "status": status}]
                manager = Mock()
                stdout, stderr = io.StringIO(), io.StringIO()
                with (
                    patch("clipoteca.storage.Database", return_value=database),
                    patch("clipoteca.manager.DownloadManager", return_value=manager),
                    patch("clipoteca.cli.time.sleep") as sleep,
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    result = main(["queue", "cancel", "item-1", "--wait", "--json"])

                self.assertEqual(result, expected_exit)
                manager.cancel_item.assert_called_once_with("item-1")
                sleep.assert_called_once()
                if expected_exit == 0:
                    payload = json.loads(stdout.getvalue())
                    self.assertTrue(payload["ok"])
                else:
                    payload = json.loads(stderr.getvalue())
                    self.assertEqual(payload["error"]["code"], "CANCEL_NOT_AVAILABLE")
                self.assertEqual(payload["data"], {
                    "item_id": "item-1",
                    "status": status,
                    "cancel_requested": True,
                })

    def test_queue_cancel_wait_times_out_if_the_worker_does_not_respond(self) -> None:
        database = Mock()
        database.get_item.return_value = {"id": "item-1", "status": "downloading"}
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager"),
            patch("clipoteca.cli.time.monotonic", side_effect=[0, 100]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["queue", "cancel", "item-1", "--wait", "--json"])

        self.assertEqual(result, EXIT_OPERATION_FAILED)
        self.assertEqual(stdout.getvalue(), "")
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "CANCEL_NOT_AVAILABLE")
        self.assertEqual(payload["data"]["status"], "downloading")

    def test_queue_resume_wait_starts_worker_and_waits_for_queue_idle(self) -> None:
        database = Mock()
        database.get_preference.return_value = "manual"
        database.items_with_status.return_value = []
        manager = Mock()
        manager.get_state.return_value = {"queue": [], "history": [], "counts": {}}
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["queue", "resume", "--wait", "--json"])

        self.assertEqual(result, 0)
        manager.resume_all.assert_called_once_with(start_worker=True)
        self.assertEqual(json.loads(stdout.getvalue())["data"]["queue"], [])

    def test_queue_retry_wait_starts_worker_and_returns_batch_summary(self) -> None:
        database = Mock()
        database.get_preference.return_value = "manual"
        database.get_item.return_value = {
            "id": "item-1",
            "batch_id": "batch-1",
            "title": "Video",
            "status": "completed",
            "progress": 1.0,
            "total_bytes": 100,
            "error": None,
        }
        database.batch_items.return_value = [database.get_item.return_value]
        manager = Mock()
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = main(["queue", "retry", "item-1", "--wait", "--json"])

        self.assertEqual(result, 0)
        manager.retry_item.assert_called_once_with("item-1", start_worker=True)
        self.assertEqual(json.loads(stdout.getvalue())["data"]["batch_id"], "batch-1")

    def test_history_list_returns_completed_items(self) -> None:
        database = Mock()
        manager = Mock()
        history = [{"id": "item-1", "status": "completed"}]
        manager.get_state.return_value = {"history": history, "queue": []}
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["history", "list", "--json"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["data"]["history"], history)

    def test_history_clear_requires_yes_and_preserves_media(self) -> None:
        database = Mock()
        manager = Mock()
        manager.clear_history.return_value = 2
        stderr = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["--json", "history", "clear"])

        self.assertEqual(result, EXIT_USAGE)
        manager.clear_history.assert_not_called()
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "USAGE_ERROR")

        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["history", "clear", "--yes", "--json"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["data"], {"removed": 2, "media_deleted": False})

    def test_history_open_uses_saved_path_and_windows_association(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            media_path = Path(directory) / "finished.mp4"
            media_path.write_bytes(b"media")
            database = Mock()
            manager = Mock()
            manager.get_history_path.return_value = media_path
            stdout = io.StringIO()
            with (
                patch("clipoteca.storage.Database", return_value=database),
                patch("clipoteca.manager.DownloadManager", return_value=manager),
                patch("os.startfile", create=True) as start_file,
                contextlib.redirect_stdout(stdout),
            ):
                result = main(["history", "open", "item-1", "--json"])

        self.assertEqual(result, 0)
        start_file.assert_called_once_with(str(media_path))
        self.assertEqual(json.loads(stdout.getvalue())["data"], {"item_id": "item-1", "opened": True})

    def test_settings_show_returns_shared_preferences_without_internal_flags(self) -> None:
        database = Mock()
        database.get_preferences.return_value = {
            "destination": "C:/Downloads/Clipoteca",
            "theme_mode": "system",
            "concurrency_mode": "manual",
            "manual_concurrency": 10,
            "auto_concurrency_cap": None,
            "concurrency_setup_confirmed": True,
        }
        manager = Mock()
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["settings", "show", "--json"])

        self.assertEqual(result, 0)
        self.assertEqual(
            json.loads(stdout.getvalue())["data"]["preferences"],
            {
                "destination": "C:/Downloads/Clipoteca",
                "theme_mode": "system",
                "concurrency_mode": "manual",
                "manual_concurrency": 10,
                "auto_concurrency_cap": None,
            },
        )

    def test_settings_set_persists_explicit_concurrency_without_maximum(self) -> None:
        database = Mock()
        database.get_preference.return_value = None
        database.get_preferences.return_value = {
            "destination": "C:/Downloads/Clipoteca",
            "concurrency_mode": "manual",
            "manual_concurrency": 250,
            "auto_concurrency_cap": None,
        }
        manager = Mock()
        stdout = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stdout(stdout),
        ):
            result = main([
                "settings", "set", "--concurrency-mode", "manual",
                "--manual-concurrency", "250", "--json",
            ])

        self.assertEqual(result, 0)
        manager.set_preferences.assert_called_once_with({
            "concurrency_mode": "manual",
            "manual_concurrency": 250,
        })
        self.assertEqual(json.loads(stdout.getvalue())["data"]["preferences"]["manual_concurrency"], 250)

    def test_settings_set_requires_explicit_mode_on_first_run(self) -> None:
        database = Mock()
        database.get_preference.return_value = None
        manager = Mock()
        stderr = io.StringIO()
        with (
            patch("clipoteca.storage.Database", return_value=database),
            patch("clipoteca.manager.DownloadManager", return_value=manager),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["--json", "settings", "set", "--manual-concurrency", "5"])

        self.assertEqual(result, EXIT_USAGE)
        manager.set_preferences.assert_not_called()
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "INVALID_SETTINGS")

    def test_settings_cli_persists_between_invocations_in_local_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"LOCALAPPDATA": directory}
        ):
            set_stdout = io.StringIO()
            with contextlib.redirect_stdout(set_stdout):
                set_result = main([
                    "settings", "set", "--concurrency-mode", "manual",
                    "--manual-concurrency", "250", "--json",
                ])

            show_stdout = io.StringIO()
            with contextlib.redirect_stdout(show_stdout):
                show_result = main(["settings", "show", "--json"])

        self.assertEqual(set_result, 0)
        self.assertEqual(show_result, 0)
        saved = json.loads(show_stdout.getvalue())["data"]["preferences"]
        self.assertEqual(saved["theme_mode"], "system")
        self.assertEqual(saved["concurrency_mode"], "manual")
        self.assertEqual(saved["manual_concurrency"], 250)

    def test_settings_cli_persists_theme_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"LOCALAPPDATA": directory}
        ):
            result = main(["settings", "set", "--theme-mode", "light", "--json"])
            self.assertEqual(result, 0)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                shown = main(["settings", "show", "--json"])

        self.assertEqual(shown, 0)
        preferences = json.loads(output.getvalue())["data"]["preferences"]
        self.assertEqual(preferences["theme_mode"], "light")

    def test_settings_cli_rejects_relative_destination_without_persisting_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"LOCALAPPDATA": directory}
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main([
                    "--json", "settings", "set", "--destination", "relative/path",
                ])
            show_stdout = io.StringIO()
            with contextlib.redirect_stdout(show_stdout):
                show_result = main(["settings", "show", "--json"])

        self.assertEqual(result, EXIT_USAGE)
        self.assertEqual(show_result, 0)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "INVALID_SETTINGS")
        saved = json.loads(show_stdout.getvalue())["data"]["preferences"]
        self.assertNotEqual(saved["destination"], "relative/path")
        self.assertTrue(Path(saved["destination"]).is_absolute())

    def test_playlist_selection_flags_are_mutually_exclusive(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main([
                "--json", "download", "https://www.youtube.com/watch?v=sample",
                "--all", "--item", "video-1",
            ])

        self.assertEqual(result, EXIT_USAGE)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "USAGE_ERROR")

    def test_option_abbreviations_are_rejected_for_a_stable_contract(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main(["--ver", "status"])

        self.assertEqual(result, EXIT_USAGE)
        self.assertIn("unrecognized arguments", stderr.getvalue())

    def test_status_json_reports_engine_and_ffmpeg_availability(self) -> None:
        stdout = io.StringIO()
        with patch(
            "clipoteca.cli.shutil.which",
            side_effect=lambda name: "C:/tools/ffmpeg/bin/ffprobe.exe" if name == "ffprobe" else None,
        ), contextlib.redirect_stdout(stdout):
            result = main(["--json", "status"])

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "status")
        self.assertFalse(payload["data"]["ffmpeg_ready"])
        self.assertIsNone(payload["data"]["ffmpeg_path"])
        self.assertEqual(payload["data"]["ffprobe_path"], "C:/tools/ffmpeg/bin/ffprobe.exe")

    def test_status_json_reports_ffmpeg_ready_when_both_tools_are_on_path(self) -> None:
        paths = {
            "ffmpeg": "C:/tools/ffmpeg/bin/ffmpeg.exe",
            "ffprobe": "C:/tools/ffmpeg/bin/ffprobe.exe",
        }
        stdout = io.StringIO()
        with patch("clipoteca.cli.shutil.which", side_effect=paths.get), contextlib.redirect_stdout(stdout):
            result = main(["status", "--json"])

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["data"]["ffmpeg_ready"])
        self.assertEqual(payload["data"]["ffmpeg_path"], paths["ffmpeg"])

    def test_status_json_handles_missing_download_engine(self) -> None:
        stdout = io.StringIO()
        with patch("clipoteca.cli._get_ytdlp_version", return_value=None), patch(
            "clipoteca.cli.shutil.which", return_value=None
        ), contextlib.redirect_stdout(stdout):
            result = main(["--json", "status"])

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["data"]["download_engine_ready"])
        self.assertFalse(payload["data"]["ffmpeg_ready"])

    def test_empty_playlist_error_is_returned_without_a_download(self) -> None:
        from clipoteca.engine import UserFacingError

        url = "https://www.youtube.com/playlist?list=empty"
        stderr = io.StringIO()
        with patch(
            "clipoteca.engine.analyze_url",
            side_effect=UserFacingError("No se encontraron elementos descargables en este enlace."),
        ), contextlib.redirect_stderr(stderr):
            result = main(["--json", "analyze", url])

        self.assertEqual(result, EXIT_OPERATION_FAILED)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "ANALYSIS_FAILED")
        self.assertIn("No se encontraron elementos", payload["error"]["message"])

    def test_analyze_json_uses_existing_service_without_downloading(self) -> None:
        url = "https://www.youtube.com/watch?v=sample"
        analysis = {
            "title": "Colección propia",
            "source_url": url,
            "is_playlist": False,
            "items": [{"id": "item-1", "title": "Video", "available": True, "index": 1}],
        }
        stdout = io.StringIO()
        with patch("clipoteca.engine.analyze_url", return_value=analysis) as analyze, contextlib.redirect_stdout(stdout):
            result = main(["analyze", url, "--json"])

        self.assertEqual(result, 0)
        analyze.assert_called_once_with(url)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["data"], analysis)

    def test_preview_json_returns_non_playable_metadata_without_saving(self) -> None:
        url = "https://www.youtube.com/watch?v=sample"
        preview = {
            "title": "Video",
            "thumbnail": None,
            "duration": 12,
            "kind": "video",
            "url": None,
            "mime_type": "",
            "playable": False,
        }
        stdout = io.StringIO()
        with patch("clipoteca.engine.get_preview", return_value=preview) as get_preview, contextlib.redirect_stdout(stdout):
            result = main(["preview", url, "--format", "video", "--quality", "720", "--json"])

        self.assertEqual(result, 0)
        get_preview.assert_called_once_with(url, "video", "720")
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["data"]["playable"])
        self.assertIsNone(payload["data"]["url"])

    def test_analysis_failure_has_stable_json_error_and_exit_code(self) -> None:
        from clipoteca.engine import UserFacingError

        stderr = io.StringIO()
        with patch("clipoteca.engine.analyze_url", side_effect=UserFacingError("No se pudo analizar.")), contextlib.redirect_stderr(stderr):
            result = main(["--json", "analyze", "https://www.youtube.com/watch?v=sample"])

        self.assertEqual(result, EXIT_OPERATION_FAILED)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "ANALYSIS_FAILED")
        self.assertEqual(payload["command"], "analyze")


if __name__ == "__main__":
    unittest.main()

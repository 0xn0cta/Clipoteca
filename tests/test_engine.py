from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from clipoteca.engine import (
    DownloadInterrupted,
    UserFacingError,
    _format_options,
    _friendly_error,
    analyze_url,
    download_item,
    get_preview,
    safe_filename,
    validate_source_url,
)


class FakeYoutubeDL:
    def __init__(self, _options: dict) -> None:
        pass

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def extract_info(self, _url: str, *, download: bool) -> dict:
        assert download is False
        return {
            "title": "Sample playlist",
            "extractor_key": "Example",
            "entries": [
                {"id": "one", "title": "First", "webpage_url": "https://www.youtube.com/watch?v=one", "duration": 12},
                {"id": "two", "title": "Second", "webpage_url": "https://www.youtube.com/watch?v=two", "duration": 20},
            ],
        }


class EngineTests(unittest.TestCase):
    def test_only_supported_youtube_hosts_are_accepted(self) -> None:
        self.assertEqual(
            validate_source_url(" https://www.youtube.com/watch?v=video "),
            "https://www.youtube.com/watch?v=video",
        )
        self.assertEqual(validate_source_url("https://youtu.be/video"), "https://youtu.be/video")
        with self.assertRaises(UserFacingError):
            validate_source_url("https://example.org/video")
        with self.assertRaises(UserFacingError):
            validate_source_url("https://youtube.com.evil.example/video")
        with self.assertRaises(UserFacingError):
            validate_source_url("file:///C:/private/video.mp4")
        with self.assertRaises(UserFacingError):
            validate_source_url("https://user:password@youtube.com/video")

    def test_analysis_returns_reviewable_playlist_items(self) -> None:
        with patch("clipoteca.engine.YoutubeDL", FakeYoutubeDL):
            result = analyze_url("https://www.youtube.com/playlist?list=sample")
        self.assertTrue(result["is_playlist"])
        self.assertEqual(result["title"], "Sample playlist")
        self.assertEqual([item["title"] for item in result["items"]], ["First", "Second"])
        self.assertTrue(all(item["available"] for item in result["items"]))

    def test_audio_preview_resolves_a_stream_without_download(self) -> None:
        class FakePreviewYDL(FakeYoutubeDL):
            def extract_info(self, _url: str, *, download: bool) -> dict:
                assert download is False
                return {
                    "title": "Preview track",
                    "thumbnail": "https://example.org/cover.jpg",
                    "duration": 42,
                    "formats": [
                        {"url": "https://example.org/video.mp4", "ext": "mp4", "height": 360, "vcodec": "h264", "acodec": "aac"},
                        {"url": "https://example.org/audio.m4a", "ext": "m4a", "vcodec": "none", "acodec": "aac"},
                    ],
                }

        with patch("clipoteca.engine.YoutubeDL", FakePreviewYDL):
            result = get_preview("https://www.youtube.com/watch?v=preview", "audio")
        self.assertTrue(result["playable"])
        self.assertEqual(result["kind"], "audio")
        self.assertEqual(result["url"], "https://example.org/audio.m4a")

    def test_filenames_and_format_options_are_safe(self) -> None:
        self.assertEqual(safe_filename('a:b/c*'), "a_b_c_")
        self.assertEqual(safe_filename("CON"), "_CON")
        self.assertEqual(safe_filename("LPT1.txt"), "_LPT1.txt")
        both = _format_options("both", "720")
        self.assertIn("height<=720", both[0][2]["format"])
        self.assertIn("[ext=mp4]", both[0][2]["format"])
        self.assertNotIn("recodevideo", both[0][2])
        self.assertEqual(both[1][2]["postprocessors"][0]["preferredcodec"], "mp3")
        with self.assertRaises(UserFacingError):
            _format_options("video", "4320")

    def test_drm_error_has_a_clear_non_bypass_message(self) -> None:
        message = _friendly_error(RuntimeError("The requested site is known to use DRM protection"), action="analizar")
        self.assertIn("protegido con DRM", message)
        self.assertIn("opciones oficiales", message)

    def test_drm_diagnostic_from_yt_dlp_logger_reaches_the_ui_error(self) -> None:
        class FakeDrmYDL(FakeYoutubeDL):
            def __init__(self, options: dict) -> None:
                self.logger = options["logger"]

            def extract_info(self, _url: str, *, download: bool) -> dict:
                self.logger.error("The requested site is known to use DRM protection")
                raise ValueError("Unsupported URL")

        with patch("clipoteca.engine.YoutubeDL", FakeDrmYDL):
            with self.assertRaises(UserFacingError) as raised:
                analyze_url("https://www.youtube.com/watch?v=drm")
        self.assertIn("protegido con DRM", str(raised.exception))

    def test_existing_files_are_skipped_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Title [video-1].mp4"
            target.write_bytes(b"keep")
            result = download_item(
                source_url="https://www.youtube.com/watch?v=video",
                source_id="video-1",
                title="Title",
                destination=directory,
                output_format="video",
                quality="auto",
                progress=lambda _value: None,
                should_stop=lambda: None,
            )
            self.assertTrue(result["duplicate"])
            self.assertEqual(target.read_bytes(), b"keep")

    def test_pause_signal_interrupts_download_and_preserves_resume_semantics(self) -> None:
        class FakeDownloadYDL:
            def __init__(self, options: dict) -> None:
                self.options = options
                self._download_retcode = 0

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def download(self, _urls):
                self.options["progress_hooks"][0]({"status": "downloading", "downloaded_bytes": 1})

        with tempfile.TemporaryDirectory() as directory, patch("clipoteca.engine.YoutubeDL", FakeDownloadYDL):
            with self.assertRaises(DownloadInterrupted):
                download_item(
                    source_url="https://www.youtube.com/watch?v=video",
                    source_id="video-2",
                    title="Title",
                    destination=directory,
                    output_format="video",
                    quality="auto",
                    progress=lambda _value: None,
                    should_stop=lambda: "pause",
                )


if __name__ == "__main__":
    unittest.main()

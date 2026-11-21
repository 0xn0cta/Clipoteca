from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from yt_dlp import YoutubeDL

from clipoteca.engine import (
    DownloadInterrupted,
    UserFacingError,
    _format_options,
    _friendly_error,
    _is_transient_error,
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
    def test_only_supported_media_hosts_are_accepted(self) -> None:
        self.assertEqual(
            validate_source_url(" https://www.youtube.com/watch?v=video "),
            "https://www.youtube.com/watch?v=video",
        )
        self.assertEqual(validate_source_url("https://youtu.be/video"), "https://youtu.be/video")
        self.assertEqual(validate_source_url("https://www.instagram.com/reel/demo/"), "https://www.instagram.com/reel/demo/")
        self.assertEqual(validate_source_url("https://redd.it/demo"), "https://redd.it/demo")
        with self.assertRaises(UserFacingError):
            validate_source_url("https://example.org/video")
        with self.assertRaises(UserFacingError):
            validate_source_url("https://youtube.com.evil.example/video")
        with self.assertRaises(UserFacingError):
            validate_source_url("https://instagram.com.evil.example/reel/demo")
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

    def test_analysis_counts_playlist_entries_as_they_arrive(self) -> None:
        snapshots: list[tuple[str, int]] = []

        def entries():
            for index in range(1, 4):
                yield {
                    "_type": "url", "ie_key": "Youtube", "id": str(index),
                    "url": f"https://www.youtube.com/watch?v={index}", "title": f"Video {index}",
                }
                self.assertEqual(snapshots[-1], ("extracting", index))

        def extract_info(ydl, url, *, download):
            self.assertFalse(download)
            return ydl.process_ie_result({
                "_type": "playlist", "id": "sample", "title": "Example", "entries": entries(),
                "extractor": "youtube:tab", "extractor_key": "YoutubeTab", "webpage_url": url,
            }, download=download)

        with patch.object(YoutubeDL, "extract_info", autospec=True, side_effect=extract_info):
            result = analyze_url(
                "https://www.youtube.com/playlist?list=sample",
                on_progress=lambda phase, found: snapshots.append((phase, found)),
            )

        self.assertEqual([item["title"] for item in result["items"]], ["Video 1", "Video 2", "Video 3"])
        self.assertEqual(snapshots, [("extracting", count) for count in range(4)] + [("preparing", 3)])

    def test_social_posts_use_canonical_downloadable_links(self) -> None:
        class FakePost(FakeYoutubeDL):
            def __init__(self, options):
                self.options = options

            def extract_info(self, url, *, download):
                assert download is False
                assert "generic" not in self.options["allowed_extractors"]
                return {"id": "video", "title": "Public post", "url": "https://cdn.example.invalid/file.mp4"}

        for supplied, canonical in (
            ("https://m.instagram.com/reel/demo/?igsh=test", "https://www.instagram.com/reel/demo/"),
            ("https://redd.it/demo", "https://www.reddit.com/comments/demo/"),
            ("https://old.reddit.com/r/demo/comments/test/title/?share=1", "https://www.reddit.com/r/demo/comments/test/title/"),
        ):
            with self.subTest(source=supplied), patch("clipoteca.engine.YoutubeDL", FakePost):
                result = analyze_url(supplied)
                self.assertEqual(result["source_url"], canonical)
                self.assertEqual(result["items"][0]["source_url"], canonical)
                self.assertTrue(result["items"][0]["available"])

    def test_shared_links_cannot_resolve_to_an_external_site(self) -> None:
        with patch("clipoteca.engine.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.geturl.return_value = "https://www.reddit.com/r/demo/comments/test/"
            with self.assertRaisesRegex(UserFacingError, "redirige fuera de su plataforma"):
                analyze_url("https://www.instagram.com/share/reel/test")

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

    def test_mp4_prefers_h264_with_audio_and_retains_compatible_fallbacks(self) -> None:
        def stream(format_id, extension, video_codec, audio_codec, **metadata):
            return {
                "format_id": format_id, "ext": extension, "vcodec": video_codec,
                "acodec": audio_codec, "url": f"https://example.invalid/{format_id}",
                **metadata,
            }

        audio = stream("audio", "m4a", "none", "mp4a.40.2")
        audio_only_mp4 = stream("audio-mp4", "mp4", "none", "mp4a.40.2")
        muxed_h264 = stream("mp4-avc", "mp4", "avc1.42001e", "mp4a.40.2", height=360)
        h264 = stream("avc720", "mp4", "avc1.64001f", "none", height=720)
        av1 = stream("av11080", "mp4", "av01.0.08M.08", "none", height=1080)
        instagram_h264 = stream("instagram-h264", "mp4", "h264", "mp4a.40.2", height=720)
        instagram_vp9 = stream("instagram-vp9", "mp4", "vp9", "mp4a.40.2", height=1080)
        cases = [
            ("auto", [audio, h264, av1], ["avc720+audio"]),
            ("auto", [audio, muxed_h264, av1], ["mp4-avc"]),
            ("auto", [audio, av1], ["av11080+audio"]),
            ("480", [audio, muxed_h264, h264, av1], ["mp4-avc"]),
            ("auto", [instagram_h264, instagram_vp9], ["instagram-h264"]),
            ("auto", [audio_only_mp4], []),
        ]

        with YoutubeDL({"quiet": True, "simulate": True, "auto_init": False}) as ydl:
            for quality, formats, expected in cases:
                with self.subTest(quality=quality, expected=expected):
                    selector = ydl.build_format_selector(_format_options("video", quality)[0][2]["format"])
                    selected = selector({
                        "formats": formats,
                        "has_merged_format": any(item["vcodec"] != "none" and item["acodec"] != "none" for item in formats),
                        "incomplete_formats": formats == [audio_only_mp4],
                    })
                    self.assertEqual([item["format_id"] for item in selected], expected)

    def test_drm_error_has_a_clear_non_bypass_message(self) -> None:
        message = _friendly_error(RuntimeError("The requested site is known to use DRM protection"), action="analizar")
        self.assertIn("protegido con DRM", message)
        self.assertIn("opciones oficiales", message)

    def test_disk_full_error_explains_how_to_recover(self) -> None:
        message = _friendly_error(OSError(28, "No space left on device"), action="descargar")

        self.assertIn("No hay espacio suficiente", message)
        self.assertIn("cambia la carpeta", message)

    def test_only_recoverable_transfer_failures_are_retried(self) -> None:
        for detail in ("IncompleteRead(128 bytes read)", "HTTP Error 408", "[WinError 10054]"):
            with self.subTest(detail=detail):
                error = RuntimeError(detail)
                self.assertTrue(_is_transient_error(error))
                self.assertIn("conexión", _friendly_error(error, action="descargar"))
        self.assertFalse(_is_transient_error(RuntimeError("HTTP Error 403")))
        self.assertFalse(_is_transient_error(OSError(28, "No space left on device")))

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
        with tempfile.TemporaryDirectory() as directory, patch(
            "clipoteca.engine._probe_mp4", return_value=(True, True, True),
        ):
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

    def test_reports_separate_video_audio_and_merge_phases(self) -> None:
        updates = []
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Title [video-3].mp4"

            class FakeMuxedDownload(FakeYoutubeDL):
                def __init__(self, options):
                    self.on_progress = options["progress_hooks"][0]
                    self.on_postprocess = options["postprocessor_hooks"][0]

                def download(self, _urls):
                    for filename, stream, eta in (
                        ("video.mp4", {"vcodec": "avc1", "acodec": "none"}, 8),
                        ("audio.m4a", {"vcodec": "none", "acodec": "mp4a"}, 2),
                    ):
                        self.on_progress({
                            "status": "downloading", "downloaded_bytes": 50,
                            "total_bytes": 100, "eta": eta, "info_dict": stream,
                        })
                        self.on_progress({"status": "finished", "filename": filename})
                    self.on_postprocess({"status": "started", "postprocessor": "Merger"})
                    target.write_bytes(b"simulated merged output")
                    self.on_postprocess({"status": "finished", "postprocessor": "Merger"})

            with (
                patch("clipoteca.engine.YoutubeDL", FakeMuxedDownload),
                patch("clipoteca.engine._probe_mp4", return_value=(True, True, True)),
            ):
                result = download_item(
                    source_url="https://www.youtube.com/watch?v=video",
                    source_id="video-3",
                    title="Title",
                    destination=directory,
                    output_format="video",
                    quality="auto",
                    progress=updates.append,
                    should_stop=lambda: None,
                )

        self.assertEqual(result["paths"], [str(target)])
        self.assertEqual(
            [(update["phase"], update.get("eta")) for update in updates],
            [
                ("video", 8), ("between_tracks", None), ("audio", 2),
                ("between_tracks", None), ("merging", None), ("merging", None),
            ],
        )
        self.assertEqual(
            [[(step["id"], step["status"]) for step in update["steps"]] for update in updates],
            [
                [("video", "active"), ("audio", "pending"), ("merge", "pending")],
                [("video", "done"), ("audio", "pending"), ("merge", "pending")],
                [("video", "done"), ("audio", "active"), ("merge", "pending")],
                [("video", "done"), ("audio", "done"), ("merge", "pending")],
                [("video", "done"), ("audio", "done"), ("merge", "active")],
                [("video", "done"), ("audio", "done"), ("merge", "done")],
            ],
        )

    def test_does_not_report_an_intermediate_audio_track_as_completed_video(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio_track = Path(directory) / "Title [video-4].f140.m4a"

            class FakeIncompleteDownload(FakeYoutubeDL):
                def __init__(self, options):
                    self.options = options

                def download(self, _urls):
                    audio_track.write_bytes(b"intermediate audio")
                    self.options["progress_hooks"][0]({
                        "status": "finished", "filename": str(audio_track),
                    })
                    return 0

            with patch("clipoteca.engine.YoutubeDL", FakeIncompleteDownload):
                with self.assertRaisesRegex(UserFacingError, "No se generó el archivo final MP4"):
                    download_item(
                        source_url="https://www.youtube.com/watch?v=video",
                        source_id="video-4",
                        title="Title",
                        destination=directory,
                        output_format="video",
                        quality="auto",
                        progress=lambda _value: None,
                        should_stop=lambda: None,
                    )
            self.assertTrue(audio_track.is_file())

    def test_existing_vp9_mp4_creates_compatible_copy_without_downloading_again(self) -> None:
        updates = []
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "Video [reel].mp4"
            original.write_bytes(b"original vp9")
            expected = original.with_name("Video [reel] [H.264].mp4")

            def fake_ffmpeg(command, **_kwargs):
                self.assertIn("libx264", command)
                Path(command[-1]).write_bytes(b"converted h264")
                process = MagicMock()
                process.__enter__.return_value.wait.return_value = 0
                return process

            with (
                patch("clipoteca.engine._probe_mp4", side_effect=[(False, True, True), (True, True, True)]),
                patch("clipoteca.engine.shutil.which", return_value="ffmpeg"),
                patch("clipoteca.engine.subprocess.Popen", side_effect=fake_ffmpeg),
                patch("clipoteca.engine.YoutubeDL") as youtube_dl,
            ):
                result = download_item(
                    source_url="https://www.instagram.com/reels/reel/",
                    source_id="reel",
                    title="Video",
                    destination=directory,
                    output_format="video",
                    quality="auto",
                    progress=updates.append,
                    should_stop=lambda: None,
                )

            youtube_dl.assert_not_called()
            self.assertEqual(result["paths"], [str(expected)])
            self.assertFalse(result["duplicate"])
            self.assertEqual(original.read_bytes(), b"original vp9")
            self.assertEqual(expected.read_bytes(), b"converted h264")
            self.assertEqual(updates[0]["phase"], "converting_video")


if __name__ == "__main__":
    unittest.main()

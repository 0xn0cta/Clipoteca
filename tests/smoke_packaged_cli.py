"""Exercise the compiled CLI against a temporary store without network access."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


def main() -> None:
    executable = Path(__file__).resolve().parents[1] / "dist" / "windows" / "clipoteca-cli" / "clipoteca-cli.exe"
    with TemporaryDirectory(prefix="clipoteca-frozen-") as directory:
        data = Path(directory)
        environment = {**os.environ, "LOCALAPPDATA": directory}

        def run(*arguments: str) -> subprocess.CompletedProcess[bytes]:
            return subprocess.run(
                [str(executable), *arguments], cwd=data, env=environment,
                capture_output=True, timeout=20,
            )

        def read(*arguments: str) -> dict:
            result = run("--json", *arguments)
            assert result.returncode == 0, result
            assert not result.stderr, result.stderr
            payload = json.loads(result.stdout)
            assert payload["schema_version"] == 1 and payload["ok"] is True, payload
            return payload["data"]

        assert run("--help").returncode == 0
        status = read("status")
        assert status["mode"] == "cli" and status["download_engine_ready"], status
        assert status["yt_dlp_version"], status

        destination = str(data / "Vídeos")
        read("settings", "set", "--concurrency-mode", "manual", "--manual-concurrency", "2", "--destination", destination)
        settings = read("settings", "show")
        assert settings["preferences"]["manual_concurrency"] == 2, settings
        assert settings["preferences"]["destination"] == destination, settings
        assert read("queue", "list")["queue"] == []
        assert read("history", "list")["history"] == []

        rejected = run("--json", "analyze", "https://example.invalid/video")
        assert rejected.returncode == 2 and not rejected.stdout, rejected
        assert json.loads(rejected.stderr)["error"]["code"] == "USAGE_ERROR", rejected

        inaccessible = run("--json", "analyze", "https://www.instagram.com/example/reels/")
        assert inaccessible.returncode == 3 and not inaccessible.stdout, inaccessible
        assert json.loads(inaccessible.stderr)["error"]["code"] == "ANALYSIS_FAILED", inaccessible

    print(f"CLI compilada verificada. yt-dlp {status['yt_dlp_version']}. FFmpeg disponible: {status['ffmpeg_ready']}.")


if __name__ == "__main__":
    main()

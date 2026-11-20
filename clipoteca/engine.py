from __future__ import annotations

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from yt_dlp import YoutubeDL


logger = logging.getLogger("clipoteca.engine")
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


class UserFacingError(Exception):
    """An error safe to show directly in the Spanish UI."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        self.retryable = retryable
        super().__init__(message)


class DownloadInterrupted(Exception):
    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__(action)


class _YtDlpLogCapture:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def debug(self, message: str) -> None:
        return None

    def warning(self, message: str) -> None:
        logger.debug("yt-dlp: %s", _redact_log_detail(str(message)))

    def error(self, message: str) -> None:
        self.errors.append(str(message))


def validate_source_url(url: str) -> str:
    value = url.strip()
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError as exc:
        raise UserFacingError("El enlace no tiene un formato válido.") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        raise UserFacingError("Introduce un enlace web válido (http o https).")
    if parsed.username is not None or parsed.password is not None:
        raise UserFacingError("No incluyas credenciales en el enlace.")
    return value


def redact_url(url: str) -> str:
    """Remove path details and query values before writing a URL to logs."""
    try:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.hostname or "", "/…", "", ""))
    except ValueError:
        return "<enlace no disponible>"


def _redact_log_detail(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return redact_url(match.group(0).rstrip(".,);]"))

    return _URL_PATTERN.sub(replace, value)


def _info_options() -> dict[str, Any]:
    return {
        "quiet": True,
        "no_warnings": True,
        "ignoreconfig": True,
        "logger": _YtDlpLogCapture(),
        "noplaylist": False,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "cachedir": False,
    }


def analyze_url(url: str) -> dict[str, Any]:
    source = validate_source_url(url)
    options = _info_options()
    ytdlp_log = options["logger"]
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(source, download=False)
    except Exception as exc:
        diagnostic = RuntimeError(" ".join([str(exc), *ytdlp_log.errors]))
        logger.warning(
            "No se pudo analizar %s (%s): %s",
            redact_url(source),
            type(exc).__name__,
            _redact_log_detail(str(diagnostic)),
        )
        raise UserFacingError(_friendly_error(diagnostic, action="analizar")) from exc

    if not isinstance(info, dict):
        raise UserFacingError("El sitio no devolvió información reconocible para este enlace.")

    entries = info.get("entries")
    is_playlist = entries is not None
    source_entries = list(entries) if is_playlist else [info]
    items: list[dict[str, Any]] = []
    for index, entry in enumerate(source_entries, start=1):
        if not isinstance(entry, dict):
            continue
        item_url = (
            entry.get("webpage_url")
            or entry.get("original_url")
            or entry.get("url")
        )
        extractor = str(entry.get("ie_key") or entry.get("extractor_key") or "").lower()
        try:
            item_has_scheme = bool(item_url and urlsplit(str(item_url)).scheme)
        except ValueError:
            item_has_scheme = False
            item_url = None
        if item_url and not item_has_scheme and extractor in {"youtube", "youtubeplaylist"}:
            item_url = f"https://www.youtube.com/watch?v={item_url}"
        if not item_url and entry.get("id") and extractor in {"youtube", "youtubeplaylist"}:
            item_url = f"https://www.youtube.com/watch?v={entry['id']}"
        if item_url:
            try:
                item_url = validate_source_url(str(item_url))
            except UserFacingError:
                item_url = None

        source_id = str(entry.get("id") or index)
        stable_id = hashlib.sha256(f"{index}:{source_id}:{item_url or ''}".encode()).hexdigest()[:20]
        availability = str(entry.get("availability") or "").lower()
        thumbnail = _get_thumbnail(entry)
        items.append(
            {
                "id": stable_id,
                "source_id": source_id,
                "source_url": item_url,
                "title": str(entry.get("title") or f"Elemento {index}"),
                "duration": entry.get("duration"),
                "thumbnail": thumbnail,
                "available": bool(item_url) and availability not in {"private", "subscriber_only", "needs_auth"},
                "availability": availability or None,
                "index": index,
            }
        )

    if not items:
        raise UserFacingError("No se encontraron elementos descargables en este enlace.")

    return {
        "title": str(info.get("title") or "Colección sin título"),
        "source_url": source,
        "webpage_url": info.get("webpage_url") or source,
        "extractor": info.get("extractor_key") or info.get("extractor") or "",
        "is_playlist": is_playlist,
        "items": items,
    }


def get_preview(url: str, output_format: str = "video", quality: str = "auto") -> dict[str, Any]:
    """Resolve a stream URL for an in-app preview without saving the media."""
    source = validate_source_url(url)
    if output_format not in {"video", "audio", "both"}:
        raise UserFacingError("Formato de vista previa no válido.")
    options = _info_options()
    options.pop("extract_flat", None)
    options["noplaylist"] = True
    ytdlp_log = options["logger"]
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(source, download=False)
    except Exception as exc:
        diagnostic = RuntimeError(" ".join([str(exc), *ytdlp_log.errors]))
        logger.warning(
            "No se pudo preparar la vista previa de %s (%s): %s",
            redact_url(source),
            type(exc).__name__,
            _redact_log_detail(str(diagnostic)),
        )
        raise UserFacingError(_friendly_error(diagnostic, action="previsualizar")) from exc

    if not isinstance(info, dict):
        raise UserFacingError("El sitio no devolvió datos para la vista previa.")
    formats = [item for item in info.get("formats", []) if item.get("url")]
    audio_only = output_format == "audio"
    if audio_only:
        candidates = [
            item for item in formats
            if item.get("acodec") not in (None, "none") and item.get("vcodec") in (None, "none")
        ]
        if not candidates:
            candidates = [item for item in formats if item.get("acodec") not in (None, "none")]
    else:
        candidates = [item for item in formats if item.get("vcodec") not in (None, "none")]

    height = int(quality) if str(quality).isdigit() else None
    if height and not audio_only:
        within_quality = [item for item in candidates if item.get("height") and item["height"] <= height]
        if within_quality:
            candidates = within_quality
    candidates.sort(
        key=lambda item: (
            item.get("acodec") not in (None, "none") if not audio_only else True,
            item.get("height") or 0,
            item.get("tbr") or 0,
            item.get("ext") == ("m4a" if audio_only else "mp4"),
        ),
        reverse=True,
    )
    selected = candidates[0] if candidates else info
    preview_url = selected.get("url")
    kind = "audio" if audio_only else "video"
    ext = str(selected.get("ext") or "").lower()
    mime_type = (
        "audio/mpeg" if kind == "audio" and ext == "mp3" else
        "audio/mp4" if kind == "audio" and ext in {"m4a", "mp4"} else
        f"audio/{ext}" if kind == "audio" and ext else
        f"video/{ext}" if ext and ext not in {"m3u8", "mpd"} else
        "application/vnd.apple.mpegurl" if ext == "m3u8" else
        ""
    )
    return {
        "title": str(info.get("title") or "Vista previa"),
        "thumbnail": _get_thumbnail(info),
        "duration": info.get("duration"),
        "kind": kind,
        "url": preview_url,
        "mime_type": mime_type,
        "playable": bool(preview_url),
    }


def _get_thumbnail(info: dict[str, Any]) -> str | None:
    thumbnail = info.get("thumbnail")
    if thumbnail:
        return str(thumbnail)
    thumbnails = info.get("thumbnails") or []
    candidates = [item for item in thumbnails if isinstance(item, dict) and item.get("url")]
    if not candidates:
        return None
    best = max(candidates, key=lambda item: (item.get("width") or 0) * (item.get("height") or 0))
    return str(best["url"])


def safe_filename(value: str, limit: int = 120) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:limit].rstrip(" .") or "elemento")


def _format_options(output_format: str, quality: str) -> list[tuple[str, str, dict[str, Any]]]:
    height = f"[height<={int(quality)}]" if quality.isdigit() else ""
    if output_format == "audio":
        return [("audio", " (audio)", {
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        })]
    video_selector = f"bestvideo{height}+bestaudio/best{height}" if height else "bestvideo+bestaudio/best"
    video = ("video", "", {
        "format": video_selector,
        "merge_output_format": "mp4",
        "recodevideo": "mp4",
    })
    if output_format == "both":
        return [video, ("audio", " (audio)", {
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        })]
    return [video]


def download_item(
    *,
    source_url: str,
    source_id: str,
    title: str,
    destination: str | Path,
    output_format: str,
    quality: str,
    progress: Callable[[dict[str, Any]], None],
    should_stop: Callable[[], str | None],
) -> dict[str, Any]:
    source = validate_source_url(source_url)
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    base_name = f"{safe_filename(title)} [{safe_filename(source_id, 48)}]"
    stages = _format_options(output_format, str(quality))
    outputs: list[str] = []
    skipped: list[str] = []

    for stage_index, (stage, suffix, stage_options) in enumerate(stages):
        expected_ext = "mp3" if stage == "audio" else "mp4"
        expected = destination_path / f"{base_name}{suffix}.{expected_ext}"
        if expected.exists():
            skipped.append(str(expected))
            continue

        stage_paths: list[str] = []
        last_progress_time = 0.0

        def on_progress(status: dict[str, Any], *, current_stage: int = stage_index) -> None:
            nonlocal last_progress_time
            action = should_stop()
            if action:
                # yt-dlp leaves its .part file in place when a progress hook raises.
                raise DownloadInterrupted(action)
            if status.get("status") == "finished" and status.get("filename"):
                stage_paths.append(str(status["filename"]))
                return
            if status.get("status") != "downloading":
                return
            downloaded = int(status.get("downloaded_bytes") or 0)
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            fraction = (downloaded / total) if total else 0
            now = time.monotonic()
            if now - last_progress_time < 0.4 and fraction < 1:
                return
            last_progress_time = now
            progress(
                {
                    "progress": (current_stage + fraction) / len(stages),
                    "downloaded_bytes": downloaded,
                    "total_bytes": int(total) if total else None,
                    "speed": status.get("speed"),
                    "eta": status.get("eta"),
                    "stage": stage,
                }
            )

        ytdlp_log = _YtDlpLogCapture()
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "ignoreconfig": True,
            "noplaylist": True,
            "cachedir": False,
            "continuedl": True,
            "nopart": False,
            "overwrites": False,
            "nooverwrites": True,
            "windowsfilenames": True,
            "outtmpl": str(destination_path / f"{base_name}{suffix}.%(ext)s"),
            "progress_hooks": [on_progress],
            "retries": 0,
            "fragment_retries": 0,
            "socket_timeout": 30,
            "logger": ytdlp_log,
            **stage_options,
        }
        try:
            with YoutubeDL(options) as ydl:
                ydl.download([source])
                if getattr(ydl, "_download_retcode", 0):
                    detail = ytdlp_log.errors[-1] if ytdlp_log.errors else "yt-dlp devolvió un código de error"
                    raise RuntimeError(detail)
        except DownloadInterrupted:
            raise
        except Exception as exc:
            logger.warning(
                "Fallo al descargar %s (%s): %s",
                redact_url(source),
                type(exc).__name__,
                _redact_log_detail(str(exc)),
            )
            raise UserFacingError(
                _friendly_error(exc, action="descargar"),
                retryable=_is_transient_error(exc),
            ) from exc
        outputs.append(str(expected if expected.exists() else (stage_paths[-1] if stage_paths else expected)))

    if not outputs and skipped:
        return {"paths": skipped, "duplicate": True}
    return {"paths": outputs + skipped, "duplicate": bool(skipped)}


def _friendly_error(error: Exception, *, action: str) -> str:
    message = str(error).lower()
    if "drm" in message or "protected by drm" in message:
        return "Este contenido está protegido con DRM. Clipoteca no puede previsualizarlo ni descargarlo; usa las opciones oficiales de la plataforma."
    if "ffmpeg" in message:
        return "Falta FFmpeg para convertir o unir este formato. Instálalo y vuelve a intentarlo."
    if any(text in message for text in ("private video", "private", "login", "sign in", "authentication", "members-only")):
        return "Este contenido requiere iniciar sesión o no está disponible públicamente."
    if any(text in message for text in ("unsupported url", "no suitable extractor", "not a valid url")):
        return "Este sitio o enlace no es compatible con yt-dlp."
    if any(text in message for text in ("timed out", "timeout", "connection", "network", "temporary failure")):
        return "No se pudo conectar con el sitio. Comprueba tu conexión e inténtalo de nuevo."
    return f"No se pudo {action} el contenido. Revisa el enlace y vuelve a intentarlo."


def _is_transient_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "timed out", "timeout", "connection reset", "connection refused",
            "temporary failure", "temporarily unavailable", "http error 429",
            "http error 500", "http error 502", "http error 503", "http error 504",
            "remote end closed", "network is unreachable",
        )
    )

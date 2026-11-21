from __future__ import annotations

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, build_opener

from yt_dlp import YoutubeDL


logger = logging.getLogger("clipoteca.engine")
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_YOUTUBE_HOSTS = {"youtube.com", "youtu.be", "youtube-nocookie.com"}
_REDDIT_HOSTS = {"reddit.com", "www.reddit.com", "old.reddit.com", "m.reddit.com", "redd.it", "v.redd.it"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}
_EXTRACTORS = ["youtube.*", "instagram", "reddit"]
_INSTAGRAM_POST = re.compile(r"/(?:(?!share/)[\w.]+/)?(?:p|reels?|tv)/[\w-]+/?$")
_REDDIT_POST = re.compile(r"/(?:(?:r|user)/[\w-]+/)?comments/[a-zA-Z0-9]+(?:/[^/]*)*/?$")
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


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


def _source_platform(host: str) -> str | None:
    if host in _YOUTUBE_HOSTS or host.endswith((".youtube.com", ".youtube-nocookie.com")):
        return "youtube"
    if host in _INSTAGRAM_HOSTS:
        return "instagram"
    if host in _REDDIT_HOSTS:
        return "reddit"
    return None


def validate_source_url(url: str) -> str:
    value = url.strip()
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise UserFacingError("El enlace no tiene un formato válido.") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        raise UserFacingError("Introduce un enlace web válido (http o https).")
    if parsed.username is not None or parsed.password is not None:
        raise UserFacingError("No incluyas credenciales en el enlace.")
    normalized_host = hostname.lower().rstrip(".")
    if not _source_platform(normalized_host):
        raise UserFacingError("Clipoteca admite enlaces de YouTube, Instagram y Reddit.")
    if port not in {None, 80, 443}:
        raise UserFacingError("El enlace usa un puerto no compatible.")
    return value


class _PlatformRedirectHandler(HTTPRedirectHandler):
    def __init__(self, platform: str) -> None:
        self.platform = platform

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = validate_source_url(newurl)
        if _source_platform((urlsplit(target).hostname or "").rstrip(".")) != self.platform:
            raise UserFacingError("El enlace compartido redirige fuera de su plataforma.")
        return super().redirect_request(req, fp, code, msg, headers, target)


def _resolve_source_url(url: str) -> str:
    source = validate_source_url(url)
    parsed = urlsplit(source)
    host = (parsed.hostname or "").rstrip(".")
    platform = _source_platform(host)
    if platform == "youtube":
        return source
    if host == "redd.it" and re.fullmatch(r"/[a-zA-Z0-9]+/?", parsed.path):
        return f"https://www.reddit.com/comments/{parsed.path.strip('/')}/"
    share_link = (
        parsed.path.startswith("/share/") if platform == "instagram"
        else host == "v.redd.it" or bool(re.fullmatch(r"/r/[\w-]+/s/[\w-]+/?", parsed.path))
    )
    if share_link:
        try:
            with build_opener(_PlatformRedirectHandler(platform)).open(source, timeout=8) as response:
                parsed = urlsplit(validate_source_url(response.geturl()))
        except (URLError, TimeoutError) as exc:
            raise UserFacingError("No se pudo abrir el enlace compartido. Pega el enlace directo a la publicación.") from exc
        if _source_platform((parsed.hostname or "").rstrip(".")) != platform:
            raise UserFacingError("El enlace compartido redirige fuera de su plataforma.")
    if platform == "instagram" and _INSTAGRAM_POST.fullmatch(parsed.path):
        return urlunsplit(("https", "www.instagram.com", parsed.path, "", ""))
    if platform == "reddit" and _REDDIT_POST.fullmatch(parsed.path):
        return urlunsplit(("https", "www.reddit.com", parsed.path, "", ""))
    raise UserFacingError("Pega un enlace directo a un Reel o a una publicación con vídeo.")


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
        "allowed_extractors": _EXTRACTORS,
        "logger": _YtDlpLogCapture(),
        "noplaylist": False,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "cachedir": False,
    }


def analyze_url(url: str) -> dict[str, Any]:
    source = _resolve_source_url(url)
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
    if entries is not None and _source_platform(urlsplit(source).hostname or "") != "youtube":
        raise UserFacingError("Esta publicación contiene varias piezas. Usa un enlace directo a un solo vídeo.")
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
        if not item_url and not is_playlist:
            item_url = source

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
    source = _resolve_source_url(url)
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
    cleaned = cleaned[:limit].rstrip(" .") or "elemento"
    if cleaned.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"[:limit]
    return cleaned.rstrip(" .") or "elemento"


def _format_options(output_format: str, quality: str, *, allow_silent: bool = False) -> list[tuple[str, str, dict[str, Any]]]:
    if output_format not in {"video", "audio", "both"}:
        raise UserFacingError("Formato de salida no válido.")
    if quality not in {"auto", "1080", "720", "480"}:
        raise UserFacingError("La calidad seleccionada no está disponible.")
    height = f"[height<={quality}]" if quality != "auto" else ""
    if output_format == "audio":
        return [("audio", " (audio)", {
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        })]
    # MP4 is a container. Prefer YouTube's H.264 streams for Windows playback.
    h264 = "[vcodec^=avc1]"
    mp4_with_audio = f"best[ext=mp4][vcodec!=?none][acodec!=?none]{height}"
    audio_track = "(bestaudio[ext=m4a]/bestaudio[ext=mp4])" if allow_silent else "bestaudio[ext=m4a]"
    video_selector = "/".join((
        f"bestvideo[ext=mp4]{h264}{height}+{audio_track}",
        f"{mp4_with_audio}{h264}",
        f"bestvideo[ext=mp4]{height}+{audio_track}",
        mp4_with_audio,
    ))
    video = ("video", "", {
        "format": f"{video_selector}/bestvideo[ext=mp4]{height}" if allow_silent else video_selector,
        "merge_output_format": "mp4",
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
    source = _resolve_source_url(source_url)
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    base_name = f"{safe_filename(title)} [{safe_filename(source_id, 48)}]"
    stages = _format_options(output_format, str(quality), allow_silent=_source_platform(urlsplit(source).hostname or "") != "youtube")
    outputs: list[str] = []
    skipped: list[str] = []
    steps: list[str] = []
    completed_steps: set[str] = set()

    def report_step(update: dict[str, Any], step: str | None, *, finished: bool = False) -> None:
        if step and step not in steps:
            if step in {"video", "audio", "merge"}:
                steps.extend(("video", "audio", "merge"))
            elif step in {"mp3_audio", "convert"}:
                steps.extend(("mp3_audio", "convert"))
            elif step == "silent_video":
                steps.extend(("silent_video", "save"))
            else:
                steps.extend(("file", "save"))
        if step and finished:
            completed_steps.add(step)
        progress({
            **update,
            "steps": [
                {
                    "id": entry,
                    "status": "done" if entry in completed_steps else "active" if entry == step else "pending",
                }
                for entry in steps
            ],
        })

    for stage_index, (stage, suffix, stage_options) in enumerate(stages):
        expected_ext = "mp3" if stage == "audio" else "mp4"
        expected = destination_path / f"{base_name}{suffix}.{expected_ext}"
        if expected.is_file():
            skipped.append(str(expected))
            continue

        last_progress_time = 0.0
        last_phase: str | None = None
        last_track: str | None = None

        def on_progress(status: dict[str, Any], *, current_stage: int = stage_index) -> None:
            nonlocal last_progress_time, last_phase, last_track
            action = should_stop()
            if action:
                # yt-dlp leaves its .part file in place when a progress hook raises.
                raise DownloadInterrupted(action)
            state = status.get("status")
            if state not in {"downloading", "finished"}:
                return
            stream = status.get("info_dict") or {}
            if stage == "audio":
                track = "mp3_audio"
            elif stream.get("vcodec") == "none":
                track = "audio"
            elif stream.get("acodec") == "none":
                track = "silent_video" if status.get("filename") == str(expected) else "video"
            else:
                track = (last_track or "file") if not stream else "file"
            if state == "finished":
                last_phase = None
                last_track = None
                report_step(
                    {"progress": current_stage / len(stages), "phase": "between_tracks"},
                    track,
                    finished=True,
                )
                return
            downloaded = int(status.get("downloaded_bytes") or 0)
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            fraction = (downloaded / total) if total else 0
            phase = {"video": "video", "silent_video": "video", "audio": "audio", "mp3_audio": "audio"}.get(track, "transfer")
            now = time.monotonic()
            if phase == last_phase and now - last_progress_time < 0.4 and fraction < 1:
                return
            last_progress_time = now
            last_phase = phase
            last_track = track
            report_step(
                {
                    "progress": (current_stage + fraction) / len(stages),
                    "downloaded_bytes": downloaded,
                    "total_bytes": int(total) if total else None,
                    "speed": status.get("speed"),
                    "eta": status.get("eta"),
                    "stage": stage,
                    "phase": phase,
                },
                track,
            )

        def on_postprocess(status: dict[str, Any], *, current_stage: int = stage_index) -> None:
            state = status.get("status")
            if state not in {"started", "finished"}:
                return
            action = should_stop()
            if action:
                raise DownloadInterrupted(action)
            step, phase = {
                "Merger": ("merge", "merging"),
                "ExtractAudio": ("convert", "converting"),
            }.get(
                status.get("postprocessor"),
                ("save" if "save" in steps and stage == "video" else None, "finalizing"),
            )
            report_step(
                {"progress": (current_stage + 1) / len(stages), "phase": phase},
                step,
                finished=state == "finished",
            )

        ytdlp_log = _YtDlpLogCapture()
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "ignoreconfig": True,
            "allowed_extractors": _EXTRACTORS,
            "noplaylist": True,
            "cachedir": False,
            "continuedl": True,
            "nopart": False,
            "overwrites": False,
            "nooverwrites": True,
            "windowsfilenames": True,
            "outtmpl": str(destination_path / f"{base_name}{suffix}").replace("%", "%%") + ".%(ext)s",
            "progress_hooks": [on_progress],
            "postprocessor_hooks": [on_postprocess],
            "retries": 0,
            "fragment_retries": 0,
            "skip_unavailable_fragments": False,
            "socket_timeout": 30,
            "logger": ytdlp_log,
            **stage_options,
        }
        try:
            with YoutubeDL(options) as ydl:
                if ydl.download([source]):
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
        if not expected.is_file():
            raise UserFacingError(
                f"No se generó el archivo final {expected.suffix.upper().lstrip('.')}. "
                "Comprueba FFmpeg y vuelve a intentarlo desde la cola."
            )
        outputs.append(str(expected))

    if not outputs and skipped:
        return {"paths": skipped, "duplicate": True}
    return {"paths": outputs + skipped, "duplicate": bool(skipped)}


def _friendly_error(error: Exception, *, action: str) -> str:
    message = str(error).lower()
    if "drm" in message or "protected by drm" in message:
        return "Este contenido está protegido con DRM. Clipoteca no puede previsualizarlo ni descargarlo; usa las opciones oficiales de la plataforma."
    if any(text in message for text in ("no space left on device", "disk full", "errno 28", "not enough space")):
        return "No hay espacio suficiente en el disco de destino. Libera espacio o cambia la carpeta y vuelve a intentarlo."
    if "ffmpeg" in message:
        return "Falta FFmpeg para convertir o unir este formato. Instálalo y vuelve a intentarlo."
    if any(text in message for text in ("private video", "private", "login", "sign in", "authentication", "members-only")):
        return "Este contenido requiere iniciar sesión o no está disponible públicamente."
    if any(text in message for text in ("no media found", "no video formats found", "requested format is not available")):
        return "La publicación no ofrece vídeo o audio descargable en el formato elegido."
    if any(text in message for text in ("unsupported url", "no suitable extractor", "not a valid url")):
        return "Este sitio o enlace no es compatible con yt-dlp."
    if _is_transient_error(error) or any(text in message for text in ("connection", "network")):
        return "No se pudo conectar con el sitio. Comprueba tu conexión e inténtalo de nuevo."
    return f"No se pudo {action} el contenido. Revisa el enlace y vuelve a intentarlo."


def _is_transient_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "timed out", "timeout", "connection reset", "connection refused",
            "connection aborted", "broken pipe", "incompleteread", "incomplete read",
            "did not get any data blocks", "winerror 10054", "winerror 10060",
            "temporary failure", "temporarily unavailable", "http error 408", "http error 429",
            "http error 500", "http error 502", "http error 503", "http error 504",
            "remote end closed", "network is unreachable",
        )
    )

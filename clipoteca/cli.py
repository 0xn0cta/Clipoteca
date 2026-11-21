from __future__ import annotations

import argparse
from collections import Counter
import importlib
import json
import os
import shutil
import sys
import time
from typing import Any, Sequence


CLI_VERSION = "dev"
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_OPERATION_FAILED = 3
EXIT_UNAVAILABLE = 4
EXIT_INTERRUPTED = 130
JSON_SCHEMA_VERSION = 1


class _CliUsageError(Exception):
    pass


class _CliCommandError(Exception):
    def __init__(self, code: str, message: str, data: dict[str, Any] | None = None) -> None:
        self.code = code
        self.data = data
        super().__init__(message)


class _CliArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        raise _CliUsageError(message)


def _youtube_url(value: str) -> str:
    from .engine import UserFacingError, validate_source_url

    try:
        return validate_source_url(value)
    except UserFacingError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _add_json_option(parser: argparse.ArgumentParser, *, root: bool = False) -> None:
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False if root else argparse.SUPPRESS,
        help="Emite resultados como JSON estable.",
    )


def _add_format_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("video", "audio", "both"),
        default="video",
        help="Formato de salida.",
    )
    parser.add_argument(
        "--quality",
        choices=("auto", "1080", "720", "480"),
        default="auto",
        help="Calidad solicitada.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI contract without importing desktop or media services."""
    parser = _CliArgumentParser(
        prog="clipoteca-cli",
        description="Automatiza Clipoteca localmente desde la consola.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _add_json_option(parser, root=True)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {CLI_VERSION}",
        help="Muestra la versión de la CLI.",
    )
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_CliArgumentParser)

    status = commands.add_parser("status", help="Consulta el estado local de Clipoteca.")
    _add_json_option(status)

    analyze = commands.add_parser("analyze", help="Analiza un enlace de YouTube sin descargar.")
    _add_json_option(analyze)
    analyze.add_argument("url", type=_youtube_url, help="URL de un video o playlist de YouTube.")

    preview = commands.add_parser("preview", help="Obtiene una vista previa sin guardar un archivo.")
    _add_json_option(preview)
    preview.add_argument("url", type=_youtube_url, help="URL de un video de YouTube.")
    _add_format_options(preview)

    download = commands.add_parser("download", help="Encola y ejecuta una descarga autorizada.")
    _add_json_option(download)
    download.add_argument("url", type=_youtube_url, help="URL de un video o playlist de YouTube.")
    _add_format_options(download)
    selection = download.add_mutually_exclusive_group()
    selection.add_argument("--item", action="append", dest="item_ids", help="ID de elemento a incluir; se puede repetir.")
    selection.add_argument("--all", action="store_true", help="Incluye todos los elementos disponibles de la playlist.")
    download.add_argument("--destination", help="Carpeta absoluta de destino.")
    download.add_argument(
        "--wait",
        action="store_true",
        help="Espera el resultado headless; sin esto solo se añade a la cola.",
    )

    queue = commands.add_parser("queue", help="Consulta y gestiona la cola.")
    _add_json_option(queue)
    queue_commands = queue.add_subparsers(dest="queue_action", required=True, parser_class=_CliArgumentParser)
    for name, help_text in (
        ("list", "Muestra los elementos de la cola."),
        ("pause", "Pausa las descargas activas y pendientes."),
        ("resume", "Reanuda las descargas pausadas."),
    ):
        action = queue_commands.add_parser(name, help=help_text)
        _add_json_option(action)
        if name in {"pause", "resume"}:
            action.add_argument("--wait", action="store_true", help="Espera a que se aplique la acción.")
    cancel = queue_commands.add_parser("cancel", help="Cancela un elemento o todos los trabajos activos.")
    _add_json_option(cancel)
    cancel_target = cancel.add_mutually_exclusive_group(required=True)
    cancel_target.add_argument("item_id", nargs="?", help="ID del elemento a cancelar.")
    cancel_target.add_argument("--all", action="store_true", help="Cancela los trabajos activos y pendientes.")
    cancel.add_argument("--yes", action="store_true", help="Confirma explícitamente una cancelación global.")
    cancel.add_argument("--wait", action="store_true", help="Espera a que terminen las cancelaciones.")
    retry = queue_commands.add_parser("retry", help="Reintenta un elemento fallido.")
    _add_json_option(retry)
    retry.add_argument("item_id", help="ID del elemento fallido.")
    retry.add_argument("--wait", action="store_true", help="Espera el resultado del reintento.")

    history = commands.add_parser("history", help="Consulta y gestiona el historial local.")
    _add_json_option(history)
    history_commands = history.add_subparsers(dest="history_action", required=True, parser_class=_CliArgumentParser)
    history_list = history_commands.add_parser("list", help="Muestra los elementos finalizados.")
    _add_json_option(history_list)
    history_open = history_commands.add_parser("open", help="Abre un archivo finalizado.")
    _add_json_option(history_open)
    history_open.add_argument("item_id", help="ID del elemento finalizado.")
    history_open.add_argument("--index", type=int, default=0, help="Índice de salida cuando hay más de un archivo.")
    history_clear = history_commands.add_parser("clear", help="Elimina registros, nunca los archivos descargados.")
    _add_json_option(history_clear)
    history_clear.add_argument("--yes", action="store_true", help="Confirma explícitamente el borrado de registros.")

    settings = commands.add_parser("settings", help="Consulta y configura preferencias locales.")
    _add_json_option(settings)
    settings_commands = settings.add_subparsers(dest="settings_action", required=True, parser_class=_CliArgumentParser)
    settings_show = settings_commands.add_parser("show", help="Muestra las preferencias guardadas.")
    _add_json_option(settings_show)
    settings_set = settings_commands.add_parser("set", help="Actualiza preferencias con valores explícitos.")
    _add_json_option(settings_set)
    settings_set.add_argument("--destination", help="Carpeta absoluta de destino.")
    settings_set.add_argument("--theme-mode", choices=("system", "dark", "light"))
    settings_set.add_argument("--concurrency-mode", choices=("auto", "manual"))
    settings_set.add_argument("--manual-concurrency", type=int)
    settings_set.add_argument("--auto-cap", type=int)

    return parser


def _command_name(args: argparse.Namespace) -> str:
    parts = [getattr(args, name, None) for name in ("command", "queue_action", "history_action", "settings_action")]
    return " ".join(str(part) for part in parts if part)


def _get_ytdlp_version() -> str | None:
    try:
        ytdlp = importlib.import_module("yt_dlp")
    except ImportError:
        return None
    return getattr(getattr(ytdlp, "version", None), "__version__", None)


def _status_data() -> dict[str, Any]:
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    ytdlp_version = _get_ytdlp_version()

    return {
        "mode": "cli",
        "download_engine_ready": ytdlp_version is not None,
        "yt_dlp_version": ytdlp_version,
        "ffmpeg_ready": bool(ffmpeg_path and ffprobe_path),
        "ffmpeg_path": ffmpeg_path,
        "ffprobe_path": ffprobe_path,
    }


def _selection_for_download(analysis: dict[str, Any], args: argparse.Namespace) -> list[str]:
    items = analysis.get("items") or []
    available = {str(item["id"]): item for item in items if item.get("available") and item.get("source_url")}

    if args.item_ids:
        requested = set(args.item_ids)
        unknown = requested - {str(item["id"]) for item in items}
        if unknown:
            raise _CliCommandError(
                "ITEM_NOT_FOUND",
                f"No se encontraron los elementos solicitados: {', '.join(sorted(unknown))}.",
            )
        unavailable = requested - set(available)
        if unavailable:
            raise _CliCommandError(
                "ITEM_UNAVAILABLE",
                f"Algunos elementos no están disponibles: {', '.join(sorted(unavailable))}.",
            )
        return [str(item["id"]) for item in items if str(item["id"]) in requested]

    if analysis.get("is_playlist") and not args.all:
        raise _CliCommandError(
            "SELECTION_REQUIRED",
            "Para una playlist, indica --all o selecciona elementos con --item.",
        )

    selected = [str(item["id"]) for item in items if item.get("available") and item.get("source_url")]
    if not selected:
        raise _CliCommandError("NO_AVAILABLE_ITEMS", "No hay elementos disponibles para descargar.")
    return selected


def _batch_summary(database: Any, batch_id: str) -> dict[str, Any]:
    rows = database.batch_items(batch_id)
    counts = Counter(str(item.get("status") or "unknown") for item in rows)
    summaries = []
    for item in rows:
        output_paths: list[str] = []
        if item.get("output_path"):
            try:
                decoded = json.loads(item["output_path"])
                if isinstance(decoded, list):
                    output_paths = [str(path) for path in decoded if path]
            except (json.JSONDecodeError, TypeError):
                output_paths = [str(item["output_path"])]
        summaries.append(
            {
                "id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "progress": item["progress"] if item.get("total_bytes") else None,
                "error": item.get("error"),
                "output_paths": output_paths,
            }
        )
    return {
        "batch_id": batch_id,
        "total": len(rows),
        "counts": dict(sorted(counts.items())),
        "items": summaries,
    }


def _emit_download_progress(
    *,
    batch_id: str,
    item: dict[str, Any],
    json_output: bool,
) -> None:
    progress = item.get("progress") if item.get("total_bytes") else None
    if json_output:
        event = {
            "schema_version": JSON_SCHEMA_VERSION,
            "event": "progress",
            "command": "download",
            "batch_id": batch_id,
            "item_id": item["id"],
            "title": item["title"],
            "status": item["status"],
            "progress": progress,
        }
        print(json.dumps(event, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return

    label = f"{int(progress * 100)}%" if progress is not None else "progreso indeterminado"
    print(f"[{item['status']}] {item['title']} · {label}", file=sys.stderr)


def _wait_for_batch(database: Any, batch_id: str, *, json_output: bool) -> dict[str, Any]:
    reported: dict[str, tuple[str, int | None]] = {}
    while True:
        rows = database.batch_items(batch_id)
        if not rows:
            raise _CliCommandError("BATCH_NOT_FOUND", "No se encontró el lote en la cola.")

        for item in rows:
            status = str(item.get("status") or "unknown")
            progress = item.get("progress") if item.get("total_bytes") else None
            bucket = int(float(progress) * 20) if progress is not None else None
            state = (status, bucket)
            if reported.get(str(item["id"])) != state:
                _emit_download_progress(batch_id=batch_id, item=item, json_output=json_output)
                reported[str(item["id"])] = state

        statuses = {str(item.get("status") or "unknown") for item in rows}
        if not statuses.intersection({"queued", "downloading"}):
            summary = _batch_summary(database, batch_id)
            if "paused" in statuses:
                raise _CliCommandError(
                    "DOWNLOAD_PAUSED",
                    "El lote está pausado; reanúdalo y vuelve a consultar la cola.",
                    data=summary,
                )
            if statuses.intersection({"failed", "cancelled"}):
                counts = summary["counts"]
                raise _CliCommandError(
                    "DOWNLOAD_FAILED",
                    f"El lote terminó con {counts.get('failed', 0)} fallidos y "
                    f"{counts.get('cancelled', 0)} cancelados.",
                    data=summary,
                )
            return summary
        time.sleep(0.25)


def _download(args: argparse.Namespace) -> dict[str, Any]:
    from .engine import UserFacingError, analyze_url
    from .manager import DownloadManager
    from .storage import Database

    database = Database()
    manager = DownloadManager(database, autostart=False)
    try:
        try:
            analysis = analyze_url(args.url)
        except UserFacingError as exc:
            raise _CliCommandError("ANALYSIS_FAILED", str(exc)) from exc

        selected_ids = _selection_for_download(analysis, args)
        if args.destination:
            try:
                manager.set_preferences({"destination": args.destination})
            except (ValueError, OSError, TypeError) as exc:
                raise _CliCommandError("INVALID_DESTINATION", str(exc)) from exc

        try:
            queued = manager.enqueue(
                analysis,
                selected_ids,
                args.output_format,
                args.quality,
                start_worker=args.wait,
            )
        except (ValueError, OSError) as exc:
            raise _CliCommandError("DOWNLOAD_FAILED", str(exc)) from exc

        if not args.wait:
            return {
                **queued,
                "status": "queued",
                "selected_ids": selected_ids,
                "destination": database.get_preference("destination"),
            }

        return _wait_for_batch(database, queued["batch_id"], json_output=args.json_output)
    except KeyboardInterrupt as exc:
        manager.pause_all(wait=True)
        raise _CliCommandError(
            "INTERRUPTED",
            "Interrumpido por el usuario; las tareas activas se han pausado.",
        ) from exc
    finally:
        try:
            manager.shutdown(pause_active=False)
        finally:
            database.close()


def _wait_for_item(database: Any, item_id: str, *, json_output: bool) -> dict[str, Any]:
    reported: tuple[str, int | None] | None = None
    while True:
        item = database.get_item(item_id)
        if not item:
            raise _CliCommandError("ITEM_NOT_FOUND", "No se encontró el elemento en la cola.")
        status = str(item.get("status") or "unknown")
        progress = item.get("progress") if item.get("total_bytes") else None
        bucket = int(float(progress) * 20) if progress is not None else None
        state = (status, bucket)
        if state != reported:
            _emit_download_progress(batch_id=item["batch_id"], item=item, json_output=json_output)
            reported = state
        if status not in {"queued", "downloading"}:
            if status == "completed":
                return _batch_summary(database, item["batch_id"])
            if status == "paused":
                raise _CliCommandError(
                    "DOWNLOAD_PAUSED",
                    "El elemento está pausado.",
                    data=_batch_summary(database, item["batch_id"]),
                )
            if status == "failed":
                raise _CliCommandError(
                    "DOWNLOAD_FAILED",
                    "El elemento ha fallado.",
                    data=_batch_summary(database, item["batch_id"]),
                )
            if status == "cancelled":
                raise _CliCommandError(
                    "DOWNLOAD_CANCELLED",
                    "El elemento se ha cancelado.",
                    data=_batch_summary(database, item["batch_id"]),
                )
            return item
        time.sleep(0.25)


def _wait_for_queue_idle(database: Any, manager: Any, *, json_output: bool) -> dict[str, Any]:
    reported: dict[str, tuple[str, int | None]] = {}
    while True:
        rows = database.items_with_status(("queued", "downloading"))
        if not rows:
            state = manager.get_state()
            statuses = {item["status"] for item in state["queue"]}
            if "paused" in statuses:
                raise _CliCommandError("DOWNLOAD_PAUSED", "Hay elementos pausados.", data=state)
            if "failed" in statuses:
                raise _CliCommandError("DOWNLOAD_FAILED", "Hay elementos fallidos.", data=state)
            return state
        for item in rows:
            status = str(item.get("status") or "unknown")
            progress = item.get("progress") if item.get("total_bytes") else None
            bucket = int(float(progress) * 20) if progress is not None else None
            signature = (status, bucket)
            if reported.get(str(item["id"])) != signature:
                _emit_download_progress(
                    batch_id=str(item.get("batch_id") or ""),
                    item=item,
                    json_output=json_output,
                )
                reported[str(item["id"])] = signature
        time.sleep(0.25)


def _queue_command(args: argparse.Namespace) -> dict[str, Any]:
    from .manager import DownloadManager
    from .storage import Database

    database = Database()
    manager = DownloadManager(database, autostart=False)
    try:
        action = args.queue_action
        if action == "list":
            return manager.get_state()
        if action == "pause":
            manager.pause_all(wait=args.wait)
            return manager.get_state()
        if action == "resume":
            if args.wait and not database.get_preference("concurrency_mode"):
                raise _CliCommandError(
                    "CONCURRENCY_NOT_CONFIGURED",
                    "Configura primero el modo y la concurrencia con settings set.",
                )
            manager.resume_all(start_worker=args.wait)
            if args.wait:
                return _wait_for_queue_idle(database, manager, json_output=args.json_output)
            return manager.get_state()
        if action == "cancel":
            if args.all:
                if not args.yes:
                    raise _CliCommandError(
                        "USAGE_ERROR",
                        "Añade --yes para confirmar la cancelación global.",
                    )
                before = database.items_with_status(("queued", "downloading", "paused"))
                manager.cancel_all(wait=args.wait)
                cancelled = sum(
                    1
                    for item in before
                    if (current := database.get_item(item["id"]))
                    and current["status"] == "cancelled"
                )
                return {
                    "requested": len(before),
                    "cancelled": cancelled,
                    "queue": manager.get_state()["queue"],
                }

            item = database.get_item(args.item_id)
            if not item:
                raise _CliCommandError("ITEM_NOT_FOUND", "No se encontró el elemento en la cola.")
            if item["status"] not in {"queued", "downloading", "paused"}:
                raise _CliCommandError(
                    "CANCEL_NOT_AVAILABLE",
                    "El elemento no está activo, pendiente ni pausado.",
                )
            manager.cancel_item(args.item_id)
            current = database.get_item(args.item_id)
            if args.wait:
                deadline = time.monotonic() + 40
                while (
                    current
                    and current["status"] in {"queued", "downloading"}
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.25)
                    current = database.get_item(args.item_id)
            if not current:
                raise _CliCommandError("ITEM_NOT_FOUND", "No se encontró el elemento en la cola.")
            result = {
                "item_id": args.item_id,
                "status": current["status"],
                "cancel_requested": item["status"] == "downloading",
            }
            if args.wait and current["status"] != "cancelled":
                raise _CliCommandError(
                    "CANCEL_NOT_AVAILABLE",
                    "No se confirmó la cancelación. Consulta el estado actual de la cola.",
                    data=result,
                )
            return result

        if action == "retry":
            if args.wait and not database.get_preference("concurrency_mode"):
                raise _CliCommandError(
                    "CONCURRENCY_NOT_CONFIGURED",
                    "Configura primero el modo y la concurrencia con settings set.",
                )
            try:
                manager.retry_item(args.item_id, start_worker=args.wait)
            except ValueError as exc:
                raise _CliCommandError("RETRY_NOT_AVAILABLE", str(exc)) from exc
            if args.wait:
                return _wait_for_item(database, args.item_id, json_output=args.json_output)
            return {"item_id": args.item_id, "status": "queued"}

        raise _CliCommandError("NOT_IMPLEMENTED", "Acción de cola no implementada.")
    finally:
        try:
            manager.shutdown(pause_active=False)
        finally:
            database.close()


def _history_command(args: argparse.Namespace) -> dict[str, Any]:
    import os

    from .manager import DownloadManager
    from .storage import Database

    database = Database()
    manager = DownloadManager(database, autostart=False)
    try:
        if args.history_action == "list":
            return {"history": manager.get_state()["history"]}
        if args.history_action == "clear":
            if not args.yes:
                raise _CliCommandError(
                    "USAGE_ERROR",
                    "Añade --yes para confirmar que se borrarán solo los registros del historial.",
                )
            return {"removed": manager.clear_history(), "media_deleted": False}
        if args.history_action == "open":
            start_file = getattr(os, "startfile", None)
            if start_file is None:
                raise _CliCommandError("OPEN_UNSUPPORTED", "Abrir archivos del historial solo está disponible en Windows.")
            try:
                path = manager.get_history_path(args.item_id, args.index)
            except ValueError as exc:
                raise _CliCommandError("FILE_NOT_FOUND", str(exc)) from exc
            if not path.is_file():
                raise _CliCommandError("FILE_NOT_FOUND", "El archivo ya no existe en la ruta guardada.")
            try:
                start_file(str(path))
            except OSError as exc:
                raise _CliCommandError("OPEN_FAILED", str(exc)) from exc
            return {"item_id": args.item_id, "opened": True}
        raise _CliCommandError("NOT_IMPLEMENTED", "Acción de historial no implementada.")
    finally:
        manager.shutdown(pause_active=False)
        database.close()


def _settings_command(args: argparse.Namespace) -> dict[str, Any]:
    from .manager import DownloadManager
    from .storage import Database

    database = Database()
    manager = DownloadManager(database, autostart=False)
    try:
        if args.settings_action == "show":
            preferences = database.get_preferences()
        elif args.settings_action == "set":
            updates: dict[str, Any] = {}
            for arg_name, preference_name in (
                ("destination", "destination"),
                ("theme_mode", "theme_mode"),
                ("concurrency_mode", "concurrency_mode"),
                ("manual_concurrency", "manual_concurrency"),
                ("auto_cap", "auto_concurrency_cap"),
            ):
                value = getattr(args, arg_name)
                if value is not None:
                    updates[preference_name] = value
            if not updates:
                raise _CliCommandError("USAGE_ERROR", "Indica al menos una preferencia para actualizar.")
            mode = updates.get(
                "concurrency_mode",
                database.get_preference("concurrency_mode"),
            )
            if mode is None and {"manual_concurrency", "auto_concurrency_cap"}.intersection(updates):
                raise _CliCommandError(
                    "INVALID_SETTINGS",
                    "Indica --concurrency-mode al configurar la concurrencia inicial.",
                )
            if mode == "manual" and "auto_concurrency_cap" in updates:
                raise _CliCommandError(
                    "INVALID_SETTINGS",
                    "--auto-cap solo se usa con --concurrency-mode auto.",
                )
            if mode == "auto" and "manual_concurrency" in updates:
                raise _CliCommandError(
                    "INVALID_SETTINGS",
                    "--manual-concurrency solo se usa con --concurrency-mode manual.",
                )
            try:
                manager.set_preferences(updates)
            except (ValueError, OSError, TypeError) as exc:
                raise _CliCommandError("INVALID_SETTINGS", str(exc)) from exc
            preferences = database.get_preferences()
        else:
            raise _CliCommandError("NOT_IMPLEMENTED", "Acción de preferencias no implementada.")

        return {
            "preferences": {
                key: preferences.get(key)
                for key in (
                    "destination",
                    "theme_mode",
                    "concurrency_mode",
                    "manual_concurrency",
                    "auto_concurrency_cap",
                )
            }
        }
    finally:
        manager.shutdown(pause_active=False)
        database.close()


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "status":
        return _status_data()

    if args.command == "analyze":
        try:
            from .engine import UserFacingError, analyze_url
        except ImportError as exc:
            raise _CliCommandError("ENGINE_UNAVAILABLE", "El motor yt-dlp no está disponible.") from exc
        try:
            return analyze_url(args.url)
        except UserFacingError as exc:
            raise _CliCommandError("ANALYSIS_FAILED", str(exc)) from exc

    if args.command == "preview":
        try:
            from .engine import UserFacingError, get_preview
        except ImportError as exc:
            raise _CliCommandError("ENGINE_UNAVAILABLE", "El motor yt-dlp no está disponible.") from exc
        try:
            return get_preview(args.url, args.output_format, args.quality)
        except UserFacingError as exc:
            raise _CliCommandError("PREVIEW_FAILED", str(exc)) from exc

    if args.command == "download":
        return _download(args)

    if args.command == "queue":
        return _queue_command(args)

    if args.command == "history":
        return _history_command(args)

    if args.command == "settings":
        return _settings_command(args)

    raise _CliCommandError(
        "NOT_IMPLEMENTED",
        "Este comando forma parte de la CLI en desarrollo y aún no está disponible.",
    )


def _write_text_result(command: str, data: dict[str, Any]) -> None:
    if command == "status":
        engine_state = "disponible" if data["download_engine_ready"] else "no disponible"
        ffmpeg_state = "disponible" if data["ffmpeg_ready"] else "no disponible"
        print(f"Motor yt-dlp: {engine_state} ({data['yt_dlp_version'] or 'sin versión'})")
        print(f"FFmpeg: {ffmpeg_state}")
        if data["ffmpeg_path"]:
            print(f"  ffmpeg: {data['ffmpeg_path']}")
        if data["ffprobe_path"]:
            print(f"  ffprobe: {data['ffprobe_path']}")
        return

    if command == "analyze":
        kind = "Playlist" if data.get("is_playlist") else "Video"
        items = data.get("items") or []
        print(f"{kind}: {data.get('title') or 'Colección sin título'}")
        print(f"{len(items)} elementos")
        for item in items:
            availability = "Disponible" if item.get("available") else "No disponible"
            print(f"{item.get('index', '?')}. [{availability}] {item.get('title', 'Elemento sin título')}")
        return

    if command == "preview":
        print(f"Vista previa: {data.get('title') or 'Elemento sin título'}")
        print(f"Formato: {data.get('kind') or 'desconocido'}")
        print("Reproducible" if data.get("playable") else "La fuente no ofrece un flujo reproducible.")
        if data.get("url"):
            print(f"Flujo: {data['url']}")
        return

    if command == "download":
        print(f"Lote: {data.get('batch_id')}")
        if data.get("counts"):
            for status, count in data["counts"].items():
                print(f"{status}: {count}")
        else:
            print(f"{data.get('queued', 0)} elementos añadidos a la cola.")
        return

    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _write_success(command: str, data: dict[str, Any], *, json_output: bool) -> int:
    if json_output:
        payload = {
            "schema_version": JSON_SCHEMA_VERSION,
            "ok": True,
            "command": command,
            "data": data,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        _write_text_result(command, data)
    return EXIT_OK


def _write_error(
    command: str | None,
    code: str,
    message: str,
    *,
    json_output: bool,
    data: dict[str, Any] | None = None,
) -> int:
    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "ok": False,
        "command": command,
        "error": {"code": code, "message": message},
    }
    if data is not None:
        payload["data"] = data
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    else:
        print(f"Error [{code}]: {message}", file=sys.stderr)
    if code == "USAGE_ERROR":
        return EXIT_USAGE
    if code == "OPERATION_FAILED":
        return EXIT_OPERATION_FAILED
    if code in {
        "ANALYSIS_FAILED",
        "PREVIEW_FAILED",
        "INTERNAL_ERROR",
        "DOWNLOAD_FAILED",
        "DOWNLOAD_PAUSED",
        "DOWNLOAD_CANCELLED",
        "CANCEL_NOT_AVAILABLE",
        "RETRY_NOT_AVAILABLE",
        "FILE_NOT_FOUND",
        "OPEN_FAILED",
    }:
        return EXIT_OPERATION_FAILED
    if code == "INTERRUPTED":
        return EXIT_INTERRUPTED
    if code in {
        "ITEM_NOT_FOUND",
        "ITEM_UNAVAILABLE",
        "SELECTION_REQUIRED",
        "NO_AVAILABLE_ITEMS",
        "INVALID_DESTINATION",
        "INVALID_SETTINGS",
        "CONCURRENCY_NOT_CONFIGURED",
    }:
        return EXIT_USAGE
    return EXIT_UNAVAILABLE


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    json_output = "--json" in arguments
    parser = build_parser()
    try:
        args = parser.parse_args(arguments)
    except _CliUsageError as exc:
        if not json_output:
            parser.print_usage(sys.stderr)
        return _write_error(None, "USAGE_ERROR", str(exc), json_output=json_output)
    except SystemExit as exc:
        return int(exc.code or EXIT_OK)

    command = _command_name(args)
    if not command:
        return _write_error(None, "USAGE_ERROR", "Indica un comando.", json_output=args.json_output)

    try:
        data = _dispatch(args)
    except _CliCommandError as exc:
        return _write_error(
            command,
            exc.code,
            str(exc),
            json_output=args.json_output,
            data=exc.data,
        )
    except Exception:
        return _write_error(
            command,
            "INTERNAL_ERROR",
            "No se pudo completar el comando. Consulta el registro local de Clipoteca.",
            json_output=args.json_output,
        )
    return _write_success(command, data, json_output=args.json_output)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import logging
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .engine import (
    DownloadInterrupted,
    UserFacingError,
    download_item,
    safe_filename,
    validate_source_url,
)
from .storage import ACTIVE_STATUSES, Database


logger = logging.getLogger("clipoteca.manager")
Notifier = Callable[[str, str], None]


class DownloadManager:
    def __init__(
        self,
        database: Database,
        notifier: Notifier | None = None,
        *,
        downloader: Callable[..., dict[str, Any]] = download_item,
        autostart: bool = True,
    ) -> None:
        self.database = database
        self.notifier = notifier or (lambda _title, _message: None)
        self.downloader = downloader
        self._lock = threading.RLock()
        self._running: dict[str, threading.Thread] = {}
        self._actions: dict[str, str] = {}
        self._stopping = threading.Event()
        self._auto_target = 1
        self._last_auto_sample = 0.0
        self._last_auto_speed: float | None = None
        self._scheduler: threading.Thread | None = None
        self._set_default_preferences()
        if autostart:
            self.start()

    def _set_default_preferences(self) -> None:
        if self.database.get_preference("destination") is None:
            self.database.set_preference(
                "destination",
                str(Path.home() / "Downloads" / "Clipoteca"),
            )
        if self.database.get_preference("concurrency_setup_confirmed") is not True:
            for key in ("concurrency_mode", "manual_concurrency", "auto_concurrency_cap"):
                if self.database.get_preference(key) is not None:
                    self.database.set_preference(key, None)

    def start(self) -> None:
        if self._scheduler and self._scheduler.is_alive():
            return
        self._stopping.clear()
        self._scheduler = threading.Thread(target=self._schedule, name="clipoteca-queue", daemon=True)
        self._scheduler.start()

    def shutdown(self, *, pause_active: bool = True, timeout: float = 40) -> None:
        if pause_active:
            self.pause_all(wait=True, timeout=timeout)
        self._stopping.set()
        if self._scheduler:
            self._scheduler.join(timeout=2)
        with self._lock:
            workers = list(self._running.values())
        for worker in workers:
            worker.join(timeout=max(0, timeout))

    def get_state(self) -> dict[str, Any]:
        state = self.database.get_queue_state()
        for item in (*state["queue"], *state["history"]):
            item["output_paths"] = _decode_output_paths(item.get("output_path"))
        state["active_downloads"] = sum(
            1 for item in state["queue"] if item["status"] == "downloading"
        )
        return state

    def get_history_path(self, item_id: str, index: int = 0) -> Path:
        item = self.database.get_item(item_id)
        if not item or item["status"] != "completed":
            raise ValueError("El archivo solo se puede abrir desde un elemento finalizado.")
        paths = _decode_output_paths(item.get("output_path"))
        if index < 0 or index >= len(paths):
            raise ValueError("No se encontró una ruta de archivo para este elemento.")
        return Path(paths[index])

    def has_pending_or_running(self) -> bool:
        rows = self.database.items_with_status(("queued", "downloading"))
        return bool(rows)

    def set_preferences(self, values: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        if "destination" in values:
            destination = Path(str(values["destination"])).expanduser()
            if not destination.is_absolute():
                raise ValueError("La carpeta de destino debe ser una ruta absoluta.")
            updates["destination"] = str(destination)

        current_mode = self.database.get_preference("concurrency_mode")
        mode = values.get("concurrency_mode", current_mode)
        if mode is not None:
            mode = str(mode)
            if mode not in {"auto", "manual"}:
                raise ValueError("Modo de concurrencia no válido.")
            updates["concurrency_mode"] = mode

        for key in ("manual_concurrency", "auto_concurrency_cap"):
            if key in values:
                try:
                    count = int(values[key])
                except (TypeError, ValueError) as exc:
                    raise ValueError("El número de descargas simultáneas debe ser un entero positivo.") from exc
                if count < 1:
                    raise ValueError("El número de descargas simultáneas debe ser al menos 1.")
                updates[key] = count

        if mode is not None:
            required_key = "manual_concurrency" if mode == "manual" else "auto_concurrency_cap"
            required_value = updates.get(required_key, self.database.get_preference(required_key))
            if required_value is None:
                raise ValueError("Elige cuántas descargas simultáneas quieres ejecutar.")
            updates[required_key] = int(required_value)

        for key, value in updates.items():
            self.database.set_preference(key, value)
        if mode is not None:
            self.database.set_preference("concurrency_setup_confirmed", True)
        with self._lock:
            self._auto_target = 1
        return self.database.get_preferences()

    def enqueue(
        self,
        analysis: dict[str, Any],
        selected_ids: list[str],
        output_format: str,
        quality: str,
    ) -> dict[str, Any]:
        if output_format not in {"video", "audio", "both"}:
            raise ValueError("Formato de salida no válido.")
        if self.database.get_preference("concurrency_mode") not in {"auto", "manual"}:
            raise ValueError("Elige el modo de concurrencia antes de iniciar una descarga.")
        validate_source_url(str(analysis.get("source_url") or ""))
        chosen_destination = str(self.database.get_preference("destination"))
        destination_path = Path(chosen_destination).expanduser()
        if not destination_path.is_absolute():
            raise ValueError("La carpeta de destino debe ser una ruta absoluta.")
        selected = set(selected_ids)
        selected_items = [
            item for item in analysis.get("items", [])
            if item.get("id") in selected and item.get("available") and item.get("source_url")
        ]
        if not selected_items:
            raise ValueError("Selecciona al menos un elemento disponible.")
        for item in selected_items:
            validate_source_url(str(item["source_url"]))

        batch_id = str(uuid.uuid4())
        batch = {
            "id": batch_id,
            "source_url": analysis["source_url"],
            "title": analysis.get("title") or "Colección sin título",
            "is_playlist": bool(analysis.get("is_playlist")),
            "destination": str(destination_path),
            "output_format": output_format,
            "quality": quality,
        }
        items = [
            {
                "id": str(uuid.uuid4()),
                "source_id": str(item.get("source_id") or item["id"]),
                "source_url": item["source_url"],
                "title": item.get("title") or "Elemento sin título",
                "duration": item.get("duration"),
            }
            for item in selected_items
        ]
        self.database.create_batch(batch, items)
        self.start()
        return {"batch_id": batch_id, "queued": len(items)}

    def retry_item(self, item_id: str) -> None:
        item = self.database.get_item(item_id)
        if not item or item["status"] != "failed":
            raise ValueError("Este elemento no está disponible para reintento.")
        self.database.update_item(item_id, status="queued", progress=0, error=None, attempts=0)
        self.start()

    def pause_all(self, *, wait: bool = False, timeout: float = 40) -> None:
        with self._lock:
            rows = self.database.items_with_status(ACTIVE_STATUSES)
            for item in rows:
                item_id = item["id"]
                if item["status"] == "downloading":
                    self._actions.setdefault(item_id, "pause")
                elif item["status"] == "queued":
                    self.database.update_item(item_id, status="paused")
        if wait:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                with self._lock:
                    if not self._running:
                        break
                time.sleep(0.1)

    def resume_all(self) -> None:
        for item in self.database.items_with_status(("paused",)):
            self.database.update_item(item["id"], status="queued", error=None)
        self.start()

    def cancel_item(self, item_id: str) -> None:
        with self._lock:
            item = self.database.get_item(item_id)
            if not item or item["status"] not in ACTIVE_STATUSES:
                return
            if item["status"] == "downloading":
                self._actions[item_id] = "cancel"
            else:
                self.database.mark_cancelled(item_id)
                self._remove_partials(item)

    def cancel_all(self, *, wait: bool = True, timeout: float = 40) -> None:
        with self._lock:
            rows = self.database.items_with_status(ACTIVE_STATUSES)
            for item in rows:
                if item["status"] == "downloading":
                    self._actions[item["id"]] = "cancel"
                else:
                    self.database.mark_cancelled(item["id"])
                    self._remove_partials(item)
        if wait:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                with self._lock:
                    if not self._running:
                        break
                time.sleep(0.1)

    def clear_history(self) -> int:
        return self.database.clear_history()

    def _schedule(self) -> None:
        while not self._stopping.is_set():
            try:
                self._launch_ready_items()
            except Exception:
                logger.exception("Error inesperado al programar la cola")
            self._stopping.wait(0.25)

    def _launch_ready_items(self) -> None:
        with self._lock:
            queued = self.database.items_with_status(("queued",))
            if not queued:
                return
            self._adjust_auto_target(queued)
            mode = self.database.get_preference("concurrency_mode")
            if mode == "manual":
                configured_target = self.database.get_preference("manual_concurrency")
                if configured_target is None:
                    return
                target = int(configured_target)
            elif mode == "auto":
                configured_cap = self.database.get_preference("auto_concurrency_cap")
                if configured_cap is None:
                    return
                cap = int(configured_cap)
                target = min(self._auto_target, cap)
            else:
                return
            slots = max(0, target - len(self._running))
            for item in queued[:slots]:
                if item["id"] in self._running:
                    continue
                current = self.database.get_item(item["id"])
                if not current or current["status"] != "queued":
                    continue
                thread = threading.Thread(
                    target=self._run_item,
                    args=(item["id"],),
                    name=f"clipoteca-download-{item['id'][:8]}",
                    daemon=True,
                )
                self._running[item["id"]] = thread
                thread.start()

    def _adjust_auto_target(self, queued: list[dict[str, Any]]) -> None:
        if self.database.get_preference("concurrency_mode") != "auto":
            return
        configured_cap = self.database.get_preference("auto_concurrency_cap")
        if configured_cap is None:
            return
        cap = int(configured_cap)
        now = time.monotonic()
        if now - self._last_auto_sample < 8:
            return
        active = self.database.items_with_status(("downloading",))
        if not active or not queued:
            return
        speed = sum(float(item.get("speed") or 0) for item in active)
        if len(active) >= self._auto_target and self._auto_target < cap:
            if speed > 0 and (
                self._last_auto_speed is None or speed >= self._last_auto_speed * 0.9
            ):
                self._auto_target += 1
            elif self._last_auto_speed is not None and speed < self._last_auto_speed * 0.7:
                self._auto_target = max(1, self._auto_target - 1)
        self._last_auto_speed = speed if speed > 0 else self._last_auto_speed
        self._last_auto_sample = now

    def _run_item(self, item_id: str) -> None:
        with self._lock:
            item = self.database.get_item(item_id)
            if not item or item["status"] != "queued":
                self._running.pop(item_id, None)
                return
            self.database.update_item(item_id, status="downloading", error=None)
        destination = Path(item["destination"])
        if item["is_playlist"]:
            destination = destination / safe_filename(item["batch_title"])

        try:
            for attempt in range(4):
                self.database.update_item(item_id, attempts=attempt)
                try:
                    result = self.downloader(
                        source_url=item["source_url"],
                        source_id=item["source_id"],
                        title=item["title"],
                        destination=destination,
                        output_format=item["output_format"],
                        quality=item["quality"],
                        progress=lambda value: self._update_progress(item_id, value),
                        should_stop=lambda: self._get_action(item_id),
                    )
                    action = self._get_action(item_id)
                    if action == "cancel":
                        self._remove_partials(item)
                        self.database.mark_cancelled(item_id)
                    else:
                        note = "Ya existía; no se sobrescribió." if result.get("duplicate") else None
                        self.database.update_item(
                            item_id,
                            status="completed",
                            progress=1,
                            output_path=json.dumps(result.get("paths", []), ensure_ascii=False),
                            error=note,
                        )
                        if note:
                            self._notify("Archivo duplicado omitido", item["title"])
                    self._notify_batch_if_finished(item["batch_id"])
                    return
                except DownloadInterrupted as exc:
                    if exc.action == "cancel" or self._get_action(item_id) == "cancel":
                        self._remove_partials(item)
                        self.database.mark_cancelled(item_id)
                    else:
                        self.database.update_item(item_id, status="paused", error=None)
                    return
                except UserFacingError as exc:
                    if exc.retryable and attempt < 3:
                        self.database.update_item(item_id, status="downloading", error=None)
                        if self._wait_or_stop(item_id, 2 ** attempt):
                            continue
                        action = self._get_action(item_id)
                        if action == "cancel":
                            self._remove_partials(item)
                            self.database.mark_cancelled(item_id)
                        elif action == "pause":
                            self.database.update_item(item_id, status="paused")
                        return
                    self.database.update_item(item_id, status="failed", error=str(exc))
                    self._notify("Descarga fallida", item["title"])
                    self._notify_batch_if_finished(item["batch_id"])
                    return
                except Exception as exc:
                    logger.exception("Fallo no controlado en el elemento %s", item_id)
                    self.database.update_item(
                        item_id,
                        status="failed",
                        error="No se pudo completar la descarga. Consulta el registro local para más detalles.",
                    )
                    self._notify("Descarga fallida", item["title"])
                    self._notify_batch_if_finished(item["batch_id"])
                    return
        finally:
            with self._lock:
                self._actions.pop(item_id, None)
                self._running.pop(item_id, None)

    def _update_progress(self, item_id: str, value: dict[str, Any]) -> None:
        self.database.update_item(
            item_id,
            progress=float(value.get("progress") or 0),
            downloaded_bytes=value.get("downloaded_bytes") or 0,
            total_bytes=value.get("total_bytes"),
            speed=value.get("speed"),
            eta=value.get("eta"),
        )

    def _get_action(self, item_id: str) -> str | None:
        with self._lock:
            return self._actions.get(item_id)

    def _wait_or_stop(self, item_id: str, seconds: int) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._get_action(item_id):
                return False
            time.sleep(0.1)
        return True

    def _remove_partials(self, item: dict[str, Any]) -> None:
        destination = Path(item["destination"])
        if item["is_playlist"]:
            destination = destination / safe_filename(item["batch_title"])
        base = f"{safe_filename(item['title'])} [{safe_filename(item['source_id'], 48)}]"
        if not destination.is_dir():
            return
        try:
            partial_paths = list(destination.iterdir())
        except OSError:
            logger.exception("No se pudo revisar la carpeta de temporales de una descarga cancelada")
            return
        for path in partial_paths:
            name = path.name
            if name.startswith(base) and (
                name.endswith(".part") or name.endswith(".ytdl") or ".part-Frag" in name
            ):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("No se pudo borrar el archivo parcial %s", path.name)

    def _notify_batch_if_finished(self, batch_id: str) -> None:
        items = self.database.batch_items(batch_id)
        if not items or any(item["status"] in {"queued", "downloading", "paused"} for item in items):
            return
        completed = sum(item["status"] == "completed" for item in items)
        failed = sum(item["status"] == "failed" for item in items)
        if completed == 0 and failed == 0:
            return
        if failed:
            self._notify("Lote terminado con fallos", f"{completed} completados · {failed} por reintentar")
        else:
            self._notify("Lote terminado", f"{completed} elementos completados")

    def _notify(self, title: str, message: str) -> None:
        try:
            self.notifier(title, message)
        except Exception:
            logger.exception("No se pudo mostrar una notificación de Windows")


def _decode_output_paths(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        decoded = json.loads(value)
        if isinstance(decoded, list):
            return [str(path) for path in decoded if path]
    except (json.JSONDecodeError, TypeError):
        pass
    # Backward compatibility with queue rows created by the first integration.
    return [path.strip() for path in value.split("; ") if path.strip()]

from __future__ import annotations

import logging
import json
import os
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
from .storage import Database
from .worker_lock import WorkerLock


logger = logging.getLogger("clipoteca.manager")
Notifier = Callable[[str, str], None]
_DUPLICATE_NOTE = "Ya existía; no se sobrescribió."
_PARTIAL_DUPLICATE_NOTE = "Ya existían algunos archivos; se guardó el resto."


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
        self._notified_batches: dict[str, str] = {}
        self._running_targets: dict[str, str] = {}
        self._active_output_targets: set[str] = set()
        self._stopping = threading.Event()
        self._worker_lock = WorkerLock(database.path.with_suffix(database.path.suffix + ".worker.lock"))
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
        if self.database.get_preference("theme_mode") not in {"system", "dark", "light"}:
            self.database.set_preference("theme_mode", "system")
        if self.database.get_preference("concurrency_setup_confirmed") is not True:
            for key in ("concurrency_mode", "manual_concurrency", "auto_concurrency_cap"):
                if self.database.get_preference(key) is not None:
                    self.database.set_preference(key, None)

    def start(self) -> None:
        with self._lock:
            if self._scheduler and self._scheduler.is_alive():
                return
            self._stopping.clear()
            self._scheduler = threading.Thread(target=self._schedule, name="clipoteca-queue", daemon=True)
            self._scheduler.start()

    def shutdown(self, *, pause_active: bool = True, timeout: float = 40) -> None:
        if pause_active:
            self.pause_all(wait=True, timeout=timeout)
        with self._lock:
            self._stopping.set()
            scheduler = self._scheduler
        if scheduler:
            scheduler.join(timeout=max(0, timeout))

    def get_state(self) -> dict[str, Any]:
        state = self.database.get_queue_state()
        for item in (*state["queue"], *state["history"]):
            item["output_paths"] = _decode_output_paths(item.get("output_path"))
            if item.get("download_steps"):
                item["download_steps"] = json.loads(item["download_steps"])
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

    @property
    def owns_worker(self) -> bool:
        return self._worker_lock.acquired

    def set_preferences(self, values: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        if "destination" in values:
            destination = Path(str(values["destination"])).expanduser()
            if not destination.is_absolute():
                raise ValueError("La carpeta de destino debe ser una ruta absoluta.")
            updates["destination"] = str(destination)

        if "theme_mode" in values:
            theme_mode = str(values["theme_mode"])
            if theme_mode not in {"system", "dark", "light"}:
                raise ValueError("Modo de tema no válido.")
            updates["theme_mode"] = theme_mode

        if "theme_accent" in values:
            theme_accent = str(values["theme_accent"])
            if theme_accent not in {"clipoteca", "iris", "blue", "green", "amber"}:
                raise ValueError("Color de acento no válido.")
            updates["theme_accent"] = theme_accent

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
        *,
        start_worker: bool = True,
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
        if start_worker:
            self.start()
        return {"batch_id": batch_id, "queued": len(items)}

    def retry_item(self, item_id: str, *, start_worker: bool = True) -> None:
        item = self.database.get_item(item_id)
        if not item or item["status"] != "failed":
            raise ValueError("Este elemento no está disponible para reintento.")
        self.database.clear_worker_action(item_id)
        self.database.update_item(item_id, status="queued", progress=0, error=None, attempts=0)
        if start_worker:
            self.start()

    def pause_all(self, *, wait: bool = False, timeout: float = 40) -> None:
        downloading_ids: list[str] = []
        with self._lock:
            rows = self.database.items_with_status(("queued", "downloading"))
            for item in rows:
                if self.database.set_worker_action(item["id"], "pause") == "downloading":
                    downloading_ids.append(item["id"])
        if wait:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if not any(
                    (item := self.database.get_item(item_id))
                    and item["status"] == "downloading"
                    for item_id in downloading_ids
                ):
                    break
                time.sleep(0.1)

    def resume_all(self, *, start_worker: bool = True) -> None:
        for item in self.database.items_with_status(("paused",)):
            self.database.clear_worker_action(item["id"])
            self.database.update_item(item["id"], status="queued", error=None)
        for item in self.database.items_with_status(("downloading",)):
            if self.database.get_worker_action(item["id"]) == "pause":
                self.database.clear_worker_action(item["id"])
        if start_worker:
            self.start()

    def cancel_item(self, item_id: str) -> None:
        with self._lock:
            item = self.database.get_item(item_id)
            if item and self.database.set_worker_action(item_id, "cancel") == "cancelled":
                self._remove_inactive_partials(item)

    def cancel_all(self, *, wait: bool = True, timeout: float = 40) -> None:
        downloading_ids: list[str] = []
        with self._lock:
            rows = self.database.items_with_status(("queued", "downloading", "paused"))
            for item in rows:
                status = self.database.set_worker_action(item["id"], "cancel")
                if status == "downloading":
                    downloading_ids.append(item["id"])
                elif status == "cancelled":
                    self._remove_inactive_partials(item)
        if wait:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if not any(
                    (item := self.database.get_item(item_id))
                    and item["status"] == "downloading"
                    for item_id in downloading_ids
                ):
                    break
                time.sleep(0.1)

    def clear_history(self) -> int:
        return self.database.clear_history()

    def _schedule(self) -> None:
        try:
            while not self._stopping.is_set():
                try:
                    if not self._worker_lock.acquired:
                        if not self._worker_lock.acquire():
                            self._stopping.wait(0.25)
                            continue
                        self.database.recover_interrupted_items()
                    self._launch_ready_items()
                except Exception:
                    logger.exception("Error inesperado al programar la cola")
                self._stopping.wait(0.25)
        finally:
            # A timed-out caller can return while a download still owns its files.
            with self._lock:
                workers = list(self._running.values())
            for worker in workers:
                worker.join()
            self._worker_lock.release()

    def _launch_ready_items(self) -> None:
        if not self._worker_lock.acquired:
            return
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
            started = 0
            for item in queued:
                if started >= slots:
                    break
                if item["id"] in self._running:
                    continue
                output_target = self._output_target(item)
                if output_target in self._active_output_targets:
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
                self._running_targets[item["id"]] = output_target
                self._active_output_targets.add(output_target)
                try:
                    thread.start()
                except Exception:
                    self._release_running_item(item["id"])
                    raise
                started += 1

    @staticmethod
    def _output_target(item: dict[str, Any]) -> str:
        destination = Path(item["destination"])
        if item["is_playlist"]:
            destination = destination / safe_filename(item["batch_title"])
        base_name = f"{safe_filename(item['title'])} [{safe_filename(item['source_id'], 48)}]"
        return os.path.normcase(str(destination / base_name))

    def _release_running_item(self, item_id: str) -> None:
        with self._lock:
            self._running.pop(item_id, None)
            output_target = self._running_targets.pop(item_id, None)
            if output_target:
                self._active_output_targets.discard(output_target)

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
        claimed = False
        try:
            with self._lock:
                item = self.database.get_item(item_id)
                if not item or not self.database.claim_queued_item(item_id):
                    return
                claimed = True
            destination = Path(item["destination"])
            if item["is_playlist"]:
                destination = destination / safe_filename(item["batch_title"])

            for attempt in range(4):
                self.database.update_item(item_id, attempts=attempt, download_phase="preparing")
                try:
                    action = self._get_action(item_id)
                    if action:
                        raise DownloadInterrupted(action)
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
                        note = None
                        if result.get("duplicate"):
                            note = _DUPLICATE_NOTE if result.get("duplicate_only", True) else _PARTIAL_DUPLICATE_NOTE
                        self.database.update_item(
                            item_id,
                            status="completed",
                            progress=1,
                            output_path=json.dumps(result.get("paths", []), ensure_ascii=False),
                            error=note,
                        )
                    return
                except DownloadInterrupted as exc:
                    action = self._get_action(item_id)
                    if exc.action == "cancel" or action == "cancel":
                        self._remove_partials(item)
                        self.database.mark_cancelled(item_id)
                    elif action == "pause":
                        self.database.update_item(item_id, status="paused", error=None)
                    else:
                        self.database.update_item(item_id, status="queued", error=None)
                    return
                except UserFacingError as exc:
                    if exc.retryable and attempt < 3:
                        self.database.update_item(
                            item_id, download_phase="retrying", total_bytes=None, eta=None, speed=None,
                        )
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
                    return
                except Exception as exc:
                    logger.exception("Fallo no controlado en el elemento %s", item_id)
                    self.database.update_item(
                        item_id,
                        status="failed",
                        error="No se pudo completar la descarga. Consulta el registro local para más detalles.",
                    )
                    return
        finally:
            try:
                if claimed:
                    self.database.clear_worker_action(item_id)
                    self._notify_batch_if_finished(item["batch_id"], item["batch_title"])
            finally:
                self._release_running_item(item_id)

    def _update_progress(self, item_id: str, value: dict[str, Any]) -> None:
        steps = {"download_steps": json.dumps(value["steps"])} if "steps" in value else {}
        self.database.update_item(
            item_id,
            progress=float(value.get("progress") or 0),
            downloaded_bytes=value.get("downloaded_bytes") or 0,
            total_bytes=value.get("total_bytes"),
            speed=value.get("speed"),
            eta=value.get("eta"),
            download_phase=value.get("phase"),
            **steps,
        )

    def _get_action(self, item_id: str) -> str | None:
        return self.database.get_worker_action(item_id)

    def _wait_or_stop(self, item_id: str, seconds: int) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._get_action(item_id):
                return False
            time.sleep(0.1)
        return True

    def _remove_inactive_partials(self, item: dict[str, Any]) -> None:
        target = self._output_target(item)
        with self.database.block_download_claims():
            for downloading in self.database.items_with_status(("downloading",)):
                if self._output_target(downloading) == target:
                    return
            self._remove_partials(item)

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

    def _notify_batch_if_finished(self, batch_id: str, batch_title: str) -> None:
        items = self.database.batch_items(batch_id)
        if not items or any(item["status"] in {"queued", "downloading", "paused"} for item in items):
            return
        completed = sum(item["status"] == "completed" for item in items)
        failed = sum(item["status"] == "failed" for item in items)
        if completed == 0 and failed == 0:
            return
        finished_at = max(item["updated_at"] for item in items)
        with self._lock:
            if self._notified_batches.get(batch_id) == finished_at:
                return
            self._notified_batches[batch_id] = finished_at

        duplicates = sum(item["status"] == "completed" and item["error"] == _DUPLICATE_NOTE for item in items)
        if len(items) == 1:
            item = items[0]
            if failed:
                self._notify("Descarga fallida", f"{item['title']}\n{item['error'] or 'Revisa la cola e inténtalo de nuevo.'}")
            elif duplicates:
                self._notify("Archivo existente", f"{item['title']}\n{_DUPLICATE_NOTE}")
            else:
                message = item["title"]
                if item["error"] == _PARTIAL_DUPLICATE_NOTE:
                    message += f"\n{_PARTIAL_DUPLICATE_NOTE}"
                self._notify("Descarga completada", message)
            return

        downloaded = completed - duplicates
        cancelled = sum(item["status"] == "cancelled" for item in items)
        details = [f"{downloaded} nuevos"]
        if duplicates:
            details.append(f"{duplicates} ya existentes")
        if failed:
            details.append(f"{failed} por reintentar")
        if cancelled:
            details.append(f"{cancelled} cancelados")
        title = "Lote terminado con fallos" if failed else "Lote terminado"
        self._notify(title, f"{batch_title}\n{' · '.join(details)}")

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

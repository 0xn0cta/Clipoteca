from __future__ import annotations

import logging
import os
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from .engine import UserFacingError, analyze_url, get_preview
from .manager import DownloadManager
from .storage import Database


logger = logging.getLogger("clipoteca.api")
Notifier = Callable[[str, str], None]


class DesktopApi:
    """Explicit JavaScript bridge for local desktop capabilities."""

    def __init__(self, *, database_path: str | Path | None = None, notifier: Notifier | None = None) -> None:
        self.database = Database(database_path)
        self.manager = DownloadManager(self.database, notifier)
        self._analyses: dict[str, dict[str, Any]] = {}
        self._analysis_lock = threading.Lock()
        self._window: Any = None
        self._pywebview: Any = None
        self._closing_allowed = False
        self.tray_available = False

    def attach_window(self, window: Any, pywebview: Any) -> None:
        self._window = window
        self._pywebview = pywebview

    def get_app_status(self) -> dict[str, Any]:
        return {
            "desktop": True,
            "download_engine_ready": True,
            "ffmpeg_ready": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
            "message": "Motor yt-dlp conectado. Solo se usan enlaces accesibles sin iniciar sesión.",
            "tray_available": self.tray_available,
        }

    def analyze_url(self, url: str) -> dict[str, Any]:
        try:
            analysis = analyze_url(url)
        except UserFacingError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            logger.exception("Error inesperado al analizar una URL")
            return {"ok": False, "error": "No se pudo analizar el enlace. Consulta el registro local para más detalles."}
        analysis_id = str(uuid.uuid4())
        with self._analysis_lock:
            self._analyses[analysis_id] = analysis
            if len(self._analyses) > 20:
                self._analyses.pop(next(iter(self._analyses)))
        return {"ok": True, "analysis_id": analysis_id, **analysis}

    def enqueue_batch(
        self,
        analysis_id: str,
        selected_ids: list[str],
        output_format: str,
        quality: str = "auto",
        destination: str | None = None,
    ) -> dict[str, Any]:
        with self._analysis_lock:
            analysis = self._analyses.get(analysis_id)
        if not analysis:
            return {"ok": False, "error": "El análisis ha caducado. Analiza el enlace de nuevo."}
        try:
            result = self.manager.enqueue(analysis, selected_ids, output_format, quality, destination)
        except (ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            logger.exception("Error inesperado al crear un lote")
            return {"ok": False, "error": "No se pudo crear el lote. Consulta el registro local para más detalles."}
        return {"ok": True, **result}

    def get_preview(
        self,
        analysis_id: str,
        item_id: str,
        output_format: str = "video",
        quality: str = "auto",
    ) -> dict[str, Any]:
        with self._analysis_lock:
            analysis = self._analyses.get(analysis_id)
        if not analysis:
            return {"ok": False, "error": "El análisis ha caducado. Analiza el enlace de nuevo."}
        item = next((entry for entry in analysis["items"] if entry.get("id") == item_id), None)
        if not item or not item.get("source_url"):
            return {"ok": False, "error": "No se pudo localizar el elemento para la vista previa."}
        try:
            return {"ok": True, **get_preview(item["source_url"], output_format, quality)}
        except UserFacingError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            logger.exception("Error inesperado al crear una vista previa")
            return {"ok": False, "error": "No se pudo crear la vista previa."}

    def get_queue_state(self) -> dict[str, Any]:
        return self.manager.get_state()

    def get_preferences(self) -> dict[str, Any]:
        return self.database.get_preferences()

    def set_preferences(self, values: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"ok": True, "preferences": self.manager.set_preferences(values)}
        except (ValueError, OSError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    def choose_destination(self) -> dict[str, Any]:
        if self._window is None or self._pywebview is None:
            return {"ok": False, "error": "El selector de carpetas solo está disponible en la app de escritorio."}
        try:
            current = self.database.get_preference("destination", str(Path.home() / "Downloads" / "Clipoteca"))
            file_dialog = getattr(self._pywebview, "FileDialog", None)
            folder_dialog = file_dialog.FOLDER if file_dialog else self._pywebview.FOLDER_DIALOG
            selected = self._window.create_file_dialog(
                folder_dialog,
                directory=current,
                allow_multiple=False,
            )
            if not selected:
                return {"ok": False, "cancelled": True}
            preferences = self.manager.set_preferences({"destination": selected[0]})
            return {"ok": True, "destination": preferences["destination"]}
        except Exception:
            logger.exception("Error al abrir el selector de carpetas")
            return {"ok": False, "error": "No se pudo abrir el selector de carpetas."}

    def pause_all(self) -> dict[str, bool]:
        self.manager.pause_all()
        return {"ok": True}

    def resume_all(self) -> dict[str, bool]:
        self.manager.resume_all()
        return {"ok": True}

    def cancel_item(self, item_id: str) -> dict[str, bool]:
        self.manager.cancel_item(item_id)
        return {"ok": True}

    def cancel_all(self) -> dict[str, bool]:
        self.manager.cancel_all(wait=False)
        return {"ok": True}

    def retry_item(self, item_id: str) -> dict[str, Any]:
        try:
            self.manager.retry_item(item_id)
            return {"ok": True}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    def clear_history(self) -> dict[str, Any]:
        return {"ok": True, "removed": self.manager.clear_history()}

    def open_history_file(self, item_id: str, index: int = 0) -> dict[str, Any]:
        try:
            path = self.manager.get_history_path(item_id, index)
            if not path.is_file():
                return {"ok": False, "error": "El archivo ya no existe en la ruta guardada."}
            start_file = getattr(os, "startfile", None)
            if start_file is None:
                return {"ok": False, "error": "Abrir archivos desde el historial solo está disponible en Windows."}
            start_file(str(path))
            return {"ok": True}
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def request_close(self) -> dict[str, bool]:
        if not self._window:
            return {"ok": False}
        if self.manager.has_pending_or_running():
            self._window.show()
            self._dispatch_close_request()
        else:
            self.exit_app()
        return {"ok": True}

    def continue_in_background(self) -> dict[str, bool]:
        if not self._window:
            return {"ok": False}
        self._window.hide()
        return {"ok": True}

    def pause_and_close(self) -> dict[str, bool]:
        if not self._window:
            return {"ok": False}
        self.manager.pause_all(wait=True)
        self.exit_app()
        return {"ok": True}

    def exit_app(self) -> dict[str, bool]:
        if not self._window:
            return {"ok": False}
        self._closing_allowed = True
        self._window.destroy()
        return {"ok": True}

    def can_close(self) -> bool:
        return self._closing_allowed or not self.manager.has_pending_or_running()

    def show_window(self) -> None:
        if self._window:
            self._window.show()
            self._window.restore()

    def shutdown(self) -> None:
        self.manager.shutdown(pause_active=True)
        self.database.close()

    def _dispatch_close_request(self) -> None:
        if not self._window:
            return
        try:
            self._window.evaluate_js(
                "window.dispatchEvent(new CustomEvent('clipoteca:close-request'))"
            )
        except Exception:
            logger.exception("No se pudo mostrar la confirmación de cierre")

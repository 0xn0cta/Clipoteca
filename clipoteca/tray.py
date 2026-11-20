from __future__ import annotations

import ctypes
import logging
import threading
from typing import Any

from PIL import Image, ImageDraw


logger = logging.getLogger("clipoteca.tray")


def show_windows_notification(title: str, message: str) -> None:
    try:
        from winotify import Notification

        Notification(app_id="Clipoteca", title=title, msg=message).show()
    except Exception:
        logger.exception("No se pudo mostrar la notificación de Windows")


class WindowsTray:
    def __init__(self, api: Any) -> None:
        import pystray

        self.api = api
        self._pystray = pystray
        self.icon = pystray.Icon(
            "Clipoteca",
            self._make_icon(),
            "Clipoteca",
            menu=pystray.Menu(
                pystray.MenuItem("Abrir Clipoteca", self._open, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Pausar todas las descargas", self._pause),
                pystray.MenuItem("Reanudar descargas", self._resume),
                pystray.MenuItem("Cancelar descargas…", self._cancel),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir…", self._exit),
            ),
        )
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.icon.run, name="clipoteca-tray", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:
            logger.exception("No se pudo cerrar el icono de bandeja")

    def _open(self, _icon: Any, _item: Any) -> None:
        self.api.show_window()

    def _pause(self, _icon: Any, _item: Any) -> None:
        self.api.pause_all()

    def _resume(self, _icon: Any, _item: Any) -> None:
        self.api.resume_all()

    def _cancel(self, _icon: Any, _item: Any) -> None:
        if self._confirm("¿Cancelar las descargas activas y pendientes?", "Cancelar descargas"):
            self.api.cancel_all()

    def _exit(self, _icon: Any, _item: Any) -> None:
        self.api.request_close()

    @staticmethod
    def _confirm(message: str, title: str) -> bool:
        try:
            result = ctypes.windll.user32.MessageBoxW(None, message, title, 0x00000004 | 0x00000030)
            return result == 6
        except Exception:
            logger.exception("No se pudo mostrar una confirmación del sistema")
            return False

    @staticmethod
    def _make_icon() -> Image.Image:
        scale = 4
        image = Image.new("RGBA", (64 * scale, 64 * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        iris = (183, 166, 227, 255)
        ivory = (240, 238, 233, 255)

        # The C-shaped collection frame and index tab mirror the app wordmark.
        draw.arc((7 * scale, 7 * scale, 57 * scale, 57 * scale), start=45, end=315, fill=iris, width=4 * scale)
        draw.line((31 * scale, 8 * scale, 42 * scale, 8 * scale), fill=iris, width=4 * scale)
        draw.line((31 * scale, 56 * scale, 42 * scale, 56 * scale), fill=iris, width=4 * scale)
        draw.line(
            (
                (30 * scale, 21 * scale),
                (47 * scale, 21 * scale),
                (47 * scale, 43 * scale),
                (30 * scale, 43 * scale),
            ),
            fill=ivory,
            width=3 * scale,
            joint="curve",
        )
        draw.line((36 * scale, 21 * scale, 36 * scale, 28 * scale), fill=iris, width=3 * scale)
        return image.resize((64, 64), Image.Resampling.LANCZOS)

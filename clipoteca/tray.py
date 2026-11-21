from __future__ import annotations

import ctypes
import base64
import json
import logging
import os
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .storage import app_data_dir


logger = logging.getLogger("clipoteca.tray")
_icon_lock = threading.Lock()
_TOAST_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::In.ReadToEnd()))
$data = ConvertFrom-Json -InputObject $json
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast duration="short"><visual><binding template="ToastGeneric"><image placement="appLogoOverride"/><text/><text/></binding></visual><audio silent="true"/></toast>')
$xml.SelectSingleNode('//image').SetAttribute('src', [string]$data.icon)
$xml.SelectSingleNode('//text[1]').InnerText = [string]$data.title
$xml.SelectSingleNode('//text[2]').InnerText = [string]$data.message
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$toast.Group = 'Clipoteca'
$toast.Tag = [string]$data.tag
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Clipoteca').Show($toast)
"""
_ENCODED_TOAST_SCRIPT = base64.b64encode(_TOAST_SCRIPT.encode("utf-16-le")).decode("ascii")


def _notification_icon() -> Path:
    path = app_data_dir() / "notifications" / "clipoteca.png"
    with _icon_lock:
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            WindowsTray._make_icon().save(path, format="PNG")
    return path


def show_windows_notification(title: str, message: str) -> None:
    try:
        data = {
            "title": title,
            "message": message,
            "icon": _notification_icon().resolve().as_uri(),
            "tag": uuid.uuid4().hex[:16],
        }
        # Deliver metadata as data through stdin. The PowerShell program is static.
        payload = base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-EncodedCommand", _ENCODED_TOAST_SCRIPT],
            input=payload,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=True,
            timeout=8,
        )
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

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
from logging.handlers import RotatingFileHandler


ROOT = Path(__file__).resolve().parent
FRONTEND_URL = "http://127.0.0.1:5173"
BUILT_FRONTEND = ROOT / "frontend" / "dist" / "index.html"


def configure_logging() -> None:
    from clipoteca.storage import app_data_dir

    logs = app_data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        logs / "clipoteca.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[handler],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicia Clipoteca para escritorio.")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Abre la interfaz servida por Vite en 127.0.0.1:5173.",
    )
    args = parser.parse_args()

    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "Falta pywebview. Instala las dependencias con: pip install -r requirements.txt"
        ) from exc

    configure_logging()
    from clipoteca.api import DesktopApi
    from clipoteca.tray import WindowsTray, show_windows_notification

    api = DesktopApi(notifier=show_windows_notification)

    if args.dev:
        url = FRONTEND_URL
    else:
        if not BUILT_FRONTEND.is_file():
            raise SystemExit(
                "No existe frontend/dist/index.html. "
                "Ejecuta 'npm run build' dentro de la carpeta frontend."
            )
        url = BUILT_FRONTEND.as_uri()

    window = webview.create_window(
        "Clipoteca",
        url=url,
        js_api=api,
        width=1440,
        height=920,
        min_size=(960, 680),
        background_color="#131621",
    )
    api.attach_window(window, webview)

    def on_closing(*_args: object) -> bool:
        if api.can_close():
            return True
        api.request_close()
        return False

    window.events.closing += on_closing

    tray = None
    if sys.platform == "win32":
        try:
            tray = WindowsTray(api)
            tray.start()
            api.tray_available = True
        except Exception:
            api.tray_available = False
            logging.getLogger("clipoteca").exception("No se pudo iniciar la bandeja de Windows")

    try:
        webview.start(debug=args.dev)
    finally:
        if tray:
            tray.stop()
        api.shutdown()


if __name__ == "__main__":
    main()

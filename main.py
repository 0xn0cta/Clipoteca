from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND_URL = "http://127.0.0.1:5173"
BUILT_FRONTEND = ROOT / "frontend" / "dist" / "index.html"


class DesktopApi:
    """Small, explicit bridge reserved for desktop-only capabilities."""

    def get_app_status(self) -> dict[str, str | bool]:
        return {
            "desktop": True,
            "download_engine_ready": False,
            "message": "El motor de descarga todavía no está conectado.",
        }


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

    if args.dev:
        url = FRONTEND_URL
    else:
        if not BUILT_FRONTEND.is_file():
            raise SystemExit(
                "No existe frontend/dist/index.html. "
                "Ejecuta 'npm run build' dentro de la carpeta frontend."
            )
        url = BUILT_FRONTEND.as_uri()

    webview.create_window(
        "Clipoteca",
        url=url,
        js_api=DesktopApi(),
        width=1440,
        height=920,
        min_size=(960, 680),
        background_color="#111613",
    )
    webview.start(debug=args.dev)


if __name__ == "__main__":
    main()

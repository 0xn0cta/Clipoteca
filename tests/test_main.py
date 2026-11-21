from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import main


def test_main_refreshes_missing_entries_from_persisted_windows_user_path() -> None:
    registry = MagicMock()
    registry.HKEY_CURRENT_USER = object()
    registry.OpenKey.return_value.__enter__.return_value = object()
    registry.QueryValueEx.return_value = (
        r"C:\Users\Test\Programs\FFmpeg\bin;C:\Tools",
        2,
    )

    with (
        patch("main.sys.platform", "win32"),
        patch.dict(os.environ, {"PATH": r"C:\Windows\System32;c:\tools"}),
        patch.dict(sys.modules, {"winreg": registry}),
    ):
        main.refresh_windows_user_path()
        result = os.environ["PATH"]

    assert result == r"C:\Users\Test\Programs\FFmpeg\bin;C:\Windows\System32;c:\tools"


def test_main_ignores_missing_windows_user_registry_path() -> None:
    registry = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        OpenKey=MagicMock(side_effect=OSError("registry unavailable")),
    )

    with (
        patch("main.sys.platform", "win32"),
        patch.dict(os.environ, {"PATH": r"C:\Windows\System32"}),
        patch.dict(sys.modules, {"winreg": registry}),
    ):
        main.refresh_windows_user_path()
        result = os.environ["PATH"]

    assert result == r"C:\Windows\System32"


def test_main_uses_pywebview_http_server_for_built_frontend() -> None:
    api = MagicMock()
    window = SimpleNamespace(events=SimpleNamespace(closing=MagicMock()))
    tray = MagicMock()
    webview = SimpleNamespace(
        create_window=MagicMock(return_value=window),
        start=MagicMock(),
    )
    frontend_path = Path(__file__).resolve()

    with (
        patch("main.sys.platform", "win32"),
        patch("main.sys.argv", ["main.py"]),
        patch("main.BUILT_FRONTEND", frontend_path),
        patch("main.configure_logging"),
        patch("clipoteca.api.DesktopApi", return_value=api),
        patch("clipoteca.tray.WindowsTray", return_value=tray),
        patch.dict(sys.modules, {"webview": webview}),
    ):
        main.main()

    assert webview.create_window.call_args.kwargs["url"] == str(frontend_path)
    webview.start.assert_called_once_with(debug=False, http_server=True)

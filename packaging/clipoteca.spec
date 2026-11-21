# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


root = Path(SPECPATH).parent
frontend = root / "frontend" / "dist"
if not (frontend / "index.html").is_file():
    raise SystemExit("Falta la interfaz compilada. Ejecuta packaging/build.ps1.")

# yt-dlp loads its extractors dynamically. Keep the same engine in both launchers.
engine_data = collect_data_files("yt_dlp")
engine_imports = collect_submodules("yt_dlp")

desktop = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    datas=[(str(frontend), "frontend/dist"), *engine_data, *collect_data_files("webview")],
    hiddenimports=[*engine_imports, "pystray._win32", "webview.platforms.winforms", "webview.platforms.edgechromium"],
)
desktop_exe = EXE(PYZ(desktop.pure), desktop.scripts, [], exclude_binaries=True, name="Clipoteca", console=False, upx=False)
desktop_bundle = COLLECT(desktop_exe, desktop.binaries, desktop.datas, name="Clipoteca", upx=False)

cli = Analysis(
    [str(root / "packaging" / "cli_entry.py")],
    pathex=[str(root)],
    datas=engine_data,
    hiddenimports=engine_imports,
)
cli_exe = EXE(PYZ(cli.pure), cli.scripts, [], exclude_binaries=True, name="clipoteca-cli", console=True, upx=False)
cli_bundle = COLLECT(cli_exe, cli.binaries, cli.datas, name="clipoteca-cli", upx=False)

# Build e instalación de Clipoteca en Windows

El repositorio distribuye la fuente y los scripts de build. Para crear los ejecutables portables:

```powershell
cd "RUTA_CLIPOTECA"
python -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r packaging/requirements-build.txt
.\packaging\build.ps1 -Python .\.venv-build\Scripts\python.exe
```

El script compila el frontend y genera:

- `dist\windows\Clipoteca\Clipoteca.exe` — aplicación gráfica.
- `dist\windows\clipoteca-cli\clipoteca-cli.exe` — CLI independiente.

Conserva cada carpeta completa al copiar o compartir los ejecutables; las DLL y recursos de `_internal` son necesarios. Para instalar la app gráfica para el usuario actual y crear accesos directos:

```powershell
.\packaging\install.ps1
```

La app queda en `%LOCALAPPDATA%\Programs\Clipoteca\Clipoteca.exe`. También aparece en Inicio y en el Escritorio. Para desinstalar la app y los accesos directos sin borrar preferencias, cola, logs ni medios descargados:

```powershell
.\packaging\uninstall.ps1
```

## Requisitos externos y límites de esta build

- Windows x64, Python 3.11+ para compilar, Node.js/npm y Microsoft Edge WebView2 Runtime.
- FFmpeg y FFprobe deben estar en `PATH` para MP3 y para unir o convertir algunas pistas. No se incluyen: la revisión de licencia/distribución todavía está pendiente.
- Los datos se guardan en `%LOCALAPPDATA%\Clipoteca`; las descargas van a la carpeta local elegida.

Este es un build portable de desarrollo, no un instalador firmado ni un release de producción. Comprueba que la build completa se ejecuta en Windows; la descarga manual requiere material propio o autorizado.

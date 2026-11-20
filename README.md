# Clipoteca

Aplicación de escritorio para Windows para preparar y gestionar descargas autorizadas de videos y playlists. El proyecto prioriza la revisión de playlists y el estado de cada elemento.

> **Estado actual:** primera entrega visual. La interfaz funciona con datos de demostración; el análisis real con `yt-dlp` y las descargas todavía no están conectados. No se inicia ninguna descarga desde esta versión.

![Vista de escritorio de Clipoteca](docs/screenshots/clipoteca-desktop.png)

## Stack

- Python + [pywebview](https://pywebview.flowrl.com/) como ventana de escritorio.
- React + TypeScript + Vite para la interfaz local.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) previsto como motor de descarga.
- FFmpeg previsto para unir pistas y convertir audio a MP3. Su distribución y avisos de licencia deben revisarse antes de empaquetar.
- La interfaz usa WebView2 en Windows.

## Requisitos de desarrollo

- Windows.
- Python 3.11 o superior.
- Node.js y npm.
- Microsoft Edge WebView2 Runtime para ejecutar la ventana de escritorio.

## Ejecutar la interfaz en el navegador

```powershell
cd frontend
npm install
npm run dev
```

Vite mostrará la dirección local de desarrollo. En esta modalidad, la interfaz es una previsualización y no descarga contenido.

## Ejecutar en la ventana de escritorio

Desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python main.py
```

Para desarrollo con Vite Hot Module Replacement, ejecuta `npm run dev` dentro de `frontend` en una terminal y, desde otra terminal en la raíz:

```powershell
python main.py --dev
```

## Qué incluye esta primera entrega

- Interfaz oscura en español con dirección de diseño **Archivo personal premium**.
- Preparación de lote con muestra de playlist claramente marcada como ficticia.
- Selección de elementos disponibles, selección global, formato, calidad y destino en modo demostración.
- Vista inicial de cola vacía.
- Controles etiquetados y adaptaciones para ventanas más estrechas.
- La acción de inicio permanece deshabilitada hasta que exista un motor de descarga real.

## Siguiente implementación

La ruta completa, dependencias, criterios de aceptación y verificaciones están en:

- [`AGENTS.md`](AGENTS.md): reglas para agentes colaboradores.
- [`docs/IMPLEMENTATION_SPEC.md`](docs/IMPLEMENTATION_SPEC.md): flujos, contrato Python–React, estados, errores y límites.
- [`tasks/plan.md`](tasks/plan.md): fases y checkpoints.
- [`tasks/todo.md`](tasks/todo.md): tareas ejecutables `T01`–`T27`.

El colaborador debe empezar en `T01`, trabajar una tarea por vez y mantener actualizadas sus casillas solo después de verificarla.

## Alcance responsable

Clipoteca se diseña para contenido que el usuario posee o está autorizado a descargar. No contempla eludir DRM, controles de acceso ni autenticación. El usuario debe respetar los derechos de autor y las condiciones aplicables de las plataformas.

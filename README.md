# Clipoteca

Aplicación de escritorio para Windows para preparar y gestionar descargas autorizadas de videos y playlists. El proyecto prioriza la revisión de playlists y el estado de cada elemento.

> **Estado actual:** primera integración funcional en desarrollo. El análisis y la cola usan `yt-dlp`; queda validar el flujo de descarga en Windows con enlaces de prueba autorizados y completar pruebas de bandeja/notificaciones.

![Vista de escritorio de Clipoteca](docs/screenshots/clipoteca-desktop.png)

La primera propuesta de logo vectorial está en [`docs/brand/`](docs/brand/).

## Stack

- Python + [pywebview](https://pywebview.flowrl.com/) como ventana de escritorio.
- React + TypeScript + Vite para la interfaz local.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) como motor de análisis y descarga.
- FFmpeg para unir pistas y convertir audio a MP3. Debe estar instalado y accesible en `PATH`; su distribución y avisos de licencia deben revisarse antes de empaquetar.
- SQLite local para conservar la cola, los resultados y las preferencias.
- Icono de bandeja, controles en segundo plano y notificaciones de Windows.
- La interfaz usa WebView2 en Windows.

## Requisitos de desarrollo

- Windows.
- Python 3.11 o superior.
- Node.js y npm.
- Microsoft Edge WebView2 Runtime para ejecutar la ventana de escritorio.
- FFmpeg instalado en Windows para combinar pistas de vídeo o convertir audio a MP3.

## Ejecutar la interfaz en el navegador

```powershell
cd frontend
npm install
npm run dev
```

Vite mostrará la dirección local de desarrollo. En esta modalidad se previsualiza la interfaz, pero no está disponible el puente Python ni se descargan contenidos.

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

## Automatizar desde consola

Con el entorno Python del proyecto activo, consulta los comandos disponibles:

```powershell
python -m clipoteca.cli --help
python -m clipoteca.cli --json status
```

La CLI comparte la cola y las preferencias locales con la aplicación. `download` permite ejecutar en segundo plano con `--wait`; para una playlist hay que indicar `--all` o seleccionar elementos con `--item`. Sin `--wait`, el lote se añade a la cola persistente para que lo procese Clipoteca abierta o un worker activo. La guía completa está en [`docs/CLI.md`](docs/CLI.md). El ejecutable de consola independiente todavía no se incluye en un instalador.

## Funcionalidades implementadas en esta fase

- Interfaz oscura en español con dirección de diseño **Archivo personal premium**.
- Análisis de URLs de YouTube y selección de elementos antes de descargarlos.
- Previsualización de la selección con miniatura y reproducción de audio/vídeo cuando la fuente lo permite; la reproducción no guarda un archivo.
- Descarga de vídeo MP4, audio MP3 o ambos; FFmpeg es necesario para unir pistas y convertir audio.
- Cola persistente con progreso por elemento, pausa, reanudación, cancelación y hasta tres reintentos automáticos ante errores temporales.
- Historial separado; limpiar el historial borra los registros de Clipoteca, no los archivos.
- Apertura de los archivos finalizados desde el historial con la aplicación predeterminada de Windows.
- Carpeta predeterminada `Descargas\Clipoteca`, recordada y modificable; las playlists crean una subcarpeta.
- En el primer inicio se elige y recuerda la concurrencia: automática con techo del usuario o manual sin máximo impuesto por Clipoteca.
- Icono en los iconos ocultos de Windows para abrir, pausar/reanudar, cancelar o salir; las descargas pueden seguir en segundo plano.
- Mensajes de estado en la app y registro técnico local.
- Logo vectorial C-marco con pestaña de índice; primera propuesta en revisión en `docs/brand/`.

El análisis y la descarga no importan cookies o credenciales. El MVP acepta enlaces accesibles de YouTube sin iniciar sesión; no intenta sortear restricciones.

## Colaboración y tareas

La guía completa para continuar el trabajo está en:

- [`AGENTS.md`](AGENTS.md): reglas del colaborador.
- [`docs/IMPLEMENTATION_SPEC.md`](docs/IMPLEMENTATION_SPEC.md): comportamiento, arquitectura, seguridad y flujos.
- [`tasks/plan.md`](tasks/plan.md) y [`tasks/todo.md`](tasks/todo.md): fases y tareas ejecutables.

Trabajar una tarea `Txx` por vez y marcarla solo tras verificarla.

## Validación ejecutada en esta fase

```powershell
python -m unittest discover -s tests -v
cd frontend
npm run build
npm run lint
```

La suite usa yt-dlp simulado y no descarga contenido real. La descarga, reanudación, selector nativo, WebView2 y bandeja todavía requieren un smoke test manual en Windows con enlaces propios o autorizados. Los logs se guardan en `%LOCALAPPDATA%\Clipoteca\logs` y la base de datos en `%LOCALAPPDATA%\Clipoteca`.

## Alcance responsable

Clipoteca se diseña para contenido que el usuario posee o está autorizado a descargar. No contempla eludir DRM, controles de acceso ni autenticación. El usuario debe respetar los derechos de autor y las condiciones aplicables de las plataformas.

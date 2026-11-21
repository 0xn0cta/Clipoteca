# CLI de Clipoteca

Clipoteca ofrece una interfaz local de consola para automatizar procesos. Durante el desarrollo se puede invocar así:

```powershell
python -m clipoteca.cli --help
python -m clipoteca --version
```

La CLI es independiente del lanzador gráfico y reutiliza los servicios locales, las preferencias y la cola SQLite. Admite vídeos y playlists de YouTube, Reels y publicaciones con un solo vídeo de Instagram y publicaciones de vídeo de Reddit accesibles sin iniciar sesión.

## Comandos

| Comando | Función |
|---|---|
| `status` | Muestra el estado del motor local y FFmpeg. |
| `analyze URL` | Analiza un video o playlist sin descargar. |
| `preview URL` | Obtiene metadatos y un flujo de vista previa sin guardar un archivo. |
| `download URL [--item ID] [--all] [--wait]` | Encola o descarga contenido autorizado con las opciones elegidas. |
| `queue list/pause/resume/cancel/retry` | Consulta y gestiona la cola persistente. |
| `history list/open/clear` | Consulta resultados y gestiona los registros del historial local. |
| `settings show/set` | Consulta o cambia destino y concurrencia locales. |

Implementado en T28–T33: `--help`, `--version`, `status`, `analyze`, `preview`, `download`, acciones de cola e historial, y preferencias. `status` comprueba yt-dlp y FFmpeg en el `PATH` del proceso; después de cambiarlo, abre una terminal nueva. `analyze` y `preview` usan yt-dlp sin descargar ni escribir archivos. Si hay un flujo reproducible, `preview` incluye su URL temporal en la respuesta.

```powershell
python -m clipoteca.cli status
python -m clipoteca.cli --json status
python -m clipoteca.cli analyze "https://www.youtube.com/watch?v=..."
python -m clipoteca.cli preview "https://www.youtube.com/watch?v=..." --format video --quality auto --json
python -m clipoteca.cli download "https://www.youtube.com/watch?v=..." --wait --json
python -m clipoteca.cli download "https://www.youtube.com/playlist?list=..." --all --format both --wait --json
python -m clipoteca.cli queue list --json
python -m clipoteca.cli queue pause --wait
python -m clipoteca.cli queue cancel --all --yes
python -m clipoteca.cli history list --json
python -m clipoteca.cli history clear --yes
python -m clipoteca.cli settings show --json
python -m clipoteca.cli settings set --concurrency-mode manual --manual-concurrency 10
python -m clipoteca.cli settings set --theme-mode system
```

Usa solo videos o playlists que posees o tienes autorización para guardar. Para una playlist, `download` requiere `--all` o uno o más `--item ID` (los ID se obtienen con `analyze --json`). `--destination` actualiza la preferencia local de destino. Sin `--wait`, solo se encola; la app o un worker abierto puede procesarla y, si no hay ninguno, permanece en la cola persistente. Con `--wait`, descarga en modo headless, envía el progreso a stderr y devuelve un resumen final con las rutas de salida. Los eventos JSON de progreso se emiten como JSON Lines en stderr. Si falla un lote, la CLI devuelve un código de salida distinto de cero y adjunta el resumen al error JSON.

`queue resume` y `queue retry` admiten `--wait` para ejecutarse en modo headless hasta que termine el trabajo afectado. La cancelación global y el borrado del historial requieren `--yes`; cancelar o limpiar registros nunca borra los medios ya descargados. `history open` usa la aplicación predeterminada de Windows.

La configuración inicial de concurrencia requiere un modo y un valor positivo explícitos; el modo manual no tiene máximo impuesto por la app. `theme_mode` acepta `system`, `dark` o `light`; la integración visual de esos valores llega en T37. El ejecutable de consola empaquetado está pendiente de T34.

## Salida y códigos de salida

La salida es texto por defecto. Añade `--json` antes o después del comando para obtener una respuesta legible por máquina. JSON usa UTF-8 y un sobre versionado:

```json
{
  "schema_version": 1,
  "ok": true,
  "command": "status",
  "data": {
    "mode": "cli",
    "download_engine_ready": true,
    "ffmpeg_ready": true
  }
}
```

Los errores se escriben en stderr y los resultados correctos en stdout. El progreso de operaciones largas no se mezcla con el resultado JSON.

| Código | Significado |
|---:|---|
| `0` | El comando terminó correctamente o se mostró la ayuda/versión. |
| `2` | Línea de comandos o argumentos no válidos. |
| `3` | Falló la operación. |
| `4` | Función no disponible o aún no implementada. |
| `130` | Interrumpido con Ctrl+C; el trabajo activo se pausó. |

El ejecutable independiente `clipoteca-cli.exe` está pendiente de T34 y del empaquetado Windows. Hasta entonces, usa `python -m clipoteca.cli` desde el entorno del proyecto. Analizar o previsualizar una URL nunca inicia una descarga por sí solo.

# Plan de implementación: Clipoteca MVP

## Objetivo

Convertir el prototipo visual de Clipoteca en una app Windows funcional para analizar videos/playlists de YouTube, preparar formatos y destinos, descargar en una cola recuperable y empaquetar una build revisable.

## Estado de partida: entrega del colaborador `b4cba94`

Ya existen `clipoteca/api.py`, `engine.py`, `manager.py`, `storage.py` y `tray.py`, además de análisis, preview best-effort, descargas, cola persistente, historial y controles de bandeja. En esta integración comprobamos 22 tests Python, `npm run build` y `npm run lint`; eso no equivale a un smoke real de Windows/YouTube.

Correcciones añadidas en esta integración: YouTube como único host permitido, selección de concurrencia en el primer inicio (con migración de defaults automáticos anteriores), rutas sin editar desde el puente, nombres reservados de Windows, MP4 sin recodificación silenciosa y marca C-archivo en app/favicon/bandeja. El logo sigue siendo una propuesta en revisión.

Las casillas siguientes no se marcan solo porque haya código equivalente: deben cumplir todos los criterios de aceptación y verificarse. Revisar primero los módulos existentes antes de crear duplicados. Aún no hay tests automatizados React, CI ni smoke manual de WebView2/FFmpeg/bandeja.

## Arquitectura y decisiones

- Renderer local: React + TypeScript + Vite; escritorio: pywebview; backend: Python.
- Analizar/descargar con la API Python de yt-dlp; no shell command strings ni scraping propio.
- FFmpeg para merge/remux y MP3, incluido en el instalador después de comprobar licencia/avisos.
- Puente React–Python explícito y tipado. Procesos de red/descarga fuera del hilo visual.
- Preferencias en `%LOCALAPPDATA%/Clipoteca/settings.json`; destino inicial `Descargas/Clipoteca`.
- Preguntar una sola vez por la concurrencia en el primer inicio y guardar la elección. Sin máximo impuesto; advertencia no bloqueante desde 5 como propuesta inicial.
- Playlist: seleccionar todos los disponibles, conservar orden, continuar ante fallos de un elemento, omitir duplicados sin sobrescribir.
- Solo contenido que el usuario posee o está autorizado a guardar. Sin cookies, login, DRM bypass ni telemetría.

## Grafo de dependencias

```text
T01 test harness ── T02 CI
       │
       ├── T03 modelos/errores ── T04 puente ── T05 preferencias
       │                              │
       │                              └── T06 validación URL ── T07 análisis yt-dlp
       │                                                        └── T08 API análisis
       │                                                            └── T09 UI análisis
       │                                                                └── T10 selección
       │                                                                    └── T11 opciones
       │                                                                        └── T12 carpeta
       │                                                                            └── T13 rutas/duplicados
       │                                                                                └── T14 MP4
       │                                                                                    └── T15 MP3/ambos + FFmpeg
       │                                                                                        └── T16 cola/concurrencia
       │                                                                                            └── T17 progreso
       │                                                                                                └── T18 playlist
       │                                                                                                    └── T19 cancelar/reintentar
       │                                                                                                        └── T20 recuperación
       └──────────────────────────────────────────────────────────────────────────────────────────────────── T21–T27 release
```

La lista ejecutable, con criterios, verificaciones y archivos previstos, está en `tasks/todo.md`.

## Fases y checkpoints

### Fase 1 — Base de ingeniería (T01–T05)

Pruebas, CI, modelos/errores, contrato del puente y preferencias iniciales.

**Checkpoint 1:** build/lint/tests pasan; el puente funciona con respuestas simuladas; la preferencia de concurrencia se puede elegir y guardar.

### Fase 2 — Análisis y selección (T06–T10)

Validar URL, extraer metadatos sin descarga, conectar la interfaz y aplicar reglas de selección.

**Checkpoint 2:** un video y una playlist aparecen desde una respuesta yt-dlp simulada; entradas no disponibles se entienden y no se seleccionan.

### Fase 3 — Opciones y primera descarga real (T11–T15)

Formatos/calidad, destino, nombres seguros, duplicados y slices verticales MP4 y MP3/ambos.

**Checkpoint 3:** una descarga individual llega a un archivo correcto, con progreso, cancelación básica y errores visibles.

### Fase 4 — Cola robusta (T16–T20)

Concurrencia elegida, eventos de progreso, batch de playlist, recuperación/reintentos y persistencia local.

**Checkpoint 4:** playlist con mezcla de éxito/fallo termina sin perder elementos; reiniciar no deja tareas en estado falso de “descargando”.

### Fase 5 — Calidad y entrega Windows (T21–T27)

Mapeo de errores, privacidad, FFmpeg/licencias, build congelada, instalador, accesibilidad y documentación.

**Checkpoint final:** pruebas automatizadas verdes, smoke test Windows informado, instalador validado o bloqueos declarados y paquete listo para revisión del propietario.

## Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Cambios de YouTube rompen extracción | Alto | Mantener yt-dlp actualizado; errores claros y pruebas mock estables. |
| Concurrencia sin máximo | Alto | Pedir valor al primer inicio, advertir desde 5 (propuesta), no bloquear, continuar por tarea y backoff finito. |
| FFmpeg redistribuido sin cumplimiento | Alto | Auditar build, licencia, avisos y versión antes del instalador. |
| App UI bloqueada durante red | Alto | Servicios en workers; progreso por eventos; no usar operación bloqueante en hilo UI. |
| Path inválido/duplicado en Windows | Medio | Sanitización, ID en nombre, subcarpeta y skip explícito. |
| WebView2 no presente en otro equipo | Medio | Detectar requisito y dar instalación/bootstrapper documentado. |
| Live test sin autorización | Medio | CI completamente mockeada; smoke manual solo con URL/material autorizado. |

## Decisiones diferidas

- Retención de tareas completadas/historial permanente. En el MVP se persiste lo necesario para recuperar trabajos pendientes/interrumpidos; no se crea una biblioteca histórica de URLs.
- Umbral exacto de advertencia de concurrencia; 5 es una propuesta no bloqueante, no un máximo.
- Procedencia concreta de los binarios FFmpeg y del instalador tras revisar licencias disponibles.
- Actualización automática de yt-dlp/app, subtítulos y soporte de otros sitios quedan fuera del MVP.

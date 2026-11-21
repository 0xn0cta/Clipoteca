# Plan de implementación: Clipoteca MVP

## Objetivo

Convertir Clipoteca en una app Windows funcional para analizar vídeos y playlists de YouTube y publicaciones de vídeo de Instagram y Reddit, preparar la salida y descargar en una cola recuperable.

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

## Fase 6 — CLI local automatizable (T28–T34)

El propietario pidió poder ejecutar desde consola las capacidades funcionales existentes, sin abrir la interfaz, para automatizar flujos. La CLI reutilizará los servicios, validaciones, preferencias y la base SQLite existentes; no expondrá una shell arbitraria ni añadirá un servidor remoto.

### Contrato propuesto

- Punto de entrada de desarrollo: `python -m clipoteca.cli`; en la distribución, un ejecutable de consola separado (`clipoteca-cli.exe`).
- Comandos para estado, análisis, preview, descarga, cola, historial y preferencias.
- Texto legible por defecto y salida JSON estable (`--json`) con códigos de salida documentados. El progreso no debe contaminar la salida JSON de resultados.
- Modo headless: las descargas pueden completarse sin abrir la GUI; Ctrl+C debe detener/reanudar según el contrato, no dejar una tarea falsamente activa.
- CLI y GUI comparten datos locales. Se requiere una única propiedad coordinada del worker; los controles enviados desde el otro proceso deben llegar al worker activo mediante señales SQLite locales o fallar claramente. La recuperación al arrancar solo la hace quien obtiene el lock.
- Compartir la lista de fuentes permitidas con la GUI, validar rutas y mantener el uso autorizado sin cookies ni credenciales. Las acciones destructivas en automatización deben ser explícitas y comprobables.

### Orden y dependencias

1. T28: contrato, esquema de salida, códigos de salida y punto de entrada.
2. T29: estado, análisis y preview sin iniciar descargas.
3. T30: propiedad única del worker y señales de control al coexistir GUI/CLI.
4. T31: descarga headless, selección de playlist y progreso.
5. T32: operaciones de cola e historial.
6. T33: lectura/cambio de preferencias para flujos no interactivos.
7. T34: pruebas end-to-end mockeadas, documentación y launcher de consola en el instalador.

**Checkpoint CLI:** se puede automatizar un flujo completo desde consola, sin GUI; JSON/códigos de salida son estables; no hay duplicación de workers al coexistir con la app; las pruebas usan yt-dlp simulado y no descargan URLs reales.

## Hardening adicional — T35

La inspección de la cola al recuperar los parciales encontró varios lotes fallidos con el mismo `source_id`, destino y nombre de salida. Con concurrencia manual alta podrían escribir simultáneamente el mismo archivo. T35 debe serializar por identidad de salida, sin reducir la concurrencia para elementos distintos.

### Riesgos adicionales

| Riesgo | Impacto | Mitigación |
|---|---|---|
| GUI y CLI ejecutan dos schedulers sobre la misma SQLite | Alto | Añadir exclusión/coordination entre procesos antes de habilitar descargas headless. |
| Cambios de salida rompen scripts de usuario | Medio | Versionar y probar el esquema JSON; documentar códigos de salida y mantenerlos estables. |
| CLI transforma una URL en una descarga masiva accidental | Alto | Selección clara de playlist, validación y resumen antes de ejecutar; ninguna URL inicia descargas por sí sola. |

## Fase 7 — Rediseño de la experiencia visual (T36–T41)

El propietario fijó una dirección nueva: una herramienta local con la familiaridad de un producto de video (sin copiar YouTube), navegación lateral, fondos carbón con matiz rojo, tipografía blanca y controles grises. El tema sigue Windows de forma predeterminada con override claro/oscuro. La lista de playlist conserva prioridad y convive con una preview lateral; las pantallas deben caber en ventanas compactas y aprovechar bien maximizado/pantalla completa.

### Orden

1. T36: persistir modo de tema compartido por GUI/CLI.
2. T37: definir tokens oscuro/claro y selector auto/manual.
3. T38: rehacer shell/sidebar y comportamiento de ventanas compactas/maximizadas.
4. T39: ordenar la preparación en lista + preview lateral y mejorar los estados de preview.
5. T40: adaptar cola, historial, ajustes y cierre/bandeja al mismo shell.
6. T41: validación visual/accesible, captura y documentación del nuevo sistema visual.

**Checkpoint visual:** el flujo real se entiende y conserva, no hay elementos falsos ni botones decorativos, el tema sistema y sus overrides funcionan, y la UI se verifica en ventana compacta, escritorio y móvil.

### Guardrails de diseño

- La inspiración de video se limita a affordances familiares (navegación, player, metadata, lista); no copiar logos, iconos, textos ni composición exacta de YouTube.
- El rojo es una identidad controlada para selección/progreso y marcadores; los botones principales son grises, los estados semánticos mantienen colores distinguibles.
- Sidebar y tema deben ser accesibles con teclado, lector de pantalla, zoom y movimiento reducido.
- El contenido queda centrado y compacto en pantallas grandes; el modo maximizado no debe estirar filas o controles hasta hacerlos ilegibles.

# Especificación de implementación — Clipoteca

## 1. Estado y objetivo

Clipoteca es una aplicación de escritorio para Windows para preparar y gestionar descargas de videos individuales y playlists autorizadas. El repositorio contiene hoy un prototipo visual; `yt-dlp` y FFmpeg todavía no están conectados. La meta del MVP es convertir ese prototipo en un flujo real, verificable y recuperable, sin perder la dirección de diseño aprobada.

**Éxito del MVP:** pegar un enlace de YouTube, inspeccionar el video o playlist sin descargarlo todavía, elegir elementos y formato, iniciar una cola, ver progreso por elemento y recuperar errores sin perder toda la playlist.

## 2. Decisiones confirmadas

| Tema | Decisión |
|---|---|
| Plataforma | Windows; la interfaz se muestra en WebView2. |
| Stack | Python + pywebview; React + TypeScript + Vite; `yt-dlp` como API Python. |
| Diseño | Español, oscuro, moderno/premium; “Private Collection Archive” según `DESIGN.md`. |
| Contenido | Videos y playlists que el usuario posee o está autorizado a guardar. |
| Formatos | Video MP4, audio MP3 o ambos. |
| Calidad | Mejor disponible por defecto, con selector de calidades disponibles. |
| Playlist | Selección por elemento; todos los disponibles seleccionados por defecto; preservar orden. |
| Destino | `Descargas/Clipoteca` por defecto, guardado como preferencia, con cambio por lote. Playlist en subcarpeta propia. |
| Duplicados | Omitir y avisar; nunca sobrescribir en silencio. |
| Concurrencia | Preguntar en el primer inicio, guardar la elección y permitir cambiarla. No imponer un máximo en la app. |
| FFmpeg | Incluirlo en el instalador; verificar distribución, licencia, versión y avisos antes de publicar. |

El usuario pidió no fijar un máximo de concurrencia. Como medida informativa —no como límite— se propone una advertencia no bloqueante desde 5 descargas simultáneas. El valor 5 es una propuesta técnica y debe aparecer claramente en la entrega para que el responsable pueda ajustarlo.

## 3. Alcance del MVP

### Incluye

- Analizar una URL de video o playlist de YouTube sin iniciar una descarga.
- Mostrar título, duración, orden y disponibilidad por elemento; no añadir miniaturas a las filas en este MVP.
- Seleccionar/deseleccionar elementos; los no disponibles aparecen deshabilitados y con motivo cuando se conozca.
- Elegir video MP4, audio MP3 o ambos.
- Ofrecer “Automática / mejor disponible” y resoluciones solo cuando existan en la fuente.
- Permitir previsualizar el elemento seleccionado con miniatura y reproducción directa cuando el formato/origen lo permita. La vista previa no escribe archivos y puede fallar por restricciones del origen.
- Usar `Descargas/Clipoteca` por defecto, recordar la carpeta seleccionada y permitir un override por lote.
- Crear una subcarpeta segura por playlist.
- Omitir duplicados y avisar sin sobrescribir.
- Cola con estados, progreso por elemento y agregado, cancelación, reintento manual y resumen de éxitos/errores.
- Continuar una playlist aunque falle un elemento; el error se representa en ese elemento.
- Reanudar archivos parciales cuando `yt-dlp` lo permita.
- Separar la cola activa del historial finalizado; permitir abrir un archivo terminado con su aplicación predeterminada y limpiar solo los registros, nunca los archivos.
- Permitir continuar en segundo plano desde la bandeja de Windows o pausar y cerrar la app cuando haya trabajo activo.
- Guardar localmente la preferencia de carpeta y concurrencia, además de lo necesario para recuperar trabajos interrumpidos.
- Mensajes en español con acción de recuperación cuando aplique.

### Fuera de alcance

- Importar cookies, iniciar sesión, sortear desafíos, eludir DRM o acceder a contenido privado/restringido.
- Descargar desde plataformas distintas de YouTube en el MVP.
- Subtítulos, transcripción, edición, conversión arbitraria de codecs o ajuste de bitrate MP3.
- Sincronización en la nube, telemetría o envío remoto del historial.
- Reescribir el diseño aprobado o añadir un modo claro sin aprobación.

## 4. Flujos de usuario y ramas

### W1 — Primer inicio

1. Validar que la UI empaquetada y el puente de escritorio se cargaron.
2. Si no existe preferencia de concurrencia, preguntar una vez cuántas descargas simultáneas quiere el usuario. No preseleccionar en silencio.
3. Guardar un entero positivo sin imponer un máximo. En 5 o más, mostrar advertencia no bloqueante; el usuario puede continuar.
4. Crear/usar `Descargas/Clipoteca` como carpeta inicial y guardar esa preferencia.
5. Si WebView2, permisos o carpeta no están disponibles, explicar el problema y ofrecer recuperación; no iniciar trabajo a medias.

### W2 — Analizar origen

1. Campo vacío → pedir enlace, no llamar a `yt-dlp`.
2. URL mal formada o dominio no soportado → error `INVALID_URL` / `UNSUPPORTED_SITE`, conservar el texto para corregir.
3. URL válida → estado `Analizando`, mantener la UI interactiva y no descargar.
4. Video → devolver una entrada.
5. Playlist → devolver entradas ordenadas; seleccionar por defecto las disponibles.
6. Playlist vacía → estado vacío con opción de corregir el enlace.
7. Video eliminado, privado, inaccesible o no disponible → informar y continuar con el resto cuando sea playlist.
8. Fallo de red/rate limit → error recuperable y acción de reintento; no convertirlo en “no disponible”.

### W3 — Preparar elementos y salida

1. Permitir seleccionar/deseleccionar entradas disponibles y mostrar el número seleccionado.
2. No permitir seleccionar entradas no disponibles.
3. Video/audio/ambos controla la salida; calidad se desactiva en audio-only.
4. Las calidades se obtienen del análisis, no de una lista inventada. La opción automática prioriza la mejor calidad compatible con el formato elegido.
5. Elegir carpeta mediante diálogo nativo de escritorio. Cancelar el diálogo conserva el destino anterior.
6. La vista previa se abre por acción explícita en el reproductor oficial embebido de YouTube (`youtube-nocookie.com`); no inicia ni sustituye una descarga local.
7. La validación muestra qué se guardará, el destino y los elementos omitidos antes de iniciar.

### W4 — Descargar video, audio o playlist

1. Confirmación explícita del usuario inicia el lote; pegar URL o analizar nunca descarga.
2. Encolar una tarea por elemento seleccionado, conservando orden y vínculo con el lote.
3. Mostrar `En cola`, `Descargando`, `Completado`, `Fallido`, `Cancelado` u `Omitido`.
4. Progreso puede ser indeterminado si la fuente no informa tamaño/ETA; nunca inventar porcentajes.
5. Error recuperable de un elemento no detiene el resto de la playlist.
6. Al final, mostrar resumen: completados, omitidos, fallidos y acciones de reintento.

### W5 — Previsualizar y revisar historial

- Cada entrada conserva su miniatura junto a la selección; pulsarla abre el reproductor oficial de YouTube dentro de Clipoteca.
- La vista previa solo se carga tras una acción explícita del usuario, no guarda archivos y no sustituye la descarga.
- Si YouTube no permite insertar el video, el reproductor muestra su aviso; Clipoteca conserva título/duración. Cuando el WebView informa un fallo de carga, la UI permite reintentar.
- No se importan cookies ni credenciales para la vista previa.
- El reproductor respeta la reproducción iniciada por el usuario y el tamaño mínimo del player/thumbnail. En escritorio, se pasa la ruta del bundle local (no una URL `file://`) a PyWebView y se activa su servidor HTTP para que el iframe reciba un `Referer`; no se falsifica un origen.
- El historial separa resultados finalizados; abrir archivo usa la aplicación predeterminada de Windows.
- Limpiar el historial elimina registros de Clipoteca, nunca archivos descargados.

### W6 — Cancelar, reintentar y recuperar

- Cancelar una tarea afecta esa tarea; cancelar un lote pregunta solo si hay trabajo activo y explica el alcance.
- Cancelar conserva el `.part` cuando sea seguro; no deja una tarea marcada como completada.
- Reintentar solo tareas fallidas/canceladas que puedan reanudarse.
- Al reabrir la app, convertir tareas que estaban descargándose a `Interrumpida`; ofrecer reanudar o descartar.
- Duplicado en disco → `Omitido`, mostrar nombre/ruta y no sobrescribir.
- Errores terminales (no disponible, permisos, disco lleno, FFmpeg ausente) no reciben reintentos automáticos.
- Al cerrar con tareas pendientes/activas, ofrecer continuar en segundo plano (si la bandeja está disponible), pausar y cerrar, o volver a la app.
- El historial solo contiene resultados; limpiar el historial no elimina archivos descargados.
- La bandeja Windows ofrece abrir, pausar/reanudar, cancelar y salir; notificaciones informan de lotes finalizados/fallidos.

## 5. Estados y datos

### Estados de análisis

`idle → validating → analyzing → ready | empty | failed`

### Estados de descarga

`pending → queued → downloading → completed | failed | cancelled | skipped | interrupted`

`failed` solo usa reintento automático si la causa es transitoria. Se recomienda un máximo de 3 reintentos automáticos con backoff para errores de red transitorios; errores de acceso, formato, disco o FFmpeg requieren acción explícita.

### Modelos conceptuales

- `AnalyzedSource`: URL normalizada, tipo (`video`/`playlist`), título, lista ordenada de entradas.
- `MediaEntry`: ID de video, título, duración opcional, orden, disponibilidad/motivo, formatos disponibles.
- `BatchRequest`: source, IDs seleccionados, formato, calidad, carpeta destino, concurrencia elegida.
- `DownloadTask`: IDs de lote/video, estado, progreso opcional, bytes/ETA opcionales, ruta y error estructurado.
- `AppSettings`: carpeta recordada y concurrencia elegida.
- `DownloadError`: `code`, mensaje localizado, `recoverable`, acción recomendada.

No serializar callbacks, instancias `YoutubeDL`, excepciones ni rutas arbitrarias enviadas desde JavaScript.

## 6. Arquitectura y contrato del puente

### Responsabilidades

- **React:** estado y vistas; no conoce yt-dlp, FFmpeg ni filesystem directamente.
- **PyWebView API:** superficie pequeña y tipada entre renderer y Python; valida todos los argumentos.
- **Servicios Python:** análisis, plan de salida, configuración, cola y descargas.
- **yt-dlp:** extracción y descarga mediante su API Python, `progress_hooks` y opciones tipadas.
- **FFmpeg:** merge/remux y extracción MP3. Verificar disponibilidad/version antes de ofrecer la acción.

### Métodos previstos

- `get_app_status()`
- `analyze_url(url)`
- `get_preview(analysis_id, item_id, output_format, quality)`
- `enqueue_batch(analysis_id, selected_ids, output_format, quality)`
- `get_queue_state()` / `get_preferences()`
- `set_preferences(values)` / `choose_destination()`
- `pause_all()` / `resume_all()` / `cancel_item(task_id)` / `cancel_all()`
- `retry_item(task_id)` / `clear_history()` / `open_history_file(task_id, index)`
- `continue_in_background()` / `pause_and_close()`

`enqueue_batch` no acepta rutas del renderer: utiliza la carpeta persistida y `choose_destination()` la cambia mediante diálogo nativo. La implementación existente usa estos nombres; si el puente necesita refactor, conservar la semántica y actualizar Python y TypeScript juntos.

### Sincronización de estado

La UI actual consulta `get_queue_state()` de forma periódica. El MVP debe mantener la UI responsiva y evitar trabajo de descarga en el renderer; puede conservar el polling mientras su costo sea acotado, o sustituirlo por eventos tipados si se demuestra más fiable. Nunca duplicar actualizaciones ni congelar la ventana.

### Payloads de estado

- `get_queue_state()` devuelve `queue`, `history`, `counts` y `preferences`.
- Cada tarea mantiene ID estable, batch, estado, progreso nullable, bytes/ETA cuando existen, rutas finales y error legible.
- La UI actual consulta el snapshot cada 1.2 segundos. Mantenerlo mientras sea estable; sustituirlo por eventos solo si se documenta el contrato y se evita polling duplicado.
- El hilo visual nunca espera un análisis o una descarga.

## 7. Archivos y preferencias locales

- Preferencias: `%LOCALAPPDATA%/Clipoteca/settings.json`, escritura atómica y validación de esquema.
- Destino inicial: `%USERPROFILE%/Downloads/Clipoteca`.
- Playlist: subcarpeta creada desde título saneado.
- Filename recomendado: título saneado + ID de YouTube para evitar colisiones.
- Resolver caracteres reservados, nombres Windows reservados, separadores, longitud y colisiones.
- No formar rutas con `../`, no aceptar rutas arbitrarias del renderer y no ejecutar strings como shell.
- Persistir tareas pendientes/interrumpidas para recuperación. No subir historial ni URLs a ningún servicio.
- La política de retención de tareas completadas debe ser local y clara; no implementar analítica ni telemetría.

## 8. Formatos, concurrencia y errores

- **MP4:** elegir pistas compatibles, unir/remux con FFmpeg cuando proceda; no re-encodear silenciosamente.
- **MP3:** extracción/conversión por FFmpeg; si falta el binario, bloquear esa opción con instrucciones claras.
- **Ambos:** producir una salida de video y una de audio por cada entrada seleccionada; reportar cada salida/resultado.
- **Calidad:** opciones basadas en formatos reales; si una resolución no existe, no mostrarla.
- **Concurrencia:** pregunta única al primer inicio, valor recordado, editable; sin límite máximo impuesto por la app; advertencia no bloqueante desde 5.
- **Rate limit:** backoff moderado y finito; no hacer reintentos agresivos ni continuar en bucle.

Errores que requieren tratamiento: URL inválida, dominio no soportado, red/rate limit, video inaccesible, playlist vacía, formato no disponible, disco lleno/permisos, nombre inválido, FFmpeg ausente/fallido, cancelación y error inesperado. El mensaje debe explicar qué ocurrió y qué puede hacer el usuario.

## 9. Privacidad, seguridad y uso responsable

- Contenido local del usuario y material que esté autorizado a descargar.
- No autenticación, cookies, DRM, evasión de geobloqueos ni bypass de controles.
- Redactar URLs de logs; no registrar query strings completas ni datos de sesión.
- Validar URL/host, rutas, IDs y preferencias en el backend, aunque la UI ya valide.
- No usar `shell=True`; no interpolar la URL o títulos en comandos.
- Sin telemetría, backend remoto o sincronización.
- Explicar que el usuario debe respetar derechos de autor y condiciones aplicables.

## 10. Pruebas y Definition of Done

- Pruebas Python unitarias para validación, mapping de yt-dlp, estados, paths, duplicates, cancelación y settings.
- Pruebas React/Vitest para carga/error/empty, selección, formatos, calidad, estados y errores accesibles.
- Integración con yt-dlp completamente mockeada en CI; no descargar archivos reales en pruebas automáticas.
- Smoke de escritorio en Windows: PyWebView/WebView2 abre `frontend/dist`, API responde y cierre no corrompe cola/configuración.
- Manual autorizado solo con una URL cuyo contenido el usuario o tester puede guardar; marcarlo como manual y no como CI.
- Verificar build, lint, suite Python/React, empaquetado, instalador, teclado, contraste y pantallas de 1440×920 y 390×844.
- README actualizado con instalación, ejecución, FFmpeg/WebView2, limitaciones, errores comunes y licencia.
- Ningún botón principal puede fingir una acción todavía no integrada.

## 11. Decisiones diferidas

- Retención exacta de tareas completadas/historial.
- Proveedor y paquete FFmpeg definitivos, tras la revisión legal/licencias.
- Umbral de advertencia de concurrencia (propuesta inicial: 5; no es un máximo).
- Flujo de actualización de yt-dlp/app tras cambios del sitio.
- Cualquier soporte de sitios ajenos a YouTube, subtítulos o historial permanente.

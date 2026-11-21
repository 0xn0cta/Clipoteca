# Tareas para completar Clipoteca

**Regla de ejecución:** completar en orden salvo dependencias explícitas. Una tarea por vez; mantener build verde; marcar `[x]` solo tras verificar. La revisión del propietario se solicita en los checkpoints de `tasks/plan.md`.

## Base recibida

- El colaborador ya añadió análisis, descarga, queue manager SQLite, historial, preview y bandeja. Reutilizar/revisar `clipoteca/`; no reimplementar esos módulos sin causa.
- El baseline verificable en esta integración es 22 tests Python, build y lint. El flujo live de yt-dlp, FFmpeg, bandeja, WebView2 e instalador aún no se probó en Windows.
- YouTube allowlist, concurrencia inicial, validación de rutas del puente, nombres reservados y MP4 sin recodificación silenciosa se reconciliaron; revisar sus tests antes de avanzar.
- No hay todavía suite React/Vitest ni CI; no marcar T01/T02 como completadas por la suite `unittest`.
- El resto de tareas permanece abierto hasta pasar todos sus criterios.

## Fase 1 — Base de ingeniería

### T01 — Añadir test runners Python y React

**Descripción:** establecer suites repetibles para validar reglas de Python y estados de UI sin red real.

**Criterios de aceptación:**
- [ ] Python tiene pytest y frontend tiene Vitest + Testing Library configurados.
- [ ] `python -m pytest` y `npm test` funcionan desde instalaciones limpias.
- [ ] Una prueba de ejemplo por suite demuestra que el runner descubre y reporta tests.

**Verificación:** `python -m pytest`; `cd frontend; npm test; npm run build; npm run lint`.
**Dependencias:** ninguna.
**Archivos previstos:** `requirements-dev.txt`, `frontend/package.json`, `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/App.test.tsx`.
**Alcance:** M.

### T02 — Añadir CI de Windows

**Descripción:** ejecutar build, lint y suites en un runner Windows en cada cambio de la rama.

**Criterios de aceptación:**
- [ ] Workflow instala Python, Node, dependencias y ejecuta las verificaciones documentadas.
- [ ] No depende de una URL de YouTube ni descarga archivos reales.

**Verificación:** ejecutar el workflow o su equivalente local; confirmar estado verde en GitHub.
**Dependencias:** T01.
**Archivos previstos:** `.github/workflows/ci.yml`.
**Alcance:** S.

### T03 — Crear modelos de dominio y errores

**Descripción:** separar entidades de playlist, salida, tarea y error del código de UI/yt-dlp.

**Criterios de aceptación:**
- [ ] Modelos tipados representan video, playlist, disponibilidad, selección, tarea y progreso nullable.
- [ ] Estados y códigos de error son enums/constantes, no strings improvisados en cada módulo.
- [ ] Tests cubren serialización básica y transiciones inválidas.

**Verificación:** `python -m pytest tests/python/test_models.py`.
**Dependencias:** T01.
**Archivos previstos:** `clipoteca/__init__.py`, `clipoteca/models.py`, `clipoteca/errors.py`, `tests/python/test_models.py`.
**Alcance:** M.

### T04 — Definir el puente pywebview tipado

**Descripción:** sustituir el stub actual por una API pequeña común entre React y Python, manteniendo las operaciones lentas fuera del hilo UI.

**Criterios de aceptación:**
- [ ] Métodos y respuestas/error están documentados en Python y TypeScript con los mismos nombres y campos.
- [ ] El puente solo expone funciones explícitas; no ofrece eval, shell, rutas arbitrarias ni acceso genérico a Python.
- [ ] UI funciona en navegador de desarrollo con una implementación mock y en escritorio con pywebview.

**Verificación:** tests de contrato Python/TypeScript y smoke test de `python main.py --help`.
**Dependencias:** T01, T03.
**Archivos previstos:** `clipoteca/desktop_api.py`, `main.py`, `frontend/src/types/bridge.ts`, `frontend/src/lib/desktop-api.ts`, `frontend/src/lib/desktop-api.test.ts`.
**Alcance:** M.

### T05 — Implementar preferencias iniciales

**Descripción:** guardar carpeta y concurrencia en el perfil local; preguntar por concurrencia solo en el primer inicio.

**Criterios de aceptación:**
- [ ] Primer inicio solicita un entero positivo de concurrencia y lo guarda; siguientes aperturas reutilizan lo elegido.
- [ ] No existe un máximo impuesto; a partir de 5 se propone una advertencia no bloqueante, que no impide confirmar.
- [ ] La carpeta inicial es `%USERPROFILE%/Downloads/Clipoteca` y se persiste si el usuario la cambia.

**Verificación:** tests de settings por defecto, persistencia, configuración inválida, primer inicio y valor alto permitido.
**Dependencias:** T01, T03, T04.
**Archivos previstos:** `clipoteca/settings.py`, `tests/python/test_settings.py`, `frontend/src/components/ConcurrencySetup.tsx`, `frontend/src/components/ConcurrencySetup.test.tsx`.
**Alcance:** M.

### Checkpoint 1 — Base

- [ ] Build, lint y suites verdes.
- [ ] Contrato JS/Python y settings revisados por el propietario antes de integrar análisis real.

## Fase 2 — Análisis y selección

### T06 — Validar URLs de YouTube

**Descripción:** normalizar y validar URLs antes de entregarlas a yt-dlp.

**Criterios de aceptación:**
- [ ] Se aceptan URLs válidas de YouTube y youtu.be; se rechazan esquemas no HTTP(S), hosts ajenos y entradas mal formadas.
- [ ] No se almacenan ni registran query strings sensibles en logs.
- [ ] Los errores devuelven código estable y mensaje recuperable en español.

**Verificación:** tests unitarios con URLs válidas, inválidas, puertos, credenciales embebidas y hosts falsos.
**Dependencias:** T01, T03.
**Archivos previstos:** `clipoteca/url_validation.py`, `tests/python/test_url_validation.py`, `clipoteca/errors.py`.
**Alcance:** S.

### T07 — Analizar video y playlist con yt-dlp

**Descripción:** implementar extracción de metadatos sin descargar archivos.

**Criterios de aceptación:**
- [ ] Video individual produce una entrada; playlist produce entradas en orden con duración/availability cuando existan.
- [ ] `download=False` se usa para análisis; no se inicia descarga al pegar o analizar.
- [ ] Casos privados, eliminados, vacíos y errores de red se traducen a estados/códigos sin intentar bypass.

**Verificación:** unit tests con yt-dlp simulado; ninguna prueba automática hace llamadas externas.
**Dependencias:** T03, T06.
**Archivos previstos:** `clipoteca/services/analysis.py`, `clipoteca/models.py`, `tests/python/test_analysis.py`.
**Alcance:** M.

### T08 — Exponer análisis por el puente

**Descripción:** conectar `analyze_url` con el servicio, validación y serialización acordados.

**Criterios de aceptación:**
- [ ] Método valida, devuelve respuesta tipada y nunca llama a `download`.
- [ ] Errores de yt-dlp se convierten al contrato común sin stack trace al usuario.
- [ ] Operación lenta no congela la ventana.

**Verificación:** tests del API usando analyzer mock y prueba de respuesta de error.
**Dependencias:** T04, T06, T07.
**Archivos previstos:** `clipoteca/desktop_api.py`, `clipoteca/services/analysis.py`, `tests/python/test_desktop_api.py`.
**Alcance:** S.

### T09 — Conectar el formulario de origen a análisis real

**Descripción:** sustituir la respuesta de demostración por estados reales de análisis.

**Criterios de aceptación:**
- [ ] Submit vacío muestra validación local; URL válida muestra loading y resultado/error.
- [ ] Se implementan estados idle, loading, ready, empty y error con recuperación clara.
- [ ] Datos ficticios no aparecen en builds de producción como si fueran análisis real.

**Verificación:** tests de componente para submit, loading, error, respuesta y empty.
**Dependencias:** T01, T04, T08.
**Archivos previstos:** `frontend/src/App.tsx`, `frontend/src/components/SourceForm.tsx`, `frontend/src/hooks/use-source-analysis.ts`, tests asociados.
**Alcance:** M.

### T10 — Aplicar selección real de playlist

**Descripción:** enlazar selección global y por elemento a las entradas analizadas.

**Criterios de aceptación:**
- [ ] Todas las entradas disponibles aparecen seleccionadas por defecto; las no disponibles están deshabilitadas.
- [ ] Seleccionar/deseleccionar conserva orden y actualiza el total agregado.
- [ ] Video individual y playlist de un elemento usan el mismo modelo sin estados contradictorios.

**Verificación:** tests para selección individual/global, elementos no disponibles, lista vacía y orden.
**Dependencias:** T09.
**Archivos previstos:** `frontend/src/components/PlaylistManifest.tsx`, `frontend/src/hooks/use-playlist-selection.ts`, tests asociados.
**Alcance:** M.

### Checkpoint 2 — Fuente analizada

- [ ] Video y playlist se analizan desde el puente real.
- [ ] Casos vacíos/no disponibles/error no inician descarga y permiten recuperar.

## Fase 3 — Salida y descarga individual

### T11 — Validar opciones de formato y calidad

**Descripción:** construir una solicitud de salida válida según los formatos que yt-dlp reporta.

**Criterios de aceptación:**
- [ ] Video MP4, audio MP3 y ambos se representan en un modelo único y validado.
- [ ] Calidad automática es default; las opciones manuales solo incluyen resoluciones disponibles.
- [ ] Calidad se desactiva en audio-only y la UI muestra la razón.

**Verificación:** tests de builder/validación y de controles React para formatos y calidad.
**Dependencias:** T07, T10.
**Archivos previstos:** `clipoteca/output_options.py`, `tests/python/test_output_options.py`, `frontend/src/components/OutputPreferences.tsx`.
**Alcance:** M.

### T12 — Elegir carpeta de destino

**Descripción:** conectar diálogo nativo del sistema y preferencia guardada con el panel de salida.

**Criterios de aceptación:**
- [ ] Usuario puede mantener el valor guardado o cambiarlo para el lote actual.
- [ ] Cancelar el diálogo no cambia la preferencia.
- [ ] La UI muestra ruta comprensible y error de permisos sin perder selección.

**Verificación:** tests de API mockeada y prueba manual del diálogo Windows.
**Dependencias:** T04, T05, T11.
**Archivos previstos:** `clipoteca/desktop_api.py`, `clipoteca/folder_picker.py`, `frontend/src/components/OutputPreferences.tsx`, tests asociados.
**Alcance:** M.

### T13 — Crear rutas seguras y detectar duplicados

**Descripción:** preparar nombres y carpetas por video/playlist respetando reglas de Windows.

**Criterios de aceptación:**
- [ ] Títulos se saneen para Windows; playlist crea subcarpeta propia; filename incluye ID estable para reducir colisiones.
- [ ] Duplicado existente se marca `Omitido`, explica la ruta y nunca sobrescribe silenciosamente.
- [ ] Path traversal, nombres reservados, ruta vacía y ruta sin permiso se rechazan con errores claros.

**Verificación:** tests de Windows reserved names, caracteres inválidos, duplicados y rutas largas.
**Dependencias:** T05, T11, T12.
**Archivos previstos:** `clipoteca/output_paths.py`, `clipoteca/duplicate_check.py`, `tests/python/test_output_paths.py`, `tests/python/test_duplicates.py`.
**Alcance:** M.

### T14 — Completar descarga vertical de un video MP4

**Descripción:** conectar selección de un video a yt-dlp y producir MP4 con progreso.

**Criterios de aceptación:**
- [ ] Una URL analizada puede iniciar una descarga real solo tras confirmación explícita.
- [ ] El archivo queda en el destino esperado, en formato MP4 compatible; no hay re-encode silencioso.
- [ ] La UI distingue pendiente, descargando, completado y fallido.

**Verificación:** tests con yt-dlp mock; smoke manual solo con URL autorizada, marcado como manual.
**Reverificación de compatibilidad:** para MP4, el selector da prioridad a H.264 cuando está disponible y respeta el límite de resolución. Las pruebas con metadatos simulados cubren H.264, el fallback a AV1, el límite de altura y el rechazo de una fuente con solo audio. Pasaron 84 pruebas Python y 7 subpruebas. Se comprobó localmente la pista AV1 del archivo existente con FFmpeg, sin iniciar una descarga real.

**Salida para Windows:** se comprueban las pistas del MP4 y se convierten a H.264 con color de 8 bits y a AAC si hace falta. La cola muestra la fase de compatibilidad cuando hay conversión. Pasaron 93 pruebas Python, 14 subpruebas, build, lint y smokes T39/T40 con datos simulados. Se probó la conversión, la conservación del original y la reutilización de la copia con un archivo de prueba local. FFprobe confirmó H.264 y AAC en la copia generada desde el Reel ya descargado. Sigue pendiente la prueba de descarga externa autorizada.
**Dependencias:** T08, T11, T12, T13.
**Archivos previstos:** `clipoteca/services/download.py`, `clipoteca/desktop_api.py`, `frontend/src/components/DownloadAction.tsx`, tests asociados.
**Alcance:** M.

### T15 — Añadir MP3 y modo “ambos”

**Descripción:** producir MP3 por FFmpeg y soportar video + audio por entrada.

**Criterios de aceptación:**
- [ ] MP3 se extrae con FFmpeg; ambos produce salidas separadas asociadas a la misma entrada.
- [ ] FFmpeg ausente o incompatible bloquea la opción afectada y explica cómo recuperarse.
- [ ] Un fallo de audio no oculta el resultado de video ni viceversa.

**Verificación:** tests mockeados de argumentos/progreso/errores FFmpeg; smoke manual autorizado.
**Dependencias:** T14.
**Archivos previstos:** `clipoteca/services/download.py`, `clipoteca/services/ffmpeg.py`, `clipoteca/models.py`, tests asociados.
**Alcance:** M.

## Fase 4 — Cola de playlist fiable

### T16 — Ejecutar cola con concurrencia elegida

**Descripción:** ejecutar jobs con el número de workers elegido en primer inicio, sin imponer máximo de producto.

**Criterios de aceptación:**
- [ ] La cola ejecuta hasta el entero positivo configurado; el valor se conserva entre sesiones.
- [ ] A partir de 5 muestra advertencia no bloqueante; no hay clamp, no se ocultan tasks y el usuario puede continuar.
- [ ] Excepciones de worker no detienen otros workers ni corrompen estado compartido.

**Verificación:** tests con workers controlados, concurrencia 1, concurrencia >5 y fallos concurrentes.
**Dependencias:** T05, T14, T15.
**Archivos previstos:** `clipoteca/queue_manager.py`, `clipoteca/settings.py`, `tests/python/test_queue_manager.py`, `frontend/src/components/ConcurrencySetup.tsx`.
**Alcance:** M.

### T17 — Sincronizar progreso y cola en React

**Descripción:** sustituir contador y mensajes de prototipo por estado real por tarea y por lote.

**Criterios de aceptación:**
- [ ] Eventos no duplicados actualizan la fila correcta y el progreso agregado.
- [ ] Progreso/ETA ausente se representa como indeterminado, no como 0%/100% inventado.
- [ ] El estado se recupera con un snapshot al abrir la vista, además de eventos en vivo.

**Verificación:** tests reducer/hooks de eventos repetidos, desconocidos, fuera de orden y progress null.
**Verificación parcial:** los callbacks simulados y el smoke de interfaz cubren pista de vídeo, pista de audio, unión, transcurrido y restante estimado por fase. El contador queda indeterminado al unir o si faltan datos de transferencia. Build, lint y 85 pruebas Python con 7 subpruebas pasan.
**Reverificación de pasos:** los callbacks marcan cada paso en curso o completado y la cola los presenta en orden según la transferencia y el procesamiento reales. Pasaron 88 pruebas Python y 10 subpruebas, build, lint y los smokes T39/T40 con datos simulados.
**Dependencias:** T04, T16.
**Archivos previstos:** `frontend/src/types/bridge.ts`, `frontend/src/hooks/use-download-queue.ts`, `frontend/src/components/DownloadQueue.tsx`, tests asociados.
**Alcance:** M.

### T18 — Ejecutar playlist como lote tolerante a fallos

**Descripción:** crear tareas para elementos seleccionados y reportar resumen completo.

**Criterios de aceptación:**
- [ ] Orden original de la playlist queda disponible y cada tarea conserva su índice.
- [ ] Error de un elemento no aborta otros; duplicados y no disponibles se cuentan como omitidos.
- [ ] Al finalizar se muestra resumen de completados, omitidos y fallidos con reintento por entrada.

**Verificación:** integración mock con una playlist de éxito, fallo transitorio, no disponible y duplicado.
**Dependencias:** T10, T13, T16, T17.
**Archivos previstos:** `clipoteca/queue_manager.py`, `clipoteca/models.py`, `frontend/src/components/DownloadQueue.tsx`, tests asociados.
**Alcance:** M.

### T19 — Cancelar, reintentar y reanudar parciales

**Descripción:** permitir recuperar tareas sin marcar como exitosas las incompletas.

**Criterios de aceptación:**
- [ ] Cancelación por tarea y por lote actualiza estado y libera workers.
- [ ] Reintento manual funciona en fallos recuperables; fallos terminales muestran motivo sin loop.
- [ ] `.part` se conserva/reanuda solo cuando yt-dlp lo permite; duplicado final se omite.

**Verificación:** tests cancel token, retry, partial resume y terminal errors; no iniciar una descarga real.
**Verificación parcial:** 87 pruebas Python y 10 subpruebas pasan. Los cortes recuperables tienen tres reintentos con espera creciente y limpian el ETA antiguo mientras esperan. Una pista intermedia sin archivo final produce error y se conserva para reintento.
**Dependencias:** T14, T16, T18.
**Archivos previstos:** `clipoteca/services/download.py`, `clipoteca/queue_manager.py`, `frontend/src/components/DownloadQueue.tsx`, tests asociados.
**Alcance:** M.

### T20 — Recuperar tareas tras cerrar la app

**Descripción:** persistir lo mínimo necesario para reanudar y restablecer estados al reiniciar.

**Criterios de aceptación:**
- [ ] Tareas activas/pendientes se guardan localmente y reaparecen como `Interrumpida` tras un cierre abrupto.
- [ ] Ninguna tarea aparece como `Descargando` sin worker vivo.
- [ ] La política no almacena historial remoto ni URLs en logs; usuario puede descartar la tarea local.

**Verificación:** tests de restart/corrupt store/schema migration; simulación de cierre mientras job está activo.
**Dependencias:** T16, T19.
**Archivos previstos:** `clipoteca/queue_store.py`, `clipoteca/queue_manager.py`, `tests/python/test_queue_store.py`, `frontend/src/components/DownloadQueue.tsx`.
**Alcance:** M.

### Checkpoint 3 — Descargador funcional

- [ ] Video y playlist completan en flujo autorizado/manual.
- [ ] Fallo parcial, cancelación, reintento y recuperación quedan comprobados en mocks.
- [ ] El propietario revisa pantalla de cola y resúmenes antes del empaquetado.

## Fase 5 — Errores, seguridad y Windows release

### T21 — Completar mapa de errores y recuperación UI

**Descripción:** hacer que cada error esperado tenga mensaje, estado y acción apropiados.

**Criterios de aceptación:**
- [ ] URL inválida, no disponible, red/rate limit, permisos, disco lleno, formato y FFmpeg se distinguen.
- [ ] Mensajes en español indican qué falló y una acción concreta; no muestran stack traces.
- [ ] Errores no terminales no eliminan selección ni opciones del usuario.

**Verificación:** tabla de tests frontend para cada código de error y recovery action.
**Progreso parcial:** el motor ahora traduce `ENOSPC`/“No space left on device” a un mensaje en español que pide liberar espacio o cambiar el destino; `test_disk_full_error_explains_how_to_recover` pasa. T21 sigue abierto: falta completar el mapa y la recuperación de UI.
**Dependencias:** T06–T20.
**Archivos previstos:** `clipoteca/errors.py`, `frontend/src/components/ErrorNotice.tsx`, `frontend/src/components/DownloadQueue.tsx`, tests asociados.
**Alcance:** M.

### T22 — Auditar privacidad y límites del puente

**Descripción:** revisar entradas del renderer, logs, paths y métodos expuestos.

**Criterios de aceptación:**
- [ ] No se exponen cookies, credenciales, eval, shell ni paths arbitrarios.
- [ ] URLs/query strings se redactan de logs; no hay telemetría ni requests de aplicación a un servidor propio.
- [ ] Validación backend cubre host, esquema, ruta, concurrencia y selección, aunque la UI valide antes.

**Verificación:** tests de abuso de URL/path y revisión manual del API surface/logging.
**Dependencias:** T04, T06, T12, T20.
**Archivos previstos:** `clipoteca/desktop_api.py`, `clipoteca/url_validation.py`, `clipoteca/output_paths.py`, tests asociados.
**Alcance:** M.

### T23 — Seleccionar y auditar FFmpeg distribuible

**Descripción:** fijar fuente/version/hash, comprobar build y cumplir avisos/licencia.

**Criterios de aceptación:**
- [ ] El binario incluido funciona en Windows clean install y su versión queda registrada.
- [ ] Licencia y notices del build concreto se revisan y distribuyen.
- [ ] Si el cumplimiento no queda demostrado, no se publica un instalador que lo incluya; reportar bloqueo.

**Verificación:** ejecutar `ffmpeg -version`, prueba de merge/MP3 y checklist de licencias/attribution.
**Dependencias:** T15.
**Archivos previstos:** `packaging/ffmpeg/README.md`, `packaging/licenses/`, `docs/IMPLEMENTATION_SPEC.md`.
**Alcance:** M.

### T24 — Empaquetar la app Python y frontend

**Descripción:** crear build frozen que arranque la UI local en pywebview con assets de Vite.

**Criterios de aceptación:**
- [ ] Build contiene backend y `frontend/dist` con rutas relativas válidas.
- [ ] La ventana inicia, usa el fondo actual y llama al puente.
- [ ] Build falla con mensaje claro si assets/runtime requerido no están disponibles.

**Verificación:** build en Windows limpio, smoke test open/close y API status.
**Dependencias:** T04, T20, T23.
**Archivos previstos:** `pyinstaller.spec`, `packaging/build.ps1`, `main.py`, `README.md`.
**Alcance:** M.

### T25 — Crear instalador Windows y prerequisito WebView2

**Descripción:** instalar la app, FFmpeg y avisos; detectar o instalar WebView2 de forma clara.

**Criterios de aceptación:**
- [ ] Instalador crea accesos y ubicación de datos local sin borrar preferencias existentes al actualizar.
- [ ] WebView2 ausente produce instalación/bootstrapper o instrucción recuperable.
- [ ] Desinstalación no elimina archivos descargados del usuario por defecto.

**Verificación:** instalar, abrir, hacer smoke, actualizar y desinstalar en Windows limpio/VM.
**Dependencias:** T23, T24.
**Archivos previstos:** `packaging/installer/`, `packaging/build.ps1`, `docs/INSTALL_WINDOWS.md`, `README.md`.
**Alcance:** M.

### T26 — Auditar accesibilidad y acabados visuales

**Descripción:** mantener el diseño “Private Collection Archive” mientras todas las tareas funcionan.

**Criterios de aceptación:**
- [ ] Teclado alcanza cada control y los estados no dependen solo del color.
- [ ] Contraste, foco, lectura de estados, texto largo, responsive y `prefers-reduced-motion` se verifican.
- [ ] No quedan datos falsos de playlist/destino, botones de prototipo ni errores de UI no recuperables en build de producción.

**Verificación:** prueba manual con teclado, inspección visual desktop/móvil y suite de accesibilidad elegida/documentada.
**Dependencias:** T09–T25.
**Archivos previstos:** `frontend/src/App.tsx`, `frontend/src/App.css`, componentes afectados, tests UI.
**Alcance:** M.

### T27 — Cerrar aceptación, README y handoff

**Descripción:** entregar al propietario una build verificable, documentación y riesgos residuales.

**Criterios de aceptación:**
- [ ] README cubre instalación, uso, formatos, límites, errores comunes y cómo reportar fallos.
- [ ] CI verde; se distinguen pruebas automatizadas, smoke test manual y pruebas no realizadas.
- [ ] Se entregan installer, hash, versión yt-dlp/FFmpeg, notices y lista de decisiones pendientes.

**Verificación:** ejecutar Definition of Done completa de `docs/IMPLEMENTATION_SPEC.md`; revisión humana antes de release.
**Dependencias:** T21–T26.
**Archivos previstos:** `README.md`, `docs/INSTALL_WINDOWS.md`, `docs/RELEASE_CHECKLIST.md`.
**Alcance:** S.

### Checkpoint final — Revisión del propietario

- [ ] El propietario prueba el instalador y el flujo con material autorizado.
- [ ] Issues visuales/funcionales se registran como nuevas tareas, no se arreglan con cambios de alcance invisibles.
- [ ] No publicar release ni merge a main hasta aprobación explícita.

## Extensión posterior — CLI local automatizable

### T28 — Definir contrato y punto de entrada de consola

**Descripción:** establecer una CLI sin GUI que reutilice la lógica local de Clipoteca y ofrezca una interfaz estable para scripts.

**Criterios de aceptación:**
- [x] `python -m clipoteca.cli --help` y `--version` funcionan sin importar/iniciar pywebview.
- [x] Se documentan comandos, esquema JSON, códigos de salida y canales de progreso.
- [x] Los argumentos pasan por validación tipada; no hay ejecución arbitraria de shell ni métodos genéricos del puente.

**Verificación:** tests del parser, `--help`, salida JSON y errores; sin red ni descargas.
**Resultado:** `python -m unittest discover -s tests -v` y `python -m pytest -q` pasan (30 tests, 4 subtests); `--help`, `--version`, argumentos anidados, salida JSON y rechazo de hosts ajenos comprobados.
**Dependencias:** ninguna.
**Archivos previstos:** `clipoteca/cli.py`, `clipoteca/__main__.py`, `tests/test_cli.py`, `docs/CLI.md`.
**Alcance:** S.

### T29 — Exponer estado, análisis y vista previa

**Descripción:** permitir consultar disponibilidad local, analizar URLs y obtener la misma información de vista previa que la app.

**Criterios de aceptación:**
- [x] `status`, `analyze` y `preview` tienen salida legible y JSON estable.
- [x] El análisis/preview nunca inicia una descarga; el backend mantiene YouTube-only y los errores en español/código estable.
- [x] Preview no escribe archivos y documenta cómo consumir el flujo reproducible si existe.

**Verificación:** yt-dlp simulado; casos inválidos, playlist vacía, preview no reproducible y motor/FFmpeg ausentes.
**Resultado:** 37 tests Python y 4 subtests pasan; CLI `status --json` verificó yt-dlp 2026.10.26 y FFmpeg/ffprobe 9.1 disponibles. Pruebas de análisis/preview mockeadas. Por error ejecuté una consulta de metadatos con el ID de ejemplo `demo`; YouTube la rechazó como ID incompleto y no se descargó ningún archivo.
**Dependencias:** T28.
**Archivos previstos:** `clipoteca/cli.py`, servicios existentes, `tests/test_cli.py`, `docs/CLI.md`.
**Alcance:** M.

### T30 — Coordinar el worker entre GUI y CLI

**Descripción:** impedir que la GUI y la CLI arranquen schedulers que compitan por la misma cola SQLite y permitir que las acciones de cola lleguen al proceso worker.

**Criterios de aceptación:**
- [x] Un solo proceso obtiene la propiedad de ejecución de descargas para el almacén local.
- [x] Los demás procesos pueden consultar/encolar; pausa/cancelación se transmiten al worker activo mediante señales SQLite o devuelven un error recuperable, nunca simulan éxito.
- [x] La recuperación de tareas interrumpidas ocurre solo después de adquirir el lock; una salida/cierre inesperado lo libera.

**Verificación:** pruebas multiproceso con almacén temporal: adquisición, contención, señales de acción, liberación y recuperación; confirmar que solo un worker ejecuta cada tarea y que cancelar no oculta fallos reintentables.
**Resultado:** 44 tests Python y 4 subtests pasan; pruebas de lock multiproceso, caída del owner, encolado desde segundo manager, pausa/cancelación interproceso y recuperación. `npm run build` y `npm run lint` pasan.
**Reverificación:** 81 pruebas Python y 2 subpruebas pasan. Las regresiones cubren cancelación antes y después de que el worker reclame la tarea y comprueban desde otro proceso que el bloqueo sigue ocupado hasta que termina una descarga activa, incluso si vence el plazo de cierre. Build y lint del frontend pasan en una copia aislada. Se usaron descargas simuladas y SQLite temporal.
**Dependencias:** T28.
**Archivos previstos:** `clipoteca/manager.py`, `clipoteca/storage.py`, `clipoteca/worker_lock.py`, pruebas de manager/CLI.
**Alcance:** M.

### T31 — Ejecutar descargas headless

**Descripción:** descargar video/audio/ambos desde consola, elegir elementos y calidad, e informar progreso/resultado sin abrir la UI.

**Criterios de aceptación:**
- [x] Acepta video individual y playlist con selección de elementos, formato, calidad y destino validados.
- [x] Puede esperar el resultado con un código de salida útil; Ctrl+C pausa/interrumpe según el contrato y no deja estados falsos.

**Verificación:** tests mock de éxito, fallo, cancelación, destino y selección; smoke manual solo con material propio/autorizado.
**Resultado:** 51 tests Python y 3 subtests pasan; se validaron selección, destino, éxito/fallo, progreso JSONL y Ctrl+C con mocks. Build y lint del frontend pasan. No hice descarga manual real.
**Dependencias:** T28–T30.
**Archivos previstos:** `clipoteca/cli.py`, `clipoteca/manager.py`, servicios existentes, pruebas.
**Alcance:** M.

### T32 — Gestionar cola e historial desde consola

**Descripción:** exponer consulta y acciones de recuperación sobre los mismos registros que usa la app.

**Criterios de aceptación:**
- [x] Incluye listar, pausar/reanudar, cancelar por ID, cancelar lote y reintentar fallos.
- [x] Incluye listar/abrir/limpiar historial; limpiar registros nunca borra medios.
- [x] Las acciones destructivas no se confirman silenciosamente; los fallidos no desaparecen al cancelar trabajos activos.

**Verificación:** pruebas contra SQLite temporal para cada estado, permisos, cancelación, reintento e historial.
**Resultado:** 64 tests Python pasan; CLI prueba operaciones/confirmaciones con mocks y manager usa SQLite temporal. Build y lint pasan.
**Dependencias:** T28, T30–T31.
**Archivos previstos:** `clipoteca/cli.py`, `clipoteca/manager.py`, `clipoteca/storage.py`, pruebas.
**Alcance:** M.

### T33 — Gestionar preferencias en flujos no interactivos

**Descripción:** consultar y configurar destino/concurrencia desde scripts sin diálogo gráfico.

**Criterios de aceptación:**
- [x] `settings show/set` comparte y valida las preferencias de la app.
- [x] La configuración inicial no se preselecciona silenciosamente; la CLI requiere parámetros explícitos y no muestra prompts en modo automatizado.
- [x] Destinos son absolutos y validados; la ruta se guarda en la preferencia local compartida.

**Verificación:** tests de defaults, valor alto, entrada inválida, persistencia y salida JSON.
**Resultado:** 66 tests Python pasan; cobertura de persistencia con almacén temporal, concurrencia manual 250, modo inicial explícito y ruta relativa rechazada. Build y lint pasan.
**Dependencias:** T28.
**Archivos previstos:** `clipoteca/cli.py`, `clipoteca/manager.py`, `tests/test_cli.py`, `docs/CLI.md`.
**Alcance:** S.

### T34 — Empaquetar y aceptar la CLI

**Descripción:** distribuir un launcher de consola, documentar automatización y verificar flujos completos.

**Criterios de aceptación:**
- [ ] El instalador ofrece `clipoteca-cli.exe` separado de la app gráfica y conserva los datos compartidos.
- [ ] README/docs incluyen ejemplos PowerShell, JSON, códigos de salida, límites y errores comunes.
- [ ] CI prueba comandos y flujo headless con servicios mock; no usa URLs reales.

**Verificación:** build/instalación/actualización en Windows limpio; smoke CLI sin GUI, más verificación de concurrencia con la app.
**Dependencias:** T23, T24, T25, T28–T33, T01–T02.
**Archivos previstos:** `pyinstaller.spec`, `packaging/build.ps1`, `packaging/installer/`, `docs/CLI.md`, `README.md`, pruebas.
**Alcance:** M.

### Checkpoint CLI — Revisión del propietario

- [ ] Flujo automatizado de análisis → selección → descarga → historial se ejecuta sin GUI.
- [ ] Contrato JSON/códigos de salida y comportamiento al coexistir con GUI quedan revisados.
- [ ] Solo después de aprobación se integra el launcher en el instalador/release.

### T35 — Serializar tareas que comparten archivo de salida

**Descripción:** evitar que lotes/reintentos del mismo video escriban concurrentemente el mismo destino/nombre cuando la concurrencia global es mayor que uno.

**Criterios de aceptación:**
- [x] La identidad de salida usa la misma sanitización, carpeta de playlist, título e ID que la descarga real.
- [x] Dos tareas con la misma identidad no corren simultáneamente; tareas con identidades distintas sí pueden usar otros workers.
- [x] Al terminar la primera, la siguiente detecta el archivo existente y no lo sobrescribe.

**Verificación:** pruebas con downloader lento simulado, dos lotes del mismo elemento y una tarea diferente; comprobar concurrencia y no sobrescritura.
**Resultado:** `test_jobs_with_same_output_target_are_serialized` comprueba que se serialicen los destinos duplicados mientras una tarea distinta sí usa el segundo worker.
**Reverificación:** 82 pruebas Python y 2 subpruebas pasan. La regresión usa dos gestores con conexiones SQLite independientes y comprueba que cancelar el duplicado conserva el parcial de la descarga activa y permite que esta se complete.
**Dependencias:** T30, T31.
**Archivos previstos:** `clipoteca/manager.py`, `tests/test_manager.py`.
**Alcance:** S.

## Extensión visual — Rediseño Clipoteca Media Workspace

### T36 — Persistir modo de tema

**Descripción:** compartir la preferencia `system/dark/light` entre la GUI y la CLI, sin cambiar el tema por defecto de manera silenciosa.

**Criterios de aceptación:**
- [x] El backend valida y persiste `theme_mode` junto con las preferencias locales existentes.
- [x] La API de escritorio permite actualizar solo el conjunto explícito de preferencias.
- [x] La CLI `settings show/set` muestra y cambia `theme_mode` sin prompts.

**Verificación:** tests de default `system`, persistencia, valores inválidos y GUI/CLI sobre el mismo SQLite.
**Resultado:** 71 tests Python pasan; tema `system` por defecto, validación y persistencia GUI/API/CLI comprobadas. Build y lint pasan.
**Dependencias:** ninguna.
**Archivos previstos:** `clipoteca/manager.py`, `clipoteca/api.py`, `clipoteca/cli.py`, pruebas.
**Alcance:** M.

### T37 — Implementar sistema de color automático y overrides

**Descripción:** introducir tokens claros/oscuros con detección del tema del sistema y un selector manual accesible.

**Criterios de aceptación:**
- [x] `system` sigue `prefers-color-scheme`; Claro/Oscuro prevalecen hasta que se cambie la preferencia.
- [x] Controles nativos actualizan `color-scheme`; contraste/foco/estados semánticos son legibles en ambos temas.
- [x] No hay flash o estado incoherente al cargar preferencias desde pywebview.

**Verificación:** pruebas de sincronización de preferencia y visual en temas oscuro/claro; build y lint.
**Resultado:** 71 tests Python pasan; Playwright verifica detección del tema del sistema, override persistente, reflow a 390px y capturas oscuro/claro. Pares de contraste de texto/foco revisados. Build y lint pasan.
**Dependencias:** T36.
**Archivos previstos:** `frontend/index.html`, `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/src/assets/clipoteca-mark.svg`, `frontend/public/favicon.svg`, pruebas.
**Alcance:** M.

### T38 — Rehacer el shell con sidebar adaptable

**Descripción:** sustituir el top-nav actual por una navegación lateral compacta, manteniendo las rutas funcionales actuales.

**Criterios de aceptación:**
- [x] Preparar, Cola e Historial se alcanzan desde sidebar con nombre accesible y estado activo claro; Ajustes sigue disponible.
- [x] Sidebar se colapsa de manera estructural en ventanas estrechas y no provoca overflow horizontal.
- [x] Ventana compacta, maximizada y fullscreen se adaptan sin estirar el contenido fuera de lectura.

**Verificación:** inspección en 1440×920, ventana mínima prevista y 390×844; navegación por teclado.
**Resultado:** `npm run build`, `npm run lint`, `python -m pytest -q` (71 passed) y Playwright contra build con bridge simulado: navegación/aria-current, foco por teclado, Ajustes, sin overflow a 360/390/800/1440/1920px. Sidebar 228px/72px/58px; capturas desktop, 800×640 y 390×844 en `.impeccable/review/t38-shell-*.png`. `main.py` ahora permite ventana mínima 800×640. `npm test` no está definido.
**Reverificación:** el control manual de la barra lateral mantiene el foco al contraer o expandir y conserva la vista activa. El smoke verifica 228 px y 72 px en escritorio y el colapso automático a 58 px en 390 px.
**Dependencias:** T37.
**Archivos previstos:** `main.py`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/src/index.css`.
**Alcance:** M.

### T39 — Rediseñar preparación y preview

**Descripción:** ordenar el flujo de origen, playlist, preview y opciones en una composición lista+preview que conserve todas las acciones existentes.

**Criterios de aceptación:**
- [x] Cada fila muestra la miniatura junto al checkbox; pulsarla abre ese video en un reproductor oficial de YouTube integrado, sin cambiar la selección de descarga.
- [x] El panel lateral muestra el elemento abierto y su duración; carga/estado vacío son claros, el reproductor explica sus propias restricciones y nunca se implica guardado local.
- [x] No hay acción redundante «Ver selección»; el thumbnail respeta 120×70 px y el player 200×200 px, sin autoplay.
- [x] La build de escritorio pasa la ruta local a PyWebView en vez de `file://`, para servir la interfaz por HTTP y permitir el `Referer` del reproductor.
- [x] Playlist sigue primero y legible; las opciones de formato, calidad y destino permanecen visibles y compactas.
- [x] Análisis, selección, calidad, formato, destino y descarga conservan el contrato de backend.

**Verificación:** pruebas mock de thumbnails, apertura del reproductor y selección independiente; smoke de UI en desktop/compacto sin cargar fuentes externas ni descargar archivos.
**Resultado:** `npm run build`, `npm run lint` y `python tests/ui_smoke_t39.py` pasan; `tests/test_main.py` comprueba que se pasa la ruta de archivo local y `http_server=True`. El smoke UI comprueba `Referer` local, thumbnails/player con tamaño mínimo, ausencia de autoplay, que no exista «Ver selección», selección independiente, metadatos y 390px sin overflow; usa un iframe mock, sin llamadas a YouTube ni descargas. Capturas en `.impeccable/review/t39-preview-*.png`. El error real 153 aún requiere una prueba con la app reiniciada.
**Reverificación:** el smoke también comprueba apertura por teclado, foco de vuelta al cerrar, indicador de la miniatura activa y acceso al reproductor en 390 px. Volver a abrir la misma vista previa conserva el reproductor y el estado de carga.
**Dependencias:** T38.
**Archivos previstos:** `main.py`, `frontend/src/App.tsx`, `frontend/src/App.css`, `docs/IMPLEMENTATION_SPEC.md`, pruebas.
**Alcance:** M.

### T40 — Adaptar cola, historial y ajustes al nuevo sistema

**Descripción:** aplicar navegación, tema, densidad y estados coherentes a las vistas restantes y al flujo de cierre.

**Criterios de aceptación:**
- [x] Cola/historial/ajustes comparten sidebar, superficies, tipografía, focos y feedback de errores.
- [x] Se conservan acciones de pausa, reanudación, cancelación, reintento, abrir/limpiar historial y cierre a bandeja.
- [x] Progreso desconocido y errores siguen siendo distinguibles sin depender solo del color.
- [x] Sustituir el punto verde de estado del motor por un icono de `lucide-react` coherente con el estado y un nombre accesible.
- [x] El historial permite buscar por título/lote y usa filas compactas con fecha de finalización, duración del medio y tiempo de descarga medido.
- [x] El tiempo transcurrido se actualiza en la cola mientras descarga y se acumula correctamente tras pausar/reanudar; el total aparece al finalizar.
- [x] El origen se identifica junto al título con icono no ambiguo y nombre accesible; no se habilitan sitios fuera de la allowlist actual.
- [x] El arranque muestra una precarga de marca con spinner accesible hasta que respondan el puente y la cola; contempla fallo del puente y movimiento reducido.
- [x] El error de espacio insuficiente queda visible en la fila de cola/historial, explica la recuperación y no depende de un toast temporal ni del log técnico.

**Verificación:** build/lint, pruebas del cálculo/persistencia del tiempo de descarga, búsqueda/filtrado mockeados y smoke de precarga/cola con teclado y movimiento reducido.
**Reverificación del arranque y movimiento:** pantalla de precarga independiente con marca y spinner. Se muestra al menos 1,8 s desde el primer fotograma y espera el estado del motor y de la cola antes de montar la interfaz. Una ejecución aislada en WebView2 midió 2,1 s visibles y comprobó la transición a la app. El smoke cubre puente inmediato, motor demorado, reintento, movimiento reducido, progreso indeterminado y selección de formato con foco neutro. Build y lint pasan.
**Avisos:** se muestran arriba a la derecha y se cierran solos después de seis segundos. El smoke T40 comprueba posición, autocierre, pausa al pasar el ratón, cierre manual y que un mismo fallo de sondeo no vuelva a generar el aviso continuamente. Pasan build, lint, smokes T39/T40 y 88 pruebas Python con 10 subpruebas.
**Resultado:** `npm run build`, `npm run lint`, `python -m pytest -q` (83 pasadas, 2 subtests) y `python tests/ui_smoke_t40.py` pasan; también pasa smoke T39. UI smoke cubre spinner/error/reduced-motion, source icon, historial, timestamps, elapsed en cola e historial, error de disco y layout compacto con bridge simulado. Capturas en `.impeccable/review/t40-history-*.png`. No se descargaron medios; el error 153 real sigue pendiente de reiniciar/probar el PyWebView local.
**Dependencias:** T37–T38.
**Archivos previstos:** `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/src/index.css`, `frontend/package.json`, `frontend/package-lock.json`, `clipoteca/manager.py`, `clipoteca/storage.py`, `tests/test_manager.py`, pruebas UI.
**Alcance:** L.

### T41 — Cerrar revisión visual y documentar sistema

**Descripción:** hacer la inspección final del rediseño y dejar el sistema visual actualizado con evidencia.

**Criterios de aceptación:**
- [ ] Capturas válidas en tema oscuro/claro y ventanas desktop, compacta y móvil; no hay overflow ni estados cortados.
- [ ] Verificados teclado, foco, contraste, reduced-motion, texto largo y lectura de progreso/errores.
- [ ] DESIGN.md describe el mundo construido; capturas/provenance y hallazgos pendientes quedan registrados.

**Verificación:** `npm run build`, `npm run lint`, suites Python/CLI, smoke de pywebview; capturas inspeccionadas por viewport.
**Dependencias:** T26, T36–T40, T01–T02.
**Archivos previstos:** `DESIGN.md`, `docs/screenshots/`, `.impeccable/surfaces/frontend-src-app-tsx.md`, `frontend/src/`.
**Alcance:** M.

### T42 — Personalizar el color de la interfaz desde Ajustes

**Descripción:** permitir elegir un color de acento para Clipoteca y previsualizarlo desde Ajustes.

**Criterios de aceptación:**
- [x] Ajustes permite elegir un acento de una selección de colores y volver al acento predeterminado.
- [x] La elección se guarda localmente y se recupera al volver a abrir Clipoteca.
- [x] El acento funciona con los modos Sistema, Claro y Oscuro y mantiene el contraste de textos, botones y focos.
- [x] Los estados de error, éxito y progreso siguen siendo distinguibles con cualquier acento.

**Verificación:** persistencia al reiniciar, inspección de contraste en ambos temas y navegación por teclado.
**Resultado:** 88 pruebas Python y 10 subpruebas pasan, incluida la reapertura del puente con SQLite temporal. Build, lint y smokes T39/T40 pasan. El smoke cubre teclado, cancelar la previsualización, guardar el acento y contraste de las cinco muestras en claro y oscuro.
**Paletas de superficie:** los colores también cambian el fondo, la barra lateral, los paneles, los campos y los botones. El smoke comprueba en Claro y Oscuro que cambian los fondos, que el texto mantiene contraste y que el color de los iconos permanece estable.
**Dependencias:** T36, T37, T41.
**Archivos previstos:** ajustes del frontend, tokens de color, preferencias locales y pruebas.
**Alcance:** M.

### T43 — Suavizar las transiciones de la barra lateral y los diálogos

**Descripción:** animar el plegado manual de la barra lateral y la salida de los diálogos de Ajustes y cierre.

**Criterios de aceptación:**
- [x] La barra se pliega y despliega suavemente sin perder foco ni ocultar los controles de navegación.
- [x] Los diálogos salen con una transición breve y devuelven el foco cuando corresponde.
- [x] El movimiento reducido conserva toda la funcionalidad y omite el desplazamiento.

**Verificación:** smoke con teclado, clic y movimiento reducido.
**Resultado:** build, lint y smoke T40 pasan. El smoke comprueba la transición de la barra y el cierre de Ajustes con y sin movimiento, además de la devolución del foco.
**Dependencias:** T38, T40.
**Archivos previstos:** `frontend/src/App.tsx`, `frontend/src/App.css`, `tests/ui_smoke_t40.py`.
**Alcance:** S.

### T44 — Admitir vídeo público de Instagram y Reddit

**Descripción:** extender la lista de fuentes a Reels y publicaciones de Instagram con un solo vídeo y publicaciones de vídeo de Reddit.

**Criterios de aceptación:**
- [x] GUI y CLI comparten validación de fuentes y admiten enlaces directos y enlaces compartidos que resuelven en su plataforma.
- [x] La fuente se identifica con su icono y un nombre accesible en preparación, cola e historial.
- [x] La vista previa de Instagram y Reddit muestra miniatura y metadatos, y se mantiene la vista integrada de YouTube.

**Resultado:** 90 pruebas Python, 13 subpruebas, build, lint y smoke T39 pasan. Se verificaron URLs y vistas con datos simulados. Queda pendiente la aceptación con publicaciones reales autorizadas.
**Archivos:** motor, CLI, UI, documentación y pruebas.

### T45 — Mejorar las notificaciones del sistema Windows

**Descripción:** mostrar avisos nativos con la marca de Clipoteca y un resumen por lote, con nombre del vídeo o lista y resultado.

**Criterios de aceptación:**
- [x] Los avisos los emite Windows e incluyen el icono de Clipoteca.
- [x] La descarga individual distingue éxito, archivo existente y fallo. La lista genera un solo resumen con los resultados.
- [x] Los títulos se transportan como datos y se conservan los acentos y caracteres especiales.

**Resultado:** 92 pruebas Python y 13 subpruebas pasan. En Windows, la API WinRT aceptó un aviso silencioso de prueba desde el notifier real. Sin descargas externas.
**Archivos:** `clipoteca/tray.py`, `clipoteca/manager.py`, pruebas y dependencias.

### T47 — Mostrar el progreso del análisis y aligerar las listas largas

**Dependencias:** T07–T10 y T39.
**Criterios de aceptación:**
- [x] La interfaz indica qué fase del análisis está activa y cuenta las entradas al recibirlas.
- [x] Las listas muestran un máximo de 25 filas por página y cargan miniaturas según se acercan a la zona visible. Se conserva la selección global y el orden.
- [x] Las filas tienen separación vertical y admiten dos líneas de título. El reproductor tiene un marco interior redondeado sin desbordamiento en ventana compacta.

**Resultado:** 96 pruebas Python y 14 subpruebas en el árbol compartido. Build, lint y smokes T39/T40 correctos. El smoke verificó tres fases y paginación con 723 entradas simuladas, selección entre páginas y layouts de 1440 y 390 px. La prueba Python verifica el recuento a medida que yt-dlp procesa un extractor simulado. Sin descarga externa ni prueba manual con la lista real.
**Archivos:** `clipoteca/api.py`, `clipoteca/engine.py`, `frontend/src/App.tsx`, `frontend/src/App.css`, especificación y pruebas.

### T48 — Pulir la cabecera de Preparar

**Dependencias:** T39, T42 y T47.
**Criterios de aceptación:**
- [x] Título y formulario comparten panel. El título refleja el acento activo y los iconos conservan sus colores.
- [x] Las fuentes compatibles quedan visibles antes de escribir, con disposición compacta sin desbordamiento.
- [x] El formulario conserva el acceso por teclado y el progreso del análisis dentro del panel.

**Resultado:** build, lint, smokes T39/T40 y 96 pruebas Python con 14 subpruebas en el árbol compartido. Capturas del tema dorado revisadas a 1440 y 390 px. El puente de las pruebas de interfaz usa datos simulados.
**Archivos:** `frontend/src/App.tsx`, `frontend/src/App.css`, `tests/ui_smoke_t39.py` y `DESIGN.md`.

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

# Instrucciones para agentes colaboradores

## Antes de empezar

Lee en este orden:

1. `PRODUCT.md` — usuarios, objetivo y decisiones confirmadas.
2. `DESIGN.md` — sistema visual actual.
3. `docs/IMPLEMENTATION_SPEC.md` — comportamiento, arquitectura y límites del MVP.
4. `tasks/plan.md` y `tasks/todo.md` — orden de trabajo y criterios de aceptación.
5. `README.md` — comandos locales y estado visible del proyecto.

Comprueba `git status` antes de editar. No reviertas ni sobrescribas cambios que no hayas hecho.

## Forma de trabajo

- Implementa **una tarea `Txx` por vez**. Lee su dependencia, criterios y archivos previstos antes de modificar código.
- No marques una tarea completa hasta ejecutar y registrar su verificación.
- Mantén la app construible tras cada tarea. Añade o ajusta pruebas junto con el cambio.
- Si una decisión funcional contradice `PRODUCT.md` o `docs/IMPLEMENTATION_SPEC.md`, detente y pregunta al responsable; no inventes una nueva dirección.
- No hagas refactors, funciones, telemetría ni dependencias fuera del alcance de la tarea.
- Al terminar una tarea, informa ID, archivos, pruebas ejecutadas, resultado y bloqueos. Actualiza su casilla en `tasks/todo.md` solo si quedó verificada.
- Trabaja en la rama asignada. No hagas merge, push ni release sin instrucción explícita del responsable.

## Arquitectura obligatoria

- Python es el backend; `pywebview` es la ventana de escritorio; React + TypeScript + Vite son la interfaz local.
- `yt-dlp` se usa mediante su API de Python. **No** construyas comandos de shell con URLs, nombres de archivo o valores del usuario.
- La interfaz solo puede llamar métodos estrechos y tipados del puente de pywebview. No expongas `eval`, ejecución arbitraria, rutas arbitrarias ni objetos internos de Python.
- Análisis y descargas deben ejecutarse fuera del hilo visual. Envía progreso/estados mediante el canal de eventos definido en la especificación.
- Mantén datos y configuración en el equipo. No añadas cuentas, importación de cookies, analítica remota ni telemetría.
- Conserva el tema oscuro premium “Private Collection Archive” de `DESIGN.md`; no vuelvas al concepto industrial descartado.

## Límites de descarga

- Solo para contenido que el usuario posee o está autorizado a guardar.
- No eludas DRM, autenticación, controles de acceso, restricciones privadas ni desafíos del sitio.
- No solicites ni importes cookies o credenciales.
- Una entrada inaccesible debe producir un estado y un mensaje claros; no debe bloquear el resto de la playlist.
- Los nombres y destinos deben sanearse para Windows. Nunca sobrescribas silenciosamente un archivo existente.
- Los datos ficticios de la interfaz solo se permiten en pruebas o modo de desarrollo y deben identificarse claramente; nunca deben aparecer como análisis real en una build de producción.

## Verificación mínima

Ejecuta las verificaciones de la tarea y, cuando corresponda:

```powershell
cd frontend
npm run build
npm run lint
npm test
cd ..
python -m pytest
```

Las pruebas ordinarias no deben descargar archivos reales ni depender de una URL externa. Usa `yt-dlp` simulado para pruebas automatizadas. Una prueba manual real requiere material propio o autorizado y debe identificarse como tal.

## Entrega

No declares el motor, el instalador ni una integración como funcionales sin haberlos ejecutado. En el resumen distingue siempre entre:

- pruebas automatizadas que pasaron;
- pruebas manuales realizadas;
- funcionalidades todavía simuladas o pendientes;
- riesgos y decisiones que requieren al responsable.

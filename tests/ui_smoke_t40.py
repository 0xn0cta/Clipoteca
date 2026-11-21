from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / ".impeccable" / "review"
MOCK_BRIDGE = """
window.mockQueueState = {
  queue: [{
    id: 'failed-disk', batch_id: 'batch-disk', batch_title: 'Viaje de prueba',
    source_url: 'https://www.youtube.com/watch?v=abcdefghijk',
    title: 'Descarga fallida por espacio', duration: 125, status: 'failed',
    progress: 0, speed: null, eta: null,
    error: 'No hay espacio suficiente en el disco de destino. Libera espacio o cambia la carpeta y vuelve a intentarlo.',
    output_path: null, output_paths: [], completed_at: null, download_elapsed_seconds: 18
  }, {
    id: 'downloading-live', batch_id: 'batch-live', batch_title: 'Cola activa',
    source_url: 'https://www.youtube.com/watch?v=lmnopqrstuv',
    title: 'Descarga en curso', duration: 180, status: 'downloading',
    progress: 0.42, downloaded_bytes: 210000, total_bytes: 500000,
    speed: 450000, eta: 35, download_phase: 'video', error: null,
    download_steps: [
      {id: 'video', status: 'active'}, {id: 'audio', status: 'pending'}, {id: 'merge', status: 'pending'}
    ],
    output_path: null, output_paths: [], completed_at: null,
    download_elapsed_seconds: 10,
    download_attempt_started_at: new Date(Date.now() - 55000).toISOString()
  }],
  history: [
    {
      id: 'history-1', batch_id: 'batch-1', batch_title: 'Recopilación de girasoles',
      source_url: 'https://www.youtube.com/watch?v=lmnopqrstuv',
      title: 'Girasoles al atardecer', duration: 102, status: 'completed',
      progress: 1, speed: null, eta: null, error: null,
      output_path: null, output_paths: [],
      completed_at: '2026-06-02T15:35:00+00:00', download_elapsed_seconds: 65
    },
    {
      id: 'history-2', batch_id: 'batch-2', batch_title: 'Clases de guitarra',
      source_url: 'https://youtu.be/abcdefghijk',
      title: 'Acordes básicos', duration: 238, status: 'completed',
      progress: 1, speed: null, eta: null, error: null,
      output_path: null, output_paths: [],
      completed_at: '2026-06-01T09:12:00+00:00', download_elapsed_seconds: 0
    }
  ],
  counts: { active: 2, completed: 2 },
  preferences: {
    destination: 'C:/Users/Test/Downloads/Clipoteca',
    concurrency_mode: 'manual', manual_concurrency: 1, theme_mode: 'dark'
  }
};
window.mockQueuePending = true;
window.mockQueueRelease = null;
window.pywebview = { api: {
  get_app_status: async () => ({
    desktop: true, download_engine_ready: true, ffmpeg_ready: true,
    message: 'mock', tray_available: true
  }),
  get_queue_state: async () => {
    if (window.mockQueuePending) {
      await new Promise((resolve) => { window.mockQueueRelease = resolve; });
    }
    return window.mockQueueState;
  },
  get_preferences: async () => window.mockQueueState.preferences,
  set_preferences: async (values) => {
    Object.assign(window.mockQueueState.preferences, values);
    return { ok: true, preferences: window.mockQueueState.preferences };
  },
  analyze_url: async () => ({
    ok: true, analysis_id: 'mock-analysis', title: 'Playlist de prueba',
    source_url: 'https://www.youtube.com/playlist?list=mock',
    is_playlist: true, extractor: 'youtube',
    items: [{
      id: 'analysis-video', source_id: 'abcdefghijk',
      source_url: 'https://www.youtube.com/watch?v=abcdefghijk',
      title: 'Elemento de preparación', duration: 75, available: true,
      index: 1, thumbnail: null
    }]
  }),
  get_preview: async () => ({ ok: false, error: 'Mock only' }),
  enqueue_batch: async () => ({ ok: true, queued: 1, batch_id: 'mock' }),
  choose_destination: async () => ({ ok: false, cancelled: true }),
  pause_all: async () => ({ ok: true }),
  resume_all: async () => ({ ok: true }),
  cancel_item: async () => ({ ok: true }),
  cancel_all: async () => ({ ok: true }),
  retry_item: async () => ({ ok: true }),
  clear_history: async () => ({ ok: true, removed: 0 }),
  open_history_file: async () => ({ ok: true }),
  continue_in_background: async () => ({ ok: true }),
  pause_and_close: async () => ({ ok: true })
} };
"""


def assert_accent_swatch_contrast(page) -> None:
    ratios = page.locator(".accent-dot").evaluate_all(r"""(dots) => {
        const luminance = (rgb) => {
            const channels = rgb.match(/\d+/g).slice(0, 3).map(Number).map((value) => {
                value /= 255;
                return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
            });
            return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
        };
        return dots.map((dot) => 1.05 / (luminance(getComputedStyle(dot).backgroundColor) + 0.05));
    }""")
    assert len(ratios) == 5 and min(ratios) >= 4.5, ratios


def palette_snapshot(page):
    return page.evaluate("""() => {
        const canvas = document.createElement('canvas').getContext('2d');
        const luminance = (color) => {
            canvas.clearRect(0, 0, 1, 1);
            canvas.fillStyle = color;
            canvas.fillRect(0, 0, 1, 1);
            const [r, g, b] = [...canvas.getImageData(0, 0, 1, 1).data].map((value) => {
                value /= 255;
                return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
            });
            return 0.2126 * r + 0.7152 * g + 0.0722 * b;
        };
        return {
            surfaces: ['.app-shell', '.app-sidebar', '.settings-dialog', '#theme-mode'].map((selector) => {
                const style = getComputedStyle(document.querySelector(selector));
                const values = [luminance(style.backgroundColor), luminance(style.color)].sort((a, b) => b - a);
                return { color: style.backgroundColor, contrast: (values[0] + 0.05) / (values[1] + 0.05) };
            }),
            icons: ['.sidebar-nav-item.is-active svg', '.engine-status-icon'].map((selector) =>
                getComputedStyle(document.querySelector(selector)).color),
        };
    }""")


def assert_palette_change(before, after):
    assert before["icons"] == after["icons"]
    for old, new in zip(before["surfaces"], after["surfaces"], strict=True):
        assert old["color"] != new["color"]
        assert new["contrast"] >= 4.5, new


def main() -> None:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT / "frontend" / "dist"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_port}/"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 920},
                color_scheme="dark",
                reduced_motion="no-preference",
                device_scale_factor=1,
            )
            context.add_init_script(MOCK_BRIDGE)
            page = context.new_page()
            page.goto(base_url, wait_until="networkidle")

            expect(page.locator(".startup-banner")).to_be_visible()
            expect(page.get_by_role("navigation", name="Navegación principal")).to_have_count(0)
            expect(page.locator(".startup-copy strong")).to_have_text("Abriendo Clipoteca")
            assert page.locator(".startup-spinner").evaluate(
                "(el) => getComputedStyle(el).animationName"
            ) == "startup-spin"
            page.evaluate("window.mockQueuePending = false; window.mockQueueRelease()")
            expect(page.locator(".startup-banner")).to_have_count(0)

            sidebar = page.get_by_role("complementary", name="Navegación lateral")
            collapse = page.get_by_role("button", name="Contraer barra lateral")
            expect(collapse).to_have_attribute("aria-expanded", "true")
            expect(sidebar).to_have_css("width", "228px")
            expect(page.locator(".app-shell")).to_have_css("transition-property", "grid-template-columns")
            collapse.press("Enter")
            expand = page.get_by_role("button", name="Expandir barra lateral")
            expect(expand).to_have_attribute("aria-expanded", "false")
            expect(expand).to_be_focused()
            expect(sidebar).to_have_css("width", "72px")
            expect(page.get_by_role("button", name="Preparar", exact=True)).to_have_attribute("aria-current", "page")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(CAPTURES / "t38-sidebar-collapsed.png"))

            engine_status = page.locator(".engine-status")
            expect(engine_status).to_have_attribute("aria-label", "Motor de descargas conectado")
            expect(engine_status.locator(".engine-status-icon")).to_have_count(1)
            assert page.locator(".engine-dot").count() == 0

            page.locator("#source-url").fill("https://www.youtube.com/playlist?list=mock")
            page.get_by_role("button", name="Analizar enlace").click()
            expect(page.get_by_role("heading", name="Playlist de prueba")).to_be_visible()
            expect(page.get_by_role("img", name="Fuente: YouTube")).to_be_visible()

            page.get_by_role("button", name="Cola, 2 descargas activas").click()
            expect(page.locator(".queue-view")).to_have_count(1)
            assert page.locator(".queue-view").evaluate(
                "(el) => getComputedStyle(el).animationName"
            ) == "view-enter"
            expect(page.get_by_role("alert")).to_contain_text("Espacio insuficiente")
            expect(page.get_by_text("Libera espacio en la unidad de destino")).to_be_visible()
            expect(page.locator(".progress-line")).to_contain_text("Descargando pista de vídeo")
            steps = page.get_by_role("list", name="Pasos de la descarga")
            expect(steps.get_by_role("listitem", name="Vídeo, en curso")).to_have_attribute("aria-current", "step")
            expect(steps.get_by_role("listitem", name="Audio, pendiente")).to_be_visible()
            expect(page.locator(".download-timing")).to_contain_text("Transcurrido")
            expect(page.locator(".download-timing")).to_contain_text("Restante en esta fase ≈ 35 s")
            progress_bar = page.get_by_role("progressbar", name="Descarga de Descarga en curso")
            expect(progress_bar).to_have_attribute("aria-valuenow", "42")
            assert progress_bar.locator("span").evaluate(
                "(el) => getComputedStyle(el).transitionProperty"
            ) == "transform"
            page.evaluate("window.mockQueueState.queue[1].total_bytes = null")
            expect(page.locator(".progress-line")).to_contain_text("Progreso indeterminado")
            assert progress_bar.get_attribute("aria-valuenow") is None
            assert progress_bar.locator("span").evaluate(
                "(el) => getComputedStyle(el).animationName"
            ) == "queue-progress-sweep"
            page.evaluate("""Object.assign(window.mockQueueState.queue[1], {
                download_phase: 'audio', total_bytes: 1000, downloaded_bytes: 400, speed: 200, eta: null,
                download_steps: [
                    {id: 'video', status: 'done'}, {id: 'audio', status: 'active'}, {id: 'merge', status: 'pending'}
                ]
            })""")
            expect(page.locator(".progress-line")).to_contain_text("Descargando pista de audio · 40%")
            expect(page.locator(".download-timing")).to_contain_text("Restante en esta fase ≈ 3 s")
            expect(steps.get_by_role("listitem", name="Vídeo, completado")).to_be_visible()
            expect(steps.get_by_role("listitem", name="Audio, en curso")).to_have_attribute("aria-current", "step")
            page.evaluate("""Object.assign(window.mockQueueState.queue[1], {
                download_phase: 'merging', progress: 1, total_bytes: null, speed: null, eta: null,
                download_steps: [
                    {id: 'video', status: 'done'}, {id: 'audio', status: 'done'}, {id: 'merge', status: 'active'}
                ]
            })""")
            expect(page.locator(".progress-line")).to_contain_text("Uniendo vídeo y audio")
            expect(steps.get_by_role("listitem", name="Unir, en curso")).to_have_attribute("aria-current", "step")
            expect(steps.locator('[data-state="done"]')).to_have_count(2)
            steps.screenshot(path=str(CAPTURES / "t17-download-steps.png"))
            expect(page.locator(".download-timing")).to_contain_text("Sin estimación")
            assert progress_bar.get_attribute("aria-valuenow") is None
            expect(page.locator(".queue-elapsed")).to_contain_text("Tiempo descargando: 18 s")
            expect(sidebar).to_have_css("width", "72px")
            expand.press("Enter")
            expect(collapse).to_be_focused()
            expect(sidebar).to_have_css("width", "228px")

            page.get_by_role("button", name="Historial, 2 resultados").click()
            expect(page.get_by_role("searchbox", name="Buscar en el historial")).to_be_visible()
            expect(page.get_by_role("img", name="Fuente: YouTube")).to_have_count(2)
            expect(page.get_by_text("1:42 de video")).to_be_visible()
            expect(page.get_by_text("1 min 5 s")).to_be_visible()
            assert page.locator(".download-row.is-history").first.evaluate(
                "(el) => el.getBoundingClientRect().height"
            ) < 135
            page.screenshot(path=str(CAPTURES / "t40-history-desktop.png"), full_page=True)

            search = page.get_by_role("searchbox", name="Buscar en el historial")
            search.fill("girasoles")
            expect(page.locator(".download-row.is-history")).to_have_count(1)
            expect(page.get_by_role("heading", name="Girasoles al atardecer")).to_be_visible()
            search.fill("sin resultados")
            expect(page.get_by_role("heading", name="No hay coincidencias")).to_be_visible()
            page.get_by_role("button", name="Limpiar búsqueda").click()
            expect(page.locator(".download-row.is-history")).to_have_count(2)

            page.get_by_role("button", name="Ajustes").click()
            expect(page.get_by_role("dialog", name="Ajustes de descarga")).to_be_visible()
            assert page.locator(".dialog-panel").evaluate(
                "(el) => getComputedStyle(el).animationName"
            ) == "dialog-in"
            assert_accent_swatch_contrast(page)
            dark_palette = palette_snapshot(page)
            expect(page.get_by_role("radio", name="Granate")).to_be_checked()
            page.get_by_role("radio", name="Granate").press("ArrowRight")
            expect(page.get_by_role("radio", name="Iris")).to_be_checked()
            expect(page.locator("html")).to_have_attribute("data-accent", "iris")
            assert_palette_change(dark_palette, palette_snapshot(page))
            page.screenshot(path=str(CAPTURES / "t42-accents-dark.png"))
            settings_close = page.get_by_role("button", name="Cerrar ajustes")
            assert settings_close.evaluate("""(button) => {
                const backdrop = button.closest('.modal-backdrop');
                button.click();
                return backdrop.inert && backdrop.getAnimations().some(
                    (animation) => animation.effect.getTiming().duration === 150
                );
            }""")
            expect(page.locator(".modal-backdrop")).to_have_count(0)
            expect(page.get_by_role("button", name="Ajustes")).to_be_focused()
            expect(page.locator("html")).to_have_attribute("data-accent", "clipoteca")

            page.set_viewport_size({"width": 390, "height": 844})
            expect(sidebar).to_have_css("width", "58px")
            expect(collapse).to_have_count(0)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(CAPTURES / "t40-history-compact.png"), full_page=True)
            context.close()

            fast_context = browser.new_context(
                viewport={"width": 1440, "height": 920},
                color_scheme="light",
            )
            fast_context.add_init_script(MOCK_BRIDGE + """
                window.mockQueuePending = false;
                window.mockQueueState.preferences.theme_mode = 'light';
            """)
            fast_page = fast_context.new_page()
            fast_page.clock.install()
            fast_page.goto(base_url, wait_until="domcontentloaded")
            fast_banner = fast_page.locator(".startup-banner")
            expect(fast_banner).to_be_visible()
            expect(fast_banner).to_contain_text("Abriendo Clipoteca")
            expect(fast_page.locator(".startup-spinner")).to_be_visible()
            bounds = fast_banner.bounding_box()
            assert abs(bounds["y"] + bounds["height"] / 2 - 460) < 12
            fast_page.screenshot(path=str(CAPTURES / "t40-startup-fast.png"), animations="disabled")
            fast_page.clock.run_for(800)
            expect(fast_banner).to_be_visible()
            fast_page.clock.run_for(1100)
            expect(fast_banner).to_have_count(0)
            expect(fast_page.get_by_role("heading", level=1)).to_have_text("Prepara tu descarga.")
            options = fast_page.get_by_role("group", name="Formato de salida")
            audio = options.get_by_role("button", name="Audio MP3")
            audio.click()
            expect(audio).to_have_attribute("aria-pressed", "true")
            expect(fast_page.get_by_role("combobox", name="Calidad", exact=False)).to_be_disabled()
            both = options.get_by_role("button", name="Ambos MP4 + MP3")
            both.press("Enter")
            expect(both).to_have_attribute("aria-pressed", "true")
            expect(both).to_have_css("outline-color", "rgb(99, 86, 92)")
            fast_page.screenshot(path=str(CAPTURES / "t40-options-light.png"), full_page=True)
            fast_page.get_by_role("button", name="Ajustes").click()
            assert_accent_swatch_contrast(fast_page)
            light_palette = palette_snapshot(fast_page)
            fast_page.locator(".accent-option").get_by_text("Azul", exact=True).click()
            expect(fast_page.get_by_role("radio", name="Azul")).to_be_checked()
            expect(fast_page.locator("html")).to_have_attribute("data-accent", "blue")
            assert_palette_change(light_palette, palette_snapshot(fast_page))
            fast_page.screenshot(path=str(CAPTURES / "t42-accents-light.png"))
            fast_page.get_by_role("button", name="Guardar ajustes").click()
            expect(fast_page.locator(".modal-backdrop")).to_have_count(0)
            expect(fast_page.locator("html")).to_have_attribute("data-accent", "blue")
            assert fast_page.evaluate("window.mockQueueState.preferences.theme_accent") == "blue"
            toast = fast_page.locator(".toast")
            expect(toast).to_have_text("Ajustes guardados.")
            expect(toast).to_have_css("top", "16px")
            expect(toast).to_have_css("right", "16px")
            toast.hover()
            fast_page.clock.run_for(6100)
            expect(toast).to_be_visible()
            fast_page.mouse.move(400, 200)
            fast_page.clock.run_for(6100)
            expect(toast).to_have_count(0)

            fast_page.get_by_role("button", name="Analizar enlace").click()
            expect(toast).to_have_text("Pega un enlace para analizarlo.")
            toast.get_by_role("button", name="Cerrar aviso").click()
            expect(toast).to_have_count(0)

            fast_page.evaluate("""() => {
                window.pywebview.api.get_queue_state = async () => {
                    throw new Error('Mock polling failure');
                };
            }""")
            fast_page.clock.run_for(1400)
            expect(toast).to_contain_text("No se pudo actualizar la cola")
            fast_page.clock.run_for(7500)
            expect(toast).to_have_count(0)
            fast_context.close()

            reduced_context = browser.new_context(
                viewport={"width": 390, "height": 844},
                color_scheme="dark",
                reduced_motion="reduce",
            )
            reduced_context.add_init_script(MOCK_BRIDGE + """
                window.mockQueuePending = false;
                const engineStatus = window.pywebview.api.get_app_status;
                window.pywebview.api.get_app_status = () => new Promise((resolve) => {
                  window.mockEngineRelease = async () => resolve(await engineStatus());
                });
            """)
            reduced_page = reduced_context.new_page()
            reduced_page.clock.install()
            reduced_page.goto(base_url, wait_until="domcontentloaded")
            reduced_page.wait_for_function("typeof window.mockEngineRelease === 'function'")
            reduced_page.clock.run_for(1900)
            reduced_banner = reduced_page.locator(".startup-banner")
            expect(reduced_banner).to_be_visible()
            expect(reduced_page.get_by_role("heading", level=1)).to_have_count(0)
            spinner_duration = reduced_page.locator(".startup-spinner").evaluate(
                "(el) => Number.parseFloat(getComputedStyle(el).animationDuration)"
            )
            assert spinner_duration <= 0.001, spinner_duration
            reduced_page.screenshot(path=str(CAPTURES / "t40-startup-compact.png"))
            reduced_page.evaluate("window.mockEngineRelease()")
            expect(reduced_page.locator(".startup-banner")).to_have_count(0)
            reduced_page.evaluate("window.mockQueueState.queue[1].total_bytes = null")
            reduced_page.get_by_role("button", name="Cola, 2 descargas activas").click()
            expect(reduced_page.locator(".progress-line")).to_contain_text("Progreso indeterminado")
            assert reduced_page.locator(".progress-line [role=progressbar] span").evaluate(
                "(el) => getComputedStyle(el).animationName"
            ) == "none"
            reduced_page.set_viewport_size({"width": 1440, "height": 920})
            assert reduced_page.locator(".app-shell").evaluate(
                "(el) => Number.parseFloat(getComputedStyle(el).transitionDuration)"
            ) <= 0.001
            reduced_page.get_by_role("button", name="Ajustes").click()
            reduced_page.get_by_role("button", name="Cerrar ajustes").click()
            expect(reduced_page.locator(".modal-backdrop")).to_have_count(0)
            expect(reduced_page.get_by_role("button", name="Ajustes")).to_be_focused()
            reduced_context.close()

            error_context = browser.new_context(
                viewport={"width": 1000, "height": 720},
                color_scheme="dark",
            )
            error_context.add_init_script(MOCK_BRIDGE + """
              window.mockQueuePending = false;
              window.mockFailQueue = true;
              const getQueueState = window.pywebview.api.get_queue_state;
              window.pywebview.api.get_queue_state = async () => {
                if (window.mockFailQueue) throw new Error('Mock startup failure');
                return getQueueState();
              };
            """)
            error_page = error_context.new_page()
            error_page.goto(base_url, wait_until="networkidle")
            expect(error_page.locator(".startup-banner.is-error")).to_be_visible()
            expect(error_page.get_by_role("alert")).to_contain_text("No se pudo iniciar la cola")
            error_page.evaluate("window.mockFailQueue = false")
            error_page.get_by_role("button", name="Reintentar").click()
            expect(error_page.locator(".startup-banner")).to_have_count(0)
            error_context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    print("Startup, status icon, source marks, history search/metadata, disk-space error, motion, and compact layout passed.")


if __name__ == "__main__":
    main()

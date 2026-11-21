from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / ".impeccable" / "review"
THUMBNAIL = "data:image/svg+xml," + quote(
    '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180">'
    '<rect width="320" height="180" fill="#5b2632"/>'
    '<text x="20" y="98" fill="white" font-size="22">Vista de prueba</text></svg>'
)
MOCK_BRIDGE = f"""
const thumbnail = {THUMBNAIL!r};
window.mockEnqueues = 0;
window.pywebview = {{ api: {{
  get_app_status: async () => ({{
    desktop: true, download_engine_ready: true, ffmpeg_ready: true,
    message: 'mock', tray_available: false
  }}),
  get_queue_state: async () => ({{
    queue: [], history: [], counts: {{ active: 0, completed: 0 }},
    preferences: {{
      destination: 'C:/Users/Test/Downloads/Clipoteca',
      concurrency_mode: 'manual', manual_concurrency: 1, theme_mode: 'dark'
    }}
  }}),
  get_preferences: async () => ({{
    destination: 'C:/Users/Test/Downloads/Clipoteca',
    concurrency_mode: 'manual', manual_concurrency: 1, theme_mode: 'dark'
  }}),
  set_preferences: async (values) => ({{ ok: true, preferences: values }}),
  analyze_url: async () => ({{
    ok: true, analysis_id: 'mock-analysis', title: 'Lista de prueba autorizada',
    source_url: 'https://www.youtube.com/playlist?list=mock',
    is_playlist: true, extractor: 'youtube',
    items: [
      {{
        id: 'item-one', source_id: 'abcdefghijk', source_url: 'https://www.youtube.com/watch?v=abcdefghijk',
        title: 'Primer video de prueba', duration: 94, available: true, index: 1, thumbnail
      }},
      {{
        id: 'item-two', source_id: 'lmnopqrstuv', source_url: 'https://www.youtube.com/watch?v=lmnopqrstuv',
        title: 'Segundo video de prueba', duration: 126, available: true, index: 2, thumbnail
      }}
    ]
  }}),
  get_preview: async () => ({{ ok: false, error: 'Not used by the embedded player' }}),
  enqueue_batch: async () => {{ window.mockEnqueues += 1; return {{ ok: true, queued: 1, batch_id: 'mock' }}; }},
  choose_destination: async () => ({{ ok: false, cancelled: true }}),
  pause_all: async () => ({{ ok: true }}),
  resume_all: async () => ({{ ok: true }}),
  cancel_item: async () => ({{ ok: true }}),
  cancel_all: async () => ({{ ok: true }}),
  retry_item: async () => ({{ ok: true }}),
  clear_history: async () => ({{ ok: true, removed: 0 }}),
  open_history_file: async () => ({{ ok: true }}),
  continue_in_background: async () => ({{ ok: true }}),
  pause_and_close: async () => ({{ ok: true }})
}} }};
"""


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
                device_scale_factor=1,
            )
            context.add_init_script(MOCK_BRIDGE)
            page = context.new_page()
            youtube_referers: list[str | None] = []

            def mock_youtube(route) -> None:
                youtube_referers.append(route.request.headers.get("referer"))
                route.fulfill(
                    status=200,
                    content_type="text/html",
                    body=(
                        "<!doctype html><html><body style='margin:0;background:#080607;color:white;"
                        "font:16px Segoe UI;display:grid;place-items:center;height:100vh'>"
                        "<main role='status'>Mock YouTube player</main></body></html>"
                    ),
                )

            page.route("https://www.youtube-nocookie.com/**", mock_youtube)
            page.goto(base_url, wait_until="networkidle")

            page.locator("#source-url").fill("https://www.youtube.com/playlist?list=mock")
            page.get_by_role("button", name="Analizar enlace").click()
            expect(page.get_by_role("heading", name="Lista de prueba autorizada")).to_be_visible()
            expect(page.get_by_role("button", name="Abrir vista previa de Primer video de prueba en YouTube")).to_be_visible()
            expect(page.get_by_role("button", name="Ver selección")).to_have_count(0)
            expect(page.get_by_role("heading", name="Vista previa")).to_be_visible()
            expect(page.get_by_text("Elige una miniatura de la lista para abrir el reproductor integrado.")).to_be_visible()
            thumbnail_size = page.locator(".thumbnail-preview").first.evaluate(
                "(el) => ({ width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height })"
            )
            assert thumbnail_size["width"] >= 120 and thumbnail_size["height"] >= 70, thumbnail_size
            page.screenshot(path=str(CAPTURES / "t39-preview-desktop.png"), full_page=True)

            first_checkbox = page.get_by_role("checkbox", name="Seleccionar Primer video de prueba")
            first_checkbox.uncheck()
            expect(page.get_by_text("1 de 2 seleccionados")).to_be_visible()
            first_thumbnail = page.get_by_role(
                "button", name="Abrir vista previa de Primer video de prueba en YouTube",
            )
            preview_panel = page.get_by_role("region", name="Vista previa")
            first_thumbnail.press("Enter")
            player = page.get_by_title("Reproductor de YouTube: Primer video de prueba")
            expect(player).to_have_attribute(
                "src",
                "https://www.youtube-nocookie.com/embed/abcdefghijk?playsinline=1&rel=0",
            )
            expect(player).to_have_attribute("referrerpolicy", "strict-origin-when-cross-origin")
            expect(page.frame_locator("iframe").get_by_text("Mock YouTube player")).to_be_visible()
            assert youtube_referers and youtube_referers[-1].startswith("http://127.0.0.1:"), youtube_referers
            expect(first_thumbnail).to_have_attribute("aria-current", "true")
            expect(preview_panel).to_be_focused()
            player_size = player.evaluate(
                "(el) => ({ width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height })"
            )
            assert player_size["width"] >= 200 and player_size["height"] >= 200, player_size
            player_insets = page.locator(".preview-player").evaluate("""(element) => {
                const player = element.getBoundingClientRect();
                const panel = element.parentElement.getBoundingClientRect();
                return [player.left - panel.left, panel.right - player.right];
            }""")
            assert min(player_insets) >= 12 and abs(player_insets[0] - player_insets[1]) <= 1, player_insets
            expect(first_checkbox).not_to_be_checked()
            expect(page.get_by_text("1 de 2 seleccionados")).to_be_visible()
            expect(page.locator(".preview-metadata")).to_contain_text("1:34")
            assert page.evaluate("window.mockEnqueues") == 0

            request_count = len(youtube_referers)
            first_thumbnail.click()
            expect(page.get_by_text("Conectando con YouTube…")).to_have_count(0)
            assert len(youtube_referers) == request_count

            page.get_by_role("button", name="Cerrar vista previa").press("Enter")
            expect(page.get_by_title("Reproductor de YouTube: Primer video de prueba")).to_have_count(0)
            expect(first_thumbnail).to_be_focused()
            expect(first_thumbnail).not_to_have_attribute("aria-current", "true")
            page.get_by_role("button", name="Abrir vista previa de Segundo video de prueba en YouTube").click()
            second_player = page.get_by_title("Reproductor de YouTube: Segundo video de prueba")
            assert "lmnopqrstuv" in second_player.get_attribute("src")

            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            first_thumbnail.click()
            expect(preview_panel).to_be_in_viewport(ratio=0.8)
            expect(page.frame_locator("iframe").get_by_text("Mock YouTube player")).to_be_visible()
            expect(first_checkbox).not_to_be_checked()
            page.screenshot(path=str(CAPTURES / "t39-preview-compact.png"), full_page=True)

            page.evaluate("""() => {
                const analyze = window.pywebview.api.analyze_url;
                window.pywebview.api.analyze_url = async (source_url) => {
                    const sample = await analyze();
                    return {
                        ...sample, source_url, is_playlist: false,
                        items: [{ ...sample.items[0], source_url }],
                    };
                };
            }""")
            for platform, url in (
                ("Instagram", "https://www.instagram.com/reel/mock/"),
                ("Reddit", "https://www.reddit.com/r/demo/comments/mock/"),
            ):
                page.locator("#source-url").fill(url)
                page.get_by_role("button", name="Analizar enlace").click()
                expect(page.get_by_role("img", name=f"Fuente: {platform}")).to_be_visible()
                page.get_by_role(
                    "button", name=f"Abrir vista previa de Primer video de prueba en {platform}",
                ).click()
                expect(preview_panel.get_by_text("Miniatura de la publicación.")).to_be_visible()
                expect(preview_panel.locator("iframe")).to_have_count(0)

            page.set_viewport_size({"width": 1440, "height": 920})
            page.evaluate("""(thumbnail) => {
                const api = window.pywebview.api;
                api.analyze_url = (source_url, requestId) => new Promise((resolve) => {
                    window.analysisRequest = requestId;
                    window.finishAnalysis = () => resolve({
                        ok: true, analysis_id: 'large', title: 'Catálogo de prueba', source_url,
                        is_playlist: true, extractor: 'youtube',
                        items: Array.from({ length: 723 }, (_, index) => ({
                            id: `entry-${index}`, source_id: 'abcdefghijk', source_url,
                            title: index === 0 ? 'Un título muy largo para comprobar cómo se reparte el texto en la fila del catálogo' : `Vídeo ${index + 1}`,
                            duration: 94, available: true, index: index + 1, thumbnail,
                        })),
                    });
                });
                window.analysisProgress = { phase: 'validating', found: 0 };
                api.get_analysis_progress = async (requestId) => (
                    requestId === window.analysisRequest ? window.analysisProgress : null
                );
            }""", THUMBNAIL)
            page.locator("#source-url").fill("https://www.youtube.com/playlist?list=large")
            page.get_by_role("button", name="Analizar enlace").click()
            progress = page.locator(".analysis-progress")
            expect(progress.locator('[aria-current="step"]')).to_have_text("Comprobar enlace")
            expect(progress.get_by_role("status")).to_contain_text("Esperando resultados…")
            page.evaluate("window.analysisProgress = { phase: 'extracting', found: 48 }")
            expect(progress.locator('[aria-current="step"]')).to_have_text("Encontrar vídeos")
            expect(progress.get_by_role("status")).to_contain_text("48 vídeos encontrados")
            page.screenshot(path=str(CAPTURES / "t47-analysis-desktop.png"))
            page.evaluate("window.analysisProgress = { phase: 'preparing', found: 723 }")
            expect(progress.locator('[aria-current="step"]')).to_have_text("Preparar lista")
            expect(progress.get_by_role("status")).to_contain_text("723 vídeos encontrados")
            page.evaluate("window.finishAnalysis()")
            expect(progress).to_have_count(0)
            expect(page.get_by_text("723 vídeos encontrados", exact=True)).to_be_visible()
            paging = page.get_by_role("navigation", name="Páginas de la playlist")
            rows = page.locator(".media-list tbody tr")
            expect(rows).to_have_count(25)
            assert rows.first.locator(".thumbnail-preview").bounding_box()["height"] + 18 <= rows.first.bounding_box()["height"]
            expect(rows.first.locator("img")).to_have_attribute("loading", "lazy")
            rows.first.get_by_role("checkbox").uncheck()
            next_page = paging.get_by_role("button", name="Página siguiente")
            next_page.click()
            expect(paging.get_by_role("status")).to_have_text("Vídeos 26–50 de 723")
            expect(page.get_by_text("722 de 723 seleccionados")).to_be_visible()
            paging.get_by_role("button", name="Página anterior").click()
            expect(rows.first.get_by_role("checkbox")).not_to_be_checked()
            page.screenshot(path=str(CAPTURES / "t47-playlist-desktop.png"))
            for _ in range(28):
                next_page.click()
            expect(paging.get_by_role("status")).to_have_text("Vídeos 701–723 de 723")
            expect(rows).to_have_count(23)
            expect(next_page).to_be_disabled()
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            paging.scroll_into_view_if_needed()
            page.screenshot(path=str(CAPTURES / "t47-playlist-compact.png"))

            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    print("Playlist thumbnails, embedded player, analysis progress, and pagination passed at desktop and compact sizes.")


if __name__ == "__main__":
    main()

---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

# Clipoteca — compact desktop media workspace

## Scope and mode

Redesign the existing Windows desktop application shell and its preparation, queue, history, settings, and preview surfaces. Mode: Operate. Preserve working download behavior and product truth while replacing the current top-navigation/blue-ink/purple visual system.

## Audience, job, action, and content

An individual Windows user manages YouTube videos and playlists they own or are authorized to save. The user pastes a URL, reviews an ordered playlist, previews a selected item when the source permits it, chooses output options and destination, then follows the queue and history. The key information is item title, duration, availability, selection, preview and per-item outcome.

## Constraints

Spanish UI; Python + pywebview; React + TypeScript + Vite. Keep YouTube-only, no cookies/authentication/DRM bypass, no remote app services, and no invented playlist data. Preserve analysis, preview, format, quality, destination, queue, retry, history, tray and first-run concurrency functions. The interface should feel familiar to video viewers without using YouTube branding, logo, exact layout, copied labels or trade dress. Provide system theme detection plus a persistent manual Claro/Oscuro override. Keep the UI compact and responsive in small, maximized and fullscreen windows.

## Chosen direction and memorable moment

User-pinned direction: a Clipoteca media workspace with familiar video-product grammar—navigation rail, visible preview/player, item metadata and an ordered list—reinterpreted for reviewing and saving authorized media. The memorable moment is selecting a playlist item and seeing its real preview beside the exact output choices before the user commits the download.

## Open decisions

The precise fullscreen affordance and responsive sidebar collapse behavior should be resolved during the first implementation slice and verified in the running Windows app. The preview remains best-effort and must never save media.

## Direction contract

THESIS: Clipoteca turns an authorized YouTube link into a reviewed local collection, with a familiar video workspace that makes the saving action—not passive streaming—the purpose.

OWN-WORLD: A deep charcoal/near-black ground with restrained oxblood/red index and progress marks, white text and neutral gray buttons. The OS theme is followed by default; the user may explicitly choose dark or light. Use familiar media affordances (player, metadata, ordered playlist) but Clipoteca's own mark, copy, iconography, spacing and composition; never reproduce YouTube's logo or exact screen.

STORY: Paste a source, inspect its ordered items, select one or more, preview the chosen item, choose format/quality/destination, then follow its status in the persistent queue and history.

FIRST VIEWPORT: A compact, collapsible left sidebar holds Preparar, Cola and Historial, with Ajustes at the bottom. The preparation workspace places the source field first, then a playlist-first list on the left and a selected-item preview with compact format/quality/destination controls on the right; the primary download action stays unmistakable. At narrow widths the sidebar collapses and the list/preview reflow without horizontal scrolling. At maximized/fullscreen widths the workspace uses available space without stretching content into an unreadable wall.

FORM: User-pinned “Clipoteca Media Desk”—familiar video-product interaction patterns, not copied branding. The concept-seed run was 97c2994e; the user's explicit direction overrides the rolled form. Build path: code-led.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

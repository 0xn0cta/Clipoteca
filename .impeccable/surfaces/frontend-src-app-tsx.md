---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

# Clipoteca — first desktop surface

## Scope and mode

First-run download preparation and playlist review surface. Mode: Operate. This is a full visual-world replacement; the previous Media Ingest Workbench is an anti-reference, not an incumbent to preserve.

## Audience, job, action, and content

An individual Windows user pastes a video or playlist URL, inspects what will be downloaded, previews the selected item when the source allows it, chooses output settings, and starts a download batch. The playlist remains a legible list with title, duration, availability, and selection. Real analysis results must never be presented as synthetic sample data.

## Constraints

Spanish UI, dark appearance, Python + pywebview desktop shell, React + TypeScript + Vite renderer. Preserve the task flow and controls. Replace the dense industrial-console impression with a modern, premium personal-archive experience. Keep playlist checkboxes comfortably inset from the list edge, provide a selected-item preview, and allow opening completed files from history. The user approved a code-first workflow; no image comps are required.

## Chosen direction and memorable moment

Selected direction: IMPECCABLE’S PICK — the Private Collection Archive. Treat a source URL as the beginning of a personal collection, not an ingest operation. The playlist becomes a spacious catalog of selected media, while format, quality, and destination read as quiet collection preferences. Use Manrope throughout, with weight and scale—not a serif contrast—to establish hierarchy. Memorable moment: analyzing a source reveals a clear preview and an ordered selection before saving.

## Open decisions

The bridge, download queue, history, preview, file-open action, and Windows tray are now part of the functional implementation. The preview is best-effort and depends on the source's directly playable formats.

## Direction contract

THESIS: Clipoteca turns a URL into a considered personal collection entry, with every playlist choice visible before saving.

OWN-WORLD: A dark private archive inspired by premium catalogues: deep blue-ink ground, soft ivory text, a restrained muted iris accent, consistent Manrope sans typography, generous spacing, soft corners, and few visible rules. The previous orange industrial workbench, dense control grid, and numbered operations aesthetic are the anti-reference.

STORY: Paste a source, inspect its playlist as a calm collection list, choose format, quality, and destination, then save the selected items.

FIRST VIEWPORT: At desktop width, a quiet top bar holds the Clipoteca wordmark and simple navigation. The main content begins with a generous title and one wide source field. Below it, a spacious playlist list occupies the primary column, with title, duration, selection, and availability in each row; selected checkboxes are inset from the list boundary. A compact collection-options panel sits beside it. A selected item can be previewed before the enabled save action anchors the lower edge. Empty state copy must not imply that fake playlist data is real.

FORM: IMPECCABLE’S PICK, the grounded Private Collection Archive; seed key a6739c2f, mode Operate, code-first. Its strength is a more personal, premium feeling; its honest risk is reading like a streaming library if the download action is not unmistakable.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

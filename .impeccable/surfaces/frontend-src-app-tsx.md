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

An individual Windows user pastes a video or playlist URL, inspects what will be downloaded, chooses items and output settings, and starts a download batch. The playlist remains a legible list with title, duration, availability, and selection. Synthetic rows must be identified as demonstration data.

## Constraints

Spanish UI, dark appearance, Python + pywebview desktop shell, React + TypeScript + Vite renderer. Preserve the task flow and controls. Replace the dense industrial-console impression with a modern, premium personal-archive experience. Do not imply a demo download is real. The user approved a code-first workflow; no image comps are required.

## Chosen direction and memorable moment

Selected direction: IMPECCABLE’S PICK — the Private Collection Archive. Treat a source URL as the beginning of a personal collection, not an ingest operation. The playlist becomes a carefully typeset, spacious catalog of selected media, while format, quality, and destination read as quiet collection preferences. Memorable moment: analyzing a source reveals a clean playlist preview that feels ready to file without losing the download action or the source context.

## Open decisions

Real yt-dlp integration, download history, exact default destination, and exact default concurrency are not part of this visual redesign. Keep room to connect the real Python bridge later.

## Direction contract

THESIS: Clipoteca turns a URL into a considered personal collection entry, with every playlist choice visible before saving.

OWN-WORLD: A dark private archive inspired by premium art-book catalogues: deep blue-ink ground, soft ivory text, a restrained muted iris accent, editorial display typography paired with a clear contemporary sans, generous spacing, soft corners, and few visible rules. The previous orange industrial workbench, dense control grid, and numbered operations aesthetic are the anti-reference.

STORY: Paste a source, inspect its playlist as a calm collection list, choose format, quality, and destination, then save the selected items.

FIRST VIEWPORT: At desktop width, a quiet top bar holds the Clipoteca wordmark and simple navigation. The main content begins with a generous title and one wide source field. Below it, a spacious playlist list occupies the primary column, with title, duration, selection, and availability in each row; a compact collection-options panel sits beside it. The final save action anchors the lower edge and remains visibly disabled in the prototype. The sample playlist is explicitly marked as fictional and unlinked to the empty URL field.

FORM: IMPECCABLE’S PICK, the grounded Private Collection Archive; seed key a6739c2f, mode Operate, code-first. Its strength is a more personal, premium feeling; its honest risk is reading like a streaming library if the download action is not unmistakable.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

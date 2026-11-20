---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

# Clipoteca — first desktop surface

## Scope and mode

First-run download preparation and playlist review surface. Mode: Operate.

## Audience, job, action, and content

An individual Windows user pastes a video or playlist URL, inspects what will be downloaded, chooses items and output settings, and starts a download batch. The primary proof is the playlist ledger itself: item selection, duration, availability, and per-item progress are visible. Synthetic rows must be visibly identified as demonstration data.

## Constraints

Spanish UI, dark appearance, Python + pywebview desktop shell, React + TypeScript + Vite renderer. Keep the playlist legible and the settings explicit. Do not imply a demo download is real. The user approved a code-first workflow; no image comps are required for this build.

## Chosen direction and memorable moment

Selected direction: IMPECCABLE’S PICK — the Media Ingest Workbench. A URL becomes a named batch, then a numbered ledger of media items whose states remain visible through the whole workflow. Memorable moment: selecting a playlist makes its complete, ordered manifest appear beside output controls without losing the source URL or the overall batch status.

## Open decisions

Real yt-dlp integration, download history, exact default destination, and exact default concurrency are not part of this first visual increment. The design must leave room to connect the real Python bridge later.

## Direction contract

THESIS: Clipoteca turns a pasted URL into a visible ingest batch; playlists are inspectable manifests, not opaque jobs.

OWN-WORLD: A dark media-ingest workbench: flat graphite planes, precise ruled divisions, numbered rows, restrained signal-orange marks, and clear operational typography. The user-pinned dark appearance translates the seed’s dense utility grammar without copying its light palette.

STORY: Paste a source, inspect and select its items, set format, quality, and destination, then follow each item through the queue.

FIRST VIEWPORT: At a desktop window, a narrow navigation rail anchors the left edge; the upper workspace holds the URL field and analysis action; the central wide ledger shows playlist title, selection, duration, and status; a right-hand output rail holds MP4/MP3, quality, and destination; one strong bottom action starts the selected batch. The controls and list remain visible together.

FORM: IMPECCABLE’S PICK, the grounded Media Ingest Workbench; seed key 87d72b47, mode Operate, code-first. Its strength is task clarity; its honest risk is resembling a professional media-ingest tool.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

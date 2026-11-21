# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python application packaged for Windows, with pywebview as the desktop shell and a React + TypeScript + Vite local interface. yt-dlp handles media downloads; FFmpeg is planned for media merging and MP3 conversion.

## Users

Individual Windows users who want to download videos and playlists they own or are authorized to save.

## Product Purpose

Clipoteca provides a desktop workflow for preparing, managing, and reviewing video and playlist downloads. Success means users can understand what will be downloaded, choose the intended files and options, and see clear progress and outcomes.

## Positioning

Clipoteca is playlist-first: users inspect playlist contents, choose which items to download, and track outcomes per item rather than treating a playlist as one opaque download.

## Operating Context

The first release targets Windows. A user pastes a video or playlist URL, reviews the available items, chooses media output and quality, selects a destination, and monitors the download queue.

## Capabilities and Constraints

- First release is for Windows; the interface is in Spanish.
- The UI is modern and dark; the approved visual direction is documented in `DESIGN.md`.
- Support video, audio, or both: MP4 video and MP3 audio.
- Prefer the best available quality by default, with a selector for available qualities.
- Use `Descargas/Clipoteca` as the initial destination, remember it, and allow changing it for a download.
- Put playlist files in a subfolder named after the playlist.
- Offer a selected-item preview before downloading, using artwork and direct audio/video playback when the source supports it; preview playback does not save a file.
- Let users open a completed output from history with its Windows default application.
- Skip existing duplicate files and notify the user; do not silently overwrite.
- Ask for concurrency mode on first launch and remember the user’s choice. Manual mode has no application-imposed maximum; automatic mode adapts to observed throughput and uses a ceiling explicitly chosen by the user. Do not silently default to a ceiling.
- Keep completed items in a separate, manually clearable history. Failed items remain in the active queue for individual retries and stay linked to their original batch.
- On close with queued or active downloads, offer continue-in-background (tray), pause-and-close (preserve partial files), or return to the app. The Windows tray can open the app, pause/resume, cancel, and exit.
- Persist queue state locally and recover interrupted downloads as paused so the user can resume them. Cancellation removes only the incomplete temporary file; clearing history never deletes downloaded media.
- Show user-facing Spanish errors and retain a local technical log for debugging.
- FFmpeg is planned to ship with the Windows installer; distribution licensing and notices must be checked before release.
- Automatic retry policy is three retries for transient errors; continue the batch after an item fails and leave failed items available for manual retry. Validate partial-file resume behavior against real sites during Windows testing.
- FFmpeg packaging, licensing, and final Windows installer details remain to be verified.
- Scope is publicly accessible YouTube videos/playlists, Instagram Reels and single-video posts, and Reddit video posts the user owns or is authorized to save. Authentication, cookie import, and DRM circumvention are out of scope.

## Brand Commitments

- Product name: Clipoteca.
- Voice and interface language: Spanish.
- The user wants a modern desktop application and has asked that Impeccable guide the interface work.

## Evidence on Hand

The current interface and desktop screenshot are in `frontend/src/` and `docs/screenshots/clipoteca-desktop.png`. The first vector logo direction is in `docs/brand/`; it is still a draft pending owner approval. Playlist rows shown before source analysis are fictional only. No user research or licensed media assets are on hand.

## Product Principles

- Make playlist contents and per-item outcomes visible.
- Keep the download workflow understandable before, during, and after a job.
- Prefer explicit choices and clear recovery over silent behavior.
- Keep media processing local to the Windows application.

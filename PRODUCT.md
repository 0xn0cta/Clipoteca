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
- Skip existing duplicate files and notify the user; do not silently overwrite.
- Ask for the download concurrency on first launch, remember the choice, and allow changing it later. Do not impose an application-level maximum.
- FFmpeg is planned to ship with the Windows installer; distribution licensing and notices must be checked before release.
- Scope is limited to content the user owns or is authorized to download. No DRM circumvention or authentication/cookie import is in scope.
- Playlist failure recovery, cancellation/resume behavior, queue recovery after restart, and final installer details are specified for implementation and must be verified by tests.

## Brand Commitments

- Product name: Clipoteca.
- Voice and interface language: Spanish.
- The user wants a modern desktop application and has asked that Impeccable guide the interface work.

## Evidence on Hand

The current interface prototype lives in `frontend/src/` and its latest desktop screenshot is `docs/screenshots/clipoteca-desktop.png`. Playlist rows shown in the prototype are fictional demonstration data, not analyzed YouTube content. No user research or licensed media assets are on hand.

## Product Principles

- Make playlist contents and per-item outcomes visible.
- Keep the download workflow understandable before, during, and after a job.
- Prefer explicit choices and clear recovery over silent behavior.
- Keep media processing local to the Windows application.

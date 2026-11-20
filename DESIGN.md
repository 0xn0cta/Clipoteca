---
name: Clipoteca
description: A private, playlist-first archive for authorized media downloads.
colors:
  primary: "#B7A6E3"
  neutral-bg: "#131621"
  ink-raised: "#171B27"
  surface: "#1B202D"
  surface-raised: "#222736"
  border: "#303545"
  border-strong: "#414658"
  text-primary: "#F0EEE9"
  text-secondary: "#C5C3CC"
  text-muted: "#A1A1AF"
  success: "#9AC8B4"
  unavailable: "#C994A2"
  text-on-primary: "#211D2A"
typography:
  display:
    fontFamily: "Instrument Serif, Georgia, serif"
    fontSize: "clamp(42px, 4.8vw, 60px)"
    fontWeight: 400
    lineHeight: 0.98
    letterSpacing: "-0.035em"
  body:
    fontFamily: "Manrope, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Manrope, Segoe UI, sans-serif"
    fontSize: "10px"
    fontWeight: 600
rounded:
  sm: "8px"
  md: "11px"
  lg: "16px"
  pill: "100px"
spacing:
  xs: "5px"
  sm: "10px"
  md: "16px"
  lg: "22px"
  xl: "34px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.text-on-primary}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "40px"
  input-url:
    backgroundColor: "{colors.ink-raised}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "0 15px"
    height: "54px"
  nav-active:
    textColor: "{colors.text-primary}"
    height: "76px"
  sample-chip:
    backgroundColor: "#211F2A"
    textColor: "#C7B8E7"
    rounded: "{rounded.pill}"
    padding: "5px 9px"
  preferences-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    padding: "23px"
  playlist-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    height: "71px"
  format-option:
    backgroundColor: "#2B2737"
    textColor: "#E1D6F4"
    rounded: "{rounded.sm}"
    height: "50px"
---

# Design System: Clipoteca

## Overview

**Creative North Star: "The Private Collection Archive"**

Clipoteca feels like a carefully kept personal media collection, not a broadcast console or an industrial control surface. The interface gives the source URL a clear place, then lets the playlist read like a considered catalogue: roomy rows, quiet metadata, and unmistakable choices.

The dark blue-ink setting remains calm rather than dramatic. Instrument Serif brings an editorial note to the main titles; Manrope keeps controls and media details direct. Muted iris marks the selected state and the primary action without turning the whole screen into an accent-colored dashboard.

**Key Characteristics:**
- Personal archive mood with an editorial display voice.
- Dark blue-ink surfaces and soft ivory text.
- Muted iris accent for selected and primary states.
- Playlist rows remain explicit, ordered, and easy to scan.
- Prototype content and unavailable items are clearly disclosed.

## Colors

The palette uses deep blue ink, soft ivory type, a restrained iris accent, and quiet status colors.

### Primary
- **Muted Iris** (`#B7A6E3`): Active navigation, selected formats, checked items, and the main analysis action.

### Secondary
- **Quiet Success Mint** (`#9AC8B4`): Available items and successful states.
- **Muted Rose** (`#C994A2`): Unavailable items and errors that need attention.

### Neutral
- **Blue-Ink Ground** (`#131621`): Main application canvas.
- **Raised Ink** (`#171B27`): Inset source and preference controls.
- **Collection Surface** (`#1B202D`): Preference panel and grouped work areas.
- **Lifted Surface** (`#222736`): Hover and transient surfaces.
- **Fine Border** (`#303545`): Quiet structural separation.
- **Strong Border** (`#414658`): Input boundaries and panel outlines.
- **Soft Ivory** (`#F0EEE9`): Main titles and item names.
- **Warm Secondary Ink** (`#C5C3CC`): Supporting descriptions and important metadata.
- **Muted Ink** (`#A1A1AF`): Secondary labels and guidance.

**The Iris Restraint Rule.** Muted iris marks an action or a selected state; it does not decorate every surface.

## Typography

**Display Font:** Instrument Serif (with Georgia, serif fallback)

**Body Font:** Manrope (with Segoe UI, sans-serif fallback)
**Label/Mono Font:** Manrope; tabular numerals are used for durations and counts.

**Character:** Instrument Serif gives the collection a quiet editorial voice. Manrope keeps operational choices crisp and familiar, so the premium tone never makes the controls feel precious.

### Hierarchy
- **Display** (400, `clamp(42px, 4.8vw, 60px)`, `0.98`): Main page title.
- **Headline** (400, `30px`, `1`): Playlist and empty-state headings.
- **Title** (600, `12–14px`, `1.3`): Media names and preference labels.
- **Body** (400, `12–14px`, `1.55`): Instructions and supporting copy.
- **Label** (600, `9–12px`, normal tracking): Form labels, metadata, and status text.

## Layout

The desktop surface has a quiet top navigation and a centered work area. The source field spans the page; below it, the playlist occupies the broad column and collection preferences sit beside it. The selected-item action is separated at the bottom rather than mixed into the playlist.

Playlist rows retain title, duration, selection, and status. On narrow windows, rows stack metadata beneath the title and preferences move below the list; the source and action remain easy to find. The main content uses a centered maximum width, with the desktop grid collapsing at `850px` and the compact navigation treatment at `620px`.

Spacing is generous between the page title, source, playlist, and preference panel. Controls stay grouped; content lists use quiet row dividers rather than dense grids.

## Elevation & Depth

The interface relies on tonal surface changes, soft corners, and fine borders. It avoids floating stacks and decorative glows. A soft shadow is reserved for transient notices.

**The Quiet Surface Rule.** Panels are distinguished by one tonal step and one outline; do not nest containers to manufacture hierarchy.

## Shapes

Controls use soft, rounded corners (`8–11px`); larger preference surfaces use a calm `16px` radius. Navigation uses a simple underline, and selected formats use a quiet inset surface rather than a dense segmented-console treatment.

## Components

### Buttons
- **Shape:** Softly rounded (`8px`) for actions; pill silhouette for the disabled final action.
- **Primary:** Muted iris with dark ink, clear verbs, and a visible icon where it aids recognition.
- **Hover / Focus:** A slight upward shift on the primary action; focus uses a clear two-pixel outline offset from the control.
- **Secondary / Ghost:** Text-only at rest; color strengthens on hover.

### Chips
- **Style:** Quiet pill labels with a low-contrast border and muted iris text.
- **State:** “Muestra” labels synthetic content; it does not stand in for download progress or availability.

### Cards / Containers
- **Corner Style:** `16px` for the collection-preferences surface.
- **Background:** One tonal step above the page ground.
- **Shadow Strategy:** Flat at rest; only transient notices lift.
- **Border:** Fine, low-contrast outline.
- **Internal Padding:** Approximately `22px`.

### Inputs / Fields
- **Style:** Inset blue-ink field with a subtle border and `11px` corners.
- **Focus:** Border shifts toward muted iris; keyboard focus remains visible.
- **Error / Disabled:** Keep controls legible, name the state, and explain the next action.

### Navigation
- **Style:** A quiet top bar with a wordmark, two task views, and settings.
- **Hover / Active:** Active view uses ivory text and a slim iris underline; secondary navigation remains muted.
- **Narrow Windows:** Keep both task views accessible and reduce only secondary status text.

### Playlist Row
Each row preserves the playlist's order while presenting its title, duration, selection, and availability with generous vertical rhythm.

## Do's and Don'ts

### Do:
- **Do** make the source URL and primary analysis action the first clear task.
- **Do** give playlist titles room to breathe and keep duration and availability aligned.
- **Do** identify sample content and unimplemented actions honestly.
- **Do** use muted iris for focus and selection, not for broad decoration.

### Don't:
- **Don't** return to the previous dense industrial-console composition.
- **Don't** use poster-wall browsing as the default playlist layout.
- **Don't** make editorial typography smaller or denser than operational text can support.
- **Don't** imply sample metadata or destination settings are already saved.

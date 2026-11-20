---
name: Clipoteca
description: A playlist-first desktop workspace for preparing authorized media downloads.
colors:
  primary: "#E6A45F"
  neutral-bg: "#111613"
  sidebar-bg: "#141A16"
  surface: "#1A211D"
  surface-hover: "#202722"
  border: "#2A332D"
  border-strong: "#3A453D"
  text-strong: "#F0F2ED"
  text-primary: "#DCE1DC"
  text-secondary: "#B3BDB4"
  text-muted: "#99A49B"
  text-faint: "#7C8980"
  success: "#92BF9A"
  ink-on-primary: "#211810"
typography:
  display:
    fontFamily: "Barlow, Segoe UI, sans-serif"
    fontSize: "clamp(28px, 2.4vw, 36px)"
    fontWeight: 650
    lineHeight: 1.05
    letterSpacing: "-0.045em"
  body:
    fontFamily: "Barlow, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Barlow, Segoe UI, sans-serif"
    fontSize: "9px"
    fontWeight: 700
    letterSpacing: "0.12em"
rounded:
  xs: "3px"
  sm: "4px"
  md: "6px"
  lg: "9px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.ink-on-primary}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "36px"
  input-url:
    backgroundColor: "{colors.sidebar-bg}"
    textColor: "{colors.text-strong}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "49px"
  nav-active:
    backgroundColor: "{colors.surface-hover}"
    textColor: "{colors.text-strong}"
    rounded: "{rounded.md}"
    padding: "0 11px"
    height: "42px"
  demo-chip:
    backgroundColor: "#2A241D"
    textColor: "#E4B981"
    rounded: "{rounded.xs}"
    padding: "3px 5px"
  playlist-row:
    backgroundColor: "#1B241F"
    textColor: "{colors.text-primary}"
    height: "53px"
  format-option:
    backgroundColor: "#171D19"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.xs}"
    height: "47px"
  output-rail:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "17px 16px"
---

# Design System: Clipoteca

## Overview

**Creative North Star: "The Media Ingest Workbench"**

Clipoteca treats every URL as a batch that can be inspected and managed. The interface borrows the clarity of a media-ingest ledger: ordered entries, visible status, explicit output controls, and no hidden steps. Its dark appearance is grounded in a Windows desktop work session, not in a generic “tech” aesthetic.

Graphite-green surfaces and fine rules keep the manifest readable; warm signal orange marks the active choice and primary action. The system is dense enough to make playlist work practical, but every state remains legible and honest. Demonstration content is labeled as such until a real source is analyzed.

**Key Characteristics:**
- Playlist ledger before decorative media cards.
- Dark graphite-green planes with fine structural divisions.
- Signal orange reserved for active and actionable states.
- Clear, numbered media rows and tabular durations.
- Prototype and availability states are explicit.

## Colors

The palette pairs a green-black desktop ground with a warm amber-orange signal and a restrained green success state.

### Primary
- **Signal Orange** (`#E6A45F`): Active navigation, selected formats, and the primary analysis action.

### Secondary
- **Quiet Success Green** (`#92BF9A`): Available and successful media states.

### Neutral
- **Green-Black Ground** (`#111613`): Main application canvas.
- **Sidebar Green-Black** (`#141A16`): Persistent navigation rail.
- **Workbench Surface** (`#1A211D`): Output rail and contained controls.
- **Raised Surface** (`#202722`): Hover and active navigation surfaces.
- **Fine Rule** (`#2A332D`): Quiet separators between related regions.
- **Structural Rule** (`#3A453D`): Panel outlines and stronger boundaries.
- **Primary Ink** (`#F0F2ED`): Main headings and the most important labels.
- **Body Ink** (`#DCE1DC`): Primary content such as media titles.
- **Secondary Ink** (`#B3BDB4`): Supporting descriptions.
- **Muted Ink** (`#99A49B`): Lower-priority labels and values.
- **Faint Ink** (`#7C8980`): Metadata and tertiary guidance.

**The Signal Rarity Rule.** Orange belongs to a selected state, a primary action, or a meaningful status—not to decoration.

## Typography

**Display Font:** Barlow (with Segoe UI, sans-serif fallback)

**Body Font:** Barlow (with Segoe UI, sans-serif fallback)
**Label/Mono Font:** Barlow; tabular numerals are used for durations and counts.

**Character:** Barlow keeps operational information compact without making it feel like code. Weight and scale, rather than a second display family, establish hierarchy.

### Hierarchy
- **Display** (650, `clamp(28px, 2.4vw, 36px)`, `1.05`): Main page title.
- **Headline** (650, `18px`, `1.2`): Empty-state and secondary view headings.
- **Title** (650, `15px`, `1.2`): Workbench section titles.
- **Body** (400, `13px`, `1.45`): Supporting instructions and descriptions.
- **Label** (700, `9–11px`, tracked): Form labels, metadata, and state markers; uppercase is reserved for compact utility labels.

## Layout

The desktop workspace uses a persistent left rail, a flexible source-and-manifest area, and a narrow output rail. At the first screen, URL, playlist, and output settings are visible together. The download action anchors the lower edge without obscuring the manifest.

The playlist is a ledger, not a grid of equal cards. Number, title, duration, selection, and availability align in rows; rules separate entries. At narrow widths the output controls stack below the playlist and each row reflows while retaining its status. The desktop rail collapses to an icon rail around `1020px`, and the compact navigation moves to the top around `620px`.

Spacing is compact inside controls and rows, with larger breaks between the source, manifest, and output regions. The established working steps are multiples or close neighbors of `4px` (`4`, `8`, `12`, `16`, and `24px`).

## Elevation & Depth

The system is primarily flat. Depth comes from tonal surface shifts and fine borders, not floating cards or glows. A soft, offset shadow is limited to transient notices that must separate from the work area.

**The Flat-By-Default Rule.** A control is raised only when its interaction or temporary status needs separation.

## Shapes

Corners stay restrained: small radii on controls, slightly larger radii on panels, and mostly square ledger rows. The active navigation marker is a narrow structural signal; list rows use a full-row state tint rather than a thick colored side border.

## Components

### Buttons
- **Shape:** Compact corners (`4px`); primary actions use the signal color.
- **Primary:** Warm orange with dark ink, short action copy, and a clear disabled state.
- **Hover / Focus:** A small color lift on hover; keyboard focus uses a visible two-pixel outline offset from the control.
- **Secondary / Ghost:** Transparent at rest; text and border strengthen on hover.

### Chips
- **Style:** Small, squared labels with a thin border and restrained warm text.
- **State:** “Datos de muestra” and prototype markers disclose demo content; they do not impersonate availability or progress.

### Cards / Containers
- **Corner Style:** Output rail uses a restrained `6px` radius.
- **Background:** One workbench surface above the main ground.
- **Shadow Strategy:** Flat at rest; no nested cards.
- **Border:** One structural outline and internal rules for sections.
- **Internal Padding:** Approximately `16px`.

### Inputs / Fields
- **Style:** Dark inset field, fine structural border, `6px` radius.
- **Focus:** Border shifts toward the signal color with a visible focus outline.
- **Error / Disabled:** Errors name the needed recovery; disabled controls remain visibly subdued and explain why where possible.

### Navigation
- **Style:** Persistent dark rail, Barlow labels, thin active marker, and a tonal active surface.
- **Hover / Active:** Hover brightens the surface; active navigation uses the signal color only for its icon and marker.
- **Narrow Windows:** Labels collapse to icons before the rail moves above the content.

### Playlist Ledger
Ordered media entries align selection, sequence number, title, duration, and availability. On narrow screens the same information reflows into a compact row; status must not be clipped.

## Do's and Don'ts

### Do:
- **Do** label synthetic playlist data and unconnected functionality as a prototype.
- **Do** keep media order and item-level availability visible.
- **Do** keep the source, manifest, and output options close enough to compare at a glance.
- **Do** use the signal color only for actions, selections, and meaningful states.

### Don't:
- **Don't** present sample metadata as if it came from an analyzed URL.
- **Don't** imply a setting is saved when it is only a visual placeholder.
- **Don't** replace playlist rows with equal-sized content cards.
- **Don't** hide or truncate availability status on narrow windows.

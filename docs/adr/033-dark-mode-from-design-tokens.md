# ADR-033: Dark mode by redefining the design tokens

Date: 2026-11-27 · Status: Accepted · Stretch item

## Context
Dispatchers work long hours, some at night, and many phones are set to dark. The
interface already reads every colour from CSS variables (`index.css`), never raw colours
in components, so a second theme should not touch components.

## Decision
- `index.css` has a dark set of the same variables. It applies when the person has
  chosen dark (`data-theme="dark"`), or when they have not chosen and the system prefers
  dark (`prefers-color-scheme`). A choice of light beats a dark system.
- A switch ("Dark mode: on/off") sits with Sign out: in the sidebar, the drawer and the
  technician's top bar. The choice is kept in `localStorage` on that device (best effort:
  if storage is blocked the choice still holds for the visit).
- A four-line script in `index.html` applies a saved choice before the first paint, so
  there is no flash of the wrong theme.
- Contrast was checked by script: every text and background pair is at least 4.5:1,
  input borders and the brand colour on surfaces at least 3:1. Status is still never
  colour alone: each status has its own glyph (`shared/status.ts`).

## Alternatives
- **Follow the system only, no switch.** Rejected: a dispatcher in a bright office
  with a dark phone cannot override it.
- **A server-side preference.** Rejected: more API for a per-device taste.

## Trade-offs
- The map keeps its light tiles and pin colours; pins and tiles are third-party images
  that stay legible on either theme. **TIME.** Full fidelity: dark tiles.
- The sign-in page has no switch; it follows the system.
- The two dark blocks in `index.css` (explicit and system) must stay identical. CSS has
  no way to share them without a build step.

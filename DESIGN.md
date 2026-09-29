<!-- SEED: established with the user before implementation; re-run /impeccable document once the frontend has real code, to capture actual rendered tokens and components. -->

---
name: Booking System
description: A calm, operational booking tool for any appointment-based small service business.
colors:
  background: "#FAF8F5"
  foreground: "#292524"
  card: "#FFFFFF"
  primary: "#C1502E"
  primary-foreground: "#FFFFFF"
  secondary: "#F0EBE4"
  secondary-foreground: "#292524"
  muted: "#F0EBE4"
  muted-foreground: "#6B6459"
  accent: "#F7E6DE"
  accent-foreground: "#A8431F"
  accent-text: "#A8431F"
  destructive: "#B3261E"
  destructive-foreground: "#FFFFFF"
  border: "#E4DDD3"
  ring: "#A8431F"
  success: "#2F6B3E"
  success-bg: "#E6F2E8"
  warning: "#8A5A00"
  warning-bg: "#FBEEDA"
  dark-background: "#1C1917"
  dark-foreground: "#F2EDE7"
  dark-card: "#26211D"
  dark-primary: "#DD7A52"
  dark-primary-foreground: "#1C1917"
  dark-secondary: "#2A2521"
  dark-muted-foreground: "#A39A8E"
  dark-accent: "#3A241C"
  dark-destructive: "#E5827A"
  dark-destructive-foreground: "#1C1917"
  dark-border: "#3A342E"
  dark-success: "#7FBF8E"
  dark-success-bg: "#1F3324"
  dark-warning: "#E0B44C"
  dark-warning-bg: "#3A2E10"
typography:
  body:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  heading:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontWeight: 600
    lineHeight: 1.2
  numeric:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontFeature: "tabular-nums"
rounded:
  sm: "4px"
  md: "6px"
  lg: "10px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
---

# Design System: Booking System

## Overview

**Creative North Star: "The Well-Run Front Desk"**

Not a marketing surface — an operational tool three different people use to get a real job done: a customer finding and holding a slot, a provider reading their day, an admin keeping a business's schedule honest. The system stays out of the way of the task (Operate mode, per PRODUCT.md's own principle that role-appropriate surfaces beat one generic CRUD skin), while refusing the two easiest defaults for this category: the ubiquitous "calendar blue" every booking tool reaches for, and the equally common AI-generated tells (purple/indigo gradients, neon-on-near-black, cream-paper-plus-serif editorial looks). One warm, confident accent — burnt clay/terracotta — carries brand identity instead, kept rare enough that it still means something when it appears (a primary action, a link, a focus ring), never spent on decoration.

Status is legible without shouting: confirmed/pending/cancelled render as soft tinted badges in their own hue family, never as solid saturated fills, so they read as information rather than competing for the same visual weight as the one true action color.

**Key Characteristics:**
- Warm neutral base (off-white / charcoal), not cold gray or stark white/black.
- One accent color, used sparingly, never diluted into secondary/tertiary roles.
- Status colors are soft badges, never loud fills.
- Flat by default; depth comes from a single hairline border, not shadows.
- One typeface family for everything, differentiated by weight — no display/body split, no decorative serif.

## Colors

Restrained strategy: warm neutrals carry almost the entire surface; the one accent appears only where it means something (a primary action, a link, an active/focus state).

### Primary
- **Burnt Clay** (`#C1502E` light / `#DD7A52` dark): the one brand accent. Primary buttons, links, active nav state, focus rings. Never used for status.

### Neutral
- **Warm Paper** (`#FAF8F5` light bg / `#1C1917` dark bg): page background.
- **Ink** (`#292524` light text / `#F2EDE7` dark text): body text.
- **Warm Sand** (`#F0EBE4` light / `#2A2521` dark): muted/secondary surface — subtle panels, secondary buttons.
- **Clay Whisper** (`#F7E6DE` light / `#3A241C` dark): the accent's own tint — hover/active background for interactive rows and the accent-colored text's home when it needs a distinct surface.

### Status (badges only — never solid fills)
- **Confirmed / success**: text `#2F6B3E` on tint `#E6F2E8` (light); text `#7FBF8E` on tint `#1F3324` (dark).
- **Pending / warning**: text `#8A5A00` on tint `#FBEEDA` (light); text `#E0B44C` on tint `#3A2E10` (dark).
- **Cancelled / destructive**: text `#B3261E` on tint `#FBEAE8` (light); text `#E5827A` on a dark-lifted tint (dark). The same red also has a solid-fill form (`#B3261E` bg / white text) reserved for genuinely destructive *actions* (e.g. a "Cancel booking" button) — badges and buttons never share the same visual weight for the same color.

### Named Rules
**The One Accent Rule.** Burnt clay never appears twice for two different meanings on one screen. If it's already the primary action's color, a status badge reaches for its own status palette instead, never clay.

**The Verified-Contrast Rule.** Every color pair above was checked against real WCAG AA math, not eyeballed (see Accessibility below). `#C1502E` (the brand fill color) measures 4.44:1 on the light background — enough for a filled button (white text on it hits 4.71:1, and the button itself is a non-text UI element needing only 3:1) but *not* enough to use as plain text color on the page background. That's why `accent-text` (`#A8431F`, 5.68:1) exists as a separate, darker token: **use `primary` only for fills (buttons, the focus ring), use `accent-text` whenever the accent color itself needs to be the text or icon color** (a link, an active nav label). In dark mode this split isn't needed — `#DD7A52` alone clears 5.82:1 as plain text on the charcoal background, so dark mode has one accent value doing both jobs.

### Accessibility (verified, not asserted)

| Pair | Ratio | Use |
|---|---|---|
| `#292524` text on `#FAF8F5` bg | 14.3:1 | body text, light |
| `#F2EDE7` text on `#1C1917` bg | ~17:1 | body text, dark |
| `#FFFFFF` text on `#C1502E` fill | 4.71:1 | primary button, light |
| `#1C1917` text on `#DD7A52` fill | 5.82:1 | primary button, dark |
| `#A8431F` text on `#FAF8F5` bg | 5.68:1 | accent-as-text, light |
| `#DD7A52` text on `#1C1917` bg | 5.82:1 | accent-as-text, dark |
| `#6B6459` text on `#F0EBE4` bg | 4.93:1 | muted/secondary text, light |
| `#A39A8E` text on `#1C1917` bg | 6.30:1 | muted text, dark |
| `#2F6B3E` text on `#E6F2E8` bg | 5.53:1 | success badge, light |
| `#8A5A00` text on `#FBEEDA` bg | 5.18:1 | warning badge, light |
| `#B3261E` text on `#FBEAE8` bg | 5.61:1 | destructive badge, light |
| `#FFFFFF` text on `#B3261E` fill | 6.54:1 | destructive button |

All pairs clear the 4.5:1 AA threshold for normal text with real margin (the tightest is 4.71:1, still 0.2 above the floor). `#A8431F` was also used as `--ring` (focus outline) — 5.68:1 against the page background satisfies the 3:1 non-text-UI floor with room to spare, meeting PRODUCT.md's explicit "visible focus states" requirement.

### shadcn/ui token mapping (the one place these are defined)

This exact block is the canonical source — copy it verbatim into `frontend/src/index.css` when Section 8 scaffolds the project. Modern shadcn/Tailwind v4 conventions hold real color values directly in the custom properties (no `hsl(var(--x))` indirection).

```css
:root {
  --background: #FAF8F5;
  --foreground: #292524;
  --card: #FFFFFF;
  --card-foreground: #292524;
  --popover: #FFFFFF;
  --popover-foreground: #292524;
  --primary: #C1502E;
  --primary-foreground: #FFFFFF;
  --secondary: #F0EBE4;
  --secondary-foreground: #292524;
  --muted: #F0EBE4;
  --muted-foreground: #6B6459;
  --accent: #F7E6DE;
  --accent-foreground: #A8431F;
  --destructive: #B3261E;
  --destructive-foreground: #FFFFFF;
  --border: #E4DDD3;
  --input: #E4DDD3;
  --ring: #A8431F;
  --radius: 0.375rem;

  /* Custom, non-shadcn-standard tokens used for booking status */
  --success: #2F6B3E;
  --success-bg: #E6F2E8;
  --warning: #8A5A00;
  --warning-bg: #FBEEDA;
  --destructive-bg: #FBEAE8;
  --accent-text: #A8431F; /* accent color when used AS TEXT, not as a fill */
}

.dark {
  --background: #1C1917;
  --foreground: #F2EDE7;
  --card: #26211D;
  --card-foreground: #F2EDE7;
  --popover: #26211D;
  --popover-foreground: #F2EDE7;
  --primary: #DD7A52;
  --primary-foreground: #1C1917;
  --secondary: #2A2521;
  --secondary-foreground: #F2EDE7;
  --muted: #2A2521;
  --muted-foreground: #A39A8E;
  --accent: #3A241C;
  --accent-foreground: #DD7A52;
  --destructive: #E5827A;
  --destructive-foreground: #1C1917;
  --border: #3A342E;
  --input: #3A342E;
  --ring: #DD7A52;

  --success: #7FBF8E;
  --success-bg: #1F3324;
  --warning: #E0B44C;
  --warning-bg: #3A2E10;
  --destructive-bg: #3D2220;
  --accent-text: #DD7A52; /* same value as --primary in dark mode — see the Named Rule above */
}
```

## Typography

**Body & Heading Font:** Hanken Grotesk (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Numeric (times & prices):** Hanken Grotesk with `font-variant-numeric: tabular-nums` — try this first; only reach for a monospace (IBM Plex Mono) if real rendering shows tabular-nums still doesn't align cleanly in the schedule grid (unverified until the frontend exists — flag this for a visual check once Section 8's UI is up).

**Character:** One humanist grotesque family for everything, warmer and more distinctive than a bare Inter default, differentiated by weight rather than by swapping families — appropriate for an Operate-mode tool where a second display face would only add load time and visual noise without earning it.

### Hierarchy
- **Heading** (600, 1.5rem-2rem depending on level, 1.2 line-height): section/page titles.
- **Body** (400, 1rem, 1.5 line-height): everything else — forms, tables, copy. Max ~75ch line length for any prose blocks (booking confirmation text, error messages).
- **Label** (500, 0.875rem, uppercase optional for section headers only, never for buttons): form labels, table headers — every form input gets a real visible `<label>`, never a placeholder standing in for one, per PRODUCT.md's accessibility requirement.
- **Numeric** (400, tabular-nums): appointment times, prices, durations — anywhere numbers stack vertically and need to align.

### Named Rules
**The No Placeholder-Label Rule.** A placeholder is a hint, not a label. Every input keeps a visible `<label>` even when space is tight — PRODUCT.md requires it, and it survives if the placeholder disappears (autofill, focus, filled state).

## Layout

Standard content-first layout: a persistent header (business/timezone indicator, user menu) above role-scoped content. Customer views stay narrow and linear (booking is a funnel: pick service → pick slot → confirm). Provider/admin views go wide and dense (schedules, tables) since operational users benefit from seeing more at once, not less. Mobile-first: single-column, full-width touch targets (44px minimum) below `640px`; provider/admin tables gain columns and a persistent sidebar above `1024px`. Spacing rhythm follows the `sm`/`md`/`lg` (8/16/24px) scale — more space above a heading than below it.

## Elevation & Depth

Flat by default. Depth comes from one hairline border (`--border`, `#E4DDD3` light / `#3A342E` dark) separating a card (`--card`) from the page background (`--background`), not from shadows — this reads calmer at high information density (schedules, booking lists) than layered shadows would, and keeps the one accent color the only thing that visually "pops." The sole exception: floating overlays (dropdowns, popovers, dialogs, toasts) get a small, soft shadow purely to signal they're not part of the document flow — `box-shadow: 0 4px 16px rgba(28, 25, 23, 0.12)` — never used on in-flow surfaces like cards or table rows.

### Named Rules
**The Border-Not-Shadow Rule.** In-flow surfaces (cards, list rows, panels) separate from their background with a 1px border, never a shadow. Shadows are reserved for things that float above the page.

## Shapes

Moderate, consistent rounding (`--radius: 0.375rem` / 6px) on cards, buttons, and inputs — precise enough to feel operational, not so sharp it feels cold, not so round it feels consumer-playful. Badges (status pills) use a fully-rounded pill shape (`border-radius: 9999px`) to visually distinguish "this is a status label" from "this is a container" at a glance.

## Do's and Don'ts

### Do:
- **Do** use `primary` (`#C1502E` / `#DD7A52`) only for fills — buttons, the focus ring, a selected/active state's background.
- **Do** use `accent-text` (`#A8431F` light / `#DD7A52` dark) whenever the accent color is the text or icon color itself, not a fill.
- **Do** render every status (confirmed/pending/cancelled) as a soft tinted badge — text + `-bg` pair from the same row — never a solid saturated fill.
- **Do** give every form input a real, visible `<label>` and a visible `:focus-visible` ring using `--ring`.
- **Do** use `font-variant-numeric: tabular-nums` on any place two or more times/prices stack and must align.

### Don't:
- **Don't** use `primary` as a status color, or a status color as a general-purpose brand accent — they stay in separate hue families for a reason (a "confirmed" badge must never look like it's competing with the "Book now" button).
- **Don't** add a shadow to a card, table row, or any other in-flow surface — depth there comes from `--border` only.
- **Don't** introduce a second display/heading typeface — Hanken Grotesk at a heavier weight carries every heading level.
- **Don't** rely on color alone to convey status — every status badge carries a text label, never just a colored dot.

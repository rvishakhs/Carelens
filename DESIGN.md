---
version: alpha
name: CareLens
description: A care-home staff workspace with teal actions, quiet record cards and explicit clinical provenance.
colors:
  primary: "#1a8a78"
  primaryHover: "#17584f"
  primaryText: "#17584f"
  background: "#f4f6f6"
  surface: "#ffffff"
typography:
  sans:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif"
rounded:
  DEFAULT: "0.5rem"
  card: "1rem"
  record: "0.75rem"
spacing:
  cardPadding: "1.25rem"
  panelGap: "1rem"
components:
  button:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.DEFAULT}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.card}"
    padding: "{spacing.cardPadding}"
---

## Overview

CareLens serves care-home nurses and authorised staff reviewing a resident during a shift.
The visual reference is the existing resident record workspace: teal navigation, white
clinical record cards, restrained slate text, and clear source dates. This is a product
surface for the existing UK pilot. Current UI copy is English; it has no locale provider.
Avoid promotional hero treatments, decorative clinical risk scores, and chat-like
answers that obscure source records. The fall-history feature's defining detail is
a dated record that opens inline, keeping its provenance beside its contents.

## Colors

Runtime tokens remain canonical: `frontend/src/index.css` defines the brand ramp and
page background; Tailwind's slate, amber and rose utilities provide neutral, caution
and error roles. This document mirrors existing values and does not generate CSS.
`colors.primary` maps to `--color-brand-600`; hover/text map to `--color-brand-700`;
surface maps to shared `Card`'s `bg-white`. Token changes must update both this file
and the runtime owner. The current app supports a light theme.

## Typography

`typography.sans` mirrors `--font-sans` in `frontend/src/index.css`. Existing titles
use semibold; body and controls use the same family at text-sm, record dates at
text-xs. This feature retains those roles and shows years and timezone labels on
historical records. Dates use en-GB formatting in the viewer's local timezone.

## Layout

Resident Overview uses naturally scrolling stacked panels with `space-y-4`. Cards
have `p-5`; the existing summary grid expands to three columns at `lg`. Search filters
wrap on narrow screens; records remain single-column, with source fields becoming
two columns at `sm`. Do not constrain the resident page to a fixed viewport height.

## Elevation & Depth

Reuse the shared Card's slate border and subtle shadow. Source detail uses a divider
and inline disclosure rather than another overlay or elevated nested card.

## Shapes

Shared buttons and fields use rounded-lg, source records rounded-xl, and outer cards
rounded-2xl. These map to Tailwind's existing 0.5rem, 0.75rem and 1rem radii.

## Components

Reuse `Button`, `Card` and `CardHeader`; do not change sibling screens' styles for
one feature. The shared owners are `frontend/src/components/ui/Button.tsx` and
`frontend/src/components/ui/Card.tsx`. Lucide provides labelled actions and decorative icons with aria-hidden.
New controls have visible keyboard focus, pointer/hover/active states and disabled
submit while pending. Spinners respect reduced motion. Keep the submit label and
dimensions stable while pending. Loading, empty and error messages are inline.
The fall search submit uses the existing dark Button variant: the legacy primary
teal with white small text measures 4.24:1; the dark variant provides stronger contrast.
Native date fields deliberately delegate calendar popup geometry and language to
the browser/OS; visible labels and result dates remain English. Native inline
record disclosures keep focus on the trigger and re-fetch current data on opening.
Clinical text renders as escaped React text; it is never interpreted as HTML.

## Do's and Don'ts

- Keep source timestamps, missing fields and coverage limits explicit.
- Preserve the established teal/slate visual language and native record context.
- Do not use colour alone to imply clinical severity or certainty.
- Do not store resident search content in URLs, browser storage or console logs.

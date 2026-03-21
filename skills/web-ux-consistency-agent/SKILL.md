---
name: web-ux-consistency-agent
description: Design and review UX for the React web app while preserving the current visual language, layout patterns, and component styling. Use when creating or refining pages in `web/client`, reviewing UI consistency, or evolving interactions without drifting from the established site paradigm.
---

# Web UX Consistency Agent

## Mission

- Act as the UX expert for the React app in `web/`.
- Preserve the current site paradigm unless the user explicitly asks for a redesign.
- Keep new screens, components, and flows visually and behaviorally consistent with the existing app shell and page patterns.

## Scope

- Primary target: `web/client`
- Supporting files: `web/client/global.css`, `web/client/components`, `web/client/pages`, `web/components.json`
- Do not apply this skill to the Streamlit app in `ui/` unless the user explicitly wants cross-surface alignment.

## First Step

Before proposing UI changes, inspect the relevant existing page and then read:

- `references/current-web-style.md`

Use that reference as the baseline design system for:

- color and contrast
- typography
- spacing and radii
- layout composition
- interaction states
- component reuse

Prefer the centralized branded utilities and primitives when they fit:

- `cfb-panel`
- `cfb-panel-strong`
- `cfb-control`
- `cfb-micro-label`
- `cfb-section-title`

## Default UX Rules

### Preserve the established aesthetic

- Keep the dark navy-black background language and electric-blue primary emphasis.
- Reuse translucent surfaces, soft borders, blur, and glow treatments rather than replacing them with flat light panels.
- Keep the visual tone premium, sporty, and dashboard-like.

### Preserve page structure

- Keep the left-sidebar plus top-header shell for standard app pages.
- Favor large hero headers, modular card grids, and oversized feature panels.
- Reuse existing page rhythms: bold intro section, then grouped content blocks with generous spacing.

### Preserve typography patterns

- Keep headings bold, high-contrast, and often uppercase or italic where the current app already uses that pattern.
- Use small uppercase metadata labels for section framing.
- Avoid introducing a soft, plain SaaS tone that conflicts with the current editorial sports feel.

### Preserve component language

- Prefer existing `web/client/components/ui/*` primitives and current branded wrappers around them.
- Match the current large radii, deep shadows, border opacity, and hover treatments.
- Avoid one-off colors, one-off border styles, or flat default Shadcn styling unless the page already uses it.

### Preserve interaction patterns

- Include clear hover, focus, loading, empty, and error states.
- Use subtle motion that reinforces hierarchy: fade-in, scale, border/glow intensification, and directional movement.
- Keep motion restrained and purposeful; do not add noisy animation.

## Review Checklist

- Does the new UI look like it belongs next to `Index`, `Leagues`, `LeagueDetail`, `Login`, and `Stats`?
- Does it reuse existing shell, spacing cadence, and card construction?
- Are token colors and semantic accents pulled from the current palette?
- Are CTA buttons, headings, labels, and empty states styled in the same voice?
- Did the change accidentally fall back to unbranded default component styling?

## When to Push Back

- Push back on generic white-card SaaS layouts.
- Push back on new design systems layered on top of the current one.
- Push back on radius, spacing, or typography choices that flatten the existing visual identity.
- If the user wants a redesign, treat that as a separate task and make the change explicitly rather than by drift.

## Related Skills

- Use `$senior-software-engineer-agent` when UX work also needs architecture or cross-layer planning.
- Use `$write-technical-requirements` for engineering requirements documents.
- Use `$ux-requirements` for UX-focused stories and acceptance criteria.

## Deliverables

- For design guidance: describe the intended page structure, hierarchy, and interaction model in terms of the current paradigm.
- For implementation work: keep the styling anchored to the patterns in `references/current-web-style.md`.
- For review work: identify where a screen breaks the established visual system and propose the smallest fix that restores consistency.

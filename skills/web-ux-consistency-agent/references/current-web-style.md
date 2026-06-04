# Current Web Style

This reference describes the existing design paradigm for the React app in `web/`. Use it as the baseline when creating new pages or revising existing ones.

## Design Summary

The app uses a premium dark sports-dashboard aesthetic with a cinematic, slightly futuristic tone. It is not a minimal light SaaS product and it is not a neutral admin panel. The interface should feel energetic, competitive, and polished.

Short description:

`Dark, high-contrast, premium sports command-center UI with electric blue accents, oversized rounded glass panels, uppercase editorial typography, and motion-rich dashboard layouts.`

## Core Files

- `web/client/global.css`
- `web/client/components/Layout.tsx`
- `web/client/components/BackgroundEffects.tsx`
- `web/client/pages/Index.tsx`
- `web/client/pages/Leagues.tsx`
- `web/client/pages/LeagueDetail.tsx`
- `web/client/pages/Login.tsx`
- `web/client/pages/Stats.tsx`

## Visual Identity

### Background and atmosphere

- The base background is near-black to deep navy.
- The app uses a central blue glow, deep edge vignettes, and a faint radial grid.
- Background treatments are atmospheric and help the app feel immersive rather than flat.

### Palette

- Primary accent is bright electric blue.
- Main surfaces use dark navy, slate, and muted blue-gray.
- Text is off-white, not stark pure white.
- Semantic accents exist for status and categories: emerald, amber, orange, red, purple, cyan.
- Blue is the brand anchor. Other colors should usually be subordinate or semantic.

### Surface treatment

- Cards are often translucent or semi-opaque over the dark background.
- Borders are soft and low-contrast.
- Blur, gradients, and glows are used to create depth.
- Heavy flat fills should be the exception, not the default.

## Typography

### Headings

- Large headings are bold or black, tightly tracked, often uppercase, and often italic.
- Some hero headings use gradient text treatments.
- Section headings often combine a micro-label plus a large title.

### Labels and metadata

- Small utility labels are frequently uppercase and heavily letterspaced.
- These labels are used to frame sections, categories, and supporting metadata.

### Body text

- Body copy is restrained and muted.
- Explanatory text is readable but not visually dominant.

## Layout Patterns

### App shell

- Standard pages use a fixed left sidebar and sticky top header.
- Main content scrolls independently.
- Containers are centered with `max-w-*` constraints and generous internal spacing.

### Page rhythm

- Many pages open with a strong hero or section header.
- Content then flows into a card grid, dashboard modules, or large data panels.
- Spacing is generous; the design does not feel cramped.

### Composition

- Bento-style dashboards are common.
- Mixed card sizes are used to create hierarchy.
- Important areas often get oversized cards with strong framing.

## Component Patterns

### Cards

- Large radii are common, often beyond default component values.
- Cards often have soft gradients, blur, glow, and subtle border emphasis.
- Headers inside cards usually include micro-labels and bold section titles.

### Buttons

- Primary buttons are bold, high-contrast, and clearly branded.
- Outline buttons still carry the dark/glass visual language.
- CTA buttons often use uppercase text, strong tracking, and noticeable depth.

### Inputs and controls

- Inputs are typically dark, rounded, and softly bordered.
- Focus states reinforce the blue primary brand color.
- Default unstyled component-library presentation should usually be avoided on branded screens.

### Tables and dense data rows

- Even data-heavy views preserve the same dark/glass shell.
- Dense rows use subtle hover changes instead of loud separators.
- Semantic chips and pills provide color-coded scanning cues.

## Motion

- Motion is present but controlled.
- Common patterns: page fade-in, slight scale on hover, border/glow intensification, and gentle directional movement.
- Motion should support hierarchy and responsiveness, not distract from the task.

## Tone and Voice

- The interface voice is competitive, premium, and editorial.
- It should feel like a command center for fantasy sports, not a spreadsheet app.
- Avoid generic enterprise phrasing when naming sections, CTAs, or status labels.

## Consistency Rules

- Reuse `web/client/global.css` tokens and the dark shell from `Layout.tsx`.
- Prefer existing page motifs over inventing new layout idioms.
- Reuse `web/client/components/ui/*` primitives, but style them to match the branded page language.
- Avoid white surfaces, tiny radii, weak hierarchy, or default-safe component styling that feels disconnected from the current app.

## Centralized Utilities

These shared utilities exist specifically to reduce component drift and radius drift:

- `cfb-panel` for standard branded glass cards
- `cfb-panel-strong` for heavier modal or hero surfaces
- `cfb-control` for branded dark inputs and control shells
- `cfb-micro-label` for small uppercase section framing text
- `cfb-section-title` for branded section titles

Prefer these over inventing slightly different panel or control styles on each page.

## Drift Warnings

The most likely visual regressions are:

- falling back to default Shadcn styling without branded overrides
- introducing plain SaaS cards or form layouts
- using inconsistent radii or spacing density
- overusing non-blue accent colors in ways that compete with the brand
- removing the strong heading and micro-label hierarchy

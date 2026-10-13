# Current Web Style

The user-approved website redesign uses a compact charcoal sports dashboard inspired by NFL Stock Exchange, while preserving CFFB blue. Do not reintroduce the previous navy glass, field textures, X/O artwork, multicolor streaks, or oversized rounded panels.

## Source of truth

- `web/client/global.css`: color, radius, typography, surfaces and interactions.
- `web/tailwind.config.ts`: font families and semantic utility mappings.
- `web/client/components/app-shell/`: responsive shell and navigation.
- `web/client/components/player/PlayerCardHeader.tsx`: identity and portrait layout.
- `web/client/components/ui/`: shared controls, cards, tabs and menus.

## Palette and surfaces

- Canvas is neutral near-black (`0 0% 9%`); panels are charcoal (`0 0% 14%`); raised surfaces use `0 0% 17%`.
- Thin neutral dividers, matte fills and compact corners: controls 6px, surfaces 8px.
- CFFB blue remains `207 90% 63%` for brand accents and selections.
- Preserve established injury and live-game semantic colors. Never turn injury warnings blue merely to match the theme.
- Working panels have no decorative gradient, glow or texture. Modal scrims may blur underlying content to distinguish the dialog.

## Typography

- Self-hosted Poppins for rounded body text, controls, player names, scores and data.
- Self-hosted Exo 2 for bold italic uppercase sports/editorial headings.
- Font license notices ship at `/font-licenses.txt`.
- Quote `"Exo 2"` in generated CSS: an unquoted numeric font-family name is invalid CSS.
- Prefer `cfb-display-title`, `cfb-section-title`, `cfb-micro-label`, `cfb-ui-text`, and `cfb-stat-value` over custom stacks.
- Keep body text and scores upright. Use restrained tracking; reserve uppercase for headings and short metadata.

## Layout and behavior

- Compact left navigation on desktop; persistent bottom navigation and safe-area support on mobile.
- Keep data rows and action columns aligned. Contain genuinely wide data in its own horizontal scroller.
- Preserve 16px mobile inputs, visible blue keyboard focus, and reduced-motion preferences.
- Portraits have a dedicated right-side lane. Names and metadata must not overlap the portrait.
- The fixed draft context strip reserves a desktop lane for confirmations; the inline timer stays below it without shifting the player list when a pick is confirmed.
- Reuse shared theme tokens and components rather than page-specific decoration.
- Preserve scoring, draft, authentication, polling and injury logic when changing appearance.

## Verification

Run frontend type checking, unit tests, the production web build and relevant browser tests. Inspect desktop and mobile screenshots for clipped labels, overlapping pictures, hidden actions and document-level overflow. Do not sync Capacitor or change an iOS build unless explicitly requested.

# Feature: UI Look and Feel Alignment (Mobile Roster-Inspired)

## Description
Align the UI visual system and layout with the provided mobile roster screenshots, emphasizing a dark, high-contrast interface, segmented sections, and compact player cards.

## User Stories
- As a user, I want a dark, modern interface that matches the mobile roster style.
- As a user, I want clear visual hierarchy for tabs, section headers, and action buttons.
- As a user, I want roster and player rows to be scannable with consistent spacing and typography.

## Acceptance Criteria
- Primary UI uses a dark theme with high-contrast text and accent highlights.
- Tabs, section headers, and roster rows visually match the reference layout and spacing.
- Action buttons and pills match the rounded, outlined style with subtle glow/outline.
- Status badges (e.g., IR, OUT) are visually distinct and readable.

## Visual Specs
- Color palette
  - Background: near-black (#0B0B0B to #121212 range)
  - Surfaces: charcoal (#1A1A1A to #242424)
  - Primary text: off-white (#EDEDED)
  - Secondary text: gray (#9A9A9A)
  - Accent: green (#2ED158) for selected tab underline
  - Status: red/orange for IR/OUT, blue for interactive pills
- Typography
  - Primary: bold sans for headers and player names
  - Secondary: lighter weight for meta stats and labels
  - Compact line height for dense lists
- Components
  - Tabs: uppercase labels, active underline in green, inactive gray
  - Section headers: all caps, small size, spaced above lists
  - Pills: rounded outline buttons with blue border and text
  - Cards/rows: full-width, rounded corners, dark surface, consistent padding
  - Badges: rounded, solid fill with contrasting text

## UI Implementation Notes
- Apply global Streamlit theme overrides for background, text, and primary colors.
- Use custom CSS to style tabs, section headers, pills, and list rows.
- Standardize roster row layout with avatar, position pill, name, meta stats, and score.
- Ensure mobile-friendly spacing and tap targets.

## Workflow
1. Define a UI theme file (colors, fonts, spacing tokens).
2. Implement custom CSS for tabs, pills, headers, and list rows.
3. Update roster and players pages to use the new components.
4. Validate contrast and readability on mobile and desktop widths.

## API Specs
- No new endpoints required.
- UI should consume existing league/team/player/roster endpoints to render data within the new visual system.

## UI Specs
- Global theme
  - Apply dark theme tokens and accent colors consistently across all pages.
  - Add page-level padding and section spacing to mimic mobile density.
- Tabs and navigation
  - Uppercase labels with green underline on active tab.
  - Subtle separators between sections.
- Roster rows
  - Avatar + position pill + player name/meta + score aligned right.
  - Status badges for IR/OUT and availability.
- Buttons and pills
  - Rounded outline buttons with blue accent.
  - Minimal hover state change.

## Database Specs
- No database changes required; this is a presentation-layer feature.

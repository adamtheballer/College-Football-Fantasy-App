# Web App Instructions

`web/` is the canonical React frontend for the College Football Fantasy App.

## Architecture

- Use React 18, React Router, TypeScript, Vite, TailwindCSS, Radix UI, and Vitest.
- The production backend is the FastAPI app under `api/`.
- Do not add or reintroduce an Express server, Netlify function API proxy, or Vite Express middleware.
- Frontend API calls should go through the existing client-side API utilities and the configured FastAPI base URL.

## Package Manager

- Use npm commands in this folder.
- Keep `package-lock.json` as the lockfile.
- Do not add pnpm-only workflow files unless explicitly requested.

## Routing

- Routes are defined in `client/App.tsx`.
- Route components live under `client/pages/`.
- Keep league-specific fantasy workflows inside selected league routes when possible.

## Styling

- Prefer TailwindCSS utility classes and shared components in `client/components/`.
- Preserve the existing dark sports-dashboard visual system unless the user explicitly requests a visual redesign.

## Testing

- Run `npm --prefix web run typecheck` after TypeScript changes.
- Run `npm --prefix web test` for unit/component coverage when logic changes.
- Run `npm --prefix web run build` before calling frontend branch work complete.

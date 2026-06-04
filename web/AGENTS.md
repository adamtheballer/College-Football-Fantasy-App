# Web Frontend

`web/` is the React/Vite frontend for the College Football Fantasy app.

## Architecture

- The canonical backend is the FastAPI app in `api/`.
- Frontend API calls must use `VITE_API_BASE_URL`.
- The local fallback API base URL is `http://localhost:8000`.
- Do not add an Express or Vite-hosted API backend in `web/`.

## Development

- Use Vite for local frontend development.
- Keep route changes in `client/App.tsx` and page components under `client/pages/`.
- Keep shared UI components under `client/components/`.
- Preserve existing frontend auth, draft, and roster state flows unless the task explicitly targets them.

## Commands

```bash
npm run dev
npm run build
npm run typecheck
npm test
```

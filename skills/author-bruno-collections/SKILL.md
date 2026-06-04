---
name: author-bruno-collections
description: Add or update Bruno API collection requests for this repo. Use when a new API endpoint needs a Bruno request or the HappyPath workflow should be refreshed.
---

# Author Bruno Collections

## File locations

- Collection root: `bruno/collections/backend-api`
- Environment: `bruno/environments/local.env`
- Workflow note: `bruno/collections/backend-api/_Workflows/HappyPath.bru`

## Request authoring

- Create a `.bru` file inside the matching folder (Leagues, Teams, Players, Rosters, Health).
- Use `{{base_url}}` for the host and keep paths aligned with the FastAPI routes.
- Set `meta.seq` values in ascending order within a folder.

## Example structure

```
meta {
  name: List Leagues
  type: http
  seq: 2
}
get {
  url: {{base_url}}/leagues
}
```

## Workflow maintenance

- Update `_Workflows/HappyPath.bru` when the main end-to-end flow changes.
- Keep the workflow note short and list the intended sequence.

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

- Create the request in the matching domain folder; create a new domain folder when none exists. Preserve neighboring naming and sequence conventions.
- Use `{{base_url}}` for the host and keep paths aligned with the FastAPI routes.
- Set `meta.seq` values in ascending order within a folder.
- Inspect route dependencies before authoring the request. For protected routes, obtain and store `access_token` through an approved local auth setup or login request, then send `Authorization: Bearer {{access_token}}` without hard-coding credentials or tokens.
- Treat unexpected `401` and `403` responses as workflow failures, not successful smoke checks.

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
- Keep setup and post-response scripts that capture IDs or tokens next to the request that produces them.

## Verification

- Execute the changed request sequence through Bruno or its CLI when available.
- Confirm expected status codes, response contracts, authentication behavior, and post-response variable extraction.
- If execution is unavailable, report that gap instead of claiming the collection works.

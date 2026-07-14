---
name: cross-stack-contract-parity
description: Verify implemented contracts across the React frontend and FastAPI backend in this repo. Use when changing API payloads, Pydantic schemas, endpoint status or error behavior, frontend API helpers, TypeScript types, React Query hooks, pagination, enums, or nullability.
---

# Cross Stack Contract Parity

Verify both sides of a contract from implementation evidence. Do not infer parity from matching names or from tests that mock the same incorrect assumption.

## Workflow

1. Identify the endpoint and every affected consumer.
2. Inspect the FastAPI route, Pydantic request and response models, service output, and relevant database nullability.
3. Inspect `web/client/lib/api.ts`, affected TypeScript types, hooks, pages, and test fixtures.
4. Compare the contract field by field:
   - path and query parameters, headers, credentials, cookies, authentication requirements, and retry or refresh behavior
   - request names, casing, types, optionality, bounds, and enums
   - response names, wrappers, nullability, pagination, and nested shapes
   - success status codes and empty responses
   - validation, authorization, conflict, and server-error details
5. Normalize data once at a deliberate boundary. Avoid parallel ad hoc conversions in multiple components.
6. Update both sides and add tests that would fail if either side drifted again.

## Verification Rules

- Use actual Pydantic models and serialized responses as the backend authority.
- Do not render API errors as empty, preview, or successful data.
- Treat `null`, omitted fields, empty arrays, and empty objects as different contract states.
- Keep frontend pagination requests within backend bounds.
- Reject or translate unknown configuration keys at one explicit boundary.
- Prefer a shared fixture when the same domain rule must exist in Python and TypeScript.
- Cover at least one representative success case and each changed failure class.

## Files to Inspect

- `api/app/api/routes`
- `api/app/schemas`
- `api/app/services`
- `api/app/models`
- `web/client/lib/api.ts`
- `web/client/types`
- `web/client/hooks`
- affected React pages and components
- `tests/api`
- frontend unit tests and `web/tests/e2e` when relevant

## Completion

Run targeted backend pytest and frontend Vitest coverage plus `npm --prefix web run typecheck`. Run the Playwright workflow when parity depends on browser-managed cookies, navigation, or reload behavior.

Report the verified contract, tests run, and any unverified runtime boundary. Do not claim parity if only one side was executed.

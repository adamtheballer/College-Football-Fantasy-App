---
name: add-fastapi-endpoint
description: Add or modify FastAPI endpoints in this repo, including routes, Pydantic contracts, services or CRUD, authorization, router registration, and tests. Use when creating API paths or changing endpoint behavior consumed by the React frontend or other clients.
---

# Add FastAPI Endpoint

## Quick checklist

- Inspect the closest existing route and every affected client before choosing a pattern.
- Choose or create a router file in `api/app/api/routes`.
- Define Pydantic request/response models in `api/app/schemas`.
- Put simple persistence in `api/app/crud`; put multi-step business workflows in `api/app/services`.
- Apply the existing authentication, ownership, or commissioner dependency for the resource.
- Register the router in `api/app/main.py` with prefix and tags.
- Update React API helpers, types, and hooks when the contract is consumed by `web/`.
- Add or adjust tests under `tests/api` and frontend tests when relevant.

## Steps

1. Create or update a router module in `api/app/api/routes` and add an `APIRouter` instance.
2. Define endpoint functions with explicit status codes and response models.
3. Use dependency injection for database access and resource authorization.
4. Keep the route responsible for transport concerns; delegate reusable business behavior to a service and straightforward queries to CRUD.
5. Make transaction ownership explicit. Do not scatter commits across route, service, and CRUD layers for one workflow.
6. Register the router in `api/app/main.py` with a stable prefix and clear tag when it is new.
7. Use `$cross-stack-contract-parity` when React consumes the changed contract.

## Repo patterns to mirror

- Mirror the nearest collection response model. Paginated lists use `{data, total, limit, offset}`; bounded collections may use `{data}` or `{data, total}`.
- Preserve FastAPI validation details for 422 responses and use stable `HTTPException(detail=...)` messages for domain failures.
- Keep query bounds, nullability, enums, and success status codes explicit in the contract.
- Avoid adding a parallel endpoint when an existing route can be extended compatibly.

## Testing

- Add new tests in `tests/api` using the `client` fixture in `tests/conftest.py`.
- Cover representative success, unauthenticated, wrong-actor, invalid-input, not-found, and conflict behavior as applicable.
- Assert response values and persisted state, not only status and shape.
- Run the affected backend tests and the frontend contract tests when a React consumer changed.

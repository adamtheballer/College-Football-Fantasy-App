---
name: add-fastapi-endpoint
description: Add or modify FastAPI endpoints in this repo, including routes, schemas, CRUD calls, and router registration in the main app. Use when creating new API paths or changing existing endpoint behavior.
---

# Add FastAPI Endpoint

## Quick checklist

- Choose or create a router file in `api/app/api/routes`.
- Define Pydantic request/response models in `api/app/schemas`.
- Add CRUD logic in `api/app/crud` to keep route handlers thin.
- Register the router in `api/app/main.py` with prefix and tags.
- Add/adjust tests under `tests/api`.

## Steps

1. Create or update a router module in `api/app/api/routes` and add an `APIRouter` instance.
2. Define endpoint functions with explicit status codes and response models.
3. Use dependency injection (`Depends(get_db)`) for database access.
4. Implement database logic in a `api/app/crud/<resource>.py` module.
5. Add Pydantic models in `api/app/schemas/<resource>.py` following the Base/Create/Read/List pattern.
6. Register the router in `api/app/main.py` with a stable prefix (if needed) and a clear tag.

## Repo patterns to mirror

- Return list endpoints as `{data, total, limit, offset}` (see `api/app/schemas/player.py`).
- Raise `HTTPException` with `status_code` and a short `detail` string for 404s and validation errors.
- Keep route handlers small; move filtering/joins into CRUD functions.

## Testing

- Add new tests in `tests/api` using the `client` fixture in `tests/conftest.py`.
- Assert status code, response shape, and key fields.

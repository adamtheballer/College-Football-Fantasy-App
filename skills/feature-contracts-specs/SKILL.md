---
name: feature-contracts-specs
description: Define and update API feature contracts and response shapes for this repo, including schema conventions and list wrappers. Use when specifying request/response behavior across API and UI.
---

# Feature Contracts and Specs

## Contract rules

- Define request and response models in `api/app/schemas`.
- Use `ConfigDict(from_attributes=True)` for read models that map ORM objects.
- Wrap list responses in a model with `data`, `total`, `limit`, and `offset` fields.
- Keep error responses consistent with `HTTPException(detail="...")`.

## Cross-layer alignment

- Ensure the response shapes match what `ui/lib/api_client.py` expects.
- Keep list endpoints stable; UI pages use `data` for tables.

## Spec updates to apply

1. Update Pydantic schemas to reflect the contract.
2. Update FastAPI route response models and status codes.
3. Update Bruno requests if you change paths or payloads.
4. Update Streamlit UI pages if inputs/outputs change.

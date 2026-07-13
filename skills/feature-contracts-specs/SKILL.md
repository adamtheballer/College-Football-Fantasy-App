---
name: feature-contracts-specs
description: Define FastAPI request, response, error, authentication, and pagination contracts for React-consumed features before implementation. Use when drafting or revising an endpoint contract or specification; use cross-stack-contract-parity to verify implemented code.
---

# Feature Contracts and Specs

## Contract rules

- Define request and response models in `api/app/schemas`.
- Use `ConfigDict(from_attributes=True)` for read models that map ORM objects.
- Preserve the endpoint's established collection shape. Paginated lists use `data`, `total`, `limit`, and `offset`; bounded collections may use `data` only or `data` plus `total`.
- Use stable string `detail` messages for domain `HTTPException` errors; specify FastAPI validation-error payloads and how the frontend translates them separately.
- Specify authentication and authorization requirements, including relevant headers, credentials, or cookies.

## Cross-layer alignment

- Inspect consumers in `web/client/lib/api.ts`, `web/client/hooks`, `web/client/types`, and the affected page or component.
- Keep list endpoints stable; React consumers expect `data`, `total`, `limit`, and `offset` where the API uses paginated wrappers.
- Specify casing, nullability, enums, pagination bounds, status codes, and error details explicitly.
- Use `$cross-stack-contract-parity` after implementation to verify both sides and their tests agree.

For specification-only requests, state the contract and stop without editing implementation files. If the contract belongs in `requirements/`, use `$write-technical-requirements` and follow the repository's GitHub issue publication rules.

## Implementation checklist, when implementation is requested

1. Update Pydantic schemas to reflect the contract.
2. Update FastAPI route response models and status codes.
3. Update React API helpers, types, hooks, and consumers when inputs or outputs change.
4. Update Bruno requests if you change paths or payloads.
5. Add backend and frontend tests for the changed contract and its failure cases.

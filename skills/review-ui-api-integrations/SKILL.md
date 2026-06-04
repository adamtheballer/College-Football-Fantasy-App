---
name: review-ui-api-integrations
description: Review full-stack changes in this repo across UI, API, database, tests, and integrations. Use when asked to review code, identify inconsistencies, find regressions, or check cross-layer alignment between `web`, `ui`, `api`, and external data sources.
---

# Review UI API Integrations

## Review Goal

- Find behavior regressions, contract mismatches, and missing follow-through across layers.
- Prioritize issues that can break real flows over style-only comments.

## Review Order

1. Define the user flow or API workflow being changed.
2. Check UI assumptions against the actual API contract.
3. Check schemas, CRUD or service logic, and persistence changes.
4. Check integration boundaries, cache behavior, and tests.
5. Check whether docs or Bruno requests should have changed too.

## What to Look For

### UI and UX risks

- Missing loading, empty, or error states.
- Forms that do not validate inputs before sending requests.
- UI fields or filters that do not match backend support.
- Pages that assume data is always present or non-null.

### API and schema risks

- Route handlers doing too much business logic.
- Request and response models missing fields, using inconsistent names, or not matching real payloads.
- Status codes or exceptions that break existing client expectations.
- List endpoints drifting away from `{data, total, limit, offset}` when that pattern should still apply.

### Database and migration risks

- Model changes without matching schema, CRUD, or migration updates.
- New tables or relationships not registered where Alembic or tests require them.
- Nullability or uniqueness changes that can break existing data.

### Integration risks

- Missing timeout or failure handling around external APIs.
- Silent fallbacks that hide bad upstream data.
- Data normalization performed too late, causing downstream branching or duplicate mappings.

### Validation gaps

- Contract changes without tests.
- New routes without Bruno coverage when relevant.
- Requirements or specs left stale after behavior changes.

## Output Format

- Findings first, ordered by severity.
- For each finding, include:
  - what breaks or is risky
  - where it lives
  - why it matters to the flow
  - the smallest credible fix
- If no findings are present, say that directly and then note any residual testing or environment gaps.

## Repo Files to Check

- `web/client`
- `web/shared/api.ts`
- `ui/pages`
- `ui/lib/api_client.py`
- `api/app/api/routes`
- `api/app/schemas`
- `api/app/crud`
- `api/app/models`
- `api/app/integrations`
- `tests/api`
- `bruno/collections/backend-api`

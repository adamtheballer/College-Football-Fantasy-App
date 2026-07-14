---
name: review-ui-api-integrations
description: Review full-stack changes in this repo across the React frontend, FastAPI backend, database, tests, and external integrations. Use when asked to review code, find regressions, or check cross-layer alignment.
---

# Review UI API Integrations

## Review Goal

- Find behavior regressions, contract mismatches, and missing follow-through across layers.
- Prioritize issues that can break real flows over style-only comments.

## Review Order

1. Resolve the exact diff or file scope and identify the user flow it changes.
2. Establish runtime reachability from React routes, FastAPI router registration, scheduled callers, or worker entrypoints. Trace reachable flows end to end and report intended features that are unmounted or have no production caller.
3. Check UI assumptions against actual Pydantic models and serialized responses; use `$cross-stack-contract-parity` when both sides changed.
4. Check transaction boundaries, migrations, background-worker invocation, external integrations, cache behavior, and tests.
5. Run the narrowest useful verification and check whether requirements, docs, or Bruno workflows became stale.

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
- Frontend types or fixtures that do not match actual FastAPI responses.
- API failures rendered as empty, preview, or successful states.
- A service or worker that has no production caller, scheduler, or route.
- Tests that reproduce their own mocked contract without exercising the implementation boundary.
- New routes without Bruno coverage when relevant.
- Requirements or specs left stale after behavior changes.

### Reachability and completion risks

- Dead or unmounted code being reviewed as if it ships.
- A UI action with no complete backend path, or a backend capability with no reachable UI when the feature requires one.
- Statuses with no legal path to completion or no handler for retries and failures.
- Multi-row mutations that can commit partial state.

## Output Format

- Findings first, ordered by severity.
- For each finding, include:
  - what breaks or is risky
  - where it lives
  - why it matters to the flow
  - the smallest credible fix
- If no findings are present, say that directly and then note any residual testing or environment gaps.
- Separate confirmed findings from unverified concerns; omit speculative style commentary.
- Include the verification performed and any runtime boundary that was not exercised.

## Repo Files to Check

- `web/client/App.tsx`
- `web/client`
- `web/client/lib/api.ts`
- `web/client/hooks`
- `web/client/types`
- `api/app/api/routes`
- `api/app/main.py`
- `api/app/schemas`
- `api/app/crud`
- `api/app/services`
- `api/app/models`
- `api/app/integrations`
- `tests/api`
- `web/client/**/*.spec.ts`
- `web/tests/e2e`
- `scripts`
- `.github/workflows`
- `bruno/collections/backend-api`

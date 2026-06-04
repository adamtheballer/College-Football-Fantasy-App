---
name: ui-api-client-caching
description: Maintain the Streamlit UI API client and caching behavior, including cache invalidation after mutations. Use when adding or changing API calls in `ui/lib/api_client.py`.
---

# UI API Client Caching

## Rules

- Wrap GET/list calls with `@st.cache_data(show_spinner=False)`.
- Do not cache POST/PUT/DELETE calls.
- After any write, call `st.cache_data.clear()` to invalidate cached reads.

## Request pattern

- Use `_request(method, path, payload)` for all calls.
- Build query strings with `urlencode`, skipping empty values.
- Keep `BASE_URL` sourced from `UI_API_BASE_URL` with a local default.

## Adding a new API helper

1. Add a cached GET function for read endpoints.
2. Add a non-cached function for writes and clear the cache.
3. Return parsed JSON (`dict`/`list`) or `None` for 204s.

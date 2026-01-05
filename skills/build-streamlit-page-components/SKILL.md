---
name: build-streamlit-page-components
description: Build or update Streamlit UI pages and components in this repo, using the existing page layout, forms, and API client patterns. Use when adding or editing UI pages under `ui/pages`.
---

# Build Streamlit Page Components

## Structure

- Keep page modules in `ui/pages` and follow the numeric prefix pattern (e.g., `1_Leagues.py`).
- Keep global app config in `ui/app.py` only.

## Common patterns

- Use `st.header`/`st.subheader` to structure pages.
- Wrap mutating actions in `st.form` and use `st.form_submit_button`.
- Validate inputs before calling the API client.
- Use `st.spinner` for requests and `st.success`/`st.error` for outcomes.
- Use `st.dataframe(..., use_container_width=True)` for tabular data.

## API integration

- Call API helpers from `ui/lib/api_client.py` rather than calling httpx directly.
- Keep UI error messages human-readable and include the exception text.

## Minimal example pattern

- Collect inputs in a form.
- Call an API helper on submit.
- Clear or refresh data by re-calling cached GET helpers.

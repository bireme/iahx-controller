# Fix per-field facet params (`f.*`) ignored on /search_form

## Problem
Sending `facet.field=who_regions&f.who_regions.facet.sort=asc` to `/search_form` did not forward
`f.who_regions.facet.sort` to Solr. `search_form` built `all_params` from `locals()`, which only holds
the declared function parameters; FastAPI discards undeclared form fields, so the `f.` prefix loop
never saw them. `/search_json` was not affected (`SearchParams` uses `extra='allow'`).

## Changes
- `controller/app.py`
  - `search_form` now receives `request: Request` and, when called as the form endpoint, merges the
    raw form data (`await request.form()`) with `locals()` into `all_params`.
  - `search_json` receives `request: Request` and passes it through to `search_form`.
- `controller/tests/test_app_endpoints.py`
  - Added `test_search_form_forwards_per_field_facet_params` and
    `test_search_json_forwards_per_field_facet_params`.

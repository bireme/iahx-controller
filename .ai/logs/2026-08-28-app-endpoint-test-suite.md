# App Endpoint Test Suite (happy path + error cases)

**Date:** 2026-08-28
**Branch:** `feature/app-endpoint-test-suite`
**Spec:** `.ai/features/001-app-endpoint-test-suite.md`
**Reference:** https://fastapi.tiangolo.com/tutorial/testing/

## Changes

### New files
- `controller/tests/conftest.py` — shared fixtures, replacing the setup boilerplate that
  lived inside `test_app.py`:
  - `sys.path` insertion for the `controller/` package
  - mock `lifespan` installed on `app.router.lifespan_context` (`AsyncMock` httpx client,
    `MagicMock` DeCS decoder — no Solr, no Redis, no network)
  - `client` — `TestClient(app, raise_server_exceptions=False)` as a context manager
  - `auth_headers` — valid `apikey` header
  - `solr_response(text=..., side_effect=...)` — factory wiring the fake Solr answer
  - `posted_query()` — `(url, query_map)` of the last POST sent to Solr
  - `decs_decode` — handle on the mocked decoder
- `controller/tests/test_app_endpoints.py` — 30 tests covering the `app.py` gaps:
  - **Auth/validation (5):** missing `apikey` header → 422 on both endpoints, wrong key → 401
    on `/search_json`, missing `site` → 422, non-integer `count` → 422
  - **`/search_json` (5), previously untested:** basic query, `index` prefixing
    (`ti:(malaria)`), `fq` list formatting, `count`/`facet.field` aliases reaching the Solr
    query map, `output=xml` → `wt=xslt` + `tr=export-xml.xsl`
  - **Solr transport errors (3):** `httpx.RequestError` → 400, `HTTPStatusError` 503 → 503,
    `HTTPStatusError` 404 → status passed through
  - **Query map construction (8):** no `q` → `*:*`, optional params forwarded, unset params
    omitted, `fb=type:10` → `f.type.facet.limit`, `facet.field.terms=type:a,b` →
    `{!ex=tab terms=a,b}type`, `output=solr` → raw text/xml with no `wt`, default →
    `wt=json`/`json.nl=arrarr`, `Cache-Control: no-cache` on JSON and XML responses
  - **DeCS decode branch (2):** decoder not called when no `^d`/`^s` codes are present;
    decode failure still returns 200 with subfield marks stripped (`malaria22016/01234`)
  - **`/healthcheck` (5):** wrong key → 401, missing header → 422, expected query map posted,
    Solr `RequestError` → 400, decode failure → 500 `"DeCS decode failed"`, unparsable
    result → 500 `"Error parsing healthcheck response"`

### Modified files
- `controller/tests/test_app.py` — removed the duplicated `sys.path` setup, mock lifespan and
  local `client` fixture (now in `conftest.py`); endpoint tests take the `auth_headers`
  fixture instead of a module-level `API_KEY` constant. No test cases changed.

No production code was changed. No new dependencies, no coverage tooling, no CI changes.

## Result

58 tests collected, all passing (28 pre-existing + 30 new), run offline in the dev container:

```
docker compose -f docker-compose-dev.yml run --rm --no-deps iahx_controller python -m pytest tests/ -q
58 passed, 9 warnings in 0.62s
```

`make dev_test` runs the same command against a running container.

## Findings (verified, deliberately not fixed)

Per the spec these are reported rather than patched — the tests assert current behavior.

1. **`/search_json` without `site` → 500.** `SearchParams.site` defaults to `None`, so the
   request reaches `set_solr_server(None, ...)` and fails on `None.replace()`. The global
   handler turns it into `500 {"detail": "Internal server error"}`; a 422 would be correct.
   Fix: make `site` required (`site: str`).
2. **Malformed `fb` → 500.** `fb="type"` (no colon) raises `IndexError` at
   `fb_param[1]` (`app.py:250`). Same for **`facet.field.terms` without a colon**
   (`app.py:259`). Both should be validation errors.
3. **`f.*` passthrough only works on the JSON path.** `all_params = all_params or locals()`
   means `/search_form` builds its parameter map from `locals()`, which cannot contain the
   dynamic `f.<field>.facet.limit` keys. Verified: `/search_json` forwards
   `f.type.facet.limit` to Solr, `/search_form` silently drops it.
4. **Deprecated Pydantic v2 APIs in `search_json`.** `param.dict()` (`app.py:165`) emits
   `PydanticDeprecatedSince20` — use `model_dump()`. Pydantic 2.12 also warns
   `UnsupportedFieldAttributeWarning` for the `count`, `facet.field` and `facet.field.terms`
   aliases in `controller/schemas.py`; the aliases still work today, but the warning suggests
   moving them to `Annotated[...]` metadata before a future Pydantic release.

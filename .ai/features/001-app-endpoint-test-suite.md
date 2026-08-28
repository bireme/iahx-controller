# 001 — App Endpoint Test Suite (happy path + error cases)

**Status:** Spec
**Date:** 2026-08-28
**Reference:** https://fastapi.tiangolo.com/tutorial/testing/

## Summary

Extend and restructure the existing `controller/tests/` suite with a `conftest.py`
holding shared fixtures (FastAPI tutorial pattern), then close the coverage gaps in
`controller/app.py` — happy paths and error paths — without touching production code.

## Decisions (resolved with the user)

| Branch | Decision |
| --- | --- |
| Existing 28-test suite | **Keep and extend**; restructure shared setup into `conftest.py` |
| Solr HTTP boundary | **Mock `app.state.client.post`** with `AsyncMock` via fixture. No new deps, no `respx`, no DI refactor |
| Coverage scope | **`controller/app.py` only.** `decode_decs.py` gaps and `controller/util/*` scripts are out of scope |
| Done bar | Whole suite green via `make dev_test`; no coverage tooling, no CI changes |
| Bugs found | **Assert current behavior**, list suspicious findings in the implementation log; do not patch `app.py` |

## Goals

- Every route in `app.py` (`/search_form`, `/search_json`, `/healthcheck`) has at least
  one happy-path and one error-path test.
- Every `raise HTTPException` / `except` branch in `app.py` is reached by a test.
- Shared test setup lives in `controller/tests/conftest.py`; no `sys.path` or
  lifespan-patching boilerplate duplicated across test files.
- Suite runs offline: no Solr, no Redis, no network.
- `make dev_test` passes.

## Design

### `controller/tests/conftest.py`

- `sys.path` insertion for the `controller/` package (moved out of the test modules).
- Mock lifespan installed on `app.router.lifespan_context`, setting
  `app.state.client = AsyncMock()` and `app.state.decs = MagicMock()`.
- `client` fixture: `TestClient(app, raise_server_exceptions=False)` as a context manager
  so the lifespan runs.
- `auth_headers` fixture: `{"apikey": API_TOKEN}` (env `API_TOKEN`, default `"8983"`).
- `solr_response` factory fixture: takes response text (and optional side effect),
  wires `app.state.client.post`, returns the mock so tests can assert the posted `data`.
- `posted_query` helper: reads `app.state.client.post.call_args` → `(url, data)`.

### New test module

`controller/tests/test_app_endpoints.py` for the endpoint/error-branch tests;
existing `test_app.py` keeps the pure-function unit tests (`format_query`,
`fix_double_quotes`, `set_solr_server`) and its current endpoint tests, minus the
setup boilerplate now in `conftest.py`.

## Test cases

### Auth & request validation
1. `/search_form` with no `apikey` header → 422
2. `/search_json` with wrong `apikey` → 401 `"Invalid api key"`
3. `/search_json` with no `apikey` header → 422
4. `/search_form` missing required `site` field → 422
5. `/search_form` with non-integer `count` → 422

### `/search_json` (currently untested)
6. Basic query → 200, body has `diaServerResponse`
7. `index` set → posted `q` is `index:(formatted query)`
8. `fq` list → each entry passed through `format_query`
9. Aliases `count` and `facet.field` reach the Solr `query_map`
10. `output: "xml"` → `text/xml` response, `wt=xslt`, `tr=export-xml.xsl`

### Solr transport errors (`send_post_command`)
11. `httpx.RequestError` → 400 `"Invalid POST or connection error with Solr server"`
12. `httpx.HTTPStatusError` with a 503 response → 503 `"Error response from Solr server"`
13. `httpx.HTTPStatusError` with a 404 response → status passed through as 404

### Query-map construction (assert on the posted form data)
14. No `q` → `q == "*:*"`
15. `start`, `sort`, `rows`, `tag`, `fl`, `facet` forwarded when set; absent when unset
16. `fb="type:10"` → `f.type.facet.limit == "10"`
17. `facet.field.terms="type:a,b"` → `facet.field` gains `{!ex=tab terms=a,b}type`
18. `output="solr"` → no `wt`/`json.nl`; response is `text/xml`, body is raw Solr text
19. Default output → `wt=json`, `json.nl=arrarr`
20. `Cache-Control: no-cache` present on both the JSON and XML responses

### DeCS decode branch
21. Response with no `^d`/`^s` codes → `app.state.decs.decode` never called
22. `decode` raises → still 200; leftover `^d` markers stripped and `^sNNN` rendered as `/NNN`

### `/healthcheck`
23. Wrong `apikey` → 401; missing header → 422
24. Posts the expected query map (`q=malaria`, `rows=1`, `facet=false`, `wt=json`)
25. Solr `RequestError` → 400
26. `decode` raises → 500 `"DeCS decode failed"`
27. Non-JSON decoded result → 500 `"Error parsing healthcheck response"`

## Notes

- Test functions are plain `def` and `TestClient` calls are synchronous, per the
  FastAPI testing tutorial; the app's `async def` routes are driven by `TestClient`.
- The `client` fixture must be used as a context manager so `lifespan` runs and
  `app.state` is populated.
- Mocked Solr responses need `raise_for_status` as a plain `MagicMock` (not async).
- For case 22, the fake Solr text must stay valid JSON after the `^d`/`^s` regex
  substitutions, e.g. `{"docs":[{"t":"malaria^d22016^s01234"}]}`.

## Observations to record (not to fix in this feature)

Verify each during implementation; if confirmed, list in the implementation log:
- `all_params = all_params or locals()` in `search_form` — relies on `locals()` snapshot
  ordering, and makes `f.*` passthrough reachable only from the `/search_json` path.
- `SearchParams.dict()` is Pydantic-v2-deprecated (`model_dump`).
- `SearchParams.site` defaults to `None`, so `/search_json` without `site` reaches
  `set_solr_server(None, ...)` and fails as a 500 rather than a 422.
- `fb` and `facet.field.terms` without a `:` raise `IndexError` → 500.

## Out of scope

- `controller/decode_decs.py` additional cases (fr language, leading zeros, `close()`).
- `controller/util/import_decs_*.py`.
- Coverage tooling, thresholds, CI workflow.
- Any change to `controller/app.py`.

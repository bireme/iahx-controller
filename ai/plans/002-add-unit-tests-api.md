# Plan: Add Unit Tests for iahx-controller API

## Context

The project has no tests. After the recent error handling fixes, we need a simple test suite to verify the API endpoints and utility functions work correctly, and to catch regressions. The user wants standard Python `pytest` (via FastAPI's test client pattern), simple tests, and Makefile commands to run them in the dev environment.

## Approach

Use `pytest` + `httpx` (already a dependency via FastAPI) with FastAPI's `TestClient`. Mock Redis to avoid needing a running Redis instance. No new heavy dependencies — just add `pytest` to dev dependencies.

## Files to Create/Modify

### 1. `controller/tests/__init__.py` (new, empty)

### 2. `controller/tests/test_app.py` (new)

Tests for `app.py` functions and endpoints:

- **`test_format_query_lowercase`** — verifies query lowercasing and operator uppercasing
- **`test_format_query_preserves_quoted_strings`** — quoted strings stay intact
- **`test_format_query_dollar_to_wildcard`** — `$` → `*` replacement
- **`test_format_query_and_not_to_not`** — `AND NOT` → `NOT` conversion
- **`test_fix_double_quotes_curly`** — curly quotes normalized
- **`test_fix_double_quotes_unmatched`** — unmatched quote gets closed
- **`test_set_solr_server_default`** — correct URL with default server/port
- **`test_set_solr_server_with_col`** — URL includes collection suffix
- **`test_set_solr_server_random_selection`** — comma-separated servers pick one
- **`test_search_form_unauthorized`** — returns 401 with wrong apikey
- **`test_search_form_basic_query`** — mock Solr POST, verify 200 + JSON response structure
- **`test_search_form_xml_output`** — mock Solr POST with output=xml, verify XML response
- **`test_healthcheck_success`** — mock Solr + Redis, verify 200
- **`test_global_exception_handler`** — force an unhandled exception, verify 500 + logged error

### 3. `controller/tests/test_decode_decs.py` (new)

Tests for `decode_decs.py`:

- **`test_decode_replaces_codes`** — mock Redis pipeline, verify `^d` codes replaced with descriptor text
- **`test_decode_qualifier_prefix`** — `^s` codes get `/` prefix
- **`test_decode_fallback_on_missing`** — missing Redis keys fall back to raw code
- **`test_bulk_fetch_redis_error`** — mock Redis raising `ConnectionError`, returns empty dict
- **`test_bulk_fetch_unicode_error`** — mock bad bytes, returns empty dict

### 4. `pyproject.toml` (modify)

Add pytest to dev dependencies:
```toml
[tool.poetry.group.dev.dependencies]
pytest = "^9.0"
httpx = "^0.28"  # needed for TestClient async
```

Add pytest config:
```toml
[tool.pytest.ini_options]
testpaths = ["controller/tests"]
```

### 5. `Makefile` (modify)

Add test commands after the existing dev section:

```makefile
## TEST shortcuts
test:
	@cd controller && python -m pytest tests/ -v

test_docker:
	@docker compose -f $(COMPOSE_FILE_DEV) exec iahx_controller python -m pytest tests/ -v
```

## Test Strategy

- All tests use **mocks** for external dependencies (Redis, Solr/httpx) — no running services needed
- Use `unittest.mock.patch` and `unittest.mock.AsyncMock` for async httpx calls
- Use FastAPI `TestClient` (from `starlette.testclient`) for endpoint tests
- Override `app.state.decs` with a mocked `DecodDeCS` in endpoint tests
- Override `app.state.client` with a mocked `httpx.AsyncClient` to avoid real Solr calls

## Verification

1. Run `make test` locally (requires poetry install with dev deps)
2. Run `make test_docker` inside the dev container
3. All tests should pass with no external services running

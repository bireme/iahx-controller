# Current Feature: App Endpoint Test Suite

## Status

<!-- Not Started|In Progress|Completed -->

Completed

## Goals

<!-- Goals & requirements -->

- Every route in `controller/app.py` (`/search_form`, `/search_json`, `/healthcheck`) has at least one happy-path and one error-path test
- Every `raise HTTPException` / `except` branch in `app.py` is reached by a test
- Shared test setup lives in `controller/tests/conftest.py`; no `sys.path` or lifespan-patching boilerplate duplicated across test modules
- Suite runs fully offline: no Solr, no Redis, no network
- `make dev_test` passes with the whole suite green

## Notes

<!-- Any extra notes -->

Spec: [.ai/features/001-app-endpoint-test-suite.md](features/001-app-endpoint-test-suite.md) — contains the full 27-case test list.

Reference: https://fastapi.tiangolo.com/tutorial/testing/

Decisions already resolved:

- Keep the existing 28-test suite; restructure shared setup into `conftest.py` and add `controller/tests/test_app_endpoints.py`
- Fake the Solr boundary by mocking `app.state.client.post` with `AsyncMock` — no new dependencies, no `respx`, no DI refactor
- Scope is `controller/app.py` only; `decode_decs.py` gaps and `controller/util/*` are out of scope
- No coverage tooling, thresholds, or CI changes
- Tests assert **current** behavior; suspicious code is reported in the implementation log, not patched (no changes to `app.py`)

Four pre-flagged findings to verify and log rather than fix: `all_params or locals()`, Pydantic-v2-deprecated `param.dict()`, `/search_json` without `site` returning 500 instead of 422, and `IndexError` on malformed `fb` / `facet.field.terms`.

## Detailed Plan

<!-- Link to detailed plan file -->

## History

<!-- Keep this updated. Earliest to latest -->

- 2026-08-28: Starting App Endpoint Test Suite
- 2026-08-28: Implemented App Endpoint Test Suite — conftest.py + 30 new tests, 58 passing; log at .ai/logs/2026-08-28-app-endpoint-test-suite.md

# Add Unit Tests for API

**Date:** 2026-04-02

## Changes

### New files
- `controller/tests/__init__.py` — test package init
- `controller/tests/test_app.py` — 19 tests for app.py (format_query, fix_double_quotes, set_solr_server, search_form endpoint, healthcheck endpoint, global exception handler)
- `controller/tests/test_decode_decs.py` — 9 tests for decode_decs.py (decode, bulk_fetch_descriptors, Redis error handling, Unicode error handling)

### Modified files
- `pyproject.toml` — added `pytest ^9.0` and `httpx ^0.28` to dev dependencies, added `[tool.pytest.ini_options]`
- `poetry.lock` — updated with new dev dependencies
- `Dockerfile` — dev stage now installs dev dependencies (`poetry install --with dev`)
- `Makefile` — added `test` (local) and `test_docker` (container) targets
- `controller/app.py` — added default `"INFO"` for `LOG_LEVEL` env var to prevent crash when unset

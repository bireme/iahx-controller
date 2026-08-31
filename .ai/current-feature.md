# Current Feature: Replace Poetry with uv

## Status

<!-- Not Started|In Progress|Completed -->

Completed

## Goals

<!-- Goals & requirements -->

- Convert `pyproject.toml` from the Poetry format (`[tool.poetry]`, `[tool.poetry.dependencies]`, `[tool.poetry.group.dev.dependencies]`, `poetry-core` build backend) to the PEP 621 `[project]` layout with uv's `[dependency-groups]` for dev deps
- Generate `uv.lock` and remove `poetry.lock`
- Update the `Dockerfile` to install and use uv instead of `pip install poetry` + `poetry install`, following the `api-users` layout (uv project root at `/`, `WORKDIR app/`, per-stage `uv sync`), and move the base image to `python:3.14-slim`
- Keep `[tool.pytest.ini_options]` (`testpaths = ["controller/tests"]`) working unchanged
- Keep the `Makefile` as-is apart from `dev_test`, which must switch to `uv run pytest`
- Verify the full test suite (58 tests) still passes after the migration

## Notes

<!-- Any extra notes -->

- Inline feature description, no spec file in `.ai/features/`.
- Follows the conventions already in place in the sibling project `bireme/api-users`, which has
  already migrated to uv (Dockerfile shape, PEP 621 pyproject, `.python-version`).
- Poetry is referenced in: `pyproject.toml`, `Dockerfile`, `poetry.lock`, plus historical docs
  (`.ai/logs/2026-04-02-add-unit-tests.md`, `ai/plans/002-add-unit-tests-api.md`) which are
  records and should not be rewritten.
- Runtime moves from Python 3.12 to 3.14 (`requires-python = ">=3.14"`, `python:3.14-slim`).
  `pandas` must stay at `>=2.3.3` and `mysql-connector-python` at `>=9.5.0` — earlier releases
  have no cp314 wheels.
- `package-mode = false` maps to simply omitting `[build-system]`, so uv treats the project as
  virtual.
- Decisions taken: uv installed via `COPY --from=ghcr.io/astral-sh/uv:latest`; uv project root
  is `/` in the image so `/.venv` is not shadowed by the `./controller:/app` dev bind mount;
  no `UV_PROJECT_ENVIRONMENT`/`VIRTUAL_ENV`/`PATH` overrides; `controller/` is not renamed; the
  only Makefile change is `dev_test`.

## Detailed Plan

<!-- Link to detailed plan file -->

[003-replace-poetry-with-uv.md](plans/003-replace-poetry-with-uv.md)

## History

<!-- Keep this updated. Earliest to latest -->

- 2026-08-28: App Endpoint Test Suite — added `controller/tests/conftest.py` with shared offline fixtures and `test_app_endpoints.py` with 30 tests covering happy and error paths for `/search_form`, `/search_json` and `/healthcheck`; 58 tests passing. Spec: [001-app-endpoint-test-suite.md](features/001-app-endpoint-test-suite.md), log: [2026-08-28-app-endpoint-test-suite.md](logs/2026-08-28-app-endpoint-test-suite.md)
- 2026-08-31: Starting Replace Poetry with uv — following plan [003-replace-poetry-with-uv.md](plans/003-replace-poetry-with-uv.md)

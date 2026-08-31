# 2026-08-31 — Replace Poetry with uv

Migrated dependency management from Poetry to [uv](https://docs.astral.sh/uv/) and moved the
runtime from Python 3.12 to 3.14. Follows the conventions already established in the sibling
project `bireme/api-users`. Plan: [003-replace-poetry-with-uv.md](../plans/003-replace-poetry-with-uv.md).

No application code changed.

## Changes

- **`pyproject.toml`** — rewritten from `[tool.poetry]` tables to PEP 621 `[project]` plus
  `[dependency-groups]` for the dev group. Poetry carets expanded to explicit ranges
  (`^0.115.0` → `>=0.115.0,<0.116.0`). `requires-python = ">=3.14"`.
  `[tool.pytest.ini_options]` carried over unchanged.
  The `[build-system]` table was dropped rather than ported: its absence is uv's equivalent of
  Poetry's `package-mode = false`, so uv treats the project as virtual.
- **`poetry.lock`** — deleted, replaced by **`uv.lock`** (61 packages, `requires-python >=3.14`).
- **`.python-version`** — new, pinned to `3.14`.
- **`Dockerfile`** — `pip install poetry` replaced by
  `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`; base image `python:3.12-slim` →
  `python:3.14-slim`; the shared `poetry install` in the base stage became a per-stage
  `uv sync` (dev) / `uv sync --no-dev` (prod); `ENV POETRY_VIRTUALENVS_CREATE=false` dropped
  entirely; `ENV X 1` updated to the non-deprecated `ENV X=1` form.
- **`docker-compose.yml`** — removed the prod `command:` override, which duplicated the
  Dockerfile CMD verbatim. The Dockerfile is now the single source of truth for the entrypoint.
- **`Makefile`** — `dev_test` switched from `python -m pytest` to `uv run pytest`, since with no
  `PATH` override the container's bare `python` is the system interpreter without dependencies.
- **`.gitignore`** — added `.venv/` and `__pycache__/`.

## Why the venv lives at `/`, not `/app`

`docker-compose-dev.yml` bind-mounts `./controller` onto `/app`. Copying `pyproject.toml` and
`uv.lock` to `/` means `uv sync` creates the venv at `/.venv`, above the mount point, so the dev
bind mount can own `/app` outright without shadowing it:

```
/pyproject.toml, /uv.lock, /.venv    <- uv project root (image only)
/app                                 <- source: bind-mounted in dev, COPYed in prod (WORKDIR)
```

`uv run` from `/app` walks up, finds the project at `/`, and uses `/.venv`. This removes any need
for `UV_PROJECT_ENVIRONMENT`, `VIRTUAL_ENV` or `PATH` overrides, keeps `controller/` named as it
is, and keeps the flat imports working (`from decode_decs import DecodDeCS`, `uvicorn app:app`).

## Deviation from the plan: `--no-dev` on the prod CMD

The approved plan had the prod CMD as `uv run uvicorn ...`. Testing revealed a real bug: `uv run`
re-syncs the environment by default and **includes the dev group**, so a prod container built with
`uv sync --no-dev` would try to download pytest and friends at container start — failing outright
without network access. The prod CMD is therefore:

```
CMD uv run --no-dev uvicorn app:app --host 0.0.0.0 --port 8000 ${APP_RUN_PARAMS}
```

Verified: both stages now start with `--network=none`.

## Verification

Container DNS was broken during the first verification pass; the environment was fixed and
everything below was re-run against the real stack.

| Check | Result |
| --- | --- |
| `uv lock` / `uv sync` | 61 packages resolved for `>=3.14` |
| `make dev_build` | OK |
| Prod image build (`--target prod`) | OK |
| `make dev_start` | both containers up; `fastapi dev` reports "Uvicorn running on http://0.0.0.0:8000" |
| `make dev_test` (live stack) | **58 passed** on CPython 3.14.7 |
| Dev + prod container start with `--network=none` | OK (after the `--no-dev` fix) |
| `grep -rn poetry` | only historical `.ai` / `ai` documents remain |

### End-to-end HTTP smoke test

Against the running dev stack on `${APP_PORT}`:

| Request | Result |
| --- | --- |
| `GET /healthcheck` with no `apikey` header | HTTP 422 (validation) |
| `GET /healthcheck` with a wrong `apikey` | HTTP 401 `{"detail":"Invalid api key"}` |
| `GET /healthcheck` with the valid `apikey` | HTTP 400 `{"detail":"Invalid POST or connection error with Solr server"}` |
| `GET /docs` | HTTP 200 |

The 400 is not a defect: authentication and routing succeed and the request reaches the Solr
layer, but the configured backend `iahx-idx01.bireme.br:8986` is unreachable from this machine
(TCP connect times out — it is on the internal BIREME network). The endpoint correctly reports
the connection failure.

To exercise a real backing service rather than a stubbed one, the Redis-backed DeCS decoder was
run against the live `iahx-controller-cache` container:

```
input : {"numFound": 1, "docs": [{"mj_cluster": ["^d50545"]}]}
output: {"numFound": 1, "docs": [{"mj_cluster": ["Plastoquinol-Plastocianina Redutase"]}]}
```

So the app running on uv / Python 3.14.7 connects to Redis and decodes descriptors correctly.

### Note on local (non-Docker) runs

The locally installed uv is 0.7.3, which is too old to fetch a stable CPython 3.14; it resolves to
the pre-release `3.14.0a6`, on which `pytest` segfaults (exit 139). The 58 tests pass on stable
3.14.7 inside the container. Upgrading local uv (`uv self update`) is recommended before running
`uv run pytest` outside Docker.

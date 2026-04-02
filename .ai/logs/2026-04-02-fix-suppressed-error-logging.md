# Fix Suppressed Error Logging in Production

**Date:** 2026-04-02

## Problem

API returning 503 errors in production but logs only showed INFO messages. Unhandled exceptions in post-Solr processing (DeCS decode, JSON parsing) were crashing silently because no try/except blocks existed and errors bypassed loguru.

## Changes

### `controller/app.py`

- Added global `@app.exception_handler(Exception)` to catch and log any unhandled exception via loguru, returning a proper 500 JSON response.
- Wrapped `app.state.decs.decode()` call in `search_form` with try/except to log DeCS decode failures.
- Wrapped `json.loads()` in `search_form` with try/except for `JSONDecodeError`, returning a 500 with logged error.
- Added same error handling to `healthcheck` endpoint for both decode and JSON parsing.

### `controller/decode_decs.py`

- Wrapped `pipeline.execute()` in `bulk_fetch_descriptors` with try/except for `redis.ConnectionError`, `redis.TimeoutError`, and `redis.RedisError`. Returns empty dict on failure so the response can still be served with raw codes.
- Wrapped `.decode('utf-8')` dict comprehension with try/except for `UnicodeDecodeError`.

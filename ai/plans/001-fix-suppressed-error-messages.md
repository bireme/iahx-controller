# Plan 001: Fix Suppressed Error Messages in Production

**Date:** 2026-04-02
**Status:** Pending
**Problem:** API returns 503 errors in production but logs only show INFO messages — errors are silently swallowed.

## Root Causes

### 1. Unhandled exceptions in `search_form` after Solr call (CRITICAL)

In `controller/app.py:243-258`, after `send_post_command` succeeds, three operations can fail with no try/except:

- **Line 248** — `app.state.decs.decode(result, lang)`: calls Redis via `pipeline.execute()` in `decode_decs.py:60`. Any Redis connection error, timeout, or data corruption raises an unhandled exception.
- **Lines 251-253** — `re.sub()` operations on the decoded result.
- **Line 258** — `json.loads(result)`: if the DeCS decode or regex corrupts the JSON structure, this throws `JSONDecodeError`.

Since these exceptions are never caught, they bubble up to FastAPI/uvicorn's default 500 handler — which does not log through loguru.

### 2. `send_post_command` only catches httpx errors

`app.py:80-95` catches `httpx.RequestError` (returns 400) and `httpx.HTTPStatusError` (returns upstream status code). But unhandled exceptions in post-processing bypass this entirely. The request reaches Solr fine (INFO logged at line 78), Solr responds OK, then post-processing crashes silently.

### 3. Logging gap: loguru vs uvicorn's standard logging

- Line 19: `logger.remove()` removes loguru's default stderr handler.
- Line 20: `logger.add(sys.stderr, level="INFO")` — only loguru-based logs go here.
- Uvicorn's own error handler uses Python's standard `logging` module, not loguru. Unhandled exceptions logged through `logging.error()` may go to a different stream or be suppressed.

### 4. `decode_decs.py` has zero error handling

```python
# Line 57-60 — no try/except around Redis
pipeline = self.redis_client.pipeline()
results = pipeline.execute()  # crashes if Redis is down/slow

# Line 75 — can raise UnicodeDecodeError
return {k: v.decode('utf-8') if v else None for k, v in descriptors.items()}
```

### 5. The 503 comes from nginx-proxy

`docker-compose.yml` shows the app behind an external `nginx-proxy` network. When uvicorn workers crash or become exhausted (10 workers), nginx returns 503 Service Unavailable.

## Failure Sequence

```
Request arrives
  -> set_solr_server (INFO logged)
  -> send_post_command (INFO logged)
  -> Solr responds OK
  -> decs.decode() CRASHES (Redis error / bad data)
  -> Exception unhandled
  -> uvicorn returns 500
  -> nginx may convert to 503
  -> No loguru ERROR is ever emitted
```

## Recommended Fixes

### Fix 1: Wrap post-Solr processing in try/except (`controller/app.py`)

Wrap lines 246-258 in `search_form` with try/except that logs via `logger.error()` and returns a proper HTTP error response. Same for healthcheck endpoint (lines 283-285).

### Fix 2: Add error handling to `decode_decs.py`

Add try/except around `pipeline.execute()` (line 60) and `.decode('utf-8')` (line 75) in `bulk_fetch_descriptors`. On Redis failure, log the error and return an empty dict so the response can still be served (with encoded DeCS codes instead of decoded names).

### Fix 3: Add a global FastAPI exception handler (`controller/app.py`)

Add an `@app.exception_handler(Exception)` that logs unhandled exceptions through loguru and returns a 500 JSON response. This ensures no exception ever goes unlogged.

### Fix 4: Same treatment for `healthcheck` endpoint

`healthcheck` (line 283-285) has the same decode + json.loads pattern with no error handling.

## Files to Modify

- `controller/app.py` — add try/except in `search_form`, `healthcheck`; add global exception handler
- `controller/decode_decs.py` — add error handling in `bulk_fetch_descriptors`

## Verification

1. Stop Redis container and send a search request — should return a proper error response and log an ERROR message
2. Send a request that triggers DeCS decode — verify error is logged if decode fails
3. Check that normal requests still work correctly with decode
4. Verify log output contains ERROR level messages when exceptions occur

# Current Feature: Native XML Output and DeCS Entity Escaping

<!-- Feature Name -->

## Status

<!-- Not Started|In Progress|Completed -->

Completed

## Goals

<!-- Goals & requirements -->

- `output=xml` requests Solr's native XML writer: `wt=xml`, and the `tr` parameter is removed entirely
- DeCS descriptors substituted into XML responses are XML-escaped so the payload stays well-formed
- JSON output and `/healthcheck` behavior are unchanged
- Test suite updated and passing

## Notes

<!-- Any extra notes -->

Spec: [004-native-xml-output-and-entity-escaping.md](features/004-native-xml-output-and-entity-escaping.md)

Key decisions from the spec interview:

- **Where to escape:** inside `DecodDeCS.decode` via a new `escape_xml: bool = False`
  argument, applied to the Redis-sourced descriptor only — never as a post-pass over the
  full response, which would escape Solr's own markup.
- **Which outputs escape:** `output in ['xml', 'solr']`, matching exactly the branch that
  returns `media_type="text/xml"` (`app.py:265`). `/healthcheck` passes nothing.
- **Which characters:** `&`, `<`, `>` via stdlib `xml.sax.saxutils.escape`. Quotes are not
  escaped — Solr's native XML puts field values in text nodes, never attributes.
- **Payload shape:** native Solr XML is the goal; `export-xml.xsl` is not reimplemented.

Verified against `redis_data/decs-2025.rdb`: terms are stored raw (zero `&amp;`, real terms
like `anatomy & histology`), so escaping can never double-apply.

**Risk:** breaking change for consumers of `output=xml` — they now receive native Solr XML
(`<response><result><doc>…`) instead of the `export-xml.xsl` export shape.

Files affected: `controller/app.py` (221-226, 256), `controller/decode_decs.py`,
`controller/tests/test_app_endpoints.py`, `controller/tests/test_decode_decs.py`

## Detailed Plan

<!-- Link to detailed plan file -->

## History

<!-- Keep this updated. Earliest to latest -->

- 2026-08-28: App Endpoint Test Suite — added `controller/tests/conftest.py` with shared offline fixtures and `test_app_endpoints.py` with 30 tests covering happy and error paths for `/search_form`, `/search_json` and `/healthcheck`; 58 tests passing. Spec: [001-app-endpoint-test-suite.md](features/001-app-endpoint-test-suite.md), log: [2026-08-28-app-endpoint-test-suite.md](logs/2026-08-28-app-endpoint-test-suite.md)
- 2026-08-31: Replace Poetry with uv — migrated to uv + PEP 621 `pyproject.toml`, `uv.lock` replaces `poetry.lock`, runtime moved to Python 3.14; Dockerfile follows the `api-users` layout (uv project root at `/`, venv at `/.venv`, per-stage `uv sync`); 58 tests passing on CPython 3.14.7. Plan: [003-replace-poetry-with-uv.md](plans/003-replace-poetry-with-uv.md), log: [2026-08-31-replace-poetry-with-uv.md](logs/2026-08-31-replace-poetry-with-uv.md)
- 2026-09-09: Starting Native XML Output and DeCS Entity Escaping

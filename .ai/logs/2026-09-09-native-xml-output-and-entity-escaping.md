# Native XML Output and DeCS Entity Escaping

Date: 2026-09-09
Branch: `feature/native-xml-output-and-entity-escaping`
Spec: [004-native-xml-output-and-entity-escaping.md](../features/004-native-xml-output-and-entity-escaping.md)

## Summary

`output=xml` now asks Solr for its native XML writer instead of the removed XSLT
response writer, and DeCS descriptors spliced into XML responses are entity-escaped
so the payload stays well-formed.

## Changes

### `controller/app.py`

- Response writer selection: `wt=xslt` + `tr=export-xml.xsl` replaced by `wt=xml`.
  The `tr` parameter is no longer sent at all. `output=solr` (no `wt`) and the
  default JSON path (`wt=json`, `json.nl=arrarr`) are unchanged.
- Decode call now passes `escape_xml=output in ['xml', 'solr']`, matching exactly
  the branch that returns `media_type="text/xml"`.

### `controller/decode_decs.py`

- `DecodDeCS.decode` gains `escape_xml=False`. Defaulting to `False` keeps every
  existing caller — notably `/healthcheck`, which parses its result as JSON —
  behaving as before.
- When enabled, only the Redis-sourced descriptor is escaped, via stdlib
  `xml.sax.saxutils.escape` (`&`, `<`, `>`). No new dependency.
- Escaping is applied before the `^s` qualifier `/` prefix, and never to the
  surrounding response text. Escaping at the substitution site is the whole point:
  a post-pass over the full string would escape Solr's own markup and re-escape
  existing entities.
- The no-descriptor-found fallback (`f"{subcampo}{codigo}"`) is left alone — it
  yields only `^d`/`^s` plus digits.

### Tests

- `test_app_endpoints.py::test_search_json_xml_output` — now asserts `wt == "xml"`
  and `"tr" not in query_map`.
- `test_app_endpoints.py` — two new endpoint tests: an `output=xml` response
  carrying a `&`-bearing term is parseable by `xml.etree.ElementTree` and is called
  with `escape_xml=True`; the JSON path is called with `escape_xml=False`.
- `test_decode_decs.py` — five new unit tests: escaping on, escaping off by
  default, surrounding markup not double-escaped, qualifier term escaped before the
  `/` prefix, and the missing-descriptor fallback left intact.

## Verification

Terms are stored raw in Redis — checked `redis_data/decs-2025.rdb`: zero `&amp;`
occurrences and real terms such as `anatomy & histology`. Escaping therefore can
never double-apply.

Suite run via `make dev_test`: **63 passed, 2 failed**.

The 2 failures (`test_set_solr_server_default`, `test_set_solr_server_with_col`) are
pre-existing and unrelated — verified by stashing this feature's changes and
re-running: **56 passed, 2 failed**, the same two. They fail because the dev
container's `.env` sets `SOLR_PORTAL`, which `set_solr_server` reads in preference
to the `DEFAULT_SOLR_SERVER` value the tests patch.

## Environment note

The tests cannot currently run on the host: `uv` resolves the project to a locally
installed **CPython 3.14.0a6** alpha, on which `import fastapi` segfaults (exit 139).
`uv python install 3.14` re-resolves to that same alpha. Running through the dev
container, which has a working 3.14, is the reliable path for now.

## Risk

Breaking change for consumers of `output=xml`: they now receive native Solr XML
(`<response><result><doc>…`) rather than the `export-xml.xsl` export shape. This was
confirmed as the intent during the spec interview; `export-xml.xsl` was deliberately
not reimplemented.

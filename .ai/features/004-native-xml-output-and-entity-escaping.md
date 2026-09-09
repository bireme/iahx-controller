# Native XML Output and DeCS Entity Escaping

## Summary

Replace the deprecated Solr XSLT response writer with Solr's native XML writer for
`output=xml`, and escape XML entities in DeCS descriptors substituted into
XML responses so the payload stays well-formed.

## Background

`controller/app.py:221-223` currently asks Solr for an XSL-transformed response:

```python
if output == "xml":
    query_map['wt'] = "xslt"
    query_map['tr'] = "export-xml.xsl"
```

The XSLT response writer no longer exists in modern Solr, so this request fails.

Independently, DeCS decoding (`controller/decode_decs.py:14-51`) replaces `^d`/`^s`
codes with descriptor terms fetched from Redis and splices them straight into the
already-serialized Solr response. Terms are stored raw — verified against
`redis_data/decs-2025.rdb`: zero `&amp;` occurrences, and real terms such as
`anatomy & histology` are present. Splicing a raw `&` into an XML document makes it
malformed.

## Goals

- `output=xml` requests Solr's native XML writer: `wt=xml`, no `tr` parameter.
- DeCS descriptors substituted into XML responses are XML-escaped.
- JSON output and `/healthcheck` behavior are unchanged.
- Test suite updated and passing.

## Requirements

### 1. Response writer

- `output == "xml"` → `query_map['wt'] = "xml"`; the `tr` key is not set at all.
- `output == "solr"` → unchanged: no `wt`, no `json.nl`.
- Any other value → unchanged: `wt=json`, `json.nl=arrarr`.

### 2. Entity escaping

- `DecodDeCS.decode` gains a keyword argument `escape_xml: bool = False`.
  Defaulting to `False` keeps every existing caller's behavior intact.
- When `escape_xml` is true, only the descriptor term fetched from Redis is escaped,
  using `xml.sax.saxutils.escape` (stdlib — no new dependency). Characters escaped:
  `&`, `<`, `>`. Quotes are not escaped: Solr's native XML places field values in
  text nodes (`<str name="mh">…</str>`), never in attribute values.
- Escaping is applied to the descriptor *before* the `^s` qualifier `/` prefix is
  added, and never to the surrounding response text. This is the whole point of
  escaping at the substitution site: a post-pass over the full string would escape
  Solr's own markup.
- The no-descriptor-found fallback (`decode_decs.py:38`, `f"{subcampo}{codigo}"`)
  needs no escaping — it yields only `^d`/`^s` plus digits.
- `app.py` call site passes `escape_xml=output in ['xml', 'solr']`, matching exactly
  the branch that returns `media_type="text/xml"` (`app.py:265`).
- `/healthcheck` (`app.py:303`) passes nothing and stays raw — it parses its result
  as JSON.

### 3. Out of scope

- JSON-escaping descriptors for the JSON output path. A descriptor containing `"`
  or `\` is a separate bug class, not raised here.
- Reimplementing the `export-xml.xsl` transform. See "Payload shape" below.

## Acceptance criteria

1. `output=xml` → posted `query_map` has `wt == "xml"` and no `tr` key.
2. `output=solr` → posted `query_map` has neither `wt` nor `json.nl`.
3. Default output → `wt == "json"`, `json.nl == "arrarr"`.
4. `decode(text, lang)` with no flag returns terms verbatim, `&` included.
5. `decode(text, lang, escape_xml=True)` turns a term `anatomy & histology` into
   `anatomy &amp; histology`.
6. With `escape_xml=True`, surrounding markup in the input string is untouched — an
   existing `&amp;` in the response body is not re-escaped to `&amp;amp;`.
7. An `output=xml` request whose Solr response contains a code resolving to a term
   with `&` produces a body parseable by an XML parser.
8. `/healthcheck` is called without escaping and its response still parses as JSON.
9. Full suite passes (58 tests today, plus the new ones).

## Tests to update

- `controller/tests/test_app_endpoints.py:113-114` —
  `test_search_json_xml_output`: assert `wt == "xml"` and `"tr" not in query_map`.
- `controller/tests/test_decode_decs.py` — new cases for escaping on and off,
  and for markup not being double-escaped.
- `controller/tests/test_app_endpoints.py` — new endpoint test that an `output=xml`
  body containing a `&`-bearing term is well-formed XML.

## Decisions

| Question | Decision |
| --- | --- |
| Where to escape | Inside `decode()`, on the descriptor only |
| Which outputs escape | `output in ['xml', 'solr']` |
| Which characters | `&`, `<`, `>` (`saxutils.escape` defaults) |
| Payload shape | Native Solr XML is the goal; `export-xml.xsl` is not reimplemented |

## Risks

- **Breaking change for consumers.** Clients previously received the
  `export-xml.xsl` export format and will now receive native Solr XML
  (`<response><result><doc>…`). This is intended, but every downstream consumer of
  `output=xml` must be able to read the native shape.

## Files affected

- `controller/app.py` — writer selection (221-226), decode call (256)
- `controller/decode_decs.py` — `escape_xml` argument and descriptor escaping
- `controller/tests/test_app_endpoints.py`
- `controller/tests/test_decode_decs.py`

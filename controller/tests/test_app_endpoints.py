import httpx
import pytest


def _solr_error(status_code):
    """Build the httpx.HTTPStatusError raised by response.raise_for_status()."""
    request = httpx.Request("POST", "http://localhost:8983/solr/portal/select/")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


# --- Authentication and request validation ---

def test_search_form_missing_apikey_header(client):
    response = client.post("/search_form", data={"site": "solr/portal"})
    assert response.status_code == 422


def test_search_json_invalid_apikey(client):
    response = client.post(
        "/search_json",
        json={"site": "solr/portal"},
        headers={"apikey": "wrong_key"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid api key"


def test_search_json_missing_apikey_header(client):
    response = client.post("/search_json", json={"site": "solr/portal"})
    assert response.status_code == 422


def test_search_form_missing_required_site(client, auth_headers):
    response = client.post("/search_form", data={"q": "malaria"}, headers=auth_headers)
    assert response.status_code == 422


def test_search_form_non_integer_count(client, auth_headers):
    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "count": "many"},
        headers=auth_headers,
    )
    assert response.status_code == 422


# --- /search_json ---

def test_search_json_basic_query(client, auth_headers, solr_response):
    solr_response()

    response = client.post(
        "/search_json",
        json={"site": "solr/portal", "q": "malaria"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "diaServerResponse" in response.json()


def test_search_json_index_prefixes_query(client, auth_headers, solr_response, posted_query):
    solr_response()

    response = client.post(
        "/search_json",
        json={"site": "solr/portal", "q": "Malaria", "index": "ti"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    _, query_map = posted_query()
    assert query_map["q"] == "ti:(malaria)"


def test_search_json_formats_fq_entries(client, auth_headers, solr_response, posted_query):
    solr_response()

    response = client.post(
        "/search_json",
        json={"site": "solr/portal", "q": "malaria", "fq": ["Type:(Article)", "Year:(2024)"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    _, query_map = posted_query()
    assert query_map["fq"] == ["type:(article)", "year:(2024)"]


def test_search_json_aliases_reach_query_map(client, auth_headers, solr_response, posted_query):
    solr_response()

    response = client.post(
        "/search_json",
        json={"site": "solr/portal", "q": "malaria", "count": 5, "facet.field": ["type"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    _, query_map = posted_query()
    assert query_map["rows"] == 5
    assert query_map["facet.field"] == ["type"]


def test_search_json_xml_output(client, auth_headers, solr_response, posted_query):
    solr_response(text="<response><result numFound='0'/></response>")

    response = client.post(
        "/search_json",
        json={"site": "solr/portal", "q": "malaria", "output": "xml"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "text/xml" in response.headers["content-type"]
    _, query_map = posted_query()
    assert query_map["wt"] == "xslt"
    assert query_map["tr"] == "export-xml.xsl"


# --- Solr transport errors ---

def test_solr_request_error_returns_400(client, auth_headers, solr_response):
    solr_response(side_effect=httpx.RequestError("connection refused"))

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid POST or connection error with Solr server"


def test_solr_http_status_error_503(client, auth_headers, solr_response):
    fake_response = solr_response()
    fake_response.raise_for_status.side_effect = _solr_error(503)

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria"},
        headers=auth_headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Error response from Solr server"


def test_solr_http_status_error_passes_through_404(client, auth_headers, solr_response):
    fake_response = solr_response()
    fake_response.raise_for_status.side_effect = _solr_error(404)

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria"},
        headers=auth_headers,
    )
    assert response.status_code == 404


# --- Query map construction ---

def test_search_form_without_q_matches_all(client, auth_headers, solr_response, posted_query):
    solr_response()

    response = client.post("/search_form", data={"site": "solr/portal"}, headers=auth_headers)
    assert response.status_code == 200
    _, query_map = posted_query()
    assert query_map["q"] == "*:*"


def test_search_form_forwards_optional_params(client, auth_headers, solr_response, posted_query):
    solr_response()

    response = client.post(
        "/search_form",
        data={
            "site": "solr/portal",
            "q": "malaria",
            "start": 10,
            "sort": "da desc",
            "count": 20,
            "tag": "tab",
            "fl": "id,title",
            "facet": "true",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    _, query_map = posted_query()
    assert query_map["start"] == 10
    assert query_map["sort"] == "da desc"
    assert query_map["rows"] == 20
    assert query_map["tag"] == "tab"
    assert query_map["fl"] == "id,title"
    assert query_map["facet"] == "true"


def test_search_form_omits_unset_params(client, auth_headers, solr_response, posted_query):
    solr_response()

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    _, query_map = posted_query()
    for param in ["start", "sort", "rows", "tag", "fl", "facet"]:
        assert param not in query_map


def test_search_form_fb_sets_facet_limit(client, auth_headers, solr_response, posted_query):
    solr_response()

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria", "fb": "type:10"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    _, query_map = posted_query()
    assert query_map["f.type.facet.limit"] == "10"


def test_search_form_facet_field_terms_tags_exclusion(client, auth_headers, solr_response, posted_query):
    solr_response()

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria", "facet.field.terms": "type:a,b"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    _, query_map = posted_query()
    assert query_map["facet.field"] == ["{!ex=tab terms=a,b}type"]


def test_search_form_solr_output_returns_raw_response(client, auth_headers, solr_response, posted_query):
    raw = '{"response":{"numFound":0,"docs":[]}}'
    solr_response(text=raw)

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria", "output": "solr"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "text/xml" in response.headers["content-type"]
    assert response.text == raw
    _, query_map = posted_query()
    assert "wt" not in query_map
    assert "json.nl" not in query_map


def test_search_form_default_output_requests_json(client, auth_headers, solr_response, posted_query):
    solr_response()

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    _, query_map = posted_query()
    assert query_map["wt"] == "json"
    assert query_map["json.nl"] == "arrarr"


@pytest.mark.parametrize(
    "output,solr_text",
    [(None, '{"response":{}}'), ("xml", "<response/>")],
)
def test_search_form_sets_no_cache_header(client, auth_headers, solr_response, output, solr_text):
    solr_response(text=solr_text)

    data = {"site": "solr/portal", "q": "malaria"}
    if output:
        data["output"] = output

    response = client.post("/search_form", data=data, headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


# --- DeCS decode branch ---

def test_decode_skipped_without_thesaurus_codes(client, auth_headers, solr_response, decs_decode):
    solr_response(text='{"response":{"docs":[{"title":"malaria"}]}}')

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria", "lang": "pt"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    decs_decode.assert_not_called()


def test_decode_failure_strips_subfield_marks(client, auth_headers, solr_response, decs_decode):
    solr_response(text='{"response":{"docs":[{"t":"malaria^d22016^s01234"}]}}')
    decs_decode.side_effect = Exception("Redis connection lost")

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria", "lang": "pt"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    doc = response.json()["diaServerResponse"][0]["response"]["docs"][0]
    assert doc["t"] == "malaria22016/01234"


# --- /healthcheck ---

def test_healthcheck_invalid_apikey(client):
    response = client.get("/healthcheck", headers={"apikey": "wrong_key"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid api key"


def test_healthcheck_missing_apikey_header(client):
    response = client.get("/healthcheck")
    assert response.status_code == 422


def test_healthcheck_query_map(client, auth_headers, solr_response, posted_query, decs_decode):
    solr_response()
    decs_decode.return_value = '{"response":{"numFound":1}}'

    response = client.get("/healthcheck", headers=auth_headers)
    assert response.status_code == 200
    url, query_map = posted_query()
    assert url.endswith("/solr5/portal/select/")
    assert query_map == {
        "q": "malaria",
        "rows": 1,
        "facet": "false",
        "wt": "json",
        "json.nl": "arrarr",
    }


def test_healthcheck_solr_request_error(client, auth_headers, solr_response):
    solr_response(side_effect=httpx.RequestError("connection refused"))

    response = client.get("/healthcheck", headers=auth_headers)
    assert response.status_code == 400


def test_healthcheck_decode_failure(client, auth_headers, solr_response, decs_decode):
    solr_response()
    decs_decode.side_effect = Exception("Redis connection lost")

    response = client.get("/healthcheck", headers=auth_headers)
    assert response.status_code == 500
    assert response.json()["detail"] == "DeCS decode failed"


def test_healthcheck_invalid_json_response(client, auth_headers, solr_response, decs_decode):
    solr_response()
    decs_decode.return_value = "this is not valid json"

    response = client.get("/healthcheck", headers=auth_headers)
    assert response.status_code == 500
    assert response.json()["detail"] == "Error parsing healthcheck response"

import json
import sys
import os
from contextlib import asynccontextmanager
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Add controller directory to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app, format_query, fix_double_quotes, set_solr_server

API_KEY = os.getenv("API_TOKEN", "8983")

# Override the lifespan to use mocks instead of real Redis/httpx connections
@asynccontextmanager
async def _mock_lifespan(app_instance):
    app_instance.state.client = AsyncMock()
    app_instance.state.decs = MagicMock()
    app_instance.state.decs.decode = MagicMock(return_value='{"numFound":1}')
    yield

app.router.lifespan_context = _mock_lifespan


# --- Unit tests for format_query ---

def test_format_query_lowercase_and_operators():
    result = format_query("Malaria OR Dengue AND Fever")
    assert "malaria OR dengue AND fever" == result


def test_format_query_preserves_quoted_strings():
    result = format_query('title:"Exact Match" AND body')
    assert '"Exact Match"' in result
    assert "body" in result


def test_format_query_dollar_to_wildcard():
    result = format_query("test$")
    assert "test*" in result


def test_format_query_and_not_to_not():
    result = format_query("malaria AND NOT dengue")
    assert " NOT " in result
    assert " AND NOT " not in result


def test_format_query_preserves_brackets():
    result = format_query("date:[2020 TO 2024] AND malaria")
    assert "[2020 TO 2024]" in result


# --- Unit tests for fix_double_quotes ---

def test_fix_double_quotes_curly():
    result = fix_double_quotes("\u201ctest\u201d")
    assert result == '"test"'


def test_fix_double_quotes_unmatched():
    result = fix_double_quotes('"test')
    assert result == '"test"'


def test_fix_double_quotes_balanced():
    result = fix_double_quotes('"test"')
    assert result == '"test"'


# --- Unit tests for set_solr_server ---

@patch.dict(os.environ, {"DEFAULT_SOLR_SERVER": "localhost", "DEFAULT_SOLR_PORT": "8983"}, clear=False)
def test_set_solr_server_default():
    result = set_solr_server("solr/portal", None)
    assert result == "http://localhost:8983/solr/portal"


@patch.dict(os.environ, {"DEFAULT_SOLR_SERVER": "localhost", "DEFAULT_SOLR_PORT": "8983"}, clear=False)
def test_set_solr_server_with_col():
    result = set_solr_server("solr/portal", "main")
    assert result == "http://localhost:8983/solr/portal-main"


@patch.dict(os.environ, {"SOLR5_PORTAL": "server1:8986, server2:8986"}, clear=False)
def test_set_solr_server_random_selection():
    result = set_solr_server("solr5/portal", None)
    assert result in [
        "http://server1:8986/solr5/portal",
        "http://server2:8986/solr5/portal",
    ]


# --- Endpoint tests ---

@pytest.fixture
def client():
    """Create a test client with mocked external dependencies."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_search_form_unauthorized(client):
    response = client.post("/search_form", data={"site": "solr/portal"}, headers={"apikey": "wrong_key"})
    assert response.status_code == 401


def test_search_form_basic_query(client):
    mock_response = AsyncMock()
    mock_response.text = '{"responseHeader":{"status":0},"response":{"numFound":1,"docs":[]}}'
    mock_response.raise_for_status = MagicMock()
    app.state.client.post = AsyncMock(return_value=mock_response)

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria"},
        headers={"apikey": API_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "diaServerResponse" in data


def test_search_form_xml_output(client):
    mock_response = AsyncMock()
    mock_response.text = "<response><result numFound='1'/></response>"
    mock_response.raise_for_status = MagicMock()
    app.state.client.post = AsyncMock(return_value=mock_response)

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria", "output": "xml"},
        headers={"apikey": API_KEY},
    )
    assert response.status_code == 200
    assert "text/xml" in response.headers["content-type"]


def test_search_form_with_decs_decode(client):
    solr_text = '{"response":{"docs":[{"title":"^d22016 test"}]}}'
    mock_response = AsyncMock()
    mock_response.text = solr_text
    mock_response.raise_for_status = MagicMock()
    app.state.client.post = AsyncMock(return_value=mock_response)
    app.state.decs.decode = MagicMock(return_value='{"response":{"docs":[{"title":"Malaria test"}]}}')

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria", "lang": "pt"},
        headers={"apikey": API_KEY},
    )
    assert response.status_code == 200
    app.state.decs.decode.assert_called_once()


def test_search_form_decs_decode_error_handled(client):
    solr_text = '{"response":{"docs":[{"title":"^d22016 test"}]}}'
    mock_response = AsyncMock()
    mock_response.text = solr_text
    mock_response.raise_for_status = MagicMock()
    app.state.client.post = AsyncMock(return_value=mock_response)
    app.state.decs.decode = MagicMock(side_effect=Exception("Redis connection lost"))

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria", "lang": "pt"},
        headers={"apikey": API_KEY},
    )
    # Should still return 200 with raw codes stripped, not crash with 500
    assert response.status_code == 200


def test_search_form_json_parse_error(client):
    mock_response = AsyncMock()
    mock_response.text = "this is not valid json"
    mock_response.raise_for_status = MagicMock()
    app.state.client.post = AsyncMock(return_value=mock_response)

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "malaria"},
        headers={"apikey": API_KEY},
    )
    assert response.status_code == 500


def test_healthcheck_success(client):
    mock_response = AsyncMock()
    mock_response.text = '{"responseHeader":{"status":0},"response":{"numFound":1,"docs":[]}}'
    mock_response.raise_for_status = MagicMock()
    app.state.client.post = AsyncMock(return_value=mock_response)
    app.state.decs.decode = MagicMock(
        return_value='{"responseHeader":{"status":0},"response":{"numFound":1,"docs":[]}}'
    )

    response = client.get("/healthcheck", headers={"apikey": API_KEY})
    assert response.status_code == 200


def test_global_exception_handler(client):
    """Force an unhandled exception to verify the global handler returns 500."""
    app.state.client.post = AsyncMock(side_effect=RuntimeError("unexpected failure"))

    response = client.post(
        "/search_form",
        data={"site": "solr/portal", "q": "test"},
        headers={"apikey": API_KEY},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"

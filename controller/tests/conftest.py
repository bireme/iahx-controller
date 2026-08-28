import os
import sys
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Add controller directory to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: E402

API_KEY = os.getenv("API_TOKEN", "8983")

DEFAULT_SOLR_TEXT = '{"responseHeader":{"status":0},"response":{"numFound":0,"docs":[]}}'


# Override the lifespan to use mocks instead of real Redis/httpx connections
@asynccontextmanager
async def _mock_lifespan(app_instance):
    app_instance.state.client = AsyncMock()
    app_instance.state.decs = MagicMock()
    app_instance.state.decs.decode = MagicMock(return_value='{"numFound":1}')
    yield


app.router.lifespan_context = _mock_lifespan


@pytest.fixture
def client():
    """Test client with mocked external dependencies (Solr and DeCS/Redis)."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth_headers():
    """Headers carrying a valid api key."""
    return {"apikey": API_KEY}


@pytest.fixture
def solr_response(client):
    """Factory that wires the fake Solr answer returned by app.state.client.post."""

    def _set(text=DEFAULT_SOLR_TEXT, side_effect=None):
        if side_effect is not None:
            app.state.client.post = AsyncMock(side_effect=side_effect)
            return None

        response = MagicMock()
        response.text = text
        response.raise_for_status = MagicMock()
        app.state.client.post = AsyncMock(return_value=response)
        return response

    return _set


@pytest.fixture
def posted_query(client):
    """Return (url, query_map) of the last POST sent to the Solr server."""

    def _get():
        args, kwargs = app.state.client.post.call_args
        url = args[0] if args else kwargs.get("url")
        return url, kwargs["data"]

    return _get


@pytest.fixture
def decs_decode(client):
    """Access to the mocked DeCS decoder."""
    return app.state.decs.decode

import sys
import os
from unittest.mock import patch, MagicMock

import pytest
import redis

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decode_decs import DecodDeCS


@pytest.fixture
def decs():
    """Create a DecodDeCS instance with a mocked Redis client."""
    with patch("decode_decs.redis.Redis") as mock_redis_cls:
        mock_client = MagicMock()
        mock_redis_cls.return_value = mock_client
        instance = DecodDeCS()
        instance.redis_client = mock_client
        yield instance


def _setup_pipeline(decs, results):
    """Helper to configure mock pipeline with given results."""
    mock_pipeline = MagicMock()
    mock_pipeline.execute.return_value = results
    decs.redis_client.pipeline.return_value = mock_pipeline
    return mock_pipeline


def test_decode_replaces_descriptor_codes(decs):
    _setup_pipeline(decs, [
        {b'en': b'Malaria', b'pt-br': b'Malaria', b'es': b'Malaria'},
    ])

    result = decs.decode("title: ^d22016 and more text", "en")
    assert "Malaria" in result
    assert "^d22016" not in result
    assert "and more text" in result


def test_decode_qualifier_gets_slash_prefix(decs):
    # Mock bulk_fetch_descriptors directly to avoid set ordering issues
    decs.bulk_fetch_descriptors = MagicMock(return_value={
        "22016": "Malaria",
        "1327": "prevention",
    })

    result = decs.decode("^d22016^s1327", "en")
    assert "Malaria" in result
    assert "/prevention" in result


def test_decode_fallback_on_missing_key(decs):
    _setup_pipeline(decs, [{}])

    result = decs.decode("^d99999", "en")
    assert "^d99999" in result


def test_decode_portuguese_language(decs):
    _setup_pipeline(decs, [
        {b'en': b'Malaria', b'pt-br': b'Malaria (PT)', b'es': b'Malaria (ES)'},
    ])

    result = decs.decode("^d22016", "pt")
    assert "Malaria (PT)" in result


def test_decode_spanish_language(decs):
    _setup_pipeline(decs, [
        {b'en': b'Malaria', b'pt-br': b'Malaria (PT)', b'es': b'Malaria (ES)'},
    ])

    result = decs.decode("^d22016", "es")
    assert "Malaria (ES)" in result


def test_decode_no_codes_returns_original(decs):
    result = decs.decode("plain text without codes", "en")
    assert result == "plain text without codes"


def test_bulk_fetch_redis_connection_error(decs):
    mock_pipeline = MagicMock()
    mock_pipeline.execute.side_effect = redis.ConnectionError("Connection refused")
    decs.redis_client.pipeline.return_value = mock_pipeline

    result = decs.bulk_fetch_descriptors({"22016"}, "en")
    assert result == {}


def test_bulk_fetch_redis_timeout_error(decs):
    mock_pipeline = MagicMock()
    mock_pipeline.execute.side_effect = redis.TimeoutError("Timeout")
    decs.redis_client.pipeline.return_value = mock_pipeline

    result = decs.bulk_fetch_descriptors({"22016"}, "en")
    assert result == {}


def test_bulk_fetch_unicode_decode_error(decs):
    _setup_pipeline(decs, [
        {b'en': b'\xff\xfe invalid utf8'},
    ])

    result = decs.bulk_fetch_descriptors({"22016"}, "en")
    assert result == {}


# --- XML entity escaping ---

def test_decode_escapes_xml_entities_when_requested(decs):
    _setup_pipeline(decs, [
        {b'en': b'anatomy & histology'},
    ])

    result = decs.decode('<str name="mh">^d22016</str>', "en", escape_xml=True)
    assert result == '<str name="mh">anatomy &amp; histology</str>'


def test_decode_does_not_escape_by_default(decs):
    _setup_pipeline(decs, [
        {b'en': b'anatomy & histology'},
    ])

    result = decs.decode("term: ^d22016", "en")
    assert result == "term: anatomy & histology"


def test_decode_escaping_leaves_surrounding_markup_untouched(decs):
    """Only the substituted term is escaped, never the response markup around it."""
    _setup_pipeline(decs, [
        {b'en': b'Malaria'},
    ])

    text = '<doc><str name="a">R&amp;D</str><str name="mh">^d22016</str></doc>'
    result = decs.decode(text, "en", escape_xml=True)
    assert "R&amp;D" in result
    assert "&amp;amp;" not in result


def test_decode_escapes_qualifier_term_before_slash_prefix(decs):
    _setup_pipeline(decs, [
        {b'en': b'anatomy & histology'},
    ])

    result = decs.decode("^s22016", "en", escape_xml=True)
    assert result == "/anatomy &amp; histology"


def test_decode_escaping_leaves_missing_descriptor_fallback_intact(decs):
    _setup_pipeline(decs, [{}])

    result = decs.decode("^d22016", "en", escape_xml=True)
    assert result == "^d22016"

import json
import pytest
from unittest.mock import patch, MagicMock
from backend.loader import fetch_text_from_url


def _mock_response(data: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = data
    resp.raise_for_status.side_effect = None if status == 200 else Exception(f"HTTP {status}")
    return resp


def test_fetch_returns_pretty_json():
    data = {"status": "DELIVERED", "label": "Delivered"}
    with patch("backend.loader.requests.get", return_value=_mock_response(data)):
        result = fetch_text_from_url("https://example.com/api.json")
    assert '"status": "DELIVERED"' in result
    assert '"label": "Delivered"' in result


def test_fetch_truncates_to_100k():
    data = {"key": "x" * 200_000}
    with patch("backend.loader.requests.get", return_value=_mock_response(data)):
        result = fetch_text_from_url("https://example.com/api.json")
    assert len(result) <= 100_000


def test_fetch_raises_on_http_error():
    import requests as req
    resp = MagicMock()
    resp.raise_for_status.side_effect = req.HTTPError("404")
    with patch("backend.loader.requests.get", return_value=resp):
        with pytest.raises(req.HTTPError):
            fetch_text_from_url("https://example.com/bad.json")


def test_fetch_raises_on_invalid_json():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.side_effect = ValueError("No JSON")
    with patch("backend.loader.requests.get", return_value=resp):
        with pytest.raises(ValueError):
            fetch_text_from_url("https://example.com/notjson")

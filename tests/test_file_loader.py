# tests/test_file_loader.py
import json
from unittest.mock import MagicMock
from backend.loader import extract_text_from_file


def _make_file(name: str, content: bytes) -> MagicMock:
    """Simulate a Streamlit UploadedFile."""
    f = MagicMock()
    f.name = name
    f.getvalue.return_value = content
    return f


def test_json_file_pretty_printed():
    data = {"code": "DELIVERED", "label": "Zugestellt"}
    raw = json.dumps(data).encode("utf-8")
    result = extract_text_from_file(_make_file("codes.json", raw))
    assert '"code": "DELIVERED"' in result
    assert '"label": "Zugestellt"' in result


def test_json_file_invalid_returns_error():
    result = extract_text_from_file(_make_file("bad.json", b"not json"))
    assert result.startswith("Error reading file:")


def test_json_file_truncated_to_100k():
    data = {"key": "x" * 200_000}
    raw = json.dumps(data).encode("utf-8")
    result = extract_text_from_file(_make_file("big.json", raw))
    assert len(result) <= 100_000


def test_xml_file_pretty_printed():
    xml_bytes = b'<?xml version="1.0"?><codes><code id="DEL">Delivered</code></codes>'
    result = extract_text_from_file(_make_file("codes.xml", xml_bytes))
    assert "<code" in result
    assert "DEL" in result
    assert "Delivered" in result


def test_xml_file_invalid_returns_error():
    result = extract_text_from_file(_make_file("bad.xml", b"<unclosed>"))
    assert result.startswith("Error reading file:")


def test_xml_file_truncated_to_100k():
    # Build a large but valid XML document
    items = "".join(f"<item>{i * 'x'}</item>" for i in range(1, 500))
    xml_bytes = f"<root>{items}</root>".encode("utf-8")
    result = extract_text_from_file(_make_file("big.xml", xml_bytes))
    assert len(result) <= 100_000

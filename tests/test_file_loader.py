# tests/test_file_loader.py
import json
from unittest.mock import MagicMock
from backend.loader import extract_text_from_file, extract_text_from_files


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
    assert len(result) == 100_000


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
    assert len(result) == 100_000


# --- multi-file upload -------------------------------------------------

def test_multiple_files_concatenated_with_markers():
    f1 = _make_file("a.json", json.dumps({"code": "DELIVERED"}).encode("utf-8"))
    f2 = _make_file("b.json", json.dumps({"code": "PICKED_UP"}).encode("utf-8"))
    result = extract_text_from_files([f1, f2])
    # Both files' content is present, neither overwrites the other
    assert "DELIVERED" in result
    assert "PICKED_UP" in result
    # Each file is delimited by a marker carrying its name
    assert "--- FILE: a.json ---" in result
    assert "--- FILE: b.json ---" in result


def test_single_file_in_list_has_no_marker():
    # One file behaves exactly like the single-file path (no marker added)
    f = _make_file("codes.json", json.dumps({"code": "DELIVERED"}).encode("utf-8"))
    assert extract_text_from_files([f]) == extract_text_from_file(f)


def test_multiple_files_truncated_to_100k_total():
    f1 = _make_file("big1.json", json.dumps({"k": "x" * 200_000}).encode("utf-8"))
    f2 = _make_file("big2.json", json.dumps({"k": "y" * 200_000}).encode("utf-8"))
    result = extract_text_from_files([f1, f2])
    assert len(result) == 100_000


def test_no_files_returns_empty():
    assert extract_text_from_files([]) == ""

# JSON/XML File Upload Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to upload `.json` and `.xml` files in addition to the existing PDF, XLSX, CSV, and TXT formats.

**Architecture:** Add two new branches to `extract_text_from_file()` in `backend/loader.py` using stdlib-only modules (`json`, `xml.dom.minidom`). Update the Streamlit file uploader type list in `app.py`. No other files change.

**Tech Stack:** Python stdlib (`json`, `xml.dom.minidom`), pytest, Streamlit `st.file_uploader`

---

## File Map

| Action | File | What changes |
|--------|------|-------------|
| Modify | `backend/loader.py` | Add `.json` and `.xml` branches to `extract_text_from_file()` |
| Modify | `app.py` | Add `"json"`, `"xml"` to `type` list on line 250 |
| Create | `tests/test_file_loader.py` | Unit tests for the new format handlers |

---

## Task 1: Write failing tests for JSON file loading

**Files:**
- Create: `tests/test_file_loader.py`

- [ ] **Step 1: Create test file with a helper and the JSON tests**

```python
# tests/test_file_loader.py
import json
import io
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_file_loader.py -v
```

Expected: 3 tests FAIL (no `.json` branch in `extract_text_from_file` yet — returns empty string, not the expected output)

---

## Task 2: Implement JSON loading in `backend/loader.py`

**Files:**
- Modify: `backend/loader.py`

- [ ] **Step 3: Add the `.json` branch**

In `backend/loader.py`, inside `extract_text_from_file()`, add after the `.csv`/`.txt` branch (before the closing `except`):

```python
        elif filename.endswith('.json'):
            raw = uploaded_file.getvalue().decode("utf-8")
            data = json.loads(raw)
            text = json.dumps(data, indent=2, ensure_ascii=False)
```

`json` is already imported at the top of the file.

- [ ] **Step 4: Run JSON tests to verify they pass**

```bash
pytest tests/test_file_loader.py::test_json_file_pretty_printed tests/test_file_loader.py::test_json_file_invalid_returns_error tests/test_file_loader.py::test_json_file_truncated_to_100k -v
```

Expected: 3 PASS

---

## Task 3: Write failing tests for XML file loading

**Files:**
- Modify: `tests/test_file_loader.py`

- [ ] **Step 5: Add XML tests to the test file**

```python
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
```

- [ ] **Step 6: Run XML tests to verify they fail**

```bash
pytest tests/test_file_loader.py::test_xml_file_pretty_printed tests/test_file_loader.py::test_xml_file_invalid_returns_error tests/test_file_loader.py::test_xml_file_truncated_to_100k -v
```

Expected: 3 tests FAIL

---

## Task 4: Implement XML loading in `backend/loader.py`

**Files:**
- Modify: `backend/loader.py`

- [ ] **Step 7: Add the import at the top of the file**

At the top of `backend/loader.py`, add:

```python
import xml.dom.minidom
```

- [ ] **Step 8: Add the `.xml` branch**

After the `.json` branch, add:

```python
        elif filename.endswith('.xml'):
            raw = uploaded_file.getvalue()
            dom = xml.dom.minidom.parseString(raw)
            text = dom.toprettyxml(indent="  ")
```

- [ ] **Step 9: Run all tests in test_file_loader.py**

```bash
pytest tests/test_file_loader.py -v
```

Expected: 6 PASS

---

## Task 5: Update the Streamlit file uploader

**Files:**
- Modify: `app.py`

- [ ] **Step 10: Extend the type list**

In `app.py` line 250, change:

```python
uploaded_file = st.file_uploader("Upload file", type=["pdf", "xlsx", "csv", "txt"], key=f"file_uploader_{st.session_state.upload_key}")
```

to:

```python
uploaded_file = st.file_uploader("Upload file", type=["pdf", "xlsx", "csv", "txt", "json", "xml"], key=f"file_uploader_{st.session_state.upload_key}")
```

- [ ] **Step 11: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all existing tests PASS, 6 new tests PASS (22 + 6 = 28 total)

- [ ] **Step 12: Commit**

```bash
git add backend/loader.py app.py tests/test_file_loader.py
git commit -m "feat: add JSON and XML file upload support"
```

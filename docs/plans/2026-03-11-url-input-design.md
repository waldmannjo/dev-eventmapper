# Design: URL Input for Step 0

**Date:** 2026-03-11
**Status:** Approved

## Problem

Step 0 only supports file upload (PDF, XLSX, CSV, TXT). Users need to also provide a URL pointing to a JSON API endpoint (e.g. carrier translation APIs) as an alternative input source.

## Requirements

- Alternative to file upload: URL input in Step 0
- Supported content type: JSON only (public URLs, no auth required)
- UI: Two tabs — "Upload File" and "Enter URL"
- Fetch: immediate on button click ("Load URL"), not lazy
- SSL: disabled globally (consistent with rest of app)
- Limit: same 100k character truncation as file uploads

## Design

### UI (app.py — Step 0 block)

Replace the current `st.file_uploader` block with two tabs:

```
tab1, tab2 = st.tabs(["📄 Upload File", "🔗 Enter URL"])
```

**Tab 1 "Upload File":** unchanged — `st.file_uploader` + `logic.extract_text_from_file()`

**Tab 2 "Enter URL":**
- `st.text_input("URL", placeholder="https://...")`
- `st.button("Load URL")`
- On click: call `logic.fetch_text_from_url(url)`, store result in `st.session_state.raw_text`, set `current_step = 0`
- Errors shown via `st.error()`: network errors, non-200 HTTP, invalid JSON

### Backend (backend/loader.py)

New function:

```python
def fetch_text_from_url(url: str) -> str:
    """Fetches JSON from a public URL and returns pretty-printed text (max 100k chars)."""
    import requests, json
    resp = requests.get(url, verify=False, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return json.dumps(data, indent=2, ensure_ascii=False)[:100000]
```

Raises:
- `requests.RequestException` on network/HTTP errors
- `requests.exceptions.JSONDecodeError` (via `resp.json()`) on non-JSON responses

### backend/__init__.py

Add `fetch_text_from_url` to exports.

## Affected Files

| File | Change |
|------|--------|
| `backend/loader.py` | +1 function (~15 lines) |
| `backend/__init__.py` | +1 export |
| `app.py` | Step 0 block wrapped in tabs (~20 lines delta) |

## Out of Scope

- Auth headers (Bearer, Basic)
- HTML scraping
- CSV/PDF URLs
- URL validation beyond requests errors

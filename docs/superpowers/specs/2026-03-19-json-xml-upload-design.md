# Design: JSON and XML File Upload Support

**Date:** 2026-03-19
**Status:** Approved

## Overview

Extend the Eventmapper file upload to accept `.json` and `.xml` files in addition to the existing PDF, XLSX, CSV, and TXT formats. The extracted text is passed unchanged into the existing LLM analysis pipeline.

## Changes

### `backend/loader.py` — `extract_text_from_file()`

Add two new branches after the existing handlers:

- **`.json`**: Parse with `json.loads()`, re-serialize with `json.dumps(indent=2, ensure_ascii=False)`. Produces pretty-printed JSON text. Same logic as the existing URL fetcher.
- **`.xml`**: Parse with `xml.dom.minidom.parseString()`, serialize with `toprettyxml(indent="  ")`. Produces indented XML text. Both modules are Python stdlib — no new dependencies.

Both branches are wrapped in the existing `try/except` that returns `"Error reading file: {e}"` on failure.

### `app.py` — file uploader type list (line 250)

Extend `type=["pdf", "xlsx", "csv", "txt"]` to include `"json"` and `"xml"`.

## Out of Scope

- No changes to the LLM prompts, analysis, extraction, or mapping pipeline.
- No changes to the debug uploader in the sidebar (CSV/XLSX only — no reason to change).
- No new dependencies.

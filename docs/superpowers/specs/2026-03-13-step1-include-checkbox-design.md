# Design: Step 1 Include-Checkbox

**Date:** 2026-03-13
**Status:** Approved

## Problem

In Step 1 (Source Selection), all entries in both the Status and Reason candidate tables are currently passed to Step 2. There is no way for the user to exclude individual entries from the extraction.

## Goal

Allow the user to select which proposed entries are passed to Step 2 via a per-row "Include" checkbox (default: checked). Only entries with `_include = True` are forwarded.

## Design

### Data Model

`_candidates_to_df()` gains a second boolean column `_include` (default `True`) alongside the existing `_select` (Move):

```
| _select | _include | name    | description | context |
|---------|----------|---------|-------------|---------|
| False   | True     | Table_A | ...         | ...     |
```

### UI Changes (app.py only)

`st.data_editor` for both Status and Reason tables gets a new column config entry:

```python
"_include": st.column_config.CheckboxColumn("Include", default=True)
```

The "Move" column (`_select`) remains unchanged.

### Filtering at Step 2 Handoff

Lines 401–402 are updated to filter by `_include`:

```python
selected_stats = edited_stat[edited_stat["_include"]]["name"].tolist()
selected_reas  = edited_reas[edited_reas["_include"]]["name"].tolist()
```

Existing validation (at least one status source required) continues to work correctly.

### Move Logic

During Move operations, `_include` is preserved alongside `_select` — no changes needed as `drop(columns=["_select"])` only drops the Move column, and `_include` survives the concat.

Wait — actually `_include` must NOT be dropped during move. The move logic does `drop(columns=["_select"])` then re-inserts `_select`. The `_include` column should survive naturally since it is not dropped.

## Scope

**Only `app.py`** — no backend changes required.

### Files to Change

| File | Change |
|------|--------|
| `app.py` | `_candidates_to_df()`: add `_include` column |
| `app.py` | Both `st.data_editor` calls: add `_include` column config |
| `app.py` | `selected_stats` / `selected_reas` assignment: filter by `_include` |
| `app.py` | Guard block (line 324–330): add `_include` to fallback DataFrame init |

## Non-Goals

- No backend changes
- No changes to Step 2 or later steps
- No changes to the Move functionality

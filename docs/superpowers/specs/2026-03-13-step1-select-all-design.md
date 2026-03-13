# Design: Step 1 Select All / Deselect All for Include Checkboxes

**Date:** 2026-03-13
**Status:** Approved

## Problem

In Step 1, users can check/uncheck individual "Include" checkboxes to control which entries are passed to Step 2. There is no way to select or deselect all entries at once, which is tedious for large lists.

## Goal

Add "☑ Alle" and "☐ Keine" buttons below each candidate table (Status and Reason) to set all `_include` values at once.

## Design

### UI

Two small buttons appear below each `st.data_editor` table, after the existing Move button:

**col1 (Status):**
```
[Move to Reason →]
[☑ Alle]  [☐ Keine]
```

**col2 (Reason):**
```
[← Move to Status]
[☑ Alle]  [☐ Keine]
```

### Behaviour

- **☑ Alle** → sets `_include = True` for all rows in the respective `st.session_state` DataFrame, then calls `st.rerun()`
- **☐ Keine** → sets `_include = False` for all rows in the respective `st.session_state` DataFrame, then calls `st.rerun()`
- No minimum-selection guard on these buttons — the existing validator at "Continue to Step 2" already prevents proceeding with zero selected status sources

### Implementation Pattern

Follows the existing Move-button pattern exactly:

```python
col_all, col_none = st.columns([1, 1])
with col_all:
    if st.button("☑ Alle", key="stat_select_all"):
        st.session_state.stat_candidates_df["_include"] = True
        st.rerun()
with col_none:
    if st.button("☐ Keine", key="stat_select_none"):
        st.session_state.stat_candidates_df["_include"] = False
        st.rerun()
```

Same pattern for `reas_candidates_df` with keys `reas_select_all` / `reas_select_none`.

The buttons only appear when their respective table is non-empty (inside the `if not df.empty:` block).

## Scope

**Only `app.py`.** No backend changes. No new tests (pure Streamlit button interaction, not unit-testable).

| Location | Change |
|----------|--------|
| `col1` non-empty block | Add 2 buttons after Move button |
| `col2` non-empty block | Add 2 buttons after Move button |

## Non-Goals

- No "Toggle All" (invert) button
- No select-all across both tables simultaneously
- No changes to Move logic, filtering, or backend

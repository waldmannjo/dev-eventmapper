# Design: Move Candidates Between Source Columns in Step 1

**Date:** 2026-03-10
**Status:** Approved

## Problem

In Step 1 (Source Selection), the LLM may misclassify a document table — placing a reason code table in `status_candidates` or vice versa. Users need a way to correct this manually.

## Solution

Add move functionality to Step 1 using the same `st.data_editor` + checkbox + move-button pattern already used in Step 2.

## Data Model

Two new session state DataFrames replace the existing lists:

| Variable | Columns |
|---|---|
| `st.session_state.stat_candidates_df` | `_select` (bool), `name`, `description`, `context` |
| `st.session_state.reas_candidates_df` | `_select` (bool), `name`, `description`, `context` |

**Initialization:** In the "Continue to Step 1" button handler, immediately after `st.session_state.analysis_res = res`. This ensures reset on new analysis, preservation on Step 2 → Step 1 back-navigation.

**Helper:**
```python
def _candidates_to_df(candidates):
    rows = [{"_select": False, "name": c["name"], "description": c.get("description", ""), "context": c.get("context", "")} for c in candidates]
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["_select", "name", "description", "context"])
```

## UI Changes

Replace `st.multiselect` + `st.expander` blocks with `st.data_editor` tables:

- **col1:** `st.data_editor(ss.stat_candidates_df)` with `_select` as `CheckboxColumn("Move")` → `"Move to Reason →"` button below
- **col2:** `st.data_editor(ss.reas_candidates_df)` → `"← Move to Status"` button below

Move logic (identical to Step 2):
1. Read edited df from `st.data_editor` return value
2. Filter `edited_df[edited_df["_select"]]` → rows to move
3. Remove from source df, reset `_select=False`, append to target df
4. `st.rerun()`

## Downstream Impact

`selected_stats` and `selected_reas` (passed to `logic.extract_data_step2`) are now derived from the df names:
```python
selected_stats = st.session_state.stat_candidates_df["name"].tolist()
selected_reas = st.session_state.reas_candidates_df["name"].tolist()
```

Existing validation (`"Please select at least one source for status codes."`) remains unchanged.

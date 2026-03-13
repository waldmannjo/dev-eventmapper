# Design: Step 1 Include-Checkbox

**Date:** 2026-03-13
**Status:** Approved

## Problem

In Step 1 (Source Selection), all entries in both the Status and Reason candidate tables are currently passed to Step 2. There is no way for the user to exclude individual entries from the extraction.

## Goal

Allow the user to select which proposed entries are passed to Step 2 via a per-row "Include" checkbox (default: checked). Only entries with `_include = True` are forwarded.

## Design

### Data Model

`_candidates_to_df()` — two changes:
1. Add `"_include": True` to every row dict in the list comprehension.
2. Add `"_include"` to the empty-fallback columns list:
   `pd.DataFrame(columns=["_select", "_include", "name", "description", "context"])`

Column order: `_select, _include, name, description, context`

### UI Changes (app.py only)

Both `st.data_editor` calls get a new entry in `column_config`:

```python
"_include": st.column_config.CheckboxColumn("Include", default=True)
```

The "Move" column (`_select`) is unchanged.

### Filtering at Step 2 Handoff

To guarantee `edited_stat` and `edited_reas` are always defined (the data editors are inside `if not df.empty:` blocks), initialize defaults from session state before `col1, col2 = st.columns(2)`:

```python
edited_stat = st.session_state.stat_candidates_df   # fallback if table is empty
edited_reas = st.session_state.reas_candidates_df   # fallback if table is empty
```

Inside each `if not df.empty:` block, the variable is immediately reassigned to the `st.data_editor(...)` return value, which is the authoritative live source for non-empty tables. The default assignment is only used when the table is empty (in which case ignoring UI edits is correct behaviour since nothing was rendered).

Replace the current `selected_stats`/`selected_reas` lines with:

```python
selected_stats = edited_stat[edited_stat["_include"]]["name"].tolist()
selected_reas  = edited_reas[edited_reas["_include"]]["name"].tolist()
```

Filtering an empty DataFrame by `_include` returns `[]` naturally. Existing validation (`if not selected_stats: st.error("Please select at least one source for status codes.")`) continues to work — it now also fires if the user unchecks all `_include` checkboxes in the status table, which is correct behaviour.

### Move Logic

The move code does `drop(columns=["_select"])` then `insert(0, "_select", False)`. `_include` is not dropped, so it survives with the user's current checkbox values intact — this is intentional: moving a row preserves its Include state.

Column order after move: `_select, _include, name, description, context` — consistent with `_candidates_to_df`.

No changes to move logic are required.

### Guard Block (around line 324)

The guard block calls `_candidates_to_df()`, which is already being updated. No code changes needed in the guard block.

## Scope

**Only `app.py`.** Line numbers below are indicative and will shift slightly during implementation.

| Location | Change |
|----------|--------|
| `_candidates_to_df()` | Add `"_include": True` to row dicts; add `"_include"` to empty-fallback columns |
| Both `st.data_editor` calls | Add `"_include"` to `column_config` |
| Before `col1, col2 = st.columns(2)` | Add two default assignments for `edited_stat` / `edited_reas` |
| `selected_stats` / `selected_reas` assignment | Filter by `_include` from `edited_stat` / `edited_reas` |

## Non-Goals

- No backend changes
- No changes to Step 2 or later steps
- No changes to the Move functionality

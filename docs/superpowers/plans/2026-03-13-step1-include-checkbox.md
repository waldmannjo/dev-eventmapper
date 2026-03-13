# Step 1 Include-Checkbox Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-row `_include` checkbox to Step 1 candidate tables so only user-selected entries are passed to Step 2.

**Architecture:** Single-file change in `app.py`. Add `_include` column (default `True`) to the candidate DataFrame helper, expose it in both `st.data_editor` calls, and filter by it before passing names to `logic.extract_data_step2`. The existing move logic already persists DataFrames to session state before `st.rerun()`, so `_include` values survive moves automatically.

**Tech Stack:** Python, Streamlit, pandas

---

## Chunk 1: Data model + filtering

### Task 1: Update `_candidates_to_df` and existing tests

**Files:**
- Modify: `app.py` (function `_candidates_to_df`, lines 74–89)
- Modify: `tests/test_step1_candidate_move.py` (lines 13, 21)
- Create: `tests/test_app_helpers.py`

- [ ] **Step 1: Update column assertions in `tests/test_step1_candidate_move.py`**

Line 13 — replace:
```python
    assert list(df.columns) == ["_select", "name", "description", "context"]
```
with:
```python
    assert list(df.columns) == ["_select", "_include", "name", "description", "context"]
```

Line 21 — replace:
```python
    assert list(df.columns) == ["_select", "name", "description", "context"]
```
with:
```python
    assert list(df.columns) == ["_select", "_include", "name", "description", "context"]
```

- [ ] **Step 2: Write new tests in `tests/test_app_helpers.py`**

```python
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import _candidates_to_df


def test_candidates_to_df_has_include_column():
    df = _candidates_to_df([{"name": "A", "description": "d", "context": "c"}])
    assert "_include" in df.columns


def test_candidates_to_df_include_defaults_true():
    df = _candidates_to_df([{"name": "A"}, {"name": "B"}])
    assert df["_include"].all()


def test_candidates_to_df_empty_has_include_column():
    df = _candidates_to_df([])
    assert "_include" in df.columns


def test_candidates_to_df_column_order():
    df = _candidates_to_df([{"name": "A"}])
    assert list(df.columns[:2]) == ["_select", "_include"]


def test_include_filtering():
    df = _candidates_to_df([{"name": "A"}, {"name": "B"}, {"name": "C"}])
    df.loc[df["name"] == "B", "_include"] = False
    selected = df[df["_include"]]["name"].tolist()
    assert selected == ["A", "C"]


def test_include_filtering_all_unchecked():
    df = _candidates_to_df([{"name": "A"}, {"name": "B"}])
    df["_include"] = False
    selected = df[df["_include"]]["name"].tolist()
    assert selected == []


def test_include_filtering_empty_df():
    # Empty DataFrame with _include column — filter returns [] natively, no KeyError
    df = _candidates_to_df([])
    selected = df[df["_include"]]["name"].tolist()
    assert selected == []


def test_include_survives_move():
    """_include state is preserved when rows are moved between tables (mimics move button logic)."""
    stat_df = _candidates_to_df([{"name": "A"}, {"name": "B"}])
    reas_df = _candidates_to_df([{"name": "C"}])

    # User unchecks Include on B, then moves B to Reason
    stat_df.loc[stat_df["name"] == "B", "_include"] = False
    stat_df.loc[stat_df["name"] == "B", "_select"] = True

    sel = stat_df["_select"].astype(bool)
    to_move = stat_df[sel].drop(columns=["_select"])
    remaining = stat_df[~sel].drop(columns=["_select"])
    remaining.insert(0, "_select", False)
    to_move_with_sel = to_move.copy()
    to_move_with_sel.insert(0, "_select", False)
    reas_df_updated = pd.concat([reas_df, to_move_with_sel], ignore_index=True)

    # B is now in reas with _include=False preserved
    b_row = reas_df_updated[reas_df_updated["name"] == "B"]
    assert not b_row.empty
    assert b_row.iloc[0]["_include"] == False

    # A remains in stat with _include=True
    assert remaining.iloc[0]["_include"] == True
```

- [ ] **Step 3: Run tests — new ones fail, updated existing ones should pass**

```bash
source venv/bin/activate && pytest tests/ -v 2>&1 | tail -30
```

Expected: `test_app_helpers` tests FAIL (feature not yet implemented), `test_step1_candidate_move` tests PASS (assertions updated)

- [ ] **Step 4: Implement `_candidates_to_df` in `app.py`**

Replace the full function body (lines 74–89). Note: `"_include"` is the second key in the dict, which produces column order `["_select", "_include", "name", "description", "context"]` — matching the test assertions above:

```python
def _candidates_to_df(candidates):
    """Convert list of candidate dicts to a DataFrame for st.data_editor."""
    rows = [
        {
            "_select": False,
            "_include": True,
            "name": c["name"],
            "description": c.get("description", ""),
            "context": c.get("context", ""),
        }
        for c in candidates
    ]
    return (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(columns=["_select", "_include", "name", "description", "context"])
    )
```

- [ ] **Step 5: Run all tests**

```bash
source venv/bin/activate && pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_helpers.py tests/test_step1_candidate_move.py
git commit -m "feat: add _include column to _candidates_to_df"
```

---

### Task 2: Wire up `_include` in the Step 1 UI and filtering

**Files:**
- Modify: `app.py` — Step 1 section (around lines 332–402)

- [ ] **Step 1: Add default assignments after the guard block, before `col1, col2 = st.columns(2)`**

In the `if st.session_state.current_step >= 1 and st.session_state.analysis_res:` block, there is a guard block (around lines 324–330) that initialises `stat_candidates_df`/`reas_candidates_df` if missing. The fallback assignments **must be placed after this guard block** (otherwise session state may not yet exist):

Find the end of the guard block, which looks like:
```python
        st.session_state.reas_candidates_df = _candidates_to_df(res.get("reason_candidates", []))

    col1, col2 = st.columns(2)
```

Insert the two default assignments between the guard block and `col1, col2`:
```python
        st.session_state.reas_candidates_df = _candidates_to_df(res.get("reason_candidates", []))

    edited_stat = st.session_state.stat_candidates_df
    edited_reas = st.session_state.reas_candidates_df

    col1, col2 = st.columns(2)
```

This guarantees `edited_stat`/`edited_reas` are always defined. When a table is non-empty, the variable is immediately overwritten by the `st.data_editor` return value inside the `if not df.empty:` block. When empty, the session-state fallback (an empty DataFrame with `_include` column) is used and produces `[]` naturally in the filter.

- [ ] **Step 2: Add `_include` column config to the `col1` data editor**

Find inside `with col1:` > `if not st.session_state.stat_candidates_df.empty:`:
```python
                column_config={
                    "_select": st.column_config.CheckboxColumn("Move", default=False)
                },
```

Replace with:
```python
                column_config={
                    "_select": st.column_config.CheckboxColumn("Move", default=False),
                    "_include": st.column_config.CheckboxColumn("Include", default=True),
                },
```

Confirm the data editor is assigned: `edited_stat = st.data_editor(...)`.

- [ ] **Step 3: Same change for the `col2` data editor**

Find inside `with col2:` > `if not st.session_state.reas_candidates_df.empty:`:
```python
                column_config={
                    "_select": st.column_config.CheckboxColumn("Move", default=False)
                },
```

Replace with:
```python
                column_config={
                    "_select": st.column_config.CheckboxColumn("Move", default=False),
                    "_include": st.column_config.CheckboxColumn("Include", default=True),
                },
```

Confirm the data editor is assigned: `edited_reas = st.data_editor(...)`.

- [ ] **Step 4: Replace `selected_stats` / `selected_reas` lines**

Find (around lines 401–402):
```python
    selected_stats = st.session_state.stat_candidates_df["name"].tolist()
    selected_reas = st.session_state.reas_candidates_df["name"].tolist()
```

Replace with:
```python
    selected_stats = edited_stat[edited_stat["_include"]]["name"].tolist()
    selected_reas = edited_reas[edited_reas["_include"]]["name"].tolist()
```

- [ ] **Step 5: Run all tests**

```bash
source venv/bin/activate && pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass

- [ ] **Step 6: Manual smoke test**

```bash
source venv/bin/activate && streamlit run app.py
```

1. Upload a file → run Step 1 analysis.
2. Both tables show "Move" and "Include" columns (Include checked by default).
3. Uncheck "Include" on one Status row → "Continue to Step 2" → that row is excluded.
4. Uncheck all Status rows → "Continue" → error: "Please select at least one source for status codes."
5. Uncheck "Include" on a row, then move it to Reason via "Move" → "Include" remains unchecked.

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "feat: wire Include checkbox into Step 1 data editors and filtering"
```

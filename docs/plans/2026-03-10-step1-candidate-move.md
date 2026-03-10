# Step 1 Candidate Move Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to move source candidates between "Status Code Sources" and "Reason Code Sources" in Step 1 using the same checkbox + move-button pattern already used in Step 2.

**Architecture:** Store candidates as session state DataFrames initialized on analysis completion. Replace the existing multiselect + expander UI with `st.data_editor` (checkbox column + move buttons). Derive `selected_stats`/`selected_reas` from the df names instead of multiselect widget state.

**Tech Stack:** Streamlit `st.data_editor`, `st.column_config.CheckboxColumn`, pandas DataFrames

---

### Task 1: Add helper function and tests

**Files:**
- Modify: `app.py` (add `_candidates_to_df` near other helpers, around line 60–100)
- Create: `tests/test_step1_candidate_move.py`

**Step 1: Write the failing tests**

Create `tests/test_step1_candidate_move.py`:

```python
"""Tests for Step 1 candidate-move helper logic (DataFrame manipulation)."""
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _candidates_to_df(candidates):
    """Copy of the helper from app.py for testing."""
    rows = [
        {
            "_select": False,
            "name": c["name"],
            "description": c.get("description", ""),
            "context": c.get("context", ""),
        }
        for c in candidates
    ]
    return (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(columns=["_select", "name", "description", "context"])
    )


def test_candidates_to_df_columns():
    candidates = [{"name": "Table 1", "description": "Status codes", "context": "Page 2"}]
    df = _candidates_to_df(candidates)
    assert list(df.columns) == ["_select", "name", "description", "context"]
    assert df.iloc[0]["name"] == "Table 1"
    assert df.iloc[0]["_select"] is False


def test_candidates_to_df_empty():
    df = _candidates_to_df([])
    assert df.empty
    assert list(df.columns) == ["_select", "name", "description", "context"]


def test_candidates_to_df_missing_optional_fields():
    candidates = [{"name": "Table X"}]
    df = _candidates_to_df(candidates)
    assert df.iloc[0]["description"] == ""
    assert df.iloc[0]["context"] == ""


def test_move_selected_candidate_to_other_df():
    stat_df = _candidates_to_df([
        {"name": "Table 1", "description": "Status"},
        {"name": "Table 2", "description": "Status 2"},
    ])
    reas_df = _candidates_to_df([{"name": "Table 3", "description": "Reason"}])

    # Simulate user selecting Table 1 for move
    stat_df.loc[0, "_select"] = True

    to_move = stat_df[stat_df["_select"]].drop(columns=["_select"])
    remaining = stat_df[~stat_df["_select"]].drop(columns=["_select"])

    assert len(remaining) == 1
    assert remaining.iloc[0]["name"] == "Table 2"

    to_move_with_sel = to_move.copy()
    to_move_with_sel.insert(0, "_select", False)
    remaining.insert(0, "_select", False)
    reas_df_updated = pd.concat([reas_df, to_move_with_sel], ignore_index=True)

    assert len(reas_df_updated) == 2
    assert reas_df_updated.iloc[1]["name"] == "Table 1"


def test_no_selection_move_is_noop():
    stat_df = _candidates_to_df([{"name": "Table 1"}])
    to_move = stat_df[stat_df["_select"]]
    assert to_move.empty  # UI should warn and abort


def test_moving_all_status_rows_detected():
    stat_df = _candidates_to_df([{"name": "Table 1"}])
    stat_df.loc[0, "_select"] = True
    remaining = stat_df[~stat_df["_select"]]
    assert remaining.empty  # UI should block: at least one status source required
```

**Step 2: Run tests to verify they fail**

```bash
source venv/bin/activate
pytest tests/test_step1_candidate_move.py -v
```

Expected: `ImportError` or `NameError` — `_candidates_to_df` not yet in `app.py`.

**Step 3: Add `_candidates_to_df` helper to `app.py`**

Find the section with other helper functions (around `_make_usage`, before the Streamlit UI code). Add after the last helper:

```python
def _candidates_to_df(candidates):
    """Convert list of candidate dicts to a DataFrame for st.data_editor."""
    rows = [
        {
            "_select": False,
            "name": c["name"],
            "description": c.get("description", ""),
            "context": c.get("context", ""),
        }
        for c in candidates
    ]
    return (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(columns=["_select", "name", "description", "context"])
    )
```

**Step 4: Update tests to import from `app.py`**

Replace the inline copy of `_candidates_to_df` in the test file with a real import. Edit `tests/test_step1_candidate_move.py`, change the helper at the top to:

```python
from app import _candidates_to_df
```

Remove the inline `def _candidates_to_df(...)` from the test file.

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_step1_candidate_move.py -v
```

Expected: all 6 tests PASS.

**Step 6: Commit**

```bash
git add tests/test_step1_candidate_move.py app.py
git commit -m "feat: add _candidates_to_df helper and tests for Step 1 move logic"
```

---

### Task 2: Initialize session state DataFrames on analysis completion

**Files:**
- Modify: `app.py:240-247` (the "Continue to Step 1" button handler)

**Step 1: Locate the initialization point**

In `app.py`, find this block (around line 240–247):

```python
if st.button("Continue to Step 1: Start Structural Analysis"):
    with st.spinner("Analyzing structure..."):
        try:
            res, raw_usage = logic.analyze_structure_step1(...)
            st.session_state.analysis_res = res
            st.session_state.costs["step1_analysis"] = _make_usage(**raw_usage)
            st.session_state.current_step = 1
            st.rerun()
```

**Step 2: Add DataFrame initialization**

Insert two lines immediately after `st.session_state.analysis_res = res`:

```python
st.session_state.stat_candidates_df = _candidates_to_df(res.get("status_candidates", []))
st.session_state.reas_candidates_df = _candidates_to_df(res.get("reason_candidates", []))
```

Also handle the fallback for old structure. The existing fallback code (lines 274–276) builds `stat_candidates` from `res["Statuscode"]`. Replicate this logic in the initialization: after setting the two session state dfs above, add:

```python
if st.session_state.stat_candidates_df.empty and "Statuscode" in res:
    fallback_name = res["Statuscode"].get("Bezeichnung_im_Dokument", "Default")
    st.session_state.stat_candidates_df = _candidates_to_df(
        [{"name": fallback_name, "description": "Automatically detected"}]
    )
```

**Step 3: Run existing tests to confirm nothing is broken**

```bash
pytest tests/ -v
```

Expected: all existing tests still PASS (this change is in a button handler, not tested directly).

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: initialize stat/reas candidate DataFrames in session state on analysis"
```

---

### Task 3: Replace Step 1 UI with data_editor + move buttons

**Files:**
- Modify: `app.py:278-319` (the Step 1 Source Selection UI block)

**Step 1: Replace the existing col1/col2 UI block**

Find and replace the entire block from `col1, col2 = st.columns(2)` (line 278) through `selected_reas = []` (line 319) with:

```python
col1, col2 = st.columns(2)

# 2. UI for status codes
with col1:
    st.subheader("Status Code Sources")
    if not st.session_state.stat_candidates_df.empty:
        edited_stat = st.data_editor(
            st.session_state.stat_candidates_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "_select": st.column_config.CheckboxColumn("Move", default=False)
            },
            key="stat_candidates_editor",
        )
        if st.button("Move to Reason \u2192", key="move_to_reason"):
            to_move = edited_stat[edited_stat["_select"]].drop(columns=["_select"])
            if to_move.empty:
                st.warning("No rows selected.")
                st.stop()
            remaining = edited_stat[~edited_stat["_select"]].drop(columns=["_select"])
            remaining.insert(0, "_select", False)
            to_move_with_sel = to_move.copy()
            to_move_with_sel.insert(0, "_select", False)
            current_reas = st.session_state.reas_candidates_df.copy()
            st.session_state.stat_candidates_df = remaining.reset_index(drop=True)
            st.session_state.reas_candidates_df = pd.concat(
                [current_reas, to_move_with_sel], ignore_index=True
            )
            st.rerun()
    else:
        st.warning("No status tables found.")

# 3. UI for reason codes
with col2:
    st.subheader("Reason Code Sources")
    if not st.session_state.reas_candidates_df.empty:
        edited_reas = st.data_editor(
            st.session_state.reas_candidates_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "_select": st.column_config.CheckboxColumn("Move", default=False)
            },
            key="reas_candidates_editor",
        )
        if st.button("\u2190 Move to Status", key="move_to_status"):
            to_move = edited_reas[edited_reas["_select"]].drop(columns=["_select"])
            if to_move.empty:
                st.warning("No rows selected.")
                st.stop()
            remaining = edited_reas[~edited_reas["_select"]].drop(columns=["_select"])
            remaining.insert(0, "_select", False)
            to_move_with_sel = to_move.copy()
            to_move_with_sel.insert(0, "_select", False)
            current_stat = st.session_state.stat_candidates_df.copy()
            st.session_state.reas_candidates_df = remaining.reset_index(drop=True)
            st.session_state.stat_candidates_df = pd.concat(
                [current_stat, to_move_with_sel], ignore_index=True
            )
            st.rerun()
    else:
        st.info("No reason codes found.")
```

**Step 2: Update `selected_stats` and `selected_reas` derivation**

Immediately after the col1/col2 block (before `if st.session_state.current_step == 1:`), replace any remaining `selected_stats` / `selected_reas` references that came from the old multiselect. Add:

```python
selected_stats = st.session_state.stat_candidates_df["name"].tolist()
selected_reas = st.session_state.reas_candidates_df["name"].tolist()
```

**Step 3: Verify app starts without errors**

```bash
streamlit run app.py
```

Upload a document and proceed through Step 0 → Step 1. Verify:
- Two `st.data_editor` tables appear (one per column)
- Each row has a "Move" checkbox
- "Move to Reason →" and "← Move to Status" buttons are visible
- Checking a row and clicking a move button moves it to the other column

**Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

**Step 5: Commit**

```bash
git add app.py
git commit -m "feat: replace Step 1 multiselect/expander with data_editor + move buttons"
```

---

### Task 4: Guard against missing session state on back-navigation edge case

**Context:** If a user somehow arrives at step >= 1 without the candidates_df being initialized (e.g. older session state from before this change), the `st.session_state.stat_candidates_df` access will raise a `KeyError`.

**Files:**
- Modify: `app.py:264-266` (start of the Step 1 render block)

**Step 1: Add defensive initialization**

Directly after `res = st.session_state.analysis_res` (line 268), add a guard:

```python
# Guard: initialize candidate dfs if missing (e.g. session from before this feature)
if "stat_candidates_df" not in st.session_state:
    _stat = res.get("status_candidates", [])
    if not _stat and "Statuscode" in res:
        _stat = [{"name": res["Statuscode"].get("Bezeichnung_im_Dokument", "Default"), "description": "Automatically detected"}]
    st.session_state.stat_candidates_df = _candidates_to_df(_stat)
    st.session_state.reas_candidates_df = _candidates_to_df(res.get("reason_candidates", []))
```

**Step 2: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

**Step 3: Commit**

```bash
git add app.py
git commit -m "fix: guard Step 1 render against missing candidate dfs in session state"
```

# Step 2 Row Move Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to move individual rows between the status and reason code tables in Step 2 (separate mode) before proceeding to Step 3.

**Architecture:** Add a `_select` boolean column to editable working-copy DataFrames stored in session state. Render each via `st.data_editor` with checkbox column. Move buttons filter selected rows and update both DataFrames. Before Step 3, serialize edited DataFrames back into `extraction_res` CSV strings — the existing `merge_data_step3()` needs no changes.

**Tech Stack:** Streamlit `st.data_editor`, pandas, session state. Only `app.py` is touched.

---

### Task 1: Add session state keys for editable DataFrames

**Files:**
- Modify: `app.py:139-148` (state initialization block)

**Step 1: Add two new keys to the state init block**

Find this block (around line 139):
```python
if "current_step" not in st.session_state:
    st.session_state.current_step = 0

if "raw_text" not in st.session_state: st.session_state.raw_text = ""
if "analysis_res" not in st.session_state: st.session_state.analysis_res = {}
if "extraction_res" not in st.session_state: st.session_state.extraction_res = {}
if "df_merged" not in st.session_state: st.session_state.df_merged = pd.DataFrame()
if "df_final" not in st.session_state: st.session_state.df_final = pd.DataFrame()
if "show_save_confirm" not in st.session_state: st.session_state.show_save_confirm = False
```

Add two lines at the end:
```python
if "df_status_edit" not in st.session_state: st.session_state.df_status_edit = pd.DataFrame()
if "df_reasons_edit" not in st.session_state: st.session_state.df_reasons_edit = pd.DataFrame()
```

**Step 2: Verify the app still starts without errors**

```bash
streamlit run app.py &
# Open browser, check sidebar loads, no errors in terminal
# Ctrl+C to stop
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add session state keys for step2 editable row DataFrames"
```

---

### Task 2: Initialize editable DataFrames when entering Step 2 (separate mode)

**Files:**
- Modify: `app.py` — Step 2 block, top of the `if mode == "separate":` branch

**Context:** The Step 2 block starts around line 260:
```python
if st.session_state.current_step >= 2 and st.session_state.extraction_res:
    st.divider()
    st.header("Schritt 2: Extrahierte Rohdaten")

    mode = st.session_state.extraction_res.get("mode", "unknown")
    st.info(f"Erkannter Modus: **{mode}**")

    if mode == "separate":
        col_a, col_b = st.columns(2)
        with col_a:
            st.caption("Statuscodes (Vorschau)")
            df_s = logic.preview_csv_string(st.session_state.extraction_res.get("status_csv"))
            st.dataframe(df_s, height=200)
        with col_b:
            st.caption("Reasoncodes (Vorschau)")
            df_r = logic.preview_csv_string(st.session_state.extraction_res.get("reasons_csv"))
            st.dataframe(df_r, height=200)
```

**Step 1: Add initialization logic at the top of the `if mode == "separate":` block**

Replace the `if mode == "separate":` block content with:
```python
    if mode == "separate":
        # Initialize editable working copies on first entry (or after going back)
        if st.session_state.df_status_edit.empty:
            df_s_raw = logic.preview_csv_string(st.session_state.extraction_res.get("status_csv"))
            df_r_raw = logic.preview_csv_string(st.session_state.extraction_res.get("reasons_csv"))
            df_s_raw.insert(0, "_select", False)
            df_r_raw.insert(0, "_select", False)
            st.session_state.df_status_edit = df_s_raw
            st.session_state.df_reasons_edit = df_r_raw

        col_a, col_b = st.columns(2)
        with col_a:
            st.caption("Statuscodes (Vorschau)")
            df_s = logic.preview_csv_string(st.session_state.extraction_res.get("status_csv"))
            st.dataframe(df_s, height=200)
        with col_b:
            st.caption("Reasoncodes (Vorschau)")
            df_r = logic.preview_csv_string(st.session_state.extraction_res.get("reasons_csv"))
            st.dataframe(df_r, height=200)
```

**Step 2: Verify no crash by running the app and loading a document through to Step 2**

The UI should look identical to before at this point.

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: initialize editable DataFrames on Step 2 entry (separate mode)"
```

---

### Task 3: Replace static previews with interactive data_editor + move buttons

**Files:**
- Modify: `app.py` — the `if mode == "separate":` block (the `col_a / col_b` section you just edited in Task 2)

**Step 1: Replace the two static `st.dataframe` calls with `st.data_editor` + move buttons**

Replace the full `if mode == "separate":` block with:

```python
    if mode == "separate":
        # Initialize editable working copies on first entry (or after going back)
        if st.session_state.df_status_edit.empty:
            df_s_raw = logic.preview_csv_string(st.session_state.extraction_res.get("status_csv"))
            df_r_raw = logic.preview_csv_string(st.session_state.extraction_res.get("reasons_csv"))
            df_s_raw.insert(0, "_select", False)
            df_r_raw.insert(0, "_select", False)
            st.session_state.df_status_edit = df_s_raw
            st.session_state.df_reasons_edit = df_r_raw

        col_a, col_b = st.columns(2)

        with col_a:
            st.caption(f"Statuscodes ({len(st.session_state.df_status_edit)} Zeilen)")
            edited_status = st.data_editor(
                st.session_state.df_status_edit,
                key="status_editor",
                use_container_width=True,
                height=250,
                column_config={
                    "_select": st.column_config.CheckboxColumn("Verschieben", default=False)
                },
            )
            if st.button("Verschieben zu Reason \u2192"):
                to_move = edited_status[edited_status["_select"]].drop(columns=["_select"])
                remaining = edited_status[~edited_status["_select"]].drop(columns=["_select"])
                if remaining.empty:
                    st.error("Status-Tabelle darf nicht leer sein.")
                else:
                    remaining.insert(0, "_select", False)
                    to_move_with_sel = to_move.copy()
                    to_move_with_sel.insert(0, "_select", False)
                    current_reasons = st.session_state.df_reasons_edit.copy()
                    st.session_state.df_status_edit = remaining.reset_index(drop=True)
                    st.session_state.df_reasons_edit = pd.concat(
                        [current_reasons, to_move_with_sel], ignore_index=True
                    )
                    st.rerun()

        with col_b:
            st.caption(f"Reasoncodes ({len(st.session_state.df_reasons_edit)} Zeilen)")
            edited_reasons = st.data_editor(
                st.session_state.df_reasons_edit,
                key="reasons_editor",
                use_container_width=True,
                height=250,
                column_config={
                    "_select": st.column_config.CheckboxColumn("Verschieben", default=False)
                },
            )
            if st.button("\u2190 Verschieben zu Status"):
                to_move = edited_reasons[edited_reasons["_select"]].drop(columns=["_select"])
                remaining = edited_reasons[~edited_reasons["_select"]].drop(columns=["_select"])
                remaining.insert(0, "_select", False)
                to_move_with_sel = to_move.copy()
                to_move_with_sel.insert(0, "_select", False)
                current_status = st.session_state.df_status_edit.copy()
                st.session_state.df_reasons_edit = remaining.reset_index(drop=True)
                st.session_state.df_status_edit = pd.concat(
                    [current_status, to_move_with_sel], ignore_index=True
                )
                st.rerun()
```

Notes:
- `\u2192` = → and `\u2190` = ← (arrow characters, avoids encoding issues in the plan file)
- The reason table may become empty (that is valid — reason codes are optional)
- Column alignment may differ between the two tables if the LLM used different headers; that is fine — pandas concat handles it with NaN fill

**Step 2: Manually test in browser**
- Load a document, go through Step 1, run extraction in separate mode
- Verify checkboxes appear in both tables
- Check a row in status table, click "Verschieben zu Reason →", verify row moves
- Check a row in reason table, click "← Verschieben zu Status", verify row moves
- Try to move all status rows — verify the error message appears and nothing changes

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add row-move UI to Step 2 separate mode with checkbox selection"
```

---

### Task 4: Clear editable DataFrames when going back to Step 1

**Files:**
- Modify: `app.py` — the "🔙 Auswahl ändern" back button handler in the Step 2 navigation block

**Context:** Around line 283:
```python
    if st.session_state.current_step == 2:
        col_back, col_next = st.columns([1, 3])
        with col_back:
            if st.button("🔙 Auswahl ändern"):
                st.session_state.current_step = 1
                st.rerun()
```

**Step 1: Reset editable DataFrames when going back**

```python
        with col_back:
            if st.button("🔙 Auswahl ändern"):
                st.session_state.df_status_edit = pd.DataFrame()
                st.session_state.df_reasons_edit = pd.DataFrame()
                st.session_state.current_step = 1
                st.rerun()
```

This ensures that if the user goes back to Step 1 and changes their source selection, re-entering Step 2 will re-initialize from the freshly extracted CSV strings.

**Step 2: Manually test**
- Go to Step 2, move a row, click "🔙 Auswahl ändern", come back to Step 2 — verify the tables are freshly initialized from the original extraction (the move is gone)

**Step 3: Commit**

```bash
git add app.py
git commit -m "fix: reset editable DataFrames when navigating back from Step 2"
```

---

### Task 5: Serialize edited DataFrames into extraction_res before merge

**Files:**
- Modify: `app.py` — the "Weiter zu Schritt 3" button handler in the Step 2 navigation block

**Context:** Around line 289:
```python
        with col_next:
            if st.button("Weiter zu Schritt 3: Merge & Formatierung"):
                with st.spinner("Führe Merge durch..."):
                    df_m = logic.merge_data_step3(st.session_state.extraction_res)
                    st.session_state.df_merged = df_m.copy()
                    st.session_state.current_step = 3
                    st.rerun()
```

**Step 1: Serialize edited DataFrames before calling merge**

```python
        with col_next:
            if st.button("Weiter zu Schritt 3: Merge & Formatierung"):
                with st.spinner("Führe Merge durch..."):
                    ext_res = dict(st.session_state.extraction_res)
                    if ext_res.get("mode") == "separate":
                        status_clean = st.session_state.df_status_edit.drop(
                            columns=["_select"], errors="ignore"
                        )
                        reasons_clean = st.session_state.df_reasons_edit.drop(
                            columns=["_select"], errors="ignore"
                        )
                        ext_res["status_csv"] = status_clean.to_csv(index=False, sep=";")
                        ext_res["reasons_csv"] = reasons_clean.to_csv(index=False, sep=";")
                    df_m = logic.merge_data_step3(ext_res)
                    st.session_state.df_merged = df_m.copy()
                    st.session_state.current_step = 3
                    st.rerun()
```

Note: `errors="ignore"` on `drop(columns=["_select"])` ensures combined mode (where `_select` was never added) also works without error, but combined mode won't enter this branch anyway.

**Step 2: Write a pytest test for the serialization logic**

Create `tests/test_step2_row_move.py`:

```python
"""Tests for Step 2 row-move helper logic (DataFrame manipulation)."""
import pandas as pd
import io
from backend.extractor import preview_csv_string


def _df_with_select(csv_str: str) -> pd.DataFrame:
    """Reproduce the initialization logic: parse CSV and add _select column."""
    df = preview_csv_string(csv_str)
    df.insert(0, "_select", False)
    return df


def test_init_adds_select_column():
    csv = "Statuscode;Beschreibung\n10;Abholung\n20;Zustellung"
    df = _df_with_select(csv)
    assert "_select" in df.columns
    assert list(df["_select"]) == [False, False]


def test_move_selected_rows_to_other_table():
    csv_status = "Statuscode;Beschreibung\n10;Abholung\n20;Zustellung"
    csv_reason = "Reasoncode;Beschreibung\n01;Empf. nicht anwesend"

    df_s = _df_with_select(csv_status)
    df_r = _df_with_select(csv_reason)

    # Simulate user selecting row 0 in status table
    df_s.loc[0, "_select"] = True

    to_move = df_s[df_s["_select"]].drop(columns=["_select"])
    remaining = df_s[~df_s["_select"]].drop(columns=["_select"])

    assert len(remaining) == 1
    assert remaining.iloc[0]["Statuscode"] == 20

    to_move_with_sel = to_move.copy()
    to_move_with_sel.insert(0, "_select", False)
    df_r_updated = pd.concat([df_r, to_move_with_sel], ignore_index=True)

    # Reason table now has 2 rows: original + moved
    assert len(df_r_updated) == 2


def test_serialize_back_to_csv():
    csv_status = "Statuscode;Beschreibung\n10;Abholung"
    df_s = _df_with_select(csv_status)

    clean = df_s.drop(columns=["_select"], errors="ignore")
    result_csv = clean.to_csv(index=False, sep=";")

    # Round-trip: re-parse and verify
    df_back = pd.read_csv(io.StringIO(result_csv), sep=";")
    assert "_select" not in df_back.columns
    assert list(df_back.columns) == ["Statuscode", "Beschreibung"]
    assert df_back.iloc[0]["Statuscode"] == 10


def test_move_all_status_rows_is_blocked_by_empty_check():
    """Remaining must not be empty — this is enforced in the UI by an error message.
    Verify the detection logic itself."""
    csv_status = "Statuscode;Beschreibung\n10;Abholung"
    df_s = _df_with_select(csv_status)
    df_s.loc[0, "_select"] = True

    remaining = df_s[~df_s["_select"]].drop(columns=["_select"])
    assert remaining.empty  # UI should show error and block the move
```

**Step 3: Run the tests**

```bash
pytest tests/test_step2_row_move.py -v
```

Expected: 4 tests PASS.

**Step 4: End-to-end manual test**
- Upload a document, extract in separate mode
- Move a row from status → reason, then proceed to Step 3
- Verify the merged DataFrame in Step 3 reflects the moved row correctly (it should now appear with the reason code data)

**Step 5: Commit**

```bash
git add app.py tests/test_step2_row_move.py
git commit -m "feat: serialize edited step2 DataFrames into merge, add row-move tests"
```

---

## Done

All 5 tasks complete. The feature is fully implemented: users can move rows between status and reason tables in Step 2 (separate mode), the changes are preserved across reruns, and the merge step uses the edited data.

# Step 1 Select All / Deselect All Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "☑ Alle" and "☐ Keine" buttons below each Step 1 candidate table to set all `_include` values at once.

**Architecture:** Pure UI addition in `app.py`. Two buttons per table (Status and Reason), each writing directly to `st.session_state` and calling `st.rerun()`. No backend changes, no new tests (Streamlit button interactions are not unit-testable).

**Tech Stack:** Python, Streamlit, pandas

---

## Chunk 1: Add Select All / Deselect All buttons

### Task 1: Add buttons to col1 (Status) and col2 (Reason)

**Files:**
- Modify: `app.py` — Step 1 section, inside `with col1:` and `with col2:` blocks

**Context:** The Step 1 section (starting around line 319) renders two `st.data_editor` tables inside `if not df.empty:` blocks. Each block currently has one Move button. We add two more buttons after it.

- [ ] **Step 1: Read the current col1 block to find exact insertion point**

Read `app.py` lines 335–375 to locate the end of the col1 Move button block. It looks like:

```python
            if st.button("Move to Reason \u2192", key="move_to_reason"):
                ...
                st.rerun()
```

Note the exact indentation level — the new buttons must match it.

- [ ] **Step 2: Add Select All / Deselect All buttons after the Move button in col1**

Directly after the `if st.button("Move to Reason →", ...)` block (but still inside `if not st.session_state.stat_candidates_df.empty:`), add:

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

- [ ] **Step 3: Add the same buttons after the Move button in col2**

Read lines 376–410 to locate the end of the col2 Move button block (`if st.button("\u2190 Move to Status", ...)`).

Directly after that block (still inside `if not st.session_state.reas_candidates_df.empty:`), add:

```python
            col_all, col_none = st.columns([1, 1])
            with col_all:
                if st.button("☑ Alle", key="reas_select_all"):
                    st.session_state.reas_candidates_df["_include"] = True
                    st.rerun()
            with col_none:
                if st.button("☐ Keine", key="reas_select_none"):
                    st.session_state.reas_candidates_df["_include"] = False
                    st.rerun()
```

- [ ] **Step 4: Run tests to verify no regressions**

```bash
source venv/bin/activate && pytest tests/ -v 2>&1 | tail -10
```

Expected: 144 passed, 0 failed

- [ ] **Step 5: Manual smoke test**

```bash
source venv/bin/activate && streamlit run app.py
```

1. Upload a file → run Step 1 analysis.
2. Verify "☑ Alle" and "☐ Keine" buttons appear below each table.
3. Click "☐ Keine" on Status table → all Include checkboxes uncheck.
4. Click "☑ Alle" on Status table → all Include checkboxes check.
5. Uncheck one row manually, click "☑ Alle" → that row re-checks.
6. Click "☐ Keine" on Reason table → only Reason table affected, Status unchanged.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: add Select All / Deselect All buttons for Include checkboxes in Step 1"
```

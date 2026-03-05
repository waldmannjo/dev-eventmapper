# Design: Step 2 Row Move Feature

**Date:** 2026-03-05
**Status:** Approved

## Problem

After the LLM extracts status codes and reason codes into separate tables (Step 2, `mode == "separate"`), individual rows may land in the wrong table. Users have no way to correct this without re-running the extraction.

## Solution

Add an interactive row-move UI in Step 2 that lets users move selected rows between the status and reason code tables before proceeding to Step 3.

## Scope

- Only applies when `extraction_res["mode"] == "separate"`.
- `combined` mode is unchanged.

## State

When entering Step 2 in `separate` mode, convert the raw CSV strings into DataFrames and store as editable working copies:

- `st.session_state.df_status_edit` — editable status codes DataFrame
- `st.session_state.df_reasons_edit` — editable reason codes DataFrame

`extraction_res` is kept untouched to support going back to Step 1.

Before calling `merge_data_step3()`, write the edited DataFrames back into `extraction_res` as CSV strings so the existing merge logic requires no changes.

## UI

Two columns, mirroring the existing Step 2 layout:

- Left column: status codes table via `st.data_editor` (fixed rows, checkbox selection)
- Right column: reason codes table via `st.data_editor` (fixed rows, checkbox selection)
- Below each table: a move button
  - Under status: "Move selected to Reason ->"
  - Under reason: "<- Move selected to Status"
- A row count caption per table confirms moves.

On button click: append selected rows to the other DataFrame, remove from current, rerun.

## Edge Cases

- If the status table would become empty after a move, show an error and block the move (at least one status source is required).
- The reason table may be empty (no reason codes is valid).

## Integration with Step 3

Before proceeding to Step 3, serialize `df_status_edit` and `df_reasons_edit` back to CSV strings and update `extraction_res["status_csv"]` and `extraction_res["reasons_csv"]`. The existing `merge_data_step3()` function receives the updated dict unchanged.

## Files to Change

- `app.py` — Step 2 UI block only (lines ~260-294)

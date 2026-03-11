# Design: AI Transform Feature for Step 2

**Date:** 2026-03-11
**Status:** Approved

## Overview

Add the same LLM instruction/transform feature that exists in Step 3 ("Data Preparation") to Step 2 ("Extracted Raw Data"). Users can provide a natural-language instruction to an LLM, which transforms both the Status and Reason code tables.

## Scope

- Step 2 only (Step 1 excluded by user decision)
- Only applies to `mode == "separate"` (the combined-mode path shows a non-editable preview and is excluded)

## UI

An expander `🛠️ Transform Data (AI Assistant)` is placed after the two `data_editor` tables and before the navigation buttons in the Step 2 section. Pattern is identical to Step 3:

- `st.text_input("Instruction:")` — user describes the transformation
- Model selectbox (`key="model_step2_trans"`)
- `✨ Execute` button
- `↩️ Undo Last Change` button

## Behavior

**Execute:**
1. Back up both tables to session state (`df_status_edit_backup`, `df_reasons_edit_backup`)
2. Strip `_select` column from each table
3. Call `logic.apply_ai_transformation(client, df_status_edit, instruction, model)` → new status df
4. Call `logic.apply_ai_transformation(client, df_reasons_edit, instruction, model)` → new reason df
5. Re-insert `_select` column (set to `False`) into each result
6. Store results back in `st.session_state.df_status_edit` and `st.session_state.df_reasons_edit`
7. Track cost under `st.session_state.costs["step2_transform"]` (last transform wins, same as Step 3)
8. Show success/warning messages; call `st.rerun()` on success

**Undo:**
- Restore `df_status_edit` and `df_reasons_edit` from their backups

## Session State

| Key | Type | Purpose |
|-----|------|---------|
| `df_status_edit_backup` | DataFrame | Undo backup for status table |
| `df_reasons_edit_backup` | DataFrame | Undo backup for reason table |

## Cost Tracking

New key `step2_transform` added to `st.session_state.costs`. Sidebar label: `"Step 2 – Transform"`.

## Backend

No changes required. `logic.apply_ai_transformation` is reused as-is.

## Error Handling

Same pattern as Step 3: catch `AuthenticationError`, `RateLimitError`, `APIConnectionError`, `APIStatusError`.

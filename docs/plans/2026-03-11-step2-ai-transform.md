# Step 2 AI Transform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an AI transform expander (identical to Step 3's) to Step 2's "Extracted Raw Data" view, applying an LLM instruction to both Status and Reason code tables.

**Architecture:** Pure UI change in `app.py`. Reuses the existing `logic.apply_ai_transformation(client, df, instruction, model_name) -> (df, raw_usage)` function. No backend changes. Only applies in `mode == "separate"` path.

**Tech Stack:** Streamlit, OpenAI (via existing `client`), pandas

---

### Task 1: Add session state backup keys and sidebar cost label

**Files:**
- Modify: `app.py:230-234` (session state init block)
- Modify: `app.py:131-138` (sidebar `step_labels` dict)

**Step 1: Add backup keys to session state init**

In the session state initialization block (around line 232–234), add two lines after the existing `df_reasons_edit` init:

```python
if "df_status_edit_backup" not in st.session_state: st.session_state.df_status_edit_backup = pd.DataFrame()
if "df_reasons_edit_backup" not in st.session_state: st.session_state.df_reasons_edit_backup = pd.DataFrame()
```

**Step 2: Add sidebar cost label**

In the `step_labels` dict (around line 131–138), add a new entry after `"step2_extraction"`:

```python
"step2_transform":  "Step 2 – Transform",
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add session state and cost label for Step 2 AI transform"
```

---

### Task 2: Add AI transform expander inside the Step 2 separate-mode block

**Files:**
- Modify: `app.py` — inside `if mode == "separate":` block, after the `col_a`/`col_b` section (around line 495), before the `else:` (combined mode)

**Step 1: Add the expander**

After the closing of the second move-button (`← Move to Status`) block and still inside `if mode == "separate":`, insert:

```python
        with st.expander("🛠️ Transform Data (AI Assistant)", expanded=False):
            st.info("Describe how the columns should be modified.")
            example_prompt = "Remove rows where the status code is empty."
            user_instruction_s2 = st.text_input(
                "Instruction:", placeholder=example_prompt, key="step2_transform_input"
            )
            model_step2_trans = st.selectbox(
                "Select model for transformation:",
                options=MODEL_CONFIG.keys(),
                format_func=format_model_option,
                index=0,
                key="model_step2_trans",
            )

            if st.button("✨ Execute", key="step2_transform_exec"):
                if user_instruction_s2:
                    with st.spinner("AI generating and applying Pandas code..."):
                        st.session_state.df_status_edit_backup = st.session_state.df_status_edit.copy()
                        st.session_state.df_reasons_edit_backup = st.session_state.df_reasons_edit.copy()

                        try:
                            status_clean = st.session_state.df_status_edit.drop(columns=["_select"], errors="ignore")
                            reasons_clean = st.session_state.df_reasons_edit.drop(columns=["_select"], errors="ignore")

                            new_status, raw_usage_s = logic.apply_ai_transformation(
                                client, status_clean, user_instruction_s2, model_name=model_step2_trans
                            )
                            new_reasons, raw_usage_r = logic.apply_ai_transformation(
                                client, reasons_clean, user_instruction_s2, model_name=model_step2_trans
                            )

                            combined_usage = {
                                "input_tokens": raw_usage_s["input_tokens"] + raw_usage_r["input_tokens"],
                                "output_tokens": raw_usage_s["output_tokens"] + raw_usage_r["output_tokens"],
                                "model": raw_usage_r["model"],
                            }
                            st.session_state.costs["step2_transform"] = _make_usage(**combined_usage)

                            new_status.insert(0, "_select", False)
                            new_reasons.insert(0, "_select", False)

                            if new_status.equals(status_clean) and new_reasons.equals(reasons_clean):
                                st.warning("The AI made no changes (code may be faulty or condition not met).")
                            else:
                                st.session_state.df_status_edit = new_status.reset_index(drop=True)
                                st.session_state.df_reasons_edit = new_reasons.reset_index(drop=True)
                                st.success("Transformation applied!")
                                st.rerun()
                        except AuthenticationError:
                            st.error("Invalid OpenAI API key. Please check your key and try again.")
                        except RateLimitError as e:
                            msg = str(e)
                            if "insufficient_quota" in msg:
                                st.error("Your OpenAI account has exceeded its quota. Please check your plan and billing at platform.openai.com.")
                            else:
                                st.error("OpenAI rate limit reached. Please wait a moment and try again.")
                        except APIConnectionError:
                            st.error("Could not connect to OpenAI. Please check your network connection.")
                        except APIStatusError as e:
                            st.error(f"OpenAI API error {e.status_code}: {e.message}")

            if st.button("↩️ Undo Last Change", key="step2_transform_undo"):
                if not st.session_state.df_status_edit_backup.empty:
                    st.session_state.df_status_edit = st.session_state.df_status_edit_backup.copy()
                    st.session_state.df_reasons_edit = st.session_state.df_reasons_edit_backup.copy()
                    st.success("Undone.")
                    st.rerun()
```

**Step 2: Manual verification**

Start app: `streamlit run app.py`

1. Upload a document and proceed through Step 1 to Step 2
2. Verify the `🛠️ Transform Data (AI Assistant)` expander appears below the two tables
3. Enter an instruction (e.g., "Remove rows where the first column is empty") and click Execute
4. Verify both tables update and `st.rerun()` is called
5. Click Undo — verify both tables revert
6. Check sidebar cost section shows "Step 2 – Transform" entry after execution

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add AI transform expander to Step 2 extracted raw data"
```

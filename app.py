import os
from dotenv import load_dotenv
load_dotenv()
# GLOBAL FIX: Disable SSL Verify for Corporate Proxy / Self-Signed Certs
os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

import ssl
# Patch default SSL context to skip verification (corporate proxy)
_original_create_default_context = ssl.create_default_context
def _no_verify_ssl_context(*args, **kwargs):
    ctx = _original_create_default_context(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
ssl.create_default_context = _no_verify_ssl_context

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

import streamlit as st
import pandas as pd
from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError, APIStatusError
import backend as logic  # <-- Our new backend module
from backend.mapper import HISTORY_FILE, CACHE_EMBEDDINGS, CACHE_DF, CACHE_META

VERSION = "0.5.0"

st.set_page_config(page_title="Eventmapper", layout="wide")
st.title("Eventmapper")

# --- CONFIGURATION ---
# Configuration of available models with description and cost
MODEL_CONFIG = {
    "gpt-5-nano-2025-08-07": {"desc": "Fastest, most cost-efficient version of GPT-5", "cost": "Input: $0.05, Output: $0.4"},
    "gpt-5-mini-2025-08-07": {"desc": "A faster, cost-efficient version of GPT-5 for well-defined tasks", "cost": "Input: $0.25, Output: $2"},
    "gpt-5.1-2025-11-13": {"desc": "The best model for coding and agentic tasks with configurable reasoning effort.", "cost": "Input: $1.25, Output: $10"},
    "gpt-4.1-2025-04-14": {"desc": "Smartest non-reasoning model", "cost": "Input: $2, Output: $8"}
}

# Pricing per 1M tokens (verified 2026-03-09 against developers.openai.com/api/docs/pricing/)
PRICING = {
    "gpt-5-nano-2025-08-07":  {"input": 0.05,  "output": 0.40},
    "gpt-5-mini-2025-08-07":  {"input": 0.25,  "output": 2.00},
    "gpt-5.1-2025-11-13":     {"input": 1.25,  "output": 10.00},
    "gpt-4.1-2025-04-14":     {"input": 2.00,  "output": 8.00},
    "text-embedding-3-large": {"input": 0.13,  "output": 0.00},
}


def _make_usage(input_tokens: int, output_tokens: int, model: str) -> dict:
    """Compute a UsageDict from raw token counts and model name."""
    rates = PRICING.get(model, {"input": 0.0, "output": 0.0})
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "model": model,
    }


def _format_tokens(n: int) -> str:
    """Format token count with 'k' suffix above 999."""
    if n > 999:
        return f"{n / 1000:.1f}k"
    return str(n)


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


# Mapper Configuration (Phase 1 improvements)
MAPPER_CONFIG = {
    "use_multilingual_ce": True,
    "use_bm25": True,
    "use_keyword_boost": True,
    "embedding_dimensions": 1024,
    "knn_threshold": 0.93,
    "knn_voting_k": 5,
    "knn_consensus_threshold": 0.60,
    "confidence_threshold": 0.60,
    "top_k_prefilter": 10,
    "embedding_weight": 0.7,
    "bm25_weight": 0.3,
    "ce_max_pairs": 10000,
}

def format_model_option(model_key):
    info = MODEL_CONFIG.get(model_key, {})
    desc = info.get("desc", "")
    cost = info.get("cost", "")
    return f"{model_key} | {desc} | {cost}"

# --- Sidebar ---
with st.sidebar:
    api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    if api_key:
        client = OpenAI(api_key=api_key)
    else:
        st.warning("Please enter your API Key.")
        st.stop()

    if st.button("🔄 Reset Process", help="Clears all stored data and resets the workflow to step 0."):
        st.session_state.clear()
        st.rerun()

    if st.session_state.get("costs"):
        st.sidebar.markdown("---")
        st.sidebar.markdown("**💰 Session Cost**")

        step_labels = {
            "step1_analysis":   "Step 1 – Analysis",
            "step2_extraction": "Step 2 – Extraction",
            "step3_transform":  "Step 3 – Transform",
            "step4_embed":      "Step 4 – Embeddings",
            "step4_llm":        "Step 4 – LLM Fallback",
        }

        total_cost = 0.0
        for key, label in step_labels.items():
            usage = st.session_state.costs.get(key)
            if usage is None:
                continue
            total_cost += usage["cost_usd"]
            in_tok = _format_tokens(usage["input_tokens"])
            out_tok = _format_tokens(usage["output_tokens"])
            if usage["output_tokens"] == 0:
                tok_str = f"↑{in_tok}"
            else:
                tok_str = f"↑{in_tok} ↓{out_tok}"
            st.sidebar.markdown(f"**{label}** `${usage['cost_usd']:.4f}`  \n`{tok_str} tokens`")

        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Total** `${total_cost:.4f}`")

    # --- DEBUG / TEST MODE ---
    with st.sidebar:
        st.markdown("---")
        with st.expander("🛠️ Test: Direct Mapping"):
            st.caption("Upload a CSV/Excel file to jump directly to Step 3 (Pre-Mapping).")
            debug_file = st.file_uploader("Load file", type=["csv", "xlsx"], key="debug_upl")
            if debug_file and st.button("🚀 Load directly"):
                try:
                    if debug_file.name.endswith(".csv"):
                        df_d = pd.read_csv(debug_file, sep=None, engine="python")
                    else:
                        df_d = pd.read_excel(debug_file)
                    st.session_state.df_merged = df_d.copy()
                    st.session_state.current_step = 3
                    if not st.session_state.raw_text: st.session_state.raw_text = "DEBUG"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("---")
    st.caption(f"Eventmapper v{VERSION}")

    CHANGELOG = {
        "0.5.0": [
            "Cost transparency — sidebar shows token usage and estimated USD cost per step",
        ],
        "0.4.0": [
            "Save to History button — append confirmed LLM mappings to history for future k-NN use",
            "k-NN threshold slider — tune history match strictness per document (0.80–0.99)",
            "Full 31-code fallback for unknown carriers when cross-encoder has no signal",
            "Expanded AEB code keywords (IOD, CAS, ERR, HIN, WRN) with international carrier terms",
        ],
        "0.3.0": [
            "Responses API migration (OpenAI)",
            "Batched cross-encoder predictions",
            "Vectorized cosine similarity",
            "Persistent embedding disk cache",
            "MAPPER_CONFIG wired into pipeline",
            "Auto-detect CSV separator",
        ],
        "0.2.0": [
            "BM25 lexical scoring",
            "Keyword boost for AEB codes",
            "Multilingual cross-encoder",
            "Reduced embedding dimensions (1024)",
        ],
        "0.1.0": [
            "Initial release",
            "Hybrid mapping pipeline (k-NN + Bi-Encoder + Cross-Encoder + LLM)",
            "Document analysis & extraction",
        ],
    }

    with st.popover("What's new?"):
        versions = list(CHANGELOG.items())
        latest_ver, latest_items = versions[0]
        st.markdown(f"**v{latest_ver}**")
        for item in latest_items:
            st.markdown(f"- {item}")
        if len(versions) > 1:
            with st.expander("Older versions"):
                for ver, items in versions[1:]:
                    st.markdown(f"**v{ver}**")
                    for item in items:
                        st.markdown(f"- {item}")

# --- State Initialization ---
if "current_step" not in st.session_state:
    st.session_state.current_step = 0

if "raw_text" not in st.session_state: st.session_state.raw_text = ""
if "analysis_res" not in st.session_state: st.session_state.analysis_res = {}
if "extraction_res" not in st.session_state: st.session_state.extraction_res = {}
if "df_merged" not in st.session_state: st.session_state.df_merged = pd.DataFrame()
if "df_final" not in st.session_state: st.session_state.df_final = pd.DataFrame()
if "show_save_confirm" not in st.session_state: st.session_state.show_save_confirm = False
if "df_status_edit" not in st.session_state: st.session_state.df_status_edit = pd.DataFrame()
if "df_reasons_edit" not in st.session_state: st.session_state.df_reasons_edit = pd.DataFrame()
if "costs" not in st.session_state: st.session_state.costs = {}

# =========================================================
# STEP 0: UPLOAD
# =========================================================
st.header("Step 0: Document Upload")
uploaded_file = st.file_uploader("Upload file", type=["pdf", "xlsx", "csv", "txt"])

if uploaded_file and not st.session_state.raw_text:
    with st.spinner("Reading file..."):
        text = logic.extract_text_from_file(uploaded_file)
        st.session_state.raw_text = text
        st.success(f"Text extracted ({len(text)} characters).")
        st.session_state.current_step = 0

if st.session_state.raw_text:
    if st.session_state.current_step == 0:
        model_step1 = st.selectbox(
            "Select model for structural analysis:",
            options=MODEL_CONFIG.keys(),
            format_func=format_model_option,
            index=0,
            key="model_step1"
        )
        if st.button("Continue to Step 1: Start Structural Analysis"):
            with st.spinner("Analyzing structure..."):
                try:
                    res, raw_usage = logic.analyze_structure_step1(client, st.session_state.raw_text, model_name=model_step1)
                    st.session_state.analysis_res = res
                    st.session_state.costs["step1_analysis"] = _make_usage(**raw_usage)
                    st.session_state.current_step = 1
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

# =========================================================
# STEP 1: ANALYSIS RESULT
# =========================================================
if st.session_state.current_step >= 1 and st.session_state.analysis_res:
    st.divider()
    st.header("Step 1: Source Selection")

    res = st.session_state.analysis_res

    # 1. Get candidates from JSON
    stat_candidates = res.get("status_candidates", [])
    reas_candidates = res.get("reason_candidates", [])

    # Fallback for old structure (in case JSON looks different)
    if not stat_candidates and "Statuscode" in res:
        stat_candidates = [{"name": res["Statuscode"].get("Bezeichnung_im_Dokument", "Default"), "description": "Automatically detected"}]

    col1, col2 = st.columns(2)

    # 2. UI for status codes (Multiselect)
    with col1:
        st.subheader("Status Code Sources")
        if stat_candidates:
            # Create list of names for the UI
            stat_options = [c["name"] for c in stat_candidates]
            # Select all by default
            selected_stats = st.multiselect(
                "Which tables to use?",
                options=stat_options,
                default=stat_options,
                help="Select whether to use Table 8, Table 9, or both."
            )
            # Show candidate details
            for c in stat_candidates:
                with st.expander(f"📋 {c['name']}", expanded=True):
                    if c.get("context"):
                        st.caption(f"📍 Location: {c['context']}")
                    if c.get("description"):
                        st.write(c["description"])
        else:
            st.warning("No status tables found.")
            selected_stats = []

    # 3. UI for reason codes
    with col2:
        st.subheader("Reason Code Sources")
        if reas_candidates:
            reas_options = [c["name"] for c in reas_candidates]
            selected_reas = st.multiselect("Which tables to use?", options=reas_options, default=reas_options)
            # Show candidate details
            for c in reas_candidates:
                with st.expander(f"📋 {c['name']}", expanded=False):
                    if c.get("context"):
                        st.caption(f"📍 Location: {c['context']}")
                    if c.get("description"):
                        st.write(c["description"])
        else:
            st.info("No reason codes found.")
            selected_reas = []

    if st.session_state.current_step == 1:
        # Button checks whether a selection was made
        model_step2 = st.selectbox(
            "Select model for extraction:",
            options=MODEL_CONFIG.keys(),
            format_func=format_model_option,
            index=0,
            key="model_step2"
        )
        col_back, col_next = st.columns([1, 3])
        with col_back:
            if st.button("🔙 Repeat Analysis"):
                st.session_state.current_step = 0
                st.rerun()
        with col_next:
            if st.button("Continue to Step 2: Extract with Selection"):
                if not selected_stats:
                    st.error("Please select at least one source for status codes.")
                else:
                    with st.spinner(f"Extracting data from {len(selected_stats)} sources..."):
                        # Pass the lists to Step 2
                        try:
                            ext_res, raw_usage = logic.extract_data_step2(
                                client,
                                st.session_state.raw_text,
                                selected_stats,
                                selected_reas,
                                model_name=model_step2
                            )
                            st.session_state.extraction_res = ext_res
                            st.session_state.costs["step2_extraction"] = _make_usage(**raw_usage)
                            st.session_state.current_step = 2
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

# =========================================================
# STEP 2: EXTRACTION INTERMEDIATE RESULT
# =========================================================
if st.session_state.current_step >= 2 and st.session_state.extraction_res:
    st.divider()
    st.header("Step 2: Extracted Raw Data")

    mode = st.session_state.extraction_res.get("mode", "unknown")
    st.info(f"Detected mode: **{mode}**")

    if mode == "separate":
        # Initialize editable working copies on first entry
        if "_select" not in st.session_state.df_status_edit.columns:
            df_s_raw = logic.preview_csv_string(st.session_state.extraction_res.get("status_csv"))
            df_r_raw = logic.preview_csv_string(st.session_state.extraction_res.get("reasons_csv"))
            df_s_raw.insert(0, "_select", False)
            df_r_raw.insert(0, "_select", False)
            st.session_state.df_status_edit = df_s_raw
            st.session_state.df_reasons_edit = df_r_raw

        col_a, col_b = st.columns(2)

        with col_a:
            st.caption(f"Status codes ({len(st.session_state.df_status_edit)} rows)")
            edited_status = st.data_editor(
                st.session_state.df_status_edit,
                key="status_editor",
                use_container_width=True,
                height=250,
                column_config={
                    "_select": st.column_config.CheckboxColumn("Move", default=False)
                },
            )
            if st.button("Move to Reason \u2192"):
                to_move = edited_status[edited_status["_select"]].drop(columns=["_select"])
                if to_move.empty:
                    st.warning("No rows selected.")
                    st.stop()
                remaining = edited_status[~edited_status["_select"]].drop(columns=["_select"])
                if remaining.empty:
                    st.error("Status table must not be empty.")
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
            st.caption(f"Reason codes ({len(st.session_state.df_reasons_edit)} rows)")
            edited_reasons = st.data_editor(
                st.session_state.df_reasons_edit,
                key="reasons_editor",
                use_container_width=True,
                height=250,
                column_config={
                    "_select": st.column_config.CheckboxColumn("Move", default=False)
                },
            )
            if st.button("\u2190 Move to Status"):
                to_move = edited_reasons[edited_reasons["_select"]].drop(columns=["_select"])
                if to_move.empty:
                    st.warning("No rows selected.")
                    st.stop()
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
    else:
        st.caption("Combined list (preview)")
        df_c = logic.preview_csv_string(st.session_state.extraction_res.get("combined_csv"))
        st.dataframe(df_c, height=200)

    if st.session_state.current_step == 2:
        col_back, col_next = st.columns([1, 3])
        with col_back:
            if st.button("🔙 Change Selection"):
                st.session_state.df_status_edit = pd.DataFrame()
                st.session_state.df_reasons_edit = pd.DataFrame()
                st.session_state.current_step = 1
                st.rerun()
        with col_next:
            if st.button("Continue to Step 3: Merge & Formatting"):
                with st.spinner("Merging data..."):
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

# =========================================================
# STEP 3: MERGE RESULT
# =========================================================
if st.session_state.current_step >= 3:
    st.divider()
    st.header("Step 3: Data Preparation")

    if st.session_state.df_merged.empty:
        st.error("No data available.")
    else:
        # --- A. DISPLAY ---
        st.subheader("Current Data")
        st.dataframe(st.session_state.df_merged.head(), width='stretch')
        st.caption(f"Total rows: {len(st.session_state.df_merged)}")

        # --- B. AI TRANSFORMATION ---
        with st.expander("🛠️ Transform Data (AI Assistant)", expanded=False):
            st.info("Describe how the columns should be modified.")

            # Example suggestions for the user
            example_prompt = "Append reason code to status code. If reason is empty, use '00', otherwise use reason."
            user_instruction = st.text_input("Instruction:", placeholder=example_prompt)

            model_step3_trans = st.selectbox(
                "Select model for transformation:",
                options=MODEL_CONFIG.keys(),
                format_func=format_model_option,
                index=0,
                key="model_step3_trans"
            )

            if st.button("✨ Execute"):
                if user_instruction:
                    with st.spinner("AI generating and applying Pandas code..."):
                        # Save old state (light undo function)
                        st.session_state.df_merged_backup = st.session_state.df_merged.copy()

                        try:
                            # Apply transformation
                            new_df, raw_usage = logic.apply_ai_transformation(
                                client,
                                st.session_state.df_merged,
                                user_instruction,
                                model_name=model_step3_trans
                            )
                            st.session_state.costs["step3_transform"] = _make_usage(**raw_usage)  # last transform wins

                            # Check result
                            if new_df.equals(st.session_state.df_merged):
                                st.warning("The AI made no changes (code may be faulty or condition not met).")
                            else:
                                st.session_state.df_merged = new_df
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

            if st.button("↩️ Undo Last Change"):
                if "df_merged_backup" in st.session_state:
                    st.session_state.df_merged = st.session_state.df_merged_backup
                    st.success("Undone.")
                    st.rerun()

        # --- Download Button for Merge File ---
        csv_merged = st.session_state.df_merged.to_csv(index=False, sep=";").encode('utf-8')

        col_dl, col_next = st.columns([1, 2])

        with col_dl:
            st.download_button(
                label="💾 Download Merge Data",
                data=csv_merged,
                file_name="merged_codes_step3.csv",
                mime="text/csv"
            )

        with col_next:
            if st.session_state.current_step == 3:
                st.markdown("#### Mapping Configuration")
                model_step4 = st.selectbox(
                    "Select model for mapping:",
                    options=MODEL_CONFIG.keys(),
                    format_func=format_model_option,
                    index=0,
                    key="model_step4"
                )

                threshold = st.slider(
                    "LLM Threshold (Confidence Threshold)",
                    min_value=0.0, max_value=1.0, value=0.6, step=0.05,
                    help="Rows below this threshold are reviewed by the LLM. Higher = more LLM calls (more expensive, more accurate)."
                )
                st.caption(
                    "Rows where the model is uncertain (confidence < threshold) are reviewed by the LLM for safety. "
                    "Higher value = more LLM calls (more expensive, but more accurate). Lower value = faster & cheaper, but more errors."
                )

                knn_threshold = st.slider(
                    "k-NN Threshold (History Match)",
                    min_value=0.80, max_value=0.99,
                    value=float(MAPPER_CONFIG["knn_threshold"]),
                    step=0.01,
                    help="Lower threshold = more history matches, higher risk of incorrect matches. Default: 0.93."
                )
                st.caption(
                    "How similar must an event text be to a historical mapping to be applied directly (without LLM). "
                    "Higher value = stricter, only very precise matches. Lower value = more history matches, but higher risk of incorrect transfers."
                )

                if st.button("Continue to Step 4: Start AI Mapping", type="primary"):
                    prog_bar = st.progress(0)
                    status_text = st.empty()

                    def update_progress(p, text):
                        prog_bar.progress(p)
                        status_text.text(text)

                    try:
                        df_fin, step4_usage = logic.run_mapping_step4(
                            client,
                            st.session_state.df_merged,
                            model_name=model_step4,
                            threshold=threshold,
                            progress_callback=update_progress,
                            config={**MAPPER_CONFIG, "knn_threshold": knn_threshold}
                        )
                        st.session_state.df_final = df_fin
                        for key, raw in step4_usage.items():
                            if raw:
                                # raw is already {"input_tokens", "output_tokens", "model"} — same signature as _make_usage expects
                                st.session_state.costs[key] = _make_usage(**raw)
                        st.session_state.current_step = 4
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

# =========================================================
# STEP 4: FINAL RESULT
# =========================================================
if st.session_state.current_step >= 4:
    st.divider()
    st.header("✅ Step 4: Final Mapping")

    st.dataframe(st.session_state.df_final, width="stretch")

    csv_data = st.session_state.df_final.to_csv(index=False, sep=";").encode('utf-8')
    st.download_button("💾 Download Mapping", csv_data, "final_mapping.csv", "text/csv")

    # --- Save to History ---
    if not st.session_state.df_final.empty and "source" in st.session_state.df_final.columns:
        SAVE_CONF_THRESHOLD = 0.70
        llm_mask = (
            (st.session_state.df_final["source"] == "llm-batch") &
            (st.session_state.df_final["confidence"] >= SAVE_CONF_THRESHOLD)
        )
        df_save_candidates = st.session_state.df_final[llm_mask]

        if len(df_save_candidates) > 0:
            st.markdown("---")
            st.markdown(
                f"**{len(df_save_candidates)} LLM mappings** with confidence ≥ {SAVE_CONF_THRESHOLD:.0%} "
                "can be saved to history (improves future k-NN matches)."
            )

            if not st.session_state.show_save_confirm:
                if st.button("📥 Save to History"):
                    st.session_state.show_save_confirm = True
                    st.rerun()
            else:
                preview_cols = [c for c in ["Description", "final_code", "confidence"] if c in df_save_candidates.columns]
                st.caption("Preview (max. 10 rows):")
                st.dataframe(df_save_candidates[preview_cols].head(10))
                st.caption(f"Total: {len(df_save_candidates)} rows will be appended to history.")

                col_yes, col_no = st.columns([1, 1])
                with col_yes:
                    if st.button("✅ Confirm and Save", type="primary"):
                        try:
                            desc_col = "Description" if "Description" in df_save_candidates.columns else df_save_candidates.columns[0]
                            rows_to_add = pd.DataFrame({
                                "Description": df_save_candidates[desc_col].values,
                                "AEB Event Code": df_save_candidates["final_code"].values,
                            })
                            df_hist_existing = pd.read_excel(HISTORY_FILE)
                            df_hist_updated = pd.concat([df_hist_existing, rows_to_add], ignore_index=True)
                            df_hist_updated.to_excel(HISTORY_FILE, index=False)

                            for cf in [CACHE_EMBEDDINGS, CACHE_DF, CACHE_META]:
                                if os.path.exists(cf):
                                    os.remove(cf)
                            st.cache_resource.clear()

                            st.session_state.show_save_confirm = False
                            st.success(f"✅ {len(rows_to_add)} rows saved. Cache will be regenerated on the next run.")
                        except Exception as e:
                            st.error(f"Error saving: {e}")
                with col_no:
                    if st.button("❌ Cancel"):
                        st.session_state.show_save_confirm = False
                        st.rerun()

import os
# GLOBAL FIX: Disable SSL Verify for Corporate Proxy / Self-Signed Certs
os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

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
from openai import OpenAI
import backend as logic  # <-- Das ist unser neues Modul
from backend.mapper import HISTORY_FILE, CACHE_EMBEDDINGS, CACHE_DF, CACHE_META

VERSION = "0.4.0"

st.set_page_config(page_title="Eventmapper", layout="wide")
st.title("Eventmapper")

# --- KONFIGURATION ---
# Konfiguration der verfügbaren Modelle mit Beschreibung und Kosten
MODEL_CONFIG = {
    "gpt-5-nano-2025-08-07": {"desc": "Fastest, most cost-efficient version of GPT-5", "cost": "Input: $0.05, Output: $0.4"},
    "gpt-5-mini-2025-08-07": {"desc": "A faster, cost-efficient version of GPT-5 for well-defined tasks", "cost": "Input: $0.25, Output: $2"},
    "gpt-5.1-2025-11-13": {"desc": "The best model for coding and agentic tasks with configurable reasoning effort.", "cost": "Input: $1.25, Output: $10"},
    "gpt-4.1-2025-04-14": {"desc": "Smartest non-reasoning model", "cost": "Input: $2, Output: $8"}
}

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
}

def format_model_option(model_key):
    info = MODEL_CONFIG.get(model_key, {})
    desc = info.get("desc", "")
    cost = info.get("cost", "")
    return f"{model_key} | {desc} | {cost}"

# --- Sidebar ---
with st.sidebar:
    api_key = st.text_input("OpenAI API Key", type="password")
    if api_key:
        client = OpenAI(api_key=api_key)
    else:
        st.warning("Bitte API Key eingeben.")
        st.stop()
        
    if st.button("🔄 Prozess zurücksetzen", help="Löscht alle gespeicherten Daten und setzt den Workflow auf Schritt 0 zurück."):
        st.session_state.clear()
        st.rerun()

    # --- DEBUG / TEST MODE ---
    with st.sidebar:
        st.markdown("---")
        with st.expander("🛠️ Test: Mapping direkt"):
            st.caption("Lade eine CSV/Excel Datei hoch, um direkt zu Schritt 3 (Pre-Mapping) zu springen.")
            debug_file = st.file_uploader("Datei laden", type=["csv", "xlsx"], key="debug_upl")
            if debug_file and st.button("🚀 Direkt laden"):
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
                    st.error(f"Fehler: {e}")

    st.markdown("---")
    st.caption(f"Eventmapper v{VERSION}")

    CHANGELOG = {
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

# --- State Initialisierung ---
if "current_step" not in st.session_state:
    st.session_state.current_step = 0

if "raw_text" not in st.session_state: st.session_state.raw_text = ""
if "analysis_res" not in st.session_state: st.session_state.analysis_res = {}
if "extraction_res" not in st.session_state: st.session_state.extraction_res = {}
if "df_merged" not in st.session_state: st.session_state.df_merged = pd.DataFrame()
if "df_final" not in st.session_state: st.session_state.df_final = pd.DataFrame()
if "show_save_confirm" not in st.session_state: st.session_state.show_save_confirm = False

# =========================================================
# SCHRITT 0: UPLOAD
# =========================================================
st.header("Schritt 0: Dokument Upload")
uploaded_file = st.file_uploader("Datei hochladen", type=["pdf", "xlsx", "csv", "txt"])

if uploaded_file and not st.session_state.raw_text:
    with st.spinner("Lese Datei ein..."):
        text = logic.extract_text_from_file(uploaded_file)
        st.session_state.raw_text = text
        st.success(f"Text extrahiert ({len(text)} Zeichen).")
        st.session_state.current_step = 0

if st.session_state.raw_text:
    if st.session_state.current_step == 0:
        model_step1 = st.selectbox(
            "Modell für Strukturanalyse wählen:", 
            options=MODEL_CONFIG.keys(), 
            format_func=format_model_option,
            index=0, 
            key="model_step1"
        )
        if st.button("Weiter zu Schritt 1: Strukturanalyse starten"):
            with st.spinner("Analysiere Struktur..."):
                res = logic.analyze_structure_step1(client, st.session_state.raw_text, model_name=model_step1)
                st.session_state.analysis_res = res
                st.session_state.current_step = 1
                st.rerun()

# =========================================================
# SCHRITT 1: ANALYSE ERGEBNIS
# =========================================================
if st.session_state.current_step >= 1 and st.session_state.analysis_res:
    st.divider()
    st.header("Schritt 1: Quellen-Auswahl")
    
    res = st.session_state.analysis_res
    
    # 1. Kandidaten aus JSON holen
    stat_candidates = res.get("status_candidates", [])
    reas_candidates = res.get("reason_candidates", [])
    
    # Fallback für alte Struktur (falls JSON mal anders aussieht)
    if not stat_candidates and "Statuscode" in res:
        stat_candidates = [{"name": res["Statuscode"].get("Bezeichnung_im_Dokument", "Standard"), "description": "Automatisch erkannt"}]

    col1, col2 = st.columns(2)
    
    # 2. UI für Statuscodes (Multiselect)
    with col1:
        st.subheader("Statuscode Quellen")
        if stat_candidates:
            # Erstelle Liste von Namen für das UI
            stat_options = [c["name"] for c in stat_candidates]
            # Standardmäßig alle auswählen
            selected_stats = st.multiselect(
                "Welche Tabellen nutzen?", 
                options=stat_options, 
                default=stat_options,
                help="Wählen Sie hier, ob Sie Tabelle 8, Tabelle 9 oder beide nutzen wollen."
            )
        else:
            st.warning("Keine Status-Tabellen gefunden.")
            selected_stats = []

    # 3. UI für Reasoncodes
    with col2:
        st.subheader("Reasoncode Quellen")
        if reas_candidates:
            reas_options = [c["name"] for c in reas_candidates]
            selected_reas = st.multiselect("Welche Tabellen nutzen?", options=reas_options, default=reas_options)
        else:
            st.info("Keine Reason-Codes gefunden.")
            selected_reas = []

    if st.session_state.current_step == 1:
        # Button prüft, ob Auswahl getroffen wurde
        model_step2 = st.selectbox(
            "Modell für Extraktion wählen:", 
            options=MODEL_CONFIG.keys(), 
            format_func=format_model_option,
            index=0, 
            key="model_step2"
        )
        col_back, col_next = st.columns([1, 3])
        with col_back:
            if st.button("🔙 Analyse wiederholen"):
                st.session_state.current_step = 0
                st.rerun()
        with col_next:
            if st.button("Weiter zu Schritt 2: Extraktion mit Auswahl"):
                if not selected_stats:
                    st.error("Bitte mindestens eine Quelle für Statuscodes wählen.")
                else:
                    with st.spinner(f"Extrahiere Daten aus {len(selected_stats)} Quellen..."):
                        # Wir übergeben jetzt die Listen an Step 2
                        ext_res = logic.extract_data_step2(
                            client, 
                            st.session_state.raw_text, 
                            selected_stats, 
                            selected_reas,
                            model_name=model_step2
                        )
                        st.session_state.extraction_res = ext_res
                        st.session_state.current_step = 2
                        st.rerun()

# =========================================================
# SCHRITT 2: EXTRAKTION ZWISCHENERGEBNIS
# =========================================================
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
    else:
        st.caption("Kombinierte Liste (Vorschau)")
        df_c = logic.preview_csv_string(st.session_state.extraction_res.get("combined_csv"))
        st.dataframe(df_c, height=200)

    if st.session_state.current_step == 2:
        col_back, col_next = st.columns([1, 3])
        with col_back:
            if st.button("🔙 Auswahl ändern"):
                st.session_state.current_step = 1
                st.rerun()
        with col_next:
            if st.button("Weiter zu Schritt 3: Merge & Formatierung"):
                with st.spinner("Führe Merge durch..."):
                    df_m = logic.merge_data_step3(st.session_state.extraction_res)
                    st.session_state.df_merged = df_m.copy()
                    st.session_state.current_step = 3
                    st.rerun()

# =========================================================
# SCHRITT 3: MERGE ERGEBNIS
# =========================================================
if st.session_state.current_step >= 3:
    st.divider()
    st.header("Schritt 3: Datenaufbereitung")
    
    if st.session_state.df_merged.empty:
        st.error("Keine Daten vorhanden.")
    else:
        # --- A. ANZEIGE ---
        st.subheader("Aktuelle Daten")
        st.dataframe(st.session_state.df_merged.head(), width='stretch')
        st.caption(f"Gesamtzeilen: {len(st.session_state.df_merged)}")

        # --- B. KI TRANSFORMATION (NEU) ---
        with st.expander("🛠️ Daten transformieren (KI-Assistent)", expanded=False):
            st.info("Beschreiben Sie, wie die Spalten geändert werden sollen.")
            
            # Beispiel-Vorschläge für den User
            example_prompt = "Hänge Reasoncode an Statuscode an. Wenn Reason leer ist, nimm '00', sonst Reason."
            user_instruction = st.text_input("Anweisung:", placeholder=example_prompt)
            
            model_step3_trans = st.selectbox(
                "Modell für Transformation wählen:", 
                options=MODEL_CONFIG.keys(), 
                format_func=format_model_option,
                index=0, 
                key="model_step3_trans"
            )
            
            if st.button("✨ Ausführen"):
                if user_instruction:
                    with st.spinner("KI generiert Pandas-Code und wendet ihn an..."):
                        # Alten State sichern (Undo-Funktion light)
                        st.session_state.df_merged_backup = st.session_state.df_merged.copy()
                        
                        # Transformation aufrufen
                        new_df = logic.apply_ai_transformation(
                            client, 
                            st.session_state.df_merged, 
                            user_instruction,
                            model_name=model_step3_trans
                        )
                        
                        # Ergebnis prüfen
                        if new_df.equals(st.session_state.df_merged):
                            st.warning("Die KI hat keine Änderung vorgenommen (Code evtl. fehlerhaft oder Bedingung nicht erfüllt).")
                        else:
                            st.session_state.df_merged = new_df
                            st.success("Transformation angewendet!")
                            st.rerun()

            if st.button("↩️ Letzte Änderung rückgängig machen"):
                if "df_merged_backup" in st.session_state:
                    st.session_state.df_merged = st.session_state.df_merged_backup
                    st.success("Rückgängig gemacht.")
                    st.rerun()
        
        # --- NEU: Download Button für Merge-Datei ---
        csv_merged = st.session_state.df_merged.to_csv(index=False, sep=";").encode('utf-8')
        
        col_dl, col_next = st.columns([1, 2])
        
        with col_dl:
            st.download_button(
                label="💾 Merge-Daten herunterladen",
                data=csv_merged,
                file_name="merged_codes_step3.csv",
                mime="text/csv"
            )

        with col_next:
            if st.session_state.current_step == 3:
                st.markdown("#### Mapping Konfiguration")
                model_step4 = st.selectbox(
                    "Modell für Mapping wählen:", 
                    options=MODEL_CONFIG.keys(), 
                    format_func=format_model_option,
                    index=0, 
                    key="model_step4"
                )
                
                threshold = st.slider(
                    "LLM-Schwelle (Confidence Threshold)",
                    min_value=0.0, max_value=1.0, value=0.6, step=0.05,
                    help="Werte unter dieser Schwelle werden vom LLM geprüft. Höher = mehr LLM-Aufrufe (teurer, genauer)."
                )
                st.caption(
                    "Zeilen, bei denen das Modell unsicher ist (Confidence < Schwelle), werden zur Sicherheit vom LLM geprüft. "
                    "Höherer Wert = mehr LLM-Aufrufe (teurer, aber genauer). Niedrigerer Wert = schneller & günstiger, aber mehr Fehler."
                )

                knn_threshold = st.slider(
                    "k-NN Schwelle (History Match)",
                    min_value=0.80, max_value=0.99,
                    value=float(MAPPER_CONFIG["knn_threshold"]),
                    step=0.01,
                    help="Geringere Schwelle = mehr History-Treffer, höheres Risiko falscher Matches. Standard: 0.93."
                )
                st.caption(
                    "Wie ähnlich muss ein Event-Text zu einem historischen Mapping sein, damit er direkt übernommen wird (ohne LLM). "
                    "Höherer Wert = strenger, nur sehr genaue Treffer. Niedrigerer Wert = mehr Treffer aus der History, aber höheres Risiko falscher Übernahmen."
                )

                if st.button("Weiter zu Schritt 4: KI Mapping starten", type="primary"):
                    prog_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def update_progress(p, text):
                        prog_bar.progress(p)
                        status_text.text(text)

                    df_fin = logic.run_mapping_step4(
                        client,
                        st.session_state.df_merged,
                        model_name=model_step4,
                        threshold=threshold,
                        progress_callback=update_progress,
                        config={**MAPPER_CONFIG, "knn_threshold": knn_threshold}
                    )
                    st.session_state.df_final = df_fin
                    st.session_state.current_step = 4
                    st.rerun()

# =========================================================
# SCHRITT 4: FINALERGEBNIS
# =========================================================
if st.session_state.current_step >= 4:
    st.divider()
    st.header("✅ Schritt 4: Finales Mapping")
    
    st.dataframe(st.session_state.df_final, width="stretch")
    
    csv_data = st.session_state.df_final.to_csv(index=False, sep=";").encode('utf-8')
    st.download_button("💾 Mapping herunterladen", csv_data, "final_mapping.csv", "text/csv")

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
                f"**{len(df_save_candidates)} LLM-Mappings** mit Confidence ≥ {SAVE_CONF_THRESHOLD:.0%} "
                "können zur History gespeichert werden (verbessert zukünftige k-NN Treffer)."
            )

            if not st.session_state.show_save_confirm:
                if st.button("📥 In History speichern"):
                    st.session_state.show_save_confirm = True
                    st.rerun()
            else:
                preview_cols = [c for c in ["Beschreibung", "final_code", "confidence"] if c in df_save_candidates.columns]
                st.caption("Vorschau (max. 10 Zeilen):")
                st.dataframe(df_save_candidates[preview_cols].head(10))
                st.caption(f"Gesamt: {len(df_save_candidates)} Zeilen werden an die History angehängt.")

                col_yes, col_no = st.columns([1, 1])
                with col_yes:
                    if st.button("✅ Bestätigen und speichern", type="primary"):
                        try:
                            desc_col = "Beschreibung" if "Beschreibung" in df_save_candidates.columns else df_save_candidates.columns[0]
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
                            st.success(f"✅ {len(rows_to_add)} Zeilen gespeichert. Cache wird beim nächsten Run neu generiert.")
                        except Exception as e:
                            st.error(f"Fehler beim Speichern: {e}")
                with col_no:
                    if st.button("❌ Abbrechen"):
                        st.session_state.show_save_confirm = False
                        st.rerun()
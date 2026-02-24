# Schritt 4: Mapping
# Mapping der extrahierten Daten auf Standard-Codes.

import asyncio
import hashlib
import json
import os
import re

import numpy as np
import pandas as pd
from openai import AsyncOpenAI
# Fix for corporate proxy SSL issues when downloading models
os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

# Patch huggingface_hub session to disable SSL verification
import huggingface_hub.utils._http as _hf_http
_original_get_session = _hf_http.get_session
def _patched_get_session():
    session = _original_get_session()
    session.verify = False
    return session
_hf_http.get_session = _patched_get_session

from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import CrossEncoder
import streamlit as st # Für Caching des Modells

from codes import CODES  # Importiert codes.py aus dem Hauptverzeichnis
from rank_bm25 import BM25Okapi
from backend.synonyms import CONTENT_NORMALIZATION

# Konfiguration
EMB_MODEL = "text-embedding-3-large" # Konsistent bleiben
EMB_DIMENSIONS = 1024  # Reduced from 3072 for cost savings (67% reduction)
# LOW_CONF_THRESHOLD = 0.60
CROSS_ENCODER_MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
HISTORY_FILE = "examples/CES_Umschlüsselungseinträge_all.xlsx"

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def normalize_input(text):
    """Normalize carrier text before embedding/BM25.

    Performs:
    - Timestamp removal (e.g. '2026-02-17 14:30:00' or '2026-02-17T14:30')
    - Tracking ID removal (long mixed alphanumeric sequences ≥10 chars with ≥1 digit)
    - Lowercasing
    - Synonym / abbreviation expansion via CONTENT_NORMALIZATION
    """
    # Remove timestamps before lowercasing so 'T' separator is matched correctly
    text = re.sub(r'\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}(:\d{2})?', '', text)
    # Remove tracking IDs: long alphanumeric tokens (≥10 chars) that contain at
    # least one digit — avoids stripping plain German words like 'sortierzentrum'
    text = re.sub(r'\b(?=[A-Z0-9]*\d)[A-Z0-9]{10,}\b', '', text, flags=re.IGNORECASE)
    text = text.lower()
    # Apply synonym / abbreviation mapping using word-boundary regex to prevent
    # substring corruption (e.g. "avis" inside "aviso", "lager" inside "Verlagerung").
    # Longer keys are tried first so e.g. "aviso" matches before "avis".
    for abbrev in sorted(CONTENT_NORMALIZATION, key=len, reverse=True):
        expansion = CONTENT_NORMALIZATION[abbrev]
        # Abbreviations ending in '.' can't use \b (period is not a word char),
        # so use a negative lookbehind to avoid matching mid-word.
        if abbrev.endswith('.'):
            pattern = r'(?<!\w)' + re.escape(abbrev)
        else:
            pattern = r'\b' + re.escape(abbrev) + r'\b'
        text = re.sub(pattern, expansion, text)
    return text.strip()

def tokenize_for_bm25(text):
    """Tokenize text for BM25, expanding German compound words into subword parts.

    Splits on whitespace first, then extracts alphabetic parts from each token
    using a regex that handles umlauts (ä, ö, ü, ß).  When a token contains
    multiple parts (i.e. it was a compound or hyphenated word), both the
    individual parts *and* the original token are retained so that exact-match
    and subword-match queries both work.

    Example:
        "Zustellhindernis" -> ["zustellhindernis"]   (single part, no expansion)
        "Paket-Annahme"    -> ["paket", "annahme", "paket-annahme"]
    """
    tokens = text.lower().split()
    expanded = []
    for t in tokens:
        parts = re.findall(r'[a-zäöüß]+', t)
        expanded.extend(parts)
        if len(parts) > 1:
            expanded.append(t)
    return expanded

# NOTE: Changing tokenize_for_bm25 requires a server restart to invalidate this cache
@st.cache_resource
def build_bm25_index():
    """Builds a BM25 index from AEB code descriptions."""
    corpus = []
    for code in CODES:
        text = f"{code[1]} {code[2]}"
        tokens = tokenize_for_bm25(text)
        corpus.append(tokens)
    return BM25Okapi(corpus)

def get_bm25_scores(bm25_index, query_text):
    """Computes BM25 scores for a query against all codes."""
    query_tokens = tokenize_for_bm25(query_text)
    scores = bm25_index.get_scores(query_tokens)
    return scores

def extract_keywords_from_code(code_tuple):
    """Extracts keywords from AEB code description."""
    long_desc = code_tuple[2]
    if "Keywords:" in long_desc:
        keywords_section = long_desc.split("Keywords:")[-1]
        keywords = [kw.strip().lower() for kw in keywords_section.split(",")]
        return [kw for kw in keywords if kw]
    return []

def get_keyword_boost(input_text, code_keywords):
    """Calculates boost score based on keyword matches. Returns 0.0 to 0.5."""
    if not code_keywords:
        return 0.0
    input_lower = input_text.lower()
    matches = sum(1 for kw in code_keywords if kw in input_lower)
    boost = min(matches * 0.1, 0.5)
    return boost

@st.cache_resource
def load_cross_encoder():
    return CrossEncoder(CROSS_ENCODER_MODEL_NAME)

def embed_texts(client, texts, batch_size=500, dimensions=None):
    """Erzeugt Embeddings für eine Liste von Texten in Batches."""
    if not texts:
        return np.array([])

    if dimensions is None:
        dimensions = EMB_DIMENSIONS

    all_embeddings = []
    total = len(texts)

    for i in range(0, total, batch_size):
        batch = texts[i : i + batch_size]
        try:
            api_params = {
                "model": EMB_MODEL,
                "input": batch
            }
            if dimensions:
                api_params["dimensions"] = dimensions

            resp = client.embeddings.create(**api_params)
            batch_embeddings = [e.embedding for e in resp.data]
            all_embeddings.extend(batch_embeddings)

        except Exception as e:
            print(f"Embedding Error in batch {i}-{i+len(batch)}: {e}")
            raise e

    return np.array(all_embeddings)

CACHE_DIR = os.path.join(os.path.dirname(HISTORY_FILE))
CACHE_EMBEDDINGS = os.path.join(CACHE_DIR, "history_embeddings.npy")
CACHE_DF = os.path.join(CACHE_DIR, "history_df.pkl")
CACHE_META = os.path.join(CACHE_DIR, "history_cache_meta.json")

def _compute_history_cache_hash():
    """Compute a version hash from EMB_DIMENSIONS, EMB_MODEL, and history file stats."""
    if not os.path.exists(HISTORY_FILE):
        return None
    stat = os.stat(HISTORY_FILE)
    key = f"{EMB_MODEL}:{EMB_DIMENSIONS}:{stat.st_mtime}:{stat.st_size}"
    return hashlib.sha256(key.encode()).hexdigest()

@st.cache_resource
def load_history_examples(_client):
    """Lädt historische Mappings und berechnet deren Embeddings einmalig.
    Uses a disk cache (.npy + .pkl) to avoid re-embedding 11k+ texts on cold start."""
    if not os.path.exists(HISTORY_FILE):
        return None, None

    try:
        current_hash = _compute_history_cache_hash()

        # Try loading from disk cache
        if (os.path.exists(CACHE_EMBEDDINGS) and os.path.exists(CACHE_DF)
                and os.path.exists(CACHE_META)):
            with open(CACHE_META, "r") as f:
                meta = json.load(f)
            if meta.get("hash") == current_hash:
                hist_vecs = np.load(CACHE_EMBEDDINGS)
                df_hist = pd.read_pickle(CACHE_DF)
                if not df_hist.empty and len(hist_vecs) == len(df_hist):
                    return df_hist, hist_vecs

        # Cache miss — compute from scratch
        df_hist = pd.read_excel(HISTORY_FILE)
        req_cols = ['Description', 'AEB Event Code']
        if not all(c in df_hist.columns for c in req_cols):
            return None, None

        df_hist = df_hist.dropna(subset=['Description', 'AEB Event Code'])

        if df_hist.empty:
            return None, None

        hist_texts = df_hist['Description'].astype(str).tolist()
        hist_vecs = embed_texts(_client, hist_texts, batch_size=500)

        # Save to disk cache
        try:
            np.save(CACHE_EMBEDDINGS, hist_vecs)
            df_hist.to_pickle(CACHE_DF)
            with open(CACHE_META, "w") as f:
                json.dump({"hash": current_hash}, f)
        except Exception as e:
            print(f"Cache save warning: {e}")

        return df_hist, hist_vecs
    except Exception as e:
        print(f"History Loading Error: {e}")
        return None, None

def get_similar_historical_entries(query_vec, df_hist, hist_vecs, top_k=3):
    """
    Findet die ähnlichsten historischen Beispiele für einen Query-Vektor.
    Gibt eine Liste von Dicts zurück: [{'input': str, 'mapped_code': str, 'score': float}, ...]
    """
    if df_hist is None or hist_vecs is None or len(hist_vecs) == 0:
        return []
    
    # Cosine Similarity berechnen
    # query_vec ist (dim,), hist_vecs ist (N, dim)
    sims = cosine_similarity(query_vec.reshape(1, -1), hist_vecs).ravel()
    
    # Top K Indizes
    top_indices = np.argsort(sims)[-top_k:][::-1]
    
    examples = []
    for idx in top_indices:
        row = df_hist.iloc[idx]
        examples.append({
            "input": row['Description'],
            "mapped_code": row['AEB Event Code'],
            "score": sims[idx]
        })
        
    return examples

async def classify_single_row(async_client, row_text, candidates, hist_str, model_name, semaphore):
    async with semaphore:
        cand_str = "\n".join([
            f"- {c['code']} ({c['desc']}) — similarity: {c['score']:.0%}"
            for c in candidates
        ])
        if len(candidates) >= 2:
            gap = candidates[0]['score'] - candidates[1]['score']
            if gap < 0.05:
                cand_str += f"\n\nNote: Top candidates are very close in score (gap: {gap:.1%}). Pay close attention to semantic differences."
        
        system_prompt = "Du bist ein Mapping-Experte. Wähle den passendsten Code aus den Vorschlägen. Nutze die historischen Beispiele als Orientierung für den Stil der Zuordnung."
        
        user_prompt = f"""
        Mappe diesen Input auf einen Standard-Code.
        
        Input: "{row_text}"
        
        Vorschläge (basierend auf Ähnlichkeit):
        {cand_str}
        {hist_str}
        
        Antworte im JSON-Format: {{ "code": "CODE", "reasoning": "Kurze Begründung" }}
        """
        
        try:
            resp = await async_client.responses.create(
                model=model_name,
                instructions=system_prompt,
                input=user_prompt,
                text={"format": {"type": "json_object"}}
            )
            res = json.loads(resp.output_text)
            return res.get("code")
        except Exception as e:
            print(f"LLM Error: {e}")
            return None

async def run_llm_batch_async(api_key, tasks_data, model_name, progress_callback=None):
    """
    tasks_data: List of dicts { 'index': int, 'text': str, 'candidates': list, 'hist_str': str }
    """
    async_client = AsyncOpenAI(api_key=api_key)
    semaphore = asyncio.Semaphore(15) # Max 15 concurrent requests
    
    total = len(tasks_data)
    completed = 0
    
    async def wrapped_classify(item):
        nonlocal completed
        # Task ausführen
        res = await classify_single_row(
            async_client, 
            item['text'], 
            item['candidates'], 
            item['hist_str'], 
            model_name, 
            semaphore
        )
        # Progress updaten
        completed += 1
        if progress_callback:
            # Map progress from 0.7 to 0.99
            p = 0.7 + (0.29 * (completed / total))
            progress_callback(p, f"LLM Batch: {completed}/{total} verarbeitet...")
            
        return res

    tasks = []
    for item in tasks_data:
        tasks.append(wrapped_classify(item))
        
    results = await asyncio.gather(*tasks)
    return results

def run_mapping_step4(client, df, model_name, threshold: float = 0.60, progress_callback=None, config=None):
    if df.empty: return df

    # Merge config with defaults
    default_config = {
        "use_multilingual_ce": True,
        "use_bm25": True,
        "use_keyword_boost": True,
        "embedding_dimensions": EMB_DIMENSIONS,
        "knn_threshold": 0.93,
        "confidence_threshold": 0.60,
        "top_k_prefilter": 10,
        "embedding_weight": 0.7,
        "bm25_weight": 0.3,
    }
    if config:
        default_config.update(config)
    cfg = default_config

    knn_threshold = cfg["knn_threshold"]
    top_k_prefilter = cfg["top_k_prefilter"]
    emb_weight = cfg["embedding_weight"]
    bm25_weight = cfg["bm25_weight"]
    use_bm25 = cfg["use_bm25"]
    use_keyword_boost = cfg["use_keyword_boost"]

    if progress_callback: progress_callback(0.05, "Lade Ressourcen & Embeddings...")

    # Ressourcen laden
    ce_model = load_cross_encoder()
    df_hist, hist_vecs = load_history_examples(client)

    # Textspalte finden
    if "Beschreibung" not in df.columns:
        df["Beschreibung"] = df.iloc[:, -1]

    # 1. Embed Standard Codes
    code_texts = [f"Definition eines internen Sendungsstatus: {c[1]}. Details: {c[2]}" for c in CODES]
    code_vecs = embed_texts(client, code_texts)

    # 1.5. Build BM25 index
    if progress_callback: progress_callback(0.08, "Baue BM25 Index...")
    bm25_index = build_bm25_index()

    # 2. Embed Input (Enhanced Context)
    input_texts = []
    raw_input_texts_for_ce = []

    for _, row in df.iterrows():
        parts = []
        if "Statuscode" in df.columns: parts.append(str(row["Statuscode"]))
        if "Reasoncode" in df.columns: parts.append(str(row["Reasoncode"]))
        parts.append(str(row["Beschreibung"]))

        combined_text = " ".join(parts)
        normalized_text = normalize_input(combined_text)

        input_texts.append(f"Beschreibung eines Sendungsstatus vom Transportdienstleister: {normalized_text}")
        raw_input_texts_for_ce.append(normalized_text)

    q_vecs = embed_texts(client, input_texts)

    # 3. Vectorized cosine similarity (all queries vs all codes at once)
    all_sims = cosine_similarity(q_vecs, code_vecs)  # (N, 31)

    pred_codes = []
    conf_scores = []
    sources = []
    top_candidates_list = []

    # Phase 1: k-NN check + collect CE pairs for non-kNN rows
    non_knn_rows = []  # (row_index_in_df, i_in_q_vecs)
    all_ce_pairs = []  # all cross-encoder pairs across all non-kNN rows
    ce_pair_counts = []  # how many CE pairs per non-kNN row
    top_k_indices_per_row = []  # top_k indices for each non-kNN row

    total_items = len(q_vecs)
    for i, v in enumerate(q_vecs):
        if progress_callback:
            prog = 0.1 + (0.3 * (i / total_items))
            progress_callback(prog, f"Vorfilterung Zeile {i+1}/{total_items}")

        # --- A. k-NN Check (History) ---
        knn_match_found = False
        if df_hist is not None and hist_vecs is not None:
            hist_matches = get_similar_historical_entries(v, df_hist, hist_vecs, top_k=1)
            if hist_matches:
                best_hist = hist_matches[0]
                if best_hist['score'] >= knn_threshold:
                    pred_codes.append(best_hist['mapped_code'])
                    conf_scores.append(float(best_hist['score']))
                    sources.append("history-knn")
                    top_candidates_list.append([])
                    knn_match_found = True

        if knn_match_found:
            continue

        # --- B. Pre-filter with combined scores ---
        sims = all_sims[i]

        if use_bm25:
            bm25_scores = get_bm25_scores(bm25_index, raw_input_texts_for_ce[i])
            bm25_max = bm25_scores.max()
            bm25_normalized = bm25_scores / (bm25_max + 1e-10) if bm25_max > 0 else bm25_scores
            combined_scores = emb_weight * sims + bm25_weight * bm25_normalized
        else:
            combined_scores = sims.copy()

        if use_keyword_boost:
            for idx in range(len(combined_scores)):
                code_keywords = extract_keywords_from_code(CODES[idx])
                keyword_boost = get_keyword_boost(raw_input_texts_for_ce[i], code_keywords)
                combined_scores[idx] *= (1 + keyword_boost)

        top_k_idx = np.argsort(combined_scores)[-top_k_prefilter:][::-1]

        # Collect CE pairs for batched prediction
        ce_pairs_for_row = []
        for idx in top_k_idx:
            code_desc = f"{CODES[idx][1]}. {CODES[idx][2]}"
            ce_pairs_for_row.append([raw_input_texts_for_ce[i], code_desc])

        all_ce_pairs.extend(ce_pairs_for_row)
        ce_pair_counts.append(len(ce_pairs_for_row))
        top_k_indices_per_row.append(top_k_idx)
        non_knn_rows.append(i)

        # Placeholders — will be filled in phase 2
        pred_codes.append(None)
        conf_scores.append(None)
        sources.append(None)
        top_candidates_list.append(None)

    # Phase 2: Batched cross-encoder prediction
    if all_ce_pairs:
        if progress_callback: progress_callback(0.45, f"Cross-Encoder Re-Ranking ({len(all_ce_pairs)} Paare)...")
        # Batch CE predictions in chunks to avoid OOM/segfault on large inputs
        CE_BATCH_SIZE = 2048
        if len(all_ce_pairs) <= CE_BATCH_SIZE:
            all_ce_scores = ce_model.predict(all_ce_pairs)
        else:
            score_chunks = []
            for j in range(0, len(all_ce_pairs), CE_BATCH_SIZE):
                chunk = all_ce_pairs[j:j + CE_BATCH_SIZE]
                score_chunks.append(ce_model.predict(chunk))
            all_ce_scores = np.concatenate(score_chunks)

        # Unpack batched results back to per-row scores
        offset = 0
        for row_idx_in_loop, i in enumerate(non_knn_rows):
            count = ce_pair_counts[row_idx_in_loop]
            ce_scores = all_ce_scores[offset:offset + count]
            top_k_idx = top_k_indices_per_row[row_idx_in_loop]
            offset += count

            sorted_indices_in_top_k = np.argsort(ce_scores)[::-1]

            reranked_indices = [top_k_idx[j] for j in sorted_indices_in_top_k]
            reranked_scores = [ce_scores[j] for j in sorted_indices_in_top_k]

            best_idx = reranked_indices[0]
            best_score = reranked_scores[0]
            second_best_score = reranked_scores[1] if len(reranked_scores) > 1 else -10.0

            gap = max(sigmoid(best_score) - sigmoid(second_best_score), 0.0)
            conf = sigmoid(best_score) * (0.5 + 0.5 * min(gap / 0.15, 1.0))

            # pred_codes[i] == i-th q_vec: every loop iteration appends exactly once
            pred_codes[i] = CODES[best_idx][0]
            conf_scores[i] = conf
            sources[i] = "emb+ce"

            candidates = []
            for j in range(min(3, len(reranked_indices))):
                r_idx = reranked_indices[j]
                candidates.append({
                    "code": CODES[r_idx][0],
                    "desc": CODES[r_idx][1],
                    "score": float(sigmoid(reranked_scores[j]))
                })
            top_candidates_list[i] = candidates

    df["final_code"] = pred_codes
    df["confidence"] = conf_scores
    df["source"] = sources
    
    # 4. LLM Fallback (Async Batch Processing)
    unsure_mask = (df["confidence"] < threshold) & (df["source"] != "history-knn")
    unsure_indices = df[unsure_mask].index
    total_unsure = len(unsure_indices)

    if total_unsure > 0:
        if progress_callback: progress_callback(0.7, f"Starte LLM Batch-Verarbeitung für {total_unsure} Zeilen...")
        
        # Prepare data for batch processing
        tasks_data = []
        for i, idx in enumerate(unsure_indices):
            row_text = df.at[idx, 'Beschreibung']
            pos_idx = df.index.get_loc(idx)
            candidates = top_candidates_list[pos_idx]

            # Few-Shot Context
            current_vec = q_vecs[pos_idx]
            hist_examples = get_similar_historical_entries(current_vec, df_hist, hist_vecs, top_k=3)
            
            hist_str = ""
            if hist_examples:
                hist_lines = [f"- Input '{ex['input']}' wurde gemappt auf '{ex['mapped_code']}'" for ex in hist_examples]
                hist_str = "\nHistorische Beispiele (zur Orientierung):\n" + "\n".join(hist_lines)
            
            tasks_data.append({
                'index': idx, # Store original DF index
                'text': row_text,
                'candidates': candidates,
                'hist_str': hist_str
            })
            
        # Run Async Batch
        try:
            # Extract API Key safely
            api_key = client.api_key
            results = asyncio.run(run_llm_batch_async(api_key, tasks_data, model_name, progress_callback))
            
            # Process Results
            for i, new_code in enumerate(results):
                idx = tasks_data[i]['index']
                if new_code and any(c[0] == new_code for c in CODES):
                    df.at[idx, "final_code"] = new_code
                    df.at[idx, "source"] = "llm-batch"
                    
        except Exception as e:
            print(f"Async Batch Error: {e}")
            # Fallback to nothing or log error
            pass
            
    
    if progress_callback: progress_callback(1.0, "Fertig!")
    return df
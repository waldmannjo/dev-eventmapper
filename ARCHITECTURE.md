# Architecture

Detailed technical reference for the Eventmapper application. For a quick overview, see [CLAUDE.md](CLAUDE.md).

## 4-Step Workflow

The application follows a sequential pipeline where each step produces data for the next:

1. **Step 0 (Upload)**: Extracts text from PDF/Excel/CSV/TXT files -> produces `raw_text`
2. **Step 1 (Analysis)**: LLM analyzes document structure to identify status/reason code tables -> produces `analysis_res` with table candidates
3. **Step 2 (Extraction)**: LLM extracts data from selected tables -> produces `extraction_res` with CSV strings
4. **Step 3 (Merge)**: Combines and cleans extracted data -> produces `df_merged` DataFrame
5. **Step 4 (Mapping)**: Maps codes to AEB standards -> produces `df_final` DataFrame

## Backend Modules

The `backend/` package contains the core logic, organized by workflow step:

| Module | Step | Responsibility |
|--------|------|----------------|
| `loader.py` | 0 | File ingestion (PDF/Excel/CSV parsing) |
| `analyzer.py` | 1 | LLM-based document structure analysis |
| `extractor.py` | 2 | LLM-based table extraction to CSV |
| `merger.py` | 3 | Data cleaning, merging, and AI-powered transformation |
| `mapper.py` | 4 | Hybrid semantic mapping engine |
| `synonyms.py` | 1-2 | Domain vocabulary for identifying status/reason code columns |

## Hybrid Mapping Strategy (Step 4)

The mapper uses a multi-stage approach:

1. **Historical k-NN Matching**: Direct lookup from 11k+ historical mappings (`examples/CES_Umschlüsselungseinträge_all.xlsx`). Threshold: 0.93 cosine similarity.
2. **Semantic Search**: OpenAI `text-embedding-3-large` embeddings (1024 dims) for similarity scoring
3. **BM25 Lexical Scoring**: `rank-bm25` keyword matching, combined 70% embeddings + 30% BM25
4. **Keyword Boost**: Extracts keywords from AEB code descriptions, boosts scores by 10% per match (capped at 50%)
5. **Cross-Encoder Re-Ranking**: Multilingual model (`mmarco-mMiniLMv2-L12-H384-v1`) re-ranks top-10 candidates
6. **LLM Fallback**: GPT model with few-shot retrieval for low-confidence cases (below configurable threshold)

Key optimizations:
- **Batch embedding** (500 texts/batch) to reduce API calls
- **Vectorized cosine similarity**: Single matrix operation `cosine_similarity(q_vecs, code_vecs)` instead of per-row calls
- **Batched cross-encoder**: All CE pairs collected in phase 1, single `predict()` call in phase 2
- **Disk-cached historical embeddings**: `.npy` + `.pkl` files in `examples/` with hash-based invalidation, avoiding re-embedding 11k+ texts on cold start
- **Streamlit caching** (`@st.cache_resource`) as second-level in-memory cache on top of disk cache
- Bilingual code definitions in `codes.py` with extensive keyword anchors

## State Management

The app uses `st.session_state` to persist data across Streamlit reruns:

- `current_step`: Workflow position (0-4)
- `raw_text`: Extracted document text
- `analysis_res`: Structure analysis results (JSON with table candidates)
- `extraction_res`: Extracted CSV strings (mode-dependent: separate or combined)
- `df_merged`: Cleaned DataFrame ready for mapping
- `df_final`: Final mapped results

Each step advances `current_step` only after successful completion. Use `st.rerun()` after state updates to refresh the UI.

## Configuration

### Model Selection (`MODEL_CONFIG` in `app.py`)

The UI allows per-step model selection. Step 4 (mapping) is the most expensive due to batch embeddings. Use cheaper models (e.g., `gpt-5.4-nano`) for steps 1-2 when processing large documents.

### Mapper Settings (`MAPPER_CONFIG` in `app.py`)

```python
MAPPER_CONFIG = {
    "use_multilingual_ce": True,      # Multilingual cross-encoder
    "use_bm25": True,                 # BM25 lexical scoring
    "use_keyword_boost": True,        # Keyword boost feature
    "embedding_dimensions": 1024,     # 1024 or 3072
    "knn_threshold": 0.93,            # k-NN direct match threshold
    "confidence_threshold": 0.60,     # LLM fallback threshold
    "top_k_prefilter": 10,            # Top-K candidates for cross-encoder
    "embedding_weight": 0.7,          # Embedding similarity weight
    "bm25_weight": 0.3,              # BM25 lexical weight
}
```

Passed from `app.py` to `run_mapping_step4(config=MAPPER_CONFIG)`. All thresholds, weights, and feature flags are read from this config inside the mapper — no hardcoded values remain in the matching logic.

## SSL/Proxy Workaround

The application disables SSL verification globally at startup for corporate proxies:

```python
os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"
os.environ["CURL_CA_BUNDLE"] = ""
```

This affects OpenAI API calls and Hugging Face model downloads. **Do not remove** unless testing in an environment with proper SSL certificates. The same workaround is mirrored in `tests/conftest.py`.

## Data Files

| File | Purpose |
|------|---------|
| `codes.py` | 31 AEB event codes with bilingual descriptions and `Keywords:` sections |
| `examples/CES_Umschlüsselungseinträge_all.xlsx` | 11k+ historical mappings for k-NN matching |
| `backend/synonyms.py` | Domain vocabulary lists (`STATUS_SYNONYMS`, `REASON_SYNONYMS_*`) |

## Common Patterns

### Adding a New Synonym
Edit `backend/synonyms.py` and add to the appropriate list. The analyzer uses them in LLM prompts automatically.

### Extending AEB Codes
Add entries to `codes.py`:
```python
("CODE", "Short Name / DE Name",
 "English description with use cases. "
 "Deutsche Beschreibung. "
 "Keywords: en, de, keywords, for, matching.")
```
Keywords significantly improve semantic matching accuracy.

### Modifying Mapping Logic
Entry point: `run_mapping_step4()` in `backend/mapper.py`. Adjust `CROSS_ENCODER_MODEL_NAME`, `EMB_MODEL`, or `EMB_DIMENSIONS` constants at the top of the file.

## Testing

```bash
# Run all tests (22 tests, ~30s)
pytest tests/ -v

# Run integration tests only
pytest tests/test_integration_phase1.py -v -m integration

# Validate accuracy on historical data (requires OPENAI_API_KEY)
python scripts/validate_phase1.py
```

### Debug Mode
Sidebar -> "Test: Mapping direkt" allows direct CSV/Excel upload to skip to Step 3. Useful for iterating on mapping logic without re-running extraction.

## Visual Diagrams

Maintained in `.memory/diagrams/`:
- [Folder Structure](.memory/diagrams/structure.md) - Project directory layout
- [Data Flow](.memory/diagrams/logic.md) - Complete workflow with API interactions
- [Component Relationships](.memory/diagrams/components.md) - Module dependencies
- [UI Workflow](.memory/diagrams/api.md) - Session state management and UI flow

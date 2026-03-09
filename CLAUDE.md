# CLAUDE.md

## Project Overview

**Eventmapper** is a Streamlit application that maps logistics event codes from carrier documents to standardized AEB event codes. Uses OpenAI GPT for document analysis/extraction and a hybrid ML pipeline for semantic mapping.

## Quick Start

```bash
.\venv\Scripts\activate        # Windows (venv required - system Python lacks ML deps)
source venv/bin/activate        # Linux/Mac
streamlit run app.py           # Run the app
pip install -r requirements.txt # Install deps
pytest tests/ -v               # Run tests (22 tests, ~30s)
```

## Key Files

| File | What it does |
|------|-------------|
| `app.py` | Streamlit UI, `MODEL_CONFIG`, `MAPPER_CONFIG` |
| `backend/mapper.py` | Hybrid mapping engine (k-NN -> BM25 -> Cross-Encoder -> LLM) |
| `codes.py` | 31 AEB event codes with bilingual descriptions and keywords |
| `examples/CES_...xlsx` | 11k+ historical mappings for k-NN matching |

## Pipeline (5 steps)

Upload -> LLM Analysis -> LLM Extraction -> Merge/Clean -> **Hybrid Mapping**

Step 4 (mapping) is the core logic. See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Critical Constraints

- **SSL verification is disabled** globally for corporate proxy compatibility. Do not remove.
- **Always use the venv** (`.\venv\Scripts\activate`). System Python lacks `sentence-transformers` etc.
- After changing `EMB_DIMENSIONS`, **delete disk cache** (`examples/history_embeddings.npy`, `history_df.pkl`, `history_cache_meta.json`) and **clear Streamlit cache** to regenerate historical embeddings.

## Git Workflow

- Main branch: `main`. Create feature branches for all changes.
- Never push directly to main.
- Current work: see [HANDOVER.md](HANDOVER.md) for session context.

## Deep Dive References

| Document | Content |
|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full technical architecture, modules, config, data files, common patterns |
| [HANDOVER.md](HANDOVER.md) | Current session state, bugs, decisions, next steps |
| [.memory/diagrams/](.memory/diagrams/) | Visual Mermaid diagrams (folder structure, data flow, components, UI) |
| [docs/phase1-improvements.md](docs/phase1-improvements.md) | Phase 1 feature details, testing, rollback procedures |
| [docs/plans/](docs/plans/) | Design docs and implementation plans |

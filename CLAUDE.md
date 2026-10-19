# CLAUDE.md

## Project Overview

**Eventmapper** is a Streamlit application that maps logistics event codes from carrier documents to standardized AEB event codes. Uses OpenAI GPT for document analysis/extraction and a hybrid ML pipeline for semantic mapping.

## Quick Start

```bash
.\venv\Scripts\activate        # Windows (venv required - system Python lacks ML deps)
source venv/bin/activate        # Linux/Mac
streamlit run app.py           # Run the app
pip install -r requirements.txt # Install deps
pytest tests/ -v               # Run tests (~25s)
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
- When changing OpenAI model IDs, update **all** of: `MODEL_CONFIG` + `PRICING` in `app.py` (same keys), the `model_name` defaults in `backend/{analyzer,extractor,merger}.py`, and tests asserting IDs/prices (`test_cost_tracking.py`, `test_analyzer_extra_instructions.py`).
- **Releases:** run `python scripts/release.py` (dry run) → `--apply`; it derives the bump from Conventional Commits since the last `vX.Y.Z` tag and writes `VERSION` + a draft `CHANGELOG` entry (module level in `app.py`, drives the "What's new?" popover). Curate the draft, release via PR, then tag the merge on `main` (`git tag vX.Y.Z && git push origin vX.Y.Z`) — the tag is the baseline for the next bump.
  - Bump rule: breaking (`type!:` or `BREAKING CHANGE:` footer, e.g. CSV/output format change, removed feature) → major; `feat` → minor; `fix`/`harden`/`ui`/`refactor`/`perf` → patch; `docs`/`test`/`chore`/`ci` → no release. Mark breaking commits explicitly — the script can't infer it.
  - While `VERSION` is still 0.x, cut the next release with `--set 1.0.0`; from then on the rule above applies unchanged.
- **All user-facing text is English**, including `progress_callback` messages in `backend/mapper.py`.

## Testing

- Pure helpers live in `app.py` and are tested by importing from `app` (see `tests/test_app_helpers.py`).
- UI smoke test: `streamlit.testing.v1.AppTest.from_file("app.py")`; enter a dummy key into `at.sidebar.text_input[0]` first, or the app calls `st.stop()` before rendering.

## Git Workflow

- Main branch: `main`. Create feature branches for all changes.
- Never push directly to main.

## Deep Dive References

| Document | Content |
|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full technical architecture, modules, config, data files, common patterns |
| [docs/phase1-improvements.md](docs/phase1-improvements.md) | Phase 1 feature details, testing, rollback procedures |
| [docs/plans/](docs/plans/) | Design docs and implementation plans (per-feature `YYYY-MM-DD-*-design.md` + impl notes) |

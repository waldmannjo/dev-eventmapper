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
venv/bin/python -m pytest tests/ -q   # without an activated venv (bare `python` is not on PATH)
```

## Key Files

| File | What it does |
|------|-------------|
| `app.py` | Streamlit UI, `MODEL_CONFIG`, `MAPPER_CONFIG` |
| `backend/mapper.py` | Hybrid mapping engine (k-NN -> BM25 -> Cross-Encoder -> LLM) |
| `codes.py` | 32 AEB event codes with bilingual descriptions and keywords |
| `examples/CES_...xlsx` | 11k+ historical mappings for k-NN matching |

## Pipeline (5 steps)

Upload -> LLM Analysis -> LLM Extraction -> Merge/Clean -> **Hybrid Mapping**

Step 4 (mapping) is the core logic. See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Critical Constraints

- **SSL verification is disabled** globally for corporate proxy compatibility. Do not remove.
- **Always use the venv** (`.\venv\Scripts\activate`). System Python lacks `sentence-transformers` etc.
- After changing `EMB_DIMENSIONS`, **delete disk cache** (`examples/history_embeddings.npy`, `history_df.pkl`, `history_cache_meta.json`) and **clear Streamlit cache** to regenerate historical embeddings.
- When changing OpenAI model IDs, update **all** of: `MODEL_CONFIG` + `PRICING` in `app.py` (same keys), the `model_name` defaults in `backend/{analyzer,extractor,merger}.py`, and tests asserting IDs/prices (`test_cost_tracking.py`, `test_analyzer_extra_instructions.py`).
- **Releases:** run `python scripts/release.py` (dry run) → `--apply`; it derives the bump from Conventional Commits since the last `vX.Y.Z` tag and writes `VERSION` + a draft `CHANGELOG` entry (module level in `app.py`, drives the "What's new?" popover). Curate the draft, release via PR, then tag the merge on `main` (`git tag vX.Y.Z && git push origin vX.Y.Z`) — the tag is the baseline for the next bump — and run `python scripts/release.py --publish` to create the GitHub release (notes = top `CHANGELOG` entry; needs `gh` auth and the pushed tag).
  - Bump rule: breaking (`type!:` or `BREAKING CHANGE:` footer, e.g. CSV/output format change, removed feature) → major; `feat` → minor; `fix`/`harden`/`ui`/`refactor`/`perf` → patch; `docs`/`test`/`chore`/`ci` → no release. Mark breaking commits explicitly — the script can't infer it.
  - Type commits by effect on the app, not on the repo: dev tooling/scripts → `chore:` (no release), even on a `feat/` branch.
- **All user-facing text is English**, including `progress_callback` messages in `backend/mapper.py`.
- **Step-4 exports:** the plain CSV (`_plain_mapping_csv`, headerless, `;`) feeds a downstream import, so never change its columns; new `df_final` columns go into `EXPLANATION_COLUMNS`. "Download with explanation" must stay a `;` CSV (not .xlsx), with formula defusing (`_defuse_formula`).

## Testing

- Pure helpers live in `app.py` and are tested by importing from `app` (see `tests/test_app_helpers.py`).
- UI smoke test: use the `real_streamlit` fixture (`conftest.py`) for `AppTest.from_file("app.py")`, because `tests/test_cost_tracking.py` replaces `streamlit` in `sys.modules` for the whole session. Enter a dummy key into `at.sidebar.text_input[0]` first, or the app calls `st.stop()` before rendering.
- Step-4 fakes: a fake `CrossEncoder.predict` must return float32 like the real one; `normalize_input` lowercases embedded text, so marker strings in fake embeddings must be lowercase.
- pandas is unpinned: test pandas-3 text-column behaviour with `pd.option_context("future.infer_string", True)`.

## Git Workflow

- Main branch: `main`. Create feature branches for all changes.
- Never push directly to main.
- Merge PRs with `gh pr merge <N> --merge` (merge commits, no squash), then `git branch -d <branch> && git push origin --delete <branch>`.
- Untracked drafts in `docs/` (decks, `*.html`, `*.pptx`) are not part of feature work — stage files explicitly, never `git add -A`.

## Deep Dive References

| Document | Content |
|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full technical architecture, modules, config, data files, common patterns |
| [docs/phase1-improvements.md](docs/phase1-improvements.md) | Phase 1 feature details, testing, rollback procedures |
| [docs/plans/](docs/plans/) | Design docs and implementation plans (per-feature `YYYY-MM-DD-*-design.md` + impl notes) |

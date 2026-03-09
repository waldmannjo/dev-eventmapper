# Cost Transparency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show per-step LLM token usage and estimated USD cost in the Eventmapper sidebar after each step completes.

**Architecture:** Each top-level backend function returns a `(result, raw_usage)` tuple alongside its existing result. `app.py` unpacks these, computes dollar cost via `_make_usage()`, stores in `st.session_state.costs`, and renders a sidebar breakdown section. No new files needed — all changes are in existing files.

**Tech Stack:** Python, Streamlit session state, OpenAI Responses API (`resp.usage.input_tokens` / `resp.usage.output_tokens`), OpenAI Embeddings API (`resp.usage.prompt_tokens`).

---

### Task 1: Add usage mock to conftest + add `_make_usage` to app.py

**Files:**
- Modify: `tests/conftest.py`
- Modify: `app.py`
- Create: `tests/test_cost_tracking.py`

**Step 1: Write the failing test**

Create `tests/test_cost_tracking.py`:

```python
import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch


def test_make_usage_gpt5_nano():
    from app import _make_usage
    result = _make_usage(1_000_000, 0, "gpt-5-nano-2025-08-07")
    assert result["input_tokens"] == 1_000_000
    assert result["output_tokens"] == 0
    assert abs(result["cost_usd"] - 0.05) < 1e-9
    assert result["model"] == "gpt-5-nano-2025-08-07"


def test_make_usage_embedding_no_output():
    from app import _make_usage
    result = _make_usage(500_000, 0, "text-embedding-3-large")
    assert result["output_tokens"] == 0
    expected = 500_000 * 0.13 / 1_000_000
    assert abs(result["cost_usd"] - expected) < 1e-9


def test_make_usage_unknown_model_zero_cost():
    from app import _make_usage
    result = _make_usage(100, 50, "unknown-model-xyz")
    assert result["cost_usd"] == 0.0


def test_make_usage_combined_input_output():
    from app import _make_usage
    # gpt-4.1: input $2/1M, output $8/1M => 2+8 = $10 total
    result = _make_usage(1_000_000, 1_000_000, "gpt-4.1-2025-04-14")
    assert abs(result["cost_usd"] - 10.0) < 1e-9
```

Note: importing `app` in tests works because Streamlit's module-level calls
(`set_page_config`, `title`, etc.) are skipped in test mode. If they cause issues,
mock them in `conftest.py` using `monkeypatch` or add a `conftest.py` fixture.

**Step 2: Run test to verify it fails**

```bash
cd /home/jwa/projects/dev-eventmapper/cost-transparency
source venv/bin/activate
pytest tests/test_cost_tracking.py -v
```

Expected: FAIL — `cannot import name '_make_usage' from 'app'`.

**Step 3: Add `PRICING` and `_make_usage` to `app.py`**

After the `MODEL_CONFIG` dict (around line 43), insert:

```python
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
```

**Step 4: Extend the `mock_openai_client` fixture in `conftest.py`**

The existing mock does not set `mock_response.usage`. Add it so tests for `embed_texts`
do not fail on `.usage.prompt_tokens`. In the `mock_openai_client` fixture, after
setting `mock_response.data`:

```python
mock_usage = Mock()
mock_usage.prompt_tokens = 30
mock_usage.total_tokens = 30
mock_response.usage = mock_usage
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_cost_tracking.py -v
```

Expected: 4 tests PASS.

**Step 6: Run full suite to confirm no regressions**

```bash
pytest tests/ -v --ignore=tests/test_integration_phase1.py -x
```

Expected: all existing tests PASS.

**Step 7: Commit**

```bash
git add tests/test_cost_tracking.py tests/conftest.py app.py
git commit -m "feat: add PRICING table, _make_usage helper, extend mock with usage"
```

---

### Task 2: Modify `backend/analyzer.py` to return raw usage

**Files:**
- Modify: `backend/analyzer.py:95-101`

No existing tests call `analyze_structure_step1` directly — only `app.py` does.

**Step 1: Change the return in `analyze_structure_step1`**

After `client.responses.create(...)` at line 95, capture usage before returning:

```python
    response = client.responses.create(
        model=model_name,
        instructions=system_prompt,
        input=user_prompt,
        text={"format": {"type": "json_object"}}
    )
    raw_usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "model": model_name,
    }
    return json.loads(response.output_text), raw_usage
```

**Step 2: Run full suite to confirm no regressions**

```bash
pytest tests/ -v --ignore=tests/test_integration_phase1.py -x
```

Expected: all PASS (analyzer not called by any test).

**Step 3: Commit**

```bash
git add backend/analyzer.py
git commit -m "feat: analyze_structure_step1 returns (result, raw_usage)"
```

---

### Task 3: Modify `backend/extractor.py` to return raw usage

**Files:**
- Modify: `backend/extractor.py:64-70`

**Step 1: Change the return in `extract_data_step2`**

After `client.responses.create(...)` at line 64, capture usage:

```python
    response = client.responses.create(
        model=model_name,
        instructions=system_prompt,
        input=user_prompt,
        text={"format": {"type": "json_object"}}
    )
    raw_usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "model": model_name,
    }
    return json.loads(response.output_text), raw_usage
```

**Step 2: Run suite**

```bash
pytest tests/ -v --ignore=tests/test_integration_phase1.py -x
```

Expected: all PASS.

**Step 3: Commit**

```bash
git add backend/extractor.py
git commit -m "feat: extract_data_step2 returns (result, raw_usage)"
```

---

### Task 4: Modify `backend/merger.py` — `apply_ai_transformation` to return raw usage

**Files:**
- Modify: `backend/merger.py:128-153`

**Step 1: Capture usage after `responses.create` in the try block**

`apply_ai_transformation` already calls `client.responses.create` and stores the
result in `response`. After the existing `response = client.responses.create(...)` call
(line 129), build a `raw_usage` dict and return it alongside the transformed DataFrame.

In the `try` block, after `return local_vars["df"]`, change to:

```python
        raw_usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": model_name,
        }
        return local_vars["df"], raw_usage
```

In the `except` block, change `return df` to:

```python
        raw_usage = {"input_tokens": 0, "output_tokens": 0, "model": model_name}
        return df, raw_usage
```

**Step 2: Run suite**

```bash
pytest tests/ -v --ignore=tests/test_integration_phase1.py -x
```

Expected: all PASS.

**Step 3: Commit**

```bash
git add backend/merger.py
git commit -m "feat: apply_ai_transformation returns (df, raw_usage)"
```

---

### Task 5: Modify `embed_texts` in `mapper.py` + fix affected tests

This is the most impactful change because `embed_texts` is called directly in 3 test files.

**Files:**
- Modify: `backend/mapper.py:135-164`
- Modify: `tests/test_mapper.py:9`
- Modify: `tests/test_embedding_dimensions.py:16`
- Modify: `tests/test_structured_input_embedding.py:34-46`

**Step 1: Write new failing test for the updated `embed_texts`**

Add to `tests/test_cost_tracking.py`:

```python
def test_embed_texts_returns_tuple(mock_openai_client):
    from backend.mapper import embed_texts
    texts = ["hello", "world"]
    result = embed_texts(mock_openai_client, texts, batch_size=10)
    assert isinstance(result, tuple), "embed_texts must return a 2-tuple"
    embeddings, raw_usage = result
    assert embeddings.shape[0] == 2
    assert raw_usage["model"] == "text-embedding-3-large"
    assert raw_usage["output_tokens"] == 0
    assert raw_usage["input_tokens"] == 30  # matches mock_usage.prompt_tokens
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_cost_tracking.py::test_embed_texts_returns_tuple -v
```

Expected: FAIL — `embed_texts` returns `np.array`, not tuple.

**Step 3: Modify `embed_texts` in `backend/mapper.py`**

Replace lines 135–164 (the entire `embed_texts` function):

```python
def embed_texts(client, texts, batch_size=500, dimensions=None):
    """Generates embeddings for a list of texts in batches.
    Returns (embeddings: np.ndarray, raw_usage: dict)."""
    if not texts:
        return np.array([]), {"input_tokens": 0, "output_tokens": 0, "model": EMB_MODEL}

    if dimensions is None:
        dimensions = EMB_DIMENSIONS

    all_embeddings = []
    total_prompt_tokens = 0
    total = len(texts)

    for i in range(0, total, batch_size):
        batch = texts[i : i + batch_size]
        try:
            api_params = {"model": EMB_MODEL, "input": batch}
            if dimensions:
                api_params["dimensions"] = dimensions

            resp = client.embeddings.create(**api_params)
            batch_embeddings = [e.embedding for e in resp.data]
            all_embeddings.extend(batch_embeddings)
            total_prompt_tokens += resp.usage.prompt_tokens

        except Exception as e:
            print(f"Embedding Error in batch {i}-{i+len(batch)}: {e}")
            raise e

    raw_usage = {
        "input_tokens": total_prompt_tokens,
        "output_tokens": 0,
        "model": EMB_MODEL,
    }
    return np.array(all_embeddings), raw_usage
```

**Step 4: Fix `tests/test_mapper.py`**

Line 9 — unpack the return value:

```python
def test_embed_texts_basic(mock_openai_client, sample_df):
    texts = sample_df['Description'].tolist()
    embeddings, _ = embed_texts(mock_openai_client, texts, batch_size=10)
    assert embeddings.shape[0] == len(texts)
    assert embeddings.shape[1] > 0
```

**Step 5: Fix `tests/test_embedding_dimensions.py`**

Line 16 — unpack the return value:

```python
    embeddings, _ = embed_texts(mock_openai_client, texts, batch_size=10, dimensions=1024)
```

Check the file for any other `embed_texts` call and fix all occurrences.

**Step 6: Fix `tests/test_structured_input_embedding.py` — `fake_embed`**

The `fake_embed` function at line 34 returns `np.random.rand(n, dim)`. After this change,
`run_mapping_step4` will unpack `embed_texts` as a tuple. Update `fake_embed` to return
a tuple:

```python
def fake_embed(client, texts, batch_size=500, dimensions=None):
    call_count[0] += 1
    n = len(texts)
    dim = dimensions or 1024
    raw_usage = {"input_tokens": n * 10, "output_tokens": 0, "model": "text-embedding-3-large"}
    if call_count[0] == 1:
        return np.random.rand(n, dim), raw_usage
    elif call_count[0] == 2:
        captured_input_texts[0] = list(texts)
        return np.random.rand(n, dim), raw_usage
    return np.random.rand(n, dim), raw_usage
```

**Step 7: Run suite to verify all tests pass**

```bash
pytest tests/ -v --ignore=tests/test_integration_phase1.py -x
```

Expected: all PASS including `test_embed_texts_returns_tuple`.

**Step 8: Commit**

```bash
git add backend/mapper.py tests/test_mapper.py tests/test_embedding_dimensions.py tests/test_structured_input_embedding.py tests/test_cost_tracking.py
git commit -m "feat: embed_texts returns (array, raw_usage), fix dependent tests"
```

---

### Task 6: Modify async LLM calls in `mapper.py`

**Files:**
- Modify: `backend/mapper.py:280-358` (functions `classify_single_row`, `run_llm_batch_async`)

**Step 1: Write failing test**

Add to `tests/test_cost_tracking.py`:

```python
import asyncio

def test_run_llm_batch_async_returns_tuple():
    """run_llm_batch_async must return (results, raw_usage)."""
    from backend.mapper import run_llm_batch_async
    from codes import CODES

    mock_usage_obj = Mock()
    mock_usage_obj.input_tokens = 50
    mock_usage_obj.output_tokens = 10

    mock_resp = Mock()
    mock_resp.output_text = '{"code": "' + CODES[0][0] + '", "reasoning": "test"}'
    mock_resp.usage = mock_usage_obj

    async def fake_create(**kwargs):
        return mock_resp

    tasks = [{"index": 0, "text": "test", "candidates": [], "hist_str": ""}]

    with patch("backend.mapper.AsyncOpenAI") as mock_async_cls:
        mock_async_client = Mock()
        mock_async_client.responses.create = fake_create
        mock_async_cls.return_value = mock_async_client

        results, raw_usage = asyncio.run(
            run_llm_batch_async("fake-key", tasks, "gpt-5-nano-2025-08-07")
        )

    assert len(results) == 1
    assert raw_usage["input_tokens"] == 50
    assert raw_usage["output_tokens"] == 10
    assert raw_usage["model"] == "gpt-5-nano-2025-08-07"
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_cost_tracking.py::test_run_llm_batch_async_returns_tuple -v
```

Expected: FAIL — `run_llm_batch_async` currently returns a list, not a tuple.

**Step 3: Modify `classify_single_row`**

Currently returns `code: str | None`. Change to return `(code, raw_usage)`.

In the `try` block, replace `return res.get("code")` with:

```python
            raw_usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "model": model_name,
            }
            return res.get("code"), raw_usage
```

In the `except` block, replace `return None` with:

```python
            return None, {"input_tokens": 0, "output_tokens": 0, "model": model_name}
```

**Step 4: Modify `run_llm_batch_async`**

`wrapped_classify` now gets a `(code, raw_usage)` tuple from `classify_single_row`.
Aggregate usage across all tasks. Replace the `wrapped_classify` function and
`results = await asyncio.gather(*tasks)` block:

```python
    async def wrapped_classify(item):
        nonlocal completed
        code, raw_usage = await classify_single_row(
            async_client,
            item['text'],
            item['candidates'],
            item['hist_str'],
            model_name,
            semaphore
        )
        completed += 1
        if progress_callback:
            elapsed = _time.monotonic() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / rate if rate > 0 else 0
            p = 0.7 + (0.29 * (completed / total))
            progress_callback(
                p,
                f"LLM Batch: {completed}/{total} rows "
                f"({rate:.1f} rows/s, ETA {eta:.0f}s)..."
            )
        return code, raw_usage

    tasks = [wrapped_classify(item) for item in tasks_data]
    pair_results = await asyncio.gather(*tasks)

    results = [code for code, _ in pair_results]
    total_input = sum(u["input_tokens"] for _, u in pair_results)
    total_output = sum(u["output_tokens"] for _, u in pair_results)
    aggregated_usage = {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "model": model_name,
    }
    return results, aggregated_usage
```

**Step 5: Run tests**

```bash
pytest tests/test_cost_tracking.py -v
pytest tests/ -v --ignore=tests/test_integration_phase1.py -x
```

Expected: all PASS.

**Step 6: Commit**

```bash
git add backend/mapper.py tests/test_cost_tracking.py
git commit -m "feat: classify_single_row and run_llm_batch_async return usage"
```

---

### Task 7: Modify `run_mapping_step4` to aggregate and return usage

**Files:**
- Modify: `backend/mapper.py:360-681`
- Modify: `tests/test_integration_phase1.py:102-114`

**Step 1: Write failing test**

Add to `tests/test_cost_tracking.py`:

```python
def test_run_mapping_step4_returns_tuple(mock_openai_client):
    from backend.mapper import run_mapping_step4
    import backend.mapper as mapper_module
    from codes import CODES

    df = pd.DataFrame({
        "Statuscode": ["01"],
        "Reasoncode": ["A"],
        "Description": ["Package arrived at depot"],
    })

    n_codes = len(CODES)

    def fake_embed(client, texts, batch_size=500, dimensions=None):
        n = len(texts)
        raw_usage = {"input_tokens": n * 5, "output_tokens": 0, "model": "text-embedding-3-large"}
        return np.random.rand(n, 1024), raw_usage

    mock_bm25 = Mock()
    mock_bm25.get_scores.return_value = np.random.rand(n_codes)

    with patch.object(mapper_module, "embed_texts", side_effect=fake_embed), \
         patch.object(mapper_module, "load_history_examples", return_value=(None, None)), \
         patch.object(mapper_module, "load_cross_encoder", return_value=Mock(
             predict=lambda pairs: np.random.rand(len(pairs))
         )), \
         patch.object(mapper_module, "build_bm25_index", return_value=mock_bm25):
        result = run_mapping_step4(
            mock_openai_client, df.copy(), model_name="gpt-5-nano-2025-08-07", threshold=0.99
        )

    assert isinstance(result, tuple), "run_mapping_step4 must return (df, step4_usage)"
    result_df, step4_usage = result
    assert "final_code" in result_df.columns
    assert "step4_embed" in step4_usage
    assert step4_usage["step4_embed"]["input_tokens"] > 0
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_cost_tracking.py::test_run_mapping_step4_returns_tuple -v
```

Expected: FAIL.

**Step 3: Update `run_mapping_step4` in `backend/mapper.py`**

Three changes inside `run_mapping_step4`:

**3a.** Initialize `llm_usage = None` before the `if total_unsure > 0:` block.

**3b.** Unpack the two `embed_texts` calls (one for code_texts, one for input_texts)
and accumulate `total_embed_input`:

```python
# Replace:  code_vecs = embed_texts(client, code_texts)
code_vecs, _embed_usage_codes = embed_texts(client, code_texts)
total_embed_input = _embed_usage_codes["input_tokens"]

# Replace:  q_vecs = embed_texts(client, input_texts)
q_vecs, _embed_usage_queries = embed_texts(client, input_texts)
total_embed_input += _embed_usage_queries["input_tokens"]
```

**3c.** Unpack the `asyncio.run(run_llm_batch_async(...))` call:

```python
# Replace:  results = asyncio.run(run_llm_batch_async(...))
results, llm_usage = asyncio.run(run_llm_batch_async(api_key, tasks_data, model_name, progress_callback))
```

**3d.** Replace the final `return df` with:

```python
    step4_usage = {
        "step4_embed": {
            "input_tokens": total_embed_input,
            "output_tokens": 0,
            "model": EMB_MODEL,
        },
        "step4_llm": llm_usage,
    }
    return df, step4_usage
```

**Step 4: Fix `tests/test_integration_phase1.py`**

Line 102 — unpack the tuple:

```python
    with patch("backend.mapper.load_history_examples", return_value=(None, None)):
        result_df, _ = run_mapping_step4(
            mock_client,
            df_input.copy(),
            model_name="gpt-4o-mini",
            threshold=0.0,
        )
```

Also update `_make_embeddings` in that test to include `.usage.prompt_tokens` on the
mock response (so `embed_texts` can read it):

```python
    def _make_embeddings(**kwargs):
        input_texts = kwargs.get("input", [])
        n = len(input_texts) if isinstance(input_texts, list) else 1
        mock_resp = Mock()
        mock_resp.data = []
        for _ in range(n):
            emb = Mock()
            emb.embedding = np.random.rand(3072).tolist()
            mock_resp.data.append(emb)
        mock_usage = Mock()
        mock_usage.prompt_tokens = n * 5
        mock_resp.usage = mock_usage
        return mock_resp
```

**Step 5: Run full suite including integration**

```bash
pytest tests/ -v -x
```

Expected: all PASS.

**Step 6: Commit**

```bash
git add backend/mapper.py tests/test_cost_tracking.py tests/test_integration_phase1.py
git commit -m "feat: run_mapping_step4 returns (df, step4_usage), fix integration test"
```

---

### Task 8: Update `app.py` — session state, call sites, sidebar UI

**Files:**
- Modify: `app.py`

**Step 1: Initialize `costs` in session state**

After the existing state initialization block (around line 154), add:

```python
if "costs" not in st.session_state:
    st.session_state.costs = {}
```

**Step 2: Unpack tuple at Step 1 call site (~line 180)**

```python
res, raw_usage = logic.analyze_structure_step1(client, st.session_state.raw_text, model_name=model_step1)
st.session_state.analysis_res = res
st.session_state.costs["step1_analysis"] = _make_usage(**raw_usage)
```

**Step 3: Unpack tuple at Step 2 call site (~line 271)**

```python
ext_res, raw_usage = logic.extract_data_step2(
    client,
    st.session_state.raw_text,
    selected_stats,
    selected_reas,
    model_name=model_step2
)
st.session_state.extraction_res = ext_res
st.session_state.costs["step2_extraction"] = _make_usage(**raw_usage)
```

**Step 4: Unpack tuple at Step 3 AI transform call site (~line 424)**

```python
new_df, raw_usage = logic.apply_ai_transformation(
    client,
    st.session_state.df_merged,
    user_instruction,
    model_name=model_step3_trans
)
st.session_state.costs["step3_transform"] = _make_usage(**raw_usage)
```

(Leave the rest of the logic in that block unchanged.)

**Step 5: Unpack tuple at Step 4 call site (~line 499)**

```python
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
    if raw is not None:
        st.session_state.costs[key] = _make_usage(**raw)
```

**Step 6: Add `_format_tokens` helper to `app.py`**

Add near `_make_usage`:

```python
def _format_tokens(n: int) -> str:
    """Format token count with 'k' suffix above 999."""
    if n > 999:
        return f"{n / 1000:.1f}k"
    return str(n)
```

**Step 7: Add sidebar cost section**

In the sidebar block, after the Reset button and before the `st.markdown("---")` that
precedes the debug expander, insert:

```python
    if st.session_state.get("costs"):
        st.markdown("---")
        st.markdown("**💰 Session Cost**")

        STEP_LABELS = {
            "step1_analysis":   "Step 1 – Analysis",
            "step2_extraction": "Step 2 – Extraction",
            "step3_transform":  "Step 3 – Transform",
            "step4_embed":      "Step 4 – Embeddings",
            "step4_llm":        "Step 4 – LLM Fallback",
        }

        total_cost = 0.0
        for key, label in STEP_LABELS.items():
            usage = st.session_state.costs.get(key)
            if usage is None:
                continue
            total_cost += usage["cost_usd"]
            inp = _format_tokens(usage["input_tokens"])
            out = _format_tokens(usage["output_tokens"])
            st.caption(
                f"**{label}** &nbsp;&nbsp; `${usage['cost_usd']:.4f}`  \n"
                f"{usage['model']}  ↑{inp} ↓{out} tokens"
            )

        st.markdown(f"**Total: `${total_cost:.4f}`**")
```

**Step 8: Smoke-test the app manually**

```bash
streamlit run app.py
```

Upload a document, run through all steps, verify the sidebar shows cost after each step
and the total accumulates correctly.

**Step 9: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all PASS.

**Step 10: Commit**

```bash
git add app.py
git commit -m "feat: wire cost tracking into app.py sidebar"
```

---

### Task 9: Version bump and changelog

**Files:**
- Modify: `app.py`

**Step 1: Bump VERSION and add changelog entry**

Change `VERSION = "0.4.0"` to `VERSION = "0.5.0"` and prepend to `CHANGELOG`:

```python
"0.5.0": [
    "Cost transparency — sidebar shows token usage and estimated USD cost per step",
],
```

**Step 2: Run full suite one final time**

```bash
pytest tests/ -v
```

Expected: all PASS.

**Step 3: Final commit**

```bash
git add app.py
git commit -m "chore: bump version to 0.5.0, add cost transparency to changelog"
```

# Cost Transparency — Design Document

**Date:** 2026-03-09
**Branch:** cost-transparency
**Status:** Approved

## Overview

Add per-step LLM cost tracking to the Eventmapper sidebar. After each step completes, the sidebar shows the token counts (input/output) and estimated USD cost. A running total is shown at the bottom.

## Pricing Table

Stored in `app.py` as `PRICING` alongside `MODEL_CONFIG`. Prices are per 1M tokens.

```python
PRICING = {
    "gpt-5-nano-2025-08-07":  {"input": 0.05,  "output": 0.40},
    "gpt-5-mini-2025-08-07":  {"input": 0.25,  "output": 2.00},
    "gpt-5.1-2025-11-13":     {"input": 1.25,  "output": 10.00},
    "gpt-4.1-2025-04-14":     {"input": 2.00,  "output": 8.00},
    "text-embedding-3-large": {"input": 0.13,  "output": 0.00},
}
```

Sources: https://developers.openai.com/api/docs/pricing/ (verified 2026-03-09), except
`gpt-5-nano-2025-08-07` which is listed by OpenAI as "gpt-5-nano" but not yet on the
pricing page — price taken from `MODEL_CONFIG`.

## Data Model

### UsageDict shape

```python
{
    "input_tokens": int,
    "output_tokens": int,
    "cost_usd": float,
    "model": str,
}
```

Cost computed as:
```python
cost_usd = (input_tokens * PRICING[model]["input"] +
            output_tokens * PRICING[model]["output"]) / 1_000_000
```

### Session state

```python
st.session_state.costs = {
    "step1_analysis":   UsageDict | None,
    "step2_extraction": UsageDict | None,
    "step3_transform":  UsageDict | None,  # only set when AI transform is used
    "step4_embed":      UsageDict | None,
    "step4_llm":        UsageDict | None,  # only set when LLM fallback runs
}
```

Initialized to `{}` on session start (missing keys = step not yet run).

## Backend Changes

All changes follow the same pattern: capture `response.usage`, compute cost, return a
`UsageDict` alongside the existing result.

### `backend/analyzer.py` — `analyze_structure_step1`

```python
# Before
return result_dict

# After
usage = _make_usage(response.usage.input_tokens, response.usage.output_tokens, model_name)
return result_dict, usage
```

### `backend/extractor.py` — `extract_data_step2`

Same pattern as `analyze_structure_step1`.

### `backend/merger.py` — `apply_ai_transformation`

Same pattern. Only stored when the user actually clicks "Execute".

### `backend/mapper.py` — `embed_texts`

```python
# Before: returns np.ndarray
# After:  returns (np.ndarray, UsageDict)
```

Accumulates `usage.prompt_tokens` across all batches. Model is always
`"text-embedding-3-large"`. Output tokens = 0.

### `backend/mapper.py` — `classify_single_row`

```python
# Before: returns code_str | None
# After:  returns (code_str | None, UsageDict)
```

Captures `resp.usage.input_tokens` / `resp.usage.output_tokens`.

### `backend/mapper.py` — `run_llm_batch_async`

```python
# Before: returns list[code_str | None]
# After:  returns (list[code_str | None], UsageDict)
```

Aggregates usage across all `classify_single_row` results.

### `backend/mapper.py` — `run_mapping_step4`

```python
# Before: returns df
# After:  returns (df, {"step4_embed": UsageDict, "step4_llm": UsageDict | None})
```

`step4_embed` is the sum of all `embed_texts` calls (code vectors + input vectors;
history embedding is cached and not re-billed).
`step4_llm` is `None` when no rows needed LLM fallback.

## Helper Function

Add `_make_usage(input_tokens, output_tokens, model, pricing=PRICING)` to `app.py`:

```python
def _make_usage(input_tokens, output_tokens, model, pricing=PRICING):
    rates = pricing.get(model, {"input": 0.0, "output": 0.0})
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "model": model,
    }
```

Since the backend functions don't have access to `PRICING`, they return raw token counts
and the model name; `app.py` calls `_make_usage` when storing into session state.

**Revised backend return for `classify_single_row` and `embed_texts`:**
Return raw `(result, input_tokens, output_tokens)` — cost calculation stays in `app.py`.

Actually, cleaner: backend functions return `(result, {"input_tokens": N, "output_tokens": M, "model": str})` (no `cost_usd`). The `app.py` enriches with cost via `_make_usage` when storing.

## Sidebar UI

Inserted in `app.py` sidebar, between the Reset button and the Debug expander.

```
💰 Session Cost
─────────────────────────────
Step 1 – Analysis       $0.0012
  gpt-5-nano  ↑123 ↓456 tokens

Step 2 – Extraction     $0.0034
  gpt-5-nano  ↑1.2k ↓890 tokens

Step 3 – Transform      $0.0008
  gpt-5-nano  ↑400 ↓120 tokens

Step 4 – Embeddings     $0.0021
  text-embedding-3-large  ↑16k tokens

Step 4 – LLM Fallback   $0.0156
  gpt-5-nano  ↑8.4k ↓2.1k tokens

─────────────────────────────
Total                   $0.0231
```

Rules:
- Section only renders when `st.session_state.costs` is non-empty
- Steps not yet run are not shown
- Token counts use `k` suffix above 999 (1 decimal place, e.g. `1.2k`)
- ↑ = input tokens, ↓ = output tokens
- Step 4 LLM row hidden when `step4_llm` is `None`

## app.py Call-Site Changes

Each call site unpacks the new tuple and stores the raw usage into session state:

```python
# Step 1
res, raw_usage = logic.analyze_structure_step1(client, ..., model_name=model_step1)
st.session_state.analysis_res = res
st.session_state.costs["step1_analysis"] = _make_usage(**raw_usage)

# Step 4
df_fin, step4_usage = logic.run_mapping_step4(...)
st.session_state.df_final = df_fin
for key, raw in step4_usage.items():
    if raw:
        st.session_state.costs[key] = _make_usage(**raw)
```

## Reset Behavior

`st.session_state.clear()` (existing Reset button) already clears `costs`. No extra work needed.

## Files Changed

| File | Change |
|------|--------|
| `app.py` | Add `PRICING`, `_make_usage`, `costs` session state init, sidebar cost section, unpack tuples at call sites |
| `backend/analyzer.py` | Return `(result, raw_usage)` |
| `backend/extractor.py` | Return `(result, raw_usage)` |
| `backend/merger.py` | Return `(new_df, raw_usage)` |
| `backend/mapper.py` | `embed_texts` → `(array, raw_usage)`, `classify_single_row` → `(code, raw_usage)`, `run_llm_batch_async` → `(results, raw_usage)`, `run_mapping_step4` → `(df, step4_usage)` |

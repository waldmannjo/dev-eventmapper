import sys
import types
import pandas as pd

# Stub streamlit before app is imported so module-level st calls don't fail
_st = types.ModuleType("streamlit")


class _SessionState(dict):
    """Dict subclass that also supports attribute-style access."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)
    def __setattr__(self, key, value):
        self[key] = value
    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)


class _CtxNS:
    """A SimpleNamespace that also works as a context manager."""
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, key): return lambda *a, **kw: _CtxNS()


def _noop(*a, **kw): return None
def _false(*a, **kw): return False
def _empty_str(*a, **kw): return ""
def _ctx(*a, **kw): return _CtxNS()
def _df(*a, **kw): return pd.DataFrame()

_st.set_page_config = _noop
_st.title = _noop
_st.cache_resource = lambda f: f
_st.session_state = _SessionState()
_st.sidebar = _CtxNS()
_st.rerun = _noop
_st.stop = _noop
_st.header = _noop
_st.subheader = _noop
_st.markdown = _noop
_st.caption = _noop
_st.write = _noop
_st.info = _noop
_st.warning = _noop
_st.error = _noop
_st.success = _noop
_st.divider = _noop
_st.button = _false
_st.text_input = _empty_str
_st.selectbox = lambda *a, **kw: kw.get("index", None)
_st.multiselect = lambda *a, **kw: []
_st.slider = lambda *a, **kw: kw.get("value", 0)
_st.file_uploader = lambda *a, **kw: None
_st.download_button = _noop
_st.progress = _noop
_st.expander = _ctx
_st.popover = _ctx
_st.columns = lambda n, **kw: [_CtxNS() for _ in range(n if isinstance(n, int) else len(n))]
_st.data_editor = _df
_st.dataframe = _noop
_st.empty = _ctx
_st.spinner = _ctx
_st.column_config = types.SimpleNamespace(
    TextColumn=lambda *a, **kw: None,
    NumberColumn=lambda *a, **kw: None,
    SelectboxColumn=lambda *a, **kw: None,
    CheckboxColumn=lambda *a, **kw: None,
)
sys.modules["streamlit"] = _st

import pytest
import numpy as np
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


def test_embed_texts_returns_tuple(mock_openai_client):
    from backend.mapper import embed_texts
    texts = ["hello", "world"]
    result = embed_texts(mock_openai_client, texts, batch_size=10)
    assert isinstance(result, tuple), "embed_texts must return a 2-tuple"
    embeddings, raw_usage = result
    assert embeddings.ndim == 2
    assert embeddings.shape[0] > 0
    assert raw_usage["model"] == "text-embedding-3-large"
    assert raw_usage["output_tokens"] == 0
    assert raw_usage["input_tokens"] == 30  # matches mock_usage.prompt_tokens=30 in conftest


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
            mock_openai_client, df.copy(), model_name="gpt-5-nano-2025-08-07", threshold=0.0
        )

    assert isinstance(result, tuple), "run_mapping_step4 must return (df, step4_usage)"
    result_df, step4_usage = result
    assert "final_code" in result_df.columns
    assert "step4_embed" in step4_usage
    assert step4_usage["step4_embed"]["input_tokens"] > 0
    assert "step4_llm" in step4_usage

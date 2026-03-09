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
    assert embeddings.shape[0] == 3  # mock always returns 3 embeddings per call
    assert raw_usage["model"] == "text-embedding-3-large"
    assert raw_usage["output_tokens"] == 0
    assert raw_usage["input_tokens"] == 30  # matches mock_usage.prompt_tokens=30 in conftest

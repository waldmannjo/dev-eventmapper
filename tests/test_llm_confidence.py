"""
Tests for the LLM fallback result handling in run_mapping_step4.

- An LLM-decided row carries the model's own confidence, not the stale
  pre-LLM score of the candidate it rejected.
- A missing or invalid confidence is written as missing, never kept stale.
- A failed LLM call (exception, invalid code, whole-batch failure) is marked
  source="llm-failed" and keeps its pre-LLM code and score.
"""
import json
import zlib
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

import backend.mapper as mapper_module
from backend.mapper import run_mapping_step4
from codes import CODES

LLM_CODE = CODES[5][0]


def _seeded(text):
    return np.random.default_rng(zlib.crc32(text.encode("utf-8")))


def _fake_embed(client, texts, batch_size=500, dimensions=None):
    vecs = np.array([_seeded(t).random(64) for t in texts])
    return vecs, {"input_tokens": len(texts), "output_tokens": 0, "model": "fake-emb"}


def _fake_ce_predict(pairs):
    return np.array([_seeded(q + "|" + d).random() for q, d in pairs])


def _input_df():
    return pd.DataFrame({
        "Statuscode": ["01", "02"],
        "Reasoncode": ["A", "B"],
        "Description": ["Package arrived at depot", "Consignee not at home"],
    })


def _llm_response(payload):
    resp = Mock()
    resp.output_text = json.dumps(payload)
    resp.usage = Mock(input_tokens=10, output_tokens=5)
    return resp


def _run(create=None, async_client_error=None, threshold=1.01):
    """Run step 4 with external dependencies faked.

    threshold=1.01 sends every row to the LLM; threshold=0.0 sends none.
    """
    client = Mock(api_key="test-key")
    mock_bm25 = Mock()
    mock_bm25.get_scores.return_value = np.linspace(0.0, 1.0, len(CODES))

    async_client = Mock()
    async_client.responses.create = create or AsyncMock()
    async_cls = Mock(side_effect=async_client_error, return_value=async_client)

    with patch.object(mapper_module, "embed_texts", side_effect=_fake_embed), \
         patch.object(mapper_module, "load_history_examples", return_value=(None, None)), \
         patch.object(mapper_module, "load_cross_encoder", return_value=Mock(predict=_fake_ce_predict)), \
         patch.object(mapper_module, "build_bm25_index", return_value=mock_bm25), \
         patch.object(mapper_module, "AsyncOpenAI", async_cls):
        df, _ = run_mapping_step4(client, _input_df(), model_name="gpt-test", threshold=threshold)
    return df


@pytest.fixture(scope="module")
def baseline():
    """Pre-LLM result: same fakes, no row sent to the LLM."""
    return _run(threshold=0.0)


def test_baseline_rows_are_emb_ce(baseline):
    # Guards the fixtures: the rows the LLM tests start from are emb+ce rows.
    assert (baseline["source"] == "emb+ce").all()


def test_llm_row_gets_llm_confidence():
    create = AsyncMock(return_value=_llm_response(
        {"code": LLM_CODE, "confidence": 0.85, "reasoning": "r"}
    ))
    df = _run(create)

    assert (df["source"] == "llm-batch").all()
    assert (df["final_code"] == LLM_CODE).all()
    assert (df["confidence"] == 0.85).all()


@pytest.mark.parametrize("payload", [
    {"code": LLM_CODE, "reasoning": "r"},                         # field missing
    {"code": LLM_CODE, "confidence": None, "reasoning": "r"},     # null
    {"code": LLM_CODE, "confidence": "high", "reasoning": "r"},   # not a number
    {"code": LLM_CODE, "confidence": 85, "reasoning": "r"},       # out of range
    {"code": LLM_CODE, "confidence": True, "reasoning": "r"},     # bool is not a score
], ids=["missing", "null", "string", "out-of-range", "bool"])
def test_llm_row_without_valid_confidence_gets_missing(payload):
    df = _run(AsyncMock(return_value=_llm_response(payload)))

    assert (df["source"] == "llm-batch").all()
    assert (df["final_code"] == LLM_CODE).all()
    assert df["confidence"].isna().all()


def _assert_failed_rows_keep_baseline(df, baseline):
    assert (df["source"] == "llm-failed").all()
    assert df["final_code"].tolist() == baseline["final_code"].tolist()
    assert df["confidence"].tolist() == baseline["confidence"].tolist()


def test_llm_call_exception_marks_row_failed(baseline):
    df = _run(AsyncMock(side_effect=TimeoutError("timeout")))
    _assert_failed_rows_keep_baseline(df, baseline)


def test_llm_hallucinated_code_marks_row_failed(baseline):
    create = AsyncMock(return_value=_llm_response(
        {"code": "NOT_A_CODE", "confidence": 0.99, "reasoning": "r"}
    ))
    df = _run(create)
    _assert_failed_rows_keep_baseline(df, baseline)


def test_llm_malformed_json_marks_row_failed(baseline):
    resp = Mock(output_text="not json", usage=Mock(input_tokens=10, output_tokens=5))
    df = _run(AsyncMock(return_value=resp))
    _assert_failed_rows_keep_baseline(df, baseline)


def test_whole_batch_failure_marks_all_unsure_rows_failed(baseline):
    df = _run(async_client_error=RuntimeError("client init failed"))
    _assert_failed_rows_keep_baseline(df, baseline)


def test_mixed_batch_marks_only_failed_rows():
    # First row succeeds, second row's call raises.
    create = AsyncMock(side_effect=[
        _llm_response({"code": LLM_CODE, "confidence": 0.9, "reasoning": "r"}),
        TimeoutError("timeout"),
    ])
    df = _run(create)

    assert df["source"].tolist() == ["llm-batch", "llm-failed"]
    assert df.loc[0, "confidence"] == 0.9

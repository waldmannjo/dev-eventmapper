"""
Explainability columns written by run_mapping_step4 (plan changes 3 and 4):

- needs_review: per-source review rule
    history-knn  consensus vote share below 0.80
    emb+ce       gap between best and second-best sigmoid score below 0.05
    emb          always (cross-encoder skipped)
    llm-batch    always (LLM self-reported confidence does not separate good from bad)
    llm-failed   always
- candidates:  top-3 pre-LLM candidates, one "CODE score" per line
- knn_matches: top-5 history neighbours, one "CODE score input" per line
- reasoning:   the LLM's justification on llm-batch rows

Plus the guard that the plain (headerless) export keeps its column set.
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

DIM = 64
LLM_CODE = CODES[5][0]
HIST_MARKER = "xqzhistoryhit"  # lowercase: normalize_input lowercases the embedded text
HIST_DIRECTION = np.eye(DIM)[0]


def _seeded(text):
    return np.random.default_rng(zlib.crc32(text.encode("utf-8")))


def _fake_embed(client, texts, batch_size=500, dimensions=None):
    # Rows carrying HIST_MARKER embed onto HIST_DIRECTION so they hit the history.
    vecs = np.array([
        HIST_DIRECTION if HIST_MARKER in t else _seeded(t).random(DIM) for t in texts
    ])
    return vecs, {"input_tokens": len(texts), "output_tokens": 0, "model": "fake-emb"}


def _ce_predict_by_query(logits_by_marker):
    """CE fake: the n-th pair of a query gets logits[n] for the first marker in the query."""
    def predict(pairs):
        seen = {}
        out = []
        for q, _doc in pairs:
            rank = seen.get(q, 0)
            seen[q] = rank + 1
            logits = next((v for k, v in logits_by_marker.items() if k in q), [0.0])
            out.append(logits[rank] if rank < len(logits) else -5.0)
        return np.array(out, dtype=np.float32)  # float32 like the real CrossEncoder.predict
    return predict


def _history(codes, sims):
    """History rows whose vectors have the given cosine similarity to HIST_DIRECTION."""
    df_hist = pd.DataFrame({
        "Description": [f"hist input {i}" for i in range(len(codes))],
        "AEB Event Code": codes,
    })
    vecs = []
    for s in sims:
        v = np.zeros(DIM)
        v[0], v[1] = s, np.sqrt(max(1.0 - s * s, 0.0))
        vecs.append(v)
    return df_hist, np.array(vecs)


def _llm_response(payload):
    resp = Mock()
    resp.output_text = json.dumps(payload)
    resp.usage = Mock(input_tokens=10, output_tokens=5)
    return resp


def _run(descriptions, *, threshold=0.0, history=(None, None), ce_logits=None,
         llm_create=None, config=None):
    df = pd.DataFrame({
        "Statuscode": [str(i) for i in range(len(descriptions))],
        "Reasoncode": ["A"] * len(descriptions),
        "Description": descriptions,
    })
    mock_bm25 = Mock()
    mock_bm25.get_scores.return_value = np.linspace(0.0, 1.0, len(CODES))
    ce = Mock(predict=_ce_predict_by_query(ce_logits or {}))

    async_client = Mock()
    async_client.responses.create = llm_create or AsyncMock()

    with patch.object(mapper_module, "embed_texts", side_effect=_fake_embed), \
         patch.object(mapper_module, "load_history_examples", return_value=history), \
         patch.object(mapper_module, "load_cross_encoder", return_value=ce), \
         patch.object(mapper_module, "build_bm25_index", return_value=mock_bm25), \
         patch.object(mapper_module, "AsyncOpenAI", Mock(return_value=async_client)):
        out, _ = run_mapping_step4(
            Mock(api_key="test-key"), df, model_name="gpt-test",
            threshold=threshold, config=config,
        )
    return out


# Wide gap: sigmoid(3)=0.95 vs sigmoid(-5)=0.007. Close gap: sigmoid(3) vs sigmoid(2.99).
CLEAR = {"clearwin": [3.0, -5.0, -5.0]}
CLOSE = {"closecall": [3.0, 2.99, -5.0]}


# --- needs_review -----------------------------------------------------------

def test_knn_unanimous_vote_needs_no_review():
    history = _history(["ARR"] * 5, [1.0] * 5)
    df = _run([HIST_MARKER], history=history)

    assert df.loc[0, "source"] == "history-knn"
    assert df.loc[0, "needs_review"] == False


def test_knn_split_vote_needs_review():
    # 3 x ARR at 1.0, 2 x DEL at 0.95 -> consensus 3/4.9 = 0.61: accepted, but below 0.80
    history = _history(["ARR", "ARR", "ARR", "DEL", "DEL"], [1.0, 1.0, 1.0, 0.95, 0.95])
    df = _run([HIST_MARKER], history=history)

    assert df.loc[0, "source"] == "history-knn"
    assert df.loc[0, "final_code"] == "ARR"
    assert df.loc[0, "needs_review"] == True


def test_emb_ce_clear_winner_needs_no_review():
    df = _run(["clearwin row"], ce_logits=CLEAR)

    assert df.loc[0, "source"] == "emb+ce"
    assert df.loc[0, "needs_review"] == False


def test_emb_ce_close_runner_up_needs_review():
    df = _run(["closecall row"], ce_logits=CLOSE)

    assert df.loc[0, "source"] == "emb+ce"
    assert df.loc[0, "needs_review"] == True


def test_emb_row_always_needs_review():
    df = _run(["clearwin row"], ce_logits=CLEAR, config={"ce_max_pairs": 1})

    assert df.loc[0, "source"] == "emb"
    assert df.loc[0, "needs_review"] == True


@pytest.mark.parametrize("payload", [
    {"code": LLM_CODE, "confidence": 0.95, "reasoning": "r"},
    {"code": LLM_CODE, "confidence": 0.40, "reasoning": "r"},
    {"code": LLM_CODE, "reasoning": "r"},
], ids=["confident", "unsure", "missing"])
def test_llm_batch_row_always_needs_review(payload):
    # LLM self-reported confidence is a review signal only: on a 1,541-row DPD run,
    # rows disagreeing with their status's majority code still scored up to 0.88.
    df = _run(["closecall row"], threshold=1.01, ce_logits=CLOSE,
              llm_create=AsyncMock(return_value=_llm_response(payload)))

    assert df.loc[0, "source"] == "llm-batch"
    assert df.loc[0, "needs_review"] == True


def test_llm_failed_row_needs_review():
    df = _run(["clearwin row"], threshold=1.01, ce_logits=CLEAR,
              llm_create=AsyncMock(side_effect=TimeoutError("timeout")))

    assert df.loc[0, "source"] == "llm-failed"
    assert df.loc[0, "needs_review"] == True


# --- candidates -------------------------------------------------------------

def test_candidates_lists_top3_with_scores():
    df = _run(["clearwin row"], ce_logits=CLEAR)

    lines = df.loc[0, "candidates"].split("\n")
    assert len(lines) == 3
    assert lines[0] == f"{df.loc[0, 'final_code']} 0.95"
    assert [line.split(" ")[1] for line in lines[1:]] == ["0.01", "0.01"]


def test_llm_row_keeps_pre_llm_candidates():
    create = AsyncMock(return_value=_llm_response({"code": LLM_CODE, "confidence": 0.9, "reasoning": "r"}))
    df = _run(["closecall row"], threshold=1.01, ce_logits=CLOSE, llm_create=create)

    lines = df.loc[0, "candidates"].split("\n")
    assert [line.split(" ")[1] for line in lines] == ["0.95", "0.95", "0.01"]


def test_knn_row_has_no_candidates():
    history = _history(["ARR"] * 5, [1.0] * 5)
    df = _run([HIST_MARKER], history=history)

    assert df.loc[0, "candidates"] == ""


# --- knn_matches ------------------------------------------------------------

def test_knn_matches_lists_voting_neighbours():
    history = _history(["ARR", "ARR", "ARR", "DEL", "DEL"], [1.0, 1.0, 1.0, 0.95, 0.95])
    df = _run([HIST_MARKER], history=history)

    lines = df.loc[0, "knn_matches"].split("\n")
    assert len(lines) == 5
    assert sorted(lines[:3]) == ["ARR 1.00 hist input 0", "ARR 1.00 hist input 1", "ARR 1.00 hist input 2"]
    assert sorted(lines[3:]) == ["DEL 0.95 hist input 3", "DEL 0.95 hist input 4"]


def test_non_knn_row_has_no_knn_matches():
    df = _run(["clearwin row"], ce_logits=CLEAR)

    assert df.loc[0, "knn_matches"] == ""


# --- reasoning --------------------------------------------------------------

def test_llm_row_carries_reasoning():
    create = AsyncMock(return_value=_llm_response(
        {"code": LLM_CODE, "confidence": 0.9, "reasoning": "Depot scan means arrival"}
    ))
    df = _run(["closecall row"], threshold=1.01, ce_logits=CLOSE, llm_create=create)

    assert df.loc[0, "reasoning"] == "Depot scan means arrival"


def test_non_llm_row_has_no_reasoning():
    df = _run(["clearwin row"], ce_logits=CLEAR)

    assert df.loc[0, "reasoning"] == ""


# --- plain export keeps its columns -----------------------------------------

def test_plain_export_excludes_explanation_columns():
    from app import _plain_mapping_csv

    display = pd.DataFrame({
        "Event code": ["1"], "Reason code": ["2"], "AEB event code": ["ARR"],
        "Event description": ["Arrived"], "confidence": [0.9], "source": ["emb+ce"],
        "needs_review": [False], "reasoning": [""], "candidates": ["ARR 0.95"], "knn_matches": [""],
    })

    assert _plain_mapping_csv(display).decode("utf-8") == "1;2;ARR;Arrived;0.9;emb+ce\n"


# --- robustness of the LLM result loop --------------------------------------

@pytest.mark.parametrize("reasoning, expected", [
    ({"why": "depot scan"}, '{"why": "depot scan"}'),
    (["a", "b"], '["a", "b"]'),
    (42, "42"),
    (None, ""),
], ids=["object", "list", "number", "null"])
def test_non_text_reasoning_is_stored_as_text(reasoning, expected):
    # json_object mode lets the model send any JSON type. With pandas 3 text columns
    # (future.infer_string), a non-text value in the "" -initialised column raises.
    create = AsyncMock(return_value=_llm_response(
        {"code": LLM_CODE, "confidence": 0.9, "reasoning": reasoning}
    ))
    with pd.option_context("future.infer_string", True):
        df = _run(["closecall row"], threshold=1.01, ce_logits=CLOSE, llm_create=create)

    assert df.loc[0, "source"] == "llm-batch"
    assert df.loc[0, "reasoning"] == expected


def test_one_bad_llm_result_fails_only_its_row():
    baseline = _run(["closecall a", "closecall b"], ce_logits=CLOSE)
    create = AsyncMock(return_value=_llm_response(
        {"code": LLM_CODE, "confidence": 0.9, "reasoning": "r"}
    ))
    real_apply = mapper_module._apply_llm_result
    calls = []

    def flaky_apply(df, idx, result):
        calls.append(idx)
        if len(calls) == 1:
            df.at[idx, "final_code"] = LLM_CODE  # half-written, then fails
            raise TypeError("cannot store value")
        return real_apply(df, idx, result)

    with patch.object(mapper_module, "_apply_llm_result", side_effect=flaky_apply):
        df = _run(["closecall a", "closecall b"], threshold=1.01, ce_logits=CLOSE, llm_create=create)

    assert df["source"].tolist() == ["llm-failed", "llm-batch"]
    # the failed row is rolled back to its pre-LLM state
    assert df.loc[0, "final_code"] == baseline.loc[0, "final_code"]
    assert df.loc[0, "confidence"] == baseline.loc[0, "confidence"]
    assert df.loc[1, "final_code"] == LLM_CODE

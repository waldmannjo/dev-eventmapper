"""
End-to-end integration tests for Phase 1 improvements.
"""

import pytest
import pandas as pd
import numpy as np
import os
from unittest.mock import Mock, patch
from codes import CODES


@pytest.mark.integration
def test_phase1_features_activated():
    """Test that all Phase 1 features are activated."""
    from backend.mapper import (
        CROSS_ENCODER_MODEL_NAME,
        EMB_DIMENSIONS,
        build_bm25_index,
        get_keyword_boost,
        extract_keywords_from_code,
    )

    # Feature 1: Multilingual Cross-Encoder
    assert "mmarco" in CROSS_ENCODER_MODEL_NAME.lower()

    # Feature 2: BM25 available
    bm25_index = build_bm25_index()
    assert bm25_index is not None

    # Feature 3: Keyword boost available
    keywords = extract_keywords_from_code(CODES[0])
    assert isinstance(keywords, list)

    boost = get_keyword_boost("arrival depot", keywords)
    assert isinstance(boost, float)

    # Feature 4: Dimension reduction
    assert EMB_DIMENSIONS == 1024


@pytest.mark.integration
def test_phase1_cost_reduction():
    """Test that embedding dimensions are reduced for cost savings."""
    from backend.mapper import EMB_DIMENSIONS

    assert EMB_DIMENSIONS == 1024
    cost_reduction = 1 - (1024 / 3072)
    assert cost_reduction > 0.65


@pytest.mark.integration
def test_phase1_no_regression():
    """Test that Phase 1 doesn't break existing functionality."""
    from backend.mapper import load_cross_encoder, embed_texts

    # Cross-encoder should load
    ce_model = load_cross_encoder()
    assert ce_model is not None


@pytest.mark.integration
def test_phase1_full_pipeline():
    """Test complete Phase 1 pipeline with all features enabled."""
    from backend.mapper import run_mapping_step4

    df_input = pd.DataFrame(
        {
            "Statuscode": ["01", "02", "03", "04"],
            "Reasoncode": ["A", "B", "C", "D"],
            "Description": [
                "Paket ist im Depot angekommen",
                "Empfaenger nicht angetroffen, Benachrichtigung hinterlegt",
                "Sendung befindet sich in Zollabfertigung",
                "Package arrived at sorting center",
            ],
        }
    )

    # Build a mock client where embeddings.create returns the right number
    # of embedding vectors based on how many inputs are passed.
    mock_client = Mock()
    mock_client.api_key = "test-key"

    def _make_embeddings(**kwargs):
        """Return as many 3072-dim embeddings as input texts."""
        input_texts = kwargs.get("input", [])
        n = len(input_texts) if isinstance(input_texts, list) else 1
        mock_resp = Mock()
        mock_resp.data = []
        for _ in range(n):
            emb = Mock()
            emb.embedding = np.random.rand(3072).tolist()
            mock_resp.data.append(emb)
        return mock_resp

    mock_client.embeddings.create.side_effect = _make_embeddings

    # Use threshold=0.0 so LLM fallback is never triggered (all confidences >= 0)
    # Also patch load_history_examples to skip file loading
    with patch("backend.mapper.load_history_examples", return_value=(None, None)):
        result_df = run_mapping_step4(
            mock_client,
            df_input.copy(),
            model_name="gpt-4o-mini",
            threshold=0.0,
        )

    assert "final_code" in result_df.columns
    assert "confidence" in result_df.columns
    assert "source" in result_df.columns
    assert result_df["final_code"].notna().all()
    assert result_df["confidence"].notna().all()
    assert (result_df["confidence"] >= 0).all()
    assert (result_df["confidence"] <= 1).all()

    valid_codes = [c[0] for c in CODES]
    assert result_df["final_code"].isin(valid_codes).all()

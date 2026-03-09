import pytest
import numpy as np
import pandas as pd
from backend.mapper import embed_texts, load_cross_encoder, CROSS_ENCODER_MODEL_NAME

def test_embed_texts_basic(mock_openai_client, sample_df):
    """Test basic embedding functionality."""
    texts = sample_df['Description'].tolist()
    embeddings, _ = embed_texts(mock_openai_client, texts, batch_size=10)

    assert embeddings.shape[0] == len(texts)
    assert embeddings.shape[1] > 0  # Has embedding dimension

def test_load_cross_encoder():
    """Test cross-encoder model loads without error."""
    model = load_cross_encoder()
    assert model is not None

def test_multilingual_cross_encoder_loads():
    """Test that multilingual cross-encoder loads correctly."""
    # Should be multilingual model
    assert "mmarco" in CROSS_ENCODER_MODEL_NAME.lower() or "multilingual" in CROSS_ENCODER_MODEL_NAME.lower()

    # Model should load
    model = load_cross_encoder()
    assert model is not None

def test_cross_encoder_handles_german_text():
    """Test cross-encoder can score German text pairs."""
    model = load_cross_encoder()

    pairs = [
        ["Paket ist angekommen", "Arrival at depot"],
        ["Empfänger nicht angetroffen", "Consignee absence"]
    ]

    scores = model.predict(pairs)
    assert len(scores) == 2
    assert all(isinstance(s, (float, int, np.floating)) for s in scores)

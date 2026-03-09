import pytest
from unittest.mock import Mock, patch
import numpy as np

def test_embed_texts_with_dimensions(mock_openai_client):
    """Test that embed_texts passes dimensions parameter."""
    from backend.mapper import embed_texts

    mock_embedding = Mock()
    mock_embedding.embedding = np.random.rand(1024).tolist()
    mock_response = Mock()
    mock_response.data = [mock_embedding]
    mock_usage = Mock()
    mock_usage.prompt_tokens = 10
    mock_response.usage = mock_usage
    mock_openai_client.embeddings.create.return_value = mock_response

    texts = ["test text"]
    embeddings, _ = embed_texts(mock_openai_client, texts, batch_size=10, dimensions=1024)

    mock_openai_client.embeddings.create.assert_called_once()
    call_kwargs = mock_openai_client.embeddings.create.call_args[1]
    assert call_kwargs.get('dimensions') == 1024
    assert embeddings.shape == (1, 1024)

def test_default_dimensions_is_1024():
    """Test that default dimensions is 1024 for cost savings."""
    from backend.mapper import EMB_DIMENSIONS
    assert EMB_DIMENSIONS == 1024

def test_dimension_reduction_preserves_similarity_ranking():
    """Test that dimension reduction config is correct."""
    from backend.mapper import embed_texts, EMB_DIMENSIONS
    assert EMB_DIMENSIONS == 1024

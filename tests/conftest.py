import importlib
import sys
import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock

# SSL workaround for corporate proxies (mirrors app.py startup)
os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
try:
    from huggingface_hub import configure_http_backend
    _session = requests.Session()
    _session.verify = False
    configure_http_backend(backend_factory=lambda: _session)
except ImportError:
    pass  # configure_http_backend removed in huggingface_hub >= 1.x

@pytest.fixture
def sample_df():
    """Sample DataFrame mimicking extracted carrier data."""
    return pd.DataFrame({
        'Statuscode': ['01', '02', '03'],
        'Reasoncode': ['A', 'B', 'C'],
        'Description': [
            'Package arrived at depot',
            'Delivery attempted but customer absent',
            'Customs clearance in progress'
        ]
    })

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = Mock()
    client.api_key = "test-key"

    # Mock embeddings.create
    mock_embedding = Mock()
    mock_embedding.embedding = np.random.rand(3072).tolist()

    mock_response = Mock()
    mock_response.data = [mock_embedding] * 3

    mock_usage = Mock()
    mock_usage.prompt_tokens = 30
    mock_usage.total_tokens = 30
    mock_response.usage = mock_usage

    client.embeddings.create.return_value = mock_response
    return client

@pytest.fixture
def codes_sample():
    """Sample of AEB codes for testing."""
    return [
        ("ARR", "Arrival", "Shipment arrived at facility. Keywords: arrival, depot, scan."),
        ("CAS", "Consignee Absence", "Customer not home. Keywords: absent, not available."),
        ("CUS", "Customs", "In customs clearance. Keywords: customs, zoll, clearance.")
    ]


@pytest.fixture
def real_streamlit():
    """test_cost_tracking.py replaces `streamlit` in sys.modules with a stub for the
    rest of the session; swap the real package back in for the duration of this test."""
    saved = {k: v for k, v in sys.modules.items() if k == "streamlit" or k.startswith("streamlit.")}
    stubbed = "streamlit" in sys.modules and getattr(sys.modules["streamlit"], "__file__", None) is None
    if stubbed:
        for k in saved:
            del sys.modules[k]
    yield importlib.import_module("streamlit.testing.v1").AppTest
    if stubbed:
        for k in [k for k in sys.modules if k == "streamlit" or k.startswith("streamlit.")]:
            del sys.modules[k]
        sys.modules.update(saved)

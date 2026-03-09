"""Tests for Task 7: Structured Input Embedding Context (Item 5).

Verifies that input_texts construction in run_mapping_step4 uses:
- Labeled fields: "Status code:", "Reason code:", "Description:"
- Period-space separator (". ") between parts, not plain space (" ")
- English prefix "Carrier shipment event:" (not the old German prefix)
- normalize_input() is still applied to combined_text before the prefix
"""
import pandas as pd
import numpy as np
import pytest
from unittest.mock import Mock, patch


# ---------------------------------------------------------------------------
# Helper: capture the input_texts passed to embed_texts for query rows
# ---------------------------------------------------------------------------

def _capture_input_texts(df):
    """
    Build input_texts exactly as run_mapping_step4 does and return them,
    without executing the rest of the pipeline.

    We patch embed_texts to record its calls, then raise StopIteration after
    the *second* call (code_texts call + input_texts call) to abort execution
    cleanly before the expensive cross-encoder / LLM phases.
    """
    import backend.mapper as mapper_module
    from codes import CODES

    call_count = [0]
    captured_input_texts = [None]

    def fake_embed(client, texts, batch_size=500, dimensions=None):
        call_count[0] += 1
        n = len(texts)
        dim = dimensions or 1024
        raw_usage = {"input_tokens": n * 10, "output_tokens": 0, "model": "text-embedding-3-large"}
        if call_count[0] == 1:
            # First call: code_texts (one per CODES entry).  Return correct shape.
            return np.random.rand(n, dim), raw_usage
        elif call_count[0] == 2:
            # Second call: input_texts (our query rows).  Capture and return.
            captured_input_texts[0] = list(texts)
            return np.random.rand(n, dim), raw_usage
        # Subsequent calls shouldn't happen in unit tests, but just in case:
        return np.random.rand(n, dim), raw_usage

    n_codes = len(CODES)
    mock_bm25 = Mock()
    mock_bm25.get_scores.return_value = np.random.rand(n_codes)

    mock_client = Mock()
    mock_client.api_key = "test-key"

    with patch.object(mapper_module, "embed_texts", side_effect=fake_embed), \
         patch.object(mapper_module, "load_history_examples", return_value=(None, None)), \
         patch.object(mapper_module, "load_cross_encoder", return_value=Mock(
             predict=lambda pairs: np.random.rand(len(pairs))
         )), \
         patch.object(mapper_module, "build_bm25_index", return_value=mock_bm25):
        _result = mapper_module.run_mapping_step4(
            mock_client, df.copy(), model_name="gpt-4o-mini", threshold=0.99
        )

    assert captured_input_texts[0] is not None, "embed_texts was never called for input rows"
    return captured_input_texts[0]


# ---------------------------------------------------------------------------
# Labeled fields
# ---------------------------------------------------------------------------

class TestLabeledFields:
    def test_status_code_label_present(self):
        """'Status code:' prefix appears when Statuscode column is present.
        normalize_input lowercases the combined_text, so the label will be lowercase."""
        df = pd.DataFrame({
            "Statuscode": ["42"],
            "Description": ["Delivered to consignee"],
        })
        texts = _capture_input_texts(df)
        assert len(texts) == 1
        # normalize_input lowercases everything, so check lowercase form
        assert "status code: 42" in texts[0], (
            f"Expected 'status code: 42' in: {texts[0]!r}"
        )

    def test_reason_code_label_present(self):
        """'Reason code:' prefix appears when Reasoncode column is present.
        normalize_input lowercases the combined_text, so the label will be lowercase."""
        df = pd.DataFrame({
            "Reasoncode": ["03"],
            "Description": ["Attempted delivery"],
        })
        texts = _capture_input_texts(df)
        assert len(texts) == 1
        # normalize_input lowercases everything, so check lowercase form
        assert "reason code: 03" in texts[0], (
            f"Expected 'reason code: 03' in: {texts[0]!r}"
        )

    def test_description_label_always_present_no_other_columns(self):
        """'Description:' label is present even when no code columns exist.
        normalize_input lowercases the combined_text, so 'description:' will be lowercase."""
        df = pd.DataFrame({
            "Description": ["Package at sorting centre"],
        })
        texts = _capture_input_texts(df)
        assert len(texts) == 1
        # normalize_input lowercases everything after the prefix
        assert "description: " in texts[0], (
            f"Expected 'description: ' in: {texts[0]!r}"
        )

    def test_description_label_present_with_status_and_reason(self):
        """'Description:' label appears alongside Statuscode and Reasoncode."""
        df = pd.DataFrame({
            "Statuscode": ["10"],
            "Reasoncode": ["A"],
            "Description": ["Customs clearance"],
        })
        texts = _capture_input_texts(df)
        assert "description: " in texts[0], (
            f"Expected 'description: ' in: {texts[0]!r}"
        )

    def test_all_three_labels_when_all_columns_present(self):
        """All three labeled fields appear when all columns are present.
        After normalize_input the combined_text is fully lowercased."""
        df = pd.DataFrame({
            "Statuscode": ["07"],
            "Reasoncode": ["B"],
            "Description": ["Return to sender"],
        })
        texts = _capture_input_texts(df)
        assert "status code: 07" in texts[0]
        assert "reason code: b" in texts[0]
        assert "description: " in texts[0]

    def test_statuscode_absent_when_column_missing(self):
        """'Status code:' does NOT appear when Statuscode column is absent."""
        df = pd.DataFrame({
            "Description": ["In transit"],
        })
        texts = _capture_input_texts(df)
        assert "Status code:" not in texts[0], (
            f"'Status code:' should not appear when column absent: {texts[0]!r}"
        )

    def test_reasoncode_absent_when_column_missing(self):
        """'Reason code:' does NOT appear when Reasoncode column is absent."""
        df = pd.DataFrame({
            "Description": ["In transit"],
        })
        texts = _capture_input_texts(df)
        assert "Reason code:" not in texts[0], (
            f"'Reason code:' should not appear when column absent: {texts[0]!r}"
        )


# ---------------------------------------------------------------------------
# Embedding prefix
# ---------------------------------------------------------------------------

class TestEmbeddingPrefix:
    def test_english_prefix_present(self):
        """'Carrier shipment event:' is the embedding prefix."""
        df = pd.DataFrame({
            "Description": ["Delivered successfully"],
        })
        texts = _capture_input_texts(df)
        assert texts[0].startswith("Carrier shipment event:"), (
            f"Expected 'Carrier shipment event:' prefix, got: {texts[0]!r}"
        )

    def test_german_prefix_absent(self):
        """Old German prefix 'Description eines Sendungsstatus' must NOT appear."""
        df = pd.DataFrame({
            "Description": ["Sendung zugestellt"],
        })
        texts = _capture_input_texts(df)
        assert "Description eines Sendungsstatus" not in texts[0], (
            f"Old German prefix found in: {texts[0]!r}"
        )

    def test_german_prefix_absent_transportdienstleister(self):
        """'Transportdienstleister' fragment from old prefix must NOT appear."""
        df = pd.DataFrame({
            "Statuscode": ["01"],
            "Reasoncode": ["X"],
            "Description": ["Paket angekommen"],
        })
        texts = _capture_input_texts(df)
        assert "Transportdienstleister" not in texts[0], (
            f"Old German prefix fragment 'Transportdienstleister' found in: {texts[0]!r}"
        )


# ---------------------------------------------------------------------------
# Part separator
# ---------------------------------------------------------------------------

class TestPartSeparator:
    def test_period_space_between_status_and_reason(self):
        """Parts are joined with '. ' — period-space appears between status and reason."""
        df = pd.DataFrame({
            "Statuscode": ["99"],
            "Reasoncode": ["Z"],
            "Description": ["In transit"],
        })
        texts = _capture_input_texts(df)
        # After normalization: "status code: 99. reason code: z. description: in transit"
        # Then prefixed: "Carrier shipment event: status code: 99. reason code: ..."
        assert ". reason code:" in texts[0], (
            f"Expected '. reason code:' (period-space), got: {texts[0]!r}"
        )

    def test_period_space_between_reason_and_description(self):
        """Period-space separator appears between reason code and description."""
        df = pd.DataFrame({
            "Statuscode": ["01"],
            "Reasoncode": ["A"],
            "Description": ["Delivered"],
        })
        texts = _capture_input_texts(df)
        assert ". description:" in texts[0], (
            f"Expected '. description:' (period-space), got: {texts[0]!r}"
        )

    def test_no_bare_unlabeled_concatenation(self):
        """Raw code values are NOT concatenated with just a space (old behaviour)."""
        df = pd.DataFrame({
            "Statuscode": ["42"],
            "Reasoncode": ["03"],
            "Description": ["Delivered"],
        })
        texts = _capture_input_texts(df)
        # Old behaviour produced "42 03 Delivered" — bare values space-separated.
        # The new text must NOT contain that bare pattern.
        assert "42 03" not in texts[0], (
            f"Bare unlabeled concatenation '42 03' found in: {texts[0]!r}"
        )


# ---------------------------------------------------------------------------
# normalize_input integration
# ---------------------------------------------------------------------------

class TestNormalizeInputIntegration:
    def test_normalize_lowercases_description(self):
        """normalize_input lowercases the assembled combined_text."""
        df = pd.DataFrame({
            "Description": ["Package ARRIVED"],
        })
        texts = _capture_input_texts(df)
        # The prefix itself is mixed-case; everything after "Carrier shipment event: "
        # should be lowercased by normalize_input.
        payload = texts[0][len("Carrier shipment event: "):]
        assert payload == payload.lower(), (
            f"Payload after prefix should be fully lowercased: {payload!r}"
        )

    def test_normalize_expands_depot_synonym(self):
        """normalize_input expands 'DEPOT' -> 'facility' in the description."""
        df = pd.DataFrame({
            "Description": ["Package arrived at DEPOT"],
        })
        texts = _capture_input_texts(df)
        assert "facility" in texts[0], (
            f"Expected normalize_input to expand 'DEPOT'->'facility' in: {texts[0]!r}"
        )
        assert "depot" not in texts[0], (
            f"'depot' should be normalized away in: {texts[0]!r}"
        )

    def test_normalize_removes_timestamp(self):
        """normalize_input removes ISO-8601 timestamps from the description."""
        df = pd.DataFrame({
            "Description": ["Scan 2026-02-17 14:30:00 at facility"],
        })
        texts = _capture_input_texts(df)
        assert "2026-02-17" not in texts[0], (
            f"Timestamp should be removed by normalize_input in: {texts[0]!r}"
        )

    def test_normalize_applied_to_status_code_field(self):
        """normalize_input lowercases the status code field too."""
        df = pd.DataFrame({
            "Statuscode": ["ABC"],
            "Description": ["test"],
        })
        texts = _capture_input_texts(df)
        assert "status code: abc" in texts[0], (
            f"Expected lowercase 'status code: abc' in: {texts[0]!r}"
        )

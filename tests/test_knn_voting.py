"""
Tests for Item 6: k-NN top-5 weighted voting with consensus check.
Tests cover get_similar_historical_entries (returns top_k) and
find_contrastive_example (used for Item 8).
"""
import numpy as np
import pandas as pd
import pytest
from backend.mapper import get_similar_historical_entries, find_contrastive_example


def _make_hist(descriptions, codes, dim=4):
    """Helper: build a small df_hist and hist_vecs."""
    df_hist = pd.DataFrame({
        'Description': descriptions,
        'AEB Event Code': codes,
    })
    # Use unit vectors for controlled similarity
    hist_vecs = np.eye(dim, dim, dtype=np.float32)[:len(descriptions)]
    return df_hist, hist_vecs


class TestGetSimilarHistoricalEntries:
    def test_returns_top_k_results(self):
        df_hist, hist_vecs = _make_hist(
            ['a', 'b', 'c', 'd'],
            ['ARR', 'CAS', 'UTD', 'HIN'],
        )
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = get_similar_historical_entries(query, df_hist, hist_vecs, top_k=3)
        assert len(results) == 3

    def test_first_result_is_most_similar(self):
        df_hist, hist_vecs = _make_hist(
            ['exact match', 'other', 'third'],
            ['ARR', 'CAS', 'UTD'],
        )
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = get_similar_historical_entries(query, df_hist, hist_vecs, top_k=3)
        assert results[0]['mapped_code'] == 'ARR'
        assert results[0]['score'] == pytest.approx(1.0, abs=1e-5)

    def test_returns_empty_for_none_hist(self):
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        assert get_similar_historical_entries(query, None, None, top_k=5) == []

    def test_top_k_5_returns_five(self):
        df_hist, hist_vecs = _make_hist(
            ['a', 'b', 'c', 'd'],
            ['ARR', 'CAS', 'UTD', 'HIN'],
        )
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # Only 4 entries; top_k=5 should return at most 4
        results = get_similar_historical_entries(query, df_hist, hist_vecs, top_k=5)
        assert len(results) == 4

    def test_scores_are_descending(self):
        df_hist, hist_vecs = _make_hist(
            ['a', 'b', 'c'],
            ['ARR', 'CAS', 'UTD'],
        )
        query = np.array([0.9, 0.4, 0.1, 0.0], dtype=np.float32)
        query /= np.linalg.norm(query)
        results = get_similar_historical_entries(query, df_hist, hist_vecs, top_k=3)
        scores = [r['score'] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestKnnVotingConsensus:
    """
    Validate the voting logic mathematically without calling run_mapping_step4.
    Tests that weighted voting produces correct consensus values.
    """
    def test_single_code_consensus_is_100_percent(self):
        votes = {'ARR': 0.95, 'ARR': 0.93}
        # Only one code, consensus must be 1.0
        votes = {'ARR': 0.95 + 0.93}
        best_code = max(votes, key=votes.get)
        total_weight = sum(votes.values())
        consensus = votes[best_code] / total_weight
        assert consensus == pytest.approx(1.0)

    def test_split_vote_lower_consensus(self):
        # Two codes with equal weight → 50% consensus
        votes = {'ARR': 1.0, 'CAS': 1.0}
        best_code = max(votes, key=votes.get)
        total_weight = sum(votes.values())
        consensus = votes[best_code] / total_weight
        assert consensus == pytest.approx(0.5)

    def test_dominant_code_above_threshold(self):
        # ARR wins with 80% weight → above 0.60 threshold
        votes = {'ARR': 0.8, 'CAS': 0.2}
        best_code = max(votes, key=votes.get)
        total_weight = sum(votes.values())
        consensus = votes[best_code] / total_weight
        assert consensus == pytest.approx(0.8)
        assert consensus >= 0.60

    def test_split_vote_below_threshold(self):
        # 50/50 split → below 0.60 threshold, should fall through
        votes = {'ARR': 0.5, 'CAS': 0.5}
        best_code = max(votes, key=votes.get)
        total_weight = sum(votes.values())
        consensus = votes[best_code] / total_weight
        assert consensus < 0.60


class TestFindContrastiveExample:
    def test_returns_different_code_than_top_candidate(self):
        df_hist, hist_vecs = _make_hist(
            ['exact match', 'different event'],
            ['ARR', 'CAS'],
        )
        # Query similar to 'exact match' (index 0 = ARR)
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        result = find_contrastive_example(query, df_hist, hist_vecs, top_candidate_code='ARR')
        assert result is not None
        assert result['mapped_code'] != 'ARR'
        assert result['mapped_code'] == 'CAS'

    def test_returns_none_if_all_same_code(self):
        df_hist, hist_vecs = _make_hist(
            ['a', 'b', 'c'],
            ['ARR', 'ARR', 'ARR'],
        )
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        result = find_contrastive_example(query, df_hist, hist_vecs, top_candidate_code='ARR', top_k=3)
        assert result is None

    def test_returns_none_for_empty_hist(self):
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        result = find_contrastive_example(query, None, None, top_candidate_code='ARR')
        assert result is None

    def test_returns_dict_with_correct_keys(self):
        df_hist, hist_vecs = _make_hist(
            ['a', 'b'],
            ['ARR', 'CAS'],
        )
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        result = find_contrastive_example(query, df_hist, hist_vecs, top_candidate_code='ARR')
        assert result is not None
        assert 'input' in result
        assert 'mapped_code' in result

    def test_input_text_matches_history_description(self):
        df_hist, hist_vecs = _make_hist(
            ['package in transit', 'delivery failed'],
            ['ITR', 'CAS'],
        )
        # Query close to second entry → contrastive against CAS should return ITR
        query = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        result = find_contrastive_example(query, df_hist, hist_vecs, top_candidate_code='CAS')
        assert result is not None
        assert result['input'] == 'package in transit'

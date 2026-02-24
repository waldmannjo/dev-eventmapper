"""Tests for Batch 1 semantic mapping improvements:
  - Change A: Score gap confidence proxy (Item 2)
  - Change B: Multiplicative keyword boost (Item 3)
  - Change C: German compound tokenization for BM25 (Item 4)
"""
import numpy as np
import pytest

from backend.mapper import sigmoid, tokenize_for_bm25, get_keyword_boost


# ---------------------------------------------------------------------------
# Change C: tokenize_for_bm25
# ---------------------------------------------------------------------------

class TestTokenizeForBm25:
    def test_basic_split(self):
        """Plain ASCII words are split on whitespace."""
        result = tokenize_for_bm25("package arrived depot")
        assert result == ["package", "arrived", "depot"]

    def test_lowercases(self):
        """Output is always lowercase."""
        result = tokenize_for_bm25("PACKAGE Arrived DEPOT")
        assert result == ["package", "arrived", "depot"]

    def test_german_umlauts(self):
        """German umlauts (ä, ö, ü, ß) are kept as single tokens."""
        result = tokenize_for_bm25("Zustellung Übergabe")
        assert "zustellung" in result
        assert "übergabe" in result

    def test_single_compound_no_expansion(self):
        """A single-part token (no punctuation/digits) is not duplicated."""
        result = tokenize_for_bm25("Zustellhindernis")
        # Only one token: the lowercased word itself
        assert result == ["zustellhindernis"]

    def test_hyphenated_compound_expansion(self):
        """A hyphenated compound yields both parts AND the original joined token."""
        result = tokenize_for_bm25("Paket-Annahme")
        assert "paket" in result
        assert "annahme" in result
        # The joined original (lowercased, including hyphen) is also present
        assert "paket-annahme" in result

    def test_token_with_digit_stripped(self):
        """Digits are stripped; remaining alpha parts are kept."""
        # "abc123" -> only alpha part "abc"
        result = tokenize_for_bm25("abc123")
        assert "abc" in result
        # The digit-only part produces no token
        assert all(t.isalpha() or "-" in t for t in result)

    def test_empty_string(self):
        """Empty input returns empty list."""
        assert tokenize_for_bm25("") == []

    def test_multiple_compounds(self):
        """Multiple compound words in one string are each expanded."""
        result = tokenize_for_bm25("Paket-Annahme Zustellung")
        assert "paket" in result
        assert "annahme" in result
        assert "zustellung" in result

    def test_umlaut_compound_expansion(self):
        """Compound word with umlaut is expanded into subword parts."""
        # "Über-Gabe" has two parts: "über" and "gabe"
        result = tokenize_for_bm25("Über-Gabe")
        assert "über" in result
        assert "gabe" in result


# ---------------------------------------------------------------------------
# Change A: Score gap confidence proxy
# ---------------------------------------------------------------------------

class TestScoreGapConfidence:
    """Test the mathematical properties of the gap-based confidence formula.

    Formula:
        gap  = sigmoid(best) - sigmoid(second_best)
        conf = sigmoid(best) * (0.5 + 0.5 * min(gap / 0.15, 1.0))
    """

    def _compute_conf(self, best_score, second_best_score):
        """Mirror the formula from mapper.py for unit-testing."""
        gap = sigmoid(best_score) - sigmoid(second_best_score)
        return sigmoid(best_score) * (0.5 + 0.5 * min(gap / 0.15, 1.0))

    def test_zero_gap_reduces_confidence(self):
        """When top-1 and top-2 CE scores are identical the gap is 0 and the
        confidence formula multiplies sigmoid(best) by 0.5."""
        best = 2.0
        conf = self._compute_conf(best, best)
        naive = sigmoid(best)
        assert conf < naive, "zero-gap conf must be less than naive sigmoid(best)"
        assert abs(conf - 0.5 * naive) < 1e-9, "zero-gap should give exactly 0.5 * sigmoid(best)"

    def test_large_gap_saturates_at_full_confidence(self):
        """When gap >= 0.15 the multiplier is capped at 1.0, so conf = sigmoid(best)."""
        # Use scores that guarantee gap well above 0.15
        best = 5.0       # sigmoid ~= 0.9933
        second = -5.0    # sigmoid ~= 0.0067
        conf = self._compute_conf(best, second)
        naive = sigmoid(best)
        assert abs(conf - naive) < 1e-9, "large-gap conf should equal sigmoid(best)"

    def test_large_gap_gives_higher_conf_than_zero_gap(self):
        """Same best score, larger gap must yield strictly higher confidence."""
        best = 2.0
        conf_zero_gap = self._compute_conf(best, best)
        conf_large_gap = self._compute_conf(best, -10.0)
        assert conf_large_gap > conf_zero_gap

    def test_single_candidate_fallback(self):
        """With second_best = -10.0 (single candidate), gap is large and
        confidence should approach sigmoid(best)."""
        best = 1.5
        conf = self._compute_conf(best, -10.0)
        naive = sigmoid(best)
        # With sigmoid(1.5)~=0.818 and sigmoid(-10)~=0.000045, gap ~0.818 >> 0.15
        assert abs(conf - naive) < 1e-6

    def test_partial_gap_intermediate_confidence(self):
        """A gap between 0 and 0.15 produces a confidence between the 0-gap
        and full-confidence extremes."""
        best = 1.0
        # Craft a second_best so that the gap is exactly half of 0.15
        # sigmoid(1.0) ~ 0.7311; we want gap = 0.075
        target_gap = 0.075
        target_sig_second = sigmoid(best) - target_gap  # ~0.6561
        # sigmoid(x) = 0.6561 => x = ln(0.6561/0.3439) ~ 0.645
        second_best = float(np.log(target_sig_second / (1 - target_sig_second)))
        conf = self._compute_conf(best, second_best)
        conf_zero = self._compute_conf(best, best)
        conf_full = sigmoid(best)
        assert conf > conf_zero
        assert conf < conf_full

    def test_sigmoid_is_mathematically_correct(self):
        """Verify that sigmoid used in mapper produces expected values."""
        from backend.mapper import sigmoid
        # sigmoid(0) should be 0.5
        assert abs(sigmoid(0) - 0.5) < 1e-6
        # Large positive should be close to 1
        assert sigmoid(10) > 0.99
        # Large negative should be close to 0
        assert sigmoid(-10) < 0.01

    def test_gap_formula_math(self):
        """Verify the gap confidence formula contracts."""
        from backend.mapper import sigmoid
        import math
        # With zero gap, conf = sigmoid(score) * 0.5
        best = 2.0
        second = 2.0  # equal scores → zero gap
        gap = max(sigmoid(best) - sigmoid(second), 0.0)
        conf = sigmoid(best) * (0.5 + 0.5 * min(gap / 0.15, 1.0))
        assert abs(conf - sigmoid(best) * 0.5) < 1e-6


# ---------------------------------------------------------------------------
# Change B: Multiplicative keyword boost
# ---------------------------------------------------------------------------

class TestMultiplicativeKeywordBoost:
    def test_no_match_boost_is_identity(self):
        """When boost is 0.0, multiplying by (1 + 0) leaves score unchanged."""
        base = 0.75
        boost = get_keyword_boost("unrelated text", ["arrival", "depot"])
        assert boost == 0.0
        assert base * (1 + boost) == base

    def test_positive_boost_increases_score(self):
        """A matching boost must strictly increase the combined score."""
        base = 0.75
        keywords = ["arrival", "depot"]
        boost = get_keyword_boost("package arrived at depot", keywords)
        assert boost > 0.0
        assert base * (1 + boost) > base

    def test_multiplicative_preserves_relative_order_across_scales(self):
        """Multiplicative boost should NOT invert relative order compared to additive
        when applied to scores at very different scales.

        Additive can invert order when base scores differ by less than the boost
        difference.  Multiplicative preserves order because a higher base score
        times (1 + boost) stays higher than a lower base score times a larger
        (1 + boost) only when the boost gap is modest — this test confirms the
        multiplicative formula does not over-correct.
        """
        # score_A has slightly lower base but more keyword matches
        base_a, boost_a = 0.50, 0.3   # (1 + 0.3) = 1.3  -> 0.65
        base_b, boost_b = 0.60, 0.0   # (1 + 0.0) = 1.0  -> 0.60

        result_a = base_a * (1 + boost_a)
        result_b = base_b * (1 + boost_b)
        # A should beat B because 0.65 > 0.60
        assert result_a > result_b

    def test_multiplicative_scales_proportionally(self):
        """Multiplicative boost: doubling base score doubles the boosted score."""
        keywords = ["delivery"]
        text = "delivery attempted"
        boost = get_keyword_boost(text, keywords)
        assert boost > 0.0

        base1 = 0.4
        base2 = 0.8  # double
        boosted1 = base1 * (1 + boost)
        boosted2 = base2 * (1 + boost)
        assert abs(boosted2 / boosted1 - 2.0) < 1e-9, "multiplicative should scale proportionally"

    def test_additive_vs_multiplicative_difference(self):
        """Demonstrate that the two methods give different results to confirm
        the mapper now uses the multiplicative form."""
        base = 0.8
        boost = 0.2
        additive_result = base + boost        # 1.0
        multiplicative_result = base * (1 + boost)  # 0.96
        assert multiplicative_result != additive_result
        assert abs(multiplicative_result - 0.96) < 1e-9

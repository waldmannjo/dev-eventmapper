"""Tests for Item 7: Score Context in LLM Prompts.

Verifies that classify_single_row formats candidate scores correctly and
appends a close-score note when the gap between top candidates is < 0.05.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json


# ---------------------------------------------------------------------------
# Helper: build candidate dicts mirroring the structure in mapper.py phase 2
# ---------------------------------------------------------------------------

def make_candidates(scores):
    """Build a list of candidate dicts with the shape used by mapper.py.

    Each candidate has 'code', 'desc', and 'score' (float in [0, 1]).
    """
    return [
        {"code": f"CODE{i}", "desc": f"Description {i}", "score": float(s)}
        for i, s in enumerate(scores)
    ]


def build_cand_str(candidates):
    """Mirrors the cand_str construction logic from classify_single_row."""
    cand_str = "\n".join([
        f"- {c['code']} ({c['desc']}) — similarity: {c['score']:.0%}"
        for c in candidates
    ])
    if len(candidates) >= 2:
        gap = candidates[0]['score'] - candidates[1]['score']
        if gap < 0.05:
            cand_str += (
                f"\n\nNote: Top candidates are very close in score "
                f"(gap: {gap:.1%}). Pay close attention to semantic differences."
            )
    return cand_str


# ---------------------------------------------------------------------------
# Tests: candidate string format (scores shown as percentages)
# ---------------------------------------------------------------------------

class TestCandidateStringFormat:
    def test_score_formatted_as_percentage(self):
        """Each candidate line must contain the score as a whole-number percentage."""
        candidates = make_candidates([0.82, 0.75, 0.60])
        cand_str = build_cand_str(candidates)
        assert "82%" in cand_str
        assert "75%" in cand_str
        assert "60%" in cand_str

    def test_score_rounded_to_nearest_percent(self):
        """:.0% rounds to the nearest whole percent (no decimal places)."""
        candidates = make_candidates([0.876])
        cand_str = build_cand_str(candidates)
        # 0.876 formatted as :.0% rounds to 88%
        assert "88%" in cand_str

    def test_similarity_label_present(self):
        """Each candidate line includes the '— similarity:' label."""
        candidates = make_candidates([0.90, 0.80])
        cand_str = build_cand_str(candidates)
        lines = cand_str.split("\n")
        for line in lines[:2]:  # check only candidate lines
            assert "— similarity:" in line

    def test_code_and_desc_still_present(self):
        """Code and description must still appear in the candidate line."""
        candidates = [{"code": "ARR", "desc": "Arrival at depot", "score": 0.91}]
        cand_str = build_cand_str(candidates)
        assert "ARR" in cand_str
        assert "Arrival at depot" in cand_str


# ---------------------------------------------------------------------------
# Tests: close-score note logic
# ---------------------------------------------------------------------------

class TestCloseScoreNote:
    NOTE_FRAGMENT = "Top candidates are very close in score"

    def test_note_added_when_gap_is_zero(self):
        """Gap of 0.0 (< 0.05) must trigger the close-score note."""
        candidates = make_candidates([0.80, 0.80])
        cand_str = build_cand_str(candidates)
        assert self.NOTE_FRAGMENT in cand_str

    def test_note_added_when_gap_just_below_threshold(self):
        """Gap of 0.049 (just under 0.05) must trigger the note."""
        candidates = make_candidates([0.80, 0.751])  # gap = 0.049
        cand_str = build_cand_str(candidates)
        assert self.NOTE_FRAGMENT in cand_str

    def test_note_not_added_when_gap_equals_threshold(self):
        """Gap of exactly 0.05 must NOT trigger the note (strict < 0.05)."""
        candidates = make_candidates([0.80, 0.75])  # gap = 0.05
        cand_str = build_cand_str(candidates)
        assert self.NOTE_FRAGMENT not in cand_str

    def test_note_not_added_when_gap_exceeds_threshold(self):
        """Gap well above 0.05 must NOT trigger the note."""
        candidates = make_candidates([0.90, 0.70])  # gap = 0.20
        cand_str = build_cand_str(candidates)
        assert self.NOTE_FRAGMENT not in cand_str

    def test_note_not_added_for_single_candidate(self):
        """With only one candidate there is no second score, so no note."""
        candidates = make_candidates([0.85])
        cand_str = build_cand_str(candidates)
        assert self.NOTE_FRAGMENT not in cand_str

    def test_note_includes_gap_percentage(self):
        """The note must include the actual gap formatted as a percentage."""
        # gap = 0.80 - 0.762 = 0.038, formatted as :.1% → 3.8%
        candidates = make_candidates([0.80, 0.762])
        cand_str = build_cand_str(candidates)
        assert self.NOTE_FRAGMENT in cand_str
        assert "3.8%" in cand_str

    def test_note_not_added_when_gap_exactly_threshold_float_precision(self):
        """Boundary: 0.80 - 0.75 = 0.05 exactly, note must be absent."""
        s1, s2 = 0.80, 0.75
        gap = s1 - s2
        assert abs(gap - 0.05) < 1e-12, "Pre-condition: gap should be exactly 0.05"
        candidates = make_candidates([s1, s2])
        cand_str = build_cand_str(candidates)
        assert self.NOTE_FRAGMENT not in cand_str


# ---------------------------------------------------------------------------
# Integration smoke-test: classify_single_row uses the updated format
# ---------------------------------------------------------------------------

class TestClassifySingleRowPromptContent:
    """Verify that the actual async function passes the enriched candidate
    string into the LLM prompt (without making real API calls)."""

    def _make_mock_async_client(self, return_code="ARR"):
        """Return an AsyncMock client whose responses.create returns JSON."""
        mock_resp = MagicMock()
        mock_resp.output_text = json.dumps({"code": return_code, "reasoning": "test"})

        mock_responses = MagicMock()
        mock_responses.create = AsyncMock(return_value=mock_resp)

        client = MagicMock()
        client.responses = mock_responses
        return client

    def test_score_appears_in_prompt(self):
        """The LLM prompt must contain the score percentage."""
        from backend.mapper import classify_single_row

        candidates = make_candidates([0.82, 0.70])
        client = self._make_mock_async_client("CODE0")
        semaphore = asyncio.Semaphore(1)

        asyncio.run(classify_single_row(
            client, "some input", candidates, "", "gpt-4o-mini", semaphore
        ))

        # Inspect the prompt that was passed to responses.create
        call_kwargs = client.responses.create.call_args
        prompt_text = call_kwargs.kwargs.get("input", "") or call_kwargs.args[0] if call_kwargs.args else ""
        # The prompt is in the 'input' keyword argument
        input_arg = call_kwargs.kwargs.get("input", "")
        assert "82%" in input_arg

    def test_close_score_note_appears_in_prompt_when_gap_small(self):
        """When gap < 0.05, the close-score note must appear in the LLM input."""
        from backend.mapper import classify_single_row

        candidates = make_candidates([0.80, 0.80])  # gap = 0.0
        client = self._make_mock_async_client("CODE0")
        semaphore = asyncio.Semaphore(1)

        asyncio.run(classify_single_row(
            client, "some input", candidates, "", "gpt-4o-mini", semaphore
        ))

        input_arg = client.responses.create.call_args.kwargs.get("input", "")
        assert "Top candidates are very close in score" in input_arg

    def test_close_score_note_absent_when_gap_large(self):
        """When gap >= 0.05, the close-score note must NOT appear in the LLM input."""
        from backend.mapper import classify_single_row

        candidates = make_candidates([0.90, 0.70])  # gap = 0.20
        client = self._make_mock_async_client("CODE0")
        semaphore = asyncio.Semaphore(1)

        asyncio.run(classify_single_row(
            client, "some input", candidates, "", "gpt-4o-mini", semaphore
        ))

        input_arg = client.responses.create.call_args.kwargs.get("input", "")
        assert "Top candidates are very close in score" not in input_arg

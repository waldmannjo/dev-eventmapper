"""Tests for analyze_structure_step1 extra_instructions injection."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock
from backend.analyzer import analyze_structure_step1


def _make_client(response_text: str) -> MagicMock:
    """Return a mock OpenAI client whose responses.create returns a minimal response."""
    usage = MagicMock(input_tokens=10, output_tokens=5)
    response = MagicMock(output_text=response_text, usage=usage)
    client = MagicMock()
    client.responses.create.return_value = response
    return client


def test_extra_instructions_injected_in_prompt():
    """extra_instructions appear in the prompt before Document:."""
    client = _make_client('{"status_candidates": [], "reason_candidates": []}')
    analyze_structure_step1(client, "doc text", extra_instructions="Focus only on EDIFACT codes.")

    call_args = client.responses.create.call_args
    prompt = call_args.kwargs.get("input") or call_args.args[0]
    assert "# Additional Instructions" in prompt
    assert "Focus only on EDIFACT codes." in prompt
    # Must appear before the document
    assert prompt.index("# Additional Instructions") < prompt.index("doc text")


def test_no_extra_instructions_skips_section():
    """When extra_instructions is empty, the section is not added."""
    client = _make_client('{"status_candidates": [], "reason_candidates": []}')
    analyze_structure_step1(client, "doc text")

    call_args = client.responses.create.call_args
    prompt = call_args.kwargs.get("input") or call_args.args[0]
    assert "# Additional Instructions" not in prompt


def test_whitespace_only_extra_instructions_skipped():
    """Whitespace-only extra_instructions does not add the section."""
    client = _make_client('{"status_candidates": [], "reason_candidates": []}')
    analyze_structure_step1(client, "doc text", extra_instructions="   \n  ")

    call_args = client.responses.create.call_args
    prompt = call_args.kwargs.get("input") or call_args.args[0]
    assert "# Additional Instructions" not in prompt


def test_returns_parsed_json_and_usage():
    """Return value is (dict, usage_dict) regardless of extra_instructions."""
    client = _make_client('{"status_candidates": [{"id": "1", "name": "T1"}], "reason_candidates": []}')
    result, usage = analyze_structure_step1(client, "doc text", extra_instructions="hint")

    assert isinstance(result, dict)
    assert "status_candidates" in result
    assert usage["input_tokens"] == 10
    assert usage["output_tokens"] == 5
    assert usage["model"] == "gpt-4o"

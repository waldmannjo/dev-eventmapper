# Step 1 Extra Instructions Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional free-text field in Step 0 that appends user-defined instructions to the Step 1 analysis prompt, directly before the document content.

**Architecture:** The `analyze_structure_step1` backend function receives an optional `extra_instructions` string and injects it as a `# Additional Instructions` section into the prompt before `Document:`. The UI exposes this via an `st.expander` with an `st.text_area` in Step 0, passing the value via session state.

**Tech Stack:** Python, Streamlit, OpenAI Responses API (`client.responses.create`)

---

## Chunk 1: Backend + Tests + UI

### Task 1: Write failing test for `extra_instructions` parameter

**Files:**
- Create: `tests/test_analyzer_extra_instructions.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /home/jwa/projects/dev-eventmapper && source venv/bin/activate && pytest tests/test_analyzer_extra_instructions.py -v
```

Expected: FAIL — `analyze_structure_step1() got an unexpected keyword argument 'extra_instructions'`

---

### Task 2: Implement `extra_instructions` in `backend/analyzer.py`

**Files:**
- Modify: `backend/analyzer.py`

- [ ] **Step 3: Update `analyze_structure_step1` signature and prompt injection**

Change the function signature from:
```python
def analyze_structure_step1(client, text: str, model_name: str = "gpt-4o"):
```
to:
```python
def analyze_structure_step1(client, text: str, model_name: str = "gpt-4o", extra_instructions: str = ""):
```

Find the end of `user_prompt` (currently the f-string ends with `    Document:\n    {text}\n    `). Refactor the document injection and add the extra instructions block.

Replace the closing lines of the `user_prompt` f-string (currently):
```python
    Document:
    {text}
    """
```

With — end the f-string before the document, then conditionally append:
```python
    """

    if extra_instructions.strip():
        user_prompt += f"\n# Additional Instructions\n{extra_instructions.strip()}\n"
    user_prompt += f"\nDocument:\n{text}"
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /home/jwa/projects/dev-eventmapper && source venv/bin/activate && pytest tests/test_analyzer_extra_instructions.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /home/jwa/projects/dev-eventmapper && source venv/bin/activate && pytest tests/ -v
```

Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_analyzer_extra_instructions.py backend/analyzer.py
git commit -m "feat: add extra_instructions param to analyze_structure_step1"
```

---

### Task 3: Add UI in `app.py`

**Files:**
- Modify: `app.py` (Step 0 section, lines ~269–302)

- [ ] **Step 7: Add the expander and text_area**

In the block `if st.session_state.raw_text:` → `if st.session_state.current_step == 0:`, after the model selector (`st.selectbox`) and **before** the "Continue to Step 1" button, add:

```python
with st.expander("⚙️ Advanced Options (Step 1)"):
    st.text_area(
        "Additional Instructions for Analysis",
        placeholder="e.g. Ignore Table 3. Focus only on EDIFACT scan codes.",
        height=100,
        key="step1_extra_instructions",
    )
```

- [ ] **Step 8: Pass the value to the backend call**

In the `if st.button("Continue to Step 1: Start Structural Analysis"):` block, the call to `logic.analyze_structure_step1` is on line ~279. Update it to pass the extra instructions:

```python
res, raw_usage = logic.analyze_structure_step1(
    client,
    st.session_state.raw_text,
    model_name=model_step1,
    extra_instructions=st.session_state.get("step1_extra_instructions", ""),
)
```

- [ ] **Step 9: Run full test suite**

```bash
cd /home/jwa/projects/dev-eventmapper && source venv/bin/activate && pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add app.py
git commit -m "feat: add Advanced Options expander in Step 0 for extra Step 1 instructions"
```

---

## Notes

- `backend/__init__.py` needs no changes — `analyze_structure_step1` is already exported; Python optional params don't break the existing call sites.
- Session state key `step1_extra_instructions` persists automatically when the user clicks "🔙 Repeat Analysis" (which only sets `current_step = 0`, does not clear session state).
- No validation needed — empty/whitespace is silently ignored in the backend.

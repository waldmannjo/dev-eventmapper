# Design: Additional Instructions for Step 1 Analysis

**Date:** 2026-03-13
**Status:** Approved

## Summary

Allow users to provide additional free-text instructions that supplement the default Step 1 (structural analysis) prompt. The instructions are injected into the prompt directly before the document content.

## Problem

The Step 1 prompt is hardcoded in `backend/analyzer.py`. Users cannot guide the LLM analysis without modifying source code — e.g. to ignore specific tables, focus on particular code types, or hint at document structure.

## Solution

### UI (app.py)

Add an `st.expander("⚙️ Advanced Options (Step 1)")` in Step 0, visible after a document is loaded and before the "Continue to Step 1" button. Contains a single `st.text_area` with:

- Label: "Additional Instructions for Analysis"
- Placeholder: "e.g. Ignore Table 3. Focus only on EDIFACT scan codes."
- Height: ~100px
- Key: `"step1_extra_instructions"` (persists in session_state across "Repeat Analysis")

### Backend (backend/analyzer.py)

`analyze_structure_step1` gains an optional parameter `extra_instructions: str = ""`.

Prompt injection (before document):
```python
if extra_instructions.strip():
    user_prompt += f"\n# Additional Instructions\n{extra_instructions}\n"
user_prompt += f"\nDocument:\n{text}"
```

The document text is moved from the inline f-string to a concatenation to support this cleanly.

### Data Flow

```
Step 0 UI
  → extra_instructions = st.session_state.get("step1_extra_instructions", "")
  → logic.analyze_structure_step1(client, text, model_name, extra_instructions)
  → prompt: [Standard task/instructions] + [# Additional Instructions\n{extra}] + [Document:\n{text}]
```

## Scope

- Step 1 only
- No persistence across browser sessions
- No preset/save system
- No content validation (free text)

## Files Changed

| File | Change |
|------|--------|
| `app.py` | Add expander + text_area in Step 0; pass `extra_instructions` to `logic.analyze_structure_step1` |
| `backend/analyzer.py` | Add `extra_instructions` param; refactor document injection; inject section if non-empty |
| `backend/__init__.py` | Update `analyze_structure_step1` export signature if needed |

# Step 2: Extraction
# Extract status codes and reason codes from the document.

# Configuration
# LLM_MODEL = "gpt-4o"  # Stronger model recommended for analysis


import json
import io
import pandas as pd
from openai import OpenAI

def extract_data_step2(client, text: str, status_scope: list, reason_scope: list, model_name: str = "gpt-4o"):
    """
    Extracts data based on the scope (user selection).
    Prioritizes existing combinations in the text.
    """

    # 1. Format scopes for the prompt
    # If lists are empty, set a placeholder so the prompt is not confused.
    scope_text_status = ", ".join(status_scope) if status_scope else "No specific selection (search generally)"
    scope_text_reason = ", ".join(reason_scope) if reason_scope else "none - leave reasons_csv as an empty string"

    system_prompt = "You are a data extraction assistant. Reply exclusively with valid JSON."

    user_prompt = f"""
    # Task
    Extract status codes and reason codes from the document. Strictly follow the user's selected sources.

    # User Selection (Scope)
    - Use these sources for status codes: {scope_text_status}
    - Use these sources for reason codes: {scope_text_reason}

    # DECISION LOGIC (IMPORTANT):
    Analyze the structure of the selected sources and decide the mode:

    CASE A: COMBINATION FOUND (Mode: "combined")
    - If the selected sources already have status codes and reason codes firmly linked (e.g. a table with columns "Status" and "Reason", or codes like "10-01" where 10 is status and 01 is reason).
    - Or if the user selected the same table for both status and reason and it contains both types of information.
    -> THEN: Extract this exact combination into 'combined_csv'.

    CASE B: SEPARATE LISTS (Mode: "separate")
    - If the selected sources for status and reason are structurally separate (e.g. "Table 8" only status, "Table 12" only reasons).
    - And there is no logical link in the text.
    -> THEN: Extract status codes into 'status_csv' and reason codes into 'reasons_csv'.

    # Output JSON Format
    {{
      "mode": "combined" OR "separate",
      "combined_csv": "Statuscode;Reasoncode;Description",  // Only fill if mode=combined
      "status_csv": "Statuscode;Description",               // Only fill if mode=separate
      "reasons_csv": "Reasoncode;Description"               // Only fill if mode=separate
    }}

    # Formatting Rules
    - Separator: semicolon (;)
    - Include headers in the CSV strings.
    - If column names are missing from the text, use generic names (Code;Description).

    Document:
    {text}
    """

    response = client.responses.create(
        model=model_name,
        instructions=system_prompt,
        input=user_prompt,
        text={"format": {"type": "json_object"}}
    )
    raw_usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "model": model_name,
    }
    return json.loads(response.output_text), raw_usage

def preview_csv_string(csv_str):
    """Helper function: converts CSV string to DataFrame for preview."""
    if not csv_str or len(csv_str) < 5:
        return pd.DataFrame()
    try:
        return pd.read_csv(io.StringIO(csv_str), sep=None, engine='python', on_bad_lines='skip')
    except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as e:
        print(f"CSV Preview Error: {e}")
        return pd.DataFrame()

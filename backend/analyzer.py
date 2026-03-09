# Step 1: Structural Analysis
# Analyze the document for status codes and reason codes.

# Configuration
# LLM_MODEL = "gpt-4.1-2025-04-14" # "gpt-4o"  # Stronger model recommended for analysis

import json
from backend.synonyms import (
    STATUS_SYNONYMS,
    REASON_SYNONYMS_CLASSIC,
    REASON_SYNONYMS_CONTEXT,
    REASON_SYNONYMS_COLUMNS
)

def analyze_structure_step1(client, text: str, model_name: str = "gpt-4o"):
    system_prompt = "You are a data analysis expert. Reply exclusively with valid JSON."

    # Prepare synonym lists for the prompt
    status_synonyms_str = ", ".join(STATUS_SYNONYMS)
    reason_classic_str = ", ".join(REASON_SYNONYMS_CLASSIC)
    reason_context_str = ", ".join(REASON_SYNONYMS_CONTEXT)
    reason_columns_str = ", ".join(REASON_SYNONYMS_COLUMNS)

    user_prompt = f"""
    # Task
    Analyze the document (PDF/XLSX) and identify ALL potential sources for status codes and reason codes.
    There may be multiple tables, sets, code lists, field descriptions, or columns containing codes.

    # Goal
    Create a complete list of candidates:
    - status_candidates: all locations where status codes/event codes/scan types/events etc. are defined or listed as a column
    - reason_candidates: all locations where additional/reason/qualifier/error/sub-status codes or supplementary information are listed

    # Terms & Synonyms (IMPORTANT)
    ## Status Codes (Status)
    - {status_synonyms_str}
    ## Reason Codes (Reason/Additional)
    1) Classic:
    - {reason_classic_str}
    2) In the context of "additional information" (even if not numeric!):
    - {reason_context_str}
    3) Field/column names that often mean reason:
    - {reason_columns_str}

    # Procedure (strict)
    1) Recognize document structure:
    - PDF: chapters/sections, tables ("Table 8"), lists, "Set X", headings, field descriptions, examples.
    - XLSX: worksheets, table ranges, column headers, possibly filter/lists.
    2) Collect candidates (broadly, better too many than too few):
    - Status candidates: wherever a list/mapping of events/scan types/status codes exists OR a column contains such codes.
    - Reason candidates: wherever additional/reason/qualifier codes or supplementary info exist OR a column/structure contains additional/detail/info as a qualifier to a status.
    3) For compound codes:
    - If a set/status code + additional/qualifier together carry a meaning (e.g. "SE" + "Additional"), then:
        - SE/Status -> status_candidates
        - Additional/Qualifier -> reason_candidates
    4) Do NOT overlook examples & field definitions:
    - If the document contains field descriptions like:
        - "Scan type", "Event", "Status", "Shipment Event", "LSP Status code" => Status
        - "Codes", "Additional codes", "Additional code", "Code", "codelist/code", "Additional", "Info", "Detail" => Reason
    - Even without a dedicated code table: a column/field can still be a source.
    5) Deduplicate results:
    - Multiple mentions of the same source (e.g. same table once in table of contents, once in the chapter) list only once.
    6) If there are truly no reason codes:
    - reason_candidates must be an empty array []. (No text like "none".)

    # Output JSON Format (exactly this schema)
    {{
    "status_candidates": [
        {{ "id": "1", "name": "...", "description": "...", "context": "..." }}
    ],
    "reason_candidates": [
        {{ "id": "1", "name": "...", "description": "...", "context": "..." }}
    ]
    }}

    # Requirements for the fields
    - id: sequential as string ("1","2",...)
    - name:
    - PDF: "Table 8 – DPD Scan Types", "Set 1: Delivery", "Chapter 6.2 Record Structure" etc.
    - XLSX: "Sheet: Status Codes ASL / Column: EDIFACT Shipment Event"
    - context: precise location
    - PDF: "Page X, Chapter Y.Z, Heading ...", possibly "Table N"
    - XLSX: "Worksheet <Name>, Column <Name>", optional range if recognizable
    - description: 1–2 sentences why this is a status or reason source (e.g. "contains scan type codes 01..27 with description" / "contains additional code list (qualifier) for scanning")

    # Quality Checks (briefly verify before output)
    - Have I captured both tabular code lists and field/column sources?
    - Have I correctly split set structures (SE + Additional) into status vs. reason?
    - Are reason_candidates truly [] when nothing was found?

    Document:
    {text}
    """

    response = client.responses.create(
        model=model_name,
        instructions=system_prompt,
        input=user_prompt,
        text={"format": {"type": "json_object"}}
    )
    return json.loads(response.output_text)

# Schritt 3: Merge
# Merge der extrahierten Daten.

import pandas as pd
import numpy as np
from .extractor import preview_csv_string

def merge_data_step3(extraction_result):
    mode = extraction_result.get("mode")
    
    # FALL A: Bereits kombinierte Liste (Combined Mode)
    if mode == "combined":
        csv_data = extraction_result.get("combined_csv", "")
        df = preview_csv_string(csv_data)
        if not df.empty:
            # Cleanup Spaltennamen
            df.columns = [c.strip() for c in df.columns]
            # Safety check: if "Description" column is missing, use the last column
            if "Description" not in df.columns:
                df["Description"] = df.iloc[:, -1]
        return df

    # FALL B: Getrennte Listen (Separate Mode)
    else:
        status_csv = extraction_result.get("status_csv", "")
        reasons_csv = extraction_result.get("reasons_csv", "")
        
        df_status = preview_csv_string(status_csv)
        df_reasons = preview_csv_string(reasons_csv)
        
        # --- SMART CHECK: Are there real reason codes? ---
        has_real_reasons = False

        if not df_reasons.empty:
            # Check the first row for typical AI "empty" phrases
            first_code = str(df_reasons.iloc[0, 0]).strip().lower()

            # If there is more than one column, also check the description
            first_desc = ""
            if df_reasons.shape[1] > 1:
                first_desc = str(df_reasons.iloc[0, 1]).strip().lower()

            invalid_keywords = ["nicht vorhanden", "keine", "none", "n/a", "not available", "no codes"]

            # Only if NO invalid keyword is found, reasons are considered real
            is_dummy_code = any(k == first_code for k in invalid_keywords)  # Exact match or very close
            is_dummy_desc = any(k in first_desc for k in invalid_keywords)  # Substring match
            
            if not is_dummy_code and not is_dummy_desc:
                has_real_reasons = True

        # --- MERGE LOGIC ---
        if has_real_reasons and not df_status.empty:
            # Cross join (every status with every reason)
            df_status['key'] = 1
            df_reasons['key'] = 1
            df_combined = pd.merge(df_status, df_reasons, on='key').drop("key", axis=1)

            # Normalize columns (we expect 4 relevant columns after merge)
            # Structure now: [StatusCol1, StatusCol2, ReasonCol1, ReasonCol2]
            cols = df_combined.columns.tolist()

            # Assumption: col 0=Status, col 1=StatusDesc, col 2=Reason, col 3=ReasonDesc
            # Rename generically to avoid errors
            if len(cols) >= 4:
                df_combined.columns = ["Statuscode", "StatusDesc", "Reasoncode", "ReasonDesc"] + cols[4:]
                
                # Combine description: "StatusText - ReasonText"
                df_combined["Description"] = df_combined["StatusDesc"].astype(str) + " - " + df_combined["ReasonDesc"].astype(str)

                return df_combined[["Statuscode", "Reasoncode", "Description"]]
            
            # Fallback if column structure is unexpected
            return df_combined

        # --- FALLBACK: STATUS ONLY (when no real reasons are present) ---
        elif not df_status.empty:
            # We expect: col 0 = Code, col 1 = Description
            # If only 1 column exists, duplicate it
            if df_status.shape[1] == 1:
                df_status.columns = ["Statuscode"]
                df_status["Description"] = df_status["Statuscode"]
            else:
                # Take the first two columns
                df_status = df_status.iloc[:, :2]
                df_status.columns = ["Statuscode", "Description"]

            # Explicitly leave Reasoncode empty (NOT "not available")
            df_status["Reasoncode"] = ""

            return df_status[["Statuscode", "Reasoncode", "Description"]]
            
    return pd.DataFrame()

def apply_ai_transformation(client, df: pd.DataFrame, instruction: str, model_name: str = "gpt-4o") -> pd.DataFrame:
    """
    Passt den DataFrame basierend auf einer Nutzeranweisung per LLM an.
    """
    # Provide the AI with column and data type information
    col_info = df.dtypes.to_string()
    sample_data = df.head(3).to_string()

    system_prompt = "You are a Python Pandas expert. Reply ONLY with executable Python code. No Markdown, no explanations."

    user_prompt = f"""
    Given a Pandas DataFrame `df`.

    Columns and types:
    {col_info}

    Sample data:
    {sample_data}

    TASK:
    Manipulate `df` based on this instruction: "{instruction}"

    RULES:
    1. The code must operate directly on the variable `df`.
    2. You may overwrite columns or add new ones.
    3. Consider data types (convert to str if needed).
    4. Return ONLY the Python code, no ``` blocks.
    5. Assume `df` is already imported.

    Example input: "Concatenate column 'A' and 'B'"
    Example output: df['A'] = df['A'].astype(str) + df['B'].astype(str)
    """

    try:
        response = client.responses.create(
        model=model_name,  # z.B. "gpt-5.1-2025-11-13"
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        # Optional bei GPT-5.*:
        # reasoning={"effort": "none"},  # "none" | "low" | "medium" | "high"
        )

        # Text aus der Responses API extrahieren
        code = (response.output_text or "").strip()
        
        # Remove Markdown code blocks in case the AI includes them anyway
        code = code.replace("```python", "").replace("```", "").strip()
        
        # --- WARNING: EXEC IS POTENTIALLY DANGEROUS ---
        # In einer lokalen App/Prototyp okay. In Produktion Sandbox verwenden!
        local_vars = {"df": df.copy(), "pd": pd, "np": np}
        exec(code, {}, local_vars)
        
        return local_vars["df"]
        
    except Exception as e:
        print(f"Error during transformation: {e}")
        return df  # Return original on error
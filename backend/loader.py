import io
import json
import requests
import pandas as pd

def extract_text_from_file(uploaded_file):
    """Reads text from PDF, XLSX, CSV, TXT. For Excel, reads ALL sheets."""
    filename = uploaded_file.name
    text = ""
    
    try:
        if filename.endswith('.pdf'):
            from pypdf import PdfReader
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
                
        elif filename.endswith('.xlsx'):
            # sheet_name=None reads ALL sheets into a dictionary
            # Key = sheet name, Value = DataFrame
            dfs = pd.read_excel(uploaded_file, sheet_name=None)

            for sheet_name, df in dfs.items():
                # Add a clear marker so the AI can identify the sheet
                text += f"\n--- WORKSHEET: {sheet_name} ---\n"
                text += df.to_string() + "\n"
                
        elif filename.endswith('.csv') or filename.endswith('.txt'):
            stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
            text = stringio.read()

        elif filename.endswith('.json'):
            raw = uploaded_file.getvalue().decode("utf-8")
            data = json.loads(raw)
            text = json.dumps(data, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Error reading file: {e}"

    # Optional: increase limit if there are many sheets
    return text[:100000]


def fetch_text_from_url(url: str) -> str:
    """Fetches JSON from a public URL and returns pretty-printed text (max 100k chars)."""
    resp = requests.get(url, verify=False, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return json.dumps(data, indent=2, ensure_ascii=False)[:100_000]
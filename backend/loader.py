import io
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
            
    except Exception as e:
        return f"Error reading file: {e}"

    # Optional: increase limit if there are many sheets
    return text[:100000]
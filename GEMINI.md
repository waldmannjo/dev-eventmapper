# Eventmapper Project Context

## Project Overview
**Eventmapper** is a Streamlit-based application designed to automate the mapping of event codes (Statuscodes and Reasoncodes) from various document formats (PDF, XLSX, CSV, TXT) into a standardized structure. It leverages OpenAI's GPT models for structural analysis, data extraction, and semantic mapping.

## Key Features
- **Document Ingestion**: Supports PDF, Excel, CSV, and text files.
- **Structural Analysis (Step 1)**: Analyzes the document to identify relevant tables and data sources (Statuscodes vs. Reasoncodes).
- **Data Extraction (Step 2)**: Extracts raw data from selected sources using LLMs.
- **Data Merging & Transformation (Step 3)**: Merges extracted data into a unified format and allows natural language-based data transformation (e.g., "Combine Status and Reason columns").
- **AI Mapping (Step 4)**: Maps the processed codes to a target schema using a hybrid approach. This step is optimized for high accuracy through:
    - **k-NN Classification**: Direct mapping from historical data (11k+ examples) for high-confidence matches.
    - **Semantic Search**: Leveraging `text-embedding-3-large` for nuanced understanding.
    - **Cross-Encoder Re-Ranking**: Using multilingual models to verify and rank candidates.
    - **LLM Fallback**: Using GPT-5.x models with retrieval-augmented context (Few-Shot) for edge cases.

## Tech Stack
- **Frontend**: Streamlit
- **Language**: Python 3.14+
- **AI/ML**: OpenAI API (GPT-5.x, text-embedding-3-large), Sentence Transformers (Cross-Encoder), Scikit-learn.
- **Data Handling**: Pandas, OpenPyXL, PyPDF.

## Architecture
The project follows a modular structure:
- `app.py`: Main entry point and UI logic (Streamlit).
- `backend/`: Contains core logic modules.
    - `loader.py`: File reading and text extraction.
    - `analyzer.py`: Document structure analysis (identifying tables/sections).
    - `extractor.py`: LLM-based data extraction from raw text.
    - `merger.py`: Data cleaning, merging, and transformation logic.
    - `mapper.py`: Semantic mapping logic implementing the "Quality 5" strategy:
        1.  **History Utilization**: k-NN search on historical mappings for direct hits.
        2.  **Model Upgrade**: Uses `text-embedding-3-large`.
        3.  **Advanced Re-Ranking**: Multilingual Cross-Encoder logic.
        4.  **Input Cleaning**: Pre-processing of raw status codes/texts.
        5.  **Enhanced Definitions**: Uses bilingual, keyword-enriched definitions from `codes.py`.
- `codes.py`: Target code definitions, enriched with bilingual descriptions (DE/EN) and extensive keyword lists to anchor embeddings.

## Setup & Usage

### Prerequisites
- Python 3.x
- OpenAI API Key

### Installation
```bash
# Create and activate virtual environment (recommended)
python -m venv venv
# Windows
.\venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
streamlit run app.py
```

## Development Workflow
1.  **Upload**: User uploads a file.
2.  **Analysis**: App identifies potential data tables.
3.  **Selection**: User selects which tables to extract.
4.  **Extraction**: App extracts data to CSV format.
5.  **Transformation**: User can refine data using AI instructions.
6.  **Mapping**: Final mapping to target codes using the enhanced hybrid engine.

## Important Notes
- **API Costs**: The application uses various OpenAI models. Users can select specific models per step to manage performance vs. cost.
- **Debug Mode**: `app.py` includes a debug mode to bypass extraction and load a pre-prepared CSV/Excel directly into Step 3.
- **Mapping Quality**: Step 4 is heavily optimized using historical data and bilingual contexts. Ensure `codes.py` remains updated with new keywords for continuous improvement.
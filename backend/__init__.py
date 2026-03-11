# backend/__init__.py
from .loader import extract_text_from_file, fetch_text_from_url
from .analyzer import analyze_structure_step1
from .extractor import extract_data_step2, preview_csv_string
from .merger import merge_data_step3, apply_ai_transformation
from .mapper import run_mapping_step4